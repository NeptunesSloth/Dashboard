import pytest

from maybot_control_center import comms, agents, cultivation


def setup_function():
    comms.clear()
    agents.clear()
    cultivation.clear()


def test_run_debate_orders_sides_then_judges(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n, "persona": f"You are {n}."})

    def chat(agent, messages):
        if "impartial judge" in messages[0]["content"]:
            return True, "Winner: Alice — the clearer case.", None
        return True, f"{agent['name']} speaks", None

    monkeypatch.setattr(agents, "_chat", chat)
    comms.run_debate("is X wise", "Alice", "Bob", "Judge", 1, 1)
    feed = comms.get_feed()
    speakers = [m["from"] for m in feed if m["kind"] == "agent"]
    assert speakers == ["Alice", "Bob", "Judge"]  # FOR, AGAINST, then verdict
    assert any("Verdict" in m["content"] for m in feed)
    assert any("Alice prevails" in m["content"] for m in feed)


def test_debate_winner_parsing():
    assert comms._debate_winner("Winner: Bob, stronger evidence", "Alice", "Bob") == "Bob"
    assert comms._debate_winner("Alice clearly wins over Bob", "Alice", "Bob") == "Alice"
    assert comms._debate_winner("a draw, really", "Alice", "Bob") is None


def test_tournament_runs_a_bracket_and_crowns_a_champion(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n, "persona": f"You are {n}."})
    monkeypatch.setattr(agents.cultivation, "realm_of", lambda n: 0)
    monkeypatch.setattr(agents.cultivation, "state", lambda n: {"stones": 0})

    def chat(agent, messages):
        if "impartial judge" in messages[0]["content"]:
            return True, "Winner: Alice — stronger.", None  # Alice always wins her matches
        return True, f"{agent['name']} argues", None

    monkeypatch.setattr(agents, "_chat", chat)
    crowned = []
    monkeypatch.setattr(agents.cultivation, "reward", lambda n, s: crowned.append(n))
    monkeypatch.setattr(agents.cultivation, "on_council", lambda n: None)
    monkeypatch.setattr(agents.cultivation, "on_task", lambda n, ok: None)

    comms.run_tournament("best path", ["Alice", "Bob", "Carol", "Dan"], "Judge", 1, 1)
    feed = comms.get_feed()
    assert any("Sect Tournament" in m["content"] for m in feed)
    assert any("crowned the sect's strongest" in m["content"] for m in feed)
    assert crowned and crowned[-1] == "Alice"  # the champion was rewarded


def test_start_tournament_validates(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n} if n in ("A", "B", "J") else None)
    monkeypatch.setattr(agents.cultivation, "realm_of", lambda n: 0)
    monkeypatch.setattr(agents.cultivation, "state", lambda n: {"stones": 0})
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)
    with pytest.raises(ValueError):
        comms.start_tournament("t", ["A"], "J")            # too few entrants
    with pytest.raises(ValueError):
        comms.start_tournament("t", ["A", "B"], "Ghost")   # invalid judge
    snap = comms.start_tournament("t", ["A", "B"], "J")
    assert snap["kind"] == "tournament" and snap["participants"] == ["A", "B", "J"]


def test_start_debate_validates(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"name": n} if n in ("A", "B", "J") else None)
    monkeypatch.setattr(comms._pool, "submit", lambda *a, **k: None)
    with pytest.raises(ValueError):
        comms.start_debate("", "A", "B", "J")        # empty topic
    with pytest.raises(ValueError):
        comms.start_debate("t", "A", "A", "J")        # same debater
    with pytest.raises(ValueError):
        comms.start_debate("t", "A", "X", "J")        # X invalid
    snap = comms.start_debate("t", "A", "B", "J")
    assert snap["participants"] == ["A", "B", "J"] and snap["kind"] == "debate"
    with pytest.raises(RuntimeError):
        comms.start_debate("t2", "A", "B", "J")       # one council activity at a time
