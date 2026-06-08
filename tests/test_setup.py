"""Quick-Start onboarding/health checklist (/api/setup) + agent version drift."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import setup as setup_mod, aggregator, config, authz
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture()
def fresh(monkeypatch):
    monkeypatch.setattr(config, "load_devices", lambda: [])
    monkeypatch.setattr(aggregator, "last_summary", lambda: {})
    monkeypatch.setattr(authz, "load_users", lambda: [])
    monkeypatch.delenv("MAYBOT_CONTROL_CENTER_TOKEN", raising=False)


def test_fresh_dashboard_not_ready(fresh):
    st = setup_mod.checklist()
    assert st["ready"] is False
    by_id = {s["id"]: s for s in st["steps"]}
    assert by_id["auth"]["done"] is False
    assert by_id["first_host"]["done"] is False
    # The first actionable step offers a one-command install.
    assert by_id["first_host"]["action"]["kind"] == "install"


def test_ready_when_all_green(monkeypatch):
    monkeypatch.setattr(config, "load_devices", lambda: [{"name": "h", "url": "http://x"}])
    monkeypatch.setattr(aggregator, "last_summary",
                        lambda: {"online_devices": 1, "total_projects": 3, "agents_outdated": 0})
    monkeypatch.setattr(authz, "load_users", lambda: [{"name": "op"}])
    st = setup_mod.checklist()
    assert st["ready"] is True
    assert all(s["done"] for s in st["steps"])


def test_outdated_agent_adds_step(monkeypatch):
    monkeypatch.setattr(config, "load_devices", lambda: [{"name": "h"}])
    monkeypatch.setattr(aggregator, "last_summary",
                        lambda: {"online_devices": 1, "total_projects": 2, "agents_outdated": 1})
    monkeypatch.setattr(authz, "load_users", lambda: [{"x": 1}])
    st = setup_mod.checklist()
    assert st["ready"] is False
    assert any(s["id"] == "agents" and not s["done"] for s in st["steps"])


def test_setup_endpoint_merges_checklist():
    r = client.get("/api/setup")
    assert r.status_code == 200
    body = r.json()
    # Existing first-run wizard fields stay intact …
    assert set(body["steps"]) == {"account", "host", "member", "ai", "notifications"}
    # … plus the new action-oriented checklist.
    assert "checklist" in body and "summary" in body and "checklist_ready" in body


def test_poller_captures_version_and_drift(monkeypatch):
    def fake_call(d, endpoint):
        if endpoint == "/api/ping":
            return {"online": True, "data": {"status": "ok", "version": "0.9"}}
        return {"online": True, "data": []}          # /api/projects
    monkeypatch.setattr(aggregator, "call_agent", fake_call)
    monkeypatch.setattr(aggregator, "LATEST_AGENT_VERSION", "1.0")
    row, _ = aggregator._fetch_device({"name": "h", "url": "http://x"})
    assert row["version"] == "0.9"
    assert row["agent_outdated"] is True
