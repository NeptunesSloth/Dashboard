"""Assign-by-goal auto-routing — pick the best-fit disciple for a goal.

Instead of naming a disciple, describe the work; this scores each eligible
disciple and returns the best match with an explainable breakdown. Signals:

- **specialty match** — keywords in the goal mapped to an Elder's engineering
  domain (governance.SPECIALTIES) and signature skills,
- **standing** — the governance composite (merit / performance / leadership /
  contribution),
- **realm** — cultivation depth as a light capability prior,
- **load** — current active tasks on the board (busier disciples score lower).

Disciples in seclusion/roaming, on probation, or marked unavailable are skipped.
"""
from __future__ import annotations

import re

# Domain keyword → specialty name. Used to match a free-text goal to a path.
_DOMAIN_KEYWORDS = {
    "Sword Dao": ["backend", "api", "server", "database", "performance", "latency", "refactor", "endpoint"],
    "Alchemy": ["data", "ml", "model", "analysis", "analytics", "pipeline", "dataset", "train", "metric"],
    "Formation Dao": ["deploy", "infra", "devops", "monitor", "incident", "ci", "kubernetes", "docker", "outage", "alert"],
    "Talisman Crafting": ["ui", "ux", "frontend", "css", "design", "accessibility", "visual", "dashboard", "page"],
    "Beast Taming": ["test", "qa", "fuzz", "regression", "coverage", "bug", "flaky"],
    "Artifact Refinement": ["tooling", "automation", "script", "release", "build", "pipeline", "cli"],
}


def _specialties_for_goal(goal: str) -> set[str]:
    text = (goal or "").lower()
    words = set(re.findall(r"[a-z]+", text))
    out = set()
    for spec, kws in _DOMAIN_KEYWORDS.items():
        if any(kw in words or kw in text for kw in kws):
            out.add(spec)
    return out


def _candidate_names() -> list[str]:
    from . import agents
    return [a.get("name") for a in agents.load_agents() if a.get("name")]


def eligible(name: str) -> tuple[bool, str | None]:
    """(is_eligible, reason_if_not)."""
    from . import cultivation, reputation
    c = cultivation.state(name)
    if c.get("in_seclusion"):
        return False, "in seclusion"
    if c.get("in_roaming"):
        return False, "roaming abroad"
    try:
        if reputation.is_probation(name):
            return False, "on probation"
    except Exception:
        pass
    return True, None


def score_agent(name: str, goal_specs: set[str]) -> dict:
    from . import governance, cultivation, taskqueue
    spec = governance.specialty(name)
    spec_match = 100.0 if spec and spec in goal_specs else (40.0 if spec else 0.0)
    mastery = governance.mastery(name) if spec else 0.0
    standing = governance.standing(name)["score"]
    realm = cultivation.realm_of(name)
    load = taskqueue.active_count(name)

    # Weighted blend; load is a penalty so work spreads across idle disciples.
    score = (0.40 * spec_match + 0.20 * mastery + 0.25 * standing + 0.15 * min(100, realm * 12)
             - 12.0 * load)
    return {"agent": name, "score": round(score, 1), "specialty": spec,
            "specialty_match": spec_match >= 100, "standing": standing,
            "realm": realm, "load": load}


def rank(goal: str) -> list[dict]:
    """All eligible disciples scored for this goal, best first."""
    goal_specs = _specialties_for_goal(goal)
    rows = []
    for name in _candidate_names():
        ok, reason = eligible(name)
        if not ok:
            continue
        rows.append(score_agent(name, goal_specs))
    rows.sort(key=lambda r: -r["score"])
    return rows


def best_fit(goal: str) -> dict | None:
    """Return the chosen disciple + reasoning, or None if nobody is eligible."""
    ranked = rank(goal)
    if not ranked:
        return None
    top = ranked[0]
    matched = sorted(_specialties_for_goal(goal))
    bits = []
    if top["specialty_match"]:
        bits.append(f"specialty {top['specialty']} matches the goal")
    elif top["specialty"]:
        bits.append(f"specialty {top['specialty']}")
    bits.append(f"standing {top['standing']}")
    bits.append(f"load {top['load']}")
    return {"agent": top["agent"], "reason": "; ".join(bits),
            "matched_specialties": matched, "ranked": ranked[:5]}
