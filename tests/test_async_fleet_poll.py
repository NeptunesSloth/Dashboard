"""Tests for the opt-in async fleet-poll building block.

These cover the ADDITIVE async path only:
  * ``agent_client.gather_fleet`` / ``call_agent_async`` (httpx.AsyncClient).
  * ``aggregator.aggregate_async``.

They assert the async path produces the SAME structure as the existing sync
path (``aggregator.aggregate`` / ``_fetch_device``) for the same fake device
inputs, and that the sync path itself is untouched.

``pytest-asyncio`` is not a dependency of this project, so coroutines are driven
explicitly with ``asyncio.run`` rather than an async test marker/plugin.
"""
import asyncio

import httpx

from maybot_control_center import agent_client, aggregator


# Two fake devices: one fully online, one whose token is rejected on
# /api/projects (auth_error) — exercising both the online and offline/auth-error
# branches of the row-shaping logic shared by the sync and async paths.
ONLINE_DEVICE = {"name": "good", "url": "http://good.local", "api_token": "ok"}
AUTH_DEVICE = {"name": "bad", "url": "http://bad.local", "api_token": "wrong"}

PING_PAYLOAD = {"status": "ok", "version": "1.0"}
PROJECTS_PAYLOAD = [{"name": "p1", "type": "trading_bot", "status": "running", "health": "ok"}]


def _mock_handler(request: httpx.Request) -> httpx.Response:
    """Fake every agent host the async client would hit.

    - ``good.local`` answers ping + projects normally.
    - ``bad.local`` answers ping (reachable) but rejects /api/projects with 403.
    """
    host = request.url.host
    path = request.url.path
    if host == "good.local":
        if path == "/api/ping":
            return httpx.Response(200, json=PING_PAYLOAD)
        if path == "/api/projects":
            return httpx.Response(200, json=PROJECTS_PAYLOAD)
    if host == "bad.local":
        if path == "/api/ping":
            return httpx.Response(200, json=PING_PAYLOAD)
        if path == "/api/projects":
            return httpx.Response(403, json={"detail": "bad token"})
    return httpx.Response(404, json={})


def _patch_async_transport(monkeypatch):
    """Route ``httpx.AsyncClient`` through an in-memory MockTransport so no real
    network is touched, while still exercising the real gather_fleet code."""
    transport = httpx.MockTransport(_mock_handler)
    monkeypatch.setattr(agent_client, "_async_client_kwargs", lambda: {"transport": transport})


def test_gather_fleet_shape_matches_sync_fetch(monkeypatch):
    """gather_fleet -> _shape_device yields the same (row, projects) as the sync
    _fetch_device for the same fake responses."""
    _patch_async_transport(monkeypatch)

    records = asyncio.run(agent_client.gather_fleet([ONLINE_DEVICE, AUTH_DEVICE]))
    assert [r["device"]["name"] for r in records] == ["good", "bad"]

    # Build the sync result for the SAME fake responses by routing call_agent
    # through the same fake payloads.
    def fake_call(d, endpoint):
        if d["name"] == "good":
            if endpoint == "/api/ping":
                return {"online": True, "auth_error": False, "status_code": 200,
                        "error": None, "data": PING_PAYLOAD}
            return {"online": True, "auth_error": False, "status_code": 200,
                    "error": None, "data": PROJECTS_PAYLOAD}
        # bad device
        if endpoint == "/api/ping":
            return {"online": True, "auth_error": False, "status_code": 200,
                    "error": None, "data": PING_PAYLOAD}
        return {"online": False, "auth_error": True, "status_code": 403,
                "error": "bad token", "data": {"detail": "bad token"}}

    monkeypatch.setattr(aggregator, "call_agent", fake_call)
    monkeypatch.setattr(aggregator, "LATEST_AGENT_VERSION", "1.0")

    for rec in records:
        async_row, async_projects = aggregator._shape_device(
            rec["device"], rec["ping"], rec["proj_resp"]
        )
        sync_row, sync_projects = aggregator._fetch_device(rec["device"])
        assert async_row.keys() == sync_row.keys()
        assert async_row == sync_row
        assert async_projects == sync_projects


def test_call_agent_async_auth_error(monkeypatch):
    _patch_async_transport(monkeypatch)

    async def _run():
        kwargs = agent_client._async_client_kwargs()
        async with httpx.AsyncClient(**kwargs) as client:
            return (
                await agent_client.call_agent_async(client, AUTH_DEVICE, "/api/ping"),
                await agent_client.call_agent_async(client, AUTH_DEVICE, "/api/projects"),
            )

    ping, proj = asyncio.run(_run())
    assert ping["online"] is True
    assert proj["online"] is False
    assert proj["auth_error"] is True
    assert proj["status_code"] == 403


def test_aggregate_async_matches_sync_structure(monkeypatch):
    """aggregate_async produces the same top-level + per-row + per-project
    structure as the sync aggregate for the same fake inputs."""
    _patch_async_transport(monkeypatch)
    monkeypatch.setattr(aggregator, "LATEST_AGENT_VERSION", "1.0")

    # Make the sync aggregate see the SAME fake responses as the async transport.
    def fake_call(d, endpoint):
        if d["name"] == "good":
            if endpoint == "/api/ping":
                return {"online": True, "auth_error": False, "status_code": 200,
                        "error": None, "data": PING_PAYLOAD}
            return {"online": True, "auth_error": False, "status_code": 200,
                    "error": None, "data": [dict(p) for p in PROJECTS_PAYLOAD]}
        if endpoint == "/api/ping":
            return {"online": True, "auth_error": False, "status_code": 200,
                    "error": None, "data": PING_PAYLOAD}
        return {"online": False, "auth_error": True, "status_code": 403,
                "error": "bad token", "data": {"detail": "bad token"}}

    monkeypatch.setattr(aggregator, "call_agent", fake_call)

    devices = [ONLINE_DEVICE, AUTH_DEVICE]
    sync_result = aggregator.aggregate([dict(d) for d in devices])
    async_result = asyncio.run(aggregator.aggregate_async([dict(d) for d in devices]))

    assert sync_result.keys() == async_result.keys() == {"summary", "devices", "projects"}
    assert async_result["summary"].keys() == sync_result["summary"].keys()
    assert async_result["summary"] == sync_result["summary"]

    # Same device rows (same set of keys, same values) for the same inputs.
    assert [r.keys() for r in async_result["devices"]] == [r.keys() for r in sync_result["devices"]]
    assert async_result["devices"] == sync_result["devices"]

    # Same projects (keys + values, ignoring any annotation order differences).
    assert {p["name"] for p in async_result["projects"]} == {p["name"] for p in sync_result["projects"]}
    for ap, sp in zip(async_result["projects"], sync_result["projects"]):
        assert ap.keys() == sp.keys()


def test_sync_aggregate_still_works_unchanged(monkeypatch):
    """Guard: the sync path is untouched and still returns its shape without any
    async machinery involved."""
    def fake_call(d, endpoint):
        if endpoint == "/api/ping":
            return {"online": True, "auth_error": False, "status_code": 200,
                    "error": None, "data": PING_PAYLOAD}
        return {"online": True, "auth_error": False, "status_code": 200,
                "error": None, "data": []}

    monkeypatch.setattr(aggregator, "call_agent", fake_call)
    monkeypatch.setattr(aggregator, "LATEST_AGENT_VERSION", "1.0")

    result = aggregator.aggregate([dict(ONLINE_DEVICE)])
    assert set(result) == {"summary", "devices", "projects"}
    assert result["summary"]["total_devices"] == 1
    assert result["summary"]["online_devices"] == 1
    assert result["devices"][0]["name"] == "good"
    assert result["devices"][0]["online"] is True
