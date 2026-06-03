import pytest

from maybot_control_center import council_vote


def setup_function():
    council_vote.clear()


def test_weighted_winner_beats_simple_majority():
    # Two low-weight voters for A, one high-weight voter for B -> B wins.
    votes = {"a1": "A", "a2": "A", "b1": "B"}
    weights = {"a1": 1.0, "a2": 1.0, "b1": 5.0}
    r = council_vote.tally("which path?", votes, weights)
    assert r["winner"] == "B"
    assert r["tally"] == {"A": 2.0, "B": 5.0}
    assert r["dissent"] == ["a1", "a2"]
    assert r["weighted"] is True


def test_tie_break_highest_weight_then_alphabetical():
    # Equal totals (3 vs 3). Tie-break: highest single weight wins -> "Z".
    votes = {"x": "A", "y": "A", "z": "Z"}
    weights = {"x": 1.5, "y": 1.5, "z": 3.0}
    r = council_vote.tally("q", votes, weights)
    assert r["tally"] == {"A": 3.0, "Z": 3.0}
    assert r["winner"] == "Z"


def test_tie_break_alphabetical_when_weights_equal():
    # Totals tie and the per-choice max weights also tie -> alphabetical "A".
    votes = {"x": "A", "y": "B"}
    weights = {"x": 2.0, "y": 2.0}
    r = council_vote.tally("q", votes, weights)
    assert r["winner"] == "A"


def test_missing_and_negative_weights_count_as_zero():
    votes = {"a": "A", "b": "B", "c": "A"}
    weights = {"a": -3.0, "c": 0.0}  # b missing, a negative, c zero
    r = council_vote.tally("q", votes, weights)
    assert r["weights"] == {"a": 0.0, "b": 0.0, "c": 0.0}
    assert r["tally"] == {"A": 0.0, "B": 0.0}
    # all-zero totals -> alphabetical winner
    assert r["winner"] == "A"
    assert r["dissent"] == ["b"]


def test_dissent_lists_all_non_winners():
    votes = {"a": "X", "b": "Y", "c": "X", "d": "Z"}
    weights = {"a": 3.0, "b": 1.0, "c": 3.0, "d": 1.0}
    r = council_vote.tally("q", votes, weights)
    assert r["winner"] == "X"
    assert r["dissent"] == ["b", "d"]


def test_blank_question_raises():
    with pytest.raises(ValueError):
        council_vote.tally("", {"a": "A"}, {"a": 1.0})
    with pytest.raises(ValueError):
        council_vote.tally("   ", {"a": "A"}, {"a": 1.0})


def test_empty_votes_raises():
    with pytest.raises(ValueError):
        council_vote.tally("q", {}, {})


def test_weighted_flag_false_when_all_weights_one():
    votes = {"a": "A", "b": "B"}
    weights = {"a": 1.0, "b": 1.0}
    r = council_vote.tally("q", votes, weights)
    assert r["weighted"] is False


def test_weighted_flag_true_when_weights_omitted(monkeypatch):
    import maybot_control_center
    import maybot_control_center.council_vote as cv

    class FakeGov:
        @staticmethod
        def standing(agent):
            return {"agent": agent, "score": 1.0, "components": {}}

    # even with uniform standing, omitting weights flags the vote as weighted
    monkeypatch.setattr(maybot_control_center, "governance", FakeGov, raising=False)
    r = cv.tally("q", {"a": "A", "b": "B"})
    assert r["weighted"] is True


def test_history_accumulates_newest_last_and_clear():
    council_vote.tally("first", {"a": "A"}, {"a": 1.0})
    council_vote.tally("second", {"a": "A"}, {"a": 1.0})
    h = council_vote.history()
    assert [r["question"] for r in h] == ["first", "second"]
    council_vote.clear()
    assert council_vote.history() == []


def test_history_is_capped():
    for i in range(council_vote.HISTORY_CAP + 25):
        council_vote.tally(f"q{i}", {"a": "A"}, {"a": 1.0})
    h = council_vote.history(limit=1000)
    assert len(h) == council_vote.HISTORY_CAP
    # newest survive, oldest evicted
    assert h[-1]["question"] == f"q{council_vote.HISTORY_CAP + 24}"


def test_history_returns_copies():
    council_vote.tally("q", {"a": "A"}, {"a": 1.0})
    h = council_vote.history()
    h[0]["tally"]["A"] = 999
    h[0]["dissent"].append("hacker")
    assert council_vote.history()[0]["tally"] == {"A": 1.0}
    assert council_vote.history()[0]["dissent"] == []


def test_governance_weighted_default_path(monkeypatch):
    # Exercise the lazy governance.standing() default-weight path.
    import maybot_control_center
    import maybot_control_center.council_vote as cv

    scores = {"elder": 9.0, "junior": 1.0}

    class FakeGov:
        @staticmethod
        def standing(agent):
            return {"agent": agent, "score": scores[agent], "components": {}}

    monkeypatch.setattr(maybot_control_center, "governance", FakeGov, raising=False)

    # junior + another junior vote A; the high-standing elder votes B -> B wins.
    votes = {"junior": "A", "elder": "B"}
    r = cv.tally("ambiguous call", votes)  # no explicit weights
    assert r["weights"] == {"junior": 1.0, "elder": 9.0}
    assert r["winner"] == "B"
    assert r["weighted"] is True


def test_governance_failure_defaults_to_one(monkeypatch):
    import maybot_control_center
    import maybot_control_center.council_vote as cv

    class FakeGov:
        @staticmethod
        def standing(agent):
            raise RuntimeError("standing unavailable")

    monkeypatch.setattr(maybot_control_center, "governance", FakeGov, raising=False)
    r = cv.tally("q", {"a": "A", "b": "B"})
    assert r["weights"] == {"a": 1.0, "b": 1.0}
