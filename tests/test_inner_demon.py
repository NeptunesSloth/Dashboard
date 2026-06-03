from maybot_control_center import agents


AGENTS_YAML = """
agents:
  - {name: Nova, persona: You are Nova., provider: openai_compatible, base_url: http://x, model: m, inner_demon: true}
"""


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def setup_function():
    agents.clear()


def test_inner_demon_revises_a_flawed_answer(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    calls = []

    def fake_chat(agent, messages):
        sys = messages[0]["content"]
        calls.append(sys)
        if "Inner Demon" in sys:
            return True, "- the answer is wrong about X", None      # critique with flaws
        if len(calls) == 1:
            return True, "first draft (flawed)", None               # initial answer
        return True, "corrected final answer", None                  # revision

    monkeypatch.setattr(agents, "_chat", fake_chat)
    st = agents.run_task("Nova", "do the thing")
    assert st["last_reply"] == "corrected final answer"
    # initial answer + critique + revision = 3 model calls
    assert len(calls) == 3
    # the critique was recorded in the transcript
    assert any(m["role"] == "system" and "inner demon" in m["content"] for m in st["transcript"])


def test_inner_demon_keeps_answer_when_no_flaws(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    def fake_chat(agent, messages):
        if "Inner Demon" in messages[0]["content"]:
            return True, "NO FLAWS", None
        return True, "a solid answer", None

    monkeypatch.setattr(agents, "_chat", fake_chat)
    st = agents.run_task("Nova", "do the thing")
    assert st["last_reply"] == "a solid answer"
    assert not any(m["role"] == "system" and "inner demon" in m["content"] for m in st["transcript"])
