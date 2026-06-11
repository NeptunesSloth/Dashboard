"""/api/overview serves identically via the sync path and the opt-in async poll."""
import importlib

from starlette.testclient import TestClient


FAKE = {"summary": {"online_devices": 1, "offline_devices": 0, "total_devices": 1},
        "devices": [{"name": "d1", "online": True}],
        "projects": [{"name": "p1", "device": "d1", "type": "generic", "health": "ok"}]}


def _client(monkeypatch, async_on: bool):
    monkeypatch.setenv("MAYBOT_ASYNC_POLL", "1" if async_on else "0")
    # The /api/overview route (and its import-time MAYBOT_ASYNC_POLL flag) lives
    # in the fleet router; reload it, then the app so it mounts the fresh router.
    import maybot_control_center.routers.fleet as fleet_mod
    import maybot_control_center.app as app_mod
    importlib.reload(fleet_mod)
    importlib.reload(app_mod)
    # Stub both poll paths so the route choice is what's under test (no real agents).
    monkeypatch.setattr(fleet_mod, "all_devices", lambda: [{"name": "d1", "url": "http://x"}])
    monkeypatch.setattr(fleet_mod, "aggregate", lambda devices: {**FAKE, "via": "sync"})

    async def fake_async(devices):
        return {**FAKE, "via": "async"}

    monkeypatch.setattr(fleet_mod.aggregator, "aggregate_async", fake_async)
    return TestClient(app_mod.app), fleet_mod


def test_overview_sync_by_default(monkeypatch):
    client, _ = _client(monkeypatch, async_on=False)
    body = client.get("/api/overview").json()
    assert body["via"] == "sync" and body["summary"]["online_devices"] == 1


def test_overview_uses_async_when_enabled(monkeypatch):
    client, _ = _client(monkeypatch, async_on=True)
    body = client.get("/api/overview").json()
    assert body["via"] == "async"


def test_async_falls_back_to_sync_when_tunneled(monkeypatch):
    client, fleet_mod = _client(monkeypatch, async_on=True)
    # A device on the reverse tunnel forces the sync (direct-HTTP-safe) path.
    monkeypatch.setattr(fleet_mod, "_any_tunneled", lambda devices: True)
    assert client.get("/api/overview").json()["via"] == "sync"
    # restore default env for the rest of the suite
    _client(monkeypatch, async_on=False)
