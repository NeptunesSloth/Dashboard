"""Phase-3 Docker lab TARGETS: the catalog getter, the compose file validity, and
the (token-gated) catalog route. All read-only — nothing here executes anything.
"""
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from maybot_control_center import app, learning

REPO_ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app.app)


def test_list_lab_targets_returns_seeded_catalog():
    targets = learning.list_lab_targets()
    assert isinstance(targets, list) and targets
    ids = {t["id"] for t in targets}
    # the seeded vulnerable apps + the IDS log source
    assert {"juice-shop", "dvwa", "access-log"} <= ids
    for t in targets:
        assert set(t) >= {"id", "name", "kind", "app", "service", "ports", "look_for", "notes"}
        assert t["kind"] in ("ids", "pentest")
        assert isinstance(t["ports"], list)
        assert isinstance(t["look_for"], list)
    # the well-known vulnerable images are present
    apps = {t["app"] for t in targets}
    assert "bkimminich/juice-shop" in apps
    assert "vulnerables/web-dvwa" in apps


def test_list_lab_targets_missing_file_is_safe(monkeypatch):
    monkeypatch.setattr(learning, "LAB_TARGETS_FILE", REPO_ROOT / "does-not-exist.yaml")
    assert learning.list_lab_targets() == []


def test_compose_file_is_valid_yaml():
    compose = REPO_ROOT / "labs" / "docker-compose.yml"
    assert compose.exists()
    docs = list(yaml.safe_load_all(compose.read_text(encoding="utf-8")))
    assert docs and isinstance(docs[0], dict)
    services = docs[0].get("services") or {}
    # the compose services referenced by the catalog exist
    assert {"juice-shop", "dvwa", "log-shipper"} <= set(services)


def test_lab_targets_yaml_is_valid():
    seed = REPO_ROOT / "lab_targets.yaml"
    assert seed.exists()
    data = yaml.safe_load(seed.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and isinstance(data.get("targets"), list)


def test_targets_route_serves_catalog():
    r = client.get("/api/learning/lab/targets")
    assert r.status_code == 200
    body = r.json()
    assert "targets" in body
    ids = {t["id"] for t in body["targets"]}
    assert {"juice-shop", "dvwa", "access-log"} <= ids
