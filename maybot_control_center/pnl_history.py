"""PnL time-series recording + retrieval for the analytics panels.

This module keeps a rolling, in-process time series of equity / daily-PnL /
exposure samples derived from :func:`command.snapshot`. It works purely
in-memory by default, and — when the optional SQLite persistence in
:mod:`maybot_control_center.store` is enabled (``MAYBOT_DB`` set) — it writes
the series through to the generic ``state`` blob so it survives a restart.

Everything here is best-effort: recording must never raise into the request
path, so :func:`record` swallows its own errors.
"""
from __future__ import annotations

import os
import time
from typing import Any

# Module key used for the generic per-module JSON blob in store.py.
_STATE_MODULE = "pnl_history"

# In-process series. Each entry is a sample dict:
#   {"ts": float, "total": float, "today": float, "exposure": float}
_history: list[dict[str, float]] = []

# Whether we've already attempted to hydrate from the store this process.
_loaded = False


def _max_samples() -> int:
    """Cap on retained samples (env override, sane default)."""
    try:
        return max(1, int(os.getenv("MAYBOT_PNL_HISTORY_MAX", "2000")))
    except Exception:
        return 2000


def _store():
    """Return the store module if importable, else ``None`` (best-effort)."""
    try:
        from . import store  # local import to avoid hard dependency / cycles
        return store
    except Exception:
        return None


def _ensure_loaded() -> None:
    """Hydrate the in-memory series from the store once, if persistence is on."""
    global _loaded, _history
    if _loaded:
        return
    _loaded = True
    st = _store()
    if st is None or not getattr(st, "enabled", lambda: False)():
        return
    try:
        data = st.load_state(_STATE_MODULE)
        if isinstance(data, list):
            # Keep only well-formed sample dicts.
            _history = [d for d in data if isinstance(d, dict) and "ts" in d]
    except Exception:
        pass


def _persist() -> None:
    """Write the series through to the store, if persistence is enabled."""
    st = _store()
    if st is None or not getattr(st, "enabled", lambda: False)():
        return
    try:
        st.save_state(_STATE_MODULE, _history)
    except Exception:
        pass


def _exposure_from_positions(positions: Any) -> float:
    """Sum of abs(qty * last) across open positions (gross market exposure)."""
    total = 0.0
    if not isinstance(positions, list):
        return 0.0
    for p in positions:
        if not isinstance(p, dict):
            continue
        try:
            qty = float(p.get("qty") or 0)
            last = float(p.get("last") or 0)
            total += abs(qty * last)
        except (TypeError, ValueError):
            continue
    return total


def record(snapshot: dict) -> None:
    """Append one sample derived from a ``command.snapshot()`` dict.

    Pulls equity ("total"), daily PnL ("today") and computes gross exposure
    from the snapshot's positions. Caps history at ``MAYBOT_PNL_HISTORY_MAX``
    and persists when a store is available. Never raises.
    """
    try:
        _ensure_loaded()
        snap = snapshot if isinstance(snapshot, dict) else {}
        pnl = snap.get("pnl") if isinstance(snap.get("pnl"), dict) else {}

        # Equity: prefer explicit "equity", fall back to pnl["total"].
        equity = snap.get("equity", pnl.get("total", 0))
        try:
            total = float(equity or 0)
        except (TypeError, ValueError):
            total = 0.0

        try:
            today = float(pnl.get("today") or 0)
        except (TypeError, ValueError):
            today = 0.0

        exposure = _exposure_from_positions(snap.get("positions"))

        sample: dict[str, float] = {
            "ts": float(time.time()),
            "total": total,
            "today": today,
            "exposure": exposure,
        }
        _history.append(sample)

        # Trim oldest entries beyond the cap.
        cap = _max_samples()
        if len(_history) > cap:
            del _history[: len(_history) - cap]

        _persist()
    except Exception:
        # Best-effort: recording must never break the caller.
        pass


def series(metric: str = "total", limit: int = 500) -> list[dict]:
    """Return ``[{"ts", "value"}]`` for one metric, most-recent ``limit`` points.

    ``metric`` is one of ``"total"``, ``"today"`` or ``"exposure"`` (anything
    else falls back to ``"total"``).
    """
    _ensure_loaded()
    key = metric if metric in ("total", "today", "exposure") else "total"
    try:
        lim = max(0, int(limit))
    except (TypeError, ValueError):
        lim = 500
    window = _history[-lim:] if lim else []
    return [{"ts": s.get("ts"), "value": s.get(key, 0.0)} for s in window]


def equity_curve(limit: int = 500) -> list[dict]:
    """Convenience wrapper for the total-equity series."""
    return series("total", limit)


def summary() -> dict:
    """Summary stats over the full total-equity series."""
    _ensure_loaded()
    values = [s.get("total", 0.0) for s in _history]
    if not _history:
        return {"samples": 0, "first_ts": None, "last_ts": None,
                "min": None, "max": None, "last": None}
    return {
        "samples": len(_history),
        "first_ts": _history[0].get("ts"),
        "last_ts": _history[-1].get("ts"),
        "min": min(values),
        "max": max(values),
        "last": values[-1],
    }


def clear() -> None:
    """Drop the in-memory series (and persisted copy). Used by tests."""
    global _history
    _history = []
    _persist()
