"""Disaster recovery — full-config export/import bundle, all in-app."""
import pytest
from fastapi.testclient import TestClient

from maybot_control_center import dr, config, authz, registry
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEVICES_FILE", tmp_path / "devices.yaml")
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "users.yaml")
    monkeypatch.setattr(registry, "REGISTER_TOKEN", "")
    yield


def test_export_bundle_shape():
    config.save_devices([{"name": "h1", "url": "http://10.0.0.2:8100", "api_token": "tok"}])
    b = dr.export_all()
    assert b["version"] == dr.BUNDLE_VERSION
    assert b["hosts"][0]["name"] == "h1"
    assert "accounts" in b and "enroll_token" in b and "store" in b


def test_restore_roundtrip():
    config.save_devices([{"name": "h1", "url": "http://10.0.0.2:8100", "api_token": "tok"}])
    registry.set_register_token("enroll-secret")
    bundle = dr.export_all()

    # Wipe, then restore from the bundle.
    config.save_devices([])
    registry.set_register_token("")
    assert config.load_devices() == []

    res = dr.restore_all(bundle)
    assert config.load_devices()[0]["name"] == "h1"
    assert registry.REGISTER_TOKEN == "enroll-secret"
    assert any("host" in s for s in res["restored"])


def test_restore_rejects_garbage():
    with pytest.raises(ValueError):
        dr.restore_all({"nope": 1})


def test_export_import_endpoints():
    config.save_devices([{"name": "ep", "url": "http://1.2.3.4:8100"}])
    r = client.get("/api/admin/export")
    assert r.status_code == 200
    bundle = r.json()
    assert bundle["hosts"][0]["name"] == "ep"
    assert "attachment" in r.headers.get("content-disposition", "")

    config.save_devices([])
    imp = client.post("/api/admin/import", json=bundle)
    assert imp.status_code == 200
    assert config.load_devices()[0]["name"] == "ep"

    assert client.post("/api/admin/import", json={"bad": 1}).status_code == 400
