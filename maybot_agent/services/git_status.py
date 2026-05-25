import subprocess


def get_git_status(path: str) -> dict:
    try:
        branch = subprocess.check_output(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "-C", path, "status", "--porcelain"], text=True).strip())
        last = subprocess.check_output(["git", "-C", path, "log", "-1", "--pretty=%h %s"], text=True).strip()
        return {"branch": branch, "dirty": dirty, "last_commit": last}
    except Exception:
        return {"branch": "unknown", "dirty": "unknown", "last_commit": "unknown"}
