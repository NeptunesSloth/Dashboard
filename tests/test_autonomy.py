from maybot_control_center import autonomy


SAFE = {"name": "ver", "auto_approve": True}
UNSAFE = {"name": "rm", "auto_approve": False}


def setup_function():
    autonomy.clear()


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


def test_pause_is_a_kill_switch(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(autonomy, "MAX_CALLS", 5)
    autonomy.set_paused(True)
    assert autonomy.allow("Nova", SAFE) is False     # agents blocked while paused
    assert autonomy.allow("operator", SAFE) is True  # operator still works
    assert autonomy.set_paused(False)["paused"] is False
    assert autonomy.allow("Nova", SAFE) is True
