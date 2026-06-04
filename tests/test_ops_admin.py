"""Operator audit log + setup/diagnostics (Ops tab)."""
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import audit, diagnostics, authz

client = TestClient(app)


def setup_function():
    audit.clear()


# ---- audit log ----
def test_name_for_no_auth(monkeypatch):
    monkeypatch.setattr(authz, "load_users", lambda: [])
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "")
    assert authz.name_for("") == "operator"


def test_name_for_users(monkeypatch):
    monkeypatch.setattr(authz, "load_users", lambda: [{"name": "alice", "token": "t1", "role": "operator"}])
    assert authz.name_for("t1") == "alice"
    assert authz.name_for("wrong") == "unknown"


def test_record_and_recent():
    audit.record("alice", "POST /api/x", status=200)
    audit.record("bob", "POST /api/y", status=403)
    r = audit.recent()
    assert r[0]["actor"] == "bob" and r[1]["actor"] == "alice"   # newest first


def test_mutation_is_audited_via_middleware():
    audit.clear()
    client.post("/api/maintenance/silence", json={"target": "d:bot", "minutes": 5})
    entries = client.get("/api/audit").json()["entries"]
    assert any(e["action"].startswith("POST") and "/api/maintenance/silence" in e["action"] for e in entries)


def test_get_requests_not_audited():
    audit.clear()
    client.get("/api/overview")
    assert client.get("/api/audit").json()["count"] == 0


# ---- diagnostics ----
def test_config_checks_shape():
    c = diagnostics.config_checks()
    assert set(c) >= {"auth_configured", "persistence_db", "autopilot", "webhooks"}
    assert set(c["webhooks"]) == {"discord", "slack", "generic"}


def test_diagnostics_endpoint(monkeypatch):
    monkeypatch.setattr(diagnostics, "agent_health",
                        lambda: [{"name": "prod-1", "online": True, "latency_ms": 12}])
    body = client.get("/api/diagnostics").json()
    assert "config" in body and body["agents"][0]["name"] == "prod-1"
