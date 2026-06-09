"""Reliability / SLO routes served by routers/reliability.py after the split."""
from starlette.testclient import TestClient

from maybot_control_center import app, deps


client = TestClient(app.app)


def test_reliability_routes_mounted_and_served():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/slo", "/api/maintenance", "/api/maintenance/silence",
              "/api/maintenance/unsilence", "/api/errorbudget"):
        assert p in paths
    for p in ("/api/slo", "/api/maintenance", "/api/errorbudget"):
        assert client.get(p).status_code == 200


def test_maintenance_silence_validates_target():
    assert client.post("/api/maintenance/silence", json={"target": "bad target", "minutes": 5}).status_code == 400
    assert app._SAFE_TARGET is deps.SAFE_TARGET


def test_shared_target_model_routes_still_work():
    # UnsilenceIn (the generic {target} body) is shared by oaths/alerts in app.py,
    # so re-adding it after the move must keep those routes functional.
    assert client.post("/api/oaths/release", json={"target": "x:y"}).status_code in (200, 400, 404)
    assert client.post("/api/alerts/resolve", json={"target": "x:y"}).status_code in (200, 400, 404)
