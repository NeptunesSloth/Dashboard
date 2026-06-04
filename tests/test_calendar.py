"""Heavenly Calendar — scheduled/recurring maintenance windows in maintenance.py."""
import time

from maybot_control_center import maintenance


def setup_function():
    maintenance.clear()


def _write(tmp_path, monkeypatch, text):
    f = tmp_path / "calendar.yaml"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setattr(maintenance, "CALENDAR_FILE", f)


def _at(monkeypatch, struct):
    # Pin both the epoch clock and localtime so window math is deterministic.
    epoch = time.mktime(struct)
    monkeypatch.setattr(maintenance, "_now", lambda: epoch)
    return epoch


def test_recurring_window_active_within_hours(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "windows:\n  - {target: 'd:bot', start: '02:00', duration_minutes: 120, reason: nightly}\n")
    # A Wednesday at 02:30 local → inside the 02:00–04:00 window.
    _at(monkeypatch, time.struct_time((2026, 6, 3, 2, 30, 0, 2, 154, -1)))
    active = maintenance.scheduled_active()
    assert active and active[0]["target"] == "d:bot"
    assert maintenance.is_silenced("d", "bot") is True


def test_recurring_window_inactive_outside_hours(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "windows:\n  - {target: 'd:bot', start: '02:00', duration_minutes: 120}\n")
    _at(monkeypatch, time.struct_time((2026, 6, 3, 5, 0, 0, 2, 154, -1)))  # 05:00, after window
    assert maintenance.scheduled_active() == []
    assert maintenance.is_silenced("d", "bot") is False


def test_recurring_day_filter(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "windows:\n  - {target: 'd:bot', days: [sun], start: '02:00', duration_minutes: 120}\n")
    _at(monkeypatch, time.struct_time((2026, 6, 3, 2, 30, 0, 2, 154, -1)))  # Wednesday
    assert maintenance.scheduled_active() == []  # not Sunday


def test_window_silences_via_wildcard(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "windows:\n  - {target: 'd:*', start: '02:00', duration_minutes: 120}\n")
    _at(monkeypatch, time.struct_time((2026, 6, 3, 2, 30, 0, 2, 154, -1)))
    assert maintenance.is_silenced("d", "anything") is True
    assert maintenance.is_silenced("other", "x") is False


def test_snapshot_includes_scheduled(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "windows:\n  - {target: 'd:bot', start: '02:00', duration_minutes: 120}\n")
    _at(monkeypatch, time.struct_time((2026, 6, 3, 2, 30, 0, 2, 154, -1)))
    snap = maintenance.snapshot()
    assert snap["scheduled"] and snap["scheduled"][0]["target"] == "d:bot"
