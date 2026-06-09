"""Opt-in Sentry error tracking (default-off, additive).

These tests assert that :func:`maybot_control_center.obs.setup_sentry`:

* is a complete no-op with no DSN (no import of ``sentry_sdk``, init not called),
* initializes ``sentry_sdk`` exactly once with the DSN when one is set,
* degrades gracefully when ``sentry-sdk`` is not installed (no raise), and
* is idempotent on a second call.
"""
import builtins
import sys
import types

import pytest

from maybot_control_center import obs


@pytest.fixture(autouse=True)
def _reset_sentry_state(monkeypatch):
    """Each test starts from a clean, un-initialized Sentry state."""
    monkeypatch.setattr(obs, "_SENTRY_INITIALIZED", False, raising=False)
    monkeypatch.delenv("MAYBOT_SENTRY_DSN", raising=False)
    monkeypatch.delenv("MAYBOT_SENTRY_TRACES_SAMPLE_RATE", raising=False)
    monkeypatch.delenv("MAYBOT_ENV", raising=False)
    monkeypatch.delenv("MAYBOT_RELEASE", raising=False)
    yield


def _fake_sentry(monkeypatch):
    """Inject a fake ``sentry_sdk`` module recording calls to ``init``."""
    calls = []
    fake = types.ModuleType("sentry_sdk")

    def init(**kwargs):
        calls.append(kwargs)

    fake.init = init
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    return calls


def test_noop_without_dsn(monkeypatch):
    # Master switch off: no import attempt at all and init never reached.
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise AssertionError("sentry_sdk must not be imported without a DSN")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert obs.setup_sentry() is False
    assert obs._SENTRY_INITIALIZED is False


def test_init_called_once_with_dsn(monkeypatch):
    calls = _fake_sentry(monkeypatch)
    monkeypatch.setenv("MAYBOT_SENTRY_DSN", "https://abc@example.ingest.sentry.io/42")
    monkeypatch.setenv("MAYBOT_SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("MAYBOT_ENV", "staging")
    monkeypatch.setenv("MAYBOT_RELEASE", "maybot@1.2.3")

    assert obs.setup_sentry() is True
    assert len(calls) == 1
    kw = calls[0]
    assert kw["dsn"] == "https://abc@example.ingest.sentry.io/42"
    assert kw["traces_sample_rate"] == 0.25
    assert kw["environment"] == "staging"
    assert kw["release"] == "maybot@1.2.3"


def test_defaults_when_optional_env_unset(monkeypatch):
    calls = _fake_sentry(monkeypatch)
    monkeypatch.setenv("MAYBOT_SENTRY_DSN", "https://k@o.ingest.sentry.io/1")

    assert obs.setup_sentry() is True
    kw = calls[0]
    assert kw["traces_sample_rate"] == 0.0
    assert kw["environment"] == "production"
    assert kw["release"] is None


def test_idempotent_second_call(monkeypatch):
    calls = _fake_sentry(monkeypatch)
    monkeypatch.setenv("MAYBOT_SENTRY_DSN", "https://k@o.ingest.sentry.io/1")

    assert obs.setup_sentry() is True
    assert obs.setup_sentry() is True
    assert len(calls) == 1  # init not called a second time


def test_graceful_when_sentry_sdk_missing(monkeypatch):
    # Simulate sentry-sdk not installed: import raises ImportError.
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise ImportError("No module named 'sentry_sdk'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    monkeypatch.setenv("MAYBOT_SENTRY_DSN", "https://k@o.ingest.sentry.io/1")

    # Must not raise, and must report Sentry as not initialized.
    assert obs.setup_sentry() is False
    assert obs._SENTRY_INITIALIZED is False


def test_setup_logging_triggers_sentry(monkeypatch):
    # setup_logging() should drive Sentry init even when JSON logging is off,
    # so app.py needs no change.
    calls = _fake_sentry(monkeypatch)
    monkeypatch.delenv("MAYBOT_JSON_LOGS", raising=False)
    monkeypatch.setenv("MAYBOT_SENTRY_DSN", "https://k@o.ingest.sentry.io/1")

    assert obs.setup_logging() is False  # JSON logging stays off
    assert len(calls) == 1  # but Sentry was initialized
