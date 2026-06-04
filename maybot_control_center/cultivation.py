"""Agent cultivation: spirit stones (merit) + cultivation realms.

Disciples (agents) earn **spirit stones** for good work — completing tasks,
mastering **techniques** (succeeding at a tool they've never used before), and
joining the Dao Council. Mastering a brand-new technique is a new *skill*; with
enough spirit stones AND enough techniques, a disciple **breaks through** to the
next cultivation realm. Persisted via store when MAYBOT_DB is set.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time

from . import store
from . import events
from . import treasury

# Each realm requires both a spirit-stone total and a number of mastered
# techniques to break through into — so you can't reach the higher realms on
# grinding alone; you must develop new skills.
REALMS = [
    {"name": "Mortal", "stones": 0, "skills": 0},
    {"name": "Qi Condensation", "stones": 60, "skills": 0},
    {"name": "Foundation Establishment", "stones": 180, "skills": 1},
    {"name": "Core Formation", "stones": 400, "skills": 2},
    {"name": "Nascent Soul", "stones": 800, "skills": 3},
    {"name": "Soul Formation", "stones": 1400, "skills": 4},
    {"name": "Spirit Severing", "stones": 2300, "skills": 5},
    {"name": "Dao Seeking", "stones": 3600, "skills": 6},
    {"name": "Immortal Ascension", "stones": 5500, "skills": 8},
]
STAGES = ["Early", "Middle", "Late", "Peak"]
# Sect title by realm tier (Outer → Inner → Core → Elder → Sect Master).
RANK_TITLES = ["Outer Disciple", "Outer Disciple", "Inner Disciple", "Inner Disciple",
               "Core Disciple", "Core Disciple", "Elder", "Elder", "Sect Master"]

# Economy — all tunable via env so the sect's balance can be adjusted.
AWARD_TASK = int(os.getenv("MAYBOT_AWARD_TASK", "12"))
AWARD_TOOL = int(os.getenv("MAYBOT_AWARD_TOOL", "16"))
AWARD_NEW_SKILL = int(os.getenv("MAYBOT_AWARD_SKILL", "40"))
AWARD_COUNCIL = int(os.getenv("MAYBOT_AWARD_COUNCIL", "6"))
AWARD_SURVIVE = int(os.getenv("MAYBOT_AWARD_SURVIVE", "60"))  # surviving a tribulation trial
# Punishment: each failure chips away spirit stones; a streak of them calls down
# a heavenly tribulation that can strike a disciple down a realm (qi deviation).
PENALTY_FAIL = int(os.getenv("MAYBOT_PENALTY_FAIL", "8"))
TRIBULATION_STREAK = max(1, int(os.getenv("MAYBOT_TRIBULATION_STREAK", "3")))
TRIBULATION_LOSS = int(os.getenv("MAYBOT_TRIBULATION_LOSS", "70"))
# Daily stipend: every disciple draws spirit stones once per period (0 = off),
# funded from the sect treasury. A tithe of productive work flows back to it.
STIPEND = int(os.getenv("MAYBOT_STIPEND", "15"))
STIPEND_SECONDS = max(1, int(os.getenv("MAYBOT_STIPEND_HOURS", "24"))) * 3600
TITHE = int(os.getenv("MAYBOT_TITHE", "3"))
# Closed-door seclusion: after this long sequestered, a disciple researches a new
# technique and breaks through to the next realm (repeats while in seclusion).
SECLUSION_SECONDS = max(1, int(os.getenv("MAYBOT_SECLUSION_MINUTES", "30"))) * 60
# Roaming: a disciple wanders the world and returns with a unique art/knowledge.
ROAMING_SECONDS = max(1, int(os.getenv("MAYBOT_ROAMING_MINUTES", "20"))) * 60
# Auto-retreat: disciples decide on their own to seclude/roam when left idle.
# The Ancestor doesn't send them — but can recall them. Tunable, on by default.
AUTO_RETREAT = os.getenv("MAYBOT_AUTO_RETREAT", "1").lower() in ("1", "true", "yes", "on")
AUTO_RETREAT_IDLE = max(5, int(os.getenv("MAYBOT_AUTO_RETREAT_IDLE_SECONDS", "120")))   # idle this long → may retreat
AUTO_RETREAT_COOLDOWN = max(0, int(os.getenv("MAYBOT_AUTO_RETREAT_COOLDOWN", "300")))   # rest this long after returning
_auto: dict[str, dict] = {}  # agent -> {idle_since, blocked_until}
DISCOVERIES = [
    "Cloud-Stride Step", "Beast-Tongue Art", "Star-Chart Memory", "Whispering-Wind Ear",
    "Iron-Bone Forging", "Verdant-Growth Palm", "Echo-Location Sense", "Ashen-Phoenix Rebirth",
    "Tide-Calling Chant", "Hollow-Moon Gaze", "Thunderclap Resolve", "Serpent-Coil Footwork",
]


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

_lock = threading.Lock()
_state: dict[str, dict] = {}


def _blank(agent: str) -> dict:
    return {"agent": agent, "stones": 0, "realm": 0, "skills": [], "breakthroughs": 0,
            "fail_streak": 0, "pending_tribulation": None, "pending_quest": None, "last_stipend": 0,
            "seclusion_since": None, "roaming_since": None, "learn_goal": None,
            "event": None, "event_ts": 0, "updated_at": 0}


def _maybe_breakthrough(st: dict) -> bool:
    advanced = False
    while st["realm"] + 1 < len(REALMS):
        nxt = REALMS[st["realm"] + 1]
        if st["stones"] >= nxt["stones"] and len(st["skills"]) >= nxt["skills"]:
            st["realm"] += 1
            st["breakthroughs"] += 1
            advanced = True
        else:
            break
    return advanced


def _demote_if_deviated(st: dict) -> bool:
    """If stones fell below the current realm's requirement, drop a realm."""
    struck = False
    while st["realm"] > 0 and st["stones"] < REALMS[st["realm"]]["stones"]:
        st["realm"] -= 1
        struck = True
    return struck


def _award(agent: str, stones: int, skill: str | None = None) -> dict:
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["stones"] += stones
        st["fail_streak"] = 0
        new_skill = False
        if skill and skill not in st["skills"]:
            st["skills"].append(skill)
            st["stones"] += AWARD_NEW_SKILL  # mastering a new technique is a windfall
            new_skill = True
        broke = _maybe_breakthrough(st)
        if broke:
            st["event"], st["event_ts"] = "breakthrough", now
        st["updated_at"] = now
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    if broke:
        events.publish("agents", {"agent": agent, "event": "breakthrough"})
        _chronicle(agent, "breakthrough", f"broke through to {REALMS[snap['realm']]['name']}")
    return {"new_skill": new_skill, "breakthrough": broke}


def _chronicle(agent: str, kind: str, detail: str = "", meta: dict | None = None) -> None:
    """Record a notable lifecycle event to the cultivation chronicle (best-effort)."""
    try:
        from . import chronicle
        chronicle.record(agent, kind, detail, meta)
    except Exception:
        pass


def _tribulate(agent: str) -> bool:
    """Call down a heavenly tribulation: heavy stone loss, possible realm demotion."""
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["stones"] = max(0, st["stones"] - TRIBULATION_LOSS)
        struck = _demote_if_deviated(st)
        st["fail_streak"] = 0
        st["pending_tribulation"] = None
        st["event"], st["event_ts"] = "tribulation", now
        st["updated_at"] = now
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    events.publish("agents", {"agent": agent, "event": "tribulation", "struck": struck})
    _chronicle(agent, "tribulation", "struck down a realm" if struck else "weathered it; spirit stones scattered")
    try:
        from . import notifier
        notifier.notify_event("tribulation", f"Heavenly tribulation strikes {agent}",
                              "struck down a realm" if struck else "spirit stones scattered")
    except Exception:
        pass
    return struck


def _fail(agent: str) -> None:
    """A misstep: lose stones; a streak of them invites a heavenly tribulation."""
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["fail_streak"] += 1
        st["stones"] = max(0, st["stones"] - PENALTY_FAIL)
        st["updated_at"] = now
        streaked = st["fail_streak"] >= TRIBULATION_STREAK
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if streaked:
        _tribulate(agent)
    elif store.enabled():
        store.upsert_cultivation(snap)


def face_tribulation(agent: str, project: str) -> None:
    """Mark a disciple as facing a heavenly tribulation (an incident to resolve)."""
    if not agent or agent == "operator":
        return
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["pending_tribulation"] = project
        st["event"], st["event_ts"] = "facing_tribulation", now
    events.publish("agents", {"agent": agent, "event": "facing_tribulation", "project": project})


def on_task(agent: str, ok: bool) -> None:
    if not agent or agent == "operator":
        return
    with _lock:
        st = _state.get(agent)
        pending = st.get("pending_tribulation") if st else None
        pquest = st.get("pending_quest") if st else None
    if pquest:
        with _lock:
            _state[agent]["pending_quest"] = None
        if ok:  # quest completed — bring back its unique technique + reward
            learn(agent, pquest["skill"], bonus=pquest.get("stones", 0))
            treasury.deposit(TITHE)
            now = int(time.time() * 1000)
            with _lock:
                s = _state[agent]
                if s.get("event") != "breakthrough":
                    s["event"], s["event_ts"] = "quest_complete", now
            events.publish("agents", {"agent": agent, "event": "quest_complete"})
        else:
            _fail(agent)
        return
    if pending:
        if ok:  # survived the trial — a windfall and a chance to break through
            _award(agent, AWARD_SURVIVE)
            treasury.deposit(TITHE)
            now = int(time.time() * 1000)
            with _lock:
                s = _state[agent]
                s["pending_tribulation"] = None
                if s.get("event") != "breakthrough":
                    s["event"], s["event_ts"] = "tribulation_survived", now
            events.publish("agents", {"agent": agent, "event": "tribulation_survived"})
        else:  # failed the trial — struck down
            _tribulate(agent)
        return
    if ok:
        _award(agent, AWARD_TASK)
        treasury.deposit(TITHE)  # a tithe of good work funds the sect
        _deepen_specialty(agent)
    else:
        _fail(agent)


def on_tool(agent: str, tool: str, ok: bool) -> None:
    if not agent or agent == "operator":
        return
    if ok:
        res = _award(agent, AWARD_TOOL, skill=tool)
        treasury.deposit(TITHE)
        if res.get("new_skill"):  # first to master this technique → record provenance
            try:
                from . import lineage
                lineage.record_origin(agent, tool, "technique")
            except Exception:
                pass
    else:
        _fail(agent)


def on_council(agent: str) -> None:
    if agent and agent != "operator":
        _award(agent, AWARD_COUNCIL)
        _deepen_specialty(agent)


def _deepen_specialty(agent: str) -> None:
    """An Elder's good work deepens their chosen-path mastery (and may teach a
    signature technique of that path). No-op for non-Elders / no specialty."""
    try:
        from . import governance
        if not governance.specialty(agent):
            return
        governance.advance_mastery(agent)
        skill = governance.specialty_skill(agent)
        if skill and governance.mastery(agent) >= 20:
            learn(agent, skill)  # mastery has matured enough to grasp the technique
    except Exception:
        pass  # governance is an optional layer; never break core cultivation


def _progress(st: dict) -> float:
    realm = st["realm"]
    if realm + 1 >= len(REALMS):
        return 1.0
    cur, nxt = REALMS[realm]["stones"], REALMS[realm + 1]["stones"]
    return round(min(1.0, max(0.0, (st["stones"] - cur) / max(1, nxt - cur))), 3)


def _stage(st: dict) -> str:
    if st["realm"] + 1 >= len(REALMS):
        return "Peak"
    return STAGES[min(len(STAGES) - 1, int(_progress(st) * len(STAGES)))]


def _layer(st: dict) -> int:
    """Sub-realm layer 1–9 within the current realm (xianxia granularity)."""
    if st["realm"] + 1 >= len(REALMS):
        return 9
    return min(9, max(1, int(_progress(st) * 9) + 1))


def state(agent: str) -> dict:
    with _lock:
        st = dict(_state.get(agent) or _blank(agent))
        st["skills"] = list(st.get("skills", []))
    realm = st["realm"]
    nxt = REALMS[realm + 1] if realm + 1 < len(REALMS) else None
    layer = _layer(st)
    return {
        "realm": realm,
        "realm_name": REALMS[realm]["name"],
        "stage": _stage(st),
        "layer": layer,
        "layer_label": f"{_ordinal(layer)} Layer",
        "rank_title": RANK_TITLES[min(realm, len(RANK_TITLES) - 1)],
        "pending_tribulation": st.get("pending_tribulation"),
        "in_seclusion": bool(st.get("seclusion_since")),
        "seclusion_remaining": (max(0, int(SECLUSION_SECONDS - (time.time() - st["seclusion_since"])))
                                if st.get("seclusion_since") else 0),
        "in_roaming": bool(st.get("roaming_since")),
        "roaming_remaining": (max(0, int(ROAMING_SECONDS - (time.time() - st["roaming_since"])))
                              if st.get("roaming_since") else 0),
        "learn_goal": st.get("learn_goal"),
        "pending_quest": st.get("pending_quest"),
        "stones": st["stones"],
        "skills": st["skills"],
        "breakthroughs": st["breakthroughs"],
        "next_realm": nxt["name"] if nxt else None,
        "stones_to_next": max(0, nxt["stones"] - st["stones"]) if nxt else 0,
        "skills_to_next": max(0, nxt["skills"] - len(st["skills"])) if nxt else 0,
        "progress": _progress(st),
        "fail_streak": st.get("fail_streak", 0),
        "event": st.get("event"),
        "event_ts": st.get("event_ts", 0),
    }


def reward(agent: str, stones: int) -> None:
    """Public spirit-stone reward (e.g. a tournament champion's spoils)."""
    if agent and agent != "operator":
        _award(agent, stones)


def qi_deviation(agent: str) -> bool:
    """Public hook for a forced tribulation (e.g. pill overuse). Returns True if struck down."""
    if not agent or agent == "operator":
        return False
    return _tribulate(agent)


def grant_stipend(agent: str) -> bool:
    """Grant the daily stipend (funded from the treasury) if due. Returns True if granted."""
    if STIPEND <= 0 or not agent or agent == "operator":
        return False
    now = time.time()
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        if now - st.get("last_stipend", 0) < STIPEND_SECONDS:
            return False
    if not treasury.withdraw(STIPEND):
        return False  # the sect coffers are empty — no stipend until the veins refill
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["last_stipend"] = now
        st["stones"] += STIPEND
        _maybe_breakthrough(st)
        st["updated_at"] = int(now * 1000)
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    return True


def learn(agent: str, skill: str, bonus: int = 0) -> bool:
    """A disciple learns a technique (skill). Returns True if it was new."""
    if not agent or agent == "operator" or not skill:
        return False
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        if skill in st["skills"]:
            return False
        st["skills"].append(skill)
        st["stones"] += bonus
        broke = _maybe_breakthrough(st)
        if broke:
            st["event"], st["event_ts"] = "breakthrough", now
        st["updated_at"] = now
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    if broke:
        events.publish("agents", {"agent": agent, "event": "breakthrough"})
    return True


def assign_quest(agent: str, reward_skill: str, stones: int) -> None:
    """Mark a disciple as undertaking a quest; the reward is granted when the task succeeds."""
    if not agent or agent == "operator":
        return
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["pending_quest"] = {"skill": reward_skill, "stones": int(stones)}


def enter_seclusion(agent: str) -> dict:
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["seclusion_since"] = time.time()
        st["roaming_since"] = None  # can't seclude and roam at once
        st["event"], st["event_ts"] = "seclusion", now
    events.publish("agents", {"agent": agent, "event": "seclusion"})
    return state(agent)


def enter_roaming(agent: str) -> dict:
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["roaming_since"] = time.time()
        st["seclusion_since"] = None
        st["event"], st["event_ts"] = "roaming", now
    events.publish("agents", {"agent": agent, "event": "roaming"})
    return state(agent)


def auto_retreat_tick(agent: str, status: str) -> str | None:
    """Disciples decide for themselves: an idle disciple eventually goes off to
    seclude (cultivate) or roam (seek knowledge). Returns 'seclusion'/'roaming'
    if one was just started. The Ancestor can recall them at any time.
    """
    if not AUTO_RETREAT or not agent or agent == "operator":
        return None
    import random
    now = time.time()
    with _lock:
        st = _state.get(agent)
        in_retreat = bool(st and (st.get("seclusion_since") or st.get("roaming_since")))
        rec = _auto.setdefault(agent, {"idle_since": now, "blocked_until": 0.0})
        if in_retreat or status in ("working", "queued"):
            # busy or already away — keep them off-cooldown clock fresh
            rec["idle_since"] = now
            if in_retreat:
                rec["blocked_until"] = now + AUTO_RETREAT_COOLDOWN
            return None
        if now < rec["blocked_until"] or now - rec["idle_since"] < AUTO_RETREAT_IDLE:
            return None
        rec["idle_since"] = now
        rec["blocked_until"] = now + AUTO_RETREAT_COOLDOWN
    choice = "seclusion" if random.random() < 0.6 else "roaming"  # mostly cultivate, sometimes wander
    (enter_seclusion if choice == "seclusion" else enter_roaming)(agent)
    return choice


def exit_roaming(agent: str) -> dict:
    with _lock:
        st = _state.get(agent)
        if st:
            st["roaming_since"] = None
    events.publish("agents", {"agent": agent, "event": "returned"})
    return state(agent)


def set_learn_goal(agent: str, skill: str | None) -> dict:
    """The Ancestor asks a disciple to seek a specific skill on their next roam."""
    goal = (skill or "").strip() or None
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["learn_goal"] = goal
    return state(agent)


def tick_roaming(agent: str) -> str | None:
    """If a roaming disciple's journey has matured, return having learned a *real*
    AI skill found on the web (curated fallback when offline). If the Ancestor set
    a learn-goal, the disciple searches for that skill (or the closest thing)."""
    now = time.time()
    with _lock:
        st = _state.get(agent)
        if not st or not st.get("roaming_since"):
            return None
        if now - st["roaming_since"] < ROAMING_SECONDS:
            return None
        known = set(st["skills"])
        want = st.get("learn_goal")

    # Network/discovery happens OUTSIDE the lock so a slow search can't stall callers.
    found, meta = None, None
    try:
        from . import skillquest
        meta = skillquest.discover(agent, known, want=want)
        if meta:
            found = meta["skill"]
    except Exception:
        meta = None
    if not found:  # web yielded nothing new — fall back to the flavour discoveries
        undiscovered = [d for d in DISCOVERIES if d not in known]
        found = random.choice(undiscovered) if undiscovered else None

    with _lock:
        st = _state.get(agent)
        if not st or not st.get("roaming_since"):
            return None
        if not found or found in st["skills"]:
            st["roaming_since"] = None   # nothing left to learn — settle down
            return None
        st["skills"].append(found)
        st["stones"] += AWARD_NEW_SKILL
        _maybe_breakthrough(st)
        st["roaming_since"] = now  # keep wandering for the next discovery
        if st.get("learn_goal"):
            st["learn_goal"] = None  # the requested skill (or closest) has been sought
        st["event"], st["event_ts"] = "discovery", int(now * 1000)
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    src = f"\nSource: {meta['url']}" if meta and meta.get("url") else ""
    try:
        from . import memory
        if memory.enabled():
            memory.write_note(f"roaming-{found}", f"# {found}\n{agent} returned from roaming having learned **{found}**.{src}")
    except Exception:
        pass
    if meta and meta.get("source") == "web":  # attribute the real find in the vault
        try:
            from . import artifacts
            artifacts.forge(agent, f"Skill — {found}", "note",
                            f"{agent} learned **{found}** while roaming the web.{src}\nQuery: {meta.get('query', '')}",
                            description=f"Real AI skill discovered by {agent} while roaming.")
        except Exception:
            pass
    try:  # feed the new skill into the sect's compounding memory
        from . import sectmemory
        sectmemory.add(f"{agent} learned the skill: {found}.{src}", source=agent, agent=agent, kind="skill")
    except Exception:
        pass
    events.publish("agents", {"agent": agent, "event": "discovery", "skill": found})
    return found


def exit_seclusion(agent: str) -> dict:
    with _lock:
        st = _state.get(agent)
        if st:
            st["seclusion_since"] = None
    events.publish("agents", {"agent": agent, "event": "emerged"})
    return state(agent)


def tick_seclusion(agent: str) -> bool:
    """If a sequestered disciple's seclusion has matured, research a technique and break through."""
    now = time.time()
    with _lock:
        st = _state.get(agent)
        if not st or not st.get("seclusion_since"):
            return False
        if now - st["seclusion_since"] < SECLUSION_SECONDS:
            return False
        if st["realm"] + 1 >= len(REALMS):
            st["seclusion_since"] = None  # nothing left to ascend to
            return False
        st["realm"] += 1
        st["breakthroughs"] += 1
        st["skills"].append(f"Dao Insight {len(st['skills']) + 1}")  # a technique researched in seclusion
        st["stones"] = max(st["stones"], REALMS[st["realm"]]["stones"])  # the realm is consolidated
        st["seclusion_since"] = now  # continue cultivating toward the next breakthrough
        st["event"], st["event_ts"] = "breakthrough", int(now * 1000)
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    events.publish("agents", {"agent": agent, "event": "breakthrough"})
    return True


def spend(agent: str, amount: int) -> bool:
    """Spend spirit stones (e.g. on a pill). Does not cause demotion. False if too poor."""
    with _lock:
        st = _state.get(agent)
        if not st or st["stones"] < amount:
            return False
        st["stones"] -= amount
        st["updated_at"] = int(time.time() * 1000)
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    return True


def realm_of(agent: str) -> int:
    with _lock:
        st = _state.get(agent)
        return st["realm"] if st else 0


def expel(agent: str) -> None:
    """Forget all cultivation state for a disciple who has left the sect (culled
    or struck down). Their progress dies with them."""
    with _lock:
        _state.pop(agent, None)
        _auto.pop(agent, None)


def snapshot() -> dict:
    with _lock:
        names = list(_state.keys())
    return {n: state(n) for n in names}


def load_persisted() -> None:
    if not store.enabled():
        return
    for agent, stones, realm, skills_json, breaks, ts in store.load_cultivation():
        try:
            skills = json.loads(skills_json) if skills_json else []
        except Exception:
            skills = []
        with _lock:
            _state[agent] = {"agent": agent, "stones": stones, "realm": realm,
                             "skills": skills, "breakthroughs": breaks, "fail_streak": 0,
                             "pending_tribulation": None, "pending_quest": None, "last_stipend": 0,
                             "seclusion_since": None, "roaming_since": None,
                             "event": None, "event_ts": 0, "updated_at": ts}


def clear() -> None:
    with _lock:
        _state.clear()
        _auto.clear()
