"""Hard LLM spend caps (daily/monthly) with pause + once-per-threshold alerts.

These are additive and OFF BY DEFAULT: with no MAYBOT_BUDGET_DAILY_USD /
MAYBOT_BUDGET_MONTHLY_USD set, allow_call() always permits and no alerts fire.
"""
from maybot_control_center import agents, budget, notify


def setup_function():
    budget.reset_caps()
    notify.clear()


# --- spend stub: make budget see a fixed rolling-window spend ----------------
def _spend(usd):
    return lambda hours=24: {
        "hours": hours, "buckets": [],
        "totals": {"cost": usd, "calls": 0, "tokens": 0, "errors": 0},
    }


def test_allow_call_unconfigured_is_true(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 0.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 0.0)
    monkeypatch.setattr(budget, "_series", _spend(999.0))  # spend irrelevant when off
    ok, reason = budget.allow_call("Nova")
    assert ok is True and reason is None


def test_allow_call_under_cap_is_true(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 10.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 0.0)
    monkeypatch.setattr(budget, "_series", _spend(4.0))    # 40% used
    ok, reason = budget.allow_call("Nova")
    assert ok is True and reason is None


def test_allow_call_over_daily_cap_is_blocked(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 10.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 0.0)
    monkeypatch.setattr(budget, "_series", _spend(10.5))   # over cap
    ok, reason = budget.allow_call("Nova")
    assert ok is False
    assert reason is not None and "daily" in reason and "paused" in reason


def test_allow_call_over_monthly_cap_is_blocked(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 0.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 100.0)
    monkeypatch.setattr(budget, "_series", _spend(120.0))
    ok, reason = budget.allow_call("Nova")
    assert ok is False and "monthly" in reason


def test_caps_surfaced_in_snapshot(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 10.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 0.0)
    monkeypatch.setattr(budget, "_series", _spend(8.0))
    monkeypatch.setattr(budget, "_usage", lambda: {"agents": [], "totals": {"cost": 8.0}})
    snap = budget.snapshot()
    d = snap["caps"]["daily"]
    assert d["enabled"] is True and d["cap"] == 10.0
    assert d["remaining"] == 2.0 and d["paused"] is False
    assert snap["caps"]["monthly"]["enabled"] is False


# --- enforcement at the agents call site -------------------------------------
def test_chat_blocked_when_over_budget(monkeypatch):
    # Over-budget gate: _chat must return the (False, "", err) failure shape and
    # never reach the backend. Monkeypatch the injectable budget check.
    monkeypatch.setattr(budget, "allow_call",
                        lambda agent_name=None: (False, "daily LLM budget reached ($10/$10) — calls paused"))
    called = {"backend": False}

    def _boom(*a, **k):
        called["backend"] = True
        raise AssertionError("backend must not be called when over budget")

    monkeypatch.setattr(agents.requests, "post", _boom)
    agent = {"name": "Nova", "provider": "openai_compatible", "base_url": "http://x", "model": "m"}
    ok, text, err = agents._chat(agent, [{"role": "user", "content": "hi"}])
    assert ok is False and text == ""
    assert "budget" in err and "paused" in err
    assert called["backend"] is False


def test_chat_allowed_when_under_budget_reaches_backend(monkeypatch):
    # Sanity: when allow_call permits, _chat proceeds to the backend as normal.
    monkeypatch.setattr(budget, "allow_call", lambda agent_name=None: (True, None))
    reached = {"backend": False}

    def _boom(*a, **k):
        reached["backend"] = True
        raise RuntimeError("network down")  # any backend error is fine; we only assert it ran

    monkeypatch.setattr(agents.requests, "post", _boom)
    agent = {"name": "Nova", "provider": "openai_compatible", "base_url": "http://x", "model": "m"}
    ok, text, err = agents._chat(agent, [{"role": "user", "content": "hi"}])
    assert reached["backend"] is True and ok is False


def test_stream_chat_yields_nothing_when_over_budget(monkeypatch):
    monkeypatch.setattr(budget, "allow_call",
                        lambda agent_name=None: (False, "daily LLM budget reached — calls paused"))
    agent = {"name": "Nova", "provider": "openai_compatible", "base_url": "http://x", "model": "m"}
    chunks = list(agents.stream_chat(agent, [{"role": "user", "content": "hi"}]))
    assert chunks == []


# --- alerts fire once per threshold per day ----------------------------------
def test_alert_fires_once_per_threshold(monkeypatch):
    monkeypatch.setattr(budget, "DAILY_USD", 10.0)
    monkeypatch.setattr(budget, "MONTHLY_USD", 0.0)
    sent = []
    monkeypatch.setattr(notify, "send",
                        lambda title, body="", level="info", kind="alert": sent.append((title, level)))

    # 85% used → crosses the 80% warn threshold once.
    monkeypatch.setattr(budget, "_series", _spend(8.5))
    budget.allow_call("Nova")
    budget.allow_call("Nova")  # repeat same day → no second warn alert
    assert len(sent) == 1
    assert "warning" in sent[0][0].lower()

    # 100% used → crosses the 100% threshold once (distinct from the warn one).
    monkeypatch.setattr(budget, "_series", _spend(10.0))
    budget.allow_call("Nova")
    budget.allow_call("Nova")
    assert len(sent) == 2
    assert "paused" in sent[1][0].lower()
