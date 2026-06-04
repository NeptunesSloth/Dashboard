"""Per-agent LLM usage & cost tracking.

``agents._chat`` records every call here: latency, success/failure, token
counts (when the backend reports them — Claude always; OpenAI-compatible and
Ollama when present), and an estimated cost from a per-model price table.
Surfaced at ``/api/usage`` and on the dashboard. Local models cost $0.
"""
from __future__ import annotations

import threading
import time

from . import store

# USD per 1K tokens, (input, output). Anything not listed (local models) is free.
PRICES = {
    "claude-opus-4-8": (0.005, 0.025),
    "claude-opus-4-7": (0.005, 0.025),
    "claude-opus-4-6": (0.005, 0.025),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.001, 0.005),
}

_lock = threading.Lock()
_agents: dict[str, dict] = {}
# Hourly time-series buckets: hour-epoch (seconds) -> aggregate. Bounded so memory
# can't grow without limit; powers the cost/token-over-time chart.
_series: dict[int, dict] = {}
SERIES_CAP = 24 * 14  # keep up to two weeks of hourly buckets
HOUR = 3600


def _bucket(ts_ms: int, ok, tin: int, tout: int, cost: float) -> None:
    hour = (int(ts_ms / 1000) // HOUR) * HOUR
    b = _series.get(hour)
    if b is None:
        b = {"hour": hour, "calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0}
        _series[hour] = b
    b["calls"] += 1
    if not ok:
        b["errors"] += 1
    b["tokens_in"] += tin
    b["tokens_out"] += tout
    b["cost"] = round(b["cost"] + cost, 6)
    if len(_series) > SERIES_CAP:                  # drop the oldest buckets
        for h in sorted(_series)[:len(_series) - SERIES_CAP]:
            del _series[h]


def cost_for(model: str, tin: int, tout: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return round((tin / 1000.0) * pin + (tout / 1000.0) * pout, 6)


def _blank(agent: str) -> dict:
    return {"agent": agent, "calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0,
            "cost": 0.0, "latency_ms": 0, "last_ts": 0, "models": {}}


def _apply(agent: str, model: str, ok, latency_ms: int, tin: int, tout: int, cost: float, ts: int) -> None:
    a = _agents.get(agent) or _blank(agent)
    a["calls"] += 1
    if not ok:
        a["errors"] += 1
    a["tokens_in"] += tin
    a["tokens_out"] += tout
    a["cost"] = round(a["cost"] + cost, 6)
    a["latency_ms"] += latency_ms
    a["last_ts"] = max(a["last_ts"], ts)
    a["models"][model] = a["models"].get(model, 0) + 1
    _agents[agent] = a
    _bucket(ts, ok, tin, tout, cost)


def record(agent: str, model: str, ok: bool, latency_ms: int, tin: int = 0, tout: int = 0) -> None:
    tin, tout = tin or 0, tout or 0
    cost = cost_for(model, tin, tout)
    ts = int(time.time() * 1000)
    with _lock:
        _apply(agent, model, ok, latency_ms, tin, tout, cost, ts)
    if store.enabled():
        store.add_usage(agent, model, ok, latency_ms, tin, tout, cost, ts)


def snapshot() -> dict:
    with _lock:
        rows = []
        for a in _agents.values():
            calls = a["calls"] or 1
            rows.append({
                "agent": a["agent"], "calls": a["calls"], "errors": a["errors"],
                "tokens_in": a["tokens_in"], "tokens_out": a["tokens_out"], "cost": a["cost"],
                "avg_latency_ms": round(a["latency_ms"] / calls),
                "success_pct": round(100 * (a["calls"] - a["errors"]) / calls),
                "models": a["models"], "last_ts": a["last_ts"],
            })
        rows.sort(key=lambda r: -r["cost"])
        totals = {
            "calls": sum(a["calls"] for a in _agents.values()),
            "tokens_in": sum(a["tokens_in"] for a in _agents.values()),
            "tokens_out": sum(a["tokens_out"] for a in _agents.values()),
            "cost": round(sum(a["cost"] for a in _agents.values()), 4),
        }
    return {"agents": rows, "totals": totals}


def series(hours: int = 24) -> dict:
    """Hourly cost/token/call buckets for the last ``hours`` hours, oldest first,
    with empty hours zero-filled so the chart has a continuous timeline."""
    hours = max(1, min(hours, SERIES_CAP))
    now_hour = (int(time.time()) // HOUR) * HOUR
    with _lock:
        buckets = []
        for i in range(hours - 1, -1, -1):
            h = now_hour - i * HOUR
            b = _series.get(h)
            buckets.append({"hour": h, "calls": b["calls"] if b else 0,
                            "errors": b["errors"] if b else 0,
                            "tokens_in": b["tokens_in"] if b else 0,
                            "tokens_out": b["tokens_out"] if b else 0,
                            "cost": round(b["cost"], 6) if b else 0.0})
    totals = {
        "cost": round(sum(b["cost"] for b in buckets), 6),
        "calls": sum(b["calls"] for b in buckets),
        "tokens": sum(b["tokens_in"] + b["tokens_out"] for b in buckets),
        "errors": sum(b["errors"] for b in buckets),
    }
    return {"hours": hours, "buckets": buckets, "totals": totals}


def load_persisted() -> None:
    if not store.enabled():
        return
    with _lock:
        for agent, model, ok, lat, tin, tout, cost, ts in store.load_usage():
            _apply(agent, model, bool(ok), lat, tin, tout, cost, ts)


def clear() -> None:
    with _lock:
        _agents.clear()
        _series.clear()
