"""Alert acknowledgement & snooze — the operator's "I've got eyes on it".

Distinct from a sworn *oath* (ownership of a live incident) and a maintenance
*silence* (a planned, target-pattern mute): an **ack** is a lightweight, alert-
level "stop paging me about this for a while". An operator acks a project's
alert (optionally with a snooze duration); while acked, the notifier suppresses
repeat pages and the escalation clock is held off. Acks are time-boxed — they
expire after ``minutes`` (default ``MAYBOT_ACK_DEFAULT_MINUTES``) — and a
recovery to ``ok`` clears them automatically.

State is in-memory (a coordination aid) and persisted through the store, keyed
by the project's ``device:project``.
"""
from __future__ import annotations

import os
import threading
import time

DEFAULT_MINUTES = float(os.getenv("MAYBOT_ACK_DEFAULT_MINUTES", "60"))

_lock = threading.Lock()
# key -> {"target", "who", "reason", "since": ms, "until": ms|None}
_acks: dict[str, dict] = {}


def _key(device: str, name: str) -> str:
    return f"{device}:{name}"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _live(rec: dict, now_ms: int | None = None) -> bool:
    now_ms = now_ms if now_ms is not None else _now_ms()
    until = rec.get("until")
    return until is None or now_ms < until


def ack(target: str, who: str, minutes: float | None = None, reason: str = "") -> dict:
    """Acknowledge ``target`` (``device:project``) for ``minutes`` (None/<=0 = no expiry)."""
    mins = DEFAULT_MINUTES if minutes is None else float(minutes)
    now = _now_ms()
    rec = {
        "target": target,
        "who": who,
        "reason": reason.strip()[:200],
        "since": now,
        "until": (now + int(mins * 60_000)) if mins and mins > 0 else None,
    }
    with _lock:
        _acks[target] = rec
    _save()
    return dict(rec)


def resolve(target: str) -> bool:
    """Clear an acknowledgement (e.g. the operator marks it handled)."""
    with _lock:
        removed = _acks.pop(target, None) is not None
    if removed:
        _save()
    return removed


def is_acked(device: str, name: str) -> bool:
    """True while a live (un-expired) ack exists for the project."""
    key = _key(device, name)
    now = _now_ms()
    with _lock:
        rec = _acks.get(key)
        if rec is None:
            return False
        if not _live(rec, now):
            del _acks[key]            # lazily reap expired acks
            expired = True
        else:
            return True
    if expired:
        _save()
    return False


def note_recovery(device: str, name: str) -> None:
    """A project that recovered to ``ok`` no longer needs its ack."""
    resolve(_key(device, name))


def annotate(project: dict) -> dict:
    key = _key(project.get("device", "?"), project.get("name", "?"))
    now = _now_ms()
    with _lock:
        rec = _acks.get(key)
        live = rec is not None and _live(rec, now)
    if live:
        project["ack"] = {"who": rec["who"], "since": rec["since"],
                          "until": rec["until"], "reason": rec["reason"]}
    return project


def snapshot() -> dict:
    now = _now_ms()
    with _lock:
        rows = [dict(r) for r in _acks.values() if _live(r, now)]
    rows.sort(key=lambda r: r["since"])
    return {"acks": rows, "default_minutes": DEFAULT_MINUTES}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("acks", _acks)


def load_persisted() -> None:
    from . import store
    data = store.load_state("acks")
    if data:
        with _lock:
            _acks.update(data)


def clear() -> None:
    with _lock:
        _acks.clear()
    _save()
