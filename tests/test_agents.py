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
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"].startswith("You are Nova.")
    assert "Ancestor" in msgs[0]["content"]  # sect persona context is appended
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


class _Block:
    def __init__(self, type, text=None):
        self.type = type
        self.text = text


class _Resp:
    content = [_Block("text", "hello from claude")]


class _FakeMessages:
    def __init__(self, store):
        self.store = store

    def create(self, **kwargs):
        self.store.update(kwargs)
        return _Resp()


class _FakeClient:
    def __init__(self, store):
        self.messages = _FakeMessages(store)


def test_chat_claude_splits_system_and_omits_sampling(monkeypatch):
    store = {}
    monkeypatch.setattr(agents, "_anthropic_client", lambda: _FakeClient(store))
    agent = {"name": "Cy", "provider": "claude", "model": "claude-opus-4-8",
             "persona": "You are Cy.", "max_tokens": 256}
    msgs = [
        {"role": "system", "content": "You are Cy."},
        {"role": "user", "content": "hi"},
    ]
    ok, text, err = agents._chat(agent, msgs)
    assert ok and err is None and text == "hello from claude"
    # system is split out with a cache breakpoint; conversation excludes the system turn
    assert store["model"] == "claude-opus-4-8"
    assert store["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert store["messages"] == [{"role": "user", "content": "hi"}]
    # Opus 4.8 rejects sampling params — make sure none are sent
    assert "temperature" not in store and "top_p" not in store and "top_k" not in store


def test_claude_provider_routes_through_claude(monkeypatch):
    called = {}
    monkeypatch.setattr(agents, "_chat_claude", lambda agent, messages: (called.setdefault("hit", True), "x", None))
    agents._chat({"provider": "anthropic"}, [{"role": "user", "content": "y"}])
    assert called.get("hit") is True


def test_transcript_is_capped(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, "r", None))
    for i in range(agents.MAX_TURNS * 2 + 5):
        agents.run_task("Nova", f"t{i}")
    assert len(agents.get_agent("Nova")["transcript"]) <= agents.MAX_TURNS * 2
