"""Dial OUT to the control center so this host needs no inbound ports.

Opens a WebSocket to ``{control}/ws/agent``, authenticates with the API token,
then serves the dashboard's requests by dispatching them to our own ASGI app
in-process (so existing routes + auth are reused). Reconnects with backoff.

Enabled when ``MAYBOT_CONTROL_CENTER_URL`` is set and ``MAYBOT_TUNNEL`` != "0".
If ``websockets``/``httpx`` aren't installed, it stays dormant — the dashboard
simply falls back to reaching the agent over direct HTTP.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time

CONTROL_URL = os.getenv("MAYBOT_CONTROL_CENTER_URL", "").rstrip("/")
ENABLED = bool(CONTROL_URL) and os.getenv("MAYBOT_TUNNEL", "1") != "0"


def _ws_url() -> str:
    base = CONTROL_URL
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base + "/ws/agent"


def _agent_name() -> str:
    return os.getenv("MAYBOT_AGENT_NAME", "") or socket.gethostname() or "agent"


async def _serve() -> None:
    import httpx
    import websockets

    from .app import app
    from .config import API_TOKEN

    token = API_TOKEN or os.getenv("MAYBOT_REGISTER_TOKEN", "")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://agent") as client:
        async with websockets.connect(_ws_url(), max_size=8 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"t": "hello", "name": _agent_name(), "token": token}))
            ack = json.loads(await ws.recv())
            if not ack.get("ok"):
                return
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("t") != "req":
                    continue
                rid, method, path = msg.get("id"), msg.get("method", "GET"), msg.get("path", "/")
                try:
                    r = await client.request(method, path, headers={"x-api-token": API_TOKEN},
                                             json=msg.get("body"))
                    ctype = r.headers.get("content-type", "")
                    data = r.json() if ctype.startswith("application/json") else {}
                    await ws.send(json.dumps({"t": "res", "id": rid, "status": r.status_code, "data": data}))
                except Exception as exc:  # noqa: BLE001
                    await ws.send(json.dumps({"t": "res", "id": rid, "status": 0, "error": str(exc)}))


def _loop() -> None:
    backoff = 2
    while True:
        try:
            asyncio.run(_serve())
            backoff = 2                       # clean disconnect → reconnect promptly
        except Exception:
            pass                              # missing deps / network → retry with backoff
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def start() -> None:
    if not ENABLED:
        return
    threading.Thread(target=_loop, daemon=True).start()
