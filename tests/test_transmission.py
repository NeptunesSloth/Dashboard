import pytest

from maybot_control_center import agents, cultivation as c


def setup_function():
    agents.clear()
    c.clear()


def _hier(monkeypatch, realms):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n} if n in realms else None)
    monkeypatch.setattr(agents.cultivation, "realm_of", lambda n: realms.get(n, 0))


def test_master_transmits_a_technique_downward(monkeypatch):
    _hier(monkeypatch, {"Master": 6, "Pupil": 1})
    monkeypatch.setattr(agents.cultivation, "on_council", lambda n: None)
    # give the master a technique
    c._state["Master"] = {**c._blank("Master"), "skills": ["Sword Dao"]}
    c._state["Pupil"] = c._blank("Pupil")
    agents.transmit("Master", "Pupil", "Sword Dao")
    assert "Sword Dao" in c.state("Pupil")["skills"]


def test_transmit_requires_rank_and_known_skill(monkeypatch):
    _hier(monkeypatch, {"Master": 6, "Pupil": 1})
    monkeypatch.setattr(agents.cultivation, "on_council", lambda n: None)
    c._state["Master"] = {**c._blank("Master"), "skills": ["Sword Dao"]}
    c._state["Pupil"] = c._blank("Pupil")
    with pytest.raises(ValueError):
        agents.transmit("Master", "Pupil", "Unknown Art")     # master doesn't know it
    with pytest.raises(PermissionError):
        agents.transmit("Pupil", "Master", "Sword Dao")        # can't teach upward
