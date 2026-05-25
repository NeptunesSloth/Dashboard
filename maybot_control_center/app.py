import re
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from .config import load_devices, CONTROL_CENTER_TOKEN
from .aggregator import aggregate
from .agent_client import call_agent, post_agent

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}

app = FastAPI(title="maybot-control-center")


def _check_token(x_control_token: str = Header(default="")):
    if CONTROL_CENTER_TOKEN and x_control_token != CONTROL_CENTER_TOKEN:
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


@app.get("/")
def home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")
