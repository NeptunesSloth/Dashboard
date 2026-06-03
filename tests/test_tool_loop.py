from maybot_control_center import agents, tools


AGENTS_YAML = """
agents:
  - {name: Nova, persona: You are Nova., provider: openai_compatible, base_url: http://x, model: m}
"""


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def setup_function():
    agents.clear()
    tools.clear()


def test_tool_completion_feeds_back_to_agent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # capture follow-up tasks instead of running them on the pool
    runs = []
    monkeypatch.setattr(agents._pool, "submit", lambda fn, name, task: runs.append((name, task)))
    agents._followups["Nova"] = 0
    agents._tool_followup({"requester": "Nova", "tool": "say", "status": "done", "output": "RESULT"})
    assert len(runs) == 1
    assert runs[0][0] == "Nova" and "RESULT" in runs[0][1]


def test_followup_respects_cap(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    runs = []
    monkeypatch.setattr(agents._pool, "submit", lambda fn, name, task: runs.append(task))
    monkeypatch.setattr(agents, "MAX_FOLLOWUPS", 2)
    agents._followups["Nova"] = 0
    for _ in range(5):
        agents._tool_followup({"requester": "Nova", "tool": "t", "status": "done", "output": "o"})
    assert len(runs) == 2  # capped


def test_operator_requester_does_not_loop(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    runs = []
    monkeypatch.setattr(agents._pool, "submit", lambda *a: runs.append(a))
    agents._tool_followup({"requester": "operator", "tool": "t", "status": "done", "output": "o"})
    assert runs == []  # operator runs don't trigger an agent continuation
