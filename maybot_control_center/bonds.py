"""Karmic-bond pairs — the pair registry for mandatory cross-checks.

A *karmic bond* ties two disciples together so one reviews the other's work
before it ships (pair-agent QA). Under the cultivation costume this is just a
symmetric 1:1 pairing registry: each disciple has at most one partner, and the
partner is the agent who must review their output.

This module is the REGISTRY ONLY — it records who is bonded to whom. The actual
review step (intercepting work and routing it to the reviewer) is wired in
elsewhere; this just answers "who reviews agent X?" via :func:`reviewer_for`.

State is in-memory under a lock and resets on restart (or via :func:`clear`).
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
# Single source of truth: agent -> partner, kept symmetric in both directions.
_bonds: dict[str, str] = {}


def _break(a: str) -> None:
    """Remove any bond involving ``a`` (both directions). Caller holds the lock."""
    old = _bonds.pop(a, None)
    if old is not None:
        _bonds.pop(old, None)


def bind(a: str, b: str) -> dict:
    """Bond two distinct disciples, replacing any prior bond either one had.

    Returns ``{"pair": [a, b]}`` with the pair sorted for determinism.
    Raises ValueError if ``a == b`` or either is falsy.
    """
    if not a or not b:
        raise ValueError("both agents must be non-empty")
    if a == b:
        raise ValueError("cannot bond an agent to itself")
    with _lock:
        # Break whatever bonds a and b already had, then bind them together.
        _break(a)
        _break(b)
        _bonds[a] = b
        _bonds[b] = a
    return {"pair": sorted([a, b])}


def unbind(a: str) -> bool:
    """Dissolve ``a``'s bond (and its partner's). Return True if a bond existed."""
    with _lock:
        if a not in _bonds:
            return False
        _break(a)
        return True


def partner(a: str) -> str | None:
    """Return ``a``'s bonded partner, or None."""
    with _lock:
        return _bonds.get(a)


def reviewer_for(a: str) -> str | None:
    """Who reviews ``a``'s work — the bonded partner. (Alias of :func:`partner`.)"""
    return partner(a)


def is_bonded(a: str) -> bool:
    """Whether ``a`` currently has a partner."""
    with _lock:
        return a in _bonds


def pairs() -> list[list[str]]:
    """All current bonds as deduped, sorted ``[a, b]`` lists (sorted overall)."""
    with _lock:
        seen: set[tuple[str, str]] = set()
        for agent, mate in _bonds.items():
            seen.add(tuple(sorted([agent, mate])))
    return sorted([list(p) for p in seen])


def snapshot() -> dict:
    """A consistent view: ``{"pairs": [...], "bonded": {agent: partner, ...}}``."""
    with _lock:
        bonded = dict(_bonds)
    return {"pairs": pairs(), "bonded": bonded}


def clear() -> None:
    """Reset all bonds."""
    with _lock:
        _bonds.clear()
