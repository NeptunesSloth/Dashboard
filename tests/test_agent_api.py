"""Agent API contract — the routes the dashboard/control center polls.

The control center talks to each host's ``maybot_agent`` over this contract:
liveness/identity are unauthenticated health checks, while project data (which
can include bot config and PnL) stays behind the API token.
"""
import pytest
from fastapi.testclient import TestClient

from maybot_agent import app as agent_app
from maybot_agent import auth, config

TOKEN = "test-agent-token-abc123"
AUTH = {"x-api-token": TOKEN}


@pytest.fixture()
def agent_client(monkeypatch):
    # Configure a known API token and an empty project set (fresh host).
    monkeypatch.setattr(auth, "API_TOKEN", TOKEN)
    monkeypatch.setattr(agent_app, "load_projects", lambda: [])
    return TestClient(agent_app.app)


@pytest.fixture()
def cfg_client(monkeypatch, tmp_path):
    """Agent client backed by a throwaway projects file (for config read/write)."""
    monkeypatch.setattr(auth, "API_TOKEN", TOKEN)
    pfile = tmp_path / "projects.yaml"
    monkeypatch.setattr(config, "PROJECTS_FILE", pfile)
    return TestClient(agent_app.app), pfile


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


# --- Dashboard-managed bot config -----------------------------------------

def test_projects_config_roundtrip(cfg_client):
    client, pfile = cfg_client
    # A fresh host (no file yet) reads back an empty list, not a 404.
    assert client.get("/api/projects/config", headers=AUTH).json() == {"projects": []}

    bots = [{"name": "daybot", "type": "generic", "expect_running": True}]
    r = client.put("/api/projects/config", headers=AUTH, json={"projects": bots})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert pfile.exists()                                   # persisted to disk

    # Readable back, and the adapted /api/projects now lists it.
    assert client.get("/api/projects/config", headers=AUTH).json()["projects"][0]["name"] == "daybot"
    assert any(p["name"] == "daybot" for p in client.get("/api/projects", headers=AUTH).json())


def test_projects_config_rejects_invalid(cfg_client):
    client, _ = cfg_client
    # Missing name.
    assert client.put("/api/projects/config", headers=AUTH, json={"projects": [{"type": "x"}]}).status_code == 400
    # Duplicate names.
    dupe = {"projects": [{"name": "a"}, {"name": "a"}]}
    assert client.put("/api/projects/config", headers=AUTH, json=dupe).status_code == 400


def test_projects_config_requires_token(cfg_client):
    client, _ = cfg_client
    assert client.get("/api/projects/config").status_code == 401
    assert client.put("/api/projects/config", json={"projects": []}).status_code == 401


def test_discover_shape_and_auth(agent_client):
    r = agent_client.get("/api/discover", headers=AUTH)
    assert r.status_code == 200
    assert isinstance(r.json().get("candidates"), list)
    assert agent_client.get("/api/discover").status_code == 401     # token required
