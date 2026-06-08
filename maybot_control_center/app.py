import csv
import io
import os
import queue
import re
import secrets
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, JSONResponse, Response
from pydantic import BaseModel
from .config import load_devices, all_devices, save_devices, CONTROL_CENTER_TOKEN
from . import config as _config
from . import aggregator
from .aggregator import aggregate
from .agent_client import call_agent, post_agent
from . import history
from . import agents
from . import comms
from . import memory
from . import tools as tooling
from . import store
from . import events
from . import autonomy
from . import usage
from . import authz
from . import cultivation
from . import pills
from . import treasury
from . import quests
from . import metrics as metrics_mod
from . import scheduler
from . import reputation
from . import prophecy
from . import formations
from . import governance
from . import nightwatch
from . import spirit_root
from . import dreamscape
from . import chaos
from . import github_repo
from . import daoheart
from . import bonds
from . import lineage
from . import council_vote
from . import artifacts
from . import titles
from . import chronicle
from . import runbooks
from . import lifecycle
from . import tournament
from . import maintenance
from . import slo
from . import errorbudget
from . import meridians
from . import talismans
from . import oaths
from . import escalation
from . import taskqueue
from . import routing
from . import orchestrator
from . import autopilot
from . import sectmemory
from . import audit
from . import diagnostics
from . import inbound
from . import backup
from . import registry
from . import push
from . import command
from . import quotes
from . import broker
from . import risk
from . import botcontrol
from . import signals
from . import advisor
from . import notify
from . import pnl_history
from . import acks
from . import reports
from . import retention
from . import selfcheck

# Restore persisted state (no-op unless MAYBOT_DB is set).
store.init()
for _loader in (history.load_persisted, agents.load_persisted, comms.load_persisted,
                tooling.load_persisted, usage.load_persisted, cultivation.load_persisted,
                treasury.load_persisted, taskqueue.load_persisted, oaths.load_persisted,
                maintenance.load_persisted, autopilot.load_persisted, sectmemory.load_persisted,
                audit.load_persisted, inbound.load_persisted, registry.load_persisted,
                push.load_persisted, acks.load_persisted):
    try:
        _loader()
    except Exception:
        pass
scheduler.start()  # background cron for scheduled missions (no-op without schedules.yaml)
talismans.start()  # background synthetic uptime probes (no-op without talismans.yaml)
autopilot.start()  # the Sect Leader's autonomous ops loop (no-op unless MAYBOT_AUTOPILOT=1)
reports.start()    # periodic summary reports (no-op unless MAYBOT_REPORT_INTERVAL_HOURS>0)
retention.start()  # data-retention pruning + scheduled backups (no-op unless configured)

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
# A silence target: "*", "device:*", or "device:project".
_SAFE_TARGET = re.compile(r'^(\*|[a-zA-Z0-9_\-\.]{1,128}:(\*|[a-zA-Z0-9_\-\.]{1,128}))$')
_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}

app = FastAPI(title="maybot-control-center")


@app.middleware("http")
async def _rate_limit(request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/stream"):
        key = request.headers.get("x-control-token") or (request.client.host if request.client else "anon")
        if not authz.allow_request(key):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    response = await call_next(request)
    # Always serve fresh UI: tell browsers to revalidate static assets/pages so a
    # redeploy never leaves a stale app.js/style.css (and the rail/reskin) cached.
    path = request.url.path
    if not path.startswith("/api/") and (path == "/" or path.endswith((".js", ".css", ".html"))
                                         or path in ("/console", "/login", "/chamber", "/trade", "/treasury")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    # Self-observability: count served API requests (and 5xx errors).
    if request.url.path.startswith("/api/"):
        try:
            selfcheck.note_request(response.status_code)
        except Exception:
            pass
    # Operator audit: record every mutating API call (who, what, outcome).
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and request.url.path.startswith("/api/") \
            and not request.url.path.startswith("/api/audit"):
        try:
            actor = authz.name_for(request.headers.get("x-control-token", ""))
            audit.record(actor, f"{request.method} {request.url.path}", status=response.status_code)
        except Exception:
            pass
    return response


def _role(token: str) -> str:
    r = authz.role_for(token)
    if r is None:
        raise HTTPException(status_code=401, detail="invalid control token")
    return r


def _check_token(x_control_token: str = Header(default="")):
    """Any valid role (viewer or operator)."""
    _role(x_control_token)


def _check_operator(x_control_token: str = Header(default="")):
    """Operator role required for mutating actions."""
    if _role(x_control_token) != "operator":
        raise HTTPException(status_code=403, detail="operator role required")


def _check_project_access(token: str, device: str, project: str):
    """Per-project ACL gate (no-op unless a user declares a `projects` list)."""
    if not authz.can_access_project(token, device, project):
        raise HTTPException(status_code=403, detail="not authorized for this project")


def _resolve_device(device_name: str):
    device = next((d for d in all_devices() if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    return device


@app.get("/api/meta")
def meta():
    """Non-secret UI hints: whether auth is configured (for the setup warning),
    and which optional subsystems are on."""
    auth_configured = bool(authz.load_users()) or bool(CONTROL_CENTER_TOKEN)
    return {"auth_configured": auth_configured, "autopilot_enabled": autopilot.ENABLED,
            "public_status": status_page.enabled()}


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(all_devices())


@app.get("/api/logs/{device_name}/{project_name}")
def proxy_logs(device_name: str, project_name: str, level: str = Query(default="ALL"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    if level.upper() not in _VALID_LEVELS:
        raise HTTPException(400, f"invalid log level '{level}'")
    result = call_agent(_resolve_device(device_name), f"/api/projects/{project_name}/logs?level={level.upper()}")
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


@app.get("/api/diagnose/{device_name}/{project_name}")
def diagnose_project(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    """Heuristic root-cause analysis of a bot's recent error logs + status."""
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    from . import diagnosis
    return diagnosis.diagnose(device_name, project_name)


@app.get("/api/history/{device_name}/{project_name}")
def project_history(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    return {"history": history.get(device_name, project_name)}


# ---------------------------------------------------------------------------
# Host (agent) management — add/edit/remove bot hosts from the dashboard so the
# operator never has to hand-edit devices.yaml. All operator-gated.
# ---------------------------------------------------------------------------
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


def _mask_token(tok: str) -> str:
    t = tok or ""
    if len(t) <= 6:
        return "•" * len(t)
    return t[:3] + "•" * 6 + t[-3:]


def _host_status_row(d: dict) -> dict:
    ping = call_agent(d, "/api/ping")
    online = bool(ping.get("online"))
    projects, names = 0, []
    if online:
        pl = call_agent(d, "/api/projects").get("data", [])
        if isinstance(pl, list):
            projects = len(pl)
            names = [p.get("name") for p in pl][:30]
    return {
        "name": d.get("name"), "url": d.get("url"), "timeout": d.get("timeout"),
        "token_masked": _mask_token(d.get("api_token", "")), "has_token": bool(d.get("api_token")),
        "online": online, "auth_error": bool(ping.get("auth_error")),
        "status_code": ping.get("status_code"), "error": ping.get("error"),
        "projects": projects, "project_names": names,
    }


@app.get("/api/hosts")
def hosts_list(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    from concurrent.futures import ThreadPoolExecutor
    devices = load_devices()
    if not devices:
        return {"hosts": []}
    with ThreadPoolExecutor(max_workers=min(len(devices), 8) or 1) as pool:
        rows = list(pool.map(_host_status_row, devices))
    return {"hosts": rows}


@app.get("/api/hosts/gen-token")
def hosts_gen_token(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"token": secrets.token_hex(32)}


@app.post("/api/hosts/test")
def hosts_test(body: HostTestIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    url = (body.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "url must start with http:// or https://")
    d = {"url": url, "api_token": body.api_token or "", "timeout": body.timeout or 5}
    ping = call_agent(d, "/api/ping")
    res = {"online": bool(ping.get("online")), "auth_error": bool(ping.get("auth_error")),
           "status_code": ping.get("status_code"), "error": ping.get("error"),
           "projects": 0, "project_names": []}
    if res["online"]:
        pl = call_agent(d, "/api/projects").get("data", [])
        if isinstance(pl, list):
            res["projects"] = len(pl)
            res["project_names"] = [p.get("name") for p in pl][:30]
    return res


@app.post("/api/hosts")
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
    return {"ok": True, "name": name}


@app.delete("/api/hosts/{name}")
def hosts_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid host name")
    devices = load_devices()
    remaining = [d for d in devices if d.get("name") != name]
    if len(remaining) == len(devices):
        raise HTTPException(404, "host not found")
    save_devices(remaining)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Account management — create/remove dashboard users from the UI (operator only).
# No public sign-up: an operator provisions accounts here, each gets a token.
# ---------------------------------------------------------------------------
class AccountIn(BaseModel):
    name: str
    role: str = "viewer"
    token: str = ""
    projects: list[str] | None = None
    original_name: str | None = None


@app.get("/api/accounts")
def accounts_list(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    out = [{
        "name": u.get("name"), "role": u.get("role", "viewer"),
        "token_masked": _mask_token(u.get("token", "")), "has_token": bool(u.get("token")),
        "projects": u.get("projects") or [],
    } for u in authz.load_users()]
    return {"accounts": out, "auth_active": bool(authz.load_users())}


@app.post("/api/accounts")
def accounts_save(body: AccountIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "account name may contain letters, numbers, dashes and underscores only")
    role = body.role if body.role in ("operator", "viewer") else "viewer"
    users = authz.load_users()
    was_empty = not users
    token = (body.token or "").strip() or secrets.token_hex(32)
    entry = {"name": name, "token": token, "role": role}
    if body.projects:
        entry["projects"] = body.projects
    if body.original_name:
        idx = next((i for i, u in enumerate(users) if u.get("name") == body.original_name.strip()), None)
        if idx is None:
            raise HTTPException(404, "account not found")
        if any(u.get("name") == name for i, u in enumerate(users) if i != idx):
            raise HTTPException(409, f"an account named '{name}' already exists")
        if not (body.token or "").strip() and users[idx].get("token"):
            entry["token"] = users[idx]["token"]
        users[idx] = entry
    else:
        if any(u.get("name") == name for u in users):
            raise HTTPException(409, f"an account named '{name}' already exists")
        users.append(entry)
    authz.save_users(users)
    # `first` tells the UI to adopt this token immediately (avoids a bootstrap lockout
    # the moment auth turns on); `token` is returned once so it can be copied.
    return {"ok": True, "name": name, "role": role, "token": entry["token"], "first": was_empty}


@app.delete("/api/accounts/{name}")
def accounts_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid account name")
    users = authz.load_users()
    remaining = [u for u in users if u.get("name") != name]
    if len(remaining) == len(users):
        raise HTTPException(404, "account not found")
    # never strand the dashboard with users but no operator (would lock everyone out)
    if remaining and not any(u.get("role") == "operator" for u in remaining):
        raise HTTPException(409, "can't remove the last operator account")
    authz.save_users(remaining)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Sect Member management — add/edit/remove members (agents.yaml) from the UI.
# ---------------------------------------------------------------------------
class MemberIn(BaseModel):
    name: str
    role: str = "Disciple"
    provider: str = "ollama"
    model: str = ""
    base_url: str = ""
    persona: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    original_name: str | None = None

_PROVIDERS = {"ollama", "openai_compatible", "claude", "openai"}


@app.get("/api/members/profiles")
def members_profiles(x_control_token: str = Header(default="")):
    """Persistent, evolving RPG dossiers for the current roster (the sect sim)."""
    _check_token(x_control_token)
    from . import sectsim
    return {"profiles": sectsim.profiles(agents.snapshot())}


class MemberTestIn(BaseModel):
    provider: str = "ollama"
    model: str = ""
    base_url: str = ""


@app.post("/api/members/test")
def members_test(body: MemberTestIn, x_control_token: str = Header(default="")):
    """Send a tiny prompt to a member's AI backend to confirm it actually answers."""
    _check_operator(x_control_token)
    if not (body.model or "").strip():
        raise HTTPException(400, "a model is required")
    probe = {"name": "(test)", "provider": (body.provider or "ollama"), "model": body.model.strip(),
             "base_url": (body.base_url or "").strip(), "max_tokens": 16, "temperature": 0}
    import time as _t
    t0 = _t.time()
    ok, text, err = agents._chat(probe, [{"role": "user", "content": "Reply with the single word: pong"}])
    return {"ok": bool(ok), "reply": (text or "").strip()[:200], "error": err, "latency_ms": int((_t.time() - t0) * 1000)}


@app.post("/api/members/seed")
def members_seed(x_control_token: str = Header(default="")):
    """One-click starter sect: a few Hermes-backed members (only when empty)."""
    _check_operator(x_control_token)
    if agents.file_agents():
        raise HTTPException(409, "the sect already has members")
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    starter = [
        ("Nova", "Research Analyst", "Meticulous, data-driven, concise. Answers in tight bullet points."),
        ("Forge", "Builder", "Pragmatic engineer; proposes the smallest implementation that works."),
        ("Sage", "Reviewer", "Careful reviewer; checks claims and gives a clear go / no-go."),
        ("Atlas", "Strategist", "Weighs trade-offs explicitly and gives one clear recommendation."),
    ]
    roster = [{"name": n, "role": r, "provider": "ollama", "base_url": base,
               "model": "nous-hermes", "persona": p, "max_tokens": 512} for n, r, p in starter]
    agents.save_agents(roster)
    return {"ok": True, "count": len(roster)}


@app.post("/api/projects/{device_name}/{project_name}/explain")
def explain_project(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    """Plain-English status + recommendation for a bot: heuristic diagnosis,
    elaborated by a member if an LLM backend is configured."""
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    from . import diagnosis
    d = diagnosis.diagnose(device_name, project_name)
    # try to elaborate with the first member that has a usable backend
    explanation = None
    for a in agents.file_agents():
        if (a.get("base_url") or a.get("provider") in ("claude", "anthropic")):
            facts = (f"Bot '{project_name}' on '{device_name}'. Health: {d.get('health')}. "
                     f"Findings: {[f['signal'] for f in d.get('findings', [])] or 'none'}. "
                     f"Summary: {d.get('summary')}")
            ok, text, _ = agents._chat({**a, "max_tokens": 220, "temperature": 0.3}, [
                {"role": "system", "content": "You are a terse trading-ops engineer. In 2-3 sentences, explain what's going on with this bot and the single most useful next action."},
                {"role": "user", "content": facts}])
            if ok and text:
                explanation = text.strip()
            break
    return {**d, "explanation": explanation}


@app.get("/api/members")
def members_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    out = [{
        "name": a.get("name"), "role": a.get("role", ""), "provider": a.get("provider", ""),
        "model": a.get("model", ""), "base_url": a.get("base_url", ""),
        "persona": a.get("persona") or a.get("system") or "",
        "temperature": a.get("temperature"), "max_tokens": a.get("max_tokens"),
    } for a in agents.file_agents()]
    return {"members": out}


@app.post("/api/members")
def members_save(body: MemberIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "member name may contain letters, numbers, dashes and underscores only")
    provider = body.provider if body.provider in _PROVIDERS else "ollama"
    if not (body.model or "").strip():
        raise HTTPException(400, "a model is required")
    if provider in ("ollama", "openai_compatible", "openai") and not (body.base_url or "").strip() and provider != "openai":
        raise HTTPException(400, "this provider needs a base_url (e.g. http://127.0.0.1:11434)")
    entry: dict = {"name": name, "role": (body.role or "Disciple").strip(), "provider": provider,
                   "model": body.model.strip()}
    if body.base_url.strip():
        entry["base_url"] = body.base_url.strip()
    if body.persona.strip():
        entry["persona"] = body.persona.strip()
    if body.temperature is not None:
        entry["temperature"] = float(body.temperature)
    if body.max_tokens is not None:
        entry["max_tokens"] = int(body.max_tokens)
    roster = agents.file_agents()
    if body.original_name:
        idx = next((i for i, a in enumerate(roster) if a.get("name") == body.original_name.strip()), None)
        if idx is None:
            raise HTTPException(404, "member not found")
        if any(a.get("name") == name for i, a in enumerate(roster) if i != idx):
            raise HTTPException(409, f"a member named '{name}' already exists")
        roster[idx] = entry
    else:
        if any(a.get("name") == name for a in roster):
            raise HTTPException(409, f"a member named '{name}' already exists")
        roster.append(entry)
    agents.save_agents(roster)
    return {"ok": True, "name": name}


@app.delete("/api/members/{name}")
def members_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid member name")
    roster = agents.file_agents()
    remaining = [a for a in roster if a.get("name") != name]
    if len(remaining) == len(roster):
        raise HTTPException(404, "member not found")
    agents.save_agents(remaining)
    return {"ok": True}


@app.post("/api/action/{device_name}/{project_name}/{action}")
def proxy_action(device_name: str, project_name: str, action: str, force: bool = Query(default=False),
                 x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, f"unknown action '{action}'; must be one of {sorted(_VALID_ACTIONS)}")
    # Heavenly Decree: a project that burned its error budget is frozen against
    # state-changing actions until reliability recovers (override with ?force=1).
    if action in {"start", "stop"} and not force and errorbudget.is_frozen(device_name, project_name):
        raise HTTPException(423, f"'{project_name}' is under a Heavenly Decree (error budget exhausted); "
                                 f"reliability work only, or retry with force=true")
    agent_path = "run-tests" if action == "run-tests" else action
    timeout = _ACTION_TIMEOUTS[action]
    result = post_agent(_resolve_device(device_name), f"/api/projects/{project_name}/{agent_path}", timeout=timeout)
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


class TaskIn(BaseModel):
    task: str
    critical: bool = False        # critical work the Sect Leader handles directly
    project: str | None = None    # optional project this task acts on (personal guard)
    device: str | None = None
    repo: str | None = None       # optional GitHub repo (owner/name) for context
    issue: int | None = None      # optional issue/PR number


@app.get("/api/agents")
def list_agents(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"agents": agents.snapshot()}


@app.get("/api/agents/{name}")
def agent_detail(name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    detail = agents.get_agent(name)
    if detail is None:
        raise HTTPException(404, "agent not found")
    return detail


class DelegateIn(BaseModel):
    to: str
    task: str


@app.post("/api/agents/{name}/delegate")
def agent_delegate(name: str, body: DelegateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name) or not _SAFE_NAME.match(body.to or ""):
        raise HTTPException(400, "invalid agent name")
    task = (body.task or "").strip()
    if not task:
        raise HTTPException(400, "task must not be empty")
    if len(task) > 4000:
        raise HTTPException(400, "task too long (max 4000 chars)")
    try:
        return agents.delegate(name, body.to, task)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except KeyError:
        raise HTTPException(404, "agent not found")


def _bot_context(device: str | None, project: str | None, log_lines: int = 12) -> str:
    """A compact live snapshot of one bot (status, PnL metrics, recent log tail)
    so a dispatched disciple can see what's actually going on with it."""
    if not project:
        return ""
    devices = all_devices()
    found, dev = None, None
    for d in devices:
        if device and d.get("name") != device:
            continue
        pl = call_agent(d, "/api/projects").get("data", [])
        if isinstance(pl, list):
            match = next((p for p in pl if p.get("name") == project), None)
            if match:
                found, dev = match, d
                break
        if device:
            break
    if not found or not dev:
        return ""
    m = found.get("metrics", {}) or {}
    lines = [f"### Live status — bot '{project}' on host '{dev.get('name')}'",
             f"- type: {found.get('type')} · status: {found.get('status')} · health: {found.get('health')}"]
    if found.get("type") == "trading_bot":
        for key, label in (("profit_today", "PnL today"), ("profit_this_week", "PnL this week"),
                           ("realized_pnl", "realized PnL"), ("unrealized_pnl", "unrealized PnL"),
                           ("open_positions", "open positions"), ("open_exposure", "open exposure"),
                           ("trades_today", "trades today"), ("fill_rate", "fill rate"),
                           ("last_trade_time", "last trade")):
            v = m.get(key)
            if v not in (None, "", "unknown"):
                lines.append(f"- {label}: {v}")
    for a in (found.get("alerts") or [])[:4]:
        lines.append(f"- alert: {a}")
    lg = call_agent(dev, f"/api/projects/{project}/logs?level=ALL").get("data", {})
    tail = lg.get("lines") if isinstance(lg, dict) else None
    if isinstance(tail, list) and tail:
        lines.append("\nRecent log tail:\n```")
        lines.extend(str(x) for x in tail[-log_lines:])
        lines.append("```")
    return "\n".join(lines)


@app.post("/api/agents/{name}/task")
def assign_agent_task(name: str, body: TaskIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    task = (body.task or "").strip()
    if not task:
        raise HTTPException(400, "task must not be empty")
    if len(task) > 4000:
        raise HTTPException(400, "task too long (max 4000 chars)")
    # The Ancestor's personal bot projects are off-limits to disciples.
    if body.project and governance.is_personal_project(body.project, body.device):
        raise HTTPException(403, f"'{body.project}' is the Ancestor's personal project — disciples may not be assigned to it")
    # Optional GitHub reference is prepended as context for the disciple.
    if body.repo:
        if not _SAFE_NAME.match(body.repo.replace("/", "_")):
            raise HTTPException(400, "invalid repo name")
        ref = github_repo.task_reference(body.repo, body.issue)
        if ref:
            task = f"{ref}\n\n{task}"
    # When the task is tied to a bot, prepend that bot's live status + recent logs
    # so the disciple can act on what's actually happening with it.
    if body.project:
        try:
            botctx = _bot_context(body.device, body.project)
            if botctx:
                task = f"{botctx}\n\n---\n\n{task}"
        except Exception:
            pass  # never let an observability lookup block dispatch
    # The Sect Leader oversees: routine work is routed to a deputy Elder.
    executor, delegated_from = governance.route_task(name, body.critical)
    try:
        snap = agents.assign_task(executor, task)
    except KeyError:
        raise HTTPException(404, "agent not found")
    if delegated_from:
        snap = dict(snap)
        snap["oversight"] = {"leader": delegated_from, "delegated_to": executor,
                             "note": "the Sect Leader oversees; routine work was passed to a deputy"}
    return snap


class MissionIn(BaseModel):
    goal: str
    participants: list[str] = []
    rounds: int = 2


@app.get("/api/comms")
def comms_feed(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"feed": comms.get_feed(max(1, min(limit, 200))), "status": comms.status()}


@app.post("/api/comms/mission")
def comms_mission(body: MissionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    goal = (body.goal or "").strip()
    if not goal:
        raise HTTPException(400, "goal required")
    if len(goal) > 2000:
        raise HTTPException(400, "goal too long (max 2000 chars)")
    parts = [p for p in body.participants if _SAFE_NAME.match(p or "")]
    try:
        return comms.start_mission(goal, parts, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/memory")
def memory_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "subdir": memory.SUBDIR}


@app.get("/api/memory/search")
def memory_search(q: str = Query(default=""), limit: int = Query(default=5), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "results": memory.search(q, max(1, min(limit, 20)))}


@app.get("/api/memory/note")
def memory_note(path: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if len(path) > 512:
        raise HTTPException(400, "path too long")
    content = memory.read_note(path)
    if content is None:
        raise HTTPException(404, "note not found")
    return {"path": path, "content": content}


class ToolRunIn(BaseModel):
    tool: str
    args: dict = {}


@app.get("/api/tools")
def tools_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": tooling.enabled(), "tools": tooling.tool_summaries(),
            "calls": tooling.list_calls(), "autonomy": autonomy.status()}


@app.get("/api/tools/audit")
def tools_audit(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if store.enabled():
        return {"persisted": True, "calls": store.load_tool_calls(500)}
    return {"persisted": False, "calls": tooling.list_calls(200)}


@app.post("/api/autonomy/pause")
def autonomy_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(True)


@app.post("/api/autonomy/resume")
def autonomy_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(False)


@app.post("/api/tools/run")
def tools_run(body: ToolRunIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.tool or ""):
        raise HTTPException(400, "invalid tool name")
    try:
        call = tooling.request_tool("operator", body.tool, body.args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    # Operator both requests and approves — run it now if it's still pending.
    if call.get("status") == "pending":
        call = tooling.approve(call["id"])
    return call


@app.post("/api/tools/{call_id}/approve")
def tools_approve(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.approve(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@app.post("/api/tools/{call_id}/deny")
def tools_deny(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.deny(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@app.get("/api/usage")
def usage_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.snapshot()


@app.get("/api/usage/series")
def usage_series(hours: int = Query(default=24), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.series(max(1, min(hours, 336)))


@app.get("/api/budget")
def budget_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    from . import budget
    return budget.snapshot()


@app.get("/api/cultivation")
def cultivation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return cultivation.snapshot()


@app.get("/api/reputation")
def reputation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return reputation.snapshot()


@app.get("/api/prophecy")
def prophecy_omens(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"omens": prophecy.divine()}


@app.get("/api/formations")
def formations_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": formations.catalog()}


class FormationIn(BaseModel):
    formation: str
    goal: str


@app.post("/api/formations/run")
def formations_run(body: FormationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return comms.start_formation(body.formation, body.goal)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/governance")
def governance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return governance.snapshot()


class ChallengeIn(BaseModel):
    challenger: str


@app.post("/api/governance/challenge")
def governance_challenge(body: ChallengeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.challenger or ""):
        raise HTTPException(400, "invalid challenger name")
    try:
        return governance.challenge(body.challenger)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class LeaderIn(BaseModel):
    leader: str | None = None     # None releases the role back to merit
    pinned: bool = True


@app.post("/api/governance/leader")
def governance_set_leader(body: LeaderIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # Ancestor authority
    if body.leader is not None and not _SAFE_NAME.match(body.leader):
        raise HTTPException(400, "invalid leader name")
    try:
        return governance.set_leader(body.leader, body.pinned)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class SpecialtyIn(BaseModel):
    agent: str
    specialty: str


@app.post("/api/governance/specialty")
def governance_specialty(body: SpecialtyIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        return governance.choose_specialty(body.agent, body.specialty)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class StrikeDownIn(BaseModel):
    agent: str
    reason: str = ""


@app.post("/api/governance/strike-down")
def governance_strike_down(body: StrikeDownIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # only the Ancestor may strike a disciple down
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        new = lifecycle.strike_down(body.agent, body.reason)
        return {"struck_down": body.agent, "replacement": new["name"]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/tournament")
def tournament_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return tournament.snapshot()


@app.post("/api/tournament/start")
def tournament_start(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # the Ancestor calls the Grand Tournament
    try:
        return tournament.hold()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/governance/inbox")
def governance_inbox(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"messages": governance.inbox(max(1, min(limit, 200)))}


class AncestorMsgIn(BaseModel):
    sender: str
    text: str


@app.post("/api/governance/message")
def governance_message(body: AncestorMsgIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.sender or ""):
        raise HTTPException(400, "invalid sender name")
    try:
        return governance.message_ancestor(body.sender, body.text)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Night-Watch (on-call rotation + auto-triage) ----
@app.get("/api/nightwatch")
def nightwatch_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return nightwatch.status()


class RotationIn(BaseModel):
    names: list[str] = []


@app.post("/api/nightwatch/rotation")
def nightwatch_rotation(body: RotationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    names = [n for n in body.names if _SAFE_NAME.match(n or "")]
    return nightwatch.set_rotation(names)


@app.post("/api/nightwatch/{record_id}/handled")
def nightwatch_handled(record_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"resolved": nightwatch.handled(record_id)}


# ---- Spirit-Root assessment (capability benchmarking) ----
@app.get("/api/spirit-root")
def spirit_root_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"profiles": spirit_root.snapshot(), "probes": spirit_root.PROBES,
            "baseline": spirit_root.BASELINE_PROBES}


class AssessIn(BaseModel):
    agent: str
    results: list[dict] = []


@app.post("/api/spirit-root/assess")
def spirit_root_assess(body: AssessIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    return spirit_root.assess(body.agent, body.results)


# ---- Dreamscape dry-run (formation plan preview) ----
class DreamIn(BaseModel):
    formation: str
    goal: str


@app.post("/api/dreamscape/preview")
def dreamscape_preview(body: DreamIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return dreamscape.preview(body.formation, body.goal)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Tribulation Trials (chaos engineering) ----
@app.get("/api/chaos")
def chaos_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return chaos.status()


class SummonIn(BaseModel):
    target: str
    kind: str
    disciple: str | None = None
    inject: bool = False          # actively inject the fault via a guarded tool


@app.post("/api/chaos/summon")
def chaos_summon(body: SummonIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if body.disciple and not _SAFE_NAME.match(body.disciple):
        raise HTTPException(400, "invalid disciple name")
    try:
        return chaos.summon(body.target, body.kind, body.disciple, inject=body.inject)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class ResolveIn(BaseModel):
    recovered: bool
    recovery_seconds: float | None = None


@app.post("/api/chaos/{trial_id}/resolve")
def chaos_resolve(trial_id: int, body: ResolveIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return chaos.resolve(trial_id, body.recovered, body.recovery_seconds)
    except KeyError:
        raise HTTPException(404, "trial not found")


# ---- GitHub repos (tracked as projects) ----
@app.get("/api/github")
def github_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": github_repo.enabled(), "repos": github_repo.collect() if github_repo.enabled() else []}


# ---- Dao-Heart drift detection ----
@app.get("/api/daoheart")
def daoheart_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"drift": daoheart.snapshot()}


# ---- Karmic-bond pairs ----
@app.get("/api/bonds")
def bonds_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return bonds.snapshot()


class BondIn(BaseModel):
    a: str
    b: str


@app.post("/api/bonds/bind")
def bonds_bind(body: BondIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.a or "") or not _SAFE_NAME.match(body.b or ""):
        raise HTTPException(400, "invalid disciple name")
    try:
        return bonds.bind(body.a, body.b)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class UnbondIn(BaseModel):
    agent: str


@app.post("/api/bonds/unbind")
def bonds_unbind(body: UnbondIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid disciple name")
    return {"unbound": bonds.unbind(body.agent)}


# ---- Lineage (knowledge graph) ----
@app.get("/api/lineage")
def lineage_graph(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return lineage.graph()


# ---- Merit-weighted council vote ----
class VoteIn(BaseModel):
    question: str
    votes: dict[str, str]


@app.post("/api/council/vote")
def council_vote_run(body: VoteIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return council_vote.tally(body.question, body.votes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/council/history")
def council_history(limit: int = Query(default=25), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"history": council_vote.history(max(1, min(limit, 100)))}


# ---- Artifact vault ----
@app.get("/api/artifacts")
def artifacts_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return artifacts.snapshot()


class ForgeIn(BaseModel):
    creator: str
    name: str
    kind: str
    content: str
    description: str = ""


@app.post("/api/artifacts/forge")
def artifacts_forge(body: ForgeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.name or ""):
        raise HTTPException(400, "invalid artifact name")
    try:
        return artifacts.forge(body.creator, body.name, body.kind, body.content, body.description)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class WieldIn(BaseModel):
    agent: str
    name: str


@app.post("/api/artifacts/wield")
def artifacts_wield(body: WieldIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return artifacts.wield(body.agent, body.name)
    except KeyError:
        raise HTTPException(404, "artifact not found")


# ---- Titles & achievements ----
@app.get("/api/titles")
def titles_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": titles.catalog()}


# ---- Cultivation chronicle (per-disciple timeline) ----
@app.get("/api/chronicle")
def chronicle_recent(limit: int = Query(default=50), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"recent": chronicle.recent(max(1, min(limit, 200))), "summary": chronicle.snapshot()}


@app.get("/api/chronicle/{name}")
def chronicle_agent(name: str, limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    return {"agent": name, "timeline": chronicle.timeline(name, max(1, min(limit, 200)))}


# ---- Auto-remediation runbooks ----
@app.get("/api/runbooks")
def runbooks_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"runbooks": runbooks.catalog()}


@app.get("/api/treasury")
def treasury_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return treasury.status()


class EndowIn(BaseModel):
    amount: int


@app.post("/api/treasury/endow")
def treasury_endow(body: EndowIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    amount = int(body.amount or 0)
    if amount <= 0 or amount > 1_000_000:
        raise HTTPException(400, "amount must be 1..1000000")
    treasury.deposit(amount)
    return treasury.status()


class SeclusionIn(BaseModel):
    enter: bool = True


@app.post("/api/agents/{name}/seclusion")
def agent_seclusion(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_seclusion(name) if body.enter else cultivation.exit_seclusion(name)


@app.post("/api/agents/{name}/roaming")
def agent_roaming(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_roaming(name) if body.enter else cultivation.exit_roaming(name)


class LearnGoalIn(BaseModel):
    skill: str = ""   # empty clears the goal


@app.post("/api/agents/{name}/learn-goal")
def agent_learn_goal(name: str, body: LearnGoalIn, x_control_token: str = Header(default="")):
    """Ask a disciple to seek a specific skill on their next roam (or the closest)."""
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    if len(body.skill) > 120:
        raise HTTPException(400, "skill too long (max 120)")
    return cultivation.set_learn_goal(name, body.skill)


class TransmitIn(BaseModel):
    to: str
    skill: str


@app.post("/api/agents/{name}/transmit")
def agent_transmit(name: str, body: TransmitIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name) or not _SAFE_NAME.match(body.to or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        return agents.transmit(name, body.to, (body.skill or "").strip())
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/quests")
def quests_board(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": quests.catalog()}


class QuestIn(BaseModel):
    quest: str


@app.post("/api/agents/{name}/quest")
def agent_quest(name: str, body: QuestIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    q = quests.get(body.quest)
    if not q:
        raise HTTPException(400, "unknown quest")
    cultivation.assign_quest(name, q["reward_skill"], q["stones"])
    return agents.assign_task(name, f"[Quest: {q['name']}] {q['task']}")


class PillBuyIn(BaseModel):
    agent: str
    pill: str


@app.get("/api/pills")
def pills_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": pills.catalog(), "active": pills.active_all()}


@app.post("/api/pills/buy")
def pills_buy(body: PillBuyIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or "") or not _SAFE_NAME.match(body.pill or ""):
        raise HTTPException(400, "invalid agent or pill")
    try:
        return pills.buy(body.agent, body.pill)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class DebateIn(BaseModel):
    topic: str
    a: str
    b: str
    judge: str
    rounds: int = 2


@app.post("/api/comms/debate")
def comms_debate(body: DebateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    for n in (body.a, body.b, body.judge):
        if not _SAFE_NAME.match(n or ""):
            raise HTTPException(400, "invalid participant name")
    try:
        return comms.start_debate(body.topic, body.a, body.b, body.judge, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


class TournamentIn(BaseModel):
    topic: str
    participants: list[str] = []
    judge: str
    rounds: int = 1


@app.post("/api/comms/tournament")
def comms_tournament(body: TournamentIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    parts = [p for p in body.participants if _SAFE_NAME.match(p or "")]
    if not _SAFE_NAME.match(body.judge or ""):
        raise HTTPException(400, "invalid judge name")
    try:
        return comms.start_tournament(body.topic, parts, body.judge, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/stream")
def stream(token: str = Query(default="")):
    # EventSource can't send custom headers, so the control token comes as a query param.
    if CONTROL_CENTER_TOKEN and not secrets.compare_digest(token, CONTROL_CENTER_TOKEN):
        raise HTTPException(status_code=401, detail="invalid control token")

    def gen():
        q = events.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    yield f"data: {q.get(timeout=15)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"  # heartbeat keeps the connection alive
        finally:
            events.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- SLO / uptime ----
@app.get("/api/slo")
def slo_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return slo.snapshot(hours if hours > 0 else None)


# ---- Maintenance windows / alert silencing ----
@app.get("/api/maintenance")
def maintenance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return maintenance.snapshot()


class SilenceIn(BaseModel):
    target: str
    minutes: float = 60.0
    reason: str = ""


@app.post("/api/maintenance/silence")
def maintenance_silence(body: SilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target):
        raise HTTPException(400, "invalid target; use '*', 'device:*', or 'device:project'")
    if body.minutes > 60 * 24 * 30:
        raise HTTPException(400, "minutes too large (max 30 days)")
    return maintenance.silence(target, body.minutes, body.reason)


class UnsilenceIn(BaseModel):
    target: str


@app.post("/api/maintenance/unsilence")
def maintenance_unsilence(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"unsilenced": maintenance.unsilence((body.target or "").strip())}


# ---- Error budgets & deploy-freeze (Karmic Debt / Heavenly Decree) ----
@app.get("/api/errorbudget")
def errorbudget_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return errorbudget.snapshot(hours if hours > 0 else None)


# ---- Dependency-aware alerting (Meridian Map) ----
@app.get("/api/meridians")
def meridians_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return meridians.graph()


# ---- Synthetic uptime probes (Warding Talismans) ----
@app.get("/api/talismans")
def talismans_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return talismans.snapshot()


# ---- Incident acknowledgement & ownership (Sworn Oath) ----
@app.get("/api/oaths")
def oaths_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return oaths.snapshot()


class OathIn(BaseModel):
    target: str
    who: str = "operator"
    note: str = ""


@app.post("/api/oaths/claim")
def oaths_claim(body: OathIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target) or target == "*" or target.endswith(":*"):
        raise HTTPException(400, "claim a specific 'device:project'")
    who = (body.who or "operator").strip()
    if not _SAFE_NAME.match(who):
        raise HTTPException(400, "invalid claimant name")
    return oaths.claim(target, who, body.note)


@app.post("/api/oaths/release")
def oaths_release(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"released": oaths.release((body.target or "").strip())}


# ---- Escalation policy (Chain of Command) ----
@app.get("/api/escalation")
def escalation_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return escalation.snapshot()


# ---- Alert acknowledgement & snooze ----
@app.get("/api/alerts")
def alerts_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return acks.snapshot()


class AckIn(BaseModel):
    target: str
    who: str = "operator"
    minutes: float | None = None
    reason: str = ""


@app.post("/api/alerts/ack")
def alerts_ack(body: AckIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target) or target == "*" or target.endswith(":*"):
        raise HTTPException(400, "acknowledge a specific 'device:project'")
    who = (body.who or "operator").strip()
    if not _SAFE_NAME.match(who):
        raise HTTPException(400, "invalid actor name")
    if body.minutes is not None and (body.minutes < 0 or body.minutes > 60 * 24 * 30):
        raise HTTPException(400, "minutes out of range (0..43200)")
    return acks.ack(target, who, body.minutes, body.reason)


@app.post("/api/alerts/resolve")
def alerts_resolve(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"resolved": acks.resolve((body.target or "").strip())}


# ---- Summary reports (Daily Proclamation) ----
@app.get("/api/reports/daily")
def reports_daily(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    window = hours if hours > 0 else None
    report = reports.build(window)
    return {"report": report, "text": reports.render_text(report)}


@app.post("/api/reports/send")
def reports_send(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return reports.deliver()


# ---- Data retention & scheduled backups (Archivist) ----
@app.get("/api/retention")
def retention_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return retention.snapshot()


@app.post("/api/retention/prune")
def retention_prune(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return retention.prune_now()


@app.post("/api/backup/snapshot")
def backup_snapshot(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return retention.snapshot_now()


@app.get("/api/backup/list")
def backup_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"backups": retention.list_backups()}


# ---- Control-center self-observability ----
@app.get("/api/selfcheck")
def selfcheck_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return selfcheck.snapshot()


# ---- Setup & diagnostics / fleet health ----
@app.get("/api/diagnostics")
def diagnostics_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return diagnostics.snapshot()


# ---- Inbound alert ingestion (external systems push incidents in) ----
def _check_ingest(x_control_token: str, x_ingest_token: str):
    if inbound.INGEST_TOKEN and x_ingest_token and secrets.compare_digest(x_ingest_token, inbound.INGEST_TOKEN):
        return
    _check_operator(x_control_token)


class InboundIn(BaseModel):
    title: str
    source: str = "external"
    severity: str = "warning"
    message: str = ""
    project: str = ""
    device: str = ""


@app.post("/api/ingest/alert")
def ingest_alert(body: InboundIn, x_control_token: str = Header(default=""),
                 x_ingest_token: str = Header(default="")):
    _check_ingest(x_control_token, x_ingest_token)
    if not (body.title or "").strip():
        raise HTTPException(400, "title required")
    return inbound.ingest(body.source, body.severity, body.title, body.message, body.project, body.device)


@app.get("/api/inbound")
def inbound_feed(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return inbound.snapshot()


# ---- State backup / restore ----
@app.get("/api/backup")
def backup_export(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return backup.export()


@app.post("/api/restore")
def backup_restore(body: dict, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return backup.restore(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Agent auto-registration ----
class RegisterIn(BaseModel):
    name: str
    url: str
    api_token: str = ""
    timeout: float | None = None


@app.post("/api/agents/register")
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
    return registry.register(body.name, body.url, body.api_token, body.timeout)


class DeregisterIn(BaseModel):
    name: str


@app.post("/api/agents/deregister")
def agents_deregister(body: DeregisterIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"deregistered": registry.deregister((body.name or "").strip())}


@app.get("/api/registry")
def registry_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return registry.snapshot()


# ---- Login / signup / account ----
class LoginIn(BaseModel):
    token: str = ""
    name: str = ""
    password: str = ""


def _issue(token: str) -> dict:
    session = authz.issue_session(token)
    out = {"ok": True, "role": authz.role_for(token), "name": authz.name_for(token)}
    if session:
        out["session"] = session["session"]
        out["expires"] = session["expires"]
    return out


@app.post("/api/login")
def login(body: LoginIn, request: Request):
    key = request.client.host if request.client else "anon"
    if authz.login_blocked(key):
        raise HTTPException(429, "too many sign-in attempts — wait a few minutes and try again")
    # Name + password sign-in (preferred). Falls back to raw-token login (legacy).
    if body.name and body.password:
        u = authz.user_by_name(body.name.strip())
        if not u or not u.get("pw") or not authz.verify_password(body.password, u.get("pw", "")):
            authz.note_login_fail(key)
            raise HTTPException(401, "invalid name or password")
        authz.reset_login(key)
        if u.get("tfa") and notify.channels():
            cid, code = authz.create_2fa_challenge(u["name"])
            ch = notify.channels()[0]
            notify.send("Aegis sign-in code", f"Your 2FA code is {code} (valid 5 minutes).", level="info", kind="security")
            return {"ok": False, "pending_2fa": True, "challenge": cid, "channel": ch}
        return _issue(u["token"])
    role = authz.role_for(body.token)
    if role is None:
        authz.note_login_fail(key)
        raise HTTPException(401, "invalid token")
    authz.reset_login(key)
    return _issue(body.token)


class TwoFAIn(BaseModel):
    challenge: str = ""
    code: str = ""


@app.post("/api/login/2fa")
def login_2fa(body: TwoFAIn):
    name = authz.verify_2fa((body.challenge or "").strip(), (body.code or "").strip())
    if not name:
        raise HTTPException(401, "invalid or expired code")
    u = authz.user_by_name(name)
    if not u:
        raise HTTPException(401, "account no longer exists")
    return _issue(u["token"])


class SignupIn(BaseModel):
    name: str
    password: str


@app.post("/api/signup")
def signup(body: SignupIn):
    # Self-serve signup is allowed ONLY to claim a fresh dashboard (no accounts yet);
    # the first account becomes the owner/operator. After that, operators invite users.
    if authz.load_users():
        raise HTTPException(403, "sign-up is closed — ask an operator to create your account")
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "name may contain letters, numbers, dashes and underscores only")
    if len(body.password or "") < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    user = {"name": name, "token": secrets.token_hex(32), "role": "operator",
            "pw": authz.hash_password(body.password)}
    authz.save_users([user])
    return _issue(user["token"])


class LogoutIn(BaseModel):
    session: str = ""


@app.post("/api/logout")
def logout(body: LogoutIn):
    return {"ok": authz.revoke_session((body.session or "").strip())}


@app.get("/agent-bundle.tgz")
def agent_bundle():
    """A tarball of the agent (maybot_agent + slim deps) so a host can install it
    straight from the dashboard — no git clone, no registry. Served to the
    one-command installer below."""
    import io, tarfile, time as _t
    buf = io.BytesIO()
    reqs = "fastapi==0.136.3\nuvicorn==0.48.0\npyyaml==6.0.3\nrequests==2.34.2\npsutil==7.2.2\n"
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        pkg = os.path.join(os.path.dirname(__file__), "..", "maybot_agent")
        tar.add(os.path.realpath(pkg), arcname="maybot_agent",
                filter=lambda ti: None if ("__pycache__" in ti.name or ti.name.endswith(".pyc")) else ti)
        for name, text in (("requirements-agent.txt", reqs),):
            data = text.encode()
            info = tarfile.TarInfo(name); info.size = len(data); info.mtime = int(_t.time())
            tar.addfile(info, io.BytesIO(data))
        ex = os.path.join(os.path.dirname(__file__), "..", "projects.yaml.example")
        if os.path.exists(ex):
            tar.add(os.path.realpath(ex), arcname="projects.yaml.example")
    return Response(buf.getvalue(), media_type="application/gzip")


@app.get("/install-agent.sh")
def install_agent_sh():
    return FileResponse("scripts/install-agent.sh", media_type="text/x-shellscript")


@app.get("/install-agent.ps1")
def install_agent_ps1():
    return FileResponse("scripts/install-agent.ps1", media_type="text/plain")


@app.get("/install-ai.sh")
def install_ai_sh():
    return FileResponse("scripts/install-ai.sh", media_type="text/x-shellscript")


@app.get("/install-ai.ps1")
def install_ai_ps1():
    return FileResponse("scripts/install-ai.ps1", media_type="text/plain")


@app.get("/api/setup")
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
    return {"steps": steps, "done": all(steps.values()),
            "counts": {"hosts": len(devices), "members": len(members), "accounts": len(users)}}


@app.get("/api/account/me")
def account_me(x_control_token: str = Header(default="")):
    """Who am I — used by the account bubble and the startup auth guard.
    Never 401s; returns authed=false so the client can route to /login."""
    users = authz.load_users()
    auth_active = bool(users) or bool(CONTROL_CENTER_TOKEN)
    role = authz.role_for(x_control_token)
    if role is None:
        return {"authed": False, "auth_active": auth_active, "accounts_exist": bool(users)}
    u = authz.current_user(x_control_token)
    return {
        "authed": True, "auth_active": auth_active, "accounts_exist": bool(users),
        "open_mode": not auth_active, "name": authz.name_for(x_control_token), "role": role,
        "has_password": bool(u and u.get("pw")), "tfa": bool(u and u.get("tfa")),
        "channels": notify.channels(),
    }


class PasswordIn(BaseModel):
    old: str = ""
    new: str


@app.post("/api/account/password")
def account_password(body: PasswordIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    u = authz.current_user(x_control_token)
    if not u:
        raise HTTPException(400, "no account is associated with this session")
    if u.get("pw") and not authz.verify_password(body.old, u.get("pw", "")):
        raise HTTPException(403, "current password is incorrect")
    if len(body.new or "") < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    authz.set_password(u["name"], body.new)
    return {"ok": True}


class TwoFAToggleIn(BaseModel):
    enable: bool


@app.post("/api/account/2fa")
def account_2fa(body: TwoFAToggleIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    u = authz.current_user(x_control_token)
    if not u:
        raise HTTPException(400, "no account is associated with this session")
    if body.enable and not notify.channels():
        raise HTTPException(400, "set up a notification channel (webhook/Slack/Telegram/email) first")
    authz.set_2fa(u["name"], body.enable)
    return {"ok": True, "tfa": body.enable}


# ---- Web Push (VAPID) ----
@app.get("/api/push/key")
def push_key(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return push.public_key()


@app.post("/api/push/subscribe")
def push_subscribe(body: dict, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    try:
        return push.subscribe(body.get("subscription") or body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Operator audit log ----
@app.get("/api/audit")
def audit_log(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return audit.snapshot()


# ---- Compounding sect memory (shared knowledge) ----
@app.get("/api/sectmemory")
def sectmemory_status(q: str = Query(default=""), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if q.strip():
        return {"query": q, "results": sectmemory.search(q, 8)}
    return sectmemory.snapshot()


# ---- Autopilot (the Sect Leader's second brain) ----
@app.get("/api/autopilot")
def autopilot_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return autopilot.status()


@app.post("/api/autopilot/pause")
def autopilot_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)   # kill switch
    return autopilot.set_paused(True)


@app.post("/api/autopilot/resume")
def autopilot_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autopilot.set_paused(False)


# ---- Task board / work queue ----
@app.get("/api/tasks")
def tasks_board(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return taskqueue.board()


class NewTaskIn(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    assignee: str | None = None
    dispatch: bool = True
    project: str | None = None
    device: str | None = None


@app.post("/api/tasks")
def tasks_create(body: NewTaskIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    if len(title) > 200:
        raise HTTPException(400, "title too long (max 200)")
    if body.assignee and not _SAFE_NAME.match(body.assignee):
        raise HTTPException(400, "invalid assignee name")
    task = taskqueue.create(title, description=body.description, priority=body.priority,
                            assignee=body.assignee, project=body.project, device=body.device)
    if body.dispatch and body.assignee:
        if agents._agent_def(body.assignee) is None:
            raise HTTPException(404, "assignee not found")
        text = title + ((" — " + body.description) if body.description else "")
        agents.assign_task(body.assignee, text)
        taskqueue.link_dispatch(task["id"], body.assignee)
        task = taskqueue.get(task["id"])
    return task


class ReassignIn(BaseModel):
    assignee: str
    dispatch: bool = True


@app.post("/api/tasks/{task_id}/reassign")
def tasks_reassign(task_id: int, body: ReassignIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.assignee or ""):
        raise HTTPException(400, "invalid assignee name")
    task = taskqueue.get(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if agents._agent_def(body.assignee) is None:
        raise HTTPException(404, "assignee not found")
    taskqueue.reassign(task_id, body.assignee)
    if body.dispatch:
        text = task["title"] + ((" — " + task["description"]) if task["description"] else "")
        agents.assign_task(body.assignee, text)
        taskqueue.link_dispatch(task_id, body.assignee)
    return taskqueue.get(task_id)


class StatusIn(BaseModel):
    status: str
    result: str | None = None


@app.post("/api/tasks/{task_id}/status")
def tasks_set_status(task_id: int, body: StatusIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    valid = {"queued", "assigned", "in_progress", "done", "failed", "cancelled"}
    if body.status not in valid:
        raise HTTPException(400, f"invalid status; must be one of {sorted(valid)}")
    task = taskqueue.set_status(task_id, body.status, body.result)
    if not task:
        raise HTTPException(404, "task not found")
    return task


# ---- Assign by goal (auto-route to the best-fit disciple) ----
@app.get("/api/assign/preview")
def assign_preview(goal: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"goal": goal, "ranked": routing.rank(goal)}


class GoalIn(BaseModel):
    goal: str
    priority: str = "normal"
    dispatch: bool = True


@app.post("/api/assign/goal")
def assign_goal(body: GoalIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    goal = (body.goal or "").strip()
    if not goal:
        raise HTTPException(400, "goal required")
    if len(goal) > 4000:
        raise HTTPException(400, "goal too long (max 4000)")
    fit = routing.best_fit(goal)
    if not fit:
        raise HTTPException(409, "no eligible disciple to take this goal")
    task = taskqueue.create(goal[:200], description=goal if len(goal) > 200 else "",
                            priority=body.priority, source="goal", assignee=fit["agent"])
    if body.dispatch:
        executor, _ = governance.route_task(fit["agent"], critical=False)
        agents.assign_task(executor, goal)
        taskqueue.link_dispatch(task["id"], executor)
        task = taskqueue.get(task["id"])
    return {"task": task, "routed_to": fit["agent"], "reason": fit["reason"], "ranked": fit["ranked"]}


# ---- Orchestrate (decompose a goal into routed subtasks) ----
class OrchestrateIn(BaseModel):
    goal: str
    max_subtasks: int | None = None
    dispatch: bool = True


@app.post("/api/orchestrate")
def orchestrate_goal(body: OrchestrateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return orchestrator.orchestrate(body.goal, body.max_subtasks, body.dispatch)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Data export (CSV / JSON) ----
def _csv_response(filename: str, header: list[str], rows) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/export/usage")
def export_usage(hours: int = Query(default=168), fmt: str = Query(default="csv"),
                 x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    data = usage.series(max(1, min(hours, 24 * 14)))
    if fmt == "json":
        return data
    rows = ([b["hour"], b["calls"], b["errors"], b["tokens_in"], b["tokens_out"], b["cost"]]
            for b in data["buckets"])
    return _csv_response("usage.csv", ["hour_epoch", "calls", "errors", "tokens_in", "tokens_out", "cost_usd"], rows)


@app.get("/api/export/history")
def export_history(fmt: str = Query(default="csv"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    series = history.all_series()
    if fmt == "json":
        return {"series": series}

    def _rows():
        for key, points in series.items():
            device, _, name = key.partition(":")
            for pt in points:
                yield [device, name, pt.get("ts"), pt.get("health"), pt.get("pnl")]
    return _csv_response("history.csv", ["device", "project", "ts_ms", "health", "pnl"], _rows())


# ---- Health / readiness probes (unauthenticated, no secrets) ----
@app.get("/healthz")
def healthz():
    """Liveness: the process is up and serving."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(strict: bool = Query(default=False)):
    """Readiness: the dashboard can serve. Reports the last poll's device health;
    with ``?strict=1`` returns 503 when any configured device is offline."""
    summary = aggregator.last_summary()
    offline = summary.get("offline_devices", 0)
    online = summary.get("online_devices", 0)
    polled = bool(summary)
    degraded = polled and offline > 0
    body = {"status": "degraded" if degraded else "ok", "ready": True, "polled": polled,
            "online_devices": online, "offline_devices": offline}
    if strict and degraded:
        return JSONResponse(body, status_code=503)
    return body


@app.get("/metrics")
def prometheus_metrics():
    # Aggregate stats only (no secrets); standard unauthenticated Prometheus scrape target.
    return PlainTextResponse(metrics_mod.render(), media_type="text/plain; version=0.0.4")


# ---- Public status page (Sect Proclamation) — opt-in, unauthenticated ----
from . import status_page


@app.get("/status")
def public_status_page():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return PlainTextResponse(status_page.render_html(), media_type="text/html")


@app.get("/api/status/public")
def public_status_json():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return status_page.public_data()


@app.get("/api/command")
def command_snapshot(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return command.snapshot()


def _sect_pngs(sub: str) -> list:
    import os
    d = f"maybot_control_center/static/assets/sect/{sub}"
    return [fn[:-4] for fn in sorted(os.listdir(d)) if fn.lower().endswith(".png")] if os.path.isdir(d) else []


@app.get("/api/sect/disciples")
def sect_disciples():
    """List authored Realm Map art basenames: character sprites (disciples/,
    e.g. 'trader_walk_6f'), effect strips (fx/, e.g. 'fx_breakthrough_8f'), and
    inspect portraits (portraits/, e.g. 'leader'). The Realm Map loads only what
    exists and falls back to procedural drawing otherwise — so no 404 probing."""
    return {"sprites": _sect_pngs("disciples"), "fx": _sect_pngs("fx"), "portraits": _sect_pngs("portraits")}


# ====================================================================== #
#  Trading cockpit — live market data, risk, control, ML signals, advisor
#  All read endpoints need any valid role; mutating ones need operator.
# ====================================================================== #
@app.get("/api/market/quotes")
def market_quotes(symbols: str = Query(default=""), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:50]
    return {"quotes": quotes.get_quotes(syms), "live": quotes.live()}


@app.get("/api/market/account")
def market_account(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": broker.enabled(), "account": broker.account(), "fills": broker.recent_fills()}


@app.get("/api/risk")
def risk_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"status": risk.status(), "evaluation": command.snapshot().get("risk", {})}


class KillIn(BaseModel):
    on: bool = True


@app.post("/api/risk/kill")
def risk_kill(body: KillIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    actor = authz.name_for(x_control_token) or "operator"
    res = risk.kill_switch(bool(body.on), actor)
    try:
        notify.send("Kill-switch " + ("ENGAGED" if body.on else "released"),
                    f"by {actor}", level=("warn" if body.on else "info"), kind="risk")
    except Exception:
        pass
    return res


class BotControlIn(BaseModel):
    bot: str
    action: str


@app.post("/api/bots/control")
def bots_control(body: BotControlIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    bot = (body.bot or "").strip()
    if not bot or len(bot) > 64 or not re.match(r'^[\w \-\.]+$', bot):
        raise HTTPException(400, "invalid bot name")
    actor = authz.name_for(x_control_token) or "operator"
    res = botcontrol.set_state(bot, (body.action or "").strip().lower(), actor)
    if res.get("error"):
        raise HTTPException(400, res["error"])
    return res


@app.post("/api/bots/flatten")
def bots_flatten(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    actor = authz.name_for(x_control_token) or "operator"
    try:
        notify.send("Flatten-all requested", f"by {actor}", level="warn", kind="risk")
    except Exception:
        pass
    return botcontrol.flatten_all(actor)


@app.get("/api/signals")
def signals_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    snap = command.snapshot()
    syms = [p.get("ticker") for p in snap.get("positions", []) if p.get("ticker")]
    syms = syms or [o.get("ticker") for o in snap.get("opportunities", []) if o.get("ticker")]
    return {"enabled": signals.enabled(), "model": signals.model_info(), "scores": signals.score_symbols(syms)}


@app.get("/api/advisor")
def advisor_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return advisor.summary(command.snapshot())


@app.get("/api/notifications")
def notifications_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"channels": notify.channels(), "recent": notify.recent()}


@app.get("/api/pnl")
def pnl_view(metric: str = Query(default="total"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"metric": metric, "series": pnl_history.series(metric), "summary": pnl_history.summary()}


_CMD = "maybot_control_center/static/command"


@app.get("/")
def home():
    return FileResponse(f"{_CMD}/index.html")


@app.get("/command.js")
def command_js():
    return FileResponse(f"{_CMD}/command.js", media_type="text/javascript")


@app.get("/command.css")
def command_css():
    return FileResponse(f"{_CMD}/command.css", media_type="text/css")


@app.get("/vendor/three.module.js")
def three_js():
    return FileResponse(f"{_CMD}/vendor/three.module.js", media_type="text/javascript")


@app.get("/vendor/OrbitControls.js")
def orbit_controls_js():
    return FileResponse(f"{_CMD}/vendor/OrbitControls.js", media_type="text/javascript")


@app.get("/lib.js")
def command_lib_js():
    return FileResponse(f"{_CMD}/lib.js", media_type="text/javascript")


@app.get("/login")
def login_page():
    return FileResponse(f"{_CMD}/login.html")


@app.get("/login.js")
def login_js():
    return FileResponse(f"{_CMD}/login.js", media_type="text/javascript")


@app.get("/chamber")
def chamber():
    return FileResponse(f"{_CMD}/chamber.html")


@app.get("/chamber.js")
def chamber_js():
    return FileResponse(f"{_CMD}/chamber.js", media_type="text/javascript")


@app.get("/trade")
def trade():
    return FileResponse(f"{_CMD}/trade.html")


@app.get("/trade.js")
def trade_js():
    return FileResponse(f"{_CMD}/trade.js", media_type="text/javascript")


@app.get("/treasury")
def treasury_page():
    return FileResponse(f"{_CMD}/treasury.html")


@app.get("/treasury.js")
def treasury_js():
    return FileResponse(f"{_CMD}/treasury.js", media_type="text/javascript")


@app.get("/console")
def console_home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")


# ---- PWA (installable app + offline shell) ----
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse("maybot_control_center/static/manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse("maybot_control_center/static/sw.js", media_type="text/javascript")


@app.get("/icon.svg")
def icon():
    return FileResponse("maybot_control_center/static/icon.svg", media_type="image/svg+xml")


@app.get("/assets/{path:path}")
def assets(path: str):
    """Serve static assets (Sect Map art, sprites). Rejects path traversal."""
    import os
    base = os.path.realpath("maybot_control_center/static/assets")
    target = os.path.realpath(os.path.join(base, path))
    if os.path.commonpath([base, target]) != base or not os.path.isfile(target):
        raise HTTPException(404, "asset not found")
    return FileResponse(target)
