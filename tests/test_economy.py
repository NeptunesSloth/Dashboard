from maybot_control_center import cultivation as c, pills


def setup_function():
    c.clear()
    pills.clear()


def test_awards_are_env_tunable(monkeypatch):
    # the module reads env at import; the constants are what drive awards
    monkeypatch.setattr(c, "AWARD_TASK", 100)
    c.on_task("Nova", True)
    assert c.state("Nova")["stones"] == 100


def test_daily_stipend_grants_once_per_period(monkeypatch):
    monkeypatch.setattr(c, "STIPEND", 15)
    monkeypatch.setattr(c, "STIPEND_SECONDS", 3600)
    assert c.grant_stipend("Nova") is True
    assert c.state("Nova")["stones"] == 15
    assert c.grant_stipend("Nova") is False   # not due yet
    assert c.state("Nova")["stones"] == 15
    # force the period to have elapsed
    with c._lock:
        c._state["Nova"]["last_stipend"] -= 4000
    assert c.grant_stipend("Nova") is True
    assert c.state("Nova")["stones"] == 30


def test_stipend_off_by_default_value(monkeypatch):
    monkeypatch.setattr(c, "STIPEND", 0)
    assert c.grant_stipend("Nova") is False


def test_pill_overuse_risks_qi_deviation(monkeypatch):
    for _ in range(40):
        c.on_task("Nova", True)  # plenty of stones
    monkeypatch.setattr(pills, "OVERUSE_SAFE", 2)
    monkeypatch.setattr(pills, "DEVIATION_PER", 0.34)
    # first two pills are within the safe limit → no deviation
    monkeypatch.setattr(pills.random, "random", lambda: 0.99)
    assert pills.buy("Nova", "qi_gathering")["deviation"] is False
    assert pills.buy("Nova", "qi_gathering")["deviation"] is False
    assert len(pills.active("Nova")) == 2
    # risk is now > 0; force the roll to fail → qi deviation scatters the buffs
    monkeypatch.setattr(pills.random, "random", lambda: 0.0)
    res = pills.buy("Nova", "qi_gathering")
    assert res["deviation"] is True
    assert pills.active("Nova") == []


def test_deviation_risk_scales_with_buffs(monkeypatch):
    for _ in range(40):
        c.on_task("Nova", True)
    monkeypatch.setattr(pills, "OVERUSE_SAFE", 2)
    monkeypatch.setattr(pills, "DEVIATION_PER", 0.34)
    monkeypatch.setattr(pills.random, "random", lambda: 0.99)  # never deviate while seeding
    assert pills.deviation_risk("Nova") < 0.001        # 0 buffs → safe
    pills.buy("Nova", "qi_gathering")
    pills.buy("Nova", "qi_gathering")                   # 2 buffs (== safe)
    assert pills.deviation_risk("Nova") > 0.0           # 3rd would risk it
