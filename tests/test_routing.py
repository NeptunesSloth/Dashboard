from maybot_control_center import routing, governance, cultivation, reputation, taskqueue


def setup_function():
    taskqueue.clear()


def test_specialties_for_goal():
    assert "Sword Dao" in routing._specialties_for_goal("refactor the backend api")
    assert "Talisman Crafting" in routing._specialties_for_goal("redesign the frontend UI")
    assert "Beast Taming" in routing._specialties_for_goal("add test coverage and hunt the flaky bug")
    assert routing._specialties_for_goal("xyzzy") == set()


def _stub_fleet(monkeypatch, specialties):
    """specialties: {name: specialty_or_None}."""
    monkeypatch.setattr("maybot_control_center.agents.load_agents",
                        lambda: [{"name": n} for n in specialties])
    monkeypatch.setattr(governance, "specialty", lambda n: specialties[n])
    monkeypatch.setattr(governance, "mastery", lambda n: 50.0)
    monkeypatch.setattr(governance, "standing", lambda n: {"score": 60.0})
    monkeypatch.setattr(cultivation, "realm_of", lambda n: 3)
    monkeypatch.setattr(cultivation, "state",
                        lambda n: {"in_seclusion": False, "in_roaming": False})
    monkeypatch.setattr(reputation, "is_probation", lambda n: False)


def test_best_fit_prefers_specialty_match(monkeypatch):
    _stub_fleet(monkeypatch, {"Nova": "Sword Dao", "Quill": "Talisman Crafting"})
    fit = routing.best_fit("refactor the backend api for performance")
    assert fit["agent"] == "Nova"   # Sword Dao matches "backend api"
    assert "Sword Dao" in fit["matched_specialties"]


def test_load_penalty_spreads_work(monkeypatch):
    _stub_fleet(monkeypatch, {"Nova": "Sword Dao", "Forge": "Sword Dao"})
    # Both match; pile active tasks on Nova so Forge wins on load.
    for _ in range(3):
        taskqueue.create("busywork", assignee="Nova")
    fit = routing.best_fit("optimize the api server")
    assert fit["agent"] == "Forge"


def test_ineligible_skipped(monkeypatch):
    _stub_fleet(monkeypatch, {"Nova": "Sword Dao", "Forge": "Sword Dao"})
    monkeypatch.setattr(cultivation, "state",
                        lambda n: {"in_seclusion": n == "Nova", "in_roaming": False})
    fit = routing.best_fit("api work")
    assert fit["agent"] == "Forge"   # Nova is in seclusion


def test_none_when_all_ineligible(monkeypatch):
    _stub_fleet(monkeypatch, {"Nova": "Sword Dao"})
    monkeypatch.setattr(reputation, "is_probation", lambda n: True)
    assert routing.best_fit("api work") is None
