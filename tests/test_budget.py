from maybot_control_center import budget, usage


def _usage(total, per_agent=None):
    rows = [{"agent": a, "cost": c, "tokens_in": 0, "tokens_out": 0} for a, c in (per_agent or {}).items()]
    return lambda: {"agents": rows, "totals": {"cost": total}}


def setup_function():
    usage.clear() if hasattr(usage, "clear") else None


def test_reserves_off_by_default(monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_USD", 0.0)
    monkeypatch.setattr(budget, "_usage", _usage(12.0))
    r = budget.reserves()
    assert r["enabled"] is False and r["spent"] == 12.0
    assert budget.allowed("Nova") is True            # never throttles when off


def test_reserves_math_and_levels(monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_USD", 100.0)
    monkeypatch.setattr(budget, "LOW_PCT", 20.0)
    monkeypatch.setattr(budget, "_usage", _usage(75.0))   # 25% remaining
    r = budget.reserves()
    assert r["remaining"] == 25.0 and r["pct_remaining"] == 25.0
    assert not r["low"] and not r["exhausted"]
    monkeypatch.setattr(budget, "_usage", _usage(90.0))   # 10% → low
    assert budget.reserves()["low"] is True
    monkeypatch.setattr(budget, "_usage", _usage(95.0))   # 5% → critical
    assert budget.reserves()["critical"] is True
    monkeypatch.setattr(budget, "_usage", _usage(100.0))  # 0 → exhausted
    assert budget.reserves()["exhausted"] is True


def test_throttle_cuts_low_merit_first(monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_USD", 100.0)
    monkeypatch.setattr(budget, "LOW_PCT", 20.0)
    tiers = {"Trusty": "Trusted", "Middle": "Standard", "Probie": "Probation"}
    monkeypatch.setattr("maybot_control_center.reputation.tier", lambda a: tiers[a])

    monkeypatch.setattr(budget, "_usage", _usage(50.0))    # healthy → everyone acts
    assert all(budget.allowed(a) for a in tiers)

    monkeypatch.setattr(budget, "_usage", _usage(85.0))    # low (15%) → Probation cut
    assert budget.allowed("Trusty") and budget.allowed("Middle")
    assert not budget.allowed("Probie")

    monkeypatch.setattr(budget, "_usage", _usage(95.0))    # critical (5%) → Standard cut too
    assert budget.allowed("Trusty")
    assert not budget.allowed("Middle") and not budget.allowed("Probie")

    monkeypatch.setattr(budget, "_usage", _usage(100.0))   # exhausted → all blocked
    assert not any(budget.allowed(a) for a in tiers)
    assert budget.allowed("operator") is True              # operator never throttled


def test_per_agent_cap(monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_USD", 0.0)         # sect budget off
    monkeypatch.setattr(budget, "AGENT_CAP", 2.0)
    monkeypatch.setattr(budget, "_usage", _usage(5.0, {"Spender": 2.5, "Frugal": 0.4}))
    assert budget.allowed("Spender") is False              # over its own cap
    assert budget.allowed("Frugal") is True
    assert budget.status("Spender") == "capped"


def test_snapshot_shape(monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_USD", 10.0)
    monkeypatch.setattr(budget, "_usage", _usage(4.0, {"Nova": 4.0}))
    snap = budget.snapshot()
    assert snap["reserves"]["remaining"] == 6.0
    assert snap["agents"][0]["agent"] == "Nova" and "status" in snap["agents"][0]
