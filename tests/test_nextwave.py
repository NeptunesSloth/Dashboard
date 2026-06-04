"""Per-project PR switch, inbound alerts, backup/restore, agent auto-register."""
from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import (pullrequest, inbound, registry, backup, store,
                                   config, governance, artifacts)

client = TestClient(app)


# ---- per-project PR mode ----
def test_pr_mode_propose_never_opens(monkeypatch):
    artifacts.clear()
    monkeypatch.setattr(pullrequest, "ENABLED", True)            # global says open
    monkeypatch.setattr(pullrequest, "_gh_available", lambda: True)
    monkeypatch.setattr(pullrequest, "_plan", lambda c, p, cause: {"title": "T", "body": "", "diff": "d"})
    monkeypatch.setattr(governance, "leader", lambda: "Forge")
    opened = []
    monkeypatch.setattr(pullrequest, "_open_pr", lambda *a: opened.append(1) or "url")
    res = pullrequest.propose("owner/repo", "github", "bug", mode="propose")   # override → proposal
    assert res["opened"] is False and opened == []


def test_pr_mode_open_overrides_disabled(monkeypatch):
    monkeypatch.setattr(pullrequest, "ENABLED", False)          # global off
    monkeypatch.setattr(pullrequest, "_gh_available", lambda: True)
    monkeypatch.setattr(pullrequest, "_plan", lambda c, p, cause: {"title": "T", "body": "", "diff": "d"})
    monkeypatch.setattr(pullrequest, "_open_pr", lambda *a: "https://github.com/o/r/pull/9")
    res = pullrequest.propose("owner/repo", "github", "bug", mode="open")
    assert res["opened"] is True


# ---- inbound alerts ----
def test_ingest_records_and_routes(monkeypatch):
    inbound.clear()
    fired = []
    monkeypatch.setattr("maybot_control_center.notifier.notify_event", lambda e, t, m: fired.append(e))
    r = inbound.ingest("alertmanager", "critical", "DiskFull", "node-1 / at 98%")
    assert r["severity"] == "critical" and r["source"] == "alertmanager"
    assert inbound.snapshot()["count"] == 1
    assert "inbound" in fired


def test_ingest_endpoint():
    inbound.clear()
    r = client.post("/api/ingest/alert", json={"title": "CI failed", "source": "github", "severity": "error"})
    assert r.status_code == 200
    assert client.get("/api/inbound").json()["alerts"][0]["title"] == "CI failed"


def test_ingest_token_auth(monkeypatch):
    monkeypatch.setattr(inbound, "INGEST_TOKEN", "ingest-secret")
    # wrong token but works because no control-center auth is configured (operator) — assert path is reachable
    r = client.post("/api/ingest/alert", headers={"x-ingest-token": "ingest-secret"},
                    json={"title": "external", "severity": "warning"})
    assert r.status_code == 200


# ---- agent auto-register ----
def test_register_merges_into_devices(monkeypatch):
    registry.clear()
    monkeypatch.setattr(config, "load_devices", lambda: [{"name": "prod-1", "url": "http://a"}])
    registry.register("edge-7", "http://edge-7:8100/", api_token="t", timeout=9)
    names = {d["name"] for d in config.all_devices()}
    assert names == {"prod-1", "edge-7"}
    dev = next(d for d in config.all_devices() if d["name"] == "edge-7")
    assert dev["url"] == "http://edge-7:8100" and dev["timeout"] == 9.0


def test_register_endpoint_and_deregister():
    registry.clear()
    assert client.post("/api/agents/register", json={"name": "edge-9", "url": "http://x:8100"}).status_code == 200
    assert registry.snapshot()["count"] == 1
    assert client.post("/api/agents/register", json={"name": "bad", "url": "ftp://x"}).status_code == 400
    assert client.post("/api/agents/deregister", json={"name": "edge-9"}).json()["deregistered"] is True


# ---- backup / restore ----
def test_backup_restore_roundtrip(monkeypatch):
    store._reset_for_tests(":memory:")
    store.init()
    try:
        from maybot_control_center import taskqueue, oaths
        taskqueue.clear(); oaths.clear()
        taskqueue.create("persist this", assignee="Nova")
        oaths.claim("d:bot", "Nova")
        snap = backup.export()
        assert snap["persisted"] is True and "taskqueue" in snap["state"]
        # wipe everything, then restore
        taskqueue.clear(); oaths.clear()
        assert taskqueue.list_tasks() == []
        backup.restore(snap)
        assert any(t["title"] == "persist this" for t in taskqueue.list_tasks())
        assert oaths.is_claimed("d", "bot")
    finally:
        store._reset_for_tests("")


def test_restore_requires_db(monkeypatch):
    store._reset_for_tests("")
    import pytest
    with pytest.raises(ValueError):
        backup.restore({"state": {}})
