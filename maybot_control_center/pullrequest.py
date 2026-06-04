"""Disciples ship real pull requests.

When the autopilot decides a project's failure is a code issue, a coding disciple
drafts a fix as a unified diff (via its LLM). If real PRs are enabled
(``MAYBOT_PR_ENABLED=1``) and the project resolves to a GitHub repo with the
``gh`` CLI available, it opens an actual pull request. Otherwise — the default,
and whenever creds/tools are missing — it records a **Proposed PR** (title, body,
diff) in the artifact vault for the Ancestor to review. Either way the loop goes
from *detect failure* → *proposed code fix*.

The LLM planner and the PR opener are injectable, so this is testable without a
model or network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

ENABLED = os.getenv("MAYBOT_PR_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_REPO = os.getenv("MAYBOT_PR_REPO", "")
GH_TIMEOUT = int(os.getenv("MAYBOT_PR_TIMEOUT", "60"))


def _plan(coder: str | None, project: str, cause: str) -> dict | None:
    """Ask the coding disciple for {title, body, diff}. None if no model/parse."""
    from . import agents
    agent = agents._agent_def(coder) if coder else None
    if not agent:
        return None
    sys = ("You are a senior engineer fixing a failing project. Propose the SMALLEST safe fix as a "
           'unified diff. Reply with ONLY JSON: {"title":"...","body":"...","diff":"<unified diff>"}.')
    user = f"Project '{project}' is failing: {cause}. Propose the minimal patch and a clear PR title/body."
    try:
        ok, text, _ = agents._chat(agent, [{"role": "system", "content": sys},
                                           {"role": "user", "content": user}])
        if not ok or not text:
            return None
        m = re.search(r"\{.*\}", text, re.DOTALL)
        d = json.loads(m.group(0)) if m else None
        if isinstance(d, dict) and d.get("title"):
            return {"title": str(d["title"])[:120], "body": str(d.get("body", ""))[:4000],
                    "diff": str(d.get("diff", ""))[:20000]}
    except Exception:
        return None
    return None


def _gh_available() -> bool:
    return shutil.which("gh") is not None and shutil.which("git") is not None


def _run(args: list[str], cwd: str | None = None) -> str:
    out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=GH_TIMEOUT, check=True)
    return (out.stdout or "").strip()


def _open_pr(repo: str, title: str, body: str, diff: str) -> str:
    """Clone, branch, apply the diff, push, and open a PR. Returns the PR URL."""
    branch = f"maybot/autopilot-fix-{int(time.time())}"
    work = tempfile.mkdtemp(prefix="maybot-pr-")
    try:
        _run(["gh", "repo", "clone", repo, work, "--", "--depth", "1"])
        _run(["git", "-C", work, "checkout", "-b", branch])
        patch = os.path.join(work, "_maybot.patch")
        with open(patch, "w", encoding="utf-8") as f:
            f.write(diff if diff.endswith("\n") else diff + "\n")
        _run(["git", "-C", work, "apply", patch])
        os.remove(patch)
        _run(["git", "-C", work, "add", "-A"])
        _run(["git", "-C", work, "commit", "-m", title])
        _run(["git", "-C", work, "push", "-u", "origin", branch])
        return _run(["gh", "pr", "create", "--repo", repo, "--title", title,
                     "--body", body, "--head", branch])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _resolve_repo(project: str, repo: str | None) -> str:
    if repo:
        return repo
    if DEFAULT_REPO:
        return DEFAULT_REPO
    return project if "/" in (project or "") else ""   # github_repo projects are "owner/name"


def propose(project: str, device: str, cause: str, coder: str | None = None,
            repo: str | None = None) -> dict:
    """Draft a fix and either open a real PR or record a Proposed PR artifact."""
    from . import governance
    coder = coder or os.getenv("MAYBOT_AUTOPILOT_CODER", "") or governance.leader() or "Autopilot"
    plan = _plan(coder, project, cause) or {
        "title": f"Fix: {project} unhealthy", "body": f"Autopilot diagnosed: {cause}", "diff": ""}
    repo = _resolve_repo(project, repo)

    if ENABLED and repo and plan.get("diff") and _gh_available():
        try:
            url = _open_pr(repo, plan["title"], plan["body"], plan["diff"])
            _remember(project, coder, plan, opened=True, url=url)
            return {"opened": True, "url": url, "title": plan["title"], "by": coder}
        except Exception as exc:
            plan["body"] += f"\n\n(autopilot could not open the PR automatically: {exc})"

    # Default / fallback: record a reviewable proposal.
    art = _remember(project, coder, plan, opened=False)
    return {"opened": False, "proposed": True, "title": plan["title"], "by": coder,
            "artifact": art.get("name") if art else None}


def _remember(project: str, coder: str, plan: dict, opened: bool, url: str = "") -> dict | None:
    content = (f"# {plan['title']}\n\n{plan.get('body', '')}\n\n"
               + (f"Opened: {url}\n\n" if url else "")
               + (f"```diff\n{plan.get('diff', '')}\n```\n" if plan.get("diff") else ""))
    art = None
    try:
        from . import artifacts
        art = artifacts.forge(coder, f"{'PR' if opened else 'Proposed PR'} — {project} #{int(time.time())}",
                              "note", content, description=f"{'Opened' if opened else 'Proposed'} fix for {project}.")
    except Exception:
        art = None
    try:
        from . import sectmemory
        sectmemory.add(f"{'Opened PR' if opened else 'Proposed fix'} for {project}: {plan['title']}. {plan.get('body','')[:300]}",
                       source=coder, agent=coder, kind="pr")
    except Exception:
        pass
    return art
