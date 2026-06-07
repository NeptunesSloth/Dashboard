"""Control-center self-observability."""
import time

import pytest

from maybot_control_center import selfcheck


@pytest.fixture(autouse=True)
def _clean():
    selfcheck.clear()
    yield
    selfcheck.clear()


def test_initial_state_is_stale():
    snap = selfcheck.snapshot()
    assert snap["last_poll_age_seconds"] is None
    assert snap["poll_stale"] is True
    assert snap["poll_count"] == 0


def test_note_poll_updates_freshness():
    selfcheck.note_poll(42.0, devices=3, projects=9)
    snap = selfcheck.snapshot()
    assert snap["poll_count"] == 1
    assert snap["last_poll_duration_ms"] == 42.0
    assert snap["last_poll_devices"] == 3 and snap["last_poll_projects"] == 9
    assert snap["poll_stale"] is False
    assert snap["last_poll_age_seconds"] is not None


def test_request_counters():
    selfcheck.note_request(200)
    selfcheck.note_request(503)
    selfcheck.note_request(404)
    snap = selfcheck.snapshot()
    assert snap["api_requests"] == 3
    assert snap["api_errors"] == 1          # only the 5xx counts as an error


def test_staleness_threshold(monkeypatch):
    monkeypatch.setattr(selfcheck, "STALE_AFTER", 60.0)
    selfcheck.note_poll(1.0, 1, 1)
    assert selfcheck.is_stale() is False           # just polled
    # Backdate the last poll well beyond the threshold.
    selfcheck._last_poll_ts = time.time() - 600
    assert selfcheck.is_stale() is True
