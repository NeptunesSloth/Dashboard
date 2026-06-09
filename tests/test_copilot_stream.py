"""Streaming Ops Copilot — SSE event generator + the agents streaming fallback."""
from maybot_control_center import copilot, agents


OVERVIEW = {
    "summary": {"online_devices": 1, "total_devices": 1, "total_projects": 1,
                "projects_with_warnings_errors": 1, "bots_running": 0},
    "devices": [{"name": "trade-server", "online": True}],
    "projects": [
        {"name": "nightbot", "device": "trade-server", "type": "trading_bot",
         "status": "stopped", "health": "error", "alerts": ["ERROR: process expected but stopped"]},
    ],
}


def test_ask_stream_emits_meta_tokens_and_done(monkeypatch):
    monkeypatch.setattr(copilot, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})

    def fake_stream(member, messages):
        assert "nightbot" in messages[-1]["content"]      # grounded in fleet context
        for piece in ["night", "bot is ", "stopped."]:
            yield piece

    events = list(copilot.ask_stream("what needs attention?", OVERVIEW, chat_stream=fake_stream))
    assert events[0]["type"] == "meta" and events[0]["member"] == "Sage"
    assert any(a["project"] == "nightbot" for a in events[0]["actions"])
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "nightbot is stopped."
    assert events[-1]["type"] == "done"


def test_ask_stream_no_backend(monkeypatch):
    monkeypatch.setattr(copilot, "_backend_member", lambda: None)
    events = list(copilot.ask_stream("status?", OVERVIEW))
    assert events[0]["type"] == "meta" and events[0]["member"] is None
    err = next(e for e in events if e["type"] == "error")
    assert err["error"] == "no_backend" and "Sect Members" in err["answer"]


def test_ask_stream_empty_question():
    events = list(copilot.ask_stream("   ", OVERVIEW))
    assert any(e.get("error") == "empty question" for e in events)


def test_ask_stream_handles_no_output(monkeypatch):
    monkeypatch.setattr(copilot, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    events = list(copilot.ask_stream("hi", OVERVIEW, chat_stream=lambda m, msgs: iter(())))
    assert any(e["type"] == "error" and "did not respond" in e["error"] for e in events)


def test_stream_chat_falls_back_to_oneshot(monkeypatch):
    # A backend that can't stream (helper raises) must fall back to _chat's reply.
    monkeypatch.setattr(agents, "_chat", lambda agent, messages: (True, "one-shot reply", None))
    out = "".join(agents.stream_chat({"provider": "openai_compatible"}, [{"role": "user", "content": "hi"}]))
    assert out == "one-shot reply"
