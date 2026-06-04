"""Incident acknowledgement & ownership — the "Sworn Oath".

When something is on fire, a disciple (or the Ancestor) *swears an oath* to
handle it: claiming the incident records who took it up and when. Unlike a
maintenance silence (which says "ignore this"), an oath says "someone owns
this" — so repeat pages are suppressed while it's being worked, the dashboard
shows the owner, and the oath auto-releases when the project recovers.

State is in-memory (a coordination aid), keyed by the project's ``device:project``.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
# key -> {"target", "who", "note", "since"}
_oaths: dict[str, dict] = {}


def _key(device: str, name: str) -> str:
    return f"{device}:{name}"


def claim(target: str, who: str, note: str = "") -> dict:
    rec = {"target": target, "who": who, "note": note.strip()[:200], "since": int(time.time() * 1000)}
    with _lock:
        _oaths[target] = rec
    return dict(rec)


def release(target: str) -> bool:
    with _lock:
        return _oaths.pop(target, None) is not None


def is_claimed(device: str, name: str) -> bool:
    with _lock:
        return _key(device, name) in _oaths


def owner(device: str, name: str) -> str | None:
    with _lock:
        rec = _oaths.get(_key(device, name))
        return rec["who"] if rec else None


def note_recovery(device: str, name: str) -> None:
    """A claimed incident that recovered is considered resolved — release it."""
    release(_key(device, name))


def annotate(project: dict) -> dict:
    key = _key(project.get("device", "?"), project.get("name", "?"))
    with _lock:
        rec = _oaths.get(key)
    if rec:
        project["oath"] = {"who": rec["who"], "since": rec["since"], "note": rec["note"]}
    return project


def snapshot() -> dict:
    with _lock:
        return {"oaths": [dict(r) for r in sorted(_oaths.values(), key=lambda r: r["since"])]}


def clear() -> None:
    with _lock:
        _oaths.clear()
