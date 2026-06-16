import os
import queue
import secrets
import asyncio
import json as _json
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from .config import all_devices, CONTROL_CENTER_TOKEN
from . import deps
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
from . import scheduler
from . import runbooks
from . import maintenance
from . import oaths
from . import taskqueue
from . import autopilot
from . import sectmemory
from . import audit
from . import inbound
from . import registry
from . import push
from . import risk
from . import acks
from . import reports
from . import retention
from . import selfcheck
from . import learning
from . import obs
from . import comics

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
                app_settings.load_persisted, runbooks.load_persisted, learning.load_persisted,
                comics.load_persisted):
    try:
        _loader()
    except Exception:
        pass
from . import talismans
scheduler.start()  # background cron for scheduled missions (no-op without schedules.yaml)
talismans.start()  # background synthetic uptime probes (no-op without talismans.yaml)
autopilot.start()  # the Sect Leader's autonomous ops loop (no-op unless MAYBOT_AUTOPILOT=1)
reports.start()    # periodic summary reports (no-op unless MAYBOT_REPORT_INTERVAL_HOURS>0)
retention.start()  # data-retention pruning + scheduled backups (no-op unless configured)
learning.start()   # Learning Center re-engagement reminders (no-op unless MAYBOT_LEARNING_REMINDERS=1)
comics.start()     # comics library feed auto-updater (no-op unless MAYBOT_COMICS=1)
from . import deadman
deadman.start()    # external heartbeat: if the dashboard dies, your monitor pages you (no-op until configured)
from . import safemode
safemode.load_persisted()   # restore the panic-button state across restarts

# Non-fatal startup config validation: warn (never fail) on common misconfig.
from . import config_check
import logging as _logging
for _warning in config_check.check():
    _logging.getLogger("maybot.config").warning("config: %s", _warning)

# Optional security headers (off by default so existing deploys are unaffected).
_DEFAULT_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
_csp_env = os.getenv("MAYBOT_CSP", "").strip()
_CSP = _DEFAULT_CSP if _csp_env.lower() in ("1", "true", "yes", "on") else _csp_env
_HSTS = os.getenv("MAYBOT_HSTS", "0").lower() in ("1", "true", "yes", "on")
# Interactive OpenAPI docs (/docs, /redoc, /openapi.json) are opt-in: they
# enumerate the whole API surface unauthenticated, so MAYBOT_DOCS gates them.
_DOCS = os.getenv("MAYBOT_DOCS", "0").lower() in ("1", "true", "yes", "on")

def _graceful_shutdown() -> None:
    """Flush + close persistence on SIGTERM/reload. Background loops are daemon
    threads whose every mutation persists synchronously, so a clean DB close is
    what keeps a terminating pod from cutting a commit in half."""
    try:
        store.close()
    except Exception:
        pass


from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(_app):
    yield
    _graceful_shutdown()


app = FastAPI(title="maybot-control-center", lifespan=_lifespan,
              docs_url="/docs" if _DOCS else None,
              redoc_url="/redoc" if _DOCS else None,
              openapi_url="/openapi.json" if _DOCS else None)


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
                                         or path in ("/console", "/login", "/chamber", "/trade", "/treasury", "/learn", "/comics")):
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


# Shared request gates live in deps.py so domain routers can reuse them without
# importing this module. Re-exported here under their original names.
_role = deps.role
_check_token = deps.check_token
_check_operator = deps.check_operator
_check_project_access = deps.check_project_access
_resolve_device = deps.resolve_device
_mask_token = deps.mask_token
_SAFE_NAME = deps.SAFE_NAME
_SAFE_TARGET = deps.SAFE_TARGET


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


# ---------------------------------------------------------------------------
# Domain routers — every HTTP route lives in routers/<domain>.py; only the
# middleware, startup wiring, the agent tunnel and the SSE stream live here.
# ---------------------------------------------------------------------------
from .routers import (accounts as _accounts_router, adminops as _adminops_router,
                      agentops as _agentops_router, alerts as _alerts_router,
                      crew as _crew_router, economy as _economy_router,
                      enroll as _enroll_router, fleet as _fleet_router,
                      hosts as _hosts_router, learning as _learning_router,
                      members as _members_router, pages as _pages_router,
                      reliability as _reliability_router, sect as _sect_router,
                      tasks as _tasks_router, trading as _trading_router,
                      comics as _comics_router)

for _router_mod in (_fleet_router, _hosts_router, _adminops_router, _accounts_router,
                    _members_router, _learning_router, _crew_router, _agentops_router,
                    _sect_router, _economy_router, _reliability_router, _alerts_router,
                    _tasks_router, _enroll_router, _trading_router, _comics_router,
                    _pages_router):
    app.include_router(_router_mod.router)
