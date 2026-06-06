"""Command Hall snapshot — the data behind the immersive command center.

Heavy trading numbers (PnL by period, positions, exposure) are computed on the
client from the live project metrics; this endpoint supplies the rest: the
operator greeting, the monthly goal / account base, active trade opportunities,
and a unified recent-events intelligence feed. ``MAYBOT_DEMO=1`` fills vivid demo
values so the war room looks alive without a live trading bot wired up.
"""
from __future__ import annotations

import json
import os


def _demo() -> bool:
    return os.getenv("MAYBOT_DEMO", "0").strip().lower() in {"1", "true", "yes", "on"}


def opportunities() -> list[dict]:
    if _demo():
        return [
            {"ticker": "META", "edge": 4.3, "confidence": 96, "status": "EXECUTE"},
            {"ticker": "AMD", "edge": 3.2, "confidence": 92, "status": "READY"},
            {"ticker": "NVDA", "edge": 2.1, "confidence": 84, "status": "WATCHING"},
            {"ticker": "TSLA", "edge": 1.6, "confidence": 71, "status": "WATCHING"},
        ]
    raw = os.getenv("MAYBOT_OPPORTUNITIES", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def positions() -> list[dict]:
    """Open trading positions for the Trade Center floor (demo or env-supplied)."""
    if _demo():
        return [
            {"ticker": "NVDA", "side": "LONG", "qty": 40, "entry": 118.20, "last": 124.85, "pnl": 266.00, "pnl_pct": 5.63},
            {"ticker": "META", "side": "LONG", "qty": 18, "entry": 484.10, "last": 502.30, "pnl": 327.60, "pnl_pct": 3.76},
            {"ticker": "AMD", "side": "LONG", "qty": 60, "entry": 162.40, "last": 159.05, "pnl": -201.00, "pnl_pct": -2.06},
            {"ticker": "TSLA", "side": "SHORT", "qty": 25, "entry": 244.90, "last": 238.10, "pnl": 170.00, "pnl_pct": 2.78},
            {"ticker": "AAPL", "side": "LONG", "qty": 30, "entry": 211.30, "last": 214.95, "pnl": 109.50, "pnl_pct": 1.73},
        ]
    raw = os.getenv("MAYBOT_POSITIONS", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def bots() -> list[dict]:
    """Per-bot trading performance leaderboard (demo or env-supplied)."""
    if _demo():
        return [
            {"name": "Momentum Alpha", "pnl_today": 418.20, "pnl_month": 4192.80, "trades": 11, "win_rate": 73, "exposure": 6120.0, "status": "active"},
            {"name": "Mean Reversion", "pnl_today": 196.40, "pnl_month": 2310.60, "trades": 8, "win_rate": 64, "exposure": 4180.0, "status": "active"},
            {"name": "Vol Harvest", "pnl_today": 27.78, "pnl_month": 879.01, "trades": 4, "win_rate": 58, "exposure": 2180.0, "status": "throttled"},
        ]
    raw = os.getenv("MAYBOT_BOTS", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def events(limit: int = 14) -> list[dict]:
    out: list[dict] = []
    try:
        from . import autopilot
        for e in autopilot.status().get("log", [])[:8]:
            out.append({"icon": "🧠", "kind": e.get("kind", "autopilot"),
                        "text": f"{e.get('title', '')} — {e.get('message', '')}", "ts": e.get("ts")})
    except Exception:
        pass
    try:
        from . import comms
        for m in comms.get_feed(10):
            txt = f"{m.get('from', '')}: {str(m.get('content', ''))[:140]}"
            out.append({"icon": "⚡", "kind": m.get("kind", "comms"), "text": txt, "ts": m.get("ts")})
    except Exception:
        pass
    try:
        from . import inbound
        for a in inbound.recent(6):
            out.append({"icon": "📡", "kind": "alert",
                        "text": f"{a.get('source')}: {a.get('title')}", "ts": a.get("ts")})
    except Exception:
        pass
    out.sort(key=lambda e: -(e.get("ts") or 0))
    return out[:limit]


def snapshot() -> dict:
    demo = _demo()
    out = {
        "greeting_name": os.getenv("MAYBOT_USER", "Sect Master"),
        "monthly_goal": float(os.getenv("MAYBOT_MONTHLY_GOAL", "10000") or 10000),
        "account_base": float(os.getenv("MAYBOT_ACCOUNT_BASE", "0") or 0),
        "demo": demo,
        "opportunities": opportunities(),
        "positions": positions(),
        "bots": bots(),
        "events": events(),
    }
    if demo:  # vivid figures so the command center reads like a live trading floor
        out["pnl"] = {"today": 642.38, "week": 1814.22, "month": 7382.41, "total": 42182.15}
        out["trading"] = {"account_value": 42182.15, "buying_power": 18500.0, "exposure": 12480.0,
                          "positions": 7, "trades_today": 23, "win_rate": 68, "profit_factor": 2.4,
                          "risk": "Moderate", "bots": 3}
    return out
