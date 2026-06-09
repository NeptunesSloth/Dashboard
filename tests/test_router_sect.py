"""Sect / cultivation RPG routes served by routers/sect.py after the split."""
import pytest
from starlette.testclient import TestClient

from maybot_control_center import app


client = TestClient(app.app)

GET_ROUTES = [
    "/api/cultivation", "/api/reputation", "/api/prophecy", "/api/formations",
    "/api/governance", "/api/tournament", "/api/governance/inbox", "/api/nightwatch",
    "/api/spirit-root", "/api/chaos", "/api/github", "/api/daoheart", "/api/bonds",
    "/api/lineage", "/api/council/history", "/api/artifacts", "/api/titles", "/api/chronicle",
]


@pytest.mark.parametrize("path", GET_ROUTES)
def test_sect_get_routes_served(path):
    # Each handler references a feature module global; a 200 confirms the route is
    # mounted AND its module import survived the move to routers/sect.py.
    r = client.get(path)
    assert r.status_code == 200 and isinstance(r.json(), dict)


def test_sect_post_validation():
    assert client.post("/api/formations/run", json={"formation": "bad name!", "goal": "x"}).status_code == 400
    assert client.post("/api/bonds/bind", json={"a": "bad!", "b": "y"}).status_code == 400


def test_sect_routes_are_mounted():
    paths = {r.path for r in app.app.routes}
    assert "/api/chronicle/{name}" in paths and "/api/artifacts/forge" in paths
