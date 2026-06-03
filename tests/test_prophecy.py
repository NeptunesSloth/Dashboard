from maybot_control_center import prophecy, history


def setup_function():
    history.clear()


def _series(device, name, healths, pnls=None):
    pnls = pnls or [None] * len(healths)
    for h, p in zip(healths, pnls):
        proj = {"device": device, "name": name, "health": h}
        if p is not None:
            proj["metrics"] = {"profit_today": p}
        history.record([proj])


def test_steady_realm_reads_favorable():
    _series("dev", "calm", ["ok"] * 6, [10, 10, 10, 11, 10, 10])
    omen = next(o for o in prophecy.divine() if o["project"] == "calm")
    assert omen["omen"] == "favorable"


def test_recent_error_is_ominous():
    _series("dev", "broken", ["ok", "ok", "error"])
    omen = next(o for o in prophecy.divine() if o["project"] == "broken")
    assert omen["omen"] == "ominous"


def test_repeated_warnings_raise_caution():
    _series("dev", "shaky", ["ok", "warning", "ok", "warning"])
    omen = next(o for o in prophecy.divine() if o["project"] == "shaky")
    assert omen["omen"] == "caution"


def test_sharp_plunge_is_ominous():
    _series("dev", "crash", ["ok"] * 7, [10, 11, 10, 12, 11, 10, -40])
    omen = next(o for o in prophecy.divine() if o["project"] == "crash")
    assert omen["omen"] == "ominous"


def test_downtrend_is_caution():
    _series("dev", "fade", ["ok"] * 8, [20, 18, 16, 14, 12, 10, 8, 6])
    omen = next(o for o in prophecy.divine() if o["project"] == "fade")
    assert omen["omen"] == "caution"


def test_short_series_is_skipped():
    _series("dev", "new", ["ok"])  # < min_points
    assert all(o["project"] != "new" for o in prophecy.divine())


def test_ominous_omens_sort_first():
    _series("dev", "good", ["ok"] * 4)
    _series("dev", "bad", ["ok", "ok", "error"])
    omens = prophecy.divine()
    assert omens[0]["omen"] == "ominous"
