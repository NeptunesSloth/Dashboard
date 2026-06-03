from maybot_control_center import history


def _proj(device, name, pnl=None, health="ok"):
    p = {"device": device, "name": name, "type": "trading_bot", "health": health}
    if pnl is not None:
        p["metrics"] = {"profit_today": pnl}
    return p


def setup_function():
    history.clear()


def test_record_and_get_accumulates_points():
    history.record([_proj("dev1", "bot", pnl=1.0)])
    history.record([_proj("dev1", "bot", pnl=2.0)])
    series = history.get("dev1", "bot")
    assert [pt["pnl"] for pt in series] == [1.0, 2.0]
    assert all(pt["health"] == "ok" for pt in series)
    assert all(isinstance(pt["ts"], int) for pt in series)


def test_non_numeric_pnl_becomes_none():
    history.record([_proj("dev1", "bot", pnl="unknown")])
    history.record([{"device": "dev1", "name": "bot", "health": "ok"}])  # no metrics
    assert [pt["pnl"] for pt in history.get("dev1", "bot")] == [None, None]


def test_get_unknown_series_is_empty():
    assert history.get("nope", "nope") == []


def test_attach_adds_history_in_place():
    history.record([_proj("dev1", "bot", pnl=5.0)])
    projects = [_proj("dev1", "bot", pnl=6.0)]
    history.record(projects)
    history.attach(projects)
    assert "history" in projects[0]
    assert [pt["pnl"] for pt in projects[0]["history"]] == [5.0, 6.0]


def test_series_is_capped_at_max_points():
    for i in range(history.MAX_POINTS + 25):
        history.record([_proj("dev1", "bot", pnl=float(i))])
    series = history.get("dev1", "bot")
    assert len(series) == history.MAX_POINTS
    # oldest points dropped; the most recent value is retained
    assert series[-1]["pnl"] == float(history.MAX_POINTS + 24)


def test_get_returns_a_copy():
    history.record([_proj("dev1", "bot", pnl=1.0)])
    series = history.get("dev1", "bot")
    series.append({"ts": 0, "pnl": 999, "health": "ok"})
    assert len(history.get("dev1", "bot")) == 1
