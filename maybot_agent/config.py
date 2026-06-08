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


def save_projects(projects: list[dict]) -> list[dict]:
    """Validate and persist the host's projects list (the source `projects.yaml`).

    Lets the dashboard manage a host's bots over the API instead of hand-editing
    YAML over SSH. Writes atomically so a crash mid-write can't truncate the file.
    """
    if not isinstance(projects, list):
        raise ValueError("projects must be a list")
    cleaned: list[dict] = []
    names: set[str] = set()
    for p in projects:
        if not isinstance(p, dict):
            raise ValueError("each project must be a mapping/object")
        name = str(p.get("name", "")).strip()
        if not name:
            raise ValueError("each project needs a non-empty 'name'")
        if name in names:
            raise ValueError(f"duplicate project name: {name!r}")
        names.add(name)
        cleaned.append(p)
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROJECTS_FILE.with_name(PROJECTS_FILE.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump({"projects": cleaned}, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    os.replace(tmp, PROJECTS_FILE)
    return cleaned
