"""Agent-ops routes (memory / tools / autonomy / usage / budget) served by
routers/agentops.py after the split."""
from starlette.testclient import TestClient

from maybot_control_center import app


client = TestClient(app.app)


def test_agentops_routes_mounted_and_served():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/memory", "/api/memory/search", "/api/memory/note", "/api/tools",
              "/api/tools/audit", "/api/tools/run", "/api/tools/{call_id}/approve",
              "/api/tools/{call_id}/deny", "/api/autonomy/pause", "/api/autonomy/resume",
              "/api/usage", "/api/usage/series", "/api/budget"):
        assert p in paths
    # served live through the router
    for p in ("/api/memory", "/api/tools", "/api/usage", "/api/budget"):
        r = client.get(p)
        assert r.status_code == 200 and isinstance(r.json(), dict)


def test_tools_run_validates_name():
    assert client.post("/api/tools/run", json={"tool": "bad name!", "args": {}}).status_code == 400
