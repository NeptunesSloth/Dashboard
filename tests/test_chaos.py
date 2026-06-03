import pytest

from maybot_control_center import chaos
from maybot_control_center import cultivation


def setup_function():
    chaos.clear()
    cultivation.clear()


def test_catalog_lists_fault_kinds():
    cat = chaos.catalog()
    assert cat is chaos.TRIALS
    assert set(cat) == {"process_kill", "latency_storm", "disk_drought", "endpoint_seal"}


def test_summon_validates_kind():
    with pytest.raises(ValueError):
        chaos.summon("billing", "meteor_strike")


def test_summon_validates_target():
    with pytest.raises(ValueError):
        chaos.summon("", "process_kill")


def test_summon_creates_active_record_with_incrementing_id():
    a = chaos.summon("billing", "process_kill", disciple="Nova")
    b = chaos.summon("auth", "latency_storm")
    assert a["id"] == 1 and b["id"] == 2
    assert a["status"] == "active"
    assert a["target"] == "billing" and a["kind"] == "process_kill"
    assert a["disciple"] == "Nova"
    assert a["resolved_at"] is None
    assert a["score"] is None
    assert a["summoned_at"] > 0


def test_summon_returns_a_copy():
    a = chaos.summon("billing", "process_kill")
    a["target"] = "tampered"
    assert chaos.active()[0]["target"] == "billing"


def test_fast_recovery_scores_full_and_rewards_stones():
    t = chaos.summon("billing", "process_kill", disciple="Nova")
    res = chaos.resolve(t["id"], True, recovery_seconds=10)
    assert res["status"] == "weathered"
    assert res["score"] == 100  # well within RECOVER_TARGET
    # full score → full REWARD in spirit stones
    assert cultivation.state("Nova")["stones"] == chaos.REWARD


def test_recovery_without_time_scores_100():
    t = chaos.summon("billing", "process_kill", disciple="Nova")
    res = chaos.resolve(t["id"], True)
    assert res["score"] == 100
    assert res["recovery_seconds"] is None


def test_slow_recovery_scores_lower():
    t = chaos.summon("billing", "latency_storm", disciple="Nova")
    # recovering at 4x the target → roughly a quarter score
    res = chaos.resolve(t["id"], True, recovery_seconds=chaos.RECOVER_TARGET * 4)
    assert res["score"] == 25
    assert cultivation.state("Nova")["stones"] == round(chaos.REWARD * 25 / 100)


def test_not_recovered_fails_and_disciplines_disciple():
    t = chaos.summon("billing", "endpoint_seal", disciple="Nova")
    res = chaos.resolve(t["id"], False)
    assert res["status"] == "failed"
    assert res["score"] == 0
    # a failed trial is a misstep — fail_streak climbs
    assert cultivation.state("Nova")["fail_streak"] == 1
    assert cultivation.state("Nova")["stones"] == 0


def test_resolve_skips_operator_and_none_disciple():
    t1 = chaos.summon("billing", "process_kill", disciple="operator")
    t2 = chaos.summon("auth", "process_kill", disciple=None)
    # neither should touch cultivation; just verify no error + scoring works
    assert chaos.resolve(t1["id"], True, recovery_seconds=10)["score"] == 100
    assert chaos.resolve(t2["id"], False)["status"] == "failed"
    assert cultivation.state("operator")["stones"] == 0


def test_resolve_unknown_id_raises_keyerror():
    with pytest.raises(KeyError):
        chaos.resolve(999, True)


def test_active_excludes_resolved():
    a = chaos.summon("billing", "process_kill")
    b = chaos.summon("auth", "latency_storm")
    chaos.resolve(a["id"], True, recovery_seconds=5)
    act = chaos.active()
    assert [t["id"] for t in act] == [b["id"]]


def test_history_newest_first_and_limit():
    for i in range(5):
        chaos.summon(f"svc{i}", "process_kill")
    hist = chaos.history(limit=3)
    assert len(hist) == 3
    assert [t["target"] for t in hist] == ["svc4", "svc3", "svc2"]


def test_status_shape():
    chaos.summon("billing", "process_kill")
    t = chaos.summon("auth", "latency_storm")
    chaos.resolve(t["id"], False)
    st = chaos.status()
    assert st["catalog"] is chaos.TRIALS
    assert st["active"] == 1
    assert isinstance(st["trials"], list) and len(st["trials"]) == 2


def test_clear_empties_state():
    chaos.summon("billing", "process_kill")
    chaos.clear()
    assert chaos.active() == []
    assert chaos.history() == []
    # ids reset after clear
    assert chaos.summon("auth", "process_kill")["id"] == 1


def test_summon_inject_requests_guarded_tool(monkeypatch):
    from maybot_control_center import tools as tooling
    calls = []
    monkeypatch.setattr(tooling, "enabled", lambda: True)
    monkeypatch.setattr(tooling, "request_tool", lambda req, tool, args: (calls.append((req, tool, args)) or {"id": 1, "status": "pending"}))
    rec = chaos.summon("daybot", "process_kill", disciple="Nova", inject=True)
    assert rec["injection"]["requested"] is True
    assert rec["injection"]["tool"] == "chaos_process_kill"
    assert calls and calls[0][0] == "Nova" and calls[0][2]["target"] == "daybot"


def test_summon_inject_noop_when_tools_disabled(monkeypatch):
    from maybot_control_center import tools as tooling
    monkeypatch.setattr(tooling, "enabled", lambda: False)
    rec = chaos.summon("daybot", "endpoint_seal", inject=True)
    assert rec["injection"]["requested"] is False


def test_summon_without_inject_does_not_touch_tools():
    rec = chaos.summon("daybot", "latency_storm")
    assert rec["injection"] is None
