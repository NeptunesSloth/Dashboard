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
import time

from . import pills

ENABLED = os.getenv("MAYBOT_AUTONOMY", "0").lower() in ("1", "true", "yes", "on")
MAX_CALLS = max(0, int(os.getenv("MAYBOT_AUTONOMY_MAX_CALLS", "3")))
# Optional local-time window for auto-runs, "START-END" 24h (e.g. "9-17").
# Empty = always allowed. Supports overnight windows (e.g. "22-6").
HOURS = os.getenv("MAYBOT_AUTONOMY_HOURS", "")

_lock = threading.Lock()
_paused = False
_used: dict[tuple[str, str], int] = {}  # (agent, tool) -> auto-runs this task


def _window_ok() -> bool:
    if not HOURS:
        return True
    try:
        s, e = (int(x) for x in HOURS.split("-", 1))
    except Exception:
        return True
    h = time.localtime().tm_hour
    return s <= h < e if s <= e else (h >= s or h < e)


def status() -> dict:
    with _lock:
        return {"enabled": ENABLED, "paused": _paused, "max_calls": MAX_CALLS,
                "hours": HOURS, "in_window": _window_ok()}


def set_paused(value: bool) -> dict:
    global _paused
    with _lock:
        _paused = bool(value)
    return status()


def reset(agent: str) -> None:
    with _lock:
        for key in [k for k in _used if k[0] == agent]:
            _used.pop(key, None)


def allow(requester: str, tool: dict) -> bool:
    """Decide whether a tool request may run without human approval."""
    if not tool.get("auto_approve"):
        return False  # only operator-marked-safe tools are ever auto-runnable
    if requester == "operator":
        return True   # operator authority — unbounded by design
    name = tool.get("name", "")
    from . import reputation  # lazy: reputation reads the tool audit log
    if reputation.is_probation(requester):
        return False  # untrusted disciples are demoted back to human approval
    cap = (max(0, int(tool.get("max_auto_per_task", MAX_CALLS)))
           + pills.autonomy_bonus(requester) + reputation.autonomy_bonus(requester))
    with _lock:
        if not ENABLED or _paused or not _window_ok():
            return False
        key = (requester, name)
        if _used.get(key, 0) >= cap:
            return False
        _used[key] = _used.get(key, 0) + 1
        return True


def clear() -> None:
    global _paused
    with _lock:
        _used.clear()
        _paused = False
