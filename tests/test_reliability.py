"""Endpoint coverage for the operational upgrades: health/readiness probes,
SLO, maintenance silencing, and data export."""
import csv
import io

from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import aggregator, maintenance, history, oaths, errorbudget, status_page

client = TestClient(app)


def setup_function():
    maintenance.clear()
    history.clear()
    oaths.clear()


# ---- health / readiness ----
def test_healthz_always_ok():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_readyz_reports_summary(monkeypatch):
    monkeypatch.setattr(aggregator, "last_summary",
                        lambda: {"online_devices": 2, "offline_devices": 0})
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "ready": True, "polled": True,
                        "online_devices": 2, "offline_devices": 0}


def test_readyz_strict_503_when_degraded(monkeypatch):
    monkeypatch.setattr(aggregator, "last_summary",
                        lambda: {"online_devices": 1, "offline_devices": 1})
    assert client.get("/readyz").status_code == 200            # lenient by default
    assert client.get("/readyz?strict=1").status_code == 503   # strict gates on offline


# ---- maintenance silencing ----
def test_silence_roundtrip():
    r = client.post("/api/maintenance/silence", json={"target": "d:bot", "minutes": 30, "reason": "upgrade"})
    assert r.status_code == 200 and r.json()["target"] == "d:bot"
    assert maintenance.is_silenced("d", "bot") is True

    listed = client.get("/api/maintenance").json()
    assert listed["silences"][0]["target"] == "d:bot"

    r = client.post("/api/maintenance/unsilence", json={"target": "d:bot"})
    assert r.json()["unsilenced"] is True
    assert maintenance.is_silenced("d", "bot") is False


def test_silence_rejects_bad_target():
    assert client.post("/api/maintenance/silence", json={"target": "bad target!"}).status_code == 400


# ---- SLO ----
def test_slo_endpoint_shape():
    history.record([{"device": "d", "name": "bot", "health": "ok"}])
    r = client.get("/api/slo")
    assert r.status_code == 200
    body = r.json()
    assert "overall" in body and "projects" in body


# ---- export ----
def test_export_history_csv():
    history.record([{"device": "d", "name": "bot", "health": "ok",
                     "metrics": {"profit_today": 1.5}}])
    r = client.get("/api/export/history?fmt=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["device", "project", "ts_ms", "health", "pnl"]
    assert any(row[:2] == ["d", "bot"] for row in rows[1:])


def test_export_usage_json():
    r = client.get("/api/export/usage?fmt=json&hours=6")
    assert r.status_code == 200
    assert r.json()["hours"] == 6


# ---- error-budget freeze on actions ----
def test_action_frozen_returns_423(monkeypatch):
    monkeypatch.setattr(errorbudget, "is_frozen", lambda d, n: True)
    r = client.post("/api/action/prod-1/api-gateway/start")
    assert r.status_code == 423

    # force=true overrides the freeze (then fails downstream on the unreachable device)
    monkeypatch.setattr("maybot_control_center.routers.fleet._resolve_device", lambda n: {"name": n, "url": "http://x"})
    r2 = client.post("/api/action/prod-1/api-gateway/start?force=true")
    assert r2.status_code != 423


def test_errorbudget_endpoint():
    assert client.get("/api/errorbudget").status_code == 200


# ---- oaths (incident ownership) ----
def test_oath_claim_release():
    r = client.post("/api/oaths/claim", json={"target": "d:bot", "who": "Nova", "note": "on it"})
    assert r.status_code == 200 and r.json()["who"] == "Nova"
    assert oaths.is_claimed("d", "bot") is True
    assert client.get("/api/oaths").json()["oaths"][0]["target"] == "d:bot"
    assert client.post("/api/oaths/release", json={"target": "d:bot"}).json()["released"] is True


def test_oath_claim_rejects_wildcard():
    assert client.post("/api/oaths/claim", json={"target": "d:*"}).status_code == 400


# ---- meridians / talismans / escalation read endpoints ----
def test_read_endpoints_ok():
    assert client.get("/api/meridians").status_code == 200
    assert client.get("/api/talismans").status_code == 200
    assert client.get("/api/escalation").status_code == 200


# ---- public status page (gated) ----
def test_status_page_404_when_disabled(monkeypatch):
    monkeypatch.setattr(status_page, "enabled", lambda: False)
    assert client.get("/status").status_code == 404
    assert client.get("/api/status/public").status_code == 404


def test_status_page_served_when_enabled(monkeypatch):
    monkeypatch.setattr(status_page, "enabled", lambda: True)
    r = client.get("/status")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
