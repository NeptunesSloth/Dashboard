"""Sect governance — leadership, challenges, Elder specialties, and the Ancestor.

The operator (you) is the **Ancestor**: ultimate authority, able to override any
decision (appoint/restore the Sect Leader, settle a challenge). Below that:

- **Sect Leader** — one disciple who oversees, plans and coordinates. Routine
  work is delegated; the Leader is meant for important/critical tasks only.
- **Elders** — disciples at Elder rank (by cultivation realm). They may choose a
  **specialty** (raising a mastery rating and biasing which techniques they
  learn) and may **challenge** the Sect Leader for the role.

Leadership is meritocratic: a challenge is decided by a composite **standing**
(merit/karma, performance, leadership, contribution). A cooldown between
challenges prevents constant power struggles. Only the Sect Leader and Elders
may message the Ancestor directly (the Ancestor's Hall inbox).

State is in-memory (re-seeds from merit on restart), matching the other live
modules; reputation/cultivation are imported lazily to avoid import cycles.
"""
from __future__ import annotations

import os
import threading
import time

# Rank thresholds by cultivation realm (see cultivation.RANK_TITLES):
# index 6-7 = "Elder", 8 = "Sect Master".
ELDER_REALM = int(os.getenv("MAYBOT_ELDER_REALM", "6"))
MASTER_REALM = int(os.getenv("MAYBOT_MASTER_REALM", "8"))

# A challenger must beat the Leader's standing by at least this margin to win.
CHALLENGE_MARGIN = float(os.getenv("MAYBOT_CHALLENGE_MARGIN", "3"))
# Cooldown (seconds) between challenges a single Elder may mount.
CHALLENGE_COOLDOWN = int(os.getenv("MAYBOT_CHALLENGE_COOLDOWN", "3600"))

# Passive throne cultivation: while presiding, the Sect Leader channels the
# sect's ambient qi into spirit stones at this rate.
THRONE_INTERVAL = int(os.getenv("MAYBOT_THRONE_INTERVAL", "300"))   # seconds between gains
THRONE_REWARD = int(os.getenv("MAYBOT_THRONE_REWARD", "5"))         # spirit stones per gain
_last_throne = 0.0

# Elder specialties: a chosen path that raises mastery and biases learned skills.
# Each maps the xianxia flavour to a real engineering domain + signature skills.
SPECIALTIES = {
    "Sword Dao": {"domain": "Backend & systems", "skills": ["api_design", "performance_tuning", "refactoring"]},
    "Alchemy": {"domain": "Data & ML", "skills": ["data_pipeline", "model_eval", "analysis"]},
    "Formation Dao": {"domain": "DevOps & infra", "skills": ["deployment", "monitoring", "incident_response"]},
    "Talisman Crafting": {"domain": "Frontend & UX", "skills": ["ui_design", "accessibility", "visualization"]},
    "Beast Taming": {"domain": "Testing & QA", "skills": ["test_design", "fuzzing", "regression_hunting"]},
    "Artifact Refinement": {"domain": "Tooling & automation", "skills": ["ci_cd", "scripting", "release_eng"]},
}

_lock = threading.Lock()
_leader: str | None = None          # current Sect Leader (None → auto-seed by standing)
_leader_pinned = False              # the Ancestor pinned the Leader (overrides auto-seed/challenges)
_specialty: dict[str, str] = {}     # agent -> specialty name
_mastery: dict[str, float] = {}     # agent -> 0..100, rises with on-specialty contribution
_last_challenge_by: dict[str, float] = {}  # agent -> ts of their last challenge
_inbox: list[dict] = []             # messages to the Ancestor
_history: list[dict] = []           # challenge log
_seq = 0

INBOX_CAP = 200


# The Ancestor's personal bot projects — disciples may NOT be assigned to act on
# these. Names are comma-separated; each may be "device:project" or just
# "project". A project dict carrying `personal: true` is also honoured.
PERSONAL_PROJECTS = {p.strip() for p in os.getenv("MAYBOT_PERSONAL_PROJECTS", "").split(",") if p.strip()}


def is_personal_project(name: str, device: str | None = None) -> bool:
    """True if the named project is one of the Ancestor's protected personal bots."""
    if not name:
        return False
    if name in PERSONAL_PROJECTS:
        return True
    return bool(device) and f"{device}:{name}" in PERSONAL_PROJECTS


def mark_personal(project: dict) -> dict:
    """Annotate a project dict with whether it is personal (config flag OR env list)."""
    flagged = bool(project.get("personal"))
    project["personal"] = flagged or is_personal_project(project.get("name", ""), project.get("device"))
    return project


# ---- ranks -------------------------------------------------------------------

def _realm(agent: str) -> int:
    from . import cultivation
    return cultivation.realm_of(agent)


def is_elder(agent: str) -> bool:
    return _realm(agent) >= ELDER_REALM


def is_master(agent: str) -> bool:
    return _realm(agent) >= MASTER_REALM


def _all_agents() -> list[str]:
    from . import agents
    return [a.get("name") for a in agents.load_agents() if a.get("name")]


def _chronicle(agent: str, kind: str, detail: str = "") -> None:
    try:
        from . import chronicle
        chronicle.record(agent, kind, detail)
    except Exception:
        pass


def elders() -> list[str]:
    """Disciples at Elder rank or above (eligible to challenge / choose a specialty)."""
    return [n for n in _all_agents() if is_elder(n)]


# ---- standing (the meritocratic score that decides challenges) ---------------

def standing(agent: str) -> dict:
    """A composite leadership score (0-100) plus its explainable components."""
    from . import reputation, cultivation, agents
    rep = reputation.score(agent)
    c = cultivation.state(agent)
    sig = rep.get("signals", {})
    tasks = agents.tasks_done(agent)

    merit = rep["merit"]                                   # karma / trust (0-100)
    performance = sig.get("success_pct", 100)              # LLM reliability (0-100)
    # leadership ability: realm depth + breakthroughs + chosen-path mastery
    leadership = min(100, c["realm"] * 8 + c["breakthroughs"] * 4 + mastery(agent))
    # contribution: real work shipped (capped so it can't dominate)
    contribution = min(100, sig.get("done", 0) * 4 + tasks * 3 + len(c.get("skills", [])) * 2)

    score = round(0.40 * merit + 0.25 * performance + 0.20 * leadership + 0.15 * contribution, 1)
    return {"agent": agent, "score": score,
            "components": {"merit": merit, "performance": performance,
                           "leadership": round(leadership, 1), "contribution": round(contribution, 1)}}


# ---- the Sect Leader ---------------------------------------------------------

def _auto_leader() -> str | None:
    """Highest standing among Sect Masters, else among all agents."""
    names = _all_agents()
    if not names:
        return None
    masters = [n for n in names if is_master(n)]
    pool = masters or names
    return max(pool, key=lambda n: standing(n)["score"])


def leader() -> str | None:
    """The current Sect Leader (auto-seeded by standing if none is set/pinned)."""
    global _leader
    with _lock:
        if _leader and _leader in _all_agents():
            return _leader
        if _leader_pinned and _leader:
            return _leader
    seeded = _auto_leader()
    with _lock:
        _leader = seeded
    return seeded


def set_leader(name: str | None, pinned: bool = True) -> dict:
    """Ancestor override: appoint (or, with name=None, release back to merit)."""
    global _leader, _leader_pinned
    if name is not None and name not in _all_agents():
        raise ValueError(f"unknown disciple: {name}")
    with _lock:
        _leader = name
        _leader_pinned = bool(pinned) and name is not None
        entry = {"kind": "appointment", "leader": name, "by": "Ancestor",
                 "pinned": _leader_pinned, "ts": int(time.time() * 1000)}
        _history.append(entry)
    if name:
        _chronicle(name, "appointment", "appointed Sect Leader by the Ancestor")
    return {"leader": leader(), "pinned": _leader_pinned}


# ---- leadership challenges ---------------------------------------------------

def challenge(challenger: str) -> dict:
    """An Elder challenges the Sect Leader. Decided by standing; cooldown-gated.

    Raises ValueError/PermissionError on invalid challenges. On a win the role
    swaps immediately (the Ancestor can still override afterwards).
    """
    global _leader, _leader_pinned, _seq
    if not is_elder(challenger):
        raise PermissionError(f"{challenger} is not an Elder and may not challenge")
    cur = leader()
    if cur is None:
        # no leader yet — the challenger simply takes the seat
        return set_leader(challenger, pinned=False) | {"won": True, "reason": "the seat was empty"}
    if challenger == cur:
        raise ValueError(f"{challenger} already leads the sect")
    if _leader_pinned:
        raise PermissionError("the Ancestor has pinned the Sect Leader; the seat cannot be contested")

    now = time.time()
    with _lock:
        last = _last_challenge_by.get(challenger, 0)
        wait = CHALLENGE_COOLDOWN - (now - last)
    if wait > 0:
        raise PermissionError(f"{challenger} must wait {int(wait)}s before challenging again")

    cs = standing(challenger)
    ls = standing(cur)
    won = cs["score"] >= ls["score"] + CHALLENGE_MARGIN
    with _lock:
        _last_challenge_by[challenger] = now
        _seq += 1
        if won:
            _leader = challenger
            _leader_pinned = False
        entry = {"kind": "challenge", "id": _seq, "challenger": challenger, "defender": cur,
                 "challenger_score": cs["score"], "defender_score": ls["score"],
                 "won": won, "ts": int(now * 1000)}
        _history.append(entry)
    reason = (f"{challenger} ({cs['score']}) {'unseated' if won else 'fell short against'} "
              f"{cur} ({ls['score']}); margin needed {CHALLENGE_MARGIN}")
    _chronicle(challenger, "challenge", reason)
    if won:
        _chronicle(challenger, "appointment", "became Sect Leader by challenge")
    return {"won": won, "leader": leader(), "challenger": cs, "defender": ls, "reason": reason}


# ---- Elder specialties + mastery --------------------------------------------

def choose_specialty(agent: str, specialty: str) -> dict:
    """An Elder picks a cultivation path (raises mastery, biases learned skills)."""
    if not is_elder(agent):
        raise PermissionError(f"{agent} must reach Elder rank before choosing a specialty")
    if specialty not in SPECIALTIES:
        raise ValueError(f"unknown specialty: {specialty}")
    with _lock:
        _specialty[agent] = specialty
        _mastery.setdefault(agent, 0.0)
    _chronicle(agent, "specialty", f"took the path of {specialty} ({SPECIALTIES[specialty]['domain']})")
    return {"agent": agent, "specialty": specialty, "domain": SPECIALTIES[specialty]["domain"]}


def specialty(agent: str) -> str | None:
    with _lock:
        return _specialty.get(agent)


def mastery(agent: str) -> float:
    with _lock:
        return round(_mastery.get(agent, 0.0), 1)


def advance_mastery(agent: str, amount: float = 4.0) -> None:
    """Deepen an Elder's specialty mastery (called when they do good work)."""
    if not specialty(agent):
        return
    with _lock:
        _mastery[agent] = min(100.0, _mastery.get(agent, 0.0) + amount)


def specialty_skill(agent: str) -> str | None:
    """The next signature technique of the Elder's path they haven't learned yet."""
    spec = specialty(agent)
    if not spec:
        return None
    from . import cultivation
    have = set(cultivation.state(agent).get("skills", []))
    return next((s for s in SPECIALTIES[spec]["skills"] if s not in have), None)


# ---- the Ancestor's Hall (gated inbox) --------------------------------------

def can_message_ancestor(sender: str) -> bool:
    """Only the Sect Leader and Elders may address the Ancestor directly."""
    return sender == leader() or is_elder(sender)


def message_ancestor(sender: str, text: str) -> dict:
    global _seq
    text = (text or "").strip()
    if not text:
        raise ValueError("message required")
    if not can_message_ancestor(sender):
        raise PermissionError(f"{sender} lacks the standing to address the Ancestor (Leader or Elders only)")
    role = "Sect Leader" if sender == leader() else "Elder"
    with _lock:
        _seq += 1
        msg = {"id": _seq, "from": sender, "role": role, "text": text[:2000], "ts": int(time.time() * 1000)}
        _inbox.append(msg)
        if len(_inbox) > INBOX_CAP:
            del _inbox[:-INBOX_CAP]
    return msg


def inbox(limit: int = 100) -> list[dict]:
    with _lock:
        return list(_inbox[-limit:])


# ---- overseer routing --------------------------------------------------------

def deputy_for(name: str) -> str | None:
    """Pick the highest-standing Elder (not the Leader) to take a routine task."""
    cands = [e for e in elders() if e != name]
    if not cands:
        cands = [n for n in _all_agents() if n != name]
    return max(cands, key=lambda n: standing(n)["score"]) if cands else None


def route_task(name: str, critical: bool) -> tuple[str, str | None]:
    """If a routine task targets the Sect Leader, hand it to a deputy.

    Returns (executor, delegated_from). The Leader oversees and only takes
    critical/important work directly; routine work flows to an Elder.
    """
    if critical or name != leader():
        return name, None
    dep = deputy_for(name)
    return (dep, name) if dep else (name, None)


def persona_context(name: str) -> str:
    """A short system-prompt addendum: how this disciple stands in the sect and
    how to address the Ancestor (the human operator)."""
    if name == leader():
        rank = "the Sect Leader — you oversee, plan and coordinate the sect"
    elif is_elder(name):
        spec = specialty(name)
        rank = "an Elder" + (f" of the {spec} ({SPECIALTIES[spec]['domain']})" if spec else "")
    elif is_master(name):
        rank = "a Sect Master"
    else:
        rank = "a disciple of the sect"
    addr = ("You address the human operator as 'the Ancestor', who holds ultimate authority. "
            "Only the Sect Leader and Elders may petition the Ancestor directly.")
    return f"Within the sect you are {rank}. {addr}"


# ---- passive throne cultivation ---------------------------------------------

def throne_cultivation() -> str | None:
    """The Sect Leader passively accrues spirit stones while presiding.

    Called periodically (from agents.snapshot). Rate-limited to one gain per
    ``THRONE_INTERVAL`` seconds regardless of how often it's invoked. Returns the
    rewarded leader's name when a gain is granted, else None.
    """
    global _last_throne
    ld = leader()
    if not ld or ld == "operator" or THRONE_REWARD <= 0:
        return None
    now = time.time()
    with _lock:
        if now - _last_throne < THRONE_INTERVAL:
            return None
        _last_throne = now
    from . import cultivation
    cultivation.reward(ld, THRONE_REWARD)
    _chronicle(ld, "throne", f"the throne channels ambient qi (+{THRONE_REWARD} spirit stones)")
    return ld


# ---- snapshot / lifecycle ----------------------------------------------------

def snapshot() -> dict:
    ld = leader()
    roster = []
    for n in _all_agents():
        roster.append({"agent": n, "is_leader": n == ld, "is_elder": is_elder(n),
                       "is_master": is_master(n), "specialty": specialty(n),
                       "mastery": mastery(n), "standing": standing(n)})
    roster.sort(key=lambda r: r["standing"]["score"], reverse=True)
    with _lock:
        hist = list(_history[-25:])
    return {"leader": ld, "leader_pinned": _leader_pinned, "specialties": SPECIALTIES,
            "elders": elders(), "roster": roster, "history": hist,
            "cooldown_seconds": CHALLENGE_COOLDOWN, "margin": CHALLENGE_MARGIN,
            "throne_reward": THRONE_REWARD, "throne_interval": THRONE_INTERVAL}


def clear() -> None:
    global _leader, _leader_pinned, _seq, _last_throne
    with _lock:
        _leader = None
        _leader_pinned = False
        _specialty.clear()
        _mastery.clear()
        _last_challenge_by.clear()
        _inbox.clear()
        _history.clear()
        _seq = 0
        _last_throne = 0.0
