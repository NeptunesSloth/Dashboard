from maybot_control_center import reputation, cultivation, autonomy


def setup_function():
    cultivation.clear()
    autonomy.clear()


def _calls(requester, done=0, failed=0, denied=0):
    rows = []
    rows += [{"requester": requester, "status": "done"}] * done
    rows += [{"requester": requester, "status": "failed"}] * failed
    rows += [{"requester": requester, "status": "denied"}] * denied
    return rows


def test_fresh_disciple_is_standard(monkeypatch):
    monkeypatch.setattr(reputation, "_tool_stats", lambda a: {"done": 0, "failed": 0, "denied": 0})
    s = reputation.score("Nova")
    # 40 base + (100-50)*0.4 = 60 with no realm/tools → Standard
    assert s["merit"] == 60
    assert s["tier"] == "Standard"
    assert s["agent"] == "Nova"


def test_reliable_disciple_becomes_trusted(monkeypatch):
    monkeypatch.setattr(reputation, "_tool_stats", lambda a: {"done": 10, "failed": 0, "denied": 0})
    cultivation.on_tool("Nova", "scan", True)  # earn realm progress + a skill
    s = reputation.score("Nova")
    assert s["tier"] == "Trusted"
    assert reputation.autonomy_bonus("Nova") == reputation.TRUSTED_BONUS


def test_denied_calls_demote_to_probation(monkeypatch):
    monkeypatch.setattr(reputation, "_tool_stats", lambda a: {"done": 0, "failed": 0, "denied": 4})
    s = reputation.score("Rogue")
    # 60 - 4*6 = 36 < 45 → Probation
    assert s["tier"] == "Probation"
    assert reputation.is_probation("Rogue") is True


def test_probation_blocks_autonomy(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(reputation, "is_probation", lambda a: True)
    tool = {"name": "scan", "auto_approve": True, "max_auto_per_task": 5}
    assert autonomy.allow("Rogue", tool) is False


def test_trusted_adds_autonomy_budget(monkeypatch):
    monkeypatch.setattr(autonomy, "ENABLED", True)
    monkeypatch.setattr(reputation, "is_probation", lambda a: False)
    monkeypatch.setattr(reputation, "autonomy_bonus", lambda a: 2)
    tool = {"name": "scan", "auto_approve": True, "max_auto_per_task": 1}
    # base 1 + bonus 2 = 3 auto-runs before approval is required
    assert sum(autonomy.allow("Nova", tool) for _ in range(5)) == 3


def test_snapshot_covers_loaded_agents(monkeypatch):
    monkeypatch.setattr(reputation, "_tool_stats", lambda a: {"done": 0, "failed": 0, "denied": 0})
    snap = reputation.snapshot()
    assert isinstance(snap, dict)
    for name, rep in snap.items():
        assert rep["agent"] == name
        assert 0 <= rep["merit"] <= 100
        assert rep["tier"] in ("Trusted", "Standard", "Probation")
