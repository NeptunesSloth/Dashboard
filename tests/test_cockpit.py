"""Integration tests for the trading-cockpit API: live-data overlay, risk,
control, ML signals, advisor, notifications, and P&L history. Everything is
flagged off by default, so these assert the safe demo/fallback behaviour."""
import os

from fastapi.testclient import TestClient

os.environ.setdefault("MAYBOT_DEMO", "1")
import maybot_control_center.app as appmod  # noqa: E402
from maybot_control_center import botcontrol, risk  # noqa: E402

client = TestClient(appmod.app)


def setup_function(_):
    botcontrol.clear()
    risk.kill_switch(False)
    risk.reset_hwm()


def test_snapshot_has_live_layer():
    s = client.get("/api/command").json()
    assert "risk" in s and "halted" in s["risk"]
    assert s.get("live_market") is False          # no provider configured
    assert s["advisor"]["llm"] is False           # no API key configured


def test_risk_status_and_killswitch():
    assert client.get("/api/risk").json()["status"]["kill_switch"] is False
    assert client.post("/api/risk/kill", json={"on": True}).status_code == 200
    assert risk.is_halted() is True
    assert client.get("/api/risk").json()["status"]["kill_switch"] is True
    client.post("/api/risk/kill", json={"on": False})
    assert risk.is_halted() is False


def test_bot_control_overlays_snapshot():
    r = client.post("/api/bots/control", json={"bot": "Momentum Alpha", "action": "pause"})
    assert r.status_code == 200 and r.json()["state"] == "paused"
    bots = client.get("/api/command").json()["bots"]
    assert any(b["name"] == "Momentum Alpha" and b["status"] == "paused" for b in bots)
    assert client.post("/api/bots/control", json={"bot": "X", "action": "bogus"}).status_code == 400


def test_flatten_all():
    assert client.post("/api/bots/flatten").status_code == 200
    assert botcontrol.is_flatten_all() is True


def test_signals_disabled_by_default():
    j = client.get("/api/signals").json()
    assert j["enabled"] is False and j["scores"] == []


def test_signals_enabled(monkeypatch):
    monkeypatch.setenv("MAYBOT_SIGNALS", "1")
    j = client.get("/api/signals").json()
    assert j["enabled"] is True and len(j["scores"]) >= 1
    for s in j["scores"]:
        assert 0.0 <= s["score"] <= 1.0 and s["direction"] in {"long", "short", "flat"}


def test_advisor_local_briefing():
    j = client.get("/api/advisor").json()
    assert j["source"] == "local" and j["text"] and isinstance(j["highlights"], list)


def test_notifications_and_pnl():
    n = client.get("/api/notifications").json()
    assert n["channels"] == [] and isinstance(n["recent"], list)
    p = client.get("/api/pnl?metric=total").json()
    assert p["metric"] == "total" and isinstance(p["series"], list)


def test_market_quotes_and_account_fallback():
    q = client.get("/api/market/quotes?symbols=AAPL,NVDA").json()
    assert q["live"] is False and isinstance(q["quotes"], dict)
    a = client.get("/api/market/account").json()
    assert a["enabled"] is False and a["account"] == {}
