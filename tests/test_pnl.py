"""Tests for the PnL time-series recorder (offline, in-memory)."""
from __future__ import annotations

from maybot_control_center import pnl_history


def _snap(total: float, today: float, positions: list[dict]) -> dict:
    """Build a minimal command.snapshot()-shaped dict."""
    return {"pnl": {"today": today, "total": total}, "positions": positions}


def test_record_series_and_summary() -> None:
    pnl_history.clear()
    assert pnl_history.summary()["samples"] == 0
    assert pnl_history.series("total") == []

    # First sample: one position -> exposure = |40 * 124.85| = 4994.0
    pnl_history.record(_snap(
        total=42000.0, today=600.0,
        positions=[{"ticker": "NVDA", "qty": 40, "last": 124.85}],
    ))
    # Second sample: a long + a short -> exposure sums absolute notionals.
    pnl_history.record(_snap(
        total=42500.0, today=1100.0,
        positions=[
            {"ticker": "META", "qty": 18, "last": 502.30},   # 9041.4
            {"ticker": "TSLA", "qty": 25, "last": 238.10},   # 5952.5
        ],
    ))

    # total series returns recorded points in order.
    totals = pnl_history.series("total")
    assert [round(p["value"], 2) for p in totals] == [42000.0, 42500.0]

    # equity_curve is the convenience alias for the total series.
    eq = pnl_history.equity_curve()
    assert [round(p["value"], 2) for p in eq] == [42000.0, 42500.0]

    # today series tracks the daily PnL.
    today = pnl_history.series("today")
    assert [round(p["value"], 2) for p in today] == [600.0, 1100.0]

    # exposure computed from positions (sum of abs(qty * last)).
    exposure = pnl_history.series("exposure")
    assert round(exposure[0]["value"], 2) == 4994.0
    assert round(exposure[1]["value"], 2) == round(9041.4 + 5952.5, 2)

    # summary stats over the total series.
    summ = pnl_history.summary()
    assert summ["samples"] == 2
    assert round(summ["min"], 2) == 42000.0
    assert round(summ["max"], 2) == 42500.0
    assert round(summ["last"], 2) == 42500.0
    assert summ["first_ts"] is not None and summ["last_ts"] is not None

    # ts ordering: first sample is no later than the second.
    assert totals[0]["ts"] <= totals[1]["ts"]


def test_unknown_metric_falls_back_to_total() -> None:
    pnl_history.clear()
    pnl_history.record(_snap(total=100.0, today=5.0, positions=[]))
    assert pnl_history.series("bogus")[0]["value"] == 100.0


def test_record_never_raises_on_bad_input() -> None:
    pnl_history.clear()
    pnl_history.record({})            # missing keys
    pnl_history.record({"pnl": None, "positions": "nope"})  # wrong types
    # Both should be recorded as zeroed samples without raising.
    assert pnl_history.summary()["samples"] == 2
    pnl_history.clear()
