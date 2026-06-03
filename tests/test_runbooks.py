from maybot_control_center import runbooks, tools


YAML = """
runbooks:
  - name: restart-stuck-bot
    match: {type: trading_bot, health: error, name_pattern: "daybot*", alert_contains: "ERROR"}
    tool: restart_service
    args: {service: "{name}"}
    requester: operator
    auto: true
  - name: reboot-device
    match: {type: device, health: offline}
    tool: reboot_device
    args: {device: "{device}", keep: 3}
    auto: false
"""


def _write(tmp_path, monkeypatch, text):
    f = tmp_path / "runbooks.yaml"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setattr(runbooks, "RUNBOOKS_FILE", f)
    return f


def setup_function():
    runbooks.clear()


# ---- load + normalize ----

def test_load_normalizes_defaults(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    cat = runbooks.load_runbooks()
    assert [r["name"] for r in cat] == ["restart-stuck-bot", "reboot-device"]
    rb = cat[0]
    assert rb["tool"] == "restart_service"
    assert rb["args"] == {"service": "{name}"}
    assert rb["requester"] == "operator"
    assert rb["auto"] is True
    # second runbook: requester defaults to "operator", auto false
    assert cat[1]["requester"] == "operator"
    assert cat[1]["auto"] is False


def test_catalog_matches_load(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    assert runbooks.catalog() == runbooks.load_runbooks()


def test_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(runbooks, "RUNBOOKS_FILE", tmp_path / "nope.yaml")
    assert runbooks.load_runbooks() == []
    assert runbooks.match({"type": "x"}) is None


def test_bad_entries_skipped(tmp_path, monkeypatch):
    _write(
        tmp_path,
        monkeypatch,
        """
runbooks:
  - {name: no-tool}
  - {tool: orphan_tool}
  - "not-a-dict"
  - {name: good, tool: do_thing}
""",
    )
    cat = runbooks.load_runbooks()
    assert [r["name"] for r in cat] == ["good"]
    assert cat[0]["match"] == {}
    assert cat[0]["args"] == {}


# ---- match: each key independently ----

def test_match_type_only(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
runbooks:
  - {name: r, tool: t, match: {type: trading_bot}}
""")
    assert runbooks.match({"type": "trading_bot"})["name"] == "r"
    assert runbooks.match({"type": "device"}) is None


def test_match_health_only(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
runbooks:
  - {name: r, tool: t, match: {health: error}}
""")
    assert runbooks.match({"health": "error"})["name"] == "r"
    assert runbooks.match({"health": "ok"}) is None


def test_match_name_pattern_glob(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
runbooks:
  - {name: r, tool: t, match: {name_pattern: "daybot*"}}
""")
    assert runbooks.match({"name": "daybot-1"})["name"] == "r"
    assert runbooks.match({"name": "nightbot"}) is None


def test_match_alert_contains_substring(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
runbooks:
  - {name: r, tool: t, match: {alert_contains: "ERROR"}}
""")
    assert runbooks.match({"alerts": ["x", "fatal ERROR here"]})["name"] == "r"
    assert runbooks.match({"alerts": ["all fine"]}) is None
    assert runbooks.match({}) is None  # no alerts


def test_match_combined_all_must_pass(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    proj = {
        "type": "trading_bot",
        "health": "error",
        "name": "daybot-7",
        "alerts": ["boom ERROR boom"],
    }
    assert runbooks.match(proj)["name"] == "restart-stuck-bot"
    # one key off → no match for the first runbook (and not the second either)
    assert runbooks.match({**proj, "health": "ok"}) is None


def test_match_returns_first(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
runbooks:
  - {name: first, tool: t, match: {type: x}}
  - {name: second, tool: t, match: {type: x}}
""")
    assert runbooks.match({"type": "x"})["name"] == "first"


# ---- _render_args ----

def test_render_args_substitutes(tmp_path, monkeypatch):
    proj = {"name": "daybot-1", "device": "dev42", "type": "trading_bot"}
    args = {
        "service": "{name}",
        "dev": "{device}",
        "kind": "{type}",
        "count": 3,
        "literal": "no-placeholder",
    }
    out = runbooks._render_args(args, proj)
    assert out == {
        "service": "daybot-1",
        "dev": "dev42",
        "kind": "trading_bot",
        "count": 3,
        "literal": "no-placeholder",
    }


def test_render_args_missing_field_blank(tmp_path, monkeypatch):
    out = runbooks._render_args({"x": "{name}"}, {})
    assert out == {"x": ""}


# ---- dispatch ----

def test_dispatch_requests_tool_with_rendered_args(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    calls = []

    def fake_request(requester, tool_name, args):
        calls.append((requester, tool_name, args))
        return {"id": 1, "status": "pending"}

    monkeypatch.setattr(tools, "enabled", lambda: True)
    monkeypatch.setattr(tools, "request_tool", fake_request)

    proj = {
        "type": "trading_bot",
        "health": "error",
        "name": "daybot-9",
        "alerts": ["ERROR!"],
    }
    res = runbooks.dispatch(proj)
    assert calls == [("operator", "restart_service", {"service": "daybot-9"})]
    assert res == {
        "runbook": "restart-stuck-bot",
        "tool": "restart_service",
        "requested": {"id": 1, "status": "pending"},
        "auto": True,
    }


def test_dispatch_none_when_no_match(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    monkeypatch.setattr(tools, "enabled", lambda: True)
    monkeypatch.setattr(tools, "request_tool", lambda *a, **k: pytest_fail())
    assert runbooks.dispatch({"type": "unknown"}) is None


def test_dispatch_none_when_tools_disabled(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    monkeypatch.setattr(tools, "enabled", lambda: False)

    def boom(*a, **k):
        raise AssertionError("request_tool must not be called when disabled")

    monkeypatch.setattr(tools, "request_tool", boom)
    proj = {"type": "trading_bot", "health": "error", "name": "daybot-1", "alerts": ["ERROR"]}
    assert runbooks.dispatch(proj) is None


def test_dispatch_wraps_value_error(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, YAML)
    monkeypatch.setattr(tools, "enabled", lambda: True)

    def bad(requester, tool_name, args):
        raise ValueError("unknown tool: restart_service")

    monkeypatch.setattr(tools, "request_tool", bad)
    proj = {"type": "trading_bot", "health": "error", "name": "daybot-1", "alerts": ["ERROR"]}
    res = runbooks.dispatch(proj)
    assert res == {"runbook": "restart-stuck-bot", "error": "unknown tool: restart_service"}


def pytest_fail():  # helper so the lambda above raises if ever called
    raise AssertionError("request_tool should not be called")


# ---- clear() ----

def test_clear_drops_cache(tmp_path, monkeypatch):
    f = _write(tmp_path, monkeypatch, """
runbooks:
  - {name: one, tool: t}
""")
    assert [r["name"] for r in runbooks.load_runbooks()] == ["one"]
    # edit file; without clear the cache still returns the old catalog
    f.write_text("""
runbooks:
  - {name: two, tool: t}
""", encoding="utf-8")
    assert [r["name"] for r in runbooks.load_runbooks()] == ["one"]
    runbooks.clear()
    assert [r["name"] for r in runbooks.load_runbooks()] == ["two"]
