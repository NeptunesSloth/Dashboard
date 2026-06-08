"""Global safe mode (panic button) — one switch that halts ALL automation:
autopilot, escalation auto-actions, scheduled missions, and self-healing
runbooks. The fleet freezes in a known-safe state; manual operator actions still
work. For the moment an automated rule misbehaves and you need to stop
everything without SSH. Persisted.
"""
from __future__ import annotations

import threading

_engaged = False
_lock = threading.Lock()


def engaged() -> bool:
    with _lock:
        return _engaged


def set_engaged(on: bool) -> bool:
    global _engaged
    with _lock:
        _engaged = bool(on)
    _persist()
    return engaged()


def status() -> dict:
    return {"engaged": engaged()}


def _persist() -> None:
    from . import store
    if store.enabled():
        store.save_state("safemode", {"engaged": engaged()})


def load_persisted() -> None:
    global _engaged
    from . import store
    data = store.load_state("safemode")
    if data:
        with _lock:
            _engaged = bool(data.get("engaged"))


def clear() -> None:
    global _engaged
    with _lock:
        _engaged = False
