from fastapi import Depends, FastAPI, HTTPException, Query
from .auth import verify_token
from .config import load_projects, HOST, PORT
from .services.command_runner import run_configured_command
from .services.log_reader import read_logs
from .adapters import trading_bot, code_project, game_server, website, school, ai_project, generic

app = FastAPI(title="maybot-agent")

ADAPTERS = {
    "trading_bot": trading_bot,
    "code_project": code_project,
    "game_server": game_server,
    "website": website,
    "school": school,
    "ai_project": ai_project,
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


@app.get("/api/projects/{name}/logs", dependencies=[Depends(verify_token)])
def logs(name: str, level: str = Query(default="ALL")):
    p = get_project(name)
    return read_logs(p.get("log_file"), level=level)


@app.get("/api/projects/{name}/health", dependencies=[Depends(verify_token)])
def health(name: str):
    return {"health": adapt_project(get_project(name)).get("health", "unknown")}


def _run_action(name: str, action: str):
    p = get_project(name)
    command = p.get("commands", {}).get(action)
    return run_configured_command(command, cwd=p.get("path"))


@app.post("/api/projects/{name}/run-tests", dependencies=[Depends(verify_token)])
def run_tests(name: str):
    return _run_action(name, "run_tests")


@app.post("/api/projects/{name}/start", dependencies=[Depends(verify_token)])
def start(name: str):
    return _run_action(name, "start")


@app.post("/api/projects/{name}/stop", dependencies=[Depends(verify_token)])
def stop(name: str):
    return _run_action(name, "stop")
