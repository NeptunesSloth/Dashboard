from fastapi import FastAPI
from fastapi.responses import FileResponse
from .config import load_devices
from .aggregator import aggregate

app = FastAPI(title="maybot-control-center")


@app.get("/api/overview")
def overview():
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
