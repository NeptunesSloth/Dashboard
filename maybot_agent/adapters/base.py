from ..services.git_status import get_git_status
from ..services.process_status import find_process


def base_project(project: dict) -> dict:
    name = project.get("name", "unknown")
    ptype = project.get("type", "generic")
    proc = find_process(project.get("process_name"), project.get("pid"))
    git = get_git_status(project.get("path", "")) if project.get("path") else {"branch": "unknown", "dirty": "unknown", "last_commit": "unknown"}
    return {
        "name": name,
        "type": ptype,
        "status": "running" if proc.get("running") is True else ("stopped" if proc.get("running") is False else "unknown"),
        "health": "ok",
        "metrics": {"git": git, "process": proc},
        "alerts": [],
        "actions_available": {
            "run_tests": bool(project.get("commands", {}).get("run_tests")),
            "start": bool(project.get("commands", {}).get("start")),
            "stop": bool(project.get("commands", {}).get("stop")),
        },
    }
