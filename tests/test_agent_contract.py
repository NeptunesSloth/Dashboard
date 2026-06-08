"""Contract test: pin the agent HTTP API the dashboard depends on.

The dashboard (agent_client / aggregator / host & bot management / fleet update)
calls these exact routes with these exact shapes. If the agent ever drifts from
this contract, the dashboard silently shows hosts as offline / 0 bots — exactly
the failure we hit in the field. This test fails loudly instead.
"""
import pytest
from fastapi.testclient import TestClient

from maybot_agent import app as agent_app
from maybot_agent import auth, config

TOKEN = "contract-token"
AUTH = {"x-api-token": TOKEN}


@pytest.fixture()
def agent(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "API_TOKEN", TOKEN)
    monkeypatch.setattr(config, "PROJECTS_FILE", tmp_path / "projects.yaml")
    return TestClient(agent_app.app)


def test_liveness_and_identity_are_tokenless_with_version(agent):
    for path in ("/healthz", "/api/ping"):
        r = agent.get(path)
        assert r.status_code == 200
        assert r.json().get("version")               # fleet drift detection relies on this
    dev = agent.get("/api/device")
    assert dev.status_code == 200
    assert {"hostname", "platform", "version"} <= set(dev.json())


def test_projects_contract(agent):
    # token required; returns a JSON list; empty host -> [] not 404
    assert agent.get("/api/projects").status_code == 401
    r = agent.get("/api/projects", headers=AUTH)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_bot_management_contract(agent):
    # the dashboard reads + writes the editable config here
    assert agent.get("/api/projects/config", headers=AUTH).json() == {"projects": []}
    put = agent.put("/api/projects/config", headers=AUTH,
                    json={"projects": [{"name": "b", "type": "generic"}]})
    assert put.status_code == 200 and put.json()["count"] == 1
    assert agent.get("/api/discover", headers=AUTH).status_code == 200


def test_required_routes_exist():
    paths = {r.path for r in agent_app.app.routes}
    required = {
        "/healthz", "/api/ping", "/api/device", "/api/projects",
        "/api/projects/config", "/api/discover", "/api/self-update",
        "/api/projects/{name}/start", "/api/projects/{name}/stop",
        "/api/projects/{name}/run-tests", "/api/projects/{name}/logs",
    }
    missing = required - paths
    assert not missing, f"agent is missing routes the dashboard calls: {missing}"
