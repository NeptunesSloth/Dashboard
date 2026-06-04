from maybot_control_center import status_page, aggregator


def _slo(rows):
    return lambda window_hours=None: {"overall": {}, "projects": rows}


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MAYBOT_PUBLIC_STATUS", raising=False)
    assert status_page.enabled() is False


def test_enabled_flag(monkeypatch):
    monkeypatch.setenv("MAYBOT_PUBLIC_STATUS", "1")
    assert status_page.enabled() is True


def test_public_data_operational(monkeypatch):
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "api", "uptime_pct": 99.9, "current": "ok"}]))
    monkeypatch.setattr(aggregator, "last_summary", lambda: {"online_devices": 1, "offline_devices": 0})
    d = status_page.public_data()
    assert d["overall"] == "operational"
    assert d["services"][0] == {"service": "api", "state": "ok", "uptime_pct": 99.9}
    # public payload must not leak device internals
    assert "url" not in d["services"][0] and "device" not in d["services"][0]


def test_public_data_degraded(monkeypatch):
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "api", "uptime_pct": 50.0, "current": "error"},
                              {"device": "d", "project": "web", "uptime_pct": 100.0, "current": "ok"}]))
    monkeypatch.setattr(aggregator, "last_summary", lambda: {"online_devices": 1, "offline_devices": 0})
    assert status_page.public_data()["overall"] == "degraded"


def test_render_html_contains_service(monkeypatch):
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "api", "uptime_pct": 99.9, "current": "ok"}]))
    monkeypatch.setattr(aggregator, "last_summary", lambda: {"online_devices": 1, "offline_devices": 0})
    html = status_page.render_html()
    assert "<table" in html and "api" in html and "99.90%" in html
