"""Reverse tunnel: registry, request/response correlation, the sync bridge,
agent_client routing, and the WebSocket auth handshake."""
import asyncio
import json
import threading
import time

from fastapi.testclient import TestClient

from maybot_control_center import tunnel, agent_client, registry
from maybot_control_center.app import app


def test_call_without_connection_is_offline():
    assert tunnel.call("ghost", "/api/ping")["online"] is False


def test_connection_request_resolve_roundtrip():
    async def scenario():
        loop = asyncio.get_running_loop()
        sent = []

        class FakeWS:
            async def send_text(self, s):
                sent.append(json.loads(s))

        conn = tunnel.Connection("h", FakeWS(), loop)
        task = asyncio.create_task(conn.request("GET", "/api/ping"))
        await asyncio.sleep(0)                       # let request() send its frame
        rid = sent[0]["id"]
        conn.resolve(rid, {"status": 200, "data": {"pong": True}})
        res = await task
        assert res == {"status": 200, "data": {"pong": True}}

    asyncio.run(scenario())


def test_sync_bridge_roundtrip():
    """tunnel.call() (sync, called from poller threads) hops onto the conn loop."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    conn = None

    class AutoWS:
        async def send_text(self, s):
            msg = json.loads(s)
            loop.call_soon_threadsafe(conn.resolve, msg["id"], {"status": 200, "data": {"pong": True}})

    conn = tunnel.Connection("h", AutoWS(), loop)
    tunnel.register("h", conn)
    try:
        r = tunnel.call("h", "/api/ping")
        assert r["online"] and r["status_code"] == 200 and r["data"]["pong"] is True
    finally:
        tunnel.unregister("h", conn)
        loop.call_soon_threadsafe(loop.stop)


def test_agent_client_routes_via_tunnel(monkeypatch):
    monkeypatch.setattr(tunnel, "connected", lambda name: name == "h")
    seen = {}

    def fake_call(name, path, method="GET", body=None, timeout=8.0):
        seen["args"] = (name, path, method)
        return {"online": True, "status_code": 200, "data": {"ok": True}}

    monkeypatch.setattr(tunnel, "call", fake_call)
    r = agent_client.call_agent({"name": "h", "url": "http://x"}, "/api/ping")
    assert r["online"] and seen["args"] == ("h", "/api/ping", "GET")

    # A host with no tunnel still falls back to direct HTTP (here: unreachable).
    r2 = agent_client.call_agent({"name": "n", "url": "http://127.0.0.1:59997"}, "/api/ping")
    assert r2["online"] is False


def test_ws_handshake_auth(monkeypatch):
    monkeypatch.setattr(registry, "REGISTER_TOKEN", "secret")
    client = TestClient(app)

    with client.websocket_connect("/ws/agent") as ws:        # wrong token → rejected
        ws.send_text(json.dumps({"t": "hello", "name": "h", "token": "nope"}))
        assert json.loads(ws.receive_text())["ok"] is False

    with client.websocket_connect("/ws/agent") as ws:        # enroll token → accepted
        ws.send_text(json.dumps({"t": "hello", "name": "h", "token": "secret"}))
        assert json.loads(ws.receive_text())["ok"] is True
        assert tunnel.connected("h")

    # The connection is dropped from the registry once the socket closes.
    for _ in range(50):
        if not tunnel.connected("h"):
            break
        time.sleep(0.02)
    assert not tunnel.connected("h")
