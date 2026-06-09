"""Disciple economy & lifecycle routes served by routers/economy.py after the split."""
from starlette.testclient import TestClient

from maybot_control_center import app


client = TestClient(app.app)


def test_economy_routes_mounted_and_served():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/treasury", "/api/treasury/endow", "/api/agents/{name}/seclusion",
              "/api/agents/{name}/roaming", "/api/agents/{name}/learn-goal",
              "/api/agents/{name}/transmit", "/api/quests", "/api/agents/{name}/quest",
              "/api/pills", "/api/pills/buy"):
        assert p in paths
    for p in ("/api/treasury", "/api/quests", "/api/pills"):
        assert client.get(p).status_code == 200


def test_economy_validation():
    assert client.post("/api/treasury/endow", json={"amount": 0}).status_code == 400
    assert client.post("/api/pills/buy", json={"agent": "bad!", "pill": "x"}).status_code == 400
    assert client.post("/api/agents/bad name!/seclusion", json={"enter": True}).status_code == 400
