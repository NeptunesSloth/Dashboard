"""Maintenance windows / alert silencing.

When you knowingly restart a bot or take a device down for upkeep, you don't
want to be paged for the self-inflicted ``error`` state. A *silence* mutes
alerting (and incident auto-dispatch / remediation) for a target until it
expires, is lifted, or the target recovers.

Targets are matched against a project's ``device:project`` key:

  - ``"*"``                — silence everything
  - ``"device:*"``         — silence every project on one device
  - ``"device:project"``   — silence one project

State is intentionally in-memory (a monitoring aid, not a system of record),
mirroring :mod:`history`; it resets when the control center restarts.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
# target -> {"target", "until" (epoch secs or None=indefinite), "reason", "who",
#            "created_at", "clear_on_recovery"}
_silences: dict[str, dict] = {}


def _now() -> float:
    return time.time()


def _key(device: str, name: str) -> str:
    return f"{device}:{name}"


def _matches(target: str, key: str) -> bool:
    if target == "*":
        return True
    if target == key:
        return True
    if target.endswith(":*"):
        return key.startswith(target[:-1])  # "device:*" -> prefix "device:"
    return False


def _prune(now: float) -> None:
    for t, s in list(_silences.items()):
        if s["until"] is not None and s["until"] <= now:
            del _silences[t]


def silence(target: str, minutes: float = 60.0, reason: str = "",
            who: str = "operator", clear_on_recovery: bool = True) -> dict:
    """Mute alerting for ``target``. ``minutes <= 0`` silences indefinitely
    (until lifted or, if enabled, the target recovers to ok)."""
    now = _now()
    until = None if minutes <= 0 else now + minutes * 60.0
    rec = {"target": target, "until": until, "reason": reason.strip()[:200],
           "who": who, "created_at": now, "clear_on_recovery": bool(clear_on_recovery)}
    with _lock:
        _silences[target] = rec
    return _public(rec, now)


def unsilence(target: str) -> bool:
    with _lock:
        return _silences.pop(target, None) is not None


def is_silenced(device: str, name: str) -> bool:
    key = _key(device, name)
    now = _now()
    with _lock:
        _prune(now)
        return any(_matches(t, key) for t in _silences)


def note_recovery(device: str, name: str) -> None:
    """A project returned to ok — drop any recovery-clearing silence matching it."""
    key = _key(device, name)
    with _lock:
        for t, s in list(_silences.items()):
            if s.get("clear_on_recovery") and _matches(t, key):
                del _silences[t]


def _public(rec: dict, now: float) -> dict:
    out = dict(rec)
    out["expires_in"] = None if rec["until"] is None else max(0, round(rec["until"] - now))
    return out


def active() -> list[dict]:
    now = _now()
    with _lock:
        _prune(now)
        return [_public(s, now) for s in sorted(_silences.values(), key=lambda s: s["created_at"])]


def snapshot() -> dict:
    return {"silences": active(), "now": int(_now())}


def clear() -> None:
    with _lock:
        _silences.clear()
