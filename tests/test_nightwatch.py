from __future__ import annotations


from maybot_control_center import nightwatch
from maybot_control_center import cultivation


def setup_function():
    nightwatch.clear()
    cultivation.clear()


def _epoch() -> float:
    # The rotation epoch is reset to now by set_rotation; read it for exact
    # shift-boundary arithmetic in tests.
    return nightwatch._epoch


def test_empty_rotation_gives_none_and_unassigned():
    assert nightwatch.current_watcher() is None
    assert nightwatch.next_watcher() is None
    assert nightwatch.shift_remaining() == 0
    rec = nightwatch.triage({"project": "p", "severity": "warning"})
    assert rec["watcher"] is None
    assert rec["status"] == "unassigned"
    st = nightwatch.status()
    assert st["rotation"] == []
    assert st["current"] is None and st["next"] is None
    assert st["open"] == 1


def test_set_rotation_dedups_and_drops_falsy():
    st = nightwatch.set_rotation(["a", "", "b", "a", None, "c"])
    assert st["rotation"] == ["a", "b", "c"]
    assert st["shift_seconds"] == nightwatch.SHIFT_SECONDS
    assert st["current"] == "a"
    assert st["next"] == "b"


def test_rotation_advances_by_shift():
    nightwatch.set_rotation(["a", "b", "c"])
    e = _epoch()
    s = nightwatch.SHIFT_SECONDS
    assert nightwatch.current_watcher(now=e) == "a"
    assert nightwatch.next_watcher(now=e) == "b"
    # Halfway through the first shift: still 'a'.
    assert nightwatch.current_watcher(now=e + s / 2) == "a"
    # Into the second shift: 'b'.
    assert nightwatch.current_watcher(now=e + s + 1) == "b"
    assert nightwatch.next_watcher(now=e + s + 1) == "c"
    # Third shift: 'c'.
    assert nightwatch.current_watcher(now=e + 2 * s + 1) == "c"


def test_rotation_wraps_around_with_modulo():
    nightwatch.set_rotation(["a", "b", "c"])
    e = _epoch()
    s = nightwatch.SHIFT_SECONDS
    # After 3 shifts, wrap back to 'a'.
    assert nightwatch.current_watcher(now=e + 3 * s + 1) == "a"
    assert nightwatch.next_watcher(now=e + 3 * s + 1) == "b"
    # next() wraps from last back to first.
    assert nightwatch.next_watcher(now=e + 2 * s + 1) == "a"
    # Far in the future still wraps correctly.
    assert nightwatch.current_watcher(now=e + 100 * s + 5) == ["a", "b", "c"][100 % 3]


def test_shift_remaining_counts_down():
    nightwatch.set_rotation(["a"])
    e = _epoch()
    s = nightwatch.SHIFT_SECONDS
    assert nightwatch.shift_remaining(now=e) == s
    assert nightwatch.shift_remaining(now=e + 10) == s - 10
    # At a shift boundary it resets to a full shift.
    assert nightwatch.shift_remaining(now=e + s) == s


def test_triage_warning_is_auto_triaged():
    nightwatch.set_rotation(["a", "b"])
    e = _epoch()
    rec = nightwatch.triage({"project": "p", "severity": "warning"}, now=e)
    assert rec["watcher"] == "a"
    assert rec["status"] == "auto_triaged"
    assert rec["id"] == 0
    assert isinstance(rec["ts"], int)


def test_triage_error_is_escalated():
    nightwatch.set_rotation(["a", "b"])
    e = _epoch()
    rec = nightwatch.triage({"project": "p", "severity": "error"}, now=e)
    assert rec["watcher"] == "a"
    assert rec["status"] == "escalated"


def test_triage_missing_severity_is_auto_triaged():
    nightwatch.set_rotation(["a"])
    rec = nightwatch.triage({"project": "p"})
    assert rec["status"] == "auto_triaged"


def test_triage_assigns_to_current_watcher_per_shift():
    nightwatch.set_rotation(["a", "b"])
    e = _epoch()
    s = nightwatch.SHIFT_SECONDS
    r0 = nightwatch.triage({"severity": "warning"}, now=e)
    r1 = nightwatch.triage({"severity": "warning"}, now=e + s + 1)
    assert r0["watcher"] == "a"
    assert r1["watcher"] == "b"
    assert r1["id"] == 1


def test_ids_increment_and_log_returns_copies():
    nightwatch.set_rotation(["a"])
    nightwatch.triage({"severity": "warning"})
    nightwatch.triage({"severity": "error"})
    entries = nightwatch.log()
    assert [r["id"] for r in entries] == [0, 1]
    # Mutating a returned copy must not affect internal state.
    entries[0]["status"] = "mutated"
    assert nightwatch.log()[0]["status"] != "mutated"


def test_log_limit():
    nightwatch.set_rotation(["a"])
    for _ in range(5):
        nightwatch.triage({"severity": "warning"})
    assert len(nightwatch.log(limit=2)) == 2
    assert [r["id"] for r in nightwatch.log(limit=2)] == [3, 4]


def test_handled_marks_resolved_and_rewards_watcher():
    nightwatch.set_rotation(["disciple_x"])
    e = _epoch()
    rec = nightwatch.triage({"severity": "warning"}, now=e)
    before = cultivation.state("disciple_x")["stones"]
    assert nightwatch.handled(rec["id"]) is True
    after = cultivation.state("disciple_x")["stones"]
    assert after == before + nightwatch.AWARD
    # Record is now resolved.
    resolved = next(r for r in nightwatch.log() if r["id"] == rec["id"])
    assert resolved["status"] == "resolved"


def test_handled_unknown_id_returns_false():
    nightwatch.set_rotation(["a"])
    assert nightwatch.handled(999) is False


def test_handled_skips_reward_for_unassigned():
    # Empty rotation -> watcher None -> no reward, but still resolves.
    rec = nightwatch.triage({"severity": "warning"})
    assert rec["watcher"] is None
    assert nightwatch.handled(rec["id"]) is True
    assert nightwatch.log()[0]["status"] == "resolved"


def test_handled_skips_reward_for_operator():
    nightwatch.set_rotation(["operator"])
    rec = nightwatch.triage({"severity": "warning"})
    before = cultivation.state("operator")["stones"]
    assert nightwatch.handled(rec["id"]) is True
    assert cultivation.state("operator")["stones"] == before


def test_status_open_count():
    nightwatch.set_rotation(["a"])
    r0 = nightwatch.triage({"severity": "warning"})
    nightwatch.triage({"severity": "error"})
    assert nightwatch.status()["open"] == 2
    nightwatch.handled(r0["id"])
    assert nightwatch.status()["open"] == 1


def test_clear_resets_everything():
    nightwatch.set_rotation(["a", "b"])
    nightwatch.triage({"severity": "warning"})
    nightwatch.clear()
    assert nightwatch.status()["rotation"] == []
    assert nightwatch.log() == []
    # id counter reset.
    nightwatch.set_rotation(["a"])
    assert nightwatch.triage({"severity": "warning"})["id"] == 0
