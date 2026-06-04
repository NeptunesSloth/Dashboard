import time

from maybot_control_center import slo, history


def setup_function():
    history.clear()


def _record(device, name, health, ts_ms):
    # record() stamps its own ts, so write straight into the series for control.
    history.record([{"device": device, "name": name, "health": health}])
    series = history._series[f"{device}:{name}"]
    series[-1]["ts"] = ts_ms


def test_perfect_uptime():
    now = int(time.time() * 1000)
    for i in range(5):
        _record("d", "bot", "ok", now - (5 - i) * 60_000)
    rows = slo.snapshot()["projects"]
    assert len(rows) == 1
    r = rows[0]
    assert r["uptime_pct"] == 100.0
    assert r["incidents"] == 0
    assert r["current"] == "ok"


def test_incident_and_recovery_mttr():
    now = int(time.time() * 1000)
    # ok at t-300s, error at t-240s, ok again at t-180s → one incident, 60s outage
    _record("d", "bot", "ok", now - 300_000)
    _record("d", "bot", "error", now - 240_000)
    _record("d", "bot", "ok", now - 180_000)
    _record("d", "bot", "ok", now - 60_000)
    r = slo.snapshot()["projects"][0]
    assert r["incidents"] == 1
    assert r["mttr_seconds"] == 60.0
    assert 0 < r["uptime_pct"] < 100


def test_unknown_excluded_from_denominator():
    now = int(time.time() * 1000)
    _record("d", "bot", "unknown", now - 120_000)
    _record("d", "bot", "unknown", now - 60_000)
    r = slo.snapshot()["projects"][0]
    assert r["uptime_pct"] is None  # never had measurable health


def test_window_filters_old_points():
    now = int(time.time() * 1000)
    _record("d", "bot", "error", now - 10 * 3600_000)  # 10h ago
    _record("d", "bot", "ok", now - 60_000)
    rows = slo.snapshot(window_hours=1)["projects"]  # 1h window drops the old error
    assert rows[0]["uptime_pct"] == 100.0
    assert rows[0]["incidents"] == 0


def test_overall_aggregates():
    now = int(time.time() * 1000)
    _record("d", "a", "ok", now - 120_000)
    _record("d", "a", "ok", now - 60_000)
    _record("d", "b", "ok", now - 120_000)
    _record("d", "b", "error", now - 60_000)
    overall = slo.snapshot()["overall"]
    assert overall["projects"] == 2
    assert overall["total_incidents"] == 1
    assert overall["avg_uptime_pct"] is not None
