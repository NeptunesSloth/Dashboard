import pytest
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import agents

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_agents(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "AGENTS_FILE", tmp_path / "agents.yaml")
    yield


def test_member_crud():
    assert client.get("/api/members").json()["members"] == []
    r = client.post("/api/members", json={"name": "Nova", "role": "Analyst", "provider": "ollama",
                                          "model": "llama3", "base_url": "http://127.0.0.1:11434", "persona": "concise"})
    assert r.status_code == 200
    m = client.get("/api/members").json()["members"]
    assert m[0]["name"] == "Nova" and m[0]["model"] == "llama3"
    assert agents.file_agents()[0]["persona"] == "concise"        # persisted to agents.yaml

    # validation: model required; claude needs no base_url
    assert client.post("/api/members", json={"name": "Bad", "provider": "ollama", "model": ""}).status_code == 400
    assert client.post("/api/members", json={"name": "Atlas", "provider": "claude", "model": "claude-opus-4-8"}).status_code == 200

    # rename keeps it unique; duplicate rejected
    assert client.post("/api/members", json={"name": "Nova", "model": "llama3", "provider": "ollama",
                                             "base_url": "http://x:1", "original_name": "Atlas"}).status_code == 409
    assert client.request("DELETE", "/api/members/Nova").status_code == 200
    assert {a["name"] for a in client.get("/api/members").json()["members"]} == {"Atlas"}
    assert client.request("DELETE", "/api/members/ghost").status_code == 404
