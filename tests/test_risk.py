"""Tests for the risk engine and operator bot-control — fully offline."""
from maybot_control_center import botcontrol, risk


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _reset_risk():
    risk.kill_switch(False)
    risk.reset_hwm()


def _reset_botcontrol():
    botcontrol.clear()


# --------------------------------------------------------------------------- #
# risk: drawdown
# --------------------------------------------------------------------------- #
def test_drawdown_halts_past_threshold(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_DRAWDOWN_PCT", "15.0")
    monkeypatch.setenv("MAYBOT_MAX_EXPOSURE", "0")

    # Establish a high-water mark at equity 1000.
    r1 = risk.evaluate([], account={"equity": 1000.0})
    assert r1["hwm"] == 1000.0
    assert r1["drawdown_pct"] == 0.0
    assert r1["halted"] is False

    # A small dip (5%) stays within budget.
    r2 = risk.evaluate([], account={"equity": 950.0})
    assert r2["drawdown_pct"] == 5.0
    assert r2["halted"] is False

    # A 20% drawdown from the hwm breaches the 15% decree.
    r3 = risk.evaluate([], account={"equity": 800.0})
    assert r3["drawdown_pct"] == 20.0
    assert r3["halted"] is True
    assert any(b["type"] == "drawdown" for b in r3["breaches"])


def test_reset_hwm_clears_drawdown(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_DRAWDOWN_PCT", "15.0")
    risk.evaluate([], account={"equity": 1000.0})
    assert risk.evaluate([], account={"equity": 800.0})["drawdown_pct"] == 20.0
    risk.reset_hwm()
    # After reset, the next equity becomes the new hwm => no drawdown.
    r = risk.evaluate([], account={"equity": 800.0})
    assert r["hwm"] == 800.0
    assert r["drawdown_pct"] == 0.0
    assert r["halted"] is False


# --------------------------------------------------------------------------- #
# risk: exposure
# --------------------------------------------------------------------------- #
def test_exposure_cap_breach_halts(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_DRAWDOWN_PCT", "0")  # disable drawdown halt
    monkeypatch.setenv("MAYBOT_MAX_EXPOSURE", "5000")
    positions = [
        {"qty": 40, "last": 100.0},   # 4000
        {"qty": 10, "last": 200.0},   # 2000  => total 6000 > 5000
    ]
    r = risk.evaluate(positions, account={"equity": 10000.0})
    assert r["exposure"] == 6000.0
    assert r["halted"] is True
    assert any(b["type"] == "exposure" for b in r["breaches"])


def test_exposure_uses_abs_qty(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_EXPOSURE", "0")  # unlimited
    positions = [{"qty": -25, "last": 240.0}]  # short position, gross = 6000
    r = risk.evaluate(positions)
    assert r["exposure"] == 6000.0
    assert r["halted"] is False


def test_per_bot_exposure_breach(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_BOT_EXPOSURE", "5000")
    bots = [
        {"name": "Momentum Alpha", "exposure": 6120.0},
        {"name": "Vol Harvest", "exposure": 2180.0},
    ]
    r = risk.evaluate([], bots=bots)
    assert r["bot_breaches"] == [{"bot": "Momentum Alpha", "exposure": 6120.0}]


# --------------------------------------------------------------------------- #
# risk: kill-switch
# --------------------------------------------------------------------------- #
def test_kill_switch_toggles_halt_and_can_trade():
    _reset_risk()
    assert risk.is_halted() is False
    assert risk.can_trade("any") is True

    st = risk.kill_switch(True, actor="littlejay")
    assert st["kill_switch"] is True
    assert st["actor"] == "littlejay"
    assert risk.is_halted() is True
    assert risk.can_trade("any") is False

    # evaluate also reports halted when the switch is engaged.
    r = risk.evaluate([], account={"equity": 1000.0})
    assert r["halted"] is True
    assert "kill_switch engaged" in r["reasons"]

    risk.kill_switch(False)
    assert risk.is_halted() is False
    assert risk.can_trade("any") is True


def test_status_reports_limits(monkeypatch):
    _reset_risk()
    monkeypatch.setenv("MAYBOT_MAX_DRAWDOWN_PCT", "12.5")
    s = risk.status()
    assert s["limits"]["max_drawdown_pct"] == 12.5
    assert s["kill_switch"] is False


# --------------------------------------------------------------------------- #
# botcontrol
# --------------------------------------------------------------------------- #
def test_set_state_valid():
    _reset_botcontrol()
    rec = botcontrol.set_state("Momentum Alpha", "pause", actor="littlejay")
    assert rec["bot"] == "Momentum Alpha"
    assert rec["state"] == "paused"
    assert rec["actor"] == "littlejay"
    assert "ts" in rec
    assert botcontrol.state("Momentum Alpha")["state"] == "paused"


def test_set_state_invalid():
    _reset_botcontrol()
    rec = botcontrol.set_state("Momentum Alpha", "explode")
    assert "error" in rec
    assert botcontrol.state("Momentum Alpha") == {}


def test_all_states():
    _reset_botcontrol()
    botcontrol.set_state("A", "pause")
    botcontrol.set_state("B", "throttle")
    states = botcontrol.all_states()
    assert states["A"]["state"] == "paused"
    assert states["B"]["state"] == "throttled"


def test_flatten_all_sets_flag():
    _reset_botcontrol()
    botcontrol.set_state("A", "pause")
    assert botcontrol.is_flatten_all() is False
    res = botcontrol.flatten_all(actor="op")
    assert res["flatten_all"] is True
    assert botcontrol.is_flatten_all() is True
    assert botcontrol.state("A")["state"] == "flatten"


def test_apply_to_bots_overrides_status():
    _reset_botcontrol()
    bots = [
        {"name": "Momentum Alpha", "status": "active"},
        {"name": "Mean Reversion", "status": "active"},
    ]
    botcontrol.set_state("Momentum Alpha", "pause")
    out = botcontrol.apply_to_bots(bots)
    assert out[0]["status"] == "paused"
    assert out[1]["status"] == "active"
    # Original input is not mutated.
    assert bots[0]["status"] == "active"


def test_apply_to_bots_flatten_all_overrides_everything():
    _reset_botcontrol()
    bots = [{"name": "A", "status": "active"}, {"name": "B", "status": "throttled"}]
    botcontrol.flatten_all()
    out = botcontrol.apply_to_bots(bots)
    assert all(b["status"] == "flatten" for b in out)
