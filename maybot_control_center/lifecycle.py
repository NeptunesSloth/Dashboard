"""Natural selection — ambitious disciples must keep rising, or perish.

Every disciple is ambitious: they strive to climb the realms, master techniques
and earn standing. The sect is unforgiving. Two ways a disciple's tale can end:

- **Stagnation cull** — an Outer Disciple who shows no improvement for too long
  is expelled (a 'death'); a fresh, hungry recruit immediately takes their seat.
- **Struck down** — the Ancestor (you) may strike down any disciple who angers
  you. They are cast out at once and a new disciple is summoned in their place.

Either way the roster keeps churning toward disciples who actually grow. State is
in-memory and resets on restart, matching the other live modules.
"""
from __future__ import annotations

import os
import random
import threading
import time

# Stagnation culling: an Outer Disciple (rank Outer = realm below OUTER_REALM)
# with no measurable progress for CULL_AFTER seconds is culled and replaced.
CULL_ENABLED = os.getenv("MAYBOT_CULL", "1").lower() in ("1", "true", "yes", "on")
CULL_AFTER = max(1, int(os.getenv("MAYBOT_CULL_AFTER_SECONDS", "1800")))   # 30 min of no growth
OUTER_REALM = int(os.getenv("MAYBOT_OUTER_REALM", "2"))                    # Outer rank = realm < this

# A pool of names for fresh recruits (avoids colliding with the seed roster).
RECRUIT_NAMES = [
    "Ash", "Bram", "Cinder", "Dax", "Echo", "Flint", "Gale", "Haze", "Iris",
    "Juno", "Kestrel", "Lark", "Mira", "Nyx", "Onyx", "Pyre", "Reed", "Rook",
    "Sable", "Talon", "Vesper", "Wisp", "Yara", "Zephyr",
]

AMBITIOUS_PERSONA = (
    "You are {name}, a newly accepted Outer Disciple of the sect — ambitious and "
    "hungry to rise. You strive to advance through the cultivation realms, master "
    "new techniques and earn standing in the sect. You know that a disciple who "
    "stops growing is cast out: complacency is death. Seek out work and cultivation."
)

_lock = threading.Lock()
# name -> {"mark": high-water progress, "since": ts of last improvement}
_seen: dict[str, dict] = {}


def _progress(name: str) -> int:
    """A monotonic 'how far have they come' metric for detecting stagnation."""
    from . import cultivation
    c = cultivation.state(name)
    return (c["realm"] * 10000 + c["breakthroughs"] * 1000
            + len(c.get("skills", [])) * 100 + c["stones"])


def _chronicle(agent: str, kind: str, detail: str) -> None:
    try:
        from . import chronicle
        chronicle.record(agent, kind, detail)
    except Exception:
        pass


def _new_recruit_name(taken: set[str]) -> str:
    pool = [n for n in RECRUIT_NAMES if n not in taken]
    if pool:
        return random.choice(pool)
    # pool exhausted — suffix a number so it stays unique
    base = random.choice(RECRUIT_NAMES)
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


def _replace(culled: str, reason: str, kind: str) -> dict:
    """Expel ``culled`` and summon a fresh, ambitious recruit in their place.

    Inherits the culled disciple's backend host config so the new recruit can
    actually be assigned tasks. Returns the new recruit's def.
    """
    from . import agents, cultivation, events, bonds
    src = agents._agent_def(culled) or {}
    taken = {a.get("name") for a in agents.load_agents()} | {culled}
    name = _new_recruit_name(taken)
    recruit = {"name": name, "role": src.get("role") or "Outer Disciple",
               "persona": AMBITIOUS_PERSONA.format(name=name),
               "provider": src.get("provider", "openai_compatible")}
    for k in ("base_url", "model", "default_model", "api_key_env", "max_tokens"):
        if src.get(k) is not None:
            recruit[k] = src[k]

    agents.retire_agent(culled)
    cultivation.expel(culled)
    try:
        bonds.unbind(culled)
    except Exception:
        pass
    agents.recruit_agent(recruit)
    with _lock:
        _seen.pop(culled, None)
        _seen[name] = {"mark": 0, "since": time.time()}

    _chronicle(culled, kind, reason)
    _chronicle(name, "arrival", f"summoned to the sect to replace {culled} — hungry to rise")
    try:
        events.publish("agents", {"agent": culled, "event": kind, "replacement": name})
    except Exception:
        pass
    return recruit


def strike_down(name: str, reason: str = "") -> dict:
    """The Ancestor strikes down a disciple who has angered them. They are cast
    out at once and replaced. Raises ValueError for an unknown disciple."""
    from . import agents
    if not name or name == "operator":
        raise ValueError("no such disciple")
    if name not in {a.get("name") for a in agents.load_agents()}:
        raise ValueError(f"unknown disciple: {name}")
    detail = reason.strip() or "struck down by the Ancestor for incurring their wrath"
    return _replace(name, detail, "struck_down")


def tick() -> dict | None:
    """Cull one stagnant Outer Disciple if any have idled past CULL_AFTER without
    progress. Called periodically from agents.snapshot. Returns the cull record
    (the culled name + replacement) or None.
    """
    if not CULL_ENABLED:
        return None
    from . import agents, governance, cultivation
    now = time.time()
    leader = governance.leader()
    stagnant: str | None = None
    for a in agents.load_agents():
        name = a.get("name")
        if not name or name == "operator" or name == leader:
            continue
        prog = _progress(name)
        with _lock:
            rec = _seen.get(name)
            if rec is None:
                _seen[name] = {"mark": prog, "since": now}
                continue
            if prog > rec["mark"]:                 # they grew — reset the clock
                rec["mark"] = prog
                rec["since"] = now
                continue
            idle_for = now - rec["since"]
        # only Outer Disciples are culled for stagnation; ranked disciples are safe
        if cultivation.realm_of(name) < OUTER_REALM and idle_for >= CULL_AFTER:
            stagnant = name
            break
    if not stagnant:
        return None
    new = _replace(stagnant, "expelled from the sect — failed to advance and stagnated", "culled")
    return {"culled": stagnant, "replacement": new["name"]}


def clear() -> None:
    with _lock:
        _seen.clear()
