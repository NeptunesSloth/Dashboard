"""Technique Manuals — idle Elders teach by writing, not just by mentoring.

An Elder with **no disciples to mentor** (no subordinates) who is otherwise idle
turns inward and *authors a technique manual* from their specialty and the
techniques they've mastered. The manual is forged into the shared artifact vault
(:mod:`artifacts`, kind ``manual``) so the rest of the sect can wield it.

This is an automated sect behaviour (no operator action): :func:`tick` is called
each refresh from :func:`agents.snapshot`. Each Elder authors at most one manual
per ``MAYBOT_MANUAL_COOLDOWN_SECONDS`` (default 30m), and only for a technique
not already documented by a manual they wrote.
"""
from __future__ import annotations

import os
import threading
import time

COOLDOWN = int(os.getenv("MAYBOT_MANUAL_COOLDOWN_SECONDS", "1800"))

_lock = threading.Lock()
_last: dict[str, float] = {}        # elder -> last time they authored a manual


def _manual_name(specialty: str | None, skill: str) -> str:
    pretty = skill.replace("_", " ").title()
    if specialty:
        return f"{specialty}: {pretty} Manual"
    return f"{pretty} Manual"


def _content(author: str, specialty: str | None, domain: str | None, skill: str) -> str:
    pretty = skill.replace("_", " ")
    path = f"the {specialty} ({domain})" if specialty and domain else "their own cultivation"
    return (f"# {pretty.title()} — a technique manual\n\n"
            f"Compiled by Elder {author} of {path}, set down in seclusion for the disciples to come.\n\n"
            f"## Essence\n"
            f"The art of {pretty}: when to apply it, the common pitfalls, and the form a clean "
            f"result takes. Follow the steps in order; do not skip the verification.\n\n"
            f"## Practice\n"
            f"1. Survey the terrain before acting.\n"
            f"2. Apply {pretty} with the lightest touch that achieves the goal.\n"
            f"3. Verify the result, then record what changed.\n")


def _undocumented_skill(author: str, skills: list[str], specialty_skill: str | None) -> str | None:
    """Pick a mastered technique this Elder hasn't yet written a manual for."""
    from . import artifacts
    have = {a["name"] for a in artifacts.catalog()
            if a.get("kind") == "manual" and a.get("creator") == author}
    # Prefer the specialty's signature technique, then any mastered skill.
    candidates = ([specialty_skill] if specialty_skill else []) + list(skills or [])
    seen = set()
    for skill in candidates:
        if not skill or skill in seen:
            continue
        seen.add(skill)
        # Match against either naming form (with or without specialty prefix).
        from . import governance
        spec = governance.specialty(author)
        if _manual_name(spec, skill) not in have and _manual_name(None, skill) not in have:
            return skill
    return None


def maybe_author(row: dict, now: float) -> dict | None:
    """If this Elder is idle, has no subordinates, and has an undocumented skill,
    forge a manual. Returns the artifact (or None)."""
    from . import agents, governance, artifacts
    name = row.get("name")
    gov = row.get("governance") or {}
    if not name or not gov.get("is_elder"):
        return None
    if (row.get("status") or "idle") not in ("idle",):
        return None
    c = row.get("cultivation") or {}
    if c.get("in_seclusion") or c.get("in_roaming"):
        return None
    if agents.subordinates(name):          # has disciples to mentor → teaches in person instead
        return None
    with _lock:
        if name in _last and now - _last[name] < COOLDOWN:
            return None
    skill = _undocumented_skill(name, c.get("skills") or [], governance.specialty_skill(name))
    if not skill:
        return None
    spec = governance.specialty(name)
    domain = governance.SPECIALTIES.get(spec, {}).get("domain") if spec else None
    try:
        art = artifacts.forge(name, _manual_name(spec, skill), "manual",
                              _content(name, spec, domain, skill),
                              description=f"Technique manual authored by Elder {name}.")
    except ValueError:
        return None
    try:
        from . import sectmemory
        sectmemory.add(art["content"], source=name, agent=name, kind="manual")
    except Exception:
        pass
    with _lock:
        _last[name] = now
    try:
        from . import comms
        comms._post("system", f"📖 Elder {name} sets down the {skill.replace('_', ' ')} manual for the sect.", "system")
    except Exception:
        pass
    return art


def tick(rows: list[dict], now: float | None = None) -> list[dict]:
    """Author manuals for any eligible idle Elders. Returns the artifacts forged."""
    now = time.time() if now is None else now
    forged = []
    for row in rows or []:
        art = maybe_author(row, now)
        if art:
            forged.append(art)
    return forged


def clear() -> None:
    with _lock:
        _last.clear()
