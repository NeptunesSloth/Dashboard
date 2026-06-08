"""Agent API contract — the routes the dashboard/control center polls.

The control center talks to each host's ``maybot_agent`` over this contract:
liveness/identity are unauthenticated health checks, while project data (which
can include bot config and PnL) stays behind the API token.
"""
import pytest
from fastapi.testclient import TestClient

from maybot_agent import app as agent_app
from maybot_agent import auth

TOKEN = "test-agent-token-abc123"


@pytest.fixture()
def agent_client(monkeypatch):
    # Configure a known API token and an empty project set (fresh host).
    monkeypatch.setattr(auth, "API_TOKEN", TOKEN)
    monkeypatch.setattr(agent_app, "load_projects", lambda: [])
    return TestClient(agent_app.app)


def test_healthz_ok_without_token(agent_client):
    r = agent_client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_ping_ok_without_token(agent_client):
    r = agent_client.get("/api/ping")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_device_ok_without_token(agent_client):
    r = agent_client.get("/api/device")
    assert r.status_code == 200
    body = r.json()
    assert body.get("version")                       # valid JSON identity
    assert "hostname" in body and "platform" in body
    # Identity only — never leak the API token.
    assert TOKEN not in r.text


def test_projects_empty_list_is_200_not_404(agent_client):
    # A host with no projects configured returns an empty list, not a 404.
    r = agent_client.get("/api/projects", headers={"x-api-token": TOKEN})
    assert r.status_code == 200
    assert r.json() == []


def test_projects_requires_token(agent_client):
    assert agent_client.get("/api/projects").status_code == 401


def test_projects_rejects_wrong_token(agent_client):
    r = agent_client.get("/api/projects", headers={"x-api-token": "wrong"})
    assert r.status_code == 401
