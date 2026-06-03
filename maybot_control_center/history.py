"""Server-side metrics history.

Keeps a bounded, in-memory time series per project so the dashboard's
sparklines persist across page refreshes and are shared across all viewers
(unlike the previous browser-only history, which reset on every reload).

The store is intentionally in-memory: it is a monitoring aid, not a system of
record. It is reset when the control center restarts.
"""
from __future__ import annotations

import os
import threading
import time

from . import store

# How many points to retain per project, and how many distinct project series
# to track, before older data / new series are dropped. Both are configurable
# so large fleets can tune memory use.
MAX_POINTS = max(2, int(os.getenv("MAYBOT_HISTORY_MAX_POINTS", "240")))
MAX_SERIES = max(1, int(os.getenv("MAYBOT_HISTORY_MAX_SERIES", "500")))

_lock = threading.Lock()
_series: dict[str, list[dict]] = {}


def _key(device: str, name: str) -> str:
    return f"{device}:{name}"


def _pnl(project: dict):
    try:
        return round(float(project.get("metrics", {}).get("profit_today")), 4)
    except (TypeError, ValueError):
        return None


def record(projects: list[dict]) -> None:
    """Append a snapshot point for each project to its series."""
    now = int(time.time() * 1000)
    with _lock:
        for p in projects:
            key = _key(p.get("device", "?"), p.get("name", "?"))
            buf = _series.get(key)
            if buf is None:
                if len(_series) >= MAX_SERIES:
                    continue
                buf = _series[key] = []
            point = {"ts": now, "health": p.get("health", "unknown"), "pnl": _pnl(p)}
            buf.append(point)
            if len(buf) > MAX_POINTS:
                del buf[:-MAX_POINTS]
            if store.enabled():
                store.add_history(p.get("device", "?"), p.get("name", "?"), point)


def attach(projects: list[dict]) -> None:
    """Attach each project's recorded history to its dict in-place."""
    with _lock:
        for p in projects:
            p["history"] = list(_series.get(_key(p.get("device", "?"), p.get("name", "?")), []))


def get(device: str, name: str) -> list[dict]:
    """Return a copy of the recorded series for one project."""
    with _lock:
        return list(_series.get(_key(device, name), []))


def load_persisted() -> None:
    if not store.enabled():
        return
    with _lock:
        for key, points in store.load_history().items():
            _series[key] = points[-MAX_POINTS:]


def clear() -> None:
    with _lock:
        _series.clear()
