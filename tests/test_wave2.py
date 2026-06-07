import pytest
from fastapi.testclient import TestClient
from maybot_control_center.app import app
from maybot_control_center import agents, diagnosis

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_agents(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "AGENTS_FILE", tmp_path / "agents.yaml")
    yield


def test_seed_starter_sect():
    r = client.post("/api/members/seed")
    assert r.status_code == 200 and r.json()["count"] == 4
    names = {a["name"] for a in client.get("/api/members").json()["members"]}
    assert {"Nova", "Forge", "Sage", "Atlas"} <= names
    assert client.post("/api/members/seed").status_code == 409   # not twice


def test_auto_diagnose_sweep_notifies(monkeypatch):
    sent = []
    monkeypatch.setattr("maybot_control_center.notify.send", lambda t, b="", **k: sent.append((t, b)))
    monkeypatch.setattr(diagnosis, "diagnose", lambda d, p: {"summary": "dependency unreachable", "suggestion": "start it"})
    diagnosis._notified.clear()
    diagnosis.sweep([{"device": "box", "name": "daybot", "health": "error"}])
    assert sent and "daybot" in sent[0][0]
    sent.clear()
    diagnosis.sweep([{"device": "box", "name": "daybot", "health": "error"}])   # debounced
    assert not sent
    diagnosis.sweep([{"device": "box", "name": "daybot", "health": "ok"}])      # recovers -> re-arm
    diagnosis.sweep([{"device": "box", "name": "daybot", "health": "error"}])
    assert sent
