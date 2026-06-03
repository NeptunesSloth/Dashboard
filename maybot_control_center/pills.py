"""Pills & elixirs: spend spirit stones for temporary boosts to a disciple.

Buying a pill deducts the disciple's spirit stones (cultivation) and grants a
time-limited buff applied during task execution: a stronger model, deeper
responses (more tokens), a higher autonomy budget, or a harsher inner demon.
Buffs are transient (not persisted) and expire after MAYBOT_PILL_DURATION.
"""
from __future__ import annotations

import os
import threading
import time

from . import cultivation

DURATION = int(os.getenv("MAYBOT_PILL_DURATION", "600"))  # seconds a buff lasts

CATALOG = {
    "qi_gathering": {"name": "Qi-Gathering Pill", "cost": 40, "effect": "max_tokens", "amount": 1024,
                     "desc": "Deepens responses (+1024 max tokens)."},
    "enlightenment": {"name": "Enlightenment Elixir", "cost": 140, "effect": "model", "amount": "claude-opus-4-8",
                      "desc": "Ascend to a stronger model (claude-opus-4-8)."},
    "foundation": {"name": "Foundation Pill", "cost": 90, "effect": "autonomy", "amount": 3,
                   "desc": "+3 autonomy budget per task."},
    "heart_demon": {"name": "Heart-Demon Pill", "cost": 60, "effect": "inner_demon", "amount": 2,
                    "desc": "Summons a harsher inner demon (+2 critique cycles)."},
}

_lock = threading.Lock()
_active: dict[str, list[dict]] = {}  # agent -> [{effect, amount, expires, name}]


def catalog() -> list[dict]:
    return [{"id": k, "name": v["name"], "cost": v["cost"], "effect": v["effect"], "desc": v["desc"]}
            for k, v in CATALOG.items()]


def buy(agent: str, pill_id: str) -> dict:
    pill = CATALOG.get(pill_id)
    if not pill:
        raise ValueError(f"unknown pill '{pill_id}'")
    if not cultivation.spend(agent, pill["cost"]):
        raise ValueError("not enough spirit stones")
    with _lock:
        _active.setdefault(agent, []).append(
            {"effect": pill["effect"], "amount": pill["amount"], "expires": time.time() + DURATION, "name": pill["name"]})
    return {"agent": agent, "pill": pill_id, "name": pill["name"], "expires_in": DURATION}


def _purge(agent: str, now: float) -> list[dict]:
    lst = [b for b in _active.get(agent, []) if b["expires"] > now]
    if lst:
        _active[agent] = lst
    else:
        _active.pop(agent, None)
    return lst


def effects(agent: str) -> dict:
    """Merged active effects (numeric effects summed, model last-wins)."""
    now = time.time()
    out: dict = {}
    with _lock:
        for b in _purge(agent, now):
            if b["effect"] == "model":
                out["model"] = b["amount"]
            else:
                out[b["effect"]] = out.get(b["effect"], 0) + b["amount"]
    return out


def autonomy_bonus(agent: str) -> int:
    return int(effects(agent).get("autonomy", 0))


def active(agent: str) -> list[dict]:
    now = time.time()
    with _lock:
        return [{"name": b["name"], "effect": b["effect"], "expires_in": int(b["expires"] - now)}
                for b in _purge(agent, now)]


def active_all() -> dict:
    with _lock:
        names = list(_active.keys())
    return {a: active(a) for a in names}


def clear() -> None:
    with _lock:
        _active.clear()
