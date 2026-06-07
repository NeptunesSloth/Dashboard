"""Self-observability — the control center watching itself.

A monitoring tool should be observable too. This module tracks the health of
the control center's *own* internals — how fresh the last device poll is, how
long polls take, and how many API requests/errors it has served — so operators
(and Prometheus) can tell when the dashboard itself is stale or struggling,
not just the fleet it watches.

All state is in-memory and process-local. ``note_poll`` is called by the
aggregator after each poll; ``note_request`` by the API middleware.
"""
from __future__ import annotations

import os
import threading
import time

# A poll older than this many seconds is considered stale (the dashboard may be
# showing old data — e.g. the background poller or all agents are wedged).
STALE_AFTER = float(os.getenv("MAYBOT_POLL_STALE_AFTER_SECONDS", "120"))

_START = time.time()
_lock = threading.Lock()

_last_poll_ts: float = 0.0
_last_poll_ms: float = 0.0
_last_devices: int = 0
_last_projects: int = 0
_poll_count: int = 0

_requests: int = 0
_errors: int = 0


def note_poll(duration_ms: float, devices: int, projects: int) -> None:
    """Record that a device-aggregation poll just completed."""
    with _lock:
        global _last_poll_ts, _last_poll_ms, _last_devices, _last_projects, _poll_count
        _last_poll_ts = time.time()
        _last_poll_ms = round(duration_ms, 1)
        _last_devices = devices
        _last_projects = projects
        _poll_count += 1


def note_request(status_code: int) -> None:
    """Record one served API request (and whether it errored, 5xx)."""
    with _lock:
        global _requests, _errors
        _requests += 1
        if status_code >= 500:
            _errors += 1


def poll_age_seconds() -> float | None:
    with _lock:
        if _last_poll_ts == 0.0:
            return None
        return round(time.time() - _last_poll_ts, 1)


def is_stale() -> bool:
    age = poll_age_seconds()
    return age is None or age > STALE_AFTER


def snapshot() -> dict:
    age = poll_age_seconds()
    with _lock:
        return {
            "uptime_seconds": round(time.time() - _START, 1),
            "last_poll_age_seconds": age,
            "last_poll_duration_ms": _last_poll_ms or None,
            "last_poll_devices": _last_devices,
            "last_poll_projects": _last_projects,
            "poll_count": _poll_count,
            "poll_stale": age is None or age > STALE_AFTER,
            "stale_after_seconds": STALE_AFTER,
            "api_requests": _requests,
            "api_errors": _errors,
        }


def clear() -> None:
    with _lock:
        global _last_poll_ts, _last_poll_ms, _last_devices, _last_projects, _poll_count, _requests, _errors
        _last_poll_ts = 0.0
        _last_poll_ms = 0.0
        _last_devices = 0
        _last_projects = 0
        _poll_count = 0
        _requests = 0
        _errors = 0
