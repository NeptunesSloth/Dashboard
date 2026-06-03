import queue
import re
import secrets
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from .config import load_devices, CONTROL_CENTER_TOKEN
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

# Restore persisted state (no-op unless MAYBOT_DB is set).
store.init()
for _loader in (history.load_persisted, agents.load_persisted, comms.load_persisted,
                tooling.load_persisted, usage.load_persisted, cultivation.load_persisted):
    try:
        _loader()
    except Exception:
        pass

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
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
    return await call_next(request)


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


def _resolve_device(device_name: str):
    device = next((d for d in load_devices() if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    return device


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(load_devices())


@app.get("/api/logs/{device_name}/{project_name}")
def proxy_logs(device_name: str, project_name: str, level: str = Query(default="ALL"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    if level.upper() not in _VALID_LEVELS:
        raise HTTPException(400, f"invalid log level '{level}'")
    result = call_agent(_resolve_device(device_name), f"/api/projects/{project_name}/logs?level={level.upper()}")
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


@app.get("/api/history/{device_name}/{project_name}")
def project_history(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    return {"history": history.get(device_name, project_name)}


@app.post("/api/action/{device_name}/{project_name}/{action}")
def proxy_action(device_name: str, project_name: str, action: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, f"unknown action '{action}'; must be one of {sorted(_VALID_ACTIONS)}")
    agent_path = "run-tests" if action == "run-tests" else action
    timeout = _ACTION_TIMEOUTS[action]
    result = post_agent(_resolve_device(device_name), f"/api/projects/{project_name}/{agent_path}", timeout=timeout)
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


class TaskIn(BaseModel):
    task: str


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
    try:
        return agents.assign_task(name, task)
    except KeyError:
        raise HTTPException(404, "agent not found")


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


@app.get("/api/cultivation")
def cultivation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return cultivation.snapshot()


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


@app.get("/")
def home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")
