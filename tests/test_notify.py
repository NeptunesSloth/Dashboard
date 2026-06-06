"""Offline tests for the pluggable notifier.

Run with no webhook env configured, so every send is a no-op delivery that is
still recorded to the in-memory ring.
"""
import pytest

from maybot_control_center import notify


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """No channels configured, fresh ring per test."""
    for var in ("MAYBOT_SLACK_WEBHOOK", "MAYBOT_DISCORD_WEBHOOK", "MAYBOT_WEBHOOK_URL"):
        monkeypatch.delenv(var, raising=False)
    notify.clear()
    yield
    notify.clear()


def test_channels_empty_without_env():
    assert notify.channels() == []


def test_channels_reflect_env(monkeypatch):
    monkeypatch.setenv("MAYBOT_SLACK_WEBHOOK", "https://hooks.example/slack")
    monkeypatch.setenv("MAYBOT_WEBHOOK_URL", "https://hooks.example/generic")
    assert set(notify.channels()) == {"slack", "webhook"}


def test_send_records_with_no_channels():
    res = notify.send("Tribulation", "lightning strikes the sect", level="warning")
    assert res == {"delivered": [], "recorded": True}

    events = notify.recent()
    assert len(events) == 1
    ev = events[-1]
    assert ev["title"] == "Tribulation"
    assert ev["body"] == "lightning strikes the sect"
    assert ev["level"] == "warning"
    assert ev["kind"] == "alert"
    assert ev["delivered"] == []
    assert "ts" in ev


def test_dedupe_suppresses_immediate_duplicate():
    first = notify.send("Same", "body")
    second = notify.send("Same", "body")

    assert first["recorded"] is True
    assert second["recorded"] is False
    # Only the first one lands in the log.
    assert len(notify.recent()) == 1


def test_recent_limit():
    for i in range(5):
        notify.send(f"alert-{i}", f"body-{i}")
    assert len(notify.recent(limit=3)) == 3
    assert len(notify.recent()) == 5
