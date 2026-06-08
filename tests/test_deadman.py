"""Dead-man's switch — external heartbeat ping, configured in-app."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import deadman
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(deadman, "_url", "")
    monkeypatch.setattr(deadman, "_interval", 60.0)
    yield


def test_configure_and_status():
    s = deadman.configure("https://hc-ping.com/abc", 30)
    assert s["configured"] and s["url"].endswith("/abc")
    assert s["interval"] == 30        # accepted
    # below the floor is clamped
    assert deadman.configure("https://x", 1)["interval"] == deadman.MIN_INTERVAL


def test_ping_uses_http_and_records(monkeypatch):
    calls = {}

    def fake_get(url, timeout=10.0):
        calls["url"] = url
        return 200

    monkeypatch.setattr(deadman, "_http_get", fake_get)
    deadman.configure("https://hc-ping.com/ok")
    assert deadman.ping_once() is True
    assert calls["url"].endswith("/ok")
    assert deadman.status()["last"]["ok"] is True


def test_ping_failure_recorded(monkeypatch):
    def boom(url, timeout=10.0):
        raise OSError("network down")
    monkeypatch.setattr(deadman, "_http_get", boom)
    deadman.configure("https://hc-ping.com/x")
    assert deadman.ping_once() is False
    assert deadman.status()["last"]["ok"] is False
    assert "network down" in deadman.status()["last"]["error"]


def test_ping_noop_when_unconfigured():
    assert deadman.ping_once() is False


def test_endpoints(monkeypatch):
    monkeypatch.setattr(deadman, "_http_get", lambda url, timeout=10.0: 200)
    assert client.get("/api/deadman").json()["configured"] is False
    r = client.post("/api/deadman", json={"url": "https://hc-ping.com/e", "interval": 45})
    assert r.json()["configured"] and r.json()["interval"] == 45
    assert client.post("/api/deadman/test").json()["ok"] is True
