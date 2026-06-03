"""Lightweight in-process pub/sub for Server-Sent Events.

Background threads call ``publish(kind)`` when agent state, comms, or tool calls
change; the ``/api/stream`` endpoint drains a per-subscriber queue and yields SSE
frames, so the dashboard updates instantly instead of waiting for the poll.
"""
from __future__ import annotations

import json
import queue
import threading

_subs: set[queue.Queue] = set()
_lock = threading.Lock()


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _subs.add(q)
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
