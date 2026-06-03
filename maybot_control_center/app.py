import re
import secrets
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import load_devices, CONTROL_CENTER_TOKEN
from .aggregator import aggregate
from .agent_client import call_agent, post_agent
from . import history
from . import agents
from . import comms

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}

app = FastAPI(title="maybot-control-center")


def _check_token(x_control_token: str = Header(default="")):
    if CONTROL_CENTER_TOKEN and not secrets.compare_digest(x_control_token, CONTROL_CENTER_TOKEN):
        raise HTTPException(status_code=401, detail="invalid control token")


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
    _check_token(x_control_token)
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
    _check_token(x_control_token)
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
    _check_token(x_control_token)
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


@app.get("/")
def home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")
