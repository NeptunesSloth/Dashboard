import pytest

from maybot_control_center import agents, comms, formations, cultivation


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
    cultivation.clear()


# ---- catalog ----
def test_default_catalog_has_recon_array():
    names = [f["name"] for f in formations.catalog()]
    assert "recon-array" in names
    recon = formations.get("recon-array")
    assert [s["name"] for s in recon["stages"]] == ["scout", "analyze", "propose", "review"]


def test_catalog_loads_from_file(tmp_path, monkeypatch):
    f = tmp_path / "formations.yaml"
    f.write_text(
        "formations:\n"
        "  - name: solo\n"
        "    stages:\n"
        "      - {name: think, role: ponder, agent: Nova}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(formations, "FORMATIONS_FILE", f)
    cat = formations.catalog()
    assert [c["name"] for c in cat] == ["solo"]
    assert cat[0]["stages"][0]["agent"] == "Nova"


def test_get_unknown_is_none():
    assert formations.get("no-such-array") is None


# ---- run ----
def test_run_formation_runs_stages_in_order(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, f"out-{agent['name']}", None))
    stages = [
        {"name": "scout", "role": "look", "assignee": "Nova"},
        {"name": "review", "role": "judge", "assignee": "Forge"},
    ]
    comms.run_formation("recon-array", "ship it", stages, mission_id=1)
    feed = comms.get_feed()
    agent_msgs = [m for m in feed if m["kind"] == "agent"]
    assert [m["from"] for m in agent_msgs] == ["Nova", "Forge"]
    assert "【scout】" in agent_msgs[0]["content"]
    assert feed[-1]["from"] == "system" and "disperses" in feed[-1]["content"]
    assert comms.status()["active"] is False


def test_run_formation_records_errors(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (False, "", "down"))
    stages = [{"name": "scout", "role": "look", "assignee": "Nova"}]
    comms.run_formation("a", "g", stages, mission_id=2)
    bodies = [m["content"] for m in comms.get_feed() if m["kind"] == "agent"]
    assert any("error: down" in b for b in bodies)


# ---- start (validation + assignment) ----
def test_start_formation_assigns_round_robin(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)
    snap = comms.start_formation("recon-array", "investigate the outage")
    assert snap["kind"] == "formation"
    assert snap["formation"] == "recon-array"
    # 4 stages across 2 agents → both fill stages, deduped in participants
    assert set(snap["participants"]) == {"Nova", "Forge"}
    assert comms.status()["active"] is True


def test_start_formation_validates(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        comms.start_formation("recon-array", "")        # empty goal
    with pytest.raises(ValueError):
        comms.start_formation("ghost-array", "goal")    # unknown formation


def test_start_formation_rejects_concurrent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)
    comms.start_formation("recon-array", "goal")
    with pytest.raises(RuntimeError):
        comms.start_formation("triage-array", "goal")
