"""Periodic summary reports (Daily Proclamation)."""
import pytest

from maybot_control_center import reports, slo, aggregator, notify


@pytest.fixture(autouse=True)
def _clean():
    reports.clear()
    notify.clear()
    yield
    reports.clear()
    notify.clear()


def _fake_slo(*a, **k):
    return {
        "overall": {"avg_uptime_pct": 98.5, "total_incidents": 3, "projects": 2},
        "projects": [
            {"device": "d1", "project": "p1", "uptime_pct": 99.9, "incidents": 0, "current": "ok"},
            {"device": "d2", "project": "p2", "uptime_pct": 90.0, "incidents": 3, "current": "error"},
        ],
    }


def test_build_report(monkeypatch):
    monkeypatch.setattr(slo, "snapshot", _fake_slo)
    monkeypatch.setattr(aggregator, "last_summary", lambda: {
        "total_devices": 2, "online_devices": 2, "total_projects": 2,
        "projects_with_warnings_errors": 1, "bots_running": 1, "total_trading_profit_today": 12.5})
    r = reports.build(24)
    assert r["window_hours"] == 24
    assert r["fleet"]["devices_online"] == 2
    assert r["reliability"]["avg_uptime_pct"] == 98.5
    assert r["reliability"]["worst_uptime"][0]["project"] == "p2"
    assert r["reliability"]["currently_unhealthy"][0]["project"] == "p2"


def test_render_text(monkeypatch):
    monkeypatch.setattr(slo, "snapshot", _fake_slo)
    monkeypatch.setattr(aggregator, "last_summary", lambda: {})
    text = reports.render_text(reports.build(24))
    assert "MayBot Daily Proclamation" in text
    assert "d2:p2" in text


def test_deliver_sends_notification(monkeypatch):
    monkeypatch.setattr(slo, "snapshot", _fake_slo)
    monkeypatch.setattr(aggregator, "last_summary", lambda: {})
    captured = {}
    monkeypatch.setattr(notify, "send",
                        lambda title, body, level="info", kind="alert": captured.update(title=title, kind=kind)
                        or {"delivered": ["webhook"]})
    out = reports.deliver()
    assert out["delivered"] == ["webhook"]
    assert captured["kind"] == "report"


def test_tick_respects_interval(monkeypatch):
    monkeypatch.setattr(reports, "INTERVAL_HOURS", 0)
    assert reports.tick() is False           # disabled
    monkeypatch.setattr(reports, "INTERVAL_HOURS", 24)
    monkeypatch.setattr(slo, "snapshot", _fake_slo)
    monkeypatch.setattr(aggregator, "last_summary", lambda: {})
    monkeypatch.setattr(notify, "send", lambda *a, **k: {"delivered": []})
    reports._last_run = 0.0
    assert reports.tick(now=10**12) is True   # _last_run=0, so due
