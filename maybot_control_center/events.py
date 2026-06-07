"""Lightweight in-process pub/sub for Server-Sent Events.

Background threads call ``publish(kind)`` when agent state, comms, or tool calls
change; the ``/api/stream`` endpoint drains a per-subscriber queue and yields SSE
frames, so the dashboard updates instantly instead of waiting for the poll.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time

_subs: set[queue.Queue] = set()
_lock = threading.Lock()
_hb_started = False
HEARTBEAT_SECONDS = float(os.getenv("MAYBOT_HEARTBEAT_SECONDS", "7"))


def _heartbeat() -> None:
    # Emit a periodic 'tick' so live clients can refresh PnL/overview without
    # polling. Only fires while someone is listening; the on-demand /api/overview
    # path never publishes, so this can't cause a refresh loop.
    while True:
        time.sleep(HEARTBEAT_SECONDS)
        with _lock:
            alive = len(_subs)
        if alive:
            publish("tick")


def _ensure_heartbeat() -> None:
    global _hb_started
    if _hb_started or HEARTBEAT_SECONDS <= 0:
        return
    _hb_started = True
    threading.Thread(target=_heartbeat, daemon=True).start()


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _subs.add(q)
    _ensure_heartbeat()
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        _subs.discard(q)


def publish(kind: str, data: dict | None = None) -> None:
    msg = json.dumps({"type": kind, "data": data or {}})
    with _lock:
        subs = list(_subs)
    for q in subs:
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass
