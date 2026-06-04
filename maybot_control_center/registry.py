"""Agent auto-registration — agents announce themselves instead of being
hand-listed in ``devices.yaml``.

An agent host ``POST``s ``/api/agents/register`` with its name + URL + token; the
control center stores it (persisted) and polls it alongside the file-configured
devices. Registration is gated by ``MAYBOT_REGISTER_TOKEN`` (or the operator
token). De-register to drop one.
"""
from __future__ import annotations

import os
import threading
import time

REGISTER_TOKEN = os.getenv("MAYBOT_REGISTER_TOKEN", "")

_lock = threading.Lock()
_devices: dict[str, dict] = {}     # name -> device dict


def register(name: str, url: str, api_token: str = "", timeout=None) -> dict:
    rec = {"name": name, "url": url.rstrip("/"), "api_token": api_token,
           "registered_at": int(time.time() * 1000), "source": "registered"}
    if timeout:
        try:
            rec["timeout"] = float(timeout)
        except (TypeError, ValueError):
            pass
    with _lock:
        _devices[name] = rec
    _save()
    return dict(rec)


def deregister(name: str) -> bool:
    with _lock:
        removed = _devices.pop(name, None) is not None
    if removed:
        _save()
    return removed


def registered() -> list[dict]:
    """Device dicts for the poller (same shape as devices.yaml entries)."""
    with _lock:
        return [dict(d) for d in _devices.values()]


def snapshot() -> dict:
    with _lock:
        return {"count": len(_devices), "devices": [dict(d) for d in _devices.values()]}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("registry", {"devices": _devices})


def load_persisted() -> None:
    from . import store
    data = store.load_state("registry")
    if data:
        with _lock:
            _devices.update(data.get("devices") or {})


def clear() -> None:
    with _lock:
        _devices.clear()
