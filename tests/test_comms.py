import pytest

from maybot_control_center import agents, comms


AGENTS_YAML = """
agents:
  - {name: Nova, role: Analyst, persona: You are Nova., provider: openai_compatible, base_url: http://x, model: m}
  - {name: Forge, role: Builder, persona: You are Forge., provider: openai_compatible, base_url: http://x, model: m}
"""


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def setup_function():
    comms.clear()
    agents.clear()


def test_run_mission_round_robins_all_agents(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, f"msg from {agent['name']}", None))
    comms.run_mission("ship it", ["Nova", "Forge"], rounds=2, mission_id=1)
    feed = comms.get_feed()
    agent_msgs = [m for m in feed if m["kind"] == "agent"]
    assert [m["from"] for m in agent_msgs] == ["Nova", "Forge", "Nova", "Forge"]
    assert feed[-1]["from"] == "system" and "complete" in feed[-1]["content"].lower()
    assert comms.status()["active"] is False


def test_run_mission_records_agent_errors(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (False, "", "endpoint down"))
    comms.run_mission("x", ["Nova", "Forge"], rounds=1, mission_id=2)
    bodies = [m["content"] for m in comms.get_feed() if m["kind"] == "agent"]
    assert all("error: endpoint down" in b for b in bodies)


def test_start_mission_validates_goal_and_participants(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        comms.start_mission("", ["Nova", "Forge"])
    with pytest.raises(ValueError):
        comms.start_mission("goal", ["Nova"])           # only one valid → too few
    with pytest.raises(ValueError):
        comms.start_mission("goal", ["Nova", "Ghost"])  # Ghost unknown → too few


def test_start_mission_dedups_and_caps_rounds(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)  # don't actually run
    snap = comms.start_mission("goal", ["Nova", "Nova", "Forge"], rounds=99)
    assert snap["participants"] == ["Nova", "Forge"]
    assert snap["rounds"] == comms.MAX_ROUNDS
    assert comms.status()["active"] is True


def test_start_mission_rejects_concurrent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)
    comms.start_mission("goal", ["Nova", "Forge"])
    with pytest.raises(RuntimeError):
        comms.start_mission("another", ["Nova", "Forge"])
