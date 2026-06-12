"""Hardening wave: gated OpenAPI docs, tamper-evident audit log + SIEM export,
notification severity routing + snooze, LLM context trimming + secret redaction,
graceful store close, and the paid lab-hint system."""
import importlib
import json

import pytest
from starlette.testclient import TestClient

from maybot_control_center import agents, audit, cultivation, learning, notify, store
from maybot_control_center.app import app

client = TestClient(app)


# ---- gated OpenAPI docs ----
def test_docs_hidden_by_default():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_enabled_with_env(monkeypatch):
    monkeypatch.setenv("MAYBOT_DOCS", "1")
    import maybot_control_center.app as app_mod
    importlib.reload(app_mod)
    c = TestClient(app_mod.app)
    assert c.get("/docs").status_code == 200
    assert c.get("/openapi.json").status_code == 200
    # restore the default-off app for the rest of the suite
    monkeypatch.delenv("MAYBOT_DOCS")
    importlib.reload(app_mod)


# ---- tamper-evident audit log ----
def test_audit_chain_verifies_clean():
    audit.clear()
    audit.record("op", "POST /api/x")
    audit.record("op", "POST /api/y")
    audit.record("op", "DELETE /api/z")
    v = audit.verify()
    assert v["ok"] is True and v["checked"] == 3


def test_audit_chain_detects_tampering():
    audit.clear()
    audit.record("op", "POST /api/x")
    audit.record("op", "POST /api/y")
    audit._log[0]["action"] = "POST /api/forged"   # tamper with a recorded entry
    v = audit.verify()
    assert v["ok"] is False and v["broken_at"] == 1 and "altered" in v["reason"]
    audit.clear()


def test_audit_chain_detects_deletion():
    audit.clear()
    for i in range(3):
        audit.record("op", f"POST /api/{i}")
    del audit._log[1]                              # remove an entry from the middle
    v = audit.verify()
    assert v["ok"] is False and "removed or reordered" in v["reason"]
    audit.clear()


def test_audit_export_jsonl_and_endpoints():
    audit.clear()
    audit.record("op", "POST /api/x")
    lines = audit.export_jsonl().splitlines()
    assert len(lines) >= 1 and json.loads(lines[0])["action"] == "POST /api/x"
    assert client.get("/api/audit/verify").json()["ok"] is True
    r = client.get("/api/audit/export")
    assert r.status_code == 200 and "x-ndjson" in r.headers["content-type"]
    audit.clear()


# ---- notification severity routing + snooze ----
def test_notify_severity_routing(monkeypatch):
    monkeypatch.setenv("MAYBOT_NOTIFY_MIN_LEVEL_PAGERDUTY", "error")
    assert notify._routed("pagerduty", "info") is False
    assert notify._routed("pagerduty", "warn") is False
    assert notify._routed("pagerduty", "error") is True
    assert notify._routed("pagerduty", "critical") is True
    assert notify._routed("slack", "info") is True      # other channels unaffected
    monkeypatch.setenv("MAYBOT_NOTIFY_MIN_LEVEL", "warn")
    assert notify._routed("slack", "info") is False     # global floor applies


def test_notify_snooze_mutes_but_records():
    notify.snooze(5)
    assert notify.snoozed() is True
    res = notify.send("snoozed alert", "body", level="error")
    assert res["recorded"] is True and res["delivered"] == []
    notify.unsnooze()
    assert notify.snoozed() is False


def test_notify_snooze_endpoints():
    r = client.post("/api/notifications/snooze", json={"minutes": 10})
    assert r.status_code == 200 and r.json()["snoozed"] is True
    assert client.get("/api/notifications").json()["snoozed"] is True
    r = client.post("/api/notifications/snooze", json={"minutes": 0})
    assert r.json()["snoozed"] is False


# ---- LLM context-window trimming ----
def test_fit_context_keeps_system_and_newest(monkeypatch):
    monkeypatch.setattr(agents, "LLM_CONTEXT_CHARS", 100)
    msgs = ([{"role": "system", "content": "S" * 20}] +
            [{"role": "user", "content": f"turn {i} " + "x" * 30} for i in range(10)])
    out = agents._fit_context(msgs)
    assert out[0]["role"] == "system"                    # system survives
    assert out[-1]["content"] == msgs[-1]["content"]     # newest turn survives
    assert sum(len(m["content"]) for m in out) <= 100


def test_fit_context_truncates_one_huge_message(monkeypatch):
    monkeypatch.setattr(agents, "LLM_CONTEXT_CHARS", 200)
    msgs = [{"role": "user", "content": "y" * 5000}]
    out = agents._fit_context(msgs)
    assert out[0]["content"].endswith("[truncated to fit context]")
    assert msgs[0]["content"] == "y" * 5000              # caller's dict untouched
    assert agents._fit_context([]) == []


def test_fit_context_disabled_and_noop(monkeypatch):
    monkeypatch.setattr(agents, "LLM_CONTEXT_CHARS", 0)
    msgs = [{"role": "user", "content": "z" * 100}]
    assert agents._fit_context(msgs) is msgs
    monkeypatch.setattr(agents, "LLM_CONTEXT_CHARS", 1000)
    assert agents._fit_context(msgs) is msgs             # under budget → untouched


# ---- output guardrail: secret redaction ----
def test_redact_secrets_patterns():
    text = ("key sk-abcdefghijklmnopqrstuvwx and ghp_ABCDEFGHIJKLMNOPQRSTuvwx123456 and "
            "AKIAIOSFODNN7EXAMPLE plus\n-----BEGIN RSA PRIVATE KEY-----\nMII...\n-----END RSA PRIVATE KEY-----")
    out = agents.redact_secrets(text)
    assert "sk-abcdefghijklmnop" not in out and "ghp_" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out and "BEGIN RSA PRIVATE KEY" not in out
    assert out.count("[REDACTED]") == 4
    assert agents.redact_secrets("nothing secret here") == "nothing secret here"


def test_guard_output_is_opt_in(monkeypatch):
    leaky = "the key is sk-abcdefghijklmnopqrstuvwx"
    assert agents._guard_output(leaky) == leaky          # default off
    monkeypatch.setattr(agents, "LLM_REDACT", True)
    assert "[REDACTED]" in agents._guard_output(leaky)


# ---- graceful store close ----
def test_store_close_is_safe_and_reconnects():
    store._reset_for_tests(":memory:")
    try:
        assert store.enabled()
        store.close()
        store.close()                                    # idempotent
        store.save_state("wave", {"ok": 1})              # lazy reconnect works
        assert store.load_state("wave") == {"ok": 1}
    finally:
        store._reset_for_tests("")                       # persistence off for other tests


# ---- Learning Center: paid lab hints ----
@pytest.fixture()
def fresh_learning():
    learning._state.clear()
    learning._state.update(learning._blank())
    yield


def _seed_lab():
    lab = {"track": "t1", "kind": "ids", "brief": "Find the intrusion.",
           "artifact": "logs...", "answer": "SQLi from 10.0.0.9", "indicators": ["OR 1=1"],
           "created": 0}
    learning._g().setdefault("labs", {})["lab-1"] = lab
    return lab


def hint_chat(member, messages):
    assert "do NOT reveal" in messages[-1]["content"]
    return True, "Look closely at the requests hitting the admin endpoint.", None


def test_lab_hint_spends_stones(monkeypatch, fresh_learning):
    _seed_lab()
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    cultivation.reward(learning.LEARNER, learning.HINT_COST * 2)
    res = learning.lab_hint("lab-1", chat=hint_chat)
    assert res["error"] is None and "admin endpoint" in res["hint"]
    assert res["cost"] == learning.HINT_COST and res["hints_used"] == 1


def test_lab_hint_requires_stones(monkeypatch, fresh_learning):
    _seed_lab()
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    monkeypatch.setattr(learning, "HINT_COST", 10**9)
    res = learning.lab_hint("lab-1", chat=hint_chat)
    assert "not enough spirit stones" in res["error"]


def test_lab_hint_refunds_on_llm_failure(monkeypatch, fresh_learning):
    _seed_lab()
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    cultivation.reward(learning.LEARNER, learning.HINT_COST)
    res = learning.lab_hint("lab-1", chat=lambda m, msgs: (False, "", "backend down"))
    assert res["error"] == "backend down"
    # the refund means a retry can still afford the hint
    res2 = learning.lab_hint("lab-1", chat=hint_chat)
    assert res2["error"] is None


def test_lab_hint_unknown_lab(fresh_learning):
    assert "unknown" in learning.lab_hint("nope")["error"]
