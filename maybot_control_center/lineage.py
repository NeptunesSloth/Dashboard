"""Lineage tree: the sect's knowledge-transfer & ownership graph.

This is the *graph store* for skill lineage. It answers two questions:

  - **Ownership** — who *originated* each technique? The first disciple to
    obtain a skill (by discovery, quest, seclusion, ...) owns it.
  - **Transmission** — who taught which skill to whom? Every teaching forms a
    directed edge ``teacher -> student`` labelled with the skill.

Hooks into the transmit/learn flows are wired up elsewhere; this module only
records and reports the resulting graph. State is in-memory, guarded by a lock,
and resettable via :func:`clear`.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
# skill -> {"agent", "skill", "source"}; first writer wins.
_origins: dict[str, dict] = {}
# list of {"teacher", "student", "skill"}; deduplicated.
_edges: list[dict] = []


def record_origin(agent: str, skill: str, source: str = "discovered") -> None:
    """Record that ``agent`` first obtained ``skill``.

    ``source`` describes how (e.g. "discovered", "quest", "seclusion"). First
    writer wins: an existing origin for the skill is never overwritten. Falsy
    ``agent`` or ``skill`` are ignored.
    """
    if not agent or not skill:
        return
    with _lock:
        if skill in _origins:
            return
        _origins[skill] = {"agent": agent, "skill": skill, "source": source}


def record_transmission(teacher: str, student: str, skill: str) -> None:
    """Record a teaching edge ``teacher -> student`` for ``skill``.

    Falsy inputs and self-teaching (``teacher == student``) are ignored.
    Identical edges are deduplicated. If the skill has no recorded origin yet,
    the teacher becomes a fallback origin with source "transmission" (an
    existing origin is never overwritten).
    """
    if not teacher or not student or not skill:
        return
    if teacher == student:
        return
    with _lock:
        edge = {"teacher": teacher, "student": student, "skill": skill}
        if edge not in _edges:
            _edges.append(edge)
        if skill not in _origins:
            _origins[skill] = {
                "agent": teacher,
                "skill": skill,
                "source": "transmission",
            }


def origins() -> list[dict]:
    """All origin records: ``[{"agent", "skill", "source"}, ...]``."""
    with _lock:
        return [dict(o) for o in _origins.values()]


def edges() -> list[dict]:
    """All transmission edges: ``[{"teacher", "student", "skill"}, ...]``."""
    with _lock:
        return [dict(e) for e in _edges]


def skill_origin(skill: str) -> dict | None:
    """The origin record for ``skill``, or ``None`` if unknown."""
    if not skill:
        return None
    with _lock:
        o = _origins.get(skill)
        return dict(o) if o is not None else None


def lineage_of(agent: str) -> dict:
    """Everything we know about one agent's place in the lineage.

    Returns ``{"learned_from": [{"teacher", "skill"}...],
    "taught": [{"student", "skill"}...], "originated": [skills]}``.
    """
    learned_from: list[dict] = []
    taught: list[dict] = []
    originated: list[str] = []
    if not agent:
        return {"learned_from": [], "taught": [], "originated": []}
    with _lock:
        for e in _edges:
            if e["student"] == agent:
                learned_from.append({"teacher": e["teacher"], "skill": e["skill"]})
            if e["teacher"] == agent:
                taught.append({"student": e["student"], "skill": e["skill"]})
        for o in _origins.values():
            if o["agent"] == agent:
                originated.append(o["skill"])
    return {"learned_from": learned_from, "taught": taught, "originated": originated}


def graph() -> dict:
    """The whole lineage graph.

    ``{"nodes": [unique agent names across origins+edges],
    "edges": edges(), "origins": origins()}``.
    """
    with _lock:
        nodes: list[str] = []
        seen: set[str] = set()

        def _add(name: str) -> None:
            if name and name not in seen:
                seen.add(name)
                nodes.append(name)

        for o in _origins.values():
            _add(o["agent"])
        for e in _edges:
            _add(e["teacher"])
            _add(e["student"])
        return {
            "nodes": nodes,
            "edges": [dict(e) for e in _edges],
            "origins": [dict(o) for o in _origins.values()],
        }


def clear() -> None:
    """Reset all stored lineage state (used by tests)."""
    with _lock:
        _origins.clear()
        _edges.clear()
