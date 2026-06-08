from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from .auth import verify_token
from .config import load_projects, save_projects, HOST, PORT
from .services.command_runner import run_foreground, start_background, stop_process
from .services.log_reader import read_logs
from .adapters import trading_bot, code_project, game_server, website, school, ai_project, local_ai_host, generic
from . import selfregister
from . import tunnel_client
from . import __version__ as AGENT_VERSION

import platform
import socket


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Auto-enroll with the control center if MAYBOT_CONTROL_CENTER_URL is set, so a
    # new host appears on the dashboard automatically — no manual "Add host".
    # (Modern FastAPI lifespan handler; replaces the deprecated @app.on_event.)
    selfregister.start()
    tunnel_client.start()   # dial out to the dashboard (no inbound port needed); no-op if disabled
    yield


app = FastAPI(title="maybot-agent", lifespan=lifespan)


def _hostname() -> str:
    try:
        return socket.gethostname() or "agent"
    except Exception:
        return "agent"


def _lan_ip() -> str:
    """Best-effort primary outbound IP (no packet is actually sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


ADAPTERS = {
    "trading_bot": trading_bot,
    "code_project": code_project,
    "game_server": game_server,
    "website": website,
    "school": school,
    "ai_project": ai_project,
    "local_ai_host": local_ai_host,
    "generic": generic,
}


def adapt_project(project: dict) -> dict:
    mod = ADAPTERS.get(project.get("type"), generic)
    return mod.adapt(project)


def get_project(name: str) -> dict:
    for p in load_projects():
        if p.get("name") == name:
            return p
    raise HTTPException(404, "project not found")


# --- Liveness / identity ---------------------------------------------------
# These carry no secrets and no bot/PnL data, so they are intentionally
# unauthenticated: they are the routes used for plain health checks (infra
# probes, `curl /healthz`, the dashboard's reachability ping). Sensitive
# routes below (projects, logs, run/start/stop) still require the API token.

@app.get("/healthz")
def healthz():
    """Unauthenticated liveness — the agent process is up and serving."""
    return {"status": "ok", "service": "maybot-agent", "version": AGENT_VERSION}


@app.get("/api/ping")
def ping():
    return {"status": "ok", "service": "maybot-agent", "version": AGENT_VERSION}


@app.get("/api/device")
def device():
    """Non-sensitive host identity for the dashboard's device list."""
    return {
        "host": HOST,
        "hostname": _hostname(),
        "ip": _lan_ip(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "port": PORT,
        "version": AGENT_VERSION,
    }


@app.get("/api/projects", dependencies=[Depends(verify_token)])
def projects():
    return [adapt_project(p) for p in load_projects()]


# --- Dashboard-managed bot config (edit a host's projects from the UI) -------

class ProjectsConfig(BaseModel):
    projects: list[dict]


@app.get("/api/projects/config", dependencies=[Depends(verify_token)])
def projects_config():
    """The raw, editable projects list (the source for the dashboard editor)."""
    return {"projects": load_projects()}


@app.put("/api/projects/config", dependencies=[Depends(verify_token)])
def set_projects_config(body: ProjectsConfig):
    """Replace this host's projects list and persist it to ``projects.yaml``."""
    try:
        saved = save_projects(body.projects)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"projects": saved, "count": len(saved)}


@app.get("/api/discover", dependencies=[Depends(verify_token)])
def discover():
    """Heuristic candidates (processes/containers) to seed the projects editor."""
    from .services.discover import discover_candidates
    return {"candidates": discover_candidates()}


@app.post("/api/self-update", dependencies=[Depends(verify_token)])
def self_update():
    """Re-pull the agent bundle from the control center and restart on the new code."""
    from . import updater
    return updater.update_and_restart()


@app.get("/api/projects/{name}", dependencies=[Depends(verify_token)])
def project(name: str):
    return adapt_project(get_project(name))


_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}


@app.get("/api/projects/{name}/logs", dependencies=[Depends(verify_token)])
def logs(name: str, level: str = Query(default="ALL")):
    if level.upper() not in _VALID_LEVELS:
        raise HTTPException(400, f"invalid log level '{level}'; must be one of {sorted(_VALID_LEVELS)}")
    p = get_project(name)
    return read_logs(p.get("log_file"), level=level.upper())


@app.get("/api/projects/{name}/health", dependencies=[Depends(verify_token)])
def health(name: str):
    return {"health": adapt_project(get_project(name)).get("health", "unknown")}


@app.post("/api/projects/{name}/run-tests", dependencies=[Depends(verify_token)])
def run_tests(name: str):
    p = get_project(name)
    return run_foreground(p.get("commands", {}).get("run_tests"), p)


@app.post("/api/projects/{name}/start", dependencies=[Depends(verify_token)])
def start(name: str):
    p = get_project(name)
    return start_background(p.get("commands", {}).get("start"), p)


@app.post("/api/projects/{name}/stop", dependencies=[Depends(verify_token)])
def stop(name: str):
    p = get_project(name)
    return stop_process(p.get("commands", {}).get("stop"), p)
