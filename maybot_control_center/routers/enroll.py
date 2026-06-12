"""Agent enrollment & onboarding routes (extracted from app.py): agent
auto-registration/deregistration, the registry snapshot, the downloadable agent
bundle + one-command installers, and the first-run setup checklist.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .. import agents, authz, events, notify, registry
from ..config import load_devices
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


# ---- Agent auto-registration ----
class RegisterIn(BaseModel):
    name: str
    url: str
    api_token: str = ""
    timeout: float | None = None


@router.post("/api/agents/register")
def agents_register(body: RegisterIn, x_control_token: str = Header(default=""),
                    x_register_token: str = Header(default="")):
    if registry.REGISTER_TOKEN and x_register_token and secrets.compare_digest(x_register_token, registry.REGISTER_TOKEN):
        pass
    else:
        _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.name or ""):
        raise HTTPException(400, "invalid agent name")
    if not (body.url or "").startswith(("http://", "https://")):
        raise HTTPException(400, "url must start with http:// or https://")
    rec = registry.register(body.name, body.url, body.api_token, body.timeout)
    # A host just self-enrolled — push it to live dashboards instantly.
    events.publish("hosts", {"event": "enrolled", "name": body.name})
    return rec


class DeregisterIn(BaseModel):
    name: str


@router.post("/api/agents/deregister")
def agents_deregister(body: DeregisterIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"deregistered": registry.deregister((body.name or "").strip())}


@router.get("/api/registry")
def registry_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return registry.snapshot()


@router.get("/agent-bundle.tgz")
def agent_bundle():
    """A tarball of the agent (maybot_agent + slim deps) so a host can install it
    straight from the dashboard — no git clone, no registry. Served to the
    one-command installer below."""
    import io, tarfile, time as _t
    buf = io.BytesIO()
    reqs = ("fastapi==0.136.3\nuvicorn==0.48.0\npyyaml==6.0.3\nrequests==2.34.2\n"
            "psutil==7.2.2\nhttpx>=0.27\nwebsockets>=12\n")
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        pkg = os.path.join(os.path.dirname(__file__), "..", "..", "maybot_agent")
        tar.add(os.path.realpath(pkg), arcname="maybot_agent",
                filter=lambda ti: None if ("__pycache__" in ti.name or ti.name.endswith(".pyc")) else ti)
        for name, text in (("requirements-agent.txt", reqs),):
            data = text.encode()
            info = tarfile.TarInfo(name); info.size = len(data); info.mtime = int(_t.time())
            tar.addfile(info, io.BytesIO(data))
        ex = os.path.join(os.path.dirname(__file__), "..", "..", "projects.yaml.example")
        if os.path.exists(ex):
            tar.add(os.path.realpath(ex), arcname="projects.yaml.example")
    return Response(buf.getvalue(), media_type="application/gzip")


@router.get("/install-agent.sh")
def install_agent_sh():
    return FileResponse("scripts/install-agent.sh", media_type="text/x-shellscript")


@router.get("/install-agent.ps1")
def install_agent_ps1():
    return FileResponse("scripts/install-agent.ps1", media_type="text/plain")


@router.get("/install-ai.sh")
def install_ai_sh():
    return FileResponse("scripts/install-ai.sh", media_type="text/x-shellscript")


@router.get("/install-ai.ps1")
def install_ai_ps1():
    return FileResponse("scripts/install-ai.ps1", media_type="text/plain")


@router.get("/api/setup")
def setup_status(x_control_token: str = Header(default="")):
    """Onboarding checklist state for the first-run guide."""
    _check_token(x_control_token)
    users = authz.load_users()
    members = agents.file_agents()
    devices = load_devices()
    ai = (bool(os.getenv("ANTHROPIC_API_KEY")) and any(m.get("provider") == "claude" for m in members)) \
        or bool(os.getenv("OPENAI_API_KEY")) or any(m.get("base_url") for m in members)
    steps = {
        "account": bool(users),
        "host": len(devices) > 0,
        "member": len(members) > 0,
        "ai": bool(ai),
        "notifications": len(notify.channels()) > 0,
    }
    # Action-oriented "Quick Start" checklist (get hosts + bots online and current).
    from .. import setup as setup_mod
    qs = setup_mod.checklist(devices)
    return {"steps": steps, "done": all(steps.values()),
            "counts": {"hosts": len(devices), "members": len(members), "accounts": len(users)},
            "summary": qs["summary"], "checklist": qs["steps"], "checklist_ready": qs["ready"]}
