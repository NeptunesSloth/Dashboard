"""Host (agent) management API routes (extracted from app.py).

Add/edit/remove bot hosts, test reachability, proxy bot-config edits to an agent,
and push agent self-updates. All operator-gated. Mounted by ``app.py`` via
``include_router``. Settings routes that were historically interleaved with these
remain in ``app.py``.
"""
from __future__ import annotations

import re
import secrets
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .. import events, registry
from ..agent_client import call_agent, post_agent, put_agent
from ..config import all_devices, load_devices, save_devices
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import mask_token as _mask_token
from ..deps import resolve_device as _resolve_device

try:
    from maybot_agent import __version__ as _LATEST_AGENT_VERSION
except Exception:  # pragma: no cover
    _LATEST_AGENT_VERSION = "1.0"

router = APIRouter()


class HostIn(BaseModel):
    name: str
    url: str
    api_token: str = ""
    timeout: float | None = None
    original_name: str | None = None   # set when renaming an existing host


class HostTestIn(BaseModel):
    url: str
    api_token: str = ""
    timeout: float | None = None


class EnrollTokenIn(BaseModel):
    token: str = ""
    generate: bool = False
    clear: bool = False


class HostProjectsIn(BaseModel):
    projects: list[dict]


def _host_status_row(d: dict) -> dict:
    # /api/ping is an unauthenticated liveness check (reachability). The token is
    # enforced on /api/projects, so a reachable host with a wrong/missing token
    # surfaces as auth_error there — keep that distinction for the UI badge.
    ping = call_agent(d, "/api/ping")
    reachable = bool(ping.get("online"))
    proj = call_agent(d, "/api/projects") if reachable else {}
    auth_error = bool(proj.get("auth_error"))
    online = reachable and not auth_error
    projects, names = 0, []
    if online:
        pl = proj.get("data", [])
        if isinstance(pl, list):
            projects = len(pl)
            names = [p.get("name") for p in pl][:30]
    version = (ping.get("data") or {}).get("version") if reachable else None
    return {
        "name": d.get("name"), "url": d.get("url"), "timeout": d.get("timeout"),
        "token_masked": _mask_token(d.get("api_token", "")), "has_token": bool(d.get("api_token")),
        "online": online, "auth_error": auth_error,
        "version": version, "agent_outdated": bool(version) and version != _LATEST_AGENT_VERSION,
        "status_code": proj.get("status_code", ping.get("status_code")) if reachable else ping.get("status_code"),
        "error": (proj.get("error") if auth_error else ping.get("error")),
        "projects": projects, "project_names": names,
    }


@router.get("/api/hosts")
def hosts_list(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    devices = load_devices()
    if not devices:
        return {"hosts": []}
    with ThreadPoolExecutor(max_workers=min(len(devices), 8) or 1) as pool:
        rows = list(pool.map(_host_status_row, devices))
    return {"hosts": rows}


@router.get("/api/hosts/gen-token")
def hosts_gen_token(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"token": secrets.token_hex(32)}


@router.get("/api/hosts/enroll-token")
def hosts_enroll_token_get(x_control_token: str = Header(default="")):
    """Current self-enrollment token (for the in-app one-command installer)."""
    _check_operator(x_control_token)
    return {"configured": bool(registry.REGISTER_TOKEN), "token": registry.REGISTER_TOKEN}


@router.post("/api/hosts/enroll-token")
def hosts_enroll_token_set(body: EnrollTokenIn, x_control_token: str = Header(default="")):
    """Set / generate / clear the self-enrollment token from the dashboard."""
    _check_operator(x_control_token)
    if body.clear:
        tok = ""
    elif body.generate or not body.token.strip():
        tok = secrets.token_hex(32)
    else:
        tok = body.token.strip()
    registry.set_register_token(tok)
    return {"ok": True, "configured": bool(registry.REGISTER_TOKEN), "token": registry.REGISTER_TOKEN}


@router.post("/api/hosts/test")
def hosts_test(body: HostTestIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    url = (body.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "url must start with http:// or https://")
    d = {"url": url, "api_token": body.api_token or "", "timeout": body.timeout or 5}
    ping = call_agent(d, "/api/ping")
    reachable = bool(ping.get("online"))
    proj = call_agent(d, "/api/projects") if reachable else {}
    auth_error = bool(proj.get("auth_error"))
    online = reachable and not auth_error
    res = {"online": online, "auth_error": auth_error,
           "status_code": proj.get("status_code", ping.get("status_code")) if reachable else ping.get("status_code"),
           "error": (proj.get("error") if auth_error else ping.get("error")),
           "projects": 0, "project_names": []}
    if online:
        pl = proj.get("data", [])
        if isinstance(pl, list):
            res["projects"] = len(pl)
            res["project_names"] = [p.get("name") for p in pl][:30]
    return res


@router.get("/api/hosts/{name}/projects")
def host_projects_get(name: str, x_control_token: str = Header(default="")):
    """Read a host's editable bot config (proxied to the agent)."""
    _check_operator(x_control_token)
    d = _resolve_device(name)
    r = call_agent(d, "/api/projects/config")
    if not r.get("online"):
        raise HTTPException(502, r.get("error") or "agent unreachable")
    data = r.get("data") or {}
    return {"projects": data.get("projects", []) if isinstance(data, dict) else []}


@router.put("/api/hosts/{name}/projects")
def host_projects_put(name: str, body: HostProjectsIn, x_control_token: str = Header(default="")):
    """Replace a host's bot config from the dashboard — no SSH/YAML editing."""
    _check_operator(x_control_token)
    d = _resolve_device(name)
    r = put_agent(d, "/api/projects/config", {"projects": body.projects})
    if not r.get("online"):
        # The agent rejects bad config with 400; surface its message verbatim.
        code = r.get("status_code")
        raise HTTPException(400 if code == 400 else 502, r.get("error") or "agent unreachable")
    # The audit middleware already records this mutating call.
    events.publish("hosts", {"event": "bots_saved", "name": name})
    return r.get("data") or {"projects": body.projects}


@router.get("/api/hosts/{name}/discover")
def host_discover(name: str, x_control_token: str = Header(default="")):
    """Heuristic bot candidates from the host, to seed the editor."""
    _check_operator(x_control_token)
    d = _resolve_device(name)
    r = call_agent(d, "/api/discover")
    if not r.get("online"):
        raise HTTPException(502, r.get("error") or "agent unreachable")
    data = r.get("data") or {}
    return {"candidates": data.get("candidates", []) if isinstance(data, dict) else []}


@router.post("/api/hosts/{name}/update")
def host_update(name: str, x_control_token: str = Header(default="")):
    """Push an agent self-update to one host (re-pull bundle + restart)."""
    _check_operator(x_control_token)
    d = _resolve_device(name)
    r = post_agent(d, "/api/self-update", timeout=120)
    if not r.get("online"):
        raise HTTPException(502, r.get("error") or "agent unreachable")
    return r.get("data") or {"ok": True}


@router.post("/api/fleet/update")
def fleet_update(x_control_token: str = Header(default="")):
    """Update every reachable host whose agent is behind the bundled version."""
    _check_operator(x_control_token)
    updated, skipped = [], []
    for d in all_devices():
        ping = call_agent(d, "/api/ping")
        ver = (ping.get("data") or {}).get("version")
        if ping.get("online") and ver and ver != _LATEST_AGENT_VERSION:
            res = post_agent(d, "/api/self-update", timeout=120)
            (updated if res.get("online") else skipped).append(d.get("name"))
        else:
            skipped.append(d.get("name"))
    return {"latest": _LATEST_AGENT_VERSION, "updated": updated, "skipped": skipped}


@router.post("/api/hosts")
def hosts_save(body: HostIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "host name may contain letters, numbers, dashes and underscores only")
    url = (body.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "url must start with http:// or https://")
    devices = load_devices()
    entry = {"name": name, "url": url, "api_token": (body.api_token or "").strip()}
    if body.timeout:
        entry["timeout"] = float(body.timeout)
    if body.original_name:                                   # editing an existing host
        idx = next((i for i, d in enumerate(devices) if d.get("name") == body.original_name.strip()), None)
        if idx is None:
            raise HTTPException(404, "host not found")
        if any(d.get("name") == name for i, d in enumerate(devices) if i != idx):
            raise HTTPException(409, f"a host named '{name}' already exists")
        # keep the existing token if the form left it blank (masked, unchanged)
        if not entry["api_token"] and devices[idx].get("api_token"):
            entry["api_token"] = devices[idx]["api_token"]
        devices[idx] = entry
    else:                                                    # adding a new host
        if any(d.get("name") == name for d in devices):
            raise HTTPException(409, f"a host named '{name}' already exists")
        devices.append(entry)
    save_devices(devices)
    events.publish("hosts", {"event": "saved", "name": name})
    return {"ok": True, "name": name}


@router.delete("/api/hosts/{name}")
def hosts_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid host name")
    devices = load_devices()
    remaining = [d for d in devices if d.get("name") != name]
    if len(remaining) == len(devices):
        raise HTTPException(404, "host not found")
    save_devices(remaining)
    events.publish("hosts", {"event": "removed", "name": name})
    return {"ok": True}
