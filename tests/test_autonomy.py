import pytest

from maybot_control_center import autonomy, reputation, budget, pills


SAFE = {"name": "ver", "auto_approve": True}
UNSAFE = {"name": "rm", "auto_approve": False}


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    """Isolate the budget logic from external influences on the cap (reputation /
    pills bonuses, probation, sect budget) so the tests are deterministic
    regardless of global cultivation/reputation state left by other tests."""
    autonomy.clear()
    monkeypatch.setattr(reputation, "is_probation", lambda a: False)
    monkeypatch.setattr(reputation, "autonomy_bonus", lambda a: 0)
    monkeypatch.setattr(pills, "autonomy_bonus", lambda a: 0)
    monkeypatch.setattr(budget, "allowed", lambda a: True)


def test_non_auto_approve_never_runs(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    assert autonomy.allow("operator", UNSAFE) is False
    assert autonomy.allow("Nova", UNSAFE) is False


def test_operator_runs_auto_approve_unbounded(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", False)  # even with autonomy off
    assert autonomy.allow("operator", SAFE) is True
    assert autonomy.allow("operator", SAFE) is True


def test_agent_blocked_when_disabled(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", False)
    assert autonomy.allow("Nova", SAFE) is False


def test_agent_within_budget_then_blocked(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(autonomy, "MAX_CALLS", 2)
    assert autonomy.allow("Nova", SAFE) is True
    assert autonomy.allow("Nova", SAFE) is True
    assert autonomy.allow("Nova", SAFE) is False  # budget exhausted
    autonomy.reset("Nova")
    assert autonomy.allow("Nova", SAFE) is True    # reset restores budget


def test_per_tool_budget_override(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(autonomy, "MAX_CALLS", 5)
    tool = {"name": "noisy", "auto_approve": True, "max_auto_per_task": 1}
    assert autonomy.allow("Nova", tool) is True
    assert autonomy.allow("Nova", tool) is False  # per-tool cap of 1 beats global 5
    # a different tool has its own independent budget
    assert autonomy.allow("Nova", SAFE) is True


def test_time_window_blocks_outside_hours(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(autonomy, "MAX_CALLS", 5)
    monkeypatch.setattr(autonomy, "_window_ok", lambda: False)
    assert autonomy.allow("Nova", SAFE) is False
    monkeypatch.setattr(autonomy, "_window_ok", lambda: True)
    assert autonomy.allow("Nova", SAFE) is True


def test_window_parsing():
    import maybot_control_center.autonomy as a
    # same-day window
    a.HOURS = "9-17"
    assert a._window_ok() in (True, False)  # depends on clock, just exercises parse
    a.HOURS = "bad-range"
    assert a._window_ok() is True  # malformed → permissive (no silent lockout)
    a.HOURS = ""


def test_pause_is_a_kill_switch(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(autonomy, "MAX_CALLS", 5)
    autonomy.set_paused(True)
    assert autonomy.allow("Nova", SAFE) is False     # agents blocked while paused
    assert autonomy.allow("operator", SAFE) is True  # operator still works
    assert autonomy.set_paused(False)["paused"] is False
    assert autonomy.allow("Nova", SAFE) is True
