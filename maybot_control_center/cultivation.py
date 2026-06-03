"""Agent cultivation: spirit stones (merit) + cultivation realms.

Disciples (agents) earn **spirit stones** for good work — completing tasks,
mastering **techniques** (succeeding at a tool they've never used before), and
joining the Dao Council. Mastering a brand-new technique is a new *skill*; with
enough spirit stones AND enough techniques, a disciple **breaks through** to the
next cultivation realm. Persisted via store when MAYBOT_DB is set.
"""
from __future__ import annotations

import json
import threading
import time

from . import store
from . import events

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

AWARD_TASK = 12
AWARD_TOOL = 16
AWARD_NEW_SKILL = 40
AWARD_COUNCIL = 6
# Punishment: each failure chips away spirit stones; a streak of them calls down
# a heavenly tribulation that can strike a disciple down a realm (qi deviation).
PENALTY_FAIL = 8
TRIBULATION_STREAK = 3
TRIBULATION_LOSS = 70

_lock = threading.Lock()
_state: dict[str, dict] = {}


def _blank(agent: str) -> dict:
    return {"agent": agent, "stones": 0, "realm": 0, "skills": [], "breakthroughs": 0,
            "fail_streak": 0, "event": None, "event_ts": 0, "updated_at": 0}


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
    return {"new_skill": new_skill, "breakthrough": broke}


def _fail(agent: str) -> dict:
    """A misstep: lose stones; a streak of them invites a heavenly tribulation."""
    now = int(time.time() * 1000)
    with _lock:
        st = _state.get(agent) or _blank(agent)
        _state[agent] = st
        st["fail_streak"] += 1
        st["stones"] = max(0, st["stones"] - PENALTY_FAIL)
        tribulation = struck = False
        if st["fail_streak"] >= TRIBULATION_STREAK:
            st["stones"] = max(0, st["stones"] - TRIBULATION_LOSS)
            struck = _demote_if_deviated(st)
            st["fail_streak"] = 0
            tribulation = True
            st["event"], st["event_ts"] = "tribulation", now
        st["updated_at"] = now
        snap = dict(st)
        snap["skills"] = list(st["skills"])
    if store.enabled():
        store.upsert_cultivation(snap)
    if tribulation:
        events.publish("agents", {"agent": agent, "event": "tribulation", "struck": struck})
    return {"tribulation": tribulation, "struck": struck}


def on_task(agent: str, ok: bool) -> None:
    if not agent or agent == "operator":
        return
    _award(agent, AWARD_TASK) if ok else _fail(agent)


def on_tool(agent: str, tool: str, ok: bool) -> None:
    if not agent or agent == "operator":
        return
    _award(agent, AWARD_TOOL, skill=tool) if ok else _fail(agent)


def on_council(agent: str) -> None:
    if agent and agent != "operator":
        _award(agent, AWARD_COUNCIL)


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


def state(agent: str) -> dict:
    with _lock:
        st = dict(_state.get(agent) or _blank(agent))
        st["skills"] = list(st.get("skills", []))
    realm = st["realm"]
    nxt = REALMS[realm + 1] if realm + 1 < len(REALMS) else None
    return {
        "realm": realm,
        "realm_name": REALMS[realm]["name"],
        "stage": _stage(st),
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
                             "skills": skills, "breakthroughs": breaks,
                             "fail_streak": 0, "event": None, "event_ts": 0, "updated_at": ts}


def clear() -> None:
    with _lock:
        _state.clear()
