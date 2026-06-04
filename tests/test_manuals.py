from maybot_control_center import manuals, artifacts, agents, governance


def setup_function():
    manuals.clear()
    artifacts.clear()


def _elder(name="Sage", status="idle", skills=("api_design",), in_seclusion=False):
    return {"name": name, "status": status,
            "governance": {"is_elder": True, "specialty": "Sword Dao"},
            "cultivation": {"skills": list(skills), "in_seclusion": in_seclusion, "in_roaming": False}}


def _patch(monkeypatch, subs=()):
    monkeypatch.setattr(agents, "subordinates", lambda n: list(subs))
    monkeypatch.setattr(governance, "specialty", lambda n: "Sword Dao")
    monkeypatch.setattr(governance, "specialty_skill", lambda n: "api_design")


def test_idle_elder_without_disciples_authors_manual(monkeypatch):
    _patch(monkeypatch)
    forged = manuals.tick([_elder()], now=1000)
    assert len(forged) == 1
    cat = artifacts.catalog()
    assert cat and cat[0]["kind"] == "manual" and cat[0]["creator"] == "Sage"


def test_non_elder_skipped(monkeypatch):
    _patch(monkeypatch)
    row = _elder()
    row["governance"]["is_elder"] = False
    assert manuals.tick([row], now=1000) == []


def test_busy_elder_skipped(monkeypatch):
    _patch(monkeypatch)
    assert manuals.tick([_elder(status="working")], now=1000) == []


def test_elder_with_disciples_skipped(monkeypatch):
    _patch(monkeypatch, subs=["Junior"])
    assert manuals.tick([_elder()], now=1000) == []


def test_seclusion_skipped(monkeypatch):
    _patch(monkeypatch)
    assert manuals.tick([_elder(in_seclusion=True)], now=1000) == []


def test_cooldown_prevents_repeat(monkeypatch):
    _patch(monkeypatch)
    assert len(manuals.tick([_elder(skills=("api_design", "refactoring"))], now=1000)) == 1
    # within cooldown → no new manual even though another skill is undocumented
    assert manuals.tick([_elder(skills=("api_design", "refactoring"))], now=1000 + 10) == []
    # after cooldown → authors the next undocumented skill
    assert len(manuals.tick([_elder(skills=("api_design", "refactoring"))], now=1000 + manuals.COOLDOWN + 1)) == 1


def test_no_undocumented_skill_after_all_written(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(governance, "specialty_skill", lambda n: None)
    manuals.tick([_elder(skills=("api_design",))], now=1000)
    # only skill already has a manual → nothing new even past cooldown
    assert manuals.tick([_elder(skills=("api_design",))], now=1000 + manuals.COOLDOWN + 1) == []
