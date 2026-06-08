"""Safe mode / panic button — one switch halts all automation."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import safemode, autopilot, escalation
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset():
    safemode.clear()
    yield
    safemode.clear()


def test_toggle_and_status():
    assert safemode.engaged() is False
    safemode.set_engaged(True)
    assert safemode.engaged() is True and safemode.status()["engaged"] is True
    safemode.set_engaged(False)
    assert safemode.engaged() is False


def test_halts_autopilot(monkeypatch):
    monkeypatch.setattr(autopilot, "ENABLED", True)
    monkeypatch.setattr(autopilot, "_paused", False, raising=False)
    safemode.set_engaged(True)
    assert autopilot.tick() == []          # frozen despite being enabled
    assert autopilot.handle([]) == []


def test_halts_escalation(monkeypatch):
    monkeypatch.setattr(escalation, "ENABLED", True)
    safemode.set_engaged(True)
    assert escalation.sweep() == []


def test_endpoints():
    assert client.get("/api/safemode").json()["engaged"] is False
    assert client.post("/api/safemode", json={"engaged": True}).json()["engaged"] is True
    assert client.get("/api/safemode").json()["engaged"] is True
    client.post("/api/safemode", json={"engaged": False})
