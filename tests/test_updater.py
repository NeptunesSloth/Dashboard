"""Agent self-update + the dashboard's push-update endpoints."""
import io
import tarfile

from fastapi.testclient import TestClient

from maybot_agent import updater
from maybot_control_center.app import app

client = TestClient(app)


def _bundle(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_apply_update_extracts_into_target(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_target_dir", lambda: tmp_path)
    blob = _bundle({"maybot_agent/marker.txt": b"v2"})
    res = updater.apply_update(control_url="http://dash:8200", download=lambda url: blob)
    assert res["ok"] is True
    assert (tmp_path / "maybot_agent" / "marker.txt").read_text() == "v2"


def test_apply_update_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_target_dir", lambda: tmp_path)
    evil = _bundle({"../escape.txt": b"x"})
    res = updater.apply_update(control_url="http://dash:8200", download=lambda url: evil)
    assert res["ok"] is False and "unsafe" in res["error"]


def test_apply_update_needs_control_url(monkeypatch):
    monkeypatch.delenv("MAYBOT_CONTROL_CENTER_URL", raising=False)
    assert updater.apply_update(control_url="")["ok"] is False


def test_update_and_restart_schedules_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_target_dir", lambda: tmp_path)
    started = {}
    monkeypatch.setattr(updater.threading, "Thread",
                        lambda *a, **k: type("T", (), {"start": lambda s: started.setdefault("yes", True), "daemon": True})())
    res = updater.update_and_restart(control_url="http://dash:8200", download=lambda url: _bundle({"x": b"y"}))
    assert res["ok"] and res["restarting"] and started.get("yes")


def test_host_update_endpoint_unknown_host():
    assert client.post("/api/hosts/nope-xyz/update").status_code == 404


def test_fleet_update_runs():
    r = client.post("/api/fleet/update")
    assert r.status_code == 200 and "latest" in r.json()
