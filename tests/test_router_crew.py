"""Disciple crew + missions routes served by routers/crew.py after the split."""
from starlette.testclient import TestClient

from maybot_control_center import app


client = TestClient(app.app)


def test_crew_routes_mounted_and_served():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/agents", "/api/agents/{name}", "/api/agents/{name}/delegate",
              "/api/agents/{name}/task", "/api/comms", "/api/comms/mission"):
        assert p in paths
    assert "agents" in client.get("/api/agents").json()
    assert "feed" in client.get("/api/comms").json()


def test_crew_validation():
    assert client.post("/api/agents/x/delegate", json={"to": "bad!", "task": "t"}).status_code == 400
    assert client.post("/api/comms/mission", json={"goal": "", "participants": []}).status_code == 400
    assert client.get("/api/agents/bad name!").status_code == 400
