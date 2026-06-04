"""Synthetic uptime probes — the "Warding Talismans".

Talismans are wards the sect hangs at the gates of services it cannot reach
through an agent: each one periodically pings a URL from the control center
itself and records status + latency. Results feed the same :mod:`history`
pipeline (device ``warding``) so the SLO/uptime view covers them too.

``talismans.yaml`` (see talismans.yaml.example)::

    talismans:
      - name: public-site
        url: https://example.com/health
        expect_status: 200
        timeout: 5
        every_seconds: 60

No file → idle. This is blackbox/synthetic monitoring, independent of any agent.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import requests
import yaml

from . import history

TALISMANS_FILE = Path(os.getenv("MAYBOT_TALISMANS_FILE", "talismans.yaml"))
DEVICE = "warding"

_lock = threading.Lock()
_results: dict[str, dict] = {}   # name -> latest result
_last: dict[str, float] = {}     # name -> last probe time
_started = False


def load_talismans() -> list[dict]:
    if not TALISMANS_FILE.exists():
        return []
    data = yaml.safe_load(TALISMANS_FILE.read_text(encoding="utf-8")) or {}
    t = data.get("talismans", [])
    return t if isinstance(t, list) else []


def probe(t: dict) -> dict:
    """Hit one talisman's URL and return a result dict (also records history)."""
    name = t.get("name") or t.get("url", "?")
    url = t.get("url", "")
    expect = int(t.get("expect_status", 200))
    timeout = float(t.get("timeout", 5))
    start = time.time()
    health, status_code, error = "error", None, None
    try:
        r = requests.get(url, timeout=timeout)
        status_code = r.status_code
        health = "ok" if r.status_code == expect else "error"
    except Exception as exc:
        error = str(exc)
    latency_ms = round((time.time() - start) * 1000)
    result = {"name": name, "url": url, "health": health, "status_code": status_code,
              "latency_ms": latency_ms, "error": error, "ts": int(time.time() * 1000)}
    with _lock:
        _results[name] = result
    # Feed the shared history/SLO pipeline as a synthetic project.
    history.record([{"device": DEVICE, "name": name, "health": health,
                     "metrics": {"profit_today": latency_ms}}])
    return result


def tick(now: float | None = None) -> list[str]:
    """Probe any talismans whose interval has elapsed. Returns names probed."""
    now = now if now is not None else time.time()
    probed = []
    for t in load_talismans():
        name = t.get("name") or t.get("url")
        if not name:
            continue
        every = max(5, int(t.get("every_seconds", 60)))
        with _lock:
            last = _last.get(name)
            if last is not None and now - last < every:
                continue
            _last[name] = now
        probe(t)
        probed.append(name)
    return probed


def snapshot() -> dict:
    with _lock:
        results = sorted(_results.values(), key=lambda r: r["name"])
    return {"enabled": bool(load_talismans()), "talismans": results}


def _loop() -> None:
    while True:
        time.sleep(15)
        try:
            tick()
        except Exception:
            pass


def start() -> bool:
    global _started
    if _started or not load_talismans():
        return False
    _started = True
    threading.Thread(target=_loop, daemon=True).start()
    return True


def clear() -> None:
    with _lock:
        _results.clear()
        _last.clear()
