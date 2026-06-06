"""Operator commands over trading bots — the sect's hand on each disciple.

This module records operator *intent* over the trading bots: pause a wayward
disciple, resume one, throttle its aggression, or flatten its book. It does
**not** place real orders — it tracks desired state only, so the rest of the
system (and the UI) can reflect what the operator has decreed.

State is in-memory and module-level, mirroring :mod:`audit` / :mod:`risk`. A
"flatten all" decree marks every known bot ``flatten`` and raises a global flag
that callers can honour before placing any new order.
"""
from __future__ import annotations

import threading
import time

# Valid operator actions and the bot state each one implies.
_ACTIONS: dict[str, str] = {
    "pause": "paused",
    "resume": "active",
    "throttle": "throttled",
    "flatten": "flatten",
}

_lock = threading.Lock()

# bot_name -> {"bot","state","ts","actor"}
_states: dict[str, dict] = {}

# Global "flatten everything" decree.
_flatten_all: bool = False


def actions() -> list[str]:
    """The set of valid operator actions."""
    return list(_ACTIONS)


def set_state(bot_name: str, action: str, actor: str = "operator") -> dict:
    """Record an operator's desired state for a bot.

    Validates ``action``; on success records the implied state with a timestamp
    and the acting operator and returns ``{"bot","state","ts","actor"}``. An
    invalid action returns ``{"error": ...}`` and changes nothing.
    """
    action = (action or "").strip().lower()
    if action not in _ACTIONS:
        return {"error": f"invalid action {action!r}; valid: {', '.join(_ACTIONS)}"}
    rec = {
        "bot": bot_name,
        "state": _ACTIONS[action],
        "ts": int(time.time() * 1000),
        "actor": actor or "operator",
    }
    with _lock:
        _states[bot_name] = rec
    return dict(rec)


def state(bot_name: str) -> dict:
    """The recorded operator state for a single bot ({} if none)."""
    with _lock:
        rec = _states.get(bot_name)
        return dict(rec) if rec else {}


def all_states() -> dict[str, dict]:
    """A copy of every recorded operator state, keyed by bot name."""
    with _lock:
        return {name: dict(rec) for name, rec in _states.items()}


def flatten_all(actor: str = "operator") -> dict:
    """Decree that every known bot flatten its book; raises the global flag.

    Returns ``{"flatten_all": True, "bots": [...], "ts": ...}``.
    """
    global _flatten_all
    ts = int(time.time() * 1000)
    with _lock:
        _flatten_all = True
        names = list(_states)
        for name in names:
            _states[name] = {"bot": name, "state": "flatten", "ts": ts,
                             "actor": actor or "operator"}
    return {"flatten_all": True, "bots": names, "ts": ts}


def is_flatten_all() -> bool:
    """Whether the global flatten-all decree is in force."""
    with _lock:
        return _flatten_all


def clear() -> None:
    """Forget all operator state (used between sessions / in tests)."""
    global _flatten_all
    with _lock:
        _states.clear()
        _flatten_all = False


def apply_to_bots(bots: list[dict]) -> list[dict]:
    """Overlay operator state onto bot dicts so the UI reflects control.

    Given bot dicts shaped like :func:`command.bots` ({"name","status",...}),
    return a copy where each bot's ``status`` is overridden by any operator
    state (paused / throttled / flatten / active). Bots without an operator
    decree are returned unchanged (but still copied).
    """
    states = all_states()
    flatten = is_flatten_all()
    out: list[dict] = []
    for b in (bots or []):
        bot = dict(b)
        if flatten:
            # A flatten-all decree overrides everything.
            bot["status"] = "flatten"
        else:
            rec = states.get(bot.get("name"))
            if rec:
                bot["status"] = rec["state"]
        out.append(bot)
    return out
