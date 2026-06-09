"""Retry-with-backoff + model fallback for the LLM call layer.

Both features are OFF BY DEFAULT: with MAYBOT_LLM_RETRIES unset/0 and no
`fallback_models` on the agent dict, behavior is identical to today — exactly
one attempt per call. These tests inject a fake backend (monkeypatching the
low-level request function) and a no-op backoff sleeper, so nothing actually
sleeps or hits the network.
"""
import pytest

from maybot_control_center import agents, budget


@pytest.fixture(autouse=True)
def _no_sleep_no_budget(monkeypatch):
    # Never actually sleep during backoff.
    monkeypatch.setattr(agents, "_retry_sleep", lambda *a, **k: None)
    # Budget gate always permits, so it never short-circuits a call.
    monkeypatch.setattr(budget, "allow_call", lambda agent_name=None: (True, None))


def _agent(**extra):
    a = {"name": "Nova", "provider": "openai_compatible",
         "base_url": "http://x", "model": "primary"}
    a.update(extra)
    return a


# --- a fake openai-compatible HTTP backend ----------------------------------
class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._text}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _transient():
    """A retryable failure: a 503 HTTPError."""
    import requests
    err = requests.exceptions.HTTPError("503 Server Error")
    resp = requests.Response()
    resp.status_code = 503
    err.response = resp
    return err


# --- 1. fail twice then succeed: with retries=2 → ok, called 3x --------------
def test_retries_transient_then_succeeds(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 2)
    calls = {"n": 0}

    def _post(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _transient()
        return _Resp("hello")

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(_agent(), [{"role": "user", "content": "hi"}])
    assert ok is True
    assert text == "hello"
    assert err is None
    assert calls["n"] == 3  # 1 initial + 2 retries


# --- 2. permanent auth failure is NOT retried -------------------------------
def test_auth_failure_not_retried(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 5)
    calls = {"n": 0}

    def _post(*a, **k):
        calls["n"] += 1
        # A 401 is a permanent 4xx — not transient, must not be retried.
        import requests
        err = requests.exceptions.HTTPError("401 Unauthorized")
        resp = requests.Response()
        resp.status_code = 401
        err.response = resp
        raise err

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(_agent(), [{"role": "user", "content": "hi"}])
    assert ok is False
    assert calls["n"] == 1  # tried once, no retries on a permanent failure


# --- 3. model fallback: second model tried after the first exhausts ---------
def test_fallback_model_tried_after_primary_exhausts(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 1)
    seen = []

    def _post(url, json=None, **k):
        seen.append(json["model"])
        if json["model"] == "primary":
            raise _transient()       # primary always fails (incl. its 1 retry)
        return _Resp("from-fallback")

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(
        _agent(fallback_models=["backup-a", "backup-b"]),
        [{"role": "user", "content": "hi"}],
    )
    assert ok is True
    assert text == "from-fallback"
    # primary attempted twice (1 + 1 retry), then the first fallback succeeds.
    assert seen == ["primary", "primary", "backup-a"]


def test_single_fallback_model_key(monkeypatch):
    # The singular `fallback_model: str` form is also honored.
    monkeypatch.setattr(agents, "LLM_RETRIES", 0)

    def _post(url, json=None, **k):
        if json["model"] == "primary":
            raise _transient()
        return _Resp("ok2")

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(
        _agent(fallback_model="solo-backup"),
        [{"role": "user", "content": "hi"}],
    )
    assert ok is True and text == "ok2"


# --- 4. default-off: retries=0 and no fallback → exactly one attempt ---------
def test_default_off_single_attempt(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 0)
    calls = {"n": 0}

    def _post(*a, **k):
        calls["n"] += 1
        raise _transient()  # transient, but retries are off → no retry

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(_agent(), [{"role": "user", "content": "hi"}])
    assert ok is False
    assert calls["n"] == 1  # unchanged behavior: exactly one attempt


def test_default_off_success_single_attempt(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 0)
    calls = {"n": 0}

    def _post(*a, **k):
        calls["n"] += 1
        return _Resp("done")

    monkeypatch.setattr(agents.requests, "post", _post)
    ok, text, err = agents._chat(_agent(), [{"role": "user", "content": "hi"}])
    assert ok is True and text == "done"
    assert calls["n"] == 1


# --- budget gate stays first and unretried ----------------------------------
def test_budget_block_never_reaches_backend(monkeypatch):
    monkeypatch.setattr(agents, "LLM_RETRIES", 3)
    monkeypatch.setattr(budget, "allow_call",
                        lambda agent_name=None: (False, "LLM budget reached — calls paused"))

    def _boom(*a, **k):
        raise AssertionError("backend must not be called when budget-blocked")

    monkeypatch.setattr(agents.requests, "post", _boom)
    ok, text, err = agents._chat(_agent(), [{"role": "user", "content": "hi"}])
    assert ok is False and text == ""
    assert "budget" in err and "paused" in err


# --- helper unit checks ------------------------------------------------------
def test_fallback_models_parsing():
    assert agents._fallback_models({}) == []
    assert agents._fallback_models({"fallback_models": ["a", "b"]}) == ["a", "b"]
    assert agents._fallback_models({"fallback_models": "single"}) == ["single"]
    assert agents._fallback_models({"fallback_model": "one"}) == ["one"]
    # both forms combine, de-duped
    assert agents._fallback_models(
        {"fallback_models": ["a"], "fallback_model": "a"}) == ["a"]


def test_transient_classifier_requests():
    import requests
    assert agents._is_transient_requests(requests.exceptions.Timeout()) is True
    assert agents._is_transient_requests(requests.exceptions.ConnectionError()) is True
    assert agents._is_transient_requests(_transient()) is True  # 503
    err = requests.exceptions.HTTPError()
    resp = requests.Response()
    resp.status_code = 400
    err.response = resp
    assert agents._is_transient_requests(err) is False  # permanent 4xx
    assert agents._is_transient_requests(ValueError("nope")) is False
