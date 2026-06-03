"""Spirit-Root Assessment — automated per-model capability benchmarking.

Before a disciple (model/agent) is trusted with real work, a caller runs a
battery of *probe tasks* against it (reasoning puzzles, coding challenges,
reliability checks, latency measurements) and feeds the raw outcomes here. This
module is **pure scoring**: it performs no LLM calls itself. It turns a list of
probe results into per-category scores, a weighted overall score (0-100) and a
cultivation-flavoured "spirit-root" grade.

Probe categories and their weights (sum to 1.0)::

    reasoning   0.35
    coding      0.35
    reliability 0.20
    latency     0.10

For pass/fail categories (everything except ``latency``) a category's score is
its pass rate as a percentage. For ``latency`` the mean latency in ms is mapped
to a 0-100 score where lower is better (``100 - mean_ms/20``, clamped).

Missing-category policy: if NO results were supplied for a category, it is
treated as scoring 100 (untested => no penalty). This is deliberate so that a
caller probing only a subset of categories is not punished for the categories it
chose not to run; the ``samples`` count and per-category presence let callers
detect partial assessments if they care.
"""
from __future__ import annotations

import os
import threading
import time

# Probe categories and their relative weights in the overall score (sum == 1.0).
PROBES: dict[str, float] = {
    "reasoning": 0.35,
    "coding": 0.35,
    "reliability": 0.20,
    "latency": 0.10,
}

# Suggested probe categories a caller should run; just the keys of PROBES.
BASELINE_PROBES: list[str] = list(PROBES.keys())

# Ordered grade tiers: (threshold, name). Pick the first whose threshold the
# overall score meets, scanning from highest to lowest.
GRADES: list[tuple[int, str]] = [
    (85, "Heavenly"),
    (70, "Earthly"),
    (50, "Mortal"),
    (0, "Mortal Dust"),
]

# Divisor for the latency->score mapping; configurable via env.
LATENCY_DIVISOR = float(os.getenv("MAYBOT_SPIRIT_LATENCY_DIVISOR", "20"))

_lock = threading.Lock()
_profiles: dict[str, dict] = {}


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _grade_for(overall: float) -> str:
    for threshold, name in GRADES:
        if overall >= threshold:
            return name
    # GRADES always ends at 0, so this is unreachable for non-negative scores.
    return GRADES[-1][1]


def _latency_score(latencies: list[float]) -> float:
    if not latencies:
        return 100.0
    mean_ms = sum(latencies) / len(latencies)
    return _clamp(100.0 - mean_ms / LATENCY_DIVISOR)


def _category_score(category: str, rows: list[dict]) -> float:
    """Score for a single category given its probe rows.

    No rows => 100 (untested, no penalty). For ``latency`` the score derives
    from mean latency; otherwise it is the pass rate as a percentage.
    """
    if not rows:
        return 100.0
    if category == "latency":
        lats = [float(r.get("latency_ms", 0) or 0) for r in rows]
        return _latency_score(lats)
    passed = sum(1 for r in rows if r.get("ok"))
    return _clamp(100.0 * passed / len(rows))


def assess(agent: str, results: list[dict]) -> dict:
    """Score ``agent`` from a list of probe outcomes and store the profile.

    Each result is a dict like
    ``{"category": "reasoning", "ok": bool, "latency_ms": int}``.
    Returns the stored profile dict.
    """
    results = results or []

    by_cat: dict[str, list[dict]] = {cat: [] for cat in PROBES}
    for r in results:
        cat = r.get("category")
        if cat in by_cat:
            by_cat[cat].append(r)

    categories: dict[str, float] = {}
    overall = 0.0
    for cat, weight in PROBES.items():
        cat_score = _category_score(cat, by_cat[cat])
        categories[cat] = round(cat_score, 2)
        overall += cat_score * weight

    overall_rounded = round(overall, 2)
    profile_dict = {
        "agent": agent,
        "overall": overall_rounded,
        "grade": _grade_for(overall),
        "categories": categories,
        "samples": len(results),
        "ts": int(time.time() * 1000),
    }
    with _lock:
        _profiles[agent] = profile_dict
    return profile_dict


def profile(agent: str) -> dict | None:
    """Last stored assessment for ``agent``, or None if never assessed."""
    with _lock:
        return _profiles.get(agent)


def grade(agent: str) -> str | None:
    """Spirit-root grade for ``agent``, or None if never assessed."""
    with _lock:
        p = _profiles.get(agent)
    return p["grade"] if p else None


def snapshot() -> dict:
    """Mapping of {agent: profile} for every assessed agent."""
    with _lock:
        return dict(_profiles)


def clear() -> None:
    """Reset all stored profiles (used by tests)."""
    with _lock:
        _profiles.clear()
