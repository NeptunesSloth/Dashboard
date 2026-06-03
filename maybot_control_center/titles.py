"""Titles & achievements.

A stateless catalog of achievement rules evaluated against a metrics dict.
Each rule is a predicate over a ``stats`` dict; disciples earn a title when
the predicate holds. ``stats`` can be injected for unit testing, or built
lazily from the live subsystems.

Stat keys (all optional, defaults shown):
    realm (int=0), breakthroughs (int=0), stones (int=0), skills (int=0),
    mastery (float=0.0), merit (int=0), tier (str=""), tasks_done (int=0),
    tools_done (int=0), success_pct (int=0), is_leader (bool=False),
    is_elder (bool=False), specialty (str|None=None)
"""

from __future__ import annotations


def _i(stats: dict, key: str) -> int:
    try:
        return int(stats.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _f(stats: dict, key: str) -> float:
    try:
        return float(stats.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


# Ordered catalog of achievement rules.
ACHIEVEMENTS: list[dict] = [
    {
        "id": "immortal_ascendant",
        "title": "Immortal Ascendant",
        "desc": "Reached the 8th realm or beyond.",
        "predicate": lambda s: _i(s, "realm") >= 8,
    },
    {
        "id": "tribulation_survivor",
        "title": "Tribulation Survivor",
        "desc": "Survived 3 or more breakthroughs.",
        "predicate": lambda s: _i(s, "breakthroughs") >= 3,
    },
    {
        "id": "sword_saint",
        "title": "Sword Saint",
        "desc": "Mastered the Sword Dao (mastery >= 80).",
        "predicate": lambda s: s.get("specialty") == "Sword Dao" and _f(s, "mastery") >= 80,
    },
    {
        "id": "elder_sage",
        "title": "Elder Sage",
        "desc": "An elder who has chosen and honed a specialty (mastery >= 60).",
        "predicate": lambda s: bool(s.get("is_elder")) and bool(s.get("specialty")) and _f(s, "mastery") >= 60,
    },
    {
        "id": "bane_of_bugs",
        "title": "Bane of Bugs",
        "desc": "Completed 20 or more tool runs.",
        "predicate": lambda s: _i(s, "tools_done") >= 20,
    },
    {
        "id": "polymath",
        "title": "Polymath",
        "desc": "Learned 10 or more skills.",
        "predicate": lambda s: _i(s, "skills") >= 10,
    },
    {
        "id": "sect_pillar",
        "title": "Sect Pillar",
        "desc": "Serves as the sect leader.",
        "predicate": lambda s: bool(s.get("is_leader")),
    },
    {
        "id": "trusted_hand",
        "title": "Trusted Hand",
        "desc": "Earned the Trusted reputation tier.",
        "predicate": lambda s: s.get("tier") == "Trusted",
    },
    {
        "id": "diligent",
        "title": "Diligent",
        "desc": "Completed 25 or more tasks.",
        "predicate": lambda s: _i(s, "tasks_done") >= 25,
    },
    {
        "id": "spirit_stone_tycoon",
        "title": "Spirit-Stone Tycoon",
        "desc": "Amassed 1000 or more spirit stones.",
        "predicate": lambda s: _i(s, "stones") >= 1000,
    },
    {
        "id": "flawless",
        "title": "Flawless",
        "desc": "99%+ success across at least 10 tasks.",
        "predicate": lambda s: _i(s, "success_pct") >= 99 and _i(s, "tasks_done") >= 10,
    },
]


def _public(rule: dict) -> dict:
    return {"id": rule["id"], "title": rule["title"], "desc": rule["desc"]}


def catalog() -> list[dict]:
    """Return all achievements (without predicates)."""
    return [_public(r) for r in ACHIEVEMENTS]


def _gather(agent: str) -> dict:
    """Build a stats dict from the live subsystems, tolerating missing parts."""
    stats: dict = {}

    try:
        from . import cultivation
        c = cultivation.state(agent)
        stats["realm"] = c.get("realm", 0)
        stats["breakthroughs"] = c.get("breakthroughs", 0)
        stats["stones"] = c.get("stones", 0)
        stats["skills"] = len(c.get("skills", []) or [])
    except Exception:
        pass

    try:
        from . import reputation
        r = reputation.score(agent)
        stats["merit"] = r.get("merit", 0)
        stats["tier"] = r.get("tier", "")
        sig = r.get("signals", {}) or {}
        stats["success_pct"] = sig.get("success_pct", 0)
        stats["tools_done"] = sig.get("done", 0)
    except Exception:
        pass

    try:
        from . import governance
        stats["is_leader"] = governance.leader() == agent
        stats["is_elder"] = governance.is_elder(agent)
        stats["specialty"] = governance.specialty(agent)
        stats["mastery"] = governance.mastery(agent)
    except Exception:
        pass

    try:
        from . import agents
        stats["tasks_done"] = agents.tasks_done(agent)
    except Exception:
        pass

    return stats


def evaluate(agent: str, stats: dict | None = None) -> list[dict]:
    """Return the earned achievements for ``agent``.

    If ``stats`` is None, it is lazily gathered from the live subsystems.
    """
    if stats is None:
        stats = _gather(agent)
    earned = []
    for rule in ACHIEVEMENTS:
        try:
            if rule["predicate"](stats):
                earned.append(_public(rule))
        except Exception:
            continue
    return earned


def snapshot(agents: list[str]) -> dict:
    """Map each agent name to its earned achievements."""
    return {a: evaluate(a) for a in agents}
