"""Tribulation Trials: chaos engineering / game-day for the sect.

A **tribulation trial** deliberately injects a fault scenario against a target
(a project or disciple's domain) and *scores how well it is weathered* — chiefly
by recovery time. Surviving a trial swiftly rewards spirit stones; failing one
calls a misstep down on the disciple's head (a fail-streak that can invite a
heavenly tribulation in :mod:`cultivation`).

This module manages only the **lifecycle + scoring** of trials. It does NOT kill
processes, inject latency, or fill disks — you run the real fault yourself and
then :func:`resolve` the trial with the observed outcome.
"""
from __future__ import annotations

import os
import threading
import time

# Catalog of fault kinds a tribulation trial may inflict.
TRIALS = {
    "process_kill": "Strike down the process (simulate a crash)",
    "latency_storm": "Flood the realm with latency",
    "disk_drought": "Exhaust spirit-stone storage (disk)",
    "endpoint_seal": "Seal an endpoint (simulate an outage)",
}

# Recovering within this many seconds earns full marks (score 100).
RECOVER_TARGET = int(os.getenv("MAYBOT_CHAOS_TARGET_SECONDS", "120"))
# Spirit-stone reward for a perfectly weathered trial (scaled by score).
REWARD = int(os.getenv("MAYBOT_CHAOS_REWARD", "30"))
# We don't punish stones directly for a failed trial — cultivation.on_task does
# the disciplining — but the knob exists for symmetry/tuning.
PENALTY = int(os.getenv("MAYBOT_CHAOS_PENALTY", "0"))

_lock = threading.Lock()
_trials: list[dict] = []
_next_id = 1


def catalog() -> dict:
    """Return the catalog of available fault kinds."""
    return TRIALS


def summon(target: str, kind: str, disciple: str | None = None) -> dict:
    """Summon (start) a tribulation trial against ``target``.

    ``kind`` must be a key of :data:`TRIALS` and ``target`` must be non-empty,
    else :class:`ValueError`. Returns a copy of the created record.
    """
    if kind not in TRIALS:
        raise ValueError(f"unknown trial kind: {kind!r}")
    if not target:
        raise ValueError("target must be non-empty")
    global _next_id
    now = int(time.time() * 1000)
    with _lock:
        rec = {
            "id": _next_id,
            "target": target,
            "kind": kind,
            "disciple": disciple,
            "status": "active",
            "summoned_at": now,
            "resolved_at": None,
            "recovery_seconds": None,
            "score": None,
        }
        _next_id += 1
        _trials.append(rec)
        return dict(rec)


def _score(recovery_seconds: float | None) -> int:
    """Score 0-100 from recovery time (full marks within RECOVER_TARGET)."""
    if recovery_seconds is None:
        return 100
    return round(max(0, min(100, 100 * RECOVER_TARGET / max(recovery_seconds, 1))))


def resolve(trial_id: int, recovered: bool, recovery_seconds: float | None = None) -> dict:
    """Resolve a trial with the observed outcome. Returns a copy of the record.

    Raises :class:`KeyError` if no trial has ``trial_id``. A weathered trial
    rewards the disciple proportional to its score; a failed trial marks a
    misstep via ``cultivation.on_task(disciple, False)``.
    """
    now = int(time.time() * 1000)
    with _lock:
        rec = next((t for t in _trials if t["id"] == trial_id), None)
        if rec is None:
            raise KeyError(trial_id)
        rec["resolved_at"] = now
        disciple = rec["disciple"]
        if recovered:
            score = _score(recovery_seconds)
            rec["status"] = "weathered"
            rec["recovery_seconds"] = recovery_seconds
            rec["score"] = score
            scaled = round(REWARD * score / 100)
        else:
            rec["status"] = "failed"
            rec["recovery_seconds"] = recovery_seconds
            rec["score"] = 0
            scaled = None
        snap = dict(rec)

    # Lazy-import cultivation outside the lock to avoid cycles + reentrancy.
    if disciple and disciple != "operator":
        from . import cultivation
        if recovered:
            if scaled:
                cultivation.reward(disciple, scaled)
        else:
            cultivation.on_task(disciple, False)
    return snap


def active() -> list[dict]:
    """Return copies of all currently active trials."""
    with _lock:
        return [dict(t) for t in _trials if t["status"] == "active"]


def history(limit: int = 50) -> list[dict]:
    """Return copies of the most recent trials (newest first)."""
    with _lock:
        return [dict(t) for t in reversed(_trials)][:limit]


def status() -> dict:
    """Dashboard summary: catalog, active count, and recent trials."""
    with _lock:
        n_active = sum(1 for t in _trials if t["status"] == "active")
    return {"catalog": TRIALS, "active": n_active, "trials": history(20)}


def clear() -> None:
    """Reset all trial state (for tests)."""
    global _next_id
    with _lock:
        _trials.clear()
        _next_id = 1
