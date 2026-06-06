"""Offline tests for the Sect Advisor.

These run with no ANTHROPIC_API_KEY, no network, and no ``anthropic`` package,
so the advisor must always take the strong local templated path.
"""
from maybot_control_center import advisor


def _sample_snapshot() -> dict:
    """A realistic Command Hall snapshot (mirrors command.snapshot() demo shape)."""
    return {
        "greeting_name": "Sect Master",
        "monthly_goal": 10000.0,
        "account_base": 0.0,
        "demo": True,
        "pnl": {"today": 642.38, "week": 1814.22, "month": 7382.41, "total": 42182.15},
        "positions": [
            {"ticker": "NVDA", "side": "LONG", "qty": 40, "pnl": 266.00, "pnl_pct": 5.63},
            {"ticker": "META", "side": "LONG", "qty": 18, "pnl": 327.60, "pnl_pct": 3.76},
            {"ticker": "AMD", "side": "LONG", "qty": 60, "pnl": -201.00, "pnl_pct": -2.06},
        ],
        "bots": [
            {"name": "Momentum Alpha", "pnl_today": 418.20, "win_rate": 73, "status": "active"},
            {"name": "Vol Harvest", "pnl_today": -27.78, "win_rate": 58, "status": "throttled"},
        ],
        "opportunities": [
            {"ticker": "META", "edge": 4.3, "confidence": 96, "status": "EXECUTE"},
            {"ticker": "NVDA", "edge": 2.1, "confidence": 84, "status": "WATCHING"},
        ],
        "events": [
            {"icon": "🧠", "kind": "autopilot", "text": "Rebalanced exposure", "ts": 1},
        ],
    }


def test_available_reports_no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    info = advisor.available()
    assert info["llm"] is False
    # Model default is the env default, never hardcoded opus.
    assert info["model"] == "claude-sonnet-4-6"


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("MAYBOT_ADVISOR_MODEL", "claude-haiku-4-5")
    assert advisor.available()["model"] == "claude-haiku-4-5"


def test_summary_local_path(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = advisor.summary(_sample_snapshot())

    assert out["source"] == "local"
    assert isinstance(out["text"], str) and out["text"].strip()
    assert out["highlights"] and all(isinstance(h, str) for h in out["highlights"])
    assert out["suggestions"] and all(isinstance(s, str) for s in out["suggestions"])

    blob = (out["text"] + " " + " ".join(out["highlights"] + out["suggestions"]))
    # The briefing should reflect real snapshot facts.
    assert "AMD" in blob          # the losing position is flagged
    assert "Vol Harvest" in blob  # the throttled/down bot is flagged
    assert "Sect Master" in out["text"]


def test_summary_handles_empty_snapshot(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = advisor.summary({})
    assert out["source"] == "local"
    assert out["text"].strip()
    assert out["highlights"]
    assert out["suggestions"]
