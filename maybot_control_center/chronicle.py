"""Cultivation chronicle — a per-disciple event timeline / audit history.

Every disciple (agent) accrues a *chronicle*: a chronological story of the
notable things that happened to them. Breakthroughs, tribulations, completed
tasks, tools forged, titles earned, leadership challenges, appointments, spirit
specialties and karmic bonds all leave a mark here. Stripped of the xianxia
costume it is a plain per-agent audit log: an append-only, bounded, in-memory
timeline of lifecycle events.

The recording hooks live in the other modules; this module is the SINK. It only
answers "what has happened to disciple X, and in what order?" via
:func:`timeline`, plus a cross-disciple feed via :func:`recent`.

State is in-memory under a lock and resets on restart (or via :func:`clear`).
Each agent keeps at most :data:`MAX_PER_AGENT` entries (the newest win).
"""
from __future__ import annotations

import os
import threading
import time

# Cap of timeline entries kept per disciple; older entries fall off the front.
MAX_PER_AGENT = int(os.getenv("MAYBOT_CHRONICLE_MAX", "200"))

# Known entry kinds and their display glyph. Unknown kinds fall back to "•".
GLYPHS = {
    "breakthrough": "⬆",
    "tribulation": "☄",
    "task": "✓",
    "tool": "🛠",
    "title": "🏅",
    "challenge": "⚔",
    "appointment": "👑",
    "specialty": "🜍",
    "bond": "🤝",
    "throne": "🪑",
    "guidance": "🧭",
    "mentored": "🌱",
    "culled": "💀",
    "struck_down": "⚡",
    "arrival": "✨",
    "quirk": "✦",
    "young_master": "😼",
    "main_character": "🌟",
    "face_slap": "👋",
    "ruined": "💢",
    "redeemed": "🔥",
    "hidden_dragon": "🥚",
    "awakened_dragon": "🐉",
    "reincarnator": "♾",
    "heaven_blessed": "🌈",
    "demonic": "👹",
    "chosen": "☀",
    "sword_fanatic": "🗡",
    "cannon_fodder": "⚰",
    "stepping_stone": "🪜",
    "perished": "⚰",
    "note": "•",
}

_lock = threading.Lock()
# agent -> list of entry dicts, oldest first (append order).
_entries: dict[str, list[dict]] = {}
# Global monotonically-incrementing id, so ordering is total even within a ms.
_next_id = 1


def record(
    agent: str, kind: str, detail: str = "", meta: dict | None = None
) -> dict | None:
    """Append a timeline entry for ``agent`` and return a copy of it.

    Falsy agents and the special "operator" agent are skipped (returns None) —
    the chronicle is for disciples, not the operator. ``detail`` is truncated to
    500 chars. The newest :data:`MAX_PER_AGENT` entries per agent are retained.
    """
    if not agent or agent == "operator":
        return None
    global _next_id
    with _lock:
        entry = {
            "id": _next_id,
            "agent": agent,
            "kind": kind,
            "glyph": GLYPHS.get(kind, "•"),
            "detail": detail[:500],
            "meta": dict(meta) if meta else {},
            "ts": int(time.time() * 1000),
        }
        _next_id += 1
        log = _entries.setdefault(agent, [])
        log.append(entry)
        if len(log) > MAX_PER_AGENT:
            # Keep only the newest MAX_PER_AGENT entries.
            del log[: len(log) - MAX_PER_AGENT]
    return _copy(entry)


def timeline(agent: str, limit: int = 100) -> list[dict]:
    """The disciple's most recent entries as copies, oldest->newest in the slice.

    Returns up to ``limit`` of the most recent entries (the tail of the log),
    preserving document order so the returned list reads as a story.
    """
    if limit <= 0:
        return []
    with _lock:
        log = _entries.get(agent)
        if not log:
            return []
        return [_copy(e) for e in log[-limit:]]


def recent(limit: int = 50) -> list[dict]:
    """The most recent entries across ALL disciples, newest first, as copies.

    Entries are merged from every agent and sorted by (ts, id) descending so the
    newest event leads. Returns up to ``limit`` entries.
    """
    if limit <= 0:
        return []
    with _lock:
        merged: list[dict] = []
        for log in _entries.values():
            merged.extend(log)
    merged.sort(key=lambda e: (e["ts"], e["id"]), reverse=True)
    return [_copy(e) for e in merged[:limit]]


def snapshot() -> dict:
    """Counts view: ``{"agents": {agent: count}, "total": N}``."""
    with _lock:
        agents = {agent: len(log) for agent, log in _entries.items()}
    return {"agents": agents, "total": sum(agents.values())}


def clear() -> None:
    """Reset all chronicles and the id counter."""
    global _next_id
    with _lock:
        _entries.clear()
        _next_id = 1


def _copy(entry: dict) -> dict:
    """A defensive copy of an entry, including a fresh ``meta`` dict."""
    out = dict(entry)
    out["meta"] = dict(entry["meta"])
    return out
