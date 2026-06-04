import time

from maybot_control_center import maintenance


def setup_function():
    maintenance.clear()


def test_exact_target_silences_one_project():
    maintenance.silence("dev1:bot", minutes=60)
    assert maintenance.is_silenced("dev1", "bot") is True
    assert maintenance.is_silenced("dev1", "other") is False
    assert maintenance.is_silenced("dev2", "bot") is False


def test_device_wildcard():
    maintenance.silence("dev1:*", minutes=60)
    assert maintenance.is_silenced("dev1", "bot") is True
    assert maintenance.is_silenced("dev1", "anything") is True
    assert maintenance.is_silenced("dev2", "bot") is False


def test_global_wildcard():
    maintenance.silence("*", minutes=60)
    assert maintenance.is_silenced("anything", "anywhere") is True


def test_expiry(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(maintenance, "_now", lambda: now[0])
    maintenance.silence("dev1:bot", minutes=1)  # expires at 1060
    assert maintenance.is_silenced("dev1", "bot") is True
    now[0] = 1061.0
    assert maintenance.is_silenced("dev1", "bot") is False
    assert maintenance.active() == []  # pruned


def test_indefinite_silence_does_not_expire(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(maintenance, "_now", lambda: now[0])
    s = maintenance.silence("dev1:bot", minutes=0)
    assert s["expires_in"] is None
    now[0] = 10_000_000.0
    assert maintenance.is_silenced("dev1", "bot") is True


def test_unsilence():
    maintenance.silence("dev1:bot", minutes=60)
    assert maintenance.unsilence("dev1:bot") is True
    assert maintenance.is_silenced("dev1", "bot") is False
    assert maintenance.unsilence("dev1:bot") is False  # already gone


def test_recovery_clears_recovery_silence():
    maintenance.silence("dev1:bot", minutes=0, clear_on_recovery=True)
    maintenance.note_recovery("dev1", "bot")
    assert maintenance.is_silenced("dev1", "bot") is False


def test_recovery_keeps_non_recovery_silence():
    maintenance.silence("dev1:bot", minutes=60, clear_on_recovery=False)
    maintenance.note_recovery("dev1", "bot")
    assert maintenance.is_silenced("dev1", "bot") is True


def test_snapshot_shape():
    maintenance.silence("dev1:bot", minutes=30, reason="upgrade")
    snap = maintenance.snapshot()
    assert isinstance(snap["now"], int)
    assert snap["silences"][0]["target"] == "dev1:bot"
    assert snap["silences"][0]["reason"] == "upgrade"
    assert snap["silences"][0]["expires_in"] > 0
