"""Dead-man's switch — ping an external heartbeat URL on an interval so that if
*this* dashboard dies, the outside monitor (healthchecks.io, Better Uptime, a
cron-ping, …) notices the silence and alerts you. Every other alert flows
through the dashboard; this is the one that catches the dashboard itself going
down. Configured entirely in-app and persisted.
"""
from __future__ import annotations

import os
import threading
import time
import urllib.request

_url = os.getenv("MAYBOT_HEARTBEAT_URL", "").strip()
_interval = float(os.getenv("MAYBOT_HEARTBEAT_INTERVAL", "60") or 60)
_lock = threading.Lock()
_last: dict = {"ok": None, "at": 0, "error": ""}
_started = False
MIN_INTERVAL = 15.0


def _http_get(url: str, timeout: float = 10.0) -> int:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (operator-supplied URL)
        return int(getattr(r, "status", 200))


def status() -> dict:
    with _lock:
        return {"configured": bool(_url), "url": _url, "interval": _interval, "last": dict(_last)}


def configure(url: str, interval: float | None = None) -> dict:
    global _url, _interval
    with _lock:
        _url = (url or "").strip()
        if interval:
            try:
                _interval = max(MIN_INTERVAL, float(interval))
            except (TypeError, ValueError):
                pass
    _persist()
    return status()


def ping_once() -> bool:
    with _lock:
        url = _url
    if not url:
        return False
    try:
        ok = 200 <= _http_get(url) < 400
        _set(ok, "")
        return ok
    except Exception as exc:  # noqa: BLE001
        _set(False, str(exc))
        return False


def _set(ok: bool, err: str) -> None:
    with _lock:
        _last.update(ok=ok, at=int(time.time() * 1000), error=err)


def _loop() -> None:
    while True:
        with _lock:
            interval = _interval
            armed = bool(_url)
        if armed:
            ping_once()
        time.sleep(max(MIN_INTERVAL, interval))


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    load_persisted()
    threading.Thread(target=_loop, daemon=True).start()


def _persist() -> None:
    from . import store
    if store.enabled():
        store.save_state("deadman", {"url": _url, "interval": _interval})


def load_persisted() -> None:
    global _url, _interval
    from . import store
    data = store.load_state("deadman")
    if data:
        with _lock:
            _url = (data.get("url") or _url or "").strip()
            _interval = data.get("interval") or _interval


def clear() -> None:
    global _url
    with _lock:
        _url = ""
