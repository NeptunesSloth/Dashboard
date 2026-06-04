"""Endpoint coverage for the operational upgrades: health/readiness probes,
SLO, maintenance silencing, and data export."""
import csv
import io

from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import aggregator, maintenance, history, usage

client = TestClient(app)


def setup_function():
    maintenance.clear()
    history.clear()


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
