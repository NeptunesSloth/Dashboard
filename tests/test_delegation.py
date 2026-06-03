import pytest

from maybot_control_center import agents


def setup_function():
    agents.clear()


def _hierarchy(monkeypatch, realms):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n} if n in realms else None)
    monkeypatch.setattr(agents.cultivation, "realm_of", lambda n: realms.get(n, 0))


def test_can_delegate_only_downward(monkeypatch):
    _hierarchy(monkeypatch, {"Master": 8, "Elder": 6, "Outer": 0})
    # Sect Master → everyone
    assert agents.can_delegate("Master", "Elder") is True
    assert agents.can_delegate("Master", "Outer") is True
    # Elder → only those below
    assert agents.can_delegate("Elder", "Outer") is True
    assert agents.can_delegate("Elder", "Master") is False   # never upward
    # peers and bottom-rank
    assert agents.can_delegate("Outer", "Elder") is False
    assert agents.can_delegate("Master", "Master") is False
    assert agents.can_delegate("Master", "Ghost") is False   # unknown


def test_subordinates_lists_lower_ranks(monkeypatch, tmp_path):
    f = tmp_path / "agents.yaml"
    f.write_text("agents:\n  - {name: Master}\n  - {name: Elder}\n  - {name: Outer}\n", encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)
    monkeypatch.setattr(agents.cultivation, "realm_of", lambda n: {"Master": 8, "Elder": 6, "Outer": 0}.get(n, 0))
    assert set(agents.subordinates("Master")) == {"Elder", "Outer"}
    assert agents.subordinates("Elder") == ["Outer"]
    assert agents.subordinates("Outer") == []


def test_delegate_enforces_rank_and_frames_task(monkeypatch):
    _hierarchy(monkeypatch, {"Master": 8, "Outer": 0})
    assigned = {}
    monkeypatch.setattr(agents, "assign_task", lambda to, task: assigned.update(to=to, task=task) or {"status": "queued"})
    monkeypatch.setattr(agents.cultivation, "on_council", lambda n: None)
    agents.delegate("Master", "Outer", "investigate the fallen realm")
    assert assigned["to"] == "Outer"
    assert "Delegated by Master" in assigned["task"] and "investigate" in assigned["task"]
    with pytest.raises(PermissionError):
        agents.delegate("Outer", "Master", "do my chores")  # cannot delegate upward
