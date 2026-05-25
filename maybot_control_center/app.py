from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from .config import load_devices, CONTROL_CENTER_TOKEN
from .aggregator import aggregate

app = FastAPI(title="maybot-control-center")


def _check_token(x_control_token: str = Header(default="")):
    if CONTROL_CENTER_TOKEN and x_control_token != CONTROL_CENTER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid control token")


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(load_devices())


@app.get("/")
def home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")
