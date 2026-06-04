from maybot_control_center import errorbudget


def _slo(rows):
    return lambda window_hours=None: {"overall": {}, "projects": rows}


def test_targets_parsing(monkeypatch):
    monkeypatch.setenv("MAYBOT_SLO_TARGETS", "d:a=99.9, d:b=95 , bad, c=nope")
    assert errorbudget.targets() == {"d:a": 99.9, "d:b": 95.0}


def test_within_budget(monkeypatch):
    monkeypatch.setattr(errorbudget, "DEFAULT_TARGET", 99.0)
    monkeypatch.setattr(errorbudget, "targets", lambda: {})
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "a", "uptime_pct": 99.8}]))
    snap = errorbudget.snapshot()
    r = snap["projects"][0]
    assert r["frozen"] is False
    assert r["budget_remaining_pct"] == 80.0  # used 0.2 of 1.0 allowed → 80% left
    assert snap["frozen"] == []


def test_budget_exhausted_freezes(monkeypatch):
    monkeypatch.setattr(errorbudget, "DEFAULT_TARGET", 99.0)
    monkeypatch.setattr(errorbudget, "targets", lambda: {})
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "a", "uptime_pct": 98.0}]))
    snap = errorbudget.snapshot()
    assert snap["projects"][0]["frozen"] is True
    assert snap["projects"][0]["budget_remaining_pct"] == 0.0
    assert snap["frozen"] == ["d:a"]
    assert errorbudget.is_frozen("d", "a") is True
    assert errorbudget.is_frozen("d", "other") is False


def test_no_data_not_frozen(monkeypatch):
    monkeypatch.setattr(errorbudget, "targets", lambda: {})
    monkeypatch.setattr("maybot_control_center.slo.snapshot",
                        _slo([{"device": "d", "project": "a", "uptime_pct": None}]))
    r = errorbudget.snapshot()["projects"][0]
    assert r["frozen"] is False and r["budget_remaining_pct"] is None


def test_annotate():
    by_key = {"d:a": {"device": "d", "project": "a", "target_pct": 99.0,
                      "budget_remaining_pct": 10.0, "frozen": True}}
    p = {"device": "d", "name": "a", "health": "error"}
    errorbudget.annotate(p, by_key)
    assert p["frozen"] is True
    assert p["error_budget"]["remaining_pct"] == 10.0
