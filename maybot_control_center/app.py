import csv
import io
import os
import queue
import re
import secrets
import asyncio
import json as _json
from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, JSONResponse, Response
from pydantic import BaseModel
from .config import load_devices, all_devices, CONTROL_CENTER_TOKEN
from . import deps
from . import aggregator
from .aggregator import aggregate
from .agent_client import call_agent, post_agent
try:
    from maybot_agent import __version__ as _LATEST_AGENT_VERSION
except Exception:  # pragma: no cover
    _LATEST_AGENT_VERSION = "1.0"
from . import history
from . import agents
from . import comms
from . import tools as tooling
from . import store
from . import settings as app_settings
from . import events
from . import usage
from . import authz
from . import cultivation
from . import treasury
from . import metrics as metrics_mod
from . import scheduler
from . import governance
from . import runbooks
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
from . import learning
from . import obs

# Opt-in structured JSON logging (no-op unless MAYBOT_JSON_LOGS is truthy).
obs.setup_logging()

# Restore persisted state (no-op unless MAYBOT_DB is set).
store.init()
for _loader in (history.load_persisted, agents.load_persisted, comms.load_persisted,
                tooling.load_persisted, usage.load_persisted, cultivation.load_persisted,
                treasury.load_persisted, taskqueue.load_persisted, oaths.load_persisted,
                maintenance.load_persisted, autopilot.load_persisted, sectmemory.load_persisted,
                audit.load_persisted, inbound.load_persisted, registry.load_persisted,
                push.load_persisted, acks.load_persisted, authz.load_persisted, risk.load_persisted,
                app_settings.load_persisted, runbooks.load_persisted, learning.load_persisted):
    try:
        _loader()
    except Exception:
        pass
scheduler.start()  # background cron for scheduled missions (no-op without schedules.yaml)
talismans.start()  # background synthetic uptime probes (no-op without talismans.yaml)
autopilot.start()  # the Sect Leader's autonomous ops loop (no-op unless MAYBOT_AUTOPILOT=1)
reports.start()    # periodic summary reports (no-op unless MAYBOT_REPORT_INTERVAL_HOURS>0)
retention.start()  # data-retention pruning + scheduled backups (no-op unless configured)
learning.start()   # Learning Center re-engagement reminders (no-op unless MAYBOT_LEARNING_REMINDERS=1)
from . import deadman
deadman.start()    # external heartbeat: if the dashboard dies, your monitor pages you (no-op until configured)
from . import safemode
safemode.load_persisted()   # restore the panic-button state across restarts

_SAFE_NAME = deps.SAFE_NAME
# A silence target: "*", "device:*", or "device:project".
_SAFE_TARGET = re.compile(r'^(\*|[a-zA-Z0-9_\-\.]{1,128}:(\*|[a-zA-Z0-9_\-\.]{1,128}))$')
_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}

# Optional security headers (off by default so existing deploys are unaffected).
_DEFAULT_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
_csp_env = os.getenv("MAYBOT_CSP", "").strip()
_CSP = _DEFAULT_CSP if _csp_env.lower() in ("1", "true", "yes", "on") else _csp_env
_HSTS = os.getenv("MAYBOT_HSTS", "0").lower() in ("1", "true", "yes", "on")

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
                                         or path in ("/console", "/login", "/chamber", "/trade", "/treasury", "/learn")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    # Baseline security headers on every response (safe defaults).
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # Content-Security-Policy: opt-in (MAYBOT_CSP) so existing deploys are
    # unaffected until enabled. The default policy fits this app — same-origin
    # scripts (ES modules), inline styles/style-attributes the UI relies on, and
    # data: images. Set MAYBOT_CSP to a custom policy, or "1"/"on" for the default.
    if _CSP:
        h.setdefault("Content-Security-Policy", _CSP)
    # HSTS: opt-in (MAYBOT_HSTS) — only safe behind HTTPS, so off by default.
    if _HSTS:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
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


# Shared request gates now live in deps.py so domain routers can reuse them
# without importing this module. Re-exported here under their original names.
_role = deps.role
_check_token = deps.check_token
_check_operator = deps.check_operator
_check_project_access = deps.check_project_access
_resolve_device = deps.resolve_device
_mask_token = deps.mask_token


@app.get("/api/meta")
def meta():
    """Non-secret UI hints: whether auth is configured (for the setup warning),
    and which optional subsystems are on."""
    auth_configured = bool(authz.load_users()) or bool(CONTROL_CENTER_TOKEN)
    return {"auth_configured": auth_configured, "autopilot_enabled": autopilot.ENABLED,
            "public_status": status_page.enabled()}


@app.get("/api/admin/export")
def admin_export(x_control_token: str = Header(default="")):
    """Download a full config backup (hosts, accounts, enroll token, state)."""
    _check_operator(x_control_token)
    from . import dr
    return JSONResponse(dr.export_all(),
                        headers={"Content-Disposition": "attachment; filename=maybot-backup.json"})


@app.post("/api/admin/import")
def admin_import(body: dict, x_control_token: str = Header(default="")):
    """Restore from a backup bundle — rebuilds hosts/accounts/state in place."""
    _check_operator(x_control_token)
    from . import dr
    try:
        return dr.restore_all(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class DeadmanIn(BaseModel):
    url: str = ""
    interval: float | None = None


@app.get("/api/deadman")
def deadman_get(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return deadman.status()


@app.post("/api/deadman")
def deadman_set(body: DeadmanIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return deadman.configure(body.url, body.interval)


@app.post("/api/deadman/test")
def deadman_test(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"ok": deadman.ping_once(), **deadman.status()}


class SafemodeIn(BaseModel):
    engaged: bool


@app.get("/api/safemode")
def safemode_get(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    from . import safemode
    return safemode.status()


@app.post("/api/safemode")
def safemode_set(body: SafemodeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    from . import safemode
    safemode.set_engaged(body.engaged)
    events.publish("safemode", {"engaged": body.engaged})
    return safemode.status()


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
# Host (agent) management routes live in routers/hosts.py.
from .routers import hosts as _hosts_router
app.include_router(_hosts_router.router)


def _verify_account_password(token: str, password: str) -> None:
    """Gate the secrets panel: re-check the operator's account password.

    In open mode (no account password set) there is nothing to verify against,
    so access follows the dashboard's own (open) posture.
    """
    u = authz.current_user(token)
    pw_hash = (u or {}).get("pw") or ""
    if pw_hash and not authz.verify_password(password or "", pw_hash):
        raise HTTPException(403, "incorrect password")


@app.get("/api/settings")
def settings_get(x_control_token: str = Header(default="")):
    """System settings with secrets MASKED (status only). Reveal needs /unlock."""
    _check_operator(x_control_token)
    return app_settings.view(reveal=False)


class SettingsUnlockIn(BaseModel):
    password: str = ""


@app.post("/api/settings/unlock")
def settings_unlock(body: SettingsUnlockIn, x_control_token: str = Header(default="")):
    """Password-protected reveal: returns settings incl. secret values."""
    _check_operator(x_control_token)
    _verify_account_password(x_control_token, body.password)
    return {"ok": True, **app_settings.view(reveal=True)}


class SettingsIn(BaseModel):
    values: dict = {}
    password: str = ""


@app.post("/api/settings")
def settings_set(body: SettingsIn, x_control_token: str = Header(default="")):
    """Update system settings (password-gated); persisted + applied at runtime."""
    _check_operator(x_control_token)
    _verify_account_password(x_control_token, body.password)
    app_settings.set_many(body.values or {})
    return {"ok": True, **app_settings.view(reveal=True)}




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


class CopilotIn(BaseModel):
    question: str


@app.post("/api/copilot")
def copilot_ask(body: CopilotIn, x_control_token: str = Header(default="")):
    """Ops Copilot: answer a natural-language question about the fleet, grounded
    in a fresh poll, and surface conservative one-click remediations."""
    _check_token(x_control_token)
    from . import copilot
    overview = aggregate(all_devices())
    return copilot.ask(body.question, overview)


@app.post("/api/copilot/stream")
def copilot_ask_stream(body: CopilotIn, x_control_token: str = Header(default="")):
    """Streaming Ops Copilot: server-sent events so the answer renders token by
    token. Each line is ``data: {json}`` with a type of meta/token/done/error."""
    _check_token(x_control_token)
    from . import copilot
    overview = aggregate(all_devices())

    def gen():
        try:
            for event in copilot.ask_stream(body.question, overview):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- Learning Center routes — see routers/learning.py ----
from .routers import learning as _learning_router
app.include_router(_learning_router.router)


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


# Disciple crew + missions routes -> routers/crew.py
from .routers import crew as _crew_router
app.include_router(_crew_router.router)



# Agent-ops routes (memory / tools / autonomy / usage / budget) -> routers/agentops.py
from .routers import agentops as _agentops_router
app.include_router(_agentops_router.router)


# Sect / cultivation RPG routes -> routers/sect.py
from .routers import sect as _sect_router
app.include_router(_sect_router.router)

# ---- Auto-remediation runbooks ----
@app.get("/api/runbooks")
def runbooks_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"runbooks": runbooks.catalog(), "editable": runbooks.list_rules(),
            "tools": [t.get("name") for t in tooling.tool_summaries()]}


class RunbookIn(BaseModel):
    name: str
    tool: str
    match: dict = {}
    args: dict = {}
    requester: str = "operator"
    auto: bool = False


@app.post("/api/runbooks")
def runbooks_save(body: RunbookIn, x_control_token: str = Header(default="")):
    """Create/replace a self-healing rule from the UI (persisted)."""
    _check_operator(x_control_token)
    try:
        saved = runbooks.save_rule(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "runbook": saved}


@app.delete("/api/runbooks/{name}")
def runbooks_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"ok": runbooks.delete_rule(name)}


# Disciple economy & lifecycle routes -> routers/economy.py
from .routers import economy as _economy_router
app.include_router(_economy_router.router)

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


@app.websocket("/ws/agent")
async def agent_tunnel(ws: WebSocket):
    """Reverse tunnel endpoint: an agent dials out here and authenticates, then
    the dashboard routes its requests down this socket (no inbound port on the
    host). Auth = the host's API token, or the shared enroll token."""
    from . import tunnel
    await ws.accept()
    try:
        hello = _json.loads(await ws.receive_text())
    except Exception:
        await ws.close()
        return
    name = (hello.get("name") or "").strip()
    token = hello.get("token") or ""
    dev = next((d for d in all_devices() if d.get("name") == name), None)
    authed = bool(name) and (
        (dev and dev.get("api_token") and secrets.compare_digest(token, dev["api_token"]))
        or (registry.REGISTER_TOKEN and secrets.compare_digest(token, registry.REGISTER_TOKEN))
    )
    if not authed:
        await ws.send_text(_json.dumps({"t": "hello_ack", "ok": False, "error": "auth"}))
        await ws.close()
        return
    conn = tunnel.Connection(name, ws, asyncio.get_running_loop())
    tunnel.register(name, conn)
    await ws.send_text(_json.dumps({"t": "hello_ack", "ok": True}))
    events.publish("hosts", {"event": "tunnel_up", "name": name})
    try:
        while True:
            msg = _json.loads(await ws.receive_text())
            if msg.get("t") == "res":
                conn.resolve(msg.get("id"), msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        tunnel.unregister(name, conn)
        conn.fail_all(ConnectionError("tunnel closed"))
        events.publish("hosts", {"event": "tunnel_down", "name": name})


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
    rec = registry.register(body.name, body.url, body.api_token, body.timeout)
    # A host just self-enrolled — push it to live dashboards instantly.
    events.publish("hosts", {"event": "enrolled", "name": body.name})
    return rec


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
        if u.get("totp"):
            cid, _ = authz.create_2fa_challenge(u["name"], method="totp")
            return {"ok": False, "pending_2fa": True, "challenge": cid, "method": "totp", "channel": "authenticator app"}
        if u.get("tfa") and notify.channels():
            cid, code = authz.create_2fa_challenge(u["name"], method="webhook")
            ch = notify.channels()[0]
            notify.send("Aegis sign-in code", f"Your 2FA code is {code} (valid 5 minutes).", level="info", kind="security")
            return {"ok": False, "pending_2fa": True, "challenge": cid, "method": "webhook", "channel": ch}
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
    reqs = ("fastapi==0.136.3\nuvicorn==0.48.0\npyyaml==6.0.3\nrequests==2.34.2\n"
            "psutil==7.2.2\nhttpx>=0.27\nwebsockets>=12\n")
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
    # Action-oriented "Quick Start" checklist (get hosts + bots online and current).
    from . import setup as setup_mod
    qs = setup_mod.checklist(devices)
    return {"steps": steps, "done": all(steps.values()),
            "counts": {"hosts": len(devices), "members": len(members), "accounts": len(users)},
            "summary": qs["summary"], "checklist": qs["steps"], "checklist_ready": qs["ready"]}


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
    method: str = "auto"   # "totp" (authenticator app), "webhook", or "auto"


@app.post("/api/account/2fa")
def account_2fa(body: TwoFAToggleIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    u = authz.current_user(x_control_token)
    if not u:
        raise HTTPException(400, "no account is associated with this session")
    if not body.enable:
        authz.set_totp(u["name"], None)    # also clears webhook tfa
        return {"ok": True, "tfa": False}
    method = body.method
    if method == "auto":
        method = "totp" if not notify.channels() else "webhook"
    if method == "totp":
        secret = authz.gen_totp_secret()
        authz.set_totp(u["name"], secret)
        return {"ok": True, "tfa": True, "method": "totp", "secret": secret,
                "uri": authz.totp_uri(u["name"], secret)}
    if not notify.channels():
        raise HTTPException(400, "set up a notification channel first, or use an authenticator app (method=totp)")
    authz.set_2fa(u["name"], True)
    return {"ok": True, "tfa": True, "method": "webhook"}


class ResetPwIn(BaseModel):
    new: str


@app.post("/api/accounts/{name}/reset-password")
def accounts_reset_password(name: str, body: ResetPwIn, x_control_token: str = Header(default="")):
    """Operator resets another account's password (e.g., a locked-out user)."""
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid account name")
    if not authz.user_by_name(name):
        raise HTTPException(404, "account not found")
    if len(body.new or "") < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    authz.set_password(name, body.new)
    return {"ok": True}


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


@app.get("/metrics/obs")
def prometheus_metrics_lite(x_control_token: str = Header(default="")):
    # Cheap, never-fail liveness/throughput exposition (no agent polling). Public by
    # default (internal scrape target); gated only when MAYBOT_METRICS_PUBLIC is off,
    # in which case a valid control token (or MAYBOT_METRICS_TOKEN) is required.
    if not obs.metrics_public():
        tok = obs.metrics_token()
        if not (tok and x_control_token == tok):
            deps.check_token(x_control_token)
    return PlainTextResponse(obs.render_prometheus(), media_type=obs.CONTENT_TYPE)


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


@app.get("/learn")
def learn_page():
    return FileResponse(f"{_CMD}/learn.html")


@app.get("/learn.js")
def learn_js():
    return FileResponse(f"{_CMD}/learn.js", media_type="text/javascript")


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
