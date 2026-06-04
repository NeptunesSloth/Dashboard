import pytest

from maybot_control_center import notifier, maintenance


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    notifier.clear()
    maintenance.clear()
    monkeypatch.setattr(notifier, "ALERT_STATES", {"error"})
    monkeypatch.setattr(notifier, "SEND_RECOVERY", True)
    monkeypatch.setattr(notifier, "COOLDOWN_SECONDS", 300.0)
    monkeypatch.setattr(notifier, "FLAP_THRESHOLD", 100)  # effectively off; flap test overrides
    monkeypatch.setattr(notifier, "FLAP_WINDOW_SECONDS", 600.0)
    fired = []
    monkeypatch.setattr(notifier, "_fire", lambda **k: fired.append(("alert", k["curr"])))
    monkeypatch.setattr(notifier, "_fire_recovery", lambda n, d: fired.append(("recovery", n)))
    monkeypatch.setattr(notifier, "_fire_flap", lambda n, d, c: fired.append(("flap", c)))
    return fired


def _poll(health):
    notifier.check_and_notify([{"device": "d", "name": "bot", "health": health, "status": "x"}])


def test_first_sight_does_not_alert(_reset):
    _poll("error")
    assert _reset == []


def test_transition_into_alert_fires(_reset):
    _poll("ok")
    _poll("error")
    assert _reset == [("alert", "error")]


def test_recovery_fires_after_alert(_reset):
    _poll("ok")
    _poll("error")
    _poll("ok")
    assert _reset == [("alert", "error"), ("recovery", "bot")]


def test_cooldown_dedupes_same_state(monkeypatch, _reset):
    clock = [1000.0]
    monkeypatch.setattr(notifier, "_now", lambda: clock[0])
    _poll("ok"); _poll("error")          # fire
    clock[0] += 10
    _poll("ok"); _poll("error")          # within cooldown, same state → deduped
    assert [f for f in _reset if f[0] == "alert"] == [("alert", "error")]


def test_cooldown_expires(monkeypatch, _reset):
    clock = [1000.0]
    monkeypatch.setattr(notifier, "_now", lambda: clock[0])
    _poll("ok"); _poll("error")
    clock[0] += 400                      # past the 300s cooldown
    _poll("ok"); _poll("error")
    assert [f for f in _reset if f[0] == "alert"] == [("alert", "error"), ("alert", "error")]


def test_flap_suppression(monkeypatch, _reset):
    clock = [1000.0]
    monkeypatch.setattr(notifier, "_now", lambda: clock[0])
    monkeypatch.setattr(notifier, "FLAP_THRESHOLD", 3)
    # rapid toggling; threshold 3 transitions in window
    for h in ["ok", "error", "ok", "error", "ok", "error"]:
        clock[0] += 1
        _poll(h)
    kinds = [f[0] for f in _reset]
    assert "flap" in kinds
    assert kinds.count("flap") == 1      # announced once, then quiet


def test_silenced_project_does_not_alert(_reset):
    maintenance.silence("d:bot", minutes=60)
    _poll("ok")
    _poll("error")
    assert _reset == []


def test_silenced_recovery_clears_silence(_reset):
    maintenance.silence("d:bot", minutes=0)
    _poll("ok")
    _poll("error")       # silenced, no alert
    _poll("ok")          # recovery clears the silence
    assert maintenance.is_silenced("d", "bot") is False
