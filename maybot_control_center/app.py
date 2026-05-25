from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from .config import load_devices, CONTROL_CENTER_TOKEN
from .aggregator import aggregate
from .agent_client import call_agent

app = FastAPI(title="maybot-control-center")


def _check_token(x_control_token: str = Header(default="")):
    if CONTROL_CENTER_TOKEN and x_control_token != CONTROL_CENTER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid control token")


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(load_devices())


@app.get("/api/logs/{device_name}/{project_name}")
def proxy_logs(device_name: str, project_name: str, level: str = Query(default="ALL"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    devices = load_devices()
    device = next((d for d in devices if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    result = call_agent(device, f"/api/projects/{project_name}/logs?level={level}")
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
