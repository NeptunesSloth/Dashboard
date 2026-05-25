from fastapi import Depends, FastAPI, HTTPException, Query
from .auth import verify_token
from .config import load_projects, HOST, PORT
from .services.command_runner import run_foreground, start_background, stop_process
from .services.log_reader import read_logs
from .adapters import trading_bot, code_project, game_server, website, school, ai_project, local_ai_host, generic

app = FastAPI(title="maybot-agent")

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


@app.get("/api/ping", dependencies=[Depends(verify_token)])
def ping():
    return {"status": "ok"}


@app.get("/api/device", dependencies=[Depends(verify_token)])
def device():
    return {"host": HOST, "port": PORT}


@app.get("/api/projects", dependencies=[Depends(verify_token)])
def projects():
    return [adapt_project(p) for p in load_projects()]


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
