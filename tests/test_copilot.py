"""Ops Copilot — fleet-wide natural-language Q&A grounded in live state."""
from maybot_control_center import copilot


OVERVIEW = {
    "summary": {"online_devices": 1, "total_devices": 2, "total_projects": 2,
                "projects_with_warnings_errors": 1, "bots_running": 1},
    "devices": [{"name": "trade-server", "online": True}, {"name": "old-box", "online": False}],
    "projects": [
        {"name": "daybot", "device": "trade-server", "type": "trading_bot",
         "status": "running", "health": "ok", "alerts": []},
        {"name": "nightbot", "device": "trade-server", "type": "trading_bot",
         "status": "stopped", "health": "error", "alerts": ["ERROR: process expected but stopped"]},
    ],
}


def test_build_context_mentions_fleet_and_bots():
    ctx = copilot.build_context(OVERVIEW)
    assert "1/2 hosts online" in ctx
    assert "old-box" in ctx and "nightbot" in ctx


def test_suggested_actions_target_stopped_bot():
    acts = copilot._suggested_actions(OVERVIEW["projects"])
    assert acts == [{"kind": "start", "device": "trade-server", "project": "nightbot",
                     "label": "Start nightbot on trade-server"}]


def test_ask_uses_injected_chat_and_returns_answer(monkeypatch):
    monkeypatch.setattr(copilot, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    seen = {}

    def fake_chat(member, messages):
        seen["ctx"] = messages[-1]["content"]
        return True, "nightbot is stopped — restart it.", None

    r = copilot.ask("what needs attention?", OVERVIEW, chat=fake_chat)
    assert r["answer"] == "nightbot is stopped — restart it."
    assert r["member"] == "Sage" and r["error"] is None
    assert "nightbot" in seen["ctx"]                      # grounded in fleet context
    assert any(a["project"] == "nightbot" for a in r["actions"])


def test_ask_without_backend_is_graceful(monkeypatch):
    monkeypatch.setattr(copilot, "_backend_member", lambda: None)
    r = copilot.ask("status?", OVERVIEW)
    assert r["error"] == "no_backend" and "Sect Members" in r["answer"]
    # Still offers the deterministic remediation even with no LLM.
    assert r["actions"]


def test_ask_empty_question():
    assert copilot.ask("   ", OVERVIEW)["error"] == "empty question"
