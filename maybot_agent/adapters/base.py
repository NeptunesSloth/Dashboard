from __future__ import annotations

from pathlib import Path
from ..services.git_status import get_git_status
from ..services.process_status import find_process
from ..services.log_reader import read_logs


def _health_from_alerts(alerts: list[str]) -> str:
    if not alerts:
        return "ok"
    if any(a.startswith("ERROR") for a in alerts):
        return "error"
    return "warning"


def base_project(project: dict) -> dict:
    name = project.get("name", "unknown")
    ptype = project.get("type", "generic")
    path = project.get("path")
    proc = find_process(
        pid_file=project.get("pid_file"),
        cmdline_contains=project.get("cmdline_contains"),
        process_name=project.get("process_name"),
        cwd=path,
    )
    git = get_git_status(path) if path else {"branch": "unknown", "dirty": "unknown", "last_commit": "unknown"}
    alerts: list[str] = []

    if path and not Path(path).exists():
        alerts.append("ERROR: configured path missing")
    log_file = project.get("log_file")
    if log_file and not Path(log_file).exists():
        alerts.append("WARNING: configured log file missing")
    if project.get("expect_running") and proc.get("running") is False:
        alerts.append("ERROR: process expected but stopped")

    if log_file:
        log = read_logs(log_file, level="ALL", tail=100)
        joined = "\n".join(log.get("lines", []))
        if "CRITICAL" in joined or "ERROR" in joined:
            alerts.append("WARNING: recent logs contain ERROR/CRITICAL")

    status = "running" if proc.get("running") is True else ("stopped" if proc.get("running") is False else "unknown")
    return {
        "name": name,
        "type": ptype,
        "status": status,
        "health": _health_from_alerts(alerts) if alerts else "ok",
        "metrics": {"git": git, "process": proc},
        "alerts": alerts,
        "actions_available": {
            "run_tests": bool(project.get("commands", {}).get("run_tests")),
            "start": bool(project.get("commands", {}).get("start")),
            "stop": bool(project.get("commands", {}).get("stop")),
        },
    }
