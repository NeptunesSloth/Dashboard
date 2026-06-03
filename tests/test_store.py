from maybot_control_center import store, history, comms, tools


def _db(tmp_path):
    store._reset_for_tests(str(tmp_path / "t.db"))
    store.init()


def test_disabled_is_noop(monkeypatch):
    store._reset_for_tests("")
    assert store.enabled() is False
    store.add_comms({"from": "x", "kind": "agent", "content": "y", "ts": 1})
    assert store.load_comms() == []


def test_history_roundtrip(tmp_path):
    _db(tmp_path)
    store.add_history("dev", "bot", {"ts": 1, "pnl": 1.5, "health": "ok"})
    store.add_history("dev", "bot", {"ts": 2, "pnl": 2.0, "health": "ok"})
    loaded = store.load_history()
    assert [p["pnl"] for p in loaded["dev:bot"]] == [1.5, 2.0]


def test_tool_calls_roundtrip(tmp_path):
    _db(tmp_path)
    store.upsert_tool_call({"id": 1, "requester": "Nova", "tool": "say", "args": {"x": "hi"},
                            "status": "pending", "output": None, "code": None,
                            "created_at": 1, "finished_at": None})
    store.upsert_tool_call({"id": 1, "requester": "Nova", "tool": "say", "args": {"x": "hi"},
                            "status": "done", "output": "hi", "code": 0,
                            "created_at": 1, "finished_at": 2})
    calls = store.load_tool_calls()
    assert len(calls) == 1  # upsert replaced, not duplicated
    assert calls[0]["status"] == "done" and calls[0]["args"] == {"x": "hi"}


def test_history_module_persists_and_reloads(tmp_path):
    _db(tmp_path)
    history.clear()
    history.record([{"device": "dev", "name": "bot", "health": "ok", "metrics": {"profit_today": 3.0}}])
    history.clear()
    assert history.get("dev", "bot") == []
    history.load_persisted()
    assert [p["pnl"] for p in history.get("dev", "bot")] == [3.0]
    store._reset_for_tests("")  # leave persistence off for other tests


def test_comms_module_persists_and_reloads(tmp_path):
    _db(tmp_path)
    comms.clear()
    comms._post("Nova", "hello", "agent", 1)
    comms.clear()
    assert comms.get_feed() == []
    comms.load_persisted()
    feed = comms.get_feed()
    assert feed and feed[-1]["content"] == "hello"
    store._reset_for_tests("")
