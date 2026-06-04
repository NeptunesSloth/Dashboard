import pytest

from maybot_control_center import escalation, oaths, maintenance, governance


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    escalation.clear()
    oaths.clear()
    maintenance.clear()
    monkeypatch.setattr(escalation, "ENABLED", True)
    monkeypatch.setattr(escalation, "ESCALATE_AFTER", 900.0)
    events = []
    monkeypatch.setattr("maybot_control_center.notifier.notify_event",
                        lambda e, t, m: events.append(e))
    monkeypatch.setattr(governance, "system_notice", lambda text, sender="System": events.append("notice"))
    return events


def test_no_escalation_before_threshold(_reset):
    escalation.arm("d", "bot", now=1000)
    assert escalation.sweep(now=1000 + 800) == []
    assert _reset == []


def test_escalates_after_threshold_once(_reset):
    escalation.arm("d", "bot", now=1000)
    assert escalation.sweep(now=1000 + 901) == ["d:bot"]
    assert "escalation" in _reset
    assert escalation.sweep(now=1000 + 2000) == []  # only once


def test_claim_cancels_escalation(_reset):
    escalation.arm("d", "bot", now=1000)
    oaths.claim("d:bot", "Nova")
    assert escalation.sweep(now=1000 + 901) == []


def test_silence_cancels_escalation(_reset, monkeypatch):
    escalation.arm("d", "bot", now=1000)
    maintenance.silence("d:bot", minutes=60)
    assert escalation.sweep(now=1000 + 901) == []


def test_disarm(_reset):
    escalation.arm("d", "bot", now=1000)
    escalation.disarm("d", "bot")
    assert escalation.sweep(now=1000 + 901) == []


def test_disabled(_reset, monkeypatch):
    monkeypatch.setattr(escalation, "ENABLED", False)
    escalation.arm("d", "bot", now=1000)
    assert escalation.sweep(now=1000 + 901) == []
