"""Operator audit log — who did what.

Records every mutating action taken through the API (who, what, when, outcome)
so there's accountability now that the dashboard can start/stop bots, silence
alerts, strike disciples down, and pause the autopilot. Recorded generically by
a middleware in :mod:`app`, persisted via the store, and shown in the Ops tab.
"""
from __future__ import annotations

import os
import threading
import time

CAP = max(100, int(os.getenv("MAYBOT_AUDIT_CAP", "1000")))

_lock = threading.Lock()
_log: list[dict] = []
_seq = 0


def record(actor: str, action: str, *, target: str = "", status: int | None = None,
           detail: str = "") -> dict:
    global _seq
    with _lock:
        _seq += 1
        rec = {"id": _seq, "actor": actor or "anon", "action": action, "target": target,
               "status": status, "detail": detail[:300], "ts": int(time.time() * 1000)}
        _log.append(rec)
        if len(_log) > CAP:
            del _log[:len(_log) - CAP]
    _save()
    return rec


def recent(limit: int = 200) -> list[dict]:
    with _lock:
        return [dict(r) for r in _log[-limit:][::-1]]


def snapshot() -> dict:
    with _lock:
        return {"count": len(_log), "entries": [dict(r) for r in _log[-200:][::-1]]}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("audit", {"log": _log[-CAP:], "seq": _seq})


def load_persisted() -> None:
    from . import store
    data = store.load_state("audit")
    if not data:
        return
    global _seq
    with _lock:
        _log.extend(data.get("log") or [])
        _seq = max(_seq, int(data.get("seq") or 0))


def clear() -> None:
    global _seq
    with _lock:
        _log.clear()
        _seq = 0
