from __future__ import annotations

from maybot_control_center import daoheart


def setup_function():
    daoheart.clear()


def _s(ok: bool = True, chars: int = 100, latency_ms: int = 100) -> dict:
    return {"ok": ok, "chars": chars, "latency_ms": latency_ms}


def test_insufficient_when_too_few_samples():
    for _ in range(daoheart.MIN_SAMPLES - 1):
        daoheart.record("ay", _s())
    d = daoheart.drift("ay")
    assert d["status"] == "insufficient"
    assert d["agent"] == "ay"
    assert d["samples"] == daoheart.MIN_SAMPLES - 1


def test_stable_when_consistent():
    for _ in range(10):
        daoheart.record("ay", _s(ok=True, chars=100, latency_ms=100))
    d = daoheart.drift("ay")
    assert d["status"] == "stable"
    assert d["signals"]["success_delta"] == 0.0
    assert d["signals"]["length_ratio"] == 1.0
    assert d["signals"]["latency_delta_pct"] == 0.0


def test_degraded_when_recent_failures_spike():
    for _ in range(5):
        daoheart.record("ay", _s(ok=True))
    for _ in range(5):
        daoheart.record("ay", _s(ok=False))
    d = daoheart.drift("ay")
    assert d["status"] == "degraded"
    assert d["signals"]["baseline_success"] == 1.0
    assert d["signals"]["recent_success"] == 0.0
    assert d["signals"]["success_delta"] == -1.0


def test_degraded_when_length_collapses():
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=200))
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=50))  # ratio 0.25 < 0.5
    d = daoheart.drift("ay")
    assert d["status"] == "degraded"
    assert d["signals"]["length_ratio"] == 0.25


def test_degraded_when_length_balloons():
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=100))
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=300))  # ratio 3.0 > 2.0
    d = daoheart.drift("ay")
    assert d["status"] == "degraded"
    assert d["signals"]["length_ratio"] == 3.0


def test_drifting_on_mild_success_dip():
    # baseline all ok, recent one failure out of five -> drop 0.2 (>=0.1, <0.25)
    for _ in range(5):
        daoheart.record("ay", _s(ok=True))
    daoheart.record("ay", _s(ok=False))
    for _ in range(4):
        daoheart.record("ay", _s(ok=True))
    d = daoheart.drift("ay")
    assert d["status"] == "drifting"
    assert d["signals"]["success_delta"] == -0.2


def test_drifting_on_latency_rise():
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=100, latency_ms=100))
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=100, latency_ms=200))  # +100%
    d = daoheart.drift("ay")
    assert d["status"] == "drifting"
    assert d["signals"]["latency_delta_pct"] == 100.0


def test_drifting_on_mild_length_swing():
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=100))
    for _ in range(5):
        daoheart.record("ay", _s(ok=True, chars=150))  # ratio 1.5, in drift band
    d = daoheart.drift("ay")
    assert d["status"] == "drifting"
    assert d["signals"]["length_ratio"] == 1.5


def test_window_bounds_stored_history():
    for i in range(daoheart.WINDOW + 10):
        daoheart.record("ay", _s(ok=True, chars=i))
    assert len(daoheart._history["ay"]) == daoheart.WINDOW
    # oldest were dropped: first kept sample is char index 10
    assert daoheart._history["ay"][0]["chars"] == 10


def test_record_adds_ts_if_missing():
    daoheart.record("ay", {"ok": True, "chars": 10, "latency_ms": 5})
    assert "ts" in daoheart._history["ay"][0]
    daoheart.record("by", {"ok": True, "ts": 42})
    assert daoheart._history["by"][0]["ts"] == 42


def test_record_skips_falsy_and_operator():
    daoheart.record("", _s())
    daoheart.record(None, _s())  # type: ignore[arg-type]
    daoheart.record("operator", _s())
    assert daoheart._history == {}


def test_snapshot_accumulates_all_agents():
    for _ in range(10):
        daoheart.record("ay", _s(ok=True))
        daoheart.record("by", _s(ok=True))
    daoheart.record("cy", _s())  # too few -> insufficient
    snap = daoheart.snapshot()
    assert set(snap.keys()) == {"ay", "by", "cy"}
    assert snap["ay"]["status"] == "stable"
    assert snap["cy"]["status"] == "insufficient"


def test_clear_empties_state():
    for _ in range(8):
        daoheart.record("ay", _s())
    daoheart.clear()
    assert daoheart._history == {}
    assert daoheart.snapshot() == {}
    assert daoheart.drift("ay")["status"] == "insufficient"
