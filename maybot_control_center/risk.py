"""Risk engine & global kill-switch — the sect's "Heavenly Decree" over trades.

The trading floor may run hot, but the sect keeps a hand on the great seal. This
module measures the fleet's *peril* — total gross exposure, drawdown from a
tracked equity high-water mark — and, when the peril breaches the decreed limits
(or an operator throws the kill-switch), it **halts** the floor: ``can_trade``
turns to ``False`` and no disciple may open a new position.

All state is in-memory and module-level (mirroring :mod:`errorbudget` /
:mod:`audit`); functions are pure-ish and never throw. Limits come from env:

- ``MAYBOT_MAX_DRAWDOWN_PCT`` (default 15.0) — halt past this % drawdown.
- ``MAYBOT_MAX_EXPOSURE`` (default 0 = unlimited) — total $ gross-exposure cap.
- ``MAYBOT_MAX_BOT_EXPOSURE`` (default 0 = unlimited) — per-bot $ exposure cap.
"""
from __future__ import annotations

import os
import threading
import time

_lock = threading.Lock()

# --- equity high-water mark, tracked across calls so drawdown is meaningful ---
_hwm: float = 0.0

# --- global kill-switch state ---
_kill: dict = {"on": False, "actor": "", "ts": 0}


def max_drawdown_pct() -> float:
    """Decreed maximum drawdown % before the floor is halted."""
    try:
        return float(os.getenv("MAYBOT_MAX_DRAWDOWN_PCT", "15.0"))
    except ValueError:
        return 15.0


def max_exposure() -> float:
    """Total gross-exposure cap in $ (0 = unlimited)."""
    try:
        return float(os.getenv("MAYBOT_MAX_EXPOSURE", "0"))
    except ValueError:
        return 0.0


def max_bot_exposure() -> float:
    """Per-bot gross-exposure cap in $ (0 = unlimited)."""
    try:
        return float(os.getenv("MAYBOT_MAX_BOT_EXPOSURE", "0"))
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Kill-switch
# --------------------------------------------------------------------------- #
def kill_switch(on: bool, actor: str = "system") -> dict:
    """Throw (or release) the global kill-switch. Returns the new status."""
    with _lock:
        _kill["on"] = bool(on)
        _kill["actor"] = actor or "system"
        _kill["ts"] = int(time.time() * 1000)
        snap = dict(_kill)
    try:
        from . import store
        store.save_state("risk_kill", snap)   # a halt must survive a restart
    except Exception:
        pass
    return status()


def load_persisted() -> None:
    try:
        from . import store
        data = store.load_state("risk_kill")
    except Exception:
        data = None
    if isinstance(data, dict):
        with _lock:
            _kill.update({k: data[k] for k in ("on", "actor", "ts") if k in data})


def is_halted() -> bool:
    """True when the kill-switch is engaged (manual halt only)."""
    with _lock:
        return bool(_kill["on"])


def can_trade(bot_name: str = "") -> bool:
    """Whether a (named) bot may open new positions. False once halted."""
    return not is_halted()


def status() -> dict:
    """Current kill-switch state plus configured limits and the live hwm."""
    with _lock:
        return {
            "kill_switch": bool(_kill["on"]),
            "actor": _kill["actor"],
            "ts": _kill["ts"],
            "hwm": _hwm,
            "limits": {
                "max_drawdown_pct": max_drawdown_pct(),
                "max_exposure": max_exposure(),
                "max_bot_exposure": max_bot_exposure(),
            },
        }


def reset_hwm() -> None:
    """Forget the tracked equity high-water mark (start a fresh window)."""
    global _hwm
    with _lock:
        _hwm = 0.0


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def _num(value: object, default: float = 0.0) -> float:
    """Coerce a value to float without throwing."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _position_exposure(pos: dict) -> float:
    """Gross $ exposure of a single position: abs(qty * last)."""
    qty = _num(pos.get("qty"))
    # Prefer the live mark ("last"); fall back to entry price if absent.
    price = pos.get("last")
    if price is None:
        price = pos.get("entry")
    return abs(qty * _num(price))


def _equity_from(positions: list[dict], account: dict | None) -> float:
    """Best-effort current equity: account["equity"] if present, else PnL sum."""
    if account and account.get("equity") is not None:
        return _num(account.get("equity"))
    # No account equity supplied — approximate with cumulative position PnL.
    return sum(_num(p.get("pnl")) for p in (positions or []))


def evaluate(positions: list[dict], account: dict | None = None,
             bots: list[dict] | None = None) -> dict:
    """Assess fleet risk and decide whether the floor must halt.

    Computes total gross exposure (sum of abs(qty*last)), the current drawdown %
    measured against a tracked equity high-water mark, and per-bot exposure
    breaches. ``halted`` is True if the kill-switch is engaged OR drawdown
    breaches the decreed maximum OR total exposure breaches the cap.
    """
    global _hwm
    positions = positions or []

    # --- total gross exposure ---
    exposure = round(sum(_position_exposure(p) for p in positions), 2)

    # --- drawdown vs. a persistent equity high-water mark ---
    equity = _equity_from(positions, account)
    with _lock:
        if equity > _hwm:
            _hwm = equity
        hwm = _hwm
    drawdown_pct = 0.0
    if hwm > 0:
        drawdown_pct = round(max(0.0, (hwm - equity) / hwm * 100.0), 2)

    reasons: list[str] = []
    breaches: list[dict] = []

    # --- kill-switch (manual decree) ---
    if is_halted():
        reasons.append("kill_switch engaged")

    # --- drawdown breach ---
    dd_cap = max_drawdown_pct()
    if dd_cap > 0 and drawdown_pct >= dd_cap:
        reasons.append(f"drawdown {drawdown_pct:.2f}% >= max {dd_cap:.2f}%")
        breaches.append({"type": "drawdown",
                         "detail": f"{drawdown_pct:.2f}% >= {dd_cap:.2f}%"})

    # --- total exposure breach ---
    exp_cap = max_exposure()
    if exp_cap > 0 and exposure > exp_cap:
        reasons.append(f"exposure {exposure:.2f} > cap {exp_cap:.2f}")
        breaches.append({"type": "exposure",
                         "detail": f"{exposure:.2f} > {exp_cap:.2f}"})

    # --- per-bot exposure breaches (informational; do not halt the whole floor) ---
    bot_breaches: list[dict] = []
    bot_cap = max_bot_exposure()
    if bot_cap > 0:
        for b in (bots or []):
            bexp = _num(b.get("exposure"))
            if bexp > bot_cap:
                bot_breaches.append({"bot": b.get("name", "?"), "exposure": round(bexp, 2)})

    halted = bool(reasons)
    return {
        "halted": halted,
        "reasons": reasons,
        "exposure": exposure,
        "drawdown_pct": drawdown_pct,
        "hwm": round(hwm, 2),
        "breaches": breaches,
        "bot_breaches": bot_breaches,
    }
