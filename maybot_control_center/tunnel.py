"""Reverse tunnel: agents dial OUT to the dashboard over a WebSocket, so a host
behind NAT or a firewall needs **no inbound ports** — the dashboard sends its
normal agent requests (ping/projects/device/actions) *down* the tunnel. Direct
HTTP stays as the fallback for hosts configured the old way.

Thread/loop bridge: WebSocket connections live on the app's asyncio loop, but
the fleet poller calls from worker threads. ``Connection.request`` is async;
the sync ``call()`` helper hops onto the connection's loop via
``run_coroutine_threadsafe`` and blocks for the correlated response.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

_conns: dict[str, "Connection"] = {}
_lock = threading.Lock()


class Connection:
    """One live agent WebSocket, with request/response correlation by id."""

    def __init__(self, name: str, ws, loop: asyncio.AbstractEventLoop):
        self.name = name
        self.ws = ws
        self.loop = loop
        self._pending: dict[str, asyncio.Future] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return str(self._counter)

    async def request(self, method: str, path: str, body: Any = None, timeout: float = 8.0) -> dict:
        rid = self._next_id()
        fut: asyncio.Future = self.loop.create_future()
        self._pending[rid] = fut
        await self.ws.send_text(json.dumps({"t": "req", "id": rid, "method": method, "path": path, "body": body}))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(rid, None)

    def resolve(self, rid: str, payload: dict) -> None:
        fut = self._pending.get(rid)
        if fut and not fut.done():
            fut.set_result(payload)

    def fail_all(self, exc: Exception) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()


def register(name: str, conn: "Connection") -> None:
    with _lock:
        old = _conns.get(name)
        _conns[name] = conn
    if old is not None and old is not conn:
        try:
            old.fail_all(ConnectionError("replaced by a new tunnel"))
        except Exception:
            pass


def unregister(name: str, conn: "Connection") -> None:
    with _lock:
        if _conns.get(name) is conn:
            _conns.pop(name, None)


def connected(name: str | None) -> bool:
    if not name:
        return False
    with _lock:
        return name in _conns


def get(name: str) -> "Connection | None":
    with _lock:
        return _conns.get(name)


def names() -> list[str]:
    with _lock:
        return list(_conns)


def call(name: str, path: str, method: str = "GET", body: Any = None, timeout: float = 8.0) -> dict:
    """Sync entry point for the threaded poller — returns a call_agent-shaped dict."""
    conn = get(name)
    if conn is None:
        return {"online": False, "error": "no tunnel", "data": {}}
    try:
        fut = asyncio.run_coroutine_threadsafe(conn.request(method, path, body, timeout), conn.loop)
        resp = fut.result(timeout + 2)
    except Exception as exc:  # noqa: BLE001
        return {"online": False, "error": f"tunnel: {exc}", "data": {}}
    status = int(resp.get("status", 0) or 0)
    is_2xx = 200 <= status < 300
    return {
        "online": is_2xx,
        "auth_error": status in (401, 403),
        "status_code": status,
        "error": None if is_2xx else (resp.get("error") or f"http status {status}"),
        "data": resp.get("data", {}),
    }
