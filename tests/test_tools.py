import sys

import pytest

from maybot_control_center import tools


ECHO = {"name": "say", "description": "echo a value", "argv": ["echo", "{x}"], "args": ["x"]}
SAFE = {"name": "ver", "description": "python version", "argv": [sys.executable, "-c", "print('hi')"], "auto_approve": True}


def _defs(monkeypatch, defs):
    monkeypatch.setattr(tools, "load_tools", lambda: defs)


def setup_function():
    tools.clear()


def test_builtins_available_without_yaml_tools(monkeypatch):
    # No operator-defined tools, but built-in read-only observability tools
    # (bot_status / bot_logs) are always available, so the channel stays on.
    _defs(monkeypatch, [])
    assert tools.enabled() is True
    assert "bot_status" in [t["name"] for t in tools.tool_summaries()]
    # an undefined yaml tool is still rejected
    with pytest.raises(ValueError):
        tools.request_tool("op", "say", {"x": "ok"})


def test_unknown_tool_rejected(monkeypatch):
    _defs(monkeypatch, [ECHO])
    with pytest.raises(ValueError):
        tools.request_tool("op", "not_a_tool", {})


def test_pending_call_does_not_execute(monkeypatch):
    _defs(monkeypatch, [ECHO])
    call = tools.request_tool("Nova", "say", {"x": "hello"})
    assert call["status"] == "pending"
    assert call["output"] is None
    # nothing ran until approved
    assert tools.list_calls()[-1]["status"] == "pending"


def test_approve_executes(monkeypatch):
    _defs(monkeypatch, [ECHO])
    call = tools.request_tool("Nova", "say", {"x": "hello"})
    done = tools.approve(call["id"])
    assert done["status"] == "done"
    assert done["code"] == 0
    assert "hello" in done["output"]


def test_deny_blocks_execution(monkeypatch):
    _defs(monkeypatch, [ECHO])
    call = tools.request_tool("Nova", "say", {"x": "hello"})
    denied = tools.deny(call["id"])
    assert denied["status"] == "denied"
    # approving a denied call is a no-op (still denied, never ran)
    again = tools.approve(call["id"])
    assert again["status"] == "denied" and again["output"] is None


def test_auto_approve_runs_immediately_for_operator(monkeypatch):
    _defs(monkeypatch, [SAFE])
    call = tools.request_tool("operator", "ver", {})  # operator authority
    assert call["status"] == "done"
    assert "hi" in call["output"]


def test_agent_auto_approve_is_pending_when_autonomy_off(monkeypatch):
    # Bounded autonomy default: agents do NOT auto-run, even an auto_approve tool.
    _defs(monkeypatch, [SAFE])
    call = tools.request_tool("Nova", "ver", {})
    assert call["status"] == "pending"


def test_arg_validation_blocks_injection(monkeypatch):
    _defs(monkeypatch, [ECHO])
    with pytest.raises(ValueError):
        tools.request_tool("op", "say", {"x": "; rm -rf /"})   # space + ; rejected
    with pytest.raises(ValueError):
        tools.request_tool("op", "say", {"y": "ok"})           # undeclared arg
    with pytest.raises(ValueError):
        tools.request_tool("op", "say", {})                    # missing required {x}


def test_no_shell_metachars_reach_program(monkeypatch):
    # even a benign value with a slash is fine and passed as ONE argv element
    _defs(monkeypatch, [ECHO])
    call = tools.approve(tools.request_tool("op", "say", {"x": "a/b-c.d"})["id"])
    assert call["status"] == "done" and "a/b-c.d" in call["output"]


def test_parse_request_extracts_tool_block():
    text = 'Sure, I will check.\n```tool\n{"tool": "say", "args": {"x": "hi"}}\n```'
    req = tools.parse_request(text)
    assert req == {"tool": "say", "args": {"x": "hi"}}
    assert tools.parse_request("no tool here") is None
    assert tools.parse_request("```tool\nnot json\n```") is None
