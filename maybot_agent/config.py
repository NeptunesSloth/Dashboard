from pathlib import Path
import os
import yaml


PROJECTS_FILE = Path(os.getenv("MAYBOT_PROJECTS_FILE", "projects.yaml"))
API_TOKEN = os.getenv("MAYBOT_API_TOKEN", "change-me")
HOST = os.getenv("MAYBOT_AGENT_HOST", "127.0.0.1")
PORT = int(os.getenv("MAYBOT_AGENT_PORT", "8100"))


def load_projects() -> list[dict]:
    if not PROJECTS_FILE.exists():
        return []
    with PROJECTS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    projects = data.get("projects", [])
    return projects if isinstance(projects, list) else []
