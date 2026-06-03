"""GitHub integration — track repos as monitored projects + task references.

Two capabilities:

1. **Repos as projects** — configured repos (``MAYBOT_GITHUB_REPOS``, comma-
   separated ``owner/name``) are polled for health (open PRs, failing checks,
   open issues) and surfaced in the overview as ``github_repo`` projects, right
   alongside trading bots and AI hosts. A short TTL cache keeps dashboard polls
   from hammering GitHub.

2. **Task references** — a task/mission can carry a ``repo`` + issue/PR number;
   ``task_reference`` builds a context line the disciple sees. Posting results
   back is done through the human-approved ``gh_*`` guarded tools.

The actual GitHub call is injectable (``fetcher``) so this is fully unit-
testable without network; the default fetcher shells out to the ``gh`` CLI.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time

REPOS = [r.strip() for r in os.getenv("MAYBOT_GITHUB_REPOS", "").split(",") if r.strip()]
PR_WARN = int(os.getenv("MAYBOT_GITHUB_PR_WARN", "10"))        # open PRs at/above this → warning
ISSUE_WARN = int(os.getenv("MAYBOT_GITHUB_ISSUE_WARN", "25"))  # open issues at/above this → warning
CACHE_TTL = int(os.getenv("MAYBOT_GITHUB_CACHE_TTL", "60"))    # seconds
GH_TIMEOUT = int(os.getenv("MAYBOT_GITHUB_TIMEOUT", "15"))

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}  # repo -> (ts, metrics)


def enabled() -> bool:
    return bool(REPOS)


def _gh_fetch(repo: str) -> dict:
    """Default fetcher: query repo health via the `gh` CLI (must be installed/auth'd)."""
    def _count(args: list[str]) -> int:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True,
                             timeout=GH_TIMEOUT, check=False)
        if out.returncode != 0:
            raise RuntimeError((out.stderr or "gh error").strip()[:200])
        data = json.loads(out.stdout or "[]")
        return len(data)

    open_prs = _count(["pr", "list", "--repo", repo, "--state", "open", "--json", "number", "--limit", "100"])
    open_issues = _count(["issue", "list", "--repo", repo, "--state", "open", "--json", "number", "--limit", "100"])
    # failing checks on open PRs
    pr_json = subprocess.run(["gh", "pr", "list", "--repo", repo, "--state", "open",
                              "--json", "number,statusCheckRollup", "--limit", "100"],
                             capture_output=True, text=True, timeout=GH_TIMEOUT, check=False)
    failing = 0
    if pr_json.returncode == 0:
        for pr in json.loads(pr_json.stdout or "[]"):
            roll = pr.get("statusCheckRollup") or []
            if any((c.get("conclusion") in ("FAILURE", "TIMED_OUT", "CANCELLED")
                    or c.get("state") == "FAILURE") for c in roll):
                failing += 1
    return {"open_prs": open_prs, "open_issues": open_issues, "failing_checks": failing}


def _health(m: dict) -> str:
    if m.get("error") or m.get("failing_checks", 0) > 0:
        return "error"
    if m.get("open_prs", 0) >= PR_WARN or m.get("open_issues", 0) >= ISSUE_WARN:
        return "warning"
    return "ok"


def _metrics(repo: str, fetcher) -> dict:
    """Fetch (cached) metrics for one repo; never raises — errors become a metric."""
    now = time.time()
    with _lock:
        hit = _cache.get(repo)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    try:
        m = fetcher(repo)
    except Exception as exc:  # noqa: BLE001 — surface as an unhealthy project, never crash the poll
        m = {"error": str(exc)[:200]}
    with _lock:
        _cache[repo] = (now, m)
    return m


def collect(fetcher=None) -> list[dict]:
    """Return configured repos as project dicts for the overview aggregator."""
    f = fetcher or _gh_fetch
    out = []
    for repo in REPOS:
        m = _metrics(repo, f)
        health = _health(m)
        alerts = []
        if m.get("error"):
            alerts.append(f"ERROR: {m['error']}")
        elif m.get("failing_checks"):
            alerts.append(f"ERROR: {m['failing_checks']} PR(s) with failing checks")
        out.append({
            "device": "github", "name": repo, "type": "github_repo",
            "status": "tracked", "health": health, "metrics": m, "alerts": alerts,
            "actions_available": {},
        })
    return out


def task_reference(repo: str, number: int | None = None, fetcher=None) -> str:
    """A one-line GitHub context string to prepend to a disciple's task."""
    if not repo:
        return ""
    ref = f"{repo}#{number}" if number else repo
    detail = ""
    if number:
        m = _metrics(repo, fetcher or _gh_fetch)
        if m.get("error"):
            detail = f" (could not read: {m['error']})"
    return f"[GitHub context: {ref}]{detail}"


def clear() -> None:
    with _lock:
        _cache.clear()
