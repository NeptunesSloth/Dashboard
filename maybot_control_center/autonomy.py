"""Bounded autonomy for agent tool use.

Default OFF: an agent's tool request is queued for human approval even if the
tool is ``auto_approve`` — so enabling guarded tools never silently lets agents
act on their own. Turn autonomy on (``MAYBOT_AUTONOMY=1``) and an agent may
auto-run a tool only when ALL hold:

- the tool is ``auto_approve`` (operator marked it safe to run unattended),
- autonomy is enabled and not **paused** (the global kill switch), and
- the agent is under its per-task budget (``MAYBOT_AUTONOMY_MAX_CALLS``).

Operator-initiated runs are unaffected (operator authority). The budget resets
on each fresh operator task (see agents.assign_task).
"""
from __future__ import annotations

import os
import threading

ENABLED = os.getenv("MAYBOT_AUTONOMY", "0").lower() in ("1", "true", "yes", "on")
MAX_CALLS = max(0, int(os.getenv("MAYBOT_AUTONOMY_MAX_CALLS", "3")))

_lock = threading.Lock()
_paused = False
_used: dict[str, int] = {}


def status() -> dict:
    with _lock:
        return {"enabled": ENABLED, "paused": _paused, "max_calls": MAX_CALLS}


def set_paused(value: bool) -> dict:
    global _paused
    with _lock:
        _paused = bool(value)
    return status()


def reset(agent: str) -> None:
    with _lock:
        _used[agent] = 0


def allow(requester: str, tool: dict) -> bool:
    """Decide whether a tool request may run without human approval."""
    if not tool.get("auto_approve"):
        return False  # only operator-marked-safe tools are ever auto-runnable
    if requester == "operator":
        return True   # operator authority — unbounded by design
    with _lock:
        if not ENABLED or _paused:
            return False
        used = _used.get(requester, 0)
        if used >= MAX_CALLS:
            return False
        _used[requester] = used + 1
        return True


def clear() -> None:
    global _paused
    with _lock:
        _used.clear()
        _paused = False
