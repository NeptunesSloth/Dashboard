"""The /assets/* route must serve Sect Map art (and reject path traversal)."""
from fastapi.testclient import TestClient

from maybot_control_center.app import app

client = TestClient(app)


def test_core_static_served():
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200


def test_map_assets_served():
    # the Sect Map breaks if these 404 (the bug this route fixes)
    for path in ("/assets/map/map_bg.png", "/assets/map/hall_bg.png",
                 "/assets/map/leader_bg.png", "/assets/map/sprites/agent_0.png"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert r.headers["content-type"].startswith("image/")


def test_missing_asset_404():
    assert client.get("/assets/map/does-not-exist.png").status_code == 404


def test_path_traversal_rejected():
    # must not escape the assets directory
    for evil in ("/assets/../app.py", "/assets/..%2f..%2fapp.py", "/assets/../../pyproject.toml"):
        assert client.get(evil).status_code == 404, evil
