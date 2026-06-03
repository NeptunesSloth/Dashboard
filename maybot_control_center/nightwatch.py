"""Night-Watch: on-call rotation + first-line auto-triage.

The sect keeps a **night watch** — an ordered roster of disciples who take
turns standing guard. Each disciple holds the watch for one *shift*; when the
shift ends, the duty passes to the next disciple in the rotation, wrapping
around the roster forever.

Incidents that arrive are **triaged** to whoever is on watch. Routine warnings
the watcher handles themselves (``auto_triaged``); a genuine ``error`` is
**escalated** to the Ancestor (the human operator). When a disciple resolves an
incident they were assigned, they are rewarded with spirit stones.
"""
from __future__ import annotations

import os
import threading
import time

# Length of a single watch shift, in seconds.
SHIFT_SECONDS = int(os.getenv("MAYBOT_WATCH_SHIFT_SECONDS", "3600"))
# Spirit stones awarded to a watcher who resolves an incident.
AWARD = int(os.getenv("MAYBOT_WATCH_REWARD", "5"))

_lock = threading.Lock()
_rotation: list[str] = []
_epoch: float = 0.0
_log: list[dict] = []
_next_id: int = 0


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def set_rotation(names: list[str]) -> dict:
    """Set the ordered roster of disciples on the watch, resetting the epoch.

    Falsy entries are dropped and order-preserving de-duplication is applied.
    """
    seen: set[str] = set()
    roster: list[str] = []
    for name in names or []:
        if name and name not in seen:
            seen.add(name)
            roster.append(name)
    with _lock:
        global _rotation, _epoch
        _rotation = roster
        _epoch = time.time()
    return status()


def current_watcher(now: float | None = None) -> str | None:
    """Who is on watch right now, or None if the rotation is empty."""
    with _lock:
        n = len(_rotation)
        if n == 0:
            return None
        idx = int((_now(now) - _epoch) // SHIFT_SECONDS) % n
        return _rotation[idx]


def next_watcher(now: float | None = None) -> str | None:
    """The disciple who takes the next shift, or None if the rotation is empty."""
    with _lock:
        n = len(_rotation)
        if n == 0:
            return None
        idx = (int((_now(now) - _epoch) // SHIFT_SECONDS) + 1) % n
        return _rotation[idx]


def shift_remaining(now: float | None = None) -> int:
    """Seconds left in the current shift (0 if the rotation is empty)."""
    with _lock:
        if not _rotation:
            return 0
        elapsed = _now(now) - _epoch
        return int(SHIFT_SECONDS - (elapsed % SHIFT_SECONDS))


def triage(incident: dict, now: float | None = None) -> dict:
    """Assign an incident to the current watcher and record a triage entry.

    Routine warnings are ``auto_triaged``; ``error`` severity is ``escalated``
    to the Ancestor. If the rotation is empty the incident is ``unassigned``.
    """
    watcher = current_watcher(now)
    severity = (incident or {}).get("severity")
    if watcher is None:
        st = "unassigned"
    elif severity == "error":
        st = "escalated"
    else:
        st = "auto_triaged"
    with _lock:
        global _next_id
        rec = {
            "id": _next_id,
            "watcher": watcher,
            "incident": incident,
            "status": st,
            "ts": int(time.time() * 1000),
        }
        _next_id += 1
        _log.append(rec)
        return dict(rec)


def handled(record_id: int) -> bool:
    """Mark a triage record resolved and reward the assigned watcher.

    Returns True if a record with ``record_id`` was found.
    """
    with _lock:
        rec = next((r for r in _log if r["id"] == record_id), None)
        if rec is None:
            return False
        rec["status"] = "resolved"
        watcher = rec.get("watcher")
    if watcher and watcher != "operator":
        from . import cultivation  # lazy import to avoid import cycles
        cultivation.reward(watcher, AWARD)
    return True


def log(limit: int = 50) -> list[dict]:
    """Recent triage records (copies), newest last."""
    with _lock:
        return [dict(r) for r in _log[-limit:]]


def status() -> dict:
    with _lock:
        open_count = sum(1 for r in _log if r["status"] != "resolved")
        rotation = list(_rotation)
    return {
        "rotation": rotation,
        "current": current_watcher(),
        "next": next_watcher(),
        "shift_seconds": SHIFT_SECONDS,
        "shift_remaining": shift_remaining(),
        "open": open_count,
    }


def clear() -> None:
    """Reset all module state (used by tests)."""
    with _lock:
        global _rotation, _epoch, _log, _next_id
        _rotation = []
        _epoch = 0.0
        _log = []
        _next_id = 0
