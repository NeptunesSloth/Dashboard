"""Alert acknowledgement & snooze, and its suppression in the notifier/escalation."""
import pytest

from maybot_control_center import acks, notifier, escalation


@pytest.fixture(autouse=True)
def _clean():
    acks.clear()
    notifier.clear()
    escalation.clear()
    yield
    acks.clear()
    notifier.clear()
    escalation.clear()


def test_ack_lifecycle():
    rec = acks.ack("dev:proj", "alice", minutes=30, reason="investigating")
    assert rec["who"] == "alice" and rec["reason"] == "investigating"
    assert acks.is_acked("dev", "proj") is True
    assert acks.resolve("dev:proj") is True
    assert acks.is_acked("dev", "proj") is False


def test_ack_expires(monkeypatch):
    base = 1_000_000_000_000
    monkeypatch.setattr(acks, "_now_ms", lambda: base)
    acks.ack("dev:proj", "bob", minutes=1)
    assert acks.is_acked("dev", "proj") is True
    # Jump past the 1-minute window.
    monkeypatch.setattr(acks, "_now_ms", lambda: base + 61_000)
    assert acks.is_acked("dev", "proj") is False


def test_no_expiry_when_minutes_zero():
    acks.ack("dev:proj", "carol", minutes=0)
    rec = acks.snapshot()["acks"][0]
    assert rec["until"] is None
    assert acks.is_acked("dev", "proj") is True


def test_annotate_attaches_ack():
    acks.ack("dev:proj", "dan", minutes=10)
    p = {"device": "dev", "name": "proj"}
    acks.annotate(p)
    assert p["ack"]["who"] == "dan"


def _proj(health):
    return {"device": "dev", "name": "proj", "health": health, "status": "running", "type": "generic"}


def test_notifier_suppresses_acked_alert(monkeypatch):
    fired = []
    monkeypatch.setattr(notifier, "_fire", lambda **kw: fired.append(kw))
    # First transition ok -> error pages once and arms escalation.
    notifier.check_and_notify([_proj("ok")])
    notifier.check_and_notify([_proj("error")])
    assert len(fired) == 1
    # Acknowledge, then flap error->ok->error: the re-alert is suppressed.
    acks.ack("dev:proj", "alice", minutes=60)
    notifier.check_and_notify([_proj("ok")])      # recovery clears the ack via note_recovery
    acks.ack("dev:proj", "alice", minutes=60)     # re-ack after recovery
    notifier.check_and_notify([_proj("error")])
    assert len(fired) == 1                          # still just the original page


def test_escalation_skips_acked():
    escalation.arm("dev", "proj", now=0.0)
    acks.ack("dev:proj", "alice", minutes=60)
    # Far past the escalation threshold, but acked -> no escalation.
    assert escalation.sweep(now=10_000.0) == []
