from __future__ import annotations

from pathlib import Path
import subprocess
from .base import base_project


def _todo_count(path: str | None) -> int | str:
    if not path or not Path(path).exists():
        return "unknown"
    try:
        out = subprocess.check_output(["rg", "-n", "TODO|FIXME", path], text=True, stderr=subprocess.DEVNULL)
        return len([x for x in out.splitlines() if x.strip()])
    except Exception:
        return 0


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    git = metrics.get("git", {})
    path = project.get("path")
    log_file = project.get("log_file")
    db = project.get("database")

    modified_count = "unknown"
    if path and Path(path).exists():
        try:
            out = subprocess.check_output(["git", "-C", path, "status", "--porcelain"], text=True)
            modified_count = len([x for x in out.splitlines() if x.strip()])
        except Exception:
            pass

    metrics.update({
        "git_branch": git.get("branch", "unknown"),
        "git_clean": (not git.get("dirty")) if isinstance(git.get("dirty"), bool) else "unknown",
        "modified_files": modified_count,
        "last_commit": git.get("last_commit", "unknown"),
        "todo_fixme_count": _todo_count(path),
        "last_test_result": project.get("last_test_result", "unknown"),
        "log_file_size": Path(log_file).stat().st_size if log_file and Path(log_file).exists() else "unknown",
        "database_size": Path(db).stat().st_size if db and Path(db).exists() else "unknown",
    })
    data["metrics"] = metrics
    return data
