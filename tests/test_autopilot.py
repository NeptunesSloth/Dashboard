import pytest

from maybot_control_center import autopilot, oaths, maintenance, governance


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    autopilot.clear()
    oaths.clear()
    maintenance.clear()
    monkeypatch.setattr(autopilot, "ENABLED", True)
    monkeypatch.setattr(autopilot, "STATES", {"error"})
    monkeypatch.setattr(autopilot, "MAXATTEMPTS", 3)
    monkeypatch.setattr(governance, "leader", lambda: "Nova")
    # deterministic diagnosis + action (no LLM / network)
    monkeypatch.setattr(autopilot, "_diagnose", lambda leader, p: {"cause": "boom", "action": "restart", "summary": "s", "by": leader})
    monkeypatch.setattr(autopilot, "_perform_action", lambda p, plan, coder=None: "restarted the bot")
    reports = []
    monkeypatch.setattr(autopilot, "_report", lambda kind, t, m, by: reports.append((kind, t)))
    return reports


def _err(name="bot", health="error", status="stopped"):
    return {"name": name, "device": "prod-1", "health": health, "status": status, "type": "trading_bot", "alerts": []}


def test_disabled_does_nothing(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "ENABLED", False)
    assert autopilot.handle([_err()]) == []


def test_paused_does_nothing(_reset):
    autopilot.set_paused(True)
    assert autopilot.handle([_err()]) == []


def test_no_leader_does_nothing(monkeypatch, _reset):
    monkeypatch.setattr(governance, "leader", lambda: None)
    assert autopilot.handle([_err()]) == []


def test_detect_and_fix(_reset):
    out = autopilot.handle([_err()])
    assert out == [("prod-1:bot", "restart")]
    assert oaths.is_claimed("prod-1", "bot") is True          # Leader swore an oath
    kinds = [k for k, _ in _reset]
    assert "detected" in kinds and "fix" in kinds


def test_recovery_clears_and_reports(_reset):
    autopilot.handle([_err()])                                # open incident
    _reset.clear()
    out = autopilot.handle([_err(health="ok", status="running")])
    assert out == [("prod-1:bot", "recovered")]
    assert oaths.is_claimed("prod-1", "bot") is False
    assert [k for k, _ in _reset] == ["recovered"]


def test_silenced_skipped(_reset):
    maintenance.silence("prod-1:bot", minutes=60)
    assert autopilot.handle([_err()]) == []
    assert oaths.is_claimed("prod-1", "bot") is False


def test_escalates_after_max_attempts(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "MAXATTEMPTS", 2)
    autopilot.handle([_err()])   # attempt 1
    autopilot.handle([_err()])   # attempt 2
    out = autopilot.handle([_err()])  # now escalate
    assert out == [("prod-1:bot", "escalated")]
    assert "escalated" in [k for k, _ in _reset]
    # once escalated, it stops acting until recovery
    assert autopilot.handle([_err()]) == []


def test_allowlist_skips_unlisted(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "ALLOW", {"prod-1:other"})
    assert autopilot.handle([_err()]) == []          # bot not on the allowlist
    monkeypatch.setattr(autopilot, "ALLOW", {"prod-1:bot"})
    assert autopilot.handle([_err()]) == [("prod-1:bot", "restart")]


def test_restart_loop_circuit_breaker(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "MAXATTEMPTS", 99)   # isolate the restart breaker
    monkeypatch.setattr(autopilot, "RESTART_LIMIT", 2)
    monkeypatch.setattr(autopilot, "RESTART_WINDOW", 100000)
    autopilot.handle([_err()])   # restart 1
    autopilot.handle([_err()])   # restart 2
    out = autopilot.handle([_err()])  # would be 3rd → circuit opens
    assert out == [("prod-1:bot", "circuit_open")]
    assert "escalated" in [k for k, _ in _reset]


def test_postmortem_written_on_recovery(monkeypatch, _reset):
    from maybot_control_center import artifacts
    artifacts.clear()
    autopilot.handle([_err()])                               # acts (records an action)
    autopilot.handle([_err(health="ok", status="running")])  # recovery → postmortem
    notes = [a for a in artifacts.catalog() if a["kind"] == "note" and a["creator"] == "Autopilot"]
    assert notes and "Post-incident" in notes[0]["name"]


def test_propose_mode_recommends_without_acting(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "_project_cfg", lambda d, n: {"mode": "propose"})
    acted = []
    monkeypatch.setattr(autopilot, "_perform_action", lambda p, plan, coder=None: acted.append(plan) or "x")
    out = autopilot.handle([_err()])
    assert out == [("prod-1:bot", "proposed")]
    assert acted == []                                  # nothing executed
    assert autopilot.status()["counters"]["proposals"] == 1


def test_off_mode_skips(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "_project_cfg", lambda d, n: {"mode": "off"})
    assert autopilot.handle([_err()]) == []


def test_remediation_override(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "_project_cfg", lambda d, n: {"remediation": "code"})
    seen = {}
    monkeypatch.setattr(autopilot, "_perform_action", lambda p, plan, coder=None: seen.update(plan) or "done")
    autopilot.handle([_err()])
    assert seen["action"] == "code"                     # forced by config, not the diagnosed restart


def test_counters_increment(_reset):
    autopilot.handle([_err()])                          # a fix (restart)
    autopilot.handle([_err(health="ok", status="running")])  # a recovery
    c = autopilot.status()["counters"]
    assert c["fixes"] == 1 and c["restarts"] == 1 and c["recoveries"] == 1


def test_digest(monkeypatch, _reset):
    monkeypatch.setattr(autopilot, "DIGEST_HOURS", 24)
    autopilot.handle([_err()])                          # generate some activity
    msg = autopilot.digest()
    assert msg and "fixes" in msg
    assert "digest" in [k for k, _ in _reset]


def test_status_shape(_reset):
    autopilot.handle([_err()])
    s = autopilot.status()
    assert s["enabled"] is True and s["leader"] == "Nova"
    assert s["incidents"] and s["incidents"][0]["key"] == "prod-1:bot"
    assert "counters" in s
