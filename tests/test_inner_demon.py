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
    crit_calls = {"n": 0}

    def fake_chat(agent, messages):
        if "Inner Demon" in messages[0]["content"]:
            crit_calls["n"] += 1
            return True, ("- wrong about X" if crit_calls["n"] == 1 else "NO FLAWS"), None
        return True, ("corrected final answer" if crit_calls["n"] else "first draft (flawed)"), None

    monkeypatch.setattr(agents, "_chat", fake_chat)
    st = agents.run_task("Nova", "do the thing")
    assert st["last_reply"] == "corrected final answer"  # demon caught a flaw → disciple revised
    assert any(m["role"] == "system" and "inner demon" in m["content"] for m in st["transcript"])


def test_demon_cycles_scale_inversely_with_realm():
    # harshest (most cycles) when the disciple is weakest
    assert agents._demon_cycles(0) == 3
    assert agents._demon_cycles(2) == 2
    assert agents._demon_cycles(4) == 1
    assert agents._demon_cycles(6) == 0


def test_low_realm_disciple_gets_multiple_critique_cycles(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)  # Nova has no cultivation state → realm 0 → 3 cycles
    critiques = []

    def fake_chat(agent, messages):
        if "Inner Demon" in messages[0]["content"]:
            critiques.append(1)
            return True, "- still flawed", None  # never satisfied
        return True, "draft", None

    monkeypatch.setattr(agents, "_chat", fake_chat)
    agents.run_task("Nova", "do the thing")
    assert len(critiques) == 3  # realm 0 → three critique→revise cycles


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
