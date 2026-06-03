"""Dao-Heart drift detection — behavioral / quality-regression detection.

A disciple cultivates a *Dao-Heart*: a stable temperament that should hold
steady as it acts. When a disciple's recent output starts to diverge from its
own established baseline — success rate collapsing, replies suddenly terse or
rambling, latency ballooning — the Dao-Heart has *drifted*, a tell-tale sign of
a quality regression or a personality slip (a "qi deviation").

Detection is pure analysis over recorded samples (no LLM). For each disciple we
keep a bounded history of recent samples, split it into an earlier *baseline*
half and a *recent* half, and compare the two halves on three axes:

  - success rate (did calls succeed),
  - mean output length (chars) — a big swing either way is a persona/quality
    drift proxy,
  - mean latency (ms).

The combined signals classify the disciple as ``insufficient`` (not enough
samples yet), ``stable``, ``drifting`` (a mild but real divergence) or
``degraded`` (a severe one).
"""
from __future__ import annotations

import os
import threading
import time

# Max samples kept per agent.
WINDOW = int(os.getenv("MAYBOT_DRIFT_WINDOW", "20"))
# Below this many samples, a disciple's status is "insufficient".
MIN_SAMPLES = int(os.getenv("MAYBOT_DRIFT_MIN_SAMPLES", "6"))

# --- Classification thresholds (module constants so they stay tunable). ---
# "degraded": a severe divergence.
DEGRADED_SUCCESS_DROP = 0.25      # recent pass rate fell this much (or more)
DEGRADED_LEN_RATIO_LOW = 0.5      # recent output collapsed below half
DEGRADED_LEN_RATIO_HIGH = 2.0     # recent output ballooned past double
# "drifting": a milder but real divergence.
DRIFT_SUCCESS_DROP = 0.1
DRIFT_LEN_RATIO_LOW = 0.7
DRIFT_LEN_RATIO_HIGH = 1.4
DRIFT_LATENCY_RISE_PCT = 50.0     # recent mean latency rose more than this %

_lock = threading.Lock()
_history: dict[str, list[dict]] = {}


def record(agent: str, sample: dict) -> None:
    """Append a sample to the agent's bounded history (keeps last WINDOW).

    A sample looks like ``{"ok": bool, "chars": int, "latency_ms": int}``; a
    ``ts`` is added if missing. Falsy agents and the human operator are skipped.
    """
    if not agent or agent == "operator":
        return
    rec = dict(sample or {})
    rec.setdefault("ts", int(time.time() * 1000))
    with _lock:
        hist = _history.setdefault(agent, [])
        hist.append(rec)
        if len(hist) > WINDOW:
            del hist[:-WINDOW]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _success_rate(samples: list[dict]) -> float:
    if not samples:
        return 0.0
    return sum(1 for s in samples if s.get("ok")) / len(samples)


def drift(agent: str) -> dict:
    """Compare an agent's earlier-half baseline against its recent half.

    Returns the classified status plus the raw signals that drove it.
    """
    with _lock:
        samples = list(_history.get(agent, []))
    n = len(samples)

    if n < MIN_SAMPLES:
        return {
            "agent": agent,
            "status": "insufficient",
            "samples": n,
            "signals": {
                "success_delta": 0.0,
                "length_ratio": 1.0,
                "latency_delta_pct": 0.0,
                "recent_success": round(_success_rate(samples), 3),
                "baseline_success": round(_success_rate(samples), 3),
            },
        }

    mid = n // 2
    baseline = samples[:mid]
    recent = samples[mid:]

    baseline_success = _success_rate(baseline)
    recent_success = _success_rate(recent)
    success_delta = recent_success - baseline_success

    baseline_chars = _mean([s.get("chars", 0) for s in baseline])
    recent_chars = _mean([s.get("chars", 0) for s in recent])
    if baseline_chars > 0:
        length_ratio = recent_chars / baseline_chars
    elif recent_chars > 0:
        length_ratio = float("inf")
    else:
        length_ratio = 1.0

    baseline_lat = _mean([s.get("latency_ms", 0) for s in baseline])
    recent_lat = _mean([s.get("latency_ms", 0) for s in recent])
    if baseline_lat > 0:
        latency_delta_pct = (recent_lat - baseline_lat) / baseline_lat * 100.0
    elif recent_lat > 0:
        latency_delta_pct = float("inf")
    else:
        latency_delta_pct = 0.0

    drop = -success_delta  # positive when success fell

    degraded = (
        drop >= DEGRADED_SUCCESS_DROP
        or length_ratio < DEGRADED_LEN_RATIO_LOW
        or length_ratio > DEGRADED_LEN_RATIO_HIGH
    )
    drifting = (
        drop >= DRIFT_SUCCESS_DROP
        or length_ratio < DRIFT_LEN_RATIO_LOW
        or length_ratio > DRIFT_LEN_RATIO_HIGH
        or latency_delta_pct > DRIFT_LATENCY_RISE_PCT
    )

    if degraded:
        status = "degraded"
    elif drifting:
        status = "drifting"
    else:
        status = "stable"

    def _r(x: float) -> float:
        return x if x == float("inf") else round(x, 3)

    return {
        "agent": agent,
        "status": status,
        "samples": n,
        "signals": {
            "success_delta": round(success_delta, 3),
            "length_ratio": _r(length_ratio),
            "latency_delta_pct": _r(latency_delta_pct),
            "recent_success": round(recent_success, 3),
            "baseline_success": round(baseline_success, 3),
        },
    }


def snapshot() -> dict:
    """``{agent: drift(agent)}`` for every agent with recorded samples."""
    with _lock:
        agents = list(_history.keys())
    return {agent: drift(agent) for agent in agents}


def clear() -> None:
    """Reset all module state (used by tests)."""
    with _lock:
        _history.clear()
