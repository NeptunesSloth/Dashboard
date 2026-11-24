"""The sect: a small colony sim in the cultivation world.

The sect is a colony of disciples who each have needs (food, rest, joy), a
mood, skills with passions, traits, and a list of work priorities you set. They
farm, cut wood, quarry, forage, build, brew pills, research and meditate on
their own, hour by hour. A storyteller sends events: wanderers, merchants,
windfalls, sickness, beast tides and raids that scale with the sect's wealth.

The sim runs on its own clock and does **not** need study to progress: every
disciple (the Sect Master included) cultivates by meditating. Study is a
second, optional engine wired in at three points:

* each graded answer gives the Sect Master qi and the sect a point of *insight*
  (spent automatically on research);
* a finished study session gives every disciple a "the Master lectured" mood
  lift for a day;
* a passed trial gives every disciple a surge of qi.

Time: one tick is one sim hour. The page drives ticks while it is open; while it
is closed the sect advances in *quiet mode* (work and needs, no events, nobody
starves or dies) for at most two sim days per real day.

Everything here mutates ``st["colony"]``; the engine owns locking and saving.
"""
from __future__ import annotations

import datetime as _dt
import math
import random

REALMS = ["Mortal", "Qi Condensation", "Foundation Establishment", "Core Formation",
          "Nascent Soul", "Soul Transformation", "Void Refinement", "Immortal Ascension"]
STAGES = ["Early", "Middle", "Late", "Peak"]
MAX_STEP = len(REALMS) * len(STAGES) - 1
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
DAYS_PER_SEASON = 12
STORYTELLERS = {
    "calm":     {"name": "Gentle Rain", "blurb": "Few dangers. Good for learning the ropes.", "event": 0.25, "threat_gap": 99999, "threat": 0.0, "deaths": False},
    "balanced": {"name": "Turning Seasons", "blurb": "Trouble comes, with room to recover.", "event": 0.38, "threat_gap": 5, "threat": 1.0, "deaths": True},
    "harsh":    {"name": "Heaven's Trial", "blurb": "Frequent raids. Disciples can die.", "event": 0.5, "threat_gap": 3, "threat": 1.35, "deaths": True},
}

SKILLS = ["farm", "gather", "build", "craft", "scholar", "combat"]
SKILL_NAMES = {"farm": "Farming", "gather": "Gathering", "build": "Construction", "craft": "Alchemy",
               "scholar": "Scholarship", "combat": "Combat"}
# job -> (label, skill it uses)
JOBS = {
    "build":    ("Build", "build"),
    "farm":     ("Farm", "farm"),
    "wood":     ("Cut wood", "gather"),
    "mine":     ("Quarry", "gather"),
    "forage":   ("Forage herbs", "gather"),
    "craft":    ("Brew pills", "craft"),
    "research": ("Research", "scholar"),
    "train":    ("Train", "combat"),
    "meditate": ("Meditate", "scholar"),
}
DEFAULT_PRIO = {"build": 1, "farm": 2, "wood": 3, "mine": 3, "forage": 3, "craft": 3, "research": 3, "train": 4, "meditate": 4}

TRAITS = {
    "Hardworking":  "Works 15% faster.",
    "Lazy":         "Works 15% slower.",
    "Optimist":     "+8 mood, always.",
    "Pessimist":    "-8 mood, always.",
    "Glutton":      "Gets hungry 40% faster.",
    "Ascetic":      "Needs little joy and never minds sleeping rough.",
    "Tough":        "Takes 40% less damage.",
    "Frail":        "Takes 40% more damage.",
    "Quick learner": "Skills grow 50% faster.",
    "Green thumb":  "Farms 25% better.",
    "Bookworm":     "Researches 25% better and enjoys it.",
    "Iron will":    "Almost never breaks under a low mood.",
    "Volatile":     "Breaks sooner under a low mood.",
    "Sword-mad":    "Trains twice as fast.",
}
OPPOSED = [{"Hardworking", "Lazy"}, {"Optimist", "Pessimist"}, {"Tough", "Frail"}, {"Iron will", "Volatile"}]
ROOTS = [("Common", 1.0, 52), ("Good", 1.2, 28), ("Superior", 1.45, 13), ("Heaven Grade", 1.75, 6), ("Saint Grade", 2.1, 1)]
SURNAMES = ["Lin", "Zhao", "Mo", "Yun", "Feng", "Bai", "Xiao", "Shen", "Luo", "Han", "Qin", "Su", "Ye", "Gu", "Jiang", "Tang"]
GIVEN = ["Wei", "Yan", "Chen", "Xue", "Ling", "Hao", "Mei", "Rou", "Jin", "Tian", "Qing", "Yu", "An", "Zhi", "Lan", "Shuo",
         "Feiyan", "Wuji", "Ruoxi", "Changge", "Yichen", "Suyin"]

# Rooms. cost(level) = base * 1.8**level, plus spirit stones from the third level.
ROOMS = {
    "main_hall":   {"name": "Main Hall", "wood": 40, "stone": 30, "max": 5,
                    "effect": "The heart of the sect. Other rooms can be at most one level above it, and each level houses the fame that draws wanderers."},
    "dormitory":   {"name": "Dormitory", "wood": 30, "stone": 10, "max": 5, "effect": "Three beds per level. Disciples without a bed sleep badly."},
    "fields":      {"name": "Rice Terraces", "wood": 20, "stone": 10, "max": 5, "effect": "Two farmers per level, and a better yield. Nothing grows in winter."},
    "storehouse":  {"name": "Storehouse", "wood": 30, "stone": 20, "max": 5, "effect": "Raises how much rice, wood, stone and herbs you can keep."},
    "library":     {"name": "Scripture Pavilion", "wood": 35, "stone": 20, "max": 5, "effect": "Lets disciples research. Faster per level."},
    "meditation":  {"name": "Meditation Chamber", "wood": 25, "stone": 25, "max": 5, "effect": "+15% qi from meditation per level."},
    "alchemy":     {"name": "Alchemy Hall", "wood": 25, "stone": 30, "max": 5, "effect": "Lets disciples brew pills from herbs. Pills heal and steady a breakthrough."},
    "training":    {"name": "Training Grounds", "wood": 30, "stone": 15, "max": 5, "effect": "Lets disciples train for combat. Faster per level."},
    "ward":        {"name": "Ward Formation", "wood": 15, "stone": 45, "max": 5, "effect": "Defends the sect on its own. Stronger per level."},
    "spirit_vein": {"name": "Spirit Vein", "wood": 20, "stone": 40, "max": 5, "effect": "Quarrying also yields spirit stones, and meditation gains +5% per level."},
    "market":      {"name": "Trade Post", "wood": 35, "stone": 15, "max": 3, "effect": "Merchants visit more often and pay better."},
}
RESEARCH = {
    "irrigation": {"name": "Terraced irrigation", "cost": 150, "effect": "+25% rice from farming."},
    "masonry":    {"name": "Stone masonry", "cost": 180, "effect": "Rooms cost 20% less stone."},
    "granary":    {"name": "Sealed granaries", "cost": 220, "effect": "Storehouse holds 50% more."},
    "refinement": {"name": "Pill refinement", "cost": 260, "effect": "Pills need 2 herbs instead of 3."},
    "sword_forms": {"name": "Sword forms", "cost": 300, "effect": "+25% combat strength."},
    "qi_array":   {"name": "Qi-gathering array", "cost": 360, "effect": "+20% qi from meditation."},
    "ward_ii":    {"name": "Layered wards", "cost": 420, "effect": "+50% Ward Formation strength."},
    "dao_heart":  {"name": "Dao heart", "cost": 500, "effect": "+6 mood for everyone."},
}
RES = ["rice", "wood", "stone", "herbs", "pills", "stones"]
RES_NAMES = {"rice": "Rice", "wood": "Wood", "stone": "Stone", "herbs": "Herbs", "pills": "Pills", "stones": "Spirit stones"}

SECS_PER_HOUR_OFFLINE = 1800.0     # away: one sim hour per 30 real minutes
MAX_OFFLINE_HOURS = 48
MAX_TICK = 24                      # most sim hours one request may advance
WEEK_GOAL = 5


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------
def _rng(c: dict, *salt) -> random.Random:
    return random.Random(f"{c['seed']}:{':'.join(str(s) for s in salt)}")


def _make_pawn(c: dict, n: int, master_name: str = "") -> dict:
    r = _rng(c, "pawn", n)
    roll = r.uniform(0, sum(w for _, _, w in ROOTS))
    acc, root, mult = 0.0, ROOTS[0][0], ROOTS[0][1]
    for name, m, w in ROOTS:
        acc += w
        if roll <= acc:
            root, mult = name, m
            break
    traits: list[str] = []
    while len(traits) < 2:
        t = r.choice(list(TRAITS))
        if t not in traits and not any(t in pair and (set(traits) & pair) for pair in OPPOSED):
            traits.append(t)
    skills = {s: {"lv": r.randint(0, 7), "xp": 0.0, "passion": r.choices([0, 1, 2], [55, 32, 13])[0]} for s in SKILLS}
    best = r.choice(SKILLS)
    skills[best]["lv"] = max(skills[best]["lv"], r.randint(5, 10))
    if "Sword-mad" in traits:
        skills["combat"]["passion"] = 2
    pawn = {
        "id": f"p{n}", "name": master_name or f"{r.choice(SURNAMES)} {r.choice(GIVEN)}", "age": r.randint(16, 40),
        "master": bool(master_name), "root": "Heaven Grade" if master_name else root, "root_mult": 1.75 if master_name else mult,
        "traits": traits, "skills": skills,
        "food": 80.0, "rest": 80.0, "joy": 70.0, "mood": 60.0, "health": 100.0,
        "thoughts": [], "step": 0, "qi": 0.0, "prio": dict(DEFAULT_PRIO),
        "doing": "idle", "break_until": 0, "inspired_until": 0, "sick_until": 0, "joined": c["hour"],
    }
    if master_name:
        pawn["prio"].update(meditate=2, research=2, farm=3, build=2)
    return pawn


def new_colony(now: float) -> dict:
    c = {
        "name": "", "seed": random.randrange(1 << 30), "hour": 6, "storyteller": "balanced", "paused": False,
        "res": {"rice": 36.0, "wood": 45.0, "stone": 25.0, "herbs": 4.0, "pills": 1.0, "stones": 0.0},
        "rooms": {"main_hall": 1, "dormitory": 1, "fields": 1},
        "builds": [],                # [{room, need (work hours), done}]
        "pawns": [], "next_pawn": 0, "graves": 0,
        "research": {"done": [], "current": "", "progress": 0.0},
        "craft": 0.0, "insight": 0.0, "pending": None, "last_threat_day": 0, "last_event_day": 0,
        "log": [], "last_real": now, "hint": 0,
        # study habit (kept here so one object holds the whole game)
        "streak": 0, "best_streak": 0, "last_study_day": "", "grace": 2, "seclusion": False, "secluded_on": "",
        "week": {"id": "", "days": []},
    }
    return c


def setup(st: dict, name: str, master: str, now: float) -> dict:
    c = _c(st, now)
    first = not c["name"]
    c["name"] = (name or "").strip()[:40] or "Nameless Sect"
    master = (master or "").strip()[:30] or "Sect Master"
    if first:
        c["pawns"] = [_make_pawn(c, 0, master)] + [_make_pawn(c, i) for i in (1, 2)]
        c["next_pawn"] = 3
        _letter(c, "good", "The sect is founded",
                f"{master} and two disciples raise the first hall of the {c['name']}. There is rice for a few weeks. "
                "Set who does what in Work, and queue rooms in Build.")
    else:
        for p in c["pawns"]:
            if p.get("master"):
                p["name"] = master
    return {"ok": True}


def _c(st: dict, now: float) -> dict:
    c = st.get("colony")
    if not isinstance(c, dict) or "hour" not in c:
        c = new_colony(now)
        st["colony"] = c
    else:
        for k, v in new_colony(now).items():
            c.setdefault(k, v)
    return c


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _letter(c: dict, kind: str, title: str, text: str) -> dict:
    ev = {"hour": c["hour"], "kind": kind, "title": title, "text": text}
    c["log"] = (c["log"] + [ev])[-80:]
    return ev


def _day(c: dict) -> int:
    return c["hour"] // 24


def _season(c: dict) -> int:
    return (_day(c) // DAYS_PER_SEASON) % 4


def _lvl(c: dict, room: str) -> int:
    return int(c["rooms"].get(room, 0))


def _has(c: dict, tech: str) -> bool:
    return tech in c["research"]["done"]


def _cap(c: dict) -> float:
    return (150 + 120 * _lvl(c, "storehouse")) * (1.5 if _has(c, "granary") else 1.0)


def _add(c: dict, res: str, amount: float) -> None:
    v = c["res"].get(res, 0.0) + amount
    c["res"][res] = max(0.0, min(v, _cap(c)) if res in ("rice", "wood", "stone", "herbs") else v)


def _think(p: dict, key: str, label: str, value: int, hours: int, hour: int) -> None:
    p["thoughts"] = [t for t in p["thoughts"] if t["k"] != key] + [{"k": key, "label": label, "v": value, "until": hour + hours}]


def step_need(step: int) -> float:
    return 100.0 + 90.0 * step


def realm_label(step: int) -> str:
    return f"{REALMS[step // 4]} · {STAGES[step % 4]}"


def room_cost(c: dict, room: str, level: int) -> dict:
    r = ROOMS[room]
    k = 1.8 ** level
    cost = {"wood": int(round(r["wood"] * k / 5.0)) * 5,
            "stone": int(round(r["stone"] * k * (0.8 if _has(c, "masonry") else 1.0) / 5.0)) * 5}
    if level >= 2:
        cost["stones"] = 8 * (level - 1)
    return cost


def build_hours(level: int) -> float:
    return 16.0 * (level + 1)


def beds(c: dict) -> int:
    return 3 * _lvl(c, "dormitory")


def pawn_cap(c: dict) -> int:
    return 3 + 2 * _lvl(c, "main_hall")


def wealth(c: dict) -> float:
    r = c["res"]
    return (r["rice"] * 0.5 + r["wood"] * 0.4 + r["stone"] * 0.6 + r["herbs"] * 1.5 + r["pills"] * 8 + r["stones"] * 4
            + sum(c["rooms"].values()) * 45 + len(c["pawns"]) * 30)


def _skill_mult(p: dict, skill: str) -> float:
    return 0.5 + 0.075 * p["skills"][skill]["lv"]


def _work_mult(p: dict, hour: int) -> float:
    m = 1.0 + 0.04 * p["step"]
    m *= 1.15 if "Hardworking" in p["traits"] else 0.85 if "Lazy" in p["traits"] else 1.0
    m *= 0.8 if p["mood"] < 30 else 1.1 if p["mood"] > 72 else 1.0
    m *= 1.5 if p["inspired_until"] > hour else 1.0
    m *= max(0.3, p["health"] / 100.0)
    return m


def _xp(p: dict, skill: str, amount: float) -> None:
    s = p["skills"][skill]
    s["xp"] += amount * (0.4, 1.0, 1.6)[s["passion"]] * (1.5 if "Quick learner" in p["traits"] else 1.0)
    while s["lv"] < 20 and s["xp"] >= 20 * (s["lv"] + 1):
        s["xp"] -= 20 * (s["lv"] + 1)
        s["lv"] += 1


def _hurt(p: dict, amount: float) -> None:
    amount *= 0.6 if "Tough" in p["traits"] else 1.4 if "Frail" in p["traits"] else 1.0
    p["health"] = max(0.0, p["health"] - amount)


def combat_power(c: dict, p: dict) -> float:
    if p["health"] < 25 or p["break_until"] > c["hour"]:
        return 0.0
    return (10 + 4 * p["skills"]["combat"]["lv"]) * (1 + 0.07 * p["step"]) * (p["health"] / 100.0) \
        * (1.25 if _has(c, "sword_forms") else 1.0)


def defense(c: dict) -> float:
    ward = 18 * _lvl(c, "ward") * (1.5 if _has(c, "ward_ii") else 1.0)
    return sum(combat_power(c, p) for p in c["pawns"]) + ward


# ---------------------------------------------------------------------------
# one hour of one disciple
# ---------------------------------------------------------------------------
def _job_open(c: dict, job: str, taken: dict) -> bool:
    if job == "farm":
        return _lvl(c, "fields") > 0 and _season(c) != 3 and taken.get("farm", 0) < 2 * _lvl(c, "fields")
    if job == "build":
        return bool(c["builds"])
    if job == "craft":
        return _lvl(c, "alchemy") > 0 and c["res"]["herbs"] >= (2 if _has(c, "refinement") else 3)
    if job == "research":
        return _lvl(c, "library") > 0 and bool(c["research"]["current"])
    if job == "train":
        return _lvl(c, "training") > 0
    return True          # wood, mine, forage, meditate


def _pick_job(c: dict, p: dict, taken: dict) -> str:
    best, best_key = "", None
    for job, level in p["prio"].items():
        if not level or job not in JOBS or not _job_open(c, job, taken):
            continue
        # Same priority: do what the sect is shortest of, then what you are best at.
        stock = {"farm": "rice", "wood": "wood", "mine": "stone", "forage": "herbs"}.get(job)
        scarcity = c["res"][stock] / _cap(c) if stock else 0.5
        key = (level, round(scarcity, 2), -p["skills"][JOBS[job][1]]["lv"])
        if best_key is None or key < best_key:
            best, best_key = job, key
    return best


def _do_job(c: dict, p: dict, job: str, quiet: bool) -> None:
    hour = c["hour"]
    skill = JOBS[job][1]
    out = _skill_mult(p, skill) * _work_mult(p, hour)
    _xp(p, skill, 1.0 * (2.0 if job == "train" and "Sword-mad" in p["traits"] else 1.0))
    if job == "farm":
        y = 0.38 * (1 + 0.15 * (_lvl(c, "fields") - 1)) * (1.25 if _has(c, "irrigation") else 1.0)
        _add(c, "rice", out * y * (1.25 if "Green thumb" in p["traits"] else 1.0) * (1.2 if _season(c) == 2 else 1.0))
    elif job == "wood":
        _add(c, "wood", out * 1.0)
    elif job == "mine":
        _add(c, "stone", out * 0.7)
        if _lvl(c, "spirit_vein"):
            _add(c, "stones", out * 0.1 * _lvl(c, "spirit_vein"))
    elif job == "forage":
        _add(c, "herbs", out * 0.35 * (0.3 if _season(c) == 3 else 1.0))
    elif job == "build":
        b = c["builds"][0]
        b["done"] += out
        if b["done"] >= b["need"]:
            c["builds"].pop(0)
            c["rooms"][b["room"]] = _lvl(c, b["room"]) + 1
            lv = c["rooms"][b["room"]]
            _letter(c, "good", f"{ROOMS[b['room']]['name']} {'built' if lv == 1 else f'raised to level {lv}'}",
                    f"{p['name']} set the last stone.")
    elif job == "craft":
        c["craft"] += out * (1 + 0.15 * (_lvl(c, "alchemy") - 1))
        if c["craft"] >= 6.0:
            c["craft"] -= 6.0
            _add(c, "herbs", -(2 if _has(c, "refinement") else 3))
            _add(c, "pills", 1)
    elif job == "research":
        _research(c, out * (1 + 0.2 * (_lvl(c, "library") - 1)) * (1.25 if "Bookworm" in p["traits"] else 1.0))
        if "Bookworm" in p["traits"]:
            p["joy"] = min(100.0, p["joy"] + 3)
    elif job == "meditate":
        _gain_qi(c, p, _work_mult(p, hour) * p["root_mult"] * (1 + 0.15 * _lvl(c, "meditation"))
                 * (1 + 0.05 * _lvl(c, "spirit_vein")) * (1.2 if _has(c, "qi_array") else 1.0), quiet)
        p["joy"] = min(100.0, p["joy"] + 1.5)


def _research(c: dict, points: float) -> None:
    r = c["research"]
    if not r["current"] or r["current"] not in RESEARCH:
        return
    r["progress"] += points
    if r["progress"] >= RESEARCH[r["current"]]["cost"]:
        done = r["current"]
        r["done"].append(done)
        r.setdefault("banked", {}).pop(done, None)
        c["insight"] += r["progress"] - RESEARCH[done]["cost"]      # what was left over is not wasted
        r["current"], r["progress"] = "", 0.0
        _letter(c, "good", f"Research complete: {RESEARCH[done]['name']}", RESEARCH[done]["effect"])


def _gain_qi(c: dict, p: dict, amount: float, quiet: bool = False) -> None:
    """Add qi and attempt breakthroughs. A new great realm is a gamble; a pill steadies it."""
    p["qi"] += amount
    while p["step"] < MAX_STEP and p["qi"] >= step_need(p["step"]):
        major = p["step"] % 4 == 3
        if major and quiet:
            p["qi"] = step_need(p["step"])          # wait for the player to be watching
            return
        if major:
            chance = 0.55 + 0.02 * p["skills"]["scholar"]["lv"]
            if c["res"]["pills"] >= 1:
                c["res"]["pills"] -= 1
                chance += 0.25
            r = _rng(c, "bt", p["id"], c["hour"])
            if r.random() > chance:
                p["qi"] = step_need(p["step"]) * 0.6
                _hurt(p, 25)
                _think(p, "bt_fail", "Failed a breakthrough", -10, 48, c["hour"])
                _letter(c, "bad", f"{p['name']} failed a breakthrough",
                        f"The attempt on {REALMS[p['step'] // 4 + 1]} backfired. They are hurt and must gather qi again. "
                        "A pill in the stores steadies the next attempt.")
                return
        p["qi"] -= step_need(p["step"])
        p["step"] += 1
        _think(p, "bt", "Broke through", 15 if major else 6, 72 if major else 24, c["hour"])
        if major or p.get("master"):
            _letter(c, "good", f"{p['name']} reached {realm_label(p['step'])}",
                    "A new great realm. The whole sect feels it." if major else "A steady step forward.")
        if major:
            for o in c["pawns"]:
                if o is not p:
                    _think(o, "bt_other", "A fellow disciple ascended", 5, 48, c["hour"])


def _tick_pawn(c: dict, p: dict, taken: dict, quiet: bool) -> None:
    hour = c["hour"]
    hod = hour % 24
    night = hod >= 22 or hod < 6
    p["thoughts"] = [t for t in p["thoughts"] if t["until"] > hour]
    # --- needs decay
    p["food"] = max(0.0, p["food"] - 2.2 * (1.4 if "Glutton" in p["traits"] else 1.0))
    p["joy"] = max(0.0, p["joy"] - 1.2 * (0.5 if "Ascetic" in p["traits"] else 1.0))
    # --- eat (instant) when hungry
    if p["food"] < 35 and c["res"]["rice"] >= 1:
        c["res"]["rice"] -= 1
        p["food"] = min(100.0, p["food"] + 55)
    if p["food"] <= 0:
        _think(p, "starving", "Starving", -18, 6, hour)
        if not quiet and p["health"] > 34:
            _hurt(p, 1.5)                 # hunger weakens; it never pins a disciple to the sickbed
    elif p["food"] < 25:
        _think(p, "hungry", "Hungry", -8, 3, hour)
    # --- choose what to do this hour
    sick = p["sick_until"] > hour
    if p["health"] < 30 or sick:
        doing = "recovering"
        p["rest"] = min(100.0, p["rest"] + 8)
        p["health"] = min(100.0, p["health"] + (1.2 if not sick else 0.3))
    elif p["break_until"] > hour:
        doing = "wandering in a daze"
        p["rest"] = max(0.0, p["rest"] - 2)
        p["joy"] = min(100.0, p["joy"] + 4)
    elif p["rest"] < 18 or (night and p["rest"] < 92):
        doing = "sleeping"
        order = c["pawns"].index(p)
        has_bed = order < beds(c)
        p["rest"] = min(100.0, p["rest"] + (12 if has_bed else 8))
        if not has_bed and "Ascetic" not in p["traits"]:
            _think(p, "no_bed", "Slept on the ground", -6, 20, hour)
        p["health"] = min(100.0, p["health"] + 0.6)
    elif p["joy"] < 18:
        doing = "relaxing"
        p["joy"] = min(100.0, p["joy"] + 16)
        p["rest"] = max(0.0, p["rest"] - 2)
    else:
        job = _pick_job(c, p, taken)
        p["rest"] = max(0.0, p["rest"] - 3.2)
        if job:
            taken[job] = taken.get(job, 0) + 1
            _do_job(c, p, job, quiet)
            doing = JOBS[job][0].lower()
        else:
            doing = "idle"
            p["joy"] = min(100.0, p["joy"] + 3)
        p["health"] = min(100.0, p["health"] + 0.15)
    p["doing"] = doing
    # --- mood drifts toward what the disciple has to feel about
    target = 50 + sum(t["v"] for t in p["thoughts"])
    target += 8 if "Optimist" in p["traits"] else -8 if "Pessimist" in p["traits"] else 0
    target += 6 if _has(c, "dao_heart") else 0
    target += -8 if p["rest"] < 25 else 0
    target += -8 if p["joy"] < 25 else 4 if p["joy"] > 75 else 0
    target += -6 if p["health"] < 50 else 0
    target += -4 if len(c["pawns"]) > beds(c) + 2 else 0
    p["mood"] += (max(0.0, min(100.0, target)) - p["mood"]) * 0.2
    # --- mental state
    if quiet or p["break_until"] > hour or doing in ("sleeping", "recovering"):
        return
    r = _rng(c, "mind", p["id"], hour)
    limit = 10 if "Iron will" in p["traits"] else 30 if "Volatile" in p["traits"] else 20
    if p["mood"] < limit and r.random() < 0.04:
        p["break_until"] = hour + r.randint(6, 12)
        _think(p, "catharsis", "Let it all out", 12, 36, hour + 12)
        _letter(c, "bad", f"{p['name']} is having a qi deviation",
                "Their mood sank too low and they have stopped working. It will pass in half a day. "
                "Food, a bed and some rest keep moods up.")
    elif p["mood"] > 78 and p["inspired_until"] <= hour and r.random() < 0.015:
        p["inspired_until"] = hour + 24
        _letter(c, "good", f"{p['name']} is inspired", "For the next day they work half again as fast.")


# ---------------------------------------------------------------------------
# storyteller
# ---------------------------------------------------------------------------
def _threat(c: dict, r: random.Random, kind: str) -> None:
    tell = STORYTELLERS[c["storyteller"]]
    strength = (wealth(c) / 22 + len(c["pawns"]) * 9 + _day(c) * 1.1) * r.uniform(0.7, 1.35) * tell["threat"]
    ratio = defense(c) / max(strength, 1.0)
    who = "A beast tide" if kind == "beasts" else "A rival sect's raid"
    fighters = [p for p in c["pawns"] if combat_power(c, p) > 0]
    for p in fighters:
        _xp(p, "combat", 12)
    c["last_threat_day"] = _day(c)
    if ratio >= 1.4:
        loot = r.randint(3, 8) if kind == "raid" else 0
        _add(c, "stones", loot)
        _letter(c, "good", f"{who} was driven off", "Your disciples and wards held without a scratch."
                + (f" The raiders dropped {loot} spirit stones." if loot else ""))
        return
    def wound(lo: int, hi: int, n: int) -> list[str]:
        hit = r.sample(fighters or c["pawns"], min(n, len(fighters or c["pawns"])))
        for p in hit:
            _hurt(p, r.randint(lo, hi))
        return [p["name"] for p in hit]
    if ratio >= 0.9:
        names = wound(15, 35, 2)
        text = f"The sect won, but {' and '.join(names)} took wounds. Pills and rest will mend them."
        kind_ = "info"
    elif ratio >= 0.55:
        names = wound(20, 50, max(2, len(c["pawns"]) // 2))
        for res in ("rice", "wood", "stone", "herbs"):
            c["res"][res] *= 0.9
        text = f"A costly win. {', '.join(names)} are wounded and a tenth of the stores were trampled."
        kind_ = "bad"
    else:
        names = wound(30, 70, len(c["pawns"]))
        for res in ("rice", "wood", "stone", "herbs", "stones"):
            c["res"][res] *= 0.65
        text = "The sect was overrun. A third of the stores are gone and nearly everyone is hurt. Train, and raise a Ward Formation."
        kind_ = "bad"
    dead = []
    for p in list(c["pawns"]):
        if p["health"] <= 0:
            if p.get("master") or not tell["deaths"]:
                p["health"] = 6.0
            else:
                dead.append(p["name"])
                c["pawns"].remove(p)
                c["graves"] += 1
    if dead:
        text += f" {' and '.join(dead)} did not survive."
        for p in c["pawns"]:
            _think(p, "death", "A fellow disciple died", -12, 72, c["hour"])
    for p in c["pawns"]:
        _think(p, "fought", "Fought for the sect" if ratio >= 0.9 else "The sect was beaten", 4 if ratio >= 0.9 else -8, 36, c["hour"])
    _letter(c, kind_, f"{who} struck", text)


def _daily_event(c: dict) -> None:
    tell = STORYTELLERS[c["storyteller"]]
    day = _day(c)
    r = _rng(c, "event", day)
    if c["pending"] or r.random() > tell["event"] * (1.3 if _lvl(c, "market") else 1.0):
        return
    c["last_event_day"] = day
    table = [("wanderer", 16 if len(c["pawns"]) < pawn_cap(c) else 0), ("merchant", 14 + 6 * _lvl(c, "market")),
             ("herbs", 10), ("meteor", 7), ("elder", 7), ("harvest", 8 if _season(c) != 3 else 0),
             ("sickness", 9), ("blight", 6 if _season(c) != 3 else 0), ("cold", 8 if _season(c) == 3 else 0)]
    if tell["threat"] > 0 and day >= 6 and day - c["last_threat_day"] >= tell["threat_gap"]:
        table += [("beasts", 16), ("raid", 12 if day >= 12 else 0)]
    kinds, weights = zip(*[(k, w) for k, w in table if w > 0])
    kind = r.choices(kinds, weights)[0]
    if kind == "wanderer":
        cand = _make_pawn(c, c["next_pawn"])
        c["next_pawn"] += 1
        best = max(SKILLS, key=lambda s: cand["skills"][s]["lv"])
        c["pending"] = {"kind": "wanderer", "title": "A wanderer at the gate", "cand": cand, "expires": c["hour"] + 24,
                        "text": f"{cand['name']}, {cand['age']}, asks to join. {cand['root']} spirit root; "
                                f"{' and '.join(cand['traits']).lower()}; best at {SKILL_NAMES[best].lower()} ({cand['skills'][best]['lv']}). "
                                "Another mouth, another pair of hands.",
                        "options": [{"id": "accept", "label": "Welcome them"}, {"id": "decline", "label": "Turn them away"}]}
    elif kind == "merchant":
        rate = 1.0 + 0.25 * _lvl(c, "market")
        opts = []
        if c["res"]["rice"] >= 40:
            opts.append({"id": "sell_rice", "label": f"Sell 25 rice for {int(6 * rate)} spirit stones"})
        if c["res"]["herbs"] >= 10:
            opts.append({"id": "sell_herbs", "label": f"Sell 8 herbs for {int(7 * rate)} spirit stones"})
        if c["res"]["stones"] >= 6:
            opts += [{"id": "buy_rice", "label": "Buy 30 rice for 6 spirit stones"}, {"id": "buy_wood", "label": "Buy 40 wood for 6 spirit stones"}]
        if c["res"]["stones"] >= 10:
            opts.append({"id": "buy_pills", "label": "Buy 2 pills for 10 spirit stones"})
        c["pending"] = {"kind": "merchant", "title": "A merchant caravan", "expires": c["hour"] + 24, "rate": rate,
                        "text": "Traders have stopped at the gate for the day.", "options": opts + [{"id": "decline", "label": "Send them on"}]}
    elif kind == "herbs":
        n = r.randint(8, 16)
        _add(c, "herbs", n)
        _letter(c, "good", "Spirit herbs in bloom", f"A slope of the mountain flowered overnight. Your disciples gathered {n} herbs.")
    elif kind == "meteor":
        n = r.randint(5, 12)
        _add(c, "stones", n)
        _letter(c, "good", "A star fell on the peak", f"Its core cracked open into {n} spirit stones.")
    elif kind == "elder":
        for p in c["pawns"]:
            _xp(p, r.choice(SKILLS), 25)
            _think(p, "elder", "Heard a wandering elder teach", 6, 36, c["hour"])
        _letter(c, "good", "A wandering elder stayed the night", "They taught until dawn. Everyone learned something.")
    elif kind == "harvest":
        n = r.randint(12, 24)
        _add(c, "rice", n)
        _letter(c, "good", "A bumper harvest", f"The terraces gave {n} more rice than expected.")
    elif kind == "sickness":
        p = r.choice(c["pawns"])
        p["sick_until"] = c["hour"] + r.randint(30, 60)
        _hurt(p, 15)
        _letter(c, "bad", f"{p['name']} has fallen ill", "They will rest for a day or two. A pill speeds it up.")
    elif kind == "blight":
        lost = c["res"]["rice"] * 0.25
        c["res"]["rice"] -= lost
        _letter(c, "bad", "Blight in the stores", f"{int(lost)} rice spoiled.")
    elif kind == "cold":
        burn = min(c["res"]["wood"], 6.0 * len(c["pawns"]))
        c["res"]["wood"] -= burn
        short = burn < 6.0 * len(c["pawns"])
        for p in c["pawns"]:
            if short and "Ascetic" not in p["traits"]:
                _think(p, "cold", "Shivered through a cold snap", -8, 48, c["hour"])
        _letter(c, "bad" if short else "info", "A cold snap", f"The sect burned {int(burn)} wood to keep warm."
                + (" It was not enough." if short else ""))
    else:
        _threat(c, r, kind)


def resolve(st: dict, option: str, now: float) -> dict:
    c = _c(st, now)
    ev = c["pending"]
    if not ev:
        return {"ok": False, "error": "Nothing is waiting for a decision."}
    if option not in {o["id"] for o in ev["options"]}:
        return {"ok": False, "error": "That is not one of the choices."}
    c["pending"] = None
    res = c["res"]
    rate = float(ev.get("rate", 1.0))
    if ev["kind"] == "wanderer" and option == "accept":
        if len(c["pawns"]) >= pawn_cap(c):
            c["pending"] = ev
            return {"ok": False, "error": "The sect is full. Raise the Main Hall to take in more, or turn them away."}
        p = ev["cand"]
        p["joined"] = c["hour"]
        c["pawns"].append(p)
        return {"ok": True, "event": _letter(c, "good", f"{p['name']} joined the sect", "Set their work priorities in Work.")}
    trades = {"sell_rice": ("rice", -25, int(6 * rate)), "sell_herbs": ("herbs", -8, int(7 * rate)),
              "buy_rice": ("rice", 30, -6), "buy_wood": ("wood", 40, -6), "buy_pills": ("pills", 2, -10)}
    if option in trades:
        what, qty, stones = trades[option]
        if res[what] + qty < 0 or res["stones"] + stones < 0:
            c["pending"] = ev
            return {"ok": False, "error": "You no longer have enough for that trade."}
        res[what] += qty
        res["stones"] += stones
        return {"ok": True, "event": _letter(c, "info", "A trade was struck", ev["options"][[o["id"] for o in ev["options"]].index(option)]["label"] + ".")}
    return {"ok": True}


# ---------------------------------------------------------------------------
# the clock
# ---------------------------------------------------------------------------
def _hour(c: dict, quiet: bool) -> None:
    c["hour"] += 1
    taken: dict = {}
    for p in list(c["pawns"]):
        _tick_pawn(c, p, taken, quiet)
    if c["hour"] % 24 == 6 and not quiet:
        _daily_event(c)
        if c["res"]["rice"] < len(c["pawns"]) * 2 and _day(c) % 2 == 0:
            _letter(c, "bad", "The rice is nearly gone", "Put more disciples on farming, or trade for rice. Nothing grows in winter.")
    if c["insight"] >= 1 and c["research"]["current"]:
        spend = c["insight"]
        c["insight"] = 0.0
        _research(c, spend)


def advance(st: dict, hours: int, now: float) -> dict:
    """Advance the sim while the player is watching (events on)."""
    c = _c(st, now)
    n = 0
    if not c["name"]:
        return {"ok": False, "hours": 0}
    for _ in range(max(0, min(int(hours), MAX_TICK))):
        if c["pending"] or c["seclusion"]:
            break                        # time waits for your answer, and behind sealed gates
        _hour(c, quiet=False)
        n += 1
    c["last_real"] = now
    return {"ok": True, "hours": n}


def catch_up(st: dict, now: float) -> int:
    """Quiet progress for time spent away. Returns the sim hours advanced."""
    c = _c(st, now)
    if not c["name"] or c["seclusion"] or c["pending"]:
        c["last_real"] = now             # sealed gates, or someone waiting for your answer: time waits
        return 0
    hours = int(min(max(0.0, now - c["last_real"]) / SECS_PER_HOUR_OFFLINE, MAX_OFFLINE_HOURS))
    if hours < 1:
        return 0
    for _ in range(hours):
        _hour(c, quiet=True)
    c["last_real"] = now
    if hours >= 6:
        _letter(c, "info", "While you were away", f"The sect carried on quietly for {hours} hours. No one came to harm.")
    return hours


# ---------------------------------------------------------------------------
# player orders
# ---------------------------------------------------------------------------
def set_priority(st: dict, pawn_id: str, job: str, level: int, now: float) -> dict:
    c = _c(st, now)
    p = next((x for x in c["pawns"] if x["id"] == pawn_id), None)
    if not p or job not in JOBS:
        return {"ok": False, "error": "Unknown disciple or job."}
    p["prio"][job] = int(min(max(int(level), 0), 4))
    return {"ok": True}


def queue_build(st: dict, room: str, now: float) -> dict:
    c = _c(st, now)
    if room not in ROOMS:
        return {"ok": False, "error": "Unknown room."}
    level = _lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
    if level >= ROOMS[room]["max"]:
        return {"ok": False, "error": "Already at its highest level."}
    if room != "main_hall" and level > _lvl(c, "main_hall"):
        return {"ok": False, "error": f"Raise the Main Hall to level {level} first."}
    if len(c["builds"]) >= 4:
        return {"ok": False, "error": "The builders already have four jobs queued."}
    cost = room_cost(c, room, level)
    short = [f"{int(v - c['res'][k])} more {RES_NAMES[k].lower()}" for k, v in cost.items() if c["res"][k] < v]
    if short:
        return {"ok": False, "error": "Needs " + " and ".join(short) + "."}
    for k, v in cost.items():
        c["res"][k] -= v
    c["builds"].append({"room": room, "need": build_hours(level), "done": 0.0, "cost": cost})
    return {"ok": True}


def cancel_build(st: dict, index: int, now: float) -> dict:
    c = _c(st, now)
    if not 0 <= int(index) < len(c["builds"]):
        return {"ok": False, "error": "No such job."}
    b = c["builds"].pop(int(index))
    for k, v in b.get("cost", {}).items():
        c["res"][k] = c["res"].get(k, 0.0) + float(v)     # materials come back, even past the storehouse limit
    return {"ok": True}


def set_research(st: dict, tech: str, now: float) -> dict:
    c = _c(st, now)
    if tech and (tech not in RESEARCH or tech in c["research"]["done"]):
        return {"ok": False, "error": "Unknown or finished research."}
    r = c["research"]
    if tech != r["current"]:
        bank = r.setdefault("banked", {})
        if r["current"]:
            bank[r["current"]] = r["progress"]          # switching topics keeps what was learned
        r["current"], r["progress"] = tech, float(bank.pop(tech, 0.0)) if tech else 0.0
    return {"ok": True}


def use_pill(st: dict, pawn_id: str, now: float) -> dict:
    c = _c(st, now)
    p = next((x for x in c["pawns"] if x["id"] == pawn_id), None)
    if not p:
        return {"ok": False, "error": "Unknown disciple."}
    if c["res"]["pills"] < 1:
        return {"ok": False, "error": "No pills in the stores. Brew some in the Alchemy Hall."}
    c["res"]["pills"] -= 1
    p["health"] = min(100.0, p["health"] + 45)
    p["sick_until"] = 0
    return {"ok": True}


def banish(st: dict, pawn_id: str, now: float) -> dict:
    c = _c(st, now)
    p = next((x for x in c["pawns"] if x["id"] == pawn_id), None)
    if not p or p.get("master"):
        return {"ok": False, "error": "The Sect Master cannot be sent away."}
    c["pawns"].remove(p)
    for o in c["pawns"]:
        _think(o, "banish", "A disciple was sent away", -4, 48, c["hour"])
    return {"ok": True, "event": _letter(c, "info", f"{p['name']} left the sect", "They bowed once at the gate and went down the mountain.")}


def set_storyteller(st: dict, who: str, now: float) -> dict:
    c = _c(st, now)
    if who not in STORYTELLERS:
        return {"ok": False, "error": "Unknown storyteller."}
    c["storyteller"] = who
    return {"ok": True}


def set_seclusion(st: dict, on: bool, now: float) -> dict:
    """Holiday mode: the study streak is frozen and the sect stands still."""
    c = _c(st, now)
    today = _today(st, now)
    if on and not c["seclusion"]:
        c["seclusion"], c["secluded_on"] = True, today
    elif not on and c["seclusion"]:
        c["seclusion"] = False
        c["last_real"] = now
        try:
            since = _date(c["secluded_on"]) if c["secluded_on"] else None
        except ValueError:
            since = None
        if c["last_study_day"] and since:
            away = max(0, (_date(today) - since).days)
            latest = _date(today) - _dt.timedelta(days=1)
            if _date(c["last_study_day"]) < latest:
                c["last_study_day"] = min(_date(c["last_study_day"]) + _dt.timedelta(days=away), latest).isoformat()
        c["secluded_on"] = ""
    return {"ok": True, "seclusion": c["seclusion"]}


# ---------------------------------------------------------------------------
# study hooks (called by the engine)
# ---------------------------------------------------------------------------
def _today(st: dict, now: float) -> str:
    off = int(st["settings"].get("tz_offset_min", 0)) * 60
    return _dt.datetime.fromtimestamp(now + off, _dt.timezone.utc).strftime("%Y-%m-%d")


def _date(day: str) -> _dt.date:
    return _dt.date.fromisoformat(day)


def _master(c: dict) -> dict | None:
    return next((p for p in c["pawns"] if p.get("master")), None)


def on_answer(st: dict, course: str, *, correct: bool, is_new: bool, practice: bool, typed: bool, now: float) -> dict:
    """A graded answer: qi for the Sect Master, insight for the sect's research."""
    c = _c(st, now)
    if practice:
        return {"qi": 0, "insight": 0, "events": []}
    # A day's study is worth a few days of the Master's meditation: the faster road, never the only one.
    qi = 1 if correct else 0
    qi += 1 if typed and correct else 0
    insight = 1 if correct else 0
    before = len(c["log"])
    m = _master(c)
    if m:
        _gain_qi(c, m, float(qi))
    c["insight"] += insight
    return {"qi": qi, "insight": insight, "events": [dict(e, text=f"{e['title']}. {e['text']}") for e in c["log"][before:]]}


def _mark_study_day(st: dict, c: dict, now: float) -> list[dict]:
    events = []
    if c["seclusion"]:
        set_seclusion(st, False, now)
        events.append({"kind": "info", "text": "You studied, so the gates are open again. Your streak was kept."})
    today = _today(st, now)
    if c["last_study_day"] and c["last_study_day"] >= today:
        return events
    missed = max(0, (_date(today) - _date(c["last_study_day"])).days - 1) if c["last_study_day"] else 0
    if missed and c["grace"] >= missed:
        c["grace"] -= missed
        c["streak"] += 1
        events.append({"kind": "info", "text": f"{missed} rest day{'s' if missed > 1 else ''} covered your absence. The streak holds."})
    elif missed:
        c["streak"] = 1
        events.append({"kind": "info", "text": "You returned to your studies. A new streak begins."})
    else:
        c["streak"] += 1
    c["best_streak"] = max(c["best_streak"], c["streak"])
    c["last_study_day"] = today
    if c["streak"] % 7 == 0 and c["grace"] < 2:
        c["grace"] += 1
    iso = _date(today).isocalendar()
    wid = f"{iso[0]}-W{iso[1]:02d}"
    if c["week"]["id"] != wid:
        c["week"] = {"id": wid, "days": []}
    if today not in c["week"]["days"]:
        c["week"]["days"].append(today)
    return events


def credit_rest_day(st: dict, now: float) -> list[dict]:
    c = _c(st, now)
    if c["seclusion"] or not c["last_study_day"] or c["last_study_day"] >= _today(st, now):
        return []
    return _mark_study_day(st, c, now)


def on_session(st: dict, *, answers: int, correct: int, counted: bool, due_left: int, now: float) -> dict:
    """A finished session: the Master lectures and the whole sect is lifted."""
    c = _c(st, now)
    events: list[dict] = []
    if counted:
        events += _mark_study_day(st, c, now)
        good = answers >= 8 and correct / max(answers, 1) >= 0.8
        for p in c["pawns"]:
            _think(p, "lecture", "The Master lectured brilliantly" if good else "The Master lectured", 10 if good else 6, 24, c["hour"])
        if c["pawns"]:
            events.append({"kind": "good", "text": "Your disciples gathered to hear what you learned. Their mood lifts for a day."})
    return {"stones": 0, "events": events, "streak": c["streak"]}


def on_trial(st: dict, course: str, *, passed: bool, pct: int, now: float) -> dict:
    c = _c(st, now)
    events: list[dict] = []
    if passed:
        for p in c["pawns"]:
            _gain_qi(c, p, step_need(p["step"]) * 0.15)
            _think(p, "trial", "The Master passed a trial", 8, 48, c["hour"])
        events.append({"kind": "good", "text": f"Trial passed with {pct}%. Every disciple feels a surge of qi."})
    else:
        events.append({"kind": "info", "text": f"Trial attempt: {pct}%. What you missed is back in your review queue."})
    return {"stones": 0, "events": events}


def ensure(st: dict, now: float, ctx: dict | None = None) -> list[dict]:
    hours = catch_up(st, now)
    return [{"kind": "info", "text": f"The sect carried on for {hours} hours while you were away."}] if hours >= 6 else []


# ---------------------------------------------------------------------------
# view (every number is cast here, so the UI can trust it)
# ---------------------------------------------------------------------------
def _f(v, nd: int = 0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(v):
        return 0
    return int(round(v)) if nd == 0 else round(v, nd)


def _pawn_view(c: dict, p: dict) -> dict:
    hour = c["hour"]
    need = step_need(int(p["step"]))
    return {
        "id": str(p["id"]), "name": str(p["name"]), "age": _f(p["age"]), "master": bool(p.get("master")),
        "root": str(p["root"]), "traits": [{"name": str(t), "text": TRAITS.get(t, "")} for t in p["traits"]],
        "skills": [{"id": s, "name": SKILL_NAMES[s], "lv": _f(p["skills"][s]["lv"]), "passion": _f(p["skills"][s]["passion"])} for s in SKILLS],
        "food": _f(p["food"]), "rest": _f(p["rest"]), "joy": _f(p["joy"]), "mood": _f(p["mood"]), "health": _f(p["health"]),
        "thoughts": [{"label": str(t["label"]), "v": _f(t["v"])} for t in p["thoughts"] if t["until"] > hour],
        "step": _f(p["step"]), "realm": REALMS[int(p["step"]) // 4], "stage": STAGES[int(p["step"]) % 4],
        "qi": _f(p["qi"]), "qi_need": _f(need), "qi_pct": _f(min(100.0, 100.0 * float(p["qi"]) / need)),
        "prio": {j: _f(p["prio"].get(j, 0)) for j in JOBS}, "doing": str(p["doing"]),
        "broken": p["break_until"] > hour, "inspired": p["inspired_until"] > hour, "sick": p["sick_until"] > hour,
        "power": _f(combat_power(c, p)),
    }


def view(st: dict, now: float) -> dict:
    c = _c(st, now)
    today = _today(st, now)
    day = _day(c)
    rooms = []
    for rid, r in ROOMS.items():
        level = _lvl(c, rid)
        queued = sum(1 for b in c["builds"] if b["room"] == rid)
        nxt = level + queued
        cost = room_cost(c, rid, nxt) if nxt < r["max"] else None
        locked = ""
        if cost and rid != "main_hall" and nxt > _lvl(c, "main_hall"):
            locked = f"Needs Main Hall level {nxt}."
        rooms.append({"id": rid, "name": r["name"], "effect": r["effect"], "level": level, "max": r["max"], "open": level > 0,
                      "queued": queued, "cost": {k: _f(v) for k, v in cost.items()} if cost else None, "locked": locked,
                      "affordable": bool(cost) and not locked and all(c["res"][k] >= v for k, v in cost.items())})
    last = c["last_study_day"]
    gap = (_date(today) - _date(last)).days if last else 0
    lost = bool(last) and not c["seclusion"] and gap > 1 and c["grace"] < gap - 1
    pending = c["pending"]
    cur = c["research"]["current"]
    m = _master(c)
    return {
        "name": str(c["name"]), "founded": bool(c["name"]), "master": str(m["name"]) if m else "",
        "hour": _f(c["hour"]), "day": day + 1, "hod": c["hour"] % 24, "season": SEASONS[_season(c)],
        "year": day // (DAYS_PER_SEASON * 4) + 1, "season_day": day % DAYS_PER_SEASON + 1,
        "storyteller": c["storyteller"],
        "storytellers": [{"id": k, "name": v["name"], "blurb": v["blurb"]} for k, v in STORYTELLERS.items()],
        "res": [{"id": k, "name": RES_NAMES[k], "n": _f(c["res"][k]),
                 "cap": _f(_cap(c)) if k in ("rice", "wood", "stone", "herbs") else None} for k in RES],
        "insight": _f(c["insight"]), "wealth": _f(wealth(c)), "defense": _f(defense(c)),
        "beds": beds(c), "pawn_cap": pawn_cap(c), "graves": _f(c["graves"]),
        "food_days": _f(c["res"]["rice"] / max(1, len(c["pawns"])), 1),
        "rooms": rooms,
        "builds": [{"room": b["room"], "name": ROOMS[b["room"]]["name"], "pct": _f(100.0 * b["done"] / b["need"])} for b in c["builds"]],
        "pawns": [_pawn_view(c, p) for p in c["pawns"]],
        "jobs": [{"id": j, "name": v[0], "skill": SKILL_NAMES[v[1]]} for j, v in JOBS.items()],
        "research": {"current": cur, "progress": _f(c["research"]["progress"]),
                     "items": [{"id": k, "name": v["name"], "cost": v["cost"], "effect": v["effect"], "done": k in c["research"]["done"]}
                               for k, v in RESEARCH.items()],
                     "has_library": _lvl(c, "library") > 0},
        "pending": ({"title": str(pending["title"]), "text": str(pending["text"]),
                     "options": [{"id": str(o["id"]), "label": str(o["label"])} for o in pending["options"]]} if pending else None),
        "log": [{"hour": _f(e["hour"]), "day": _f(e["hour"]) // 24 + 1, "kind": str(e["kind"]), "title": str(e["title"]), "text": str(e["text"])}
                for e in reversed(c["log"][-30:])],
        # study habit
        "streak": 0 if lost else _f(c["streak"]), "best_streak": _f(c["best_streak"]), "studied_today": last == today,
        "streak_at_risk": bool(last) and not c["seclusion"] and gap >= 1 and not lost and c["streak"] > 0,
        "grace": _f(c["grace"]), "seclusion": bool(c["seclusion"]),
        "week": {"days": len(c["week"]["days"]) if c["week"]["id"] else 0, "goal": WEEK_GOAL},
        "realm": REALMS[int(m["step"]) // 4] if m else REALMS[0], "stage": STAGES[int(m["step"]) % 4] if m else STAGES[0],
    }


def sanitize(raw, now: float) -> dict:
    """A colony from an untrusted blob. Strings are capped, non-finite numbers
    dropped, and the result is test-driven: anything that cannot run a quiet
    hour and render is discarded (study progress is kept; the sect restarts)."""
    if not isinstance(raw, dict) or "hour" not in raw:
        return {}

    def clean(v, depth=0):
        if depth > 8:
            return None
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, (int, float)):
            return v if math.isfinite(v) else 0
        if isinstance(v, str):
            return v[:300]
        if isinstance(v, list):
            return [clean(x, depth + 1) for x in v[:200]]
        if isinstance(v, dict):
            return {str(k)[:64]: clean(x, depth + 1) for k, x in list(v.items())[:200]}
        return None

    c = clean(raw)
    try:
        probe = {"colony": __import__("copy").deepcopy(c), "settings": {"tz_offset_min": 0}}
        pc = _c(probe, now)
        if not isinstance(pc["pawns"], list) or len(pc["pawns"]) > 60 or not all(isinstance(p, dict) for p in pc["pawns"]):
            return {}
        for _ in range(26):
            _hour(pc, quiet=True)
        view(probe, now)
    except Exception:
        return {}
    c.setdefault("last_real", now)
    c["last_real"] = min(float(c["last_real"]), now)
    return c
