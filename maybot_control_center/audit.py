"""Operator audit log — who did what.

Records every mutating action taken through the API (who, what, when, outcome)
so there's accountability now that the dashboard can start/stop bots, silence
alerts, strike disciples down, and pause the autopilot. Recorded generically by
a middleware in :mod:`app`, persisted via the store, and shown in the Ops tab.

Tamper-evident: every entry carries a SHA-256 ``hash`` over its own fields plus
the previous entry's hash, forming a chain — editing or deleting an entry breaks
every hash after it. ``verify()`` walks the chain; ``export_jsonl()`` emits the
log as JSON Lines for SIEM ingestion.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

CAP = max(100, int(os.getenv("MAYBOT_AUDIT_CAP", "1000")))

_lock = threading.Lock()
_log: list[dict] = []
_seq = 0
_last_hash = ""


def _entry_hash(rec: dict, prev: str) -> str:
    payload = json.dumps([rec["id"], rec["actor"], rec["action"], rec["target"],
                          rec["status"], rec["detail"], rec["ts"], prev],
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def record(actor: str, action: str, *, target: str = "", status: int | None = None,
           detail: str = "") -> dict:
    global _seq, _last_hash
    with _lock:
        _seq += 1
        rec = {"id": _seq, "actor": actor or "anon", "action": action, "target": target,
               "status": status, "detail": detail[:300], "ts": int(time.time() * 1000)}
        rec["prev"] = _last_hash
        rec["hash"] = _entry_hash(rec, _last_hash)
        _last_hash = rec["hash"]
        _log.append(rec)
        if len(_log) > CAP:
            del _log[:len(_log) - CAP]
    _save()
    return rec


def verify() -> dict:
    """Walk the hash chain; report the first break (or a clean bill of health).

    Entries recorded before hashing existed (no ``hash`` field) are counted as
    ``legacy`` and skipped — the chain is verified from the first hashed entry.
    """
    with _lock:
        entries = [dict(r) for r in _log]
    legacy = sum(1 for r in entries if not r.get("hash"))
    hashed = [r for r in entries if r.get("hash")]
    prev = None
    for r in hashed:
        if r["hash"] != _entry_hash(r, r.get("prev", "")):
            return {"ok": False, "checked": len(hashed), "legacy": legacy,
                    "broken_at": r["id"], "reason": "entry hash mismatch (contents altered)"}
        # Continuity only checkable between consecutive retained entries; the cap
        # prunes old entries, so the first retained one has nothing to link back to.
        if prev is not None and r.get("prev", "") != prev:
            return {"ok": False, "checked": len(hashed), "legacy": legacy,
                    "broken_at": r["id"], "reason": "chain break (entries removed or reordered)"}
        prev = r["hash"]
    return {"ok": True, "checked": len(hashed), "legacy": legacy}


def export_jsonl() -> str:
    """The full retained log as JSON Lines (one entry per line), oldest first —
    the standard shape for shipping to a SIEM / log pipeline."""
    with _lock:
        return "\n".join(json.dumps(r, separators=(",", ":")) for r in _log)


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
    global _seq, _last_hash
    with _lock:
        _log.extend(data.get("log") or [])
        _seq = max(_seq, int(data.get("seq") or 0))
        for r in reversed(_log):
            if r.get("hash"):
                _last_hash = r["hash"]
                break


def clear() -> None:
    global _seq, _last_hash
    with _lock:
        _log.clear()
        _seq = 0
        _last_hash = ""
