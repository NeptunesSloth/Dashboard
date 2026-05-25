from pathlib import Path
import logging
import os
import yaml

_log = logging.getLogger("maybot_agent")

PROJECTS_FILE = Path(os.getenv("MAYBOT_PROJECTS_FILE", "projects.yaml"))
API_TOKEN = os.getenv("MAYBOT_API_TOKEN", "")
HOST = os.getenv("MAYBOT_AGENT_HOST", "127.0.0.1")
PORT = int(os.getenv("MAYBOT_AGENT_PORT", "8100"))

if not API_TOKEN:
    _log.critical("SECURITY: MAYBOT_API_TOKEN is not set — all agent API requests will be rejected with 401")
elif API_TOKEN == "change-me":
    _log.warning("SECURITY: MAYBOT_API_TOKEN is using the default 'change-me' value — change it to a strong secret immediately")


def load_projects() -> list[dict]:
    if not PROJECTS_FILE.exists():
        return []
    with PROJECTS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    projects = data.get("projects", [])
    return projects if isinstance(projects, list) else []
