"""Learning routes are served by routers/learning.py and gated by deps.

Guards the app.py -> router extraction: routes stay mounted with identical paths
and the shared deps gates behave as before.
"""
import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from maybot_control_center import app, deps, authz


client = TestClient(app.app)


def test_learning_routes_are_mounted_via_router():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/learning/tracks", "/api/learning/ask/stream",
              "/api/learning/lab/real", "/api/learning/analytics",
              "/api/learning/plan", "/api/learning/remind"):
        assert p in paths
    # served live
    r = client.get("/api/learning/tracks")
    assert r.status_code == 200 and "tracks" in r.json()


def test_app_reexports_deps_helpers():
    # app.py keeps the historical private names, now backed by deps.
    assert app._check_token is deps.check_token
    assert app._check_operator is deps.check_operator
    assert app._resolve_device is deps.resolve_device
    assert app._SAFE_NAME is deps.SAFE_NAME


def test_deps_role_gate(monkeypatch):
    monkeypatch.setattr(authz, "role_for", lambda t: None)
    with pytest.raises(HTTPException) as e:
        deps.check_token("bad")
    assert e.value.status_code == 401

    monkeypatch.setattr(authz, "role_for", lambda t: "viewer")
    deps.check_token("ok")                       # any valid role passes
    with pytest.raises(HTTPException) as e2:
        deps.check_operator("viewer-token")      # viewer cannot mutate
    assert e2.value.status_code == 403

    monkeypatch.setattr(authz, "role_for", lambda t: "operator")
    deps.check_operator("op")                    # operator passes


def test_deps_resolve_device_unknown(monkeypatch):
    monkeypatch.setattr(deps, "all_devices", lambda: [{"name": "web-01"}])
    assert deps.resolve_device("web-01")["name"] == "web-01"
    with pytest.raises(HTTPException) as e:
        deps.resolve_device("nope")
    assert e.value.status_code == 404
