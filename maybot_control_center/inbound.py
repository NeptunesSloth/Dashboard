"""Inbound alert ingestion — external systems push incidents INTO the dashboard.

Lets Alertmanager, CI, cron, or any webhook ``POST /api/ingest/alert`` so external
alerts land in one place: stored in a bounded feed, routed to the configured
webhooks/Hall, and written to the sect's memory. Auth is the operator control
token, or a dedicated ``MAYBOT_INGEST_TOKEN`` so external tools don't need the
dashboard token.
"""
from __future__ import annotations

import os
import threading
import time

CAP = max(50, int(os.getenv("MAYBOT_INBOUND_CAP", "500")))
INGEST_TOKEN = os.getenv("MAYBOT_INGEST_TOKEN", "")
_SEVERITIES = {"info", "warning", "error", "critical"}

_lock = threading.Lock()
_alerts: list[dict] = []
_seq = 0


def ingest(source: str, severity: str, title: str, message: str = "",
           project: str = "", device: str = "") -> dict:
    global _seq
    sev = (severity or "info").lower()
    if sev not in _SEVERITIES:
        sev = "info"
    with _lock:
        _seq += 1
        rec = {"id": _seq, "source": (source or "external")[:80], "severity": sev,
               "title": (title or "alert")[:200], "message": (message or "")[:1000],
               "project": project[:128], "device": device[:128], "ts": int(time.time() * 1000)}
        _alerts.append(rec)
        if len(_alerts) > CAP:
            del _alerts[:len(_alerts) - CAP]
    _save()
    try:
        from . import notifier
        notifier.notify_event("inbound", f"{rec['source']}: {rec['title']}",
                              f"[{rec['severity']}] {rec['message']}")
    except Exception:
        pass
    try:
        from . import sectmemory
        sectmemory.add(f"Inbound alert from {rec['source']} ({rec['severity']}): {rec['title']}. {rec['message']}",
                       source=rec["source"], kind="alert")
    except Exception:
        pass
    return rec


def recent(limit: int = 200) -> list[dict]:
    with _lock:
        return [dict(r) for r in _alerts[-limit:][::-1]]


def snapshot() -> dict:
    with _lock:
        return {"count": len(_alerts), "alerts": [dict(r) for r in _alerts[-200:][::-1]]}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("inbound", {"alerts": _alerts[-CAP:], "seq": _seq})


def load_persisted() -> None:
    from . import store
    data = store.load_state("inbound")
    if not data:
        return
    global _seq
    with _lock:
        _alerts.extend(data.get("alerts") or [])
        _seq = max(_seq, int(data.get("seq") or 0))


def clear() -> None:
    global _seq
    with _lock:
        _alerts.clear()
        _seq = 0
