import pytest

from maybot_control_center import agents


AGENTS_YAML = """
agents:
  - name: Nova
    role: Analyst
    persona: You are Nova.
    provider: openai_compatible
    base_url: http://x
    model: m
"""


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def setup_function():
    agents.clear()


def test_load_agents(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    defs = agents.load_agents()
    assert defs and defs[0]["name"] == "Nova"


def test_load_agents_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "AGENTS_FILE", tmp_path / "nope.yaml")
    assert agents.load_agents() == []


def test_run_task_records_transcript(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, "hello from nova", None))
    st = agents.run_task("Nova", "say hi")
    assert st["status"] == "idle"
    assert st["last_reply"] == "hello from nova"
    assert st["tasks_done"] == 1
    assert [m["role"] for m in st["transcript"]] == ["user", "assistant"]


def test_run_task_error_path(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (False, "", "boom"))
    st = agents.run_task("Nova", "x")
    assert st["status"] == "error"
    assert "boom" in (st["error"] or "")


def test_messages_include_persona_and_task(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    captured = {}

    def fake_chat(agent, messages):
        captured["messages"] = messages
        return True, "ok", None

    monkeypatch.setattr(agents, "_chat", fake_chat)
    agents.run_task("Nova", "do thing")
    msgs = captured["messages"]
    assert msgs[0] == {"role": "system", "content": "You are Nova."}
    assert msgs[-1] == {"role": "user", "content": "do thing"}


def test_snapshot_and_get_agent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, "ok", None))
    agents.run_task("Nova", "hi")
    snap = agents.snapshot()
    assert snap[0]["name"] == "Nova"
    assert snap[0]["tasks_done"] == 1
    assert snap[0]["transcript_len"] == 2
    full = agents.get_agent("Nova")
    assert full["persona"] == "You are Nova."
    assert len(full["transcript"]) == 2


def test_unknown_agent_raises(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(KeyError):
        agents.run_task("Ghost", "x")
    assert agents.get_agent("Ghost") is None


def test_transcript_is_capped(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, "r", None))
    for i in range(agents.MAX_TURNS * 2 + 5):
        agents.run_task("Nova", f"t{i}")
    assert len(agents.get_agent("Nova")["transcript"]) <= agents.MAX_TURNS * 2
