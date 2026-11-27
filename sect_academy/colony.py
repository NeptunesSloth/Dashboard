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

import copy
import datetime as _dt
import math
import random
import re
from pathlib import Path

from . import lore

REALMS = ["Mortal", "Qi Condensation", "Foundation Establishment", "Core Formation",
          "Nascent Soul", "Soul Transformation", "Void Refinement", "Immortal Ascension"]
STAGES = ["Early", "Middle", "Late", "Peak"]
MAX_STEP = len(REALMS) * len(STAGES) - 1
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
DAYS_PER_SEASON = 12
STORYTELLERS = {
    "calm":     {"name": "Gentle Rain", "blurb": "Few dangers. Good for learning the ropes.", "event": 0.25, "threat_gap": 99999, "threat": 0.0, "deaths": False, "yield": 1.15},
    "balanced": {"name": "Turning Seasons", "blurb": "Trouble comes, with room to recover.", "event": 0.4, "threat_gap": 5, "threat": 1.0, "deaths": True, "yield": 0.85,
                 "quiet": 5},
    "harsh":    {"name": "Heaven's Trial", "blurb": "Frequent raids. Disciples can die.", "event": 0.5, "threat_gap": 3, "threat": 1.35, "deaths": True, "yield": 0.7,
                 "quiet": 4},
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

# Rooms. cost(level) = base * COST_CURVE**level, plus spirit stones from the fourth level (room_cost). Tuned by tests/balance.py.
ROOMS = {
    "main_hall":   {"name": "Main Hall", "wood": 15, "stone": 11, "max": 10,
                    "effect": "The heart of the sect. Each level opens rooms and room levels, and houses more disciples and the fame that draws wanderers."},
    "dormitory":   {"name": "Dormitory", "wood": 14, "stone": 5, "max": 8, "effect": "Three beds per level. Disciples without a bed sleep badly."},
    "fields":      {"name": "Rice Terraces", "wood": 9, "stone": 5, "max": 8, "effect": "Two farmers per level, and a better yield. Nothing grows in winter."},
    "storehouse":  {"name": "Storehouse", "wood": 14, "stone": 9, "max": 8, "effect": "Raises how much rice, wood, stone and herbs you can keep. Rice and herbs above half the store slowly spoil."},
    "library":     {"name": "Scripture Pavilion", "wood": 16, "stone": 9, "max": 8, "effect": "Lets disciples research. Faster per level."},
    "meditation":  {"name": "Meditation Chamber", "wood": 11, "stone": 11, "max": 8, "effect": "+15% qi from meditation per level."},
    "alchemy":     {"name": "Alchemy Hall", "wood": 11, "stone": 14, "max": 8, "effect": "Lets disciples brew pills from herbs. Pills heal and steady a breakthrough."},
    "training":    {"name": "Training Grounds", "wood": 14, "stone": 7, "max": 8, "effect": "Lets disciples train for combat. Faster per level."},
    "ward":        {"name": "Ward Formation", "wood": 7, "stone": 20, "max": 8, "effect": "Defends the sect on its own. Stronger per level."},
    "spirit_vein": {"name": "Spirit Vein", "wood": 9, "stone": 18, "max": 8, "effect": "Quarrying also yields spirit stones, and meditation gains +5% per level."},
    "market":      {"name": "Trade Post", "wood": 16, "stone": 7, "max": 3, "effect": "Merchants visit more often and pay better."},
}
# The Main Hall ladder (SECT_OVERHAUL_PLAN 3.2): the rooms each level opens, and the highest level any other room
# may reach while the Hall stands there (never more than one above the Hall). Builders come at BUILDER_HALLS.
HALL_LADDER = {
    1: {"rooms": ("dormitory", "fields", "storehouse", "ward"), "cap": 2},
    2: {"rooms": ("library", "training", "meditation"), "cap": 3},
    3: {"rooms": ("alchemy",), "cap": 3},
    4: {"rooms": ("spirit_vein",), "cap": 4, "more": ("Branch sects, with eight disciples and 100 spirit stones",)},
    5: {"rooms": ("market",), "cap": 5, "more": ("The first line of the Great Work “A Great Sect”",)},
    6: {"cap": 6},
    7: {"cap": 6},
    8: {"cap": 7},
    9: {"cap": 7},
    10: {"cap": 8, "more": ("The summit: the tallest hall in the valley",)},
}
HALL_ROOMS_NEEDED = 3              # to raise the Hall to n+1, this many other rooms must stand at level n or higher
COST_CURVE = 1.6                   # each level of a room costs this many times the one before
STONES_PER_LEVEL = 5               # spirit stones a level from the fourth on: 5 for level 4, 10 for level 5, ...


def room_opens_at(room: str) -> int:
    """The Main Hall level a room can first be built at."""
    return next((h for h, x in HALL_LADDER.items() if room in x.get("rooms", ())), 1)


def room_cap(c: dict) -> int:
    """The highest level other rooms may reach under the Hall as it stands."""
    return HALL_LADDER[max(1, min(10, _lvl(c, "main_hall")))]["cap"]


def hall_rooms_check(c: dict, target: int) -> list[tuple[str, int, bool]]:
    """The anti-rush checklist for raising the Hall to `target`: the other rooms at level target-1 or higher
    (best first), padded to HALL_ROOMS_NEEDED with the next best. [(room name, level, ok)]."""
    need = target - 1
    best = sorted(((_lvl(c, k), ROOMS[k]["name"]) for k in ROOMS if k != "main_hall" and _lvl(c, k)), key=lambda x: (-x[0], x[1]))
    rows = [(name, lv, lv >= need) for lv, name in best[:HALL_ROOMS_NEEDED]]
    while len(rows) < HALL_ROOMS_NEEDED:
        rows.append(("", 0, False))
    return rows


RESEARCH = {
    "irrigation": {"name": "Terraced irrigation", "cost": 150, "effect": "+25% rice from farming."},
    "masonry":    {"name": "Stone masonry", "cost": 180, "effect": "Rooms cost 20% less stone."},
    "granary":    {"name": "Sealed granaries", "cost": 220, "effect": "Storehouse holds 50% more, and stores spoil half as fast."},
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
# Upkeep and the slow pressures of a growing sect (all shown in view()["upkeep"]).
HUNGER = 2.2                       # food a disciple burns an hour; a bowl of rice is 38
WINTER_HUNGER = 1.25               # cold bodies burn a quarter more
WINTER_WOOD = 2.0                  # firewood per disciple per winter night
REPAIR_FREE = 3                    # room levels a sect keeps up without thinking about it
REPAIR = {"wood": 0.35, "stone": 0.2}   # per room level beyond those, per day
SPOIL_FROM = 0.5                   # rice and herbs above this share of the store start to spoil
SPOIL = 0.15                       # share of that surplus lost per day
FARM_YIELD = 0.42                  # rice per farmer-hour at skill 7 on one terrace, before the storyteller
GATHER = {"wood": 1.5, "stone": 1.05, "herbs": 0.35}   # wood, stone and herbs per worker-hour at skill 7
WORK_QI = 0.12                     # an hour of work gathers this share of an hour of meditation
STALL_DAYS = 5                     # days without meditation before the sect says so
LOW_STORE_DAYS = 4.0               # a store under this many days of use is genuinely low: its chore wins a tie
STORE_OF = {"farm": "rice", "wood": "wood", "mine": "stone", "forage": "herbs"}
# Builders (SECT_OVERHAUL_PLAN 3.1): each slot runs one job on its own clock, helped or not. Sim hours.
BUILDERS = 2                       # builder slots a sect starts with
BUILDER_HALLS = (3, 6, 9)          # one more builder at each of these Main Hall levels
HELPER_X = 0.25                    # each disciple on Build adds this share of a builder's speed, times their Construction
HELPERS_PER_SITE = 2
ROOM_HOURS = {1: 3, 2: 6, 3: 10, 4: 14, 5: 18, 6: 24, 7: 30, 8: 36}       # sim hours to reach a room level (tuned by tests/balance.py)
HALL_HOURS = {2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 7: 28, 8: 32, 9: 34, 10: 36}   # and a Main Hall level
BLUEPRINT_CUT = 0.25               # a Master's Blueprint takes this share off the time left on one running job
BLUEPRINT_BANK = 3                 # blueprints kept at most (one is drawn per real day of counted study)
MASTER_BUILDER_HOURS = 24          # meeting the weekly study goal lends the Master as a builder this long


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------
def _rng(c: dict, *salt) -> random.Random:
    return random.Random(f"{c['seed']}:{':'.join(str(s) for s in salt)}")


def default_meditate(prio: dict) -> int:
    """A newcomer's Meditate: level with their main chore (building comes and goes with the queue, so it is not it), so they
    sit half their working hours from the first day instead of never (MED_SHARE); 2 when they have no chore."""
    return min((int(v) for j, v in prio.items() if j not in ("meditate", "build") and v), default=2)


def _make_pawn(c: dict, n: int, master_name: str = "", lucky: bool = False) -> dict:
    r = _rng(c, "pawn", n)
    total = sum(w for _, _, w in ROOTS)
    roll = max(r.uniform(0, total), r.uniform(0, total)) if lucky else r.uniform(0, total)     # fame draws better talent
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
        **copy.deepcopy(PAWN_EXTRA),             # fresh lists: fates and meridians are never shared
    }
    if master_name:
        pawn["prio"].update(meditate=2, research=2, farm=3, build=2)
        pawn["origin"] = "Founder of the sect."
        pawn["element"] = r.choice(lore.ELEMENTS)
    else:
        pawn["prio"]["meditate"] = default_meditate(pawn["prio"])
        pawn["element"] = r.choice(lore.ELEMENTS)
        text, skill, bonus = r.choice(lore.ORIGINS)
        pawn["origin"] = text
        pawn["skills"][skill]["lv"] = min(20, pawn["skills"][skill]["lv"] + bonus)
    return pawn


PAWN_EXTRA = {"bt_tries": 0, "away_until": 0, "away_kind": "", "resolve_until": 0, "title": "", "hidden": False, "rank": 0, "origin": "", "element": "", "direct": False, "sat_at": -1, "work": "", "post": ""}


def new_colony(now: float) -> dict:
    c = {
        "name": "", "seed": random.randrange(1 << 30), "hour": 6, "storyteller": "balanced", "paused": False,
        "res": {"rice": 36.0, "wood": 45.0, "stone": 25.0, "herbs": 4.0, "pills": 1.0, "stones": 0.0},
        "rooms": {"main_hall": 1, "dormitory": 1, "fields": 1},
        "builds": [],                # [{room, need (sim hours of a builder), done, cost, at, crew}]: the first builders(c) are worked
        "blueprints": {"n": 0, "day": ""},   # Master's Blueprints in hand, and the real day the last was drawn
        "master_builds_until": 0,    # the sect hour the Master stops lending a hand as a builder
        HELD_SECS: 0.0,
        "tray_seen": {}, "inspected": {},   # per room: the hour the Master last looked at its tray, the day it cheered the crew
        "rushes": [], "room_idle": {},      # rushes in the last two days ({k: room or "build", h}); rooms idle after an incident
        "pawns": [], "next_pawn": 0, "graves": 0,
        "research": {"done": [], "current": "", "progress": 0.0, "banked": {}},
        # the wider world
        "fame": 0.0, "sects": [], "manuals": ["breathing"], "treasures": [], "beast": None, "later": [], "adapt": 1.0,
        "bonds": {}, "annals": [], "artifacts": [], "next_art": 0, "guide": {"i": 0, "skip": False}, "quest": None, "festival": "",
        "flags": {}, "tournament_year": 0, "recruit_year": 0, "scenes": [], "next_scene": 0,
        "craft": 0.0, "insight": 0.0, "pending": None, "last_threat_day": 0, "last_event_day": 0,
        "blight": None,              # {until (hour), x (yield multiplier)}: a failed harvest, in the farm ledger
        "tally": {"stolen": 0.0, "plague_dead": 0},   # what the mid-game has cost, for the chronicle and the balance runs
        "log": [], "last_real": now, "hint": 0,
        "made": {},                  # {hour: {"res|job|pawn" or "h|job|pawn": amount}}: what work did, the last day
        # study habit (kept here so one object holds the whole game)
        "streak": 0, "best_streak": 0, "last_study_day": "", "grace": 2, "seclusion": False, "secluded_on": "",
        "week": {"id": "", "days": []},
    }
    c.update(dao.defaults())
    return c


def setup(st: dict, name: str, master: str, now: float) -> dict:
    c = _c(st, now)
    first = not c["name"]
    c["name"] = (name or "").strip()[:40] or "Nameless Sect"
    master = (master or "").strip()[:30] or "Sect Master"
    if first:
        c["pawns"] = [_make_pawn(c, 0, master)] + [_make_pawn(c, i) for i in (1, 2)]
        c["next_pawn"] = 3
        _make_world(c)
        _annal(c, f"{master} founded the {c['name']} with two disciples.")
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
        for pw in c["pawns"]:
            for k, v in PAWN_EXTRA.items():
                pw.setdefault(k, copy.deepcopy(v))
            if pw["element"] not in lore.ELEMENTS:
                pw["element"] = _rng(c, "elem", pw.get("id")).choice(lore.ELEMENTS)
        if c["name"] and not c["sects"]:
            _make_world(c)
    return c


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
_DOUBLE_STOP = re.compile(r"(?<![.…])\.\.(?![.…])")


def tidy(text: str) -> str:
    """The punctuation slips templates make when a piece already ends in a full stop: 'everyone.. A', '  ', ' .'."""
    text = _DOUBLE_STOP.sub(".", str(text))
    text = re.sub(r" {2,}", " ", text)
    return re.sub(r" +([.,;:!?])", r"\1", text)


def _and(names) -> str:
    """'A', 'A and B', 'A, B and C'."""
    n = [str(x) for x in names]
    return " and ".join(n) if len(n) < 3 else ", ".join(n[:-1]) + " and " + n[-1]


def _be(n, one: str = "is", many: str = "are") -> str:
    """The verb that agrees with a list of names (or a count): _be(['A']) 'is', _be(['A', 'B']) 'are'."""
    k = n if isinstance(n, int) else len(n)
    return one if k == 1 else many


def _n(n, word: str, plural: str = "") -> str:
    """'1 pill', '3 pills', '1 day', '2 days'."""
    k = int(n)
    return f"{k} {word if k == 1 else plural or word + 's'}"


def _letter(c: dict, kind: str, title: str, text: str) -> dict:
    ev = {"hour": c["hour"], "kind": kind, "title": tidy(title), "text": tidy(text)}
    c["log"] = (c["log"] + [ev])[-80:]
    return ev


# ---------------------------------------------------------------------------
# result scenes: a big outcome is shown as a framed card, not just a log line
# ---------------------------------------------------------------------------
SCENE_KINDS = ("raid", "tournament", "festival", "funeral", "tribulation", "breakthrough", "realm", "sickness", "blight", "infiltrator", "theft", "incident",
               "festival_spring", "festival_moon", "festival_ghost", "festival_winter")
SCENE_CAP = 5                       # unseen scenes kept; older ones drop off (the chronicle still has them)
SCENE_ART = frozenset(k for k in SCENE_KINDS if (Path(__file__).parent / "static" / "art" / f"scene_{k}.webp").is_file())
# Disciple faces: the six originals first (so existing disciples keep their face
# until more are added), then any extra static/art/p_<name>.webp, sorted.
_FACE_BASE = ("disciple", "analyst", "architect", "engineer", "researcher", "trader")
_FACE_DIR = Path(__file__).parent / "static" / "art"
FACES = tuple(n for n in _FACE_BASE if (_FACE_DIR / f"p_{n}.webp").is_file()) + tuple(sorted(
    f.stem[2:] for f in _FACE_DIR.glob("p_*.webp")
    if f.stem[2:] not in _FACE_BASE and f.stem[2:] not in ("leader", "elder") and re.fullmatch(r"[a-z0-9_]{1,24}", f.stem[2:])))


def _snap(c: dict) -> dict:
    """What the sect looks like before an outcome, so the scene can say what changed."""
    return {"res": dict(c["res"]), "fame": float(c["fame"]), "rare": float(c.get("rare", 0.0)), "next": int(c.get("next_scene", 0)),
            "pawns": {p["id"]: (float(p["health"]), float(p["qi"]), int(p["step"])) for p in c["pawns"]}}


def _scene(c: dict, kind: str, ok: bool, title: str, text: str = "", *, verdict: str = "", party=(), lines=(),
           snap: dict | None = None, extra=(), first: int | None = None) -> dict:
    """Queue a result scene. Reads the sect only; it never changes the sim.
    party: pawn dicts (alive or just dead); lines: (who, text, ok|None); extra: (label, value, good, signed).
    first: put this scene before any scene queued since that id (a battle shows before the funerals it caused)."""
    out_lines = [{"who": str(w), "text": tidy(t), "ok": o if o is None else bool(o)} for w, t, o in lines]
    title, text = tidy(title), tidy(text)
    changes = []
    if snap:
        for k in RES:
            d = c["res"][k] - snap["res"].get(k, 0.0)
            if abs(d) >= 0.5:
                changes.append((RES_NAMES[k], d, d > 0, True))
        d = float(c.get("rare", 0.0)) - snap["rare"]
        if abs(d) >= 0.5:
            changes.append(("Rare herbs", d, d > 0, True))
        d = float(c["fame"]) - snap["fame"]
        if abs(d) >= 0.5:
            changes.append(("Fame", d, d > 0, True))
        alive = {p["id"]: p for p in c["pawns"]}
        wounded = sum(1 for pid, (hp, _, _) in snap["pawns"].items() if pid in alive and alive[pid]["health"] <= hp - 5)
        dead = sum(1 for pid in snap["pawns"] if pid not in alive)
        qi = 0.0
        for p in party:
            before = snap["pawns"].get(p["id"])
            if not before:
                continue
            q = alive.get(p["id"])
            if not q:
                out_lines.append({"who": str(p["name"]), "text": "died", "ok": False})
                continue
            if q["step"] != before[2]:
                out_lines.append({"who": str(q["name"]), "text": f"now {realm_label(q['step'])}", "ok": q["step"] > before[2]})
            else:
                qi += q["qi"] - before[1]
            if q["health"] <= before[0] - 1:
                out_lines.append({"who": str(q["name"]), "text": f"lost {int(round(before[0] - q['health']))} health", "ok": False})
        if abs(qi) >= 1:
            changes.append(("Qi", qi, qi > 0, True))
        if wounded:
            changes.append(("Wounded", wounded, False, False))
        if dead:
            changes.append(("Dead", dead, False, False))
    changes += list(extra)
    sc = {"id": int(c.get("next_scene", 0)), "hour": int(c["hour"]), "kind": kind if kind in SCENE_KINDS else "realm", "ok": bool(ok),
          "title": str(title), "text": str(text), "verdict": str(verdict or ("Success" if ok else "Failure")),
          "party": [{"id": str(p["id"]), "name": str(p["name"]), "root": str(p["root"]), "master": bool(p.get("master"))} for p in party][:6],
          "lines": out_lines[:10],
          "changes": [{"label": str(lab), "v": round(float(v)), "good": bool(g), "signed": bool(s)} for lab, v, g, s in changes][:10]}
    c["next_scene"] = sc["id"] + 1
    q = list(c.get("scenes") or [])
    at = next((i for i, x in enumerate(q) if first is not None and x["id"] >= first), len(q))
    q.insert(at, sc)
    c["scenes"] = q[-SCENE_CAP:]
    return sc


def scene_seen(st: dict, scene_id: int, now: float) -> dict:
    """The player dismissed a scene: drop it from the queue."""
    c = _c(st, now)
    n = len(c["scenes"])
    c["scenes"] = [x for x in c["scenes"] if x["id"] != int(scene_id)]
    return {"ok": True} if len(c["scenes"]) < n else {"ok": False, "error": "No such scene."}


def _scene_view(x: dict) -> dict:
    return {"id": _f(x["id"]), "day": _f(x["hour"]) // 24 + 1, "when": calendar_label(_f(x["hour"]) // 24), "kind": str(x["kind"]), "ok": bool(x["ok"]), "painted": x["kind"] in SCENE_ART,
            "title": str(x["title"]), "text": str(x["text"]), "verdict": str(x["verdict"]),
            "party": [{"id": str(p["id"]), "name": str(p["name"]), "root": str(p["root"]), "master": bool(p["master"])} for p in x["party"]],
            "lines": [{"who": str(ln["who"]), "text": str(ln["text"]), "ok": ln["ok"] if ln["ok"] is None else bool(ln["ok"])} for ln in x["lines"]],
            "changes": [{"label": str(ch["label"]), "v": _f(ch["v"]), "good": bool(ch["good"]), "signed": bool(ch["signed"])} for ch in x["changes"]]}


def _repair_scenes(c: dict, num) -> None:
    out = []
    raw = c.get("scenes") if isinstance(c.get("scenes"), list) else []
    roots = {name for name, _, _ in ROOTS} | {"Heaven-Defying", "Crippled"}
    for x in raw:
        if not (isinstance(x, dict) and x.get("kind") in SCENE_KINDS and isinstance(x.get("title"), str)):
            continue
        party = [{"id": str(p.get("id") or ""), "name": str(p.get("name") or ""), "root": p.get("root") if p.get("root") in roots else "Common",
                  "master": bool(p.get("master"))} for p in (x.get("party") if isinstance(x.get("party"), list) else []) if isinstance(p, dict)][:6]
        lines = [{"who": str(ln.get("who") or ""), "text": str(ln.get("text") or ""),
                  "ok": ln.get("ok") if ln.get("ok") is None else bool(ln.get("ok"))}
                 for ln in (x.get("lines") if isinstance(x.get("lines"), list) else []) if isinstance(ln, dict)][:10]
        changes = [{"label": str(ch.get("label") or ""), "v": int(num(ch.get("v"), -1e7, 1e7)), "good": bool(ch.get("good")), "signed": bool(ch.get("signed"))}
                   for ch in (x.get("changes") if isinstance(x.get("changes"), list) else []) if isinstance(ch, dict)][:10]
        out.append({"id": int(num(x.get("id"), 0, 1e9)), "hour": int(num(x.get("hour"), 0, 1e9)), "kind": x["kind"], "ok": bool(x.get("ok")),
                    "title": x["title"], "text": str(x.get("text") or ""), "verdict": str(x.get("verdict") or ""),
                    "party": party, "lines": lines, "changes": changes})
    seen_ids: set = set()
    c["scenes"] = [x for x in out if not (x["id"] in seen_ids or seen_ids.add(x["id"]))][-SCENE_CAP:]
    c["next_scene"] = max([int(num(c.get("next_scene"), 0, 1e9))] + [x["id"] + 1 for x in c["scenes"]])


def _day(c: dict) -> int:
    return c["hour"] // 24


def calendar_label(day0: int) -> str:
    """The one way a date is written: the header, the chronicle, the annals and the graves all use it."""
    day0 = max(0, int(day0))
    return f"{SEASONS[(day0 // DAYS_PER_SEASON) % 4]} {day0 % DAYS_PER_SEASON + 1}, year {day0 // (DAYS_PER_SEASON * 4) + 1}"


def _season(c: dict) -> int:
    return (_day(c) // DAYS_PER_SEASON) % 4


def _lvl(c: dict, room: str) -> int:
    return int(c["rooms"].get(room, 0))


def _has(c: dict, tech: str) -> bool:
    return tech in c["research"]["done"]


def _cap(c: dict) -> float:
    return (150 + 120 * _lvl(c, "storehouse")) * (1.5 if _has(c, "granary") else 1.0) * (1.3 if "pouch" in c["treasures"] else 1.0)


def rank_of(p: dict) -> int:
    """Outer, Inner, Core, Elder: a disciple's standing follows their realm."""
    realm = int(p["step"]) // 4
    return 0 if realm <= 1 else 1 if realm == 2 else 2 if realm == 3 else 3


def suit(p: dict, mid: str) -> tuple[str, float]:
    """How well a manual's element sits with a disciple's spirit root: (word, multiplier on its bonus)."""
    me, it = p.get("element"), lore.MANUAL_ELEMENT.get(mid)
    if not it or not me:
        return "", 1.0
    if me == it:
        return "well suited", 1.5
    if lore.OVERCOMES[me] == it or lore.OVERCOMES[it] == me:
        return "ill suited", 0.7
    return "", 1.0


def artifact_of(c: dict, p: dict) -> dict | None:
    return next((a for a in c["artifacts"] if a["owner"] == p["id"]), None)


def _art(c: dict, p: dict, kind: str) -> float:
    a = artifact_of(c, p)
    return float(lore.ARTIFACT_KINDS[kind][1][a["q"]]) if a and a["kind"] == kind else 0.0


def season_tilt(c: dict, p: dict) -> tuple[str, float]:
    """The season favours one element and presses on the one it overcomes."""
    fav = lore.SEASON_ELEMENT[_season(c)]
    if p["element"] == fav:
        return f"{SEASONS[_season(c)]} favours {fav} roots", 1.12
    if p["element"] == lore.OVERCOMES[fav]:
        return f"{SEASONS[_season(c)]} presses on {p['element']} roots", 0.92
    if p["element"] == "earth":
        return "Earth roots are steady in every season", 1.03
    return "", 1.0


def qi_rate(c: dict, p: dict) -> list[tuple[str, float]]:
    """Everything that multiplies a disciple's qi from meditation, as a ledger."""
    rows = [(f"{p['root']} spirit root", float(p["root_mult"]))]
    b, mid = _manual(c, p, "qi")
    if mid:
        word = suit(p, mid)[0]
        rows.append((lore.MANUALS[mid]["name"] + (f" ({word})" if word else ""), 1 + b))
    label, tilt = season_tilt(c, p)
    if label:
        rows.append((label, tilt))
    if _lvl(c, "meditation"):
        rows.append(("Meditation Chamber", 1 + 0.15 * _lvl(c, "meditation")))
    if _lvl(c, "spirit_vein"):
        rows.append(("Spirit Vein", 1 + 0.05 * _lvl(c, "spirit_vein")))
    if _has(c, "qi_array"):
        rows.append(("Qi-gathering array", 1.2))
    if "spirit_spring" in c["treasures"]:
        rows.append((lore.TREASURES["spirit_spring"]["name"], 1.1))
    if _art(c, p, "talisman"):
        rows.append((artifact_of(c, p)["name"], 1 + _art(c, p, "talisman")))
    if p.get("direct"):
        rows.append(("Direct disciple: the Master's own teaching", 1.25))
    if p["resolve_until"] > c["hour"]:
        rows.append(("Burning resolve", 1.5))
    return rows + dao.qi_rows(c, p)


def _manual(c: dict, p: dict, kind: str) -> tuple[float, str]:
    """The best manual of a kind this disciple's rank lets them study: (bonus, id)."""
    cap = 3 if p.get("master") else rank_of(p)
    best = (0.0, "")
    for mid in c["manuals"]:
        m = lore.MANUALS.get(mid)
        if not m or m["kind"] != kind or (m["grade"] > cap and not m.get("demonic")):
            continue
        b = (lore.MANUAL_BONUS[kind][m["grade"]] + (0.15 if m.get("demonic") else 0.0)) * suit(p, mid)[1]
        if b > best[0]:
            best = (b, mid)
    return best


def _add(c: dict, res: str, amount: float) -> None:
    v = c["res"].get(res, 0.0) + amount
    c["res"][res] = max(0.0, min(v, _cap(c)) if res in ("rice", "wood", "stone", "herbs") else v)


def _think(p: dict, key: str, label: str, value: int, hours: int, hour: int) -> None:
    p["thoughts"] = [t for t in p["thoughts"] if t["k"] != key] + [{"k": key, "label": label, "v": value, "until": hour + hours}]


def step_need(step: int) -> float:
    """Qi to fill a stage. The Mortal stages are body tempering, quicker than anything after them (700 in all, not 940),
    so a disciple who meditates half their working hours can stand at Qi Condensation's door in the second or third month."""
    return 70.0 + 70.0 * step if step < 4 else 100.0 + 90.0 * step


def realm_label(step: int) -> str:
    return f"{REALMS[step // 4]} · {STAGES[step % 4]}"


def room_cost(c: dict, room: str, level: int) -> dict:
    r = ROOMS[room]
    k = COST_CURVE ** level
    cost = {"wood": int(round(r["wood"] * k / 5.0)) * 5,
            "stone": int(round(r["stone"] * k * (0.8 if _has(c, "masonry") else 1.0) / 5.0)) * 5}
    if level >= 3:
        cost["stones"] = STONES_PER_LEVEL * (level - 2)
    return cost


def build_hours(room: str, level: int) -> float:
    """Sim hours one builder takes to bring `room` to `level` (helpers make it quicker)."""
    table = HALL_HOURS if room == "main_hall" else ROOM_HOURS
    return float(table.get(int(level), max(table.values())))


def hall_for_level(room_level: int) -> int:
    """The lowest Main Hall level that lets other rooms reach `room_level`."""
    return next((h for h, x in HALL_LADDER.items() if x["cap"] >= room_level), 10)


def build_block_short(c: dict, room: str, level: int) -> str:
    """build_block in a few words, for a tile."""
    if room == "main_hall":
        short = sum(1 for x in hall_rooms_check(c, level + 1) if not x[2])
        return f"Needs {_n(short, 'more room', 'more rooms')} at level {level}" if short else ""
    if level == 0 and _lvl(c, "main_hall") < room_opens_at(room):
        return f"Opens at Main Hall {room_opens_at(room)}"
    return f"Waits on Main Hall {hall_for_level(level + 1)}" if level + 1 > room_cap(c) else ""


def build_block(c: dict, room: str, level: int) -> str:
    """Why `room` cannot go from `level` to level+1 under the Main Hall ladder ("" when it can). Builders and
    materials are checked by the caller."""
    hall = _lvl(c, "main_hall")
    if room == "main_hall":
        short = [x for x in hall_rooms_check(c, level + 1) if not x[2]]
        if short:
            return (f"Raising the Main Hall to level {level + 1} needs {HALL_ROOMS_NEEDED} other rooms at level {level} or higher "
                    f"({_n(len(short), 'more room', 'more rooms')}).")
        return ""
    opens = room_opens_at(room)
    if level == 0 and hall < opens:
        return f"Opens at Main Hall level {opens}."
    if level + 1 > room_cap(c):
        return f"Raise the Main Hall to level {hall_for_level(level + 1)} first (rooms up to level {room_cap(c)} for now)."
    return ""


def builder_rows(c: dict) -> list[tuple[str, int]]:
    """Where the sect's builder slots come from (a ledger: it adds up to builders(c))."""
    rows = [("Builders every sect has", BUILDERS)]
    hall = _lvl(c, "main_hall")
    rows += [(f"Main Hall level {h}", 1) for h in BUILDER_HALLS if hall >= h]
    left = int(c.get("master_builds_until", 0)) - c["hour"]
    if left > 0:
        rows.append((f"The Master, lent by a week of study ({_n(left, 'hour')} left)", 1))
    return rows


def builders(c: dict) -> int:
    return sum(n for _, n in builder_rows(c))


def _running(c: dict) -> list[dict]:
    """The jobs a builder is on: the first builders(c) of the list (the rest wait for a builder to come free)."""
    return c["builds"][:builders(c)]


def build_rate_rows(c: dict, b: dict) -> list[tuple[str, float]]:
    """A job's speed last hour, in builder-hours an hour: the builder, then each helper."""
    return [("The builder", 1.0)] + [(f"{name} helping (Construction {lv})", float(x)) for name, lv, x in b.get("crew", [])]


def build_left(c: dict, b: dict) -> float:
    """Sim hours left on a job at last hour's speed."""
    rate = sum(x for _, x in build_rate_rows(c, b)) if b in _running(c) else 1.0
    return max(0.0, b["need"] - b["done"]) / max(rate, 1.0)


def _finish_build(c: dict, b: dict) -> None:
    c["builds"].remove(b)
    c["rooms"][b["room"]] = _lvl(c, b["room"]) + 1
    lv = c["rooms"][b["room"]]
    if b["room"] == "main_hall":
        _fame(c, 4)                       # the valley sees the sect's hall rise
    name = ROOMS[b["room"]]["name"]
    crew = sorted({x[0] for x in b.get("crew_all", [])})
    _letter(c, "good", f"{name} {'built' if lv == 1 else f'raised to level {lv}'}",
            "The builder set the last stone" + (f", with {_and(crew)} helping." if crew else "."))
    if isinstance(c.get("built_away"), list):
        c["built_away"].append(f"{name} {'built' if lv == 1 else f'to level {lv}'}")


def _tick_builds(c: dict, helped: bool = True) -> None:
    """One sim hour for every builder: each running job moves by one hour, plus what its helpers added this hour."""
    for b in list(_running(c)):
        boost = b.pop("boost", 0.0) if helped else 0.0
        b["crew"] = b.pop("crew_now", []) if helped else []
        if b["crew"]:
            b["crew_all"] = (b.get("crew_all", []) + [[x[0]] for x in b["crew"]])[-12:]
        b["done"] += 1.0 + boost
        if b["done"] >= b["need"] - 1e-9:
            _finish_build(c, b)
    for b in c["builds"][builders(c):]:
        b.pop("boost", None), b.pop("crew_now", None)
        b["crew"] = []


HELD_SECS = "held_secs"            # real seconds banked for the builders while an event waits for your answer


def _builders_wait(c: dict, now: float) -> int:
    """While an event waits for your answer, only the builders keep working, at the away rate (decided by the owner:
    building can only help). Returns the builder hours run."""
    if not c["pending"] or c["seclusion"] or not c["builds"]:
        c[HELD_SECS] = 0.0
        return 0
    c[HELD_SECS] = min(float(c.get(HELD_SECS, 0.0)) + max(0.0, now - float(c["last_real"])), MAX_OFFLINE_HOURS * SECS_PER_HOUR_OFFLINE)
    n = 0
    while c[HELD_SECS] >= SECS_PER_HOUR_OFFLINE and c["builds"]:
        c[HELD_SECS] -= SECS_PER_HOUR_OFFLINE
        _tick_builds(c, helped=False)
        n += 1
    return n


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
    s["xp"] += amount * (0.4, 1.0, 1.6)[s["passion"]] * (1.5 if "Quick learner" in p["traits"] else 1.0) * float(p.get("xp_x", 1.0))
    while s["lv"] < 20 and s["xp"] >= 20 * (s["lv"] + 1):
        s["xp"] -= 20 * (s["lv"] + 1)
        s["lv"] += 1


def hurt_mult(p: dict, c: dict | None = None) -> float:
    """How much of a blow lands: traits, and (given the sect) body manuals, armour and fates."""
    m = 0.6 if "Tough" in p["traits"] else 1.4 if "Frail" in p["traits"] else 1.0
    if c is not None:
        m *= (1.0 - _manual(c, p, "body")[0]) * (1.0 - _art(c, p, "armour")) * dao.hurt_x(c, p)
    return m


def _hurt(p: dict, amount: float, c: dict | None = None) -> None:
    p["health"] = max(0.0, p["health"] - amount * hurt_mult(p, c))


def combat_power(c: dict, p: dict) -> float:
    if p["health"] < 25 or p["break_until"] > c["hour"] or p["away_until"] > c["hour"]:
        return 0.0
    return (10 + 4 * p["skills"]["combat"]["lv"]) * (1 + 0.07 * p["step"]) * (p["health"] / 100.0) \
        * (1.25 if _has(c, "sword_forms") else 1.0) * (1 + _manual(c, p, "sword")[0]) * (1 + _art(c, p, "sword")) \
        * (1.15 if "spirit_sword" in c["treasures"] else 1.0) * dao.combat_x(c, p)


def ward_power(c: dict) -> float:
    return 18 * _lvl(c, "ward") * (1.5 if _has(c, "ward_ii") else 1.0) * (1.4 if "array_flag" in c["treasures"] else 1.0)


def beast_power(c: dict) -> float:
    b = c["beast"]
    return min(70.0, 12.0 + (c["hour"] - b["born"]) / 24.0 * 1.2) if b else 0.0


def defense(c: dict) -> float:
    return sum(combat_power(c, p) for p in c["pawns"]) + ward_power(c) + beast_power(c) + dao.defense_extra(c)


# ---------------------------------------------------------------------------
# one hour of one disciple
# ---------------------------------------------------------------------------
def _idle_room(c: dict, room: str) -> bool:
    return int(c.get("room_idle", {}).get(room, 0)) > c["hour"]


def _job_open(c: dict, job: str, taken: dict) -> bool:
    if job in ("wood", "mine", "forage") and _idle_room(c, "storehouse"):
        return False
    if job == "farm":
        return _lvl(c, "fields") > 0 and _season(c) != 3 and not _idle_room(c, "fields") and taken.get("farm", 0) < 2 * _lvl(c, "fields")
    if job == "build":
        return taken.get("build", 0) < HELPERS_PER_SITE * len(_running(c))
    if job == "craft":
        return _lvl(c, "alchemy") > 0 and not _idle_room(c, "alchemy") and c["res"]["herbs"] >= (2 if _has(c, "refinement") else 3)
    if job == "research":
        return _lvl(c, "library") > 0 and bool(c["research"]["current"])
    if job == "train":
        return _lvl(c, "training") > 0
    return True          # wood, mine, forage, meditate


def _pick_job(c: dict, p: dict, taken: dict) -> str:
    """What a disciple does this hour. Chores go by priority (1 first); at the same priority a store under
    LOW_STORE_DAYS of use comes first, then a queued build (its materials were paid when it was queued), then
    the shortest store, then what they are best at. Meditation is not a chore: when it is at the same priority
    as the work they would do, or higher, it takes a share of their working hours (MED_SHARE), and it never
    takes them from a store that is genuinely low."""
    forced = dao.road.forced_job(c, p, taken)
    if forced:
        return forced
    opts: dict = {}
    for job, level in p["prio"].items():
        if p.get("direct") and job not in ("meditate", "train", "research"):
            continue
        if p.get("direct") and job == "meditate":
            level = 1                                 # cultivation comes first for them
        if not level or job not in JOBS or not _job_open(c, job, taken):
            continue
        opts[job] = level
    med = opts.pop("meditate", 0)
    work = _best_chore(c, p, opts, taken)
    if not work:
        return "meditate" if med else ""
    if not med or (med > opts[work] and not p.get("direct")):
        return work
    if p.get("direct") and med < opts[work]:
        return "meditate"
    if work in STORE_OF and store_days(c, STORE_OF[work], taken) < LOW_STORE_DAYS:
        return work
    return "meditate" if _med_turn(c, p, opts[work] - med) else work


MED_SHARE = ((1, 2), (2, 3), (3, 4))   # meditation's share of working hours at the same priority as the work, one step above, two or more


def _med_turn(c: dict, p: dict, above: int) -> bool:
    """Whether this hour is meditation's: a steady rotation, offset per disciple so the sect is never all on the cushion at once."""
    n, d = MED_SHARE[max(0, min(2, above))]
    return (c["hour"] + c["pawns"].index(p)) % d < n


def med_share(above: int) -> str:
    n, d = MED_SHARE[max(0, min(2, above))]
    return {(1, 2): "half", (2, 3): "two thirds", (3, 4): "three quarters"}[(n, d)]


def _best_chore(c: dict, p: dict, opts: dict, taken: dict) -> str:
    if not opts:
        return ""
    top = min(opts.values())
    tied = [j for j, lv in opts.items() if lv == top]
    if len(tied) == 1:
        return tied[0]
    low = [j for j in tied if j in STORE_OF and store_days(c, STORE_OF[j], taken) < LOW_STORE_DAYS]
    if low:
        return min(low, key=lambda j: (store_days(c, STORE_OF[j], taken), -p["skills"][JOBS[j][1]]["lv"]))
    if "build" in tied:
        return "build"
    return min(tied, key=lambda j: (round(c["res"][STORE_OF[j]] / _cap(c), 2) if j in STORE_OF else 0.5, -p["skills"][JOBS[j][1]]["lv"]))


def store_days(c: dict, res: str, taken: dict | None = None) -> float:
    """How many days a store lasts at today's use (eating, firewood, repairs). inf when nothing draws on it."""
    cache = taken.setdefault("_days", {}) if taken is not None else {}
    if res not in cache:
        use = sum(v for r_, label, v in upkeep(c) if r_ == res and "spoiling" not in label)
        cache[res] = c["res"][res] / use if use > 0 else math.inf
    return cache[res]


def _do_job(c: dict, p: dict, job: str, quiet: bool) -> None:
    hour = c["hour"]
    skill = JOBS[job][1]
    out = _skill_mult(p, skill) * _work_mult(p, hour)
    _xp(p, skill, 1.0 * (2.0 if job == "train" and "Sword-mad" in p["traits"] else 1.0))
    if job == "farm":
        _add(c, "rice", out * math.prod(m for _, m in farm_rows(c)) * (1.25 if "Green thumb" in p["traits"] else 1.0))
    elif job == "wood":
        _add(c, "wood", out * GATHER["wood"])
    elif job == "mine":
        _add(c, "stone", out * GATHER["stone"])
        if _lvl(c, "spirit_vein") and not _idle_room(c, "spirit_vein"):
            _add(c, "stones", out * 0.1 * _lvl(c, "spirit_vein"))
    elif job == "forage":
        _add(c, "herbs", out * GATHER["herbs"] * (0.3 if _season(c) == 3 else 1.0) * STORYTELLERS[c["storyteller"]]["yield"])
    elif job == "build":
        # a helper: up to HELPERS_PER_SITE at each running job, in order; the builder's hour is added in _tick_builds
        sites = [x for x in _running(c) if len(x.get("crew_now", [])) < HELPERS_PER_SITE]
        if sites:
            b = sites[0]
            x = HELPER_X * out
            b["boost"] = b.get("boost", 0.0) + x
            b.setdefault("crew_now", []).append([p["name"], int(p["skills"]["build"]["lv"]), x])
    elif job == "craft":
        c["craft"] += out * (1 + 0.15 * (_lvl(c, "alchemy") - 1)) * (1 + _manual(c, p, "alchemy")[0]) \
            * (1.3 if "pill_furnace" in c["treasures"] else 1.0)
        if c["craft"] >= 6.0:
            c["craft"] -= 6.0
            dao.brew(c, p)
    elif job == "research":
        _research(c, out * (1 + 0.2 * (_lvl(c, "library") - 1)) * (1.25 if "Bookworm" in p["traits"] else 1.0)
                  * (1.25 if "jade_slip" in c["treasures"] else 1.0) * dao.research_x(c))
        if "Bookworm" in p["traits"]:
            p["joy"] = min(100.0, p["joy"] + 3)
    elif job == "meditate":
        _gain_qi(c, p, _work_mult(p, hour) * math.prod(m for _, m in qi_rate(c, p)), quiet)
        p["joy"] = min(100.0, p["joy"] + 1.5)
        p["sat_at"] = hour
    if job != "meditate":
        # daily life cultivates too, slowly: breath drawn while hauling stone is still breath
        _gain_qi(c, p, WORK_QI * _work_mult(p, hour) * math.prod(m for _, m in qi_rate(c, p)), quiet)


def farm_rows(c: dict) -> list[tuple[str, float]]:
    """Rice per farmer-hour, as a ledger: the base at skill 7 and every multiplier on it (skill and traits are the farmer's own)."""
    rows = [("A farmer-hour on the terraces", FARM_YIELD)]
    if _lvl(c, "fields") > 1:
        rows.append((f"Rice Terraces level {_lvl(c, 'fields')}", 1 + 0.15 * (_lvl(c, "fields") - 1)))
    if _has(c, "irrigation"):
        rows.append(("Terraced irrigation", 1.25))
    if _season(c) == 2:
        rows.append(("Autumn: the grain is heavy", 1.2))
    rows.append((f"The storyteller: {STORYTELLERS[c['storyteller']]['name']}", STORYTELLERS[c["storyteller"]]["yield"]))
    b = blight_left(c)
    if b:
        rows.append((f"Blight on the terraces ({_f(b / 24.0, 1)} days left)", float(c["blight"]["x"])))
    return rows


def blight_left(c: dict) -> int:
    """Hours of blight left on the terraces (the winter frost kills it)."""
    b = c.get("blight")
    if not isinstance(b, dict) or _season(c) == 3:
        return 0
    return max(0, int(b.get("until", 0)) - c["hour"])


PAVILION_READ = 7.0                # research points each disciple at home adds with an evening in the Scripture Pavilion
READ_HOUR = 21                     # when the evening reading happens


def _library_x(c: dict) -> float:
    """What the Pavilion, the jade slip and the sect's scholarship multiply research by."""
    lv = max(1, _lvl(c, "library"))
    return (1 + 0.2 * (lv - 1)) * (1.25 if "jade_slip" in c["treasures"] else 1.0) * dao.research_x(c)


def _readers(c: dict) -> list[dict]:
    return [p for p in _home(c) if p["sick_until"] <= c["hour"] and p["health"] >= 20]


def research_rows(c: dict) -> list[tuple[str, str]]:
    """Where research comes from, as a ledger: (label, amount). The evening reading is the sect's own (no study needed);
    research work and the Sect Master's study add to it."""
    lv = _lvl(c, "library")
    if not lv:
        return [("No Scripture Pavilion: only your own study moves research", "1 per correct answer")]
    n = len(_readers(c))
    x = _library_x(c)
    rows = [(f"Evening reading: {_n(n, 'disciple')} at home × {_f(PAVILION_READ)}", f"{round(n * PAVILION_READ, 1):g} a day")]
    if lv > 1:
        rows.append((f"Scripture Pavilion level {lv}", f"×{_f(1 + 0.2 * (lv - 1), 2)}"))
    if "jade_slip" in c["treasures"]:
        rows.append((lore.TREASURES["jade_slip"]["name"], "×1.25"))
    if dao.research_x(c) != 1.0:
        rows.append(("The sect's scholarship", f"×{_f(dao.research_x(c), 2)}"))
    if len(rows) > 1:
        rows.append(("Evening reading in all", f"{round(n * PAVILION_READ * x, 1):g} a day"))
    rows.append(("Research work (Work: Research)", f"about {_f(x, 2)} an hour per disciple at scholarship 7, more with skill"))
    rows.append(("Your own study", "+1 insight per correct answer"))
    return rows


def _evening_reading(c: dict) -> None:
    """Once a day every disciple at home reads in the Pavilion: research moves even when nobody studies (research_rows)."""
    lv = _lvl(c, "library")
    if not lv:
        return
    pts = len(_readers(c)) * PAVILION_READ * _library_x(c)
    if c["research"]["current"]:
        _research(c, pts)
    else:
        c["insight"] += pts                              # kept, and spent on the next topic chosen


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
    """Add qi. Small steps come on their own; a new great realm waits until you order the attempt."""
    p["qi"] += amount
    while p["step"] < MAX_STEP and p["qi"] >= step_need(p["step"]):
        if p["step"] % 4 == 3:
            if p["qi"] > step_need(p["step"]) or not p.get("told_ready"):
                if not p.get("told_ready") and not quiet:
                    p["told_ready"] = 1
                    _letter(c, "info", f"{p['name']} stands at a bottleneck",
                            f"They have gathered all the qi the {REALMS[p['step'] // 4]} realm can hold. "
                            "Open their page and order the breakthrough when the odds look good.")
            p["qi"] = step_need(p["step"])
            return
        p["qi"] -= step_need(p["step"])
        p["step"] += 1
        p["told_ready"] = 0
        if not p.get("master"):
            _fame(c, 1)                               # word travels of every step a disciple takes
        _think(p, "bt", "Broke through", 6, 24, c["hour"])
        if p.get("master"):
            _letter(c, "good", f"{p['name']} reached {realm_label(p['step'])}", "A steady step forward.")


def mood_mods(c: dict, p: dict) -> list[tuple[str, int]]:
    """The standing reasons for a disciple's mood (thoughts come and go on top of these)."""
    rows: list[tuple[str, int]] = []
    if "Optimist" in p["traits"]:
        rows.append(("Optimist", 8))
    if "Pessimist" in p["traits"]:
        rows.append(("Pessimist", -8))
    if _has(c, "dao_heart"):
        rows.append(("Dao heart", 6))
    if p["rest"] < 25:
        rows.append(("Exhausted", -8))
    if p["joy"] < 25:
        rows.append(("No joy in life", -8))
    elif p["joy"] > 75:
        rows.append(("Enjoying life", 4))
    if p["health"] < 50:
        rows.append(("In pain", -6))
    if len(c["pawns"]) > beds(c) + 2:
        rows.append(("The sect is crowded", -4))
    if c["beast"]:
        rows.append(("The sect's spirit beast", 3))
    if p.get("direct"):
        rows.append(("Chosen as a direct disciple", 5))
        if c["pawns"].index(p) >= beds(c):
            rows.append(("A direct disciple without a bed", -10))
        if p["joy"] < 40:
            rows.append(("A direct disciple expects some ease", -6))
    if _art(c, p, "sword") or artifact_of(c, p):
        rows.append((f"Entrusted with the {artifact_of(c, p)['name']}", 3))
    if _friends(c, p):
        rows.append(("Has a friend in the sect", 4))
    if _friends(c, p, -1):
        rows.append(("Lives beside a rival", -4))
    if _manual(c, p, "qi")[1] == "blood_sutra":
        rows.append(("The Blood Sutra whispers", -8))
    return rows + dao.mood_rows(c, p)


def appetite(c: dict, p: dict) -> float:
    """Food a disciple burns in an hour."""
    return HUNGER * (1.4 if "Glutton" in p["traits"] else 1.0) * dao.hunger_x(c, p) * (WINTER_HUNGER if _season(c) == 3 else 1.0)


def upkeep(c: dict) -> list[tuple[str, str, float]]:
    """What the sect uses up in a day, as a ledger: (resource, why, amount a day)."""
    rows: list[tuple[str, str, float]] = []
    n = len(c["pawns"])
    if n:
        eat = sum(appetite(c, p) for p in c["pawns"]) * 24 / 38.0
        cold = eat - eat / WINTER_HUNGER if _season(c) == 3 else 0.0
        rows.append(("rice", f"{n} disciple{'s' if n != 1 else ''} eat", eat - cold))
        if cold:
            rows.append(("rice", "Winter: cold bodies eat a quarter more", cold))
            rows.append(("wood", "Winter: firewood for the nights", WINTER_WOOD * n))
    if c["beast"]:
        rows.append(("rice", f"{c['beast']['name']} eats", 1.0))
    extra = sum(c["rooms"].values()) - REPAIR_FREE
    if extra > 0:
        for res, k in REPAIR.items():
            rows.append((res, f"Repairs: {extra} room level{'s' if extra != 1 else ''} beyond the first {REPAIR_FREE}", k * extra))
    keep = 0.5 if _has(c, "granary") else 1.0
    for res in ("rice", "herbs"):
        over = c["res"][res] - SPOIL_FROM * _cap(c)
        if over > 0:
            rows.append((res, f"{RES_NAMES[res]} spoiling above half the store", over * SPOIL * keep))
    return rows


def _upkeep(c: dict, quiet: bool) -> None:
    """The morning's upkeep (eating is hourly, in _tick_pawn). Away, nothing spoils."""
    short = set()
    for res, label, amount in upkeep(c):
        if res == "rice" and "eat" in label:
            continue
        if quiet and "spoiling" in label:
            continue
        if c["res"][res] < amount:
            short.add(label)
        c["res"][res] = max(0.0, c["res"][res] - amount)
    if quiet:
        return
    for p in c["pawns"]:
        if any(x.startswith("Winter: firewood") for x in short) and "Ascetic" not in p["traits"]:
            _think(p, "no_fire", "A night without firewood", -7, 30, c["hour"])
        if any(x.startswith("Repairs") for x in short):
            _think(p, "repairs", "Leaking roofs and cracked steps", -4, 30, c["hour"])


def _tick_pawn(c: dict, p: dict, taken: dict, quiet: bool) -> None:
    hour = c["hour"]
    hod = hour % 24
    night = hod >= 22 or hod < 6
    p["thoughts"] = [t for t in p["thoughts"] if t["until"] > hour]
    if p["sat_at"] < 0 or p["away_until"] > hour:
        p["sat_at"] = hour                # newly arrived (or an old save), or away: the count starts now
    if p["away_until"] > hour:
        p["doing"] = p["away_kind"] or "away"
        return
    # --- needs decay
    p["food"] = max(0.0, p["food"] - appetite(c, p))
    p["joy"] = max(0.0, p["joy"] - 1.2 * (0.5 if "Ascetic" in p["traits"] else 1.0))
    # --- eat (instant) when hungry
    if p["food"] < 35 and c["res"]["rice"] >= 1:
        c["res"]["rice"] -= 1
        p["food"] = min(100.0, p["food"] + 38)
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
            before = dict(c["res"])
            _do_job(c, p, job, quiet)
            _note_work(c, p, job, before)
            if job != "meditate":
                p["work"] = job                   # the chore they last did: what a stall alert measures against
            doing = JOBS[job][0].lower()
        else:
            doing = "idle"
            p["joy"] = min(100.0, p["joy"] + 3)
        p["health"] = min(100.0, p["health"] + 0.15)
    p["doing"] = doing
    # --- mood drifts toward what the disciple has to feel about
    target = 50 + sum(t["v"] for t in p["thoughts"]) + sum(v for _, v in mood_mods(c, p))
    p["mood"] += (max(0.0, min(100.0, target)) - p["mood"]) * 0.2
    # --- mental state
    if quiet or p["break_until"] > hour or doing in ("sleeping", "recovering"):
        return
    r = _rng(c, "mind", p["id"], hour)
    limit = 10 if "Iron will" in p["traits"] else 30 if "Volatile" in p["traits"] else 20
    if p["mood"] < limit and r.random() < 0.04:
        p["break_until"] = hour + r.randint(6, 12)
        _think(p, "catharsis", "Let it all out", 12, 36, hour + 12)
        foes = [o for o in _friends(c, p, -1) if o["away_until"] <= hour]
        if "Glutton" in p["traits"] and c["res"]["rice"] >= 8:
            c["res"]["rice"] -= 8
            _letter(c, "bad", f"{p['name']} raided the storehouse", "Their mood sank too low. They ate eight people's rice in one sitting and are sleeping it off.")
            return
        if foes:
            o = foes[0]
            _hurt(p, 8, c)
            _hurt(o, 8, c)
            made_up = r.random() < 0.5
            _bond(c, p, o, 25 if made_up else -15)
            _letter(c, "bad", f"{p['name']} and {o['name']} came to blows",
                    "It took three disciples to pull them apart. " + ("Afterwards they sat on the steps and talked until dark." if made_up else "Neither will look at the other now."))
            dao.brawl(c, p, o)
            return
        _letter(c, "bad", f"{p['name']} is having a qi deviation",
                "Their mood sank too low and they have stopped working. It will pass in half a day. "
                "Food, a bed and some rest keep moods up.")
    elif p["mood"] > 78 and p["inspired_until"] <= hour and r.random() < 0.015:
        p["inspired_until"] = hour + 24
        _letter(c, "good", f"{p['name']} is inspired", "For the next day they work half again as fast.")


# ---------------------------------------------------------------------------
# the wider world: rival sects, fame, manuals, treasures
# ---------------------------------------------------------------------------
def _make_world(c: dict) -> None:
    r = _rng(c, "world")
    c["sects"] = []
    for i, kind in enumerate(("righteous", "demonic", "neutral")):
        name, _, sur = r.choice([s for s in lore.SECTS if s[1] == kind])
        c["sects"].append({"id": f"s{i}", "name": name, "kind": kind, "rel": lore.KIND_START_REL[kind] + r.randint(-5, 5),
                           "power": round(r.uniform(0.85, 1.25), 2), "young": f"{sur} {r.choice(lore.YOUNG_GIVEN)}"})


def _sect(c: dict, sid: str) -> dict | None:
    return next((s for s in c["sects"] if s["id"] == sid), None)


def _rival(c: dict) -> dict | None:
    return min(c["sects"], key=lambda s: s["rel"]) if c["sects"] else None


def _rel(s: dict | None, delta: float) -> None:
    if s:
        s["rel"] = max(-100.0, min(100.0, s["rel"] + delta))


def stance(rel: float) -> str:
    return "Allied" if rel >= 40 else "Friendly" if rel >= 15 else "Wary" if rel > -15 else "Hostile" if rel > -50 else "Blood feud"


def _fame(c: dict, delta: float) -> None:
    c["fame"] = max(0.0, c["fame"] + delta)


def _p(c: dict, pid: str) -> dict | None:
    return next((p for p in c["pawns"] if p["id"] == pid), None)


def _home(c: dict) -> list[dict]:
    return [p for p in c["pawns"] if p["away_until"] <= c["hour"]]


def _strongest(c: dict, n: int, master: bool = False) -> list[dict]:
    pool = [p for p in _home(c) if (master or not p.get("master")) and p["health"] >= 40]
    return sorted(pool, key=lambda p: -duel_power(c, p))[:n]


def _max_grade(c: dict) -> int:
    d = _day(c)
    return 0 if d < 15 else 1 if d < 40 else 2 if d < 90 else 3


def _loot_manual(c: dict, r: random.Random, max_grade: int | None = None) -> str:
    g = _max_grade(c) if max_grade is None else max_grade
    pool = [k for k, m in lore.MANUALS.items() if k not in c["manuals"] and not m.get("demonic") and m["grade"] <= g]
    if not pool:
        return ""
    top = max(lore.MANUALS[k]["grade"] for k in pool)
    pick = r.choice([k for k in pool if lore.MANUALS[k]["grade"] >= top - 1])
    c["manuals"].append(pick)
    return pick


def _loot_treasure(c: dict, r: random.Random) -> str:
    pool = [k for k in lore.TREASURES if k not in c["treasures"]]
    if not pool:
        return ""
    pick = r.choice(pool)
    c["treasures"].append(pick)
    return pick


def _manual_name(mid: str) -> str:
    m = lore.MANUALS[mid]
    return f"{m['name']} ({lore.GRADES[m['grade']]} grade {lore.MANUAL_KIND[m['kind']].lower()})"


def _die(c: dict, p: dict) -> None:
    c["pawns"].remove(p)
    c["graves"] += 1
    c["adapt"] = max(0.55, c["adapt"] - 0.1)
    mourners, lines, rest = [], [], 0
    for o in c["pawns"]:
        b = bond(c, p, o)
        if b >= 30:
            v = -20 if b >= 70 else -16
            _think(o, "death", f"{p['name']}, a {'sworn sibling' if b >= 70 else 'friend'}, died", v, 240, c["hour"])
            mourners.append(o)
            lines.append((o["name"], f"grieves a {'sworn sibling' if b >= 70 else 'friend'}: {v} mood for 10 days", False))
        elif is_rival(c, p, o):
            _think(o, "death", f"{p['name']} died. They never made peace", -4, 72, c["hour"])
            lines.append((o["name"], "never made peace with them: -4 mood for 3 days", None))
        else:
            _think(o, "death", "A fellow disciple died", -10, 72, c["hour"])
            rest += 1
    if rest:
        lines.append(("", f"{rest} other disciple{'s' if rest != 1 else ''} mourn{'s' if rest == 1 else ''} a fellow disciple: -10 mood for 3 days", None))
    _unequip(c, p)
    dao.on_death(c, p)
    _annal(c, f"{p['name']} ({realm_label(p['step'])}) died." + (f" Mourned by {', '.join(o['name'] for o in _friends(c, p))}." if _friends(c, p) else ""))
    c["bonds"] = {k: v for k, v in c["bonds"].items() if p["id"] not in k.split("|")}
    _scene(c, "funeral", False, f"The funeral of {p['name']}",
           f"{p['name']} ({realm_label(p['step'])}) was laid to rest on the north slope. Incense, a bowl of rice, and a name cut into stone.",
           verdict="Mourning", party=[p] + mourners, lines=lines, extra=[("Graves on the slope", c["graves"], False, False)])


# ---------------------------------------------------------------------------
# breakthroughs and tribulations
# ---------------------------------------------------------------------------
def ready(p: dict) -> bool:
    return p["step"] < MAX_STEP and p["step"] % 4 == 3 and p["qi"] >= step_need(p["step"])


def bt_odds(c: dict, p: dict) -> list[tuple[str, int]]:
    """What a great-realm breakthrough has going for and against it, in percentage points."""
    target = p["step"] // 4 + 1
    trib = target >= 3
    rows = [("Reaching for a new great realm", 50 - 4 * max(0, target - 2))]
    if target == 1:
        rows.append(("Qi Condensation: the first gate is the widest", 10))
    lv = p["skills"]["scholar"]["lv"]
    if lv:
        rows.append((f"Scholarship {lv}", round(1.5 * lv)))
    if c["res"]["pills"] >= 1:
        rows.append(("A pill to steady the meridians (will be used)", pill_bt(target)))
    if _lvl(c, "meditation"):
        rows.append(("Meditation Chamber", 3 * _lvl(c, "meditation")))
    mid = _manual(c, p, "qi")[1]
    if mid:
        rows.append((lore.MANUALS[mid]["name"], 4 * (lore.MANUALS[mid]["grade"] + 1)))
    if p["mood"] >= 70:
        rows.append(("A calm heart", 8))
    elif p["mood"] < 35:
        rows.append(("Heart demons (low mood)", -12))
    if p["health"] < 60:
        rows.append(("Wounded", -15))
    if p["bt_tries"]:
        rows.append(("Lessons of past failures", min(20, 6 * p["bt_tries"])))
    if p["resolve_until"] > c["hour"]:
        rows.append(("Burning resolve", 10))
    if any(o["away_until"] <= c["hour"] for o in _friends(c, p)):
        rows.append(("A friend stands guard", 5))
    if _art(c, p, "charm"):
        rows.append((artifact_of(c, p)["name"], int(_art(c, p, "charm"))))
    if trib and p["element"] == lore.SEASON_ELEMENT[_season(c)]:
        rows.append((f"{SEASONS[_season(c)]} favours {p['element']} roots", 5))
    if trib and _lvl(c, "ward"):
        rows.append(("The Ward Formation draws off lightning", 3 * _lvl(c, "ward")))
    if trib and "lightning_rod" in c["treasures"]:
        rows.append((lore.TREASURES["lightning_rod"]["name"], 10))
    rows += dao.bt_rows(c, p)
    total, cap = sum(v for _, v in rows), bt_cap(target)
    if total > cap:
        rows.append((f"The bottleneck of {REALMS[min(target, len(REALMS) - 1)]}: no attempt is surer than {cap}%", cap - total))
    elif total < 5:
        rows.append(("Heaven always leaves a sliver of hope", 5 - total))
    return rows


BT_CAP = (85, 82, 80, 76, 72, 70, 68)      # the surest any attempt on great realm 1, 2, ... can be: heaven grows harder to fool


def bt_cap(target: int) -> int:
    return BT_CAP[max(0, min(len(BT_CAP) - 1, target - 1))]


def pill_bt(target: int) -> int:
    """What a pill adds to an attempt on great realm `target`: much at the first gates, less as the realms deepen."""
    return max(6, 24 - 4 * target)


def bt_chance(c: dict, p: dict) -> int:
    """The odds of a great-realm attempt: the sum of its ledger (bt_odds), which already holds the realm's cap."""
    return max(5, min(bt_cap(p["step"] // 4 + 1), sum(v for _, v in bt_odds(c, p))))


def _promote(c: dict, p: dict) -> None:
    new = rank_of(p)
    if new > p.get("rank", 0) and not p.get("master"):
        _think(p, "promoted", f"Promoted to {lore.RANKS[new]}", 8, 72, c["hour"])
        _letter(c, "good", f"{p['name']} is now {'an' if lore.RANKS[new][0] in 'AEIOU' else 'a'} {lore.RANKS[new]}",
                "Higher ranks may study higher-grade manuals in the Scripture Pavilion.")
    p["rank"] = new


def attempt(st: dict, pawn_id: str, now: float) -> dict:
    """Order a disciple to attempt a great-realm breakthrough. From Core Formation up, heaven answers with lightning."""
    c = _c(st, now)
    p = _p(c, pawn_id)
    if not p or not ready(p) or p["away_until"] > c["hour"]:
        return {"ok": False, "error": "They are not ready to break through."}
    gate_ok, gate_text = dao.road.realm_gate(c, p)
    if not gate_ok:
        return {"ok": False, "error": gate_text}
    target = p["step"] // 4 + 1
    trib = target >= 3
    chance = bt_chance(c, p) / 100.0
    snap = _snap(c)
    kind = "tribulation" if trib else "breakthrough"
    odds = ("", f"The odds were {bt_chance(c, p)}%" + (f"; heaven sent {target * 3} bolts of lightning" if trib else ""), None)
    if c["res"]["pills"] >= 1:
        c["res"]["pills"] -= 1
        odds = ("", odds[1] + "; a pill to steady the meridians was used", None)
    roll = _rng(c, "bt", p["id"], c["hour"], p["bt_tries"]).random()
    bolts = target * 3 if trib else 0
    if roll > chance:
        p["bt_tries"] += 1
        dao.on_bt(c, p, False, False, trib)
        p["qi"] = step_need(p["step"]) * 0.6
        _hurt(p, 35 if trib else 25, c)
        _think(p, "bt_fail", "Failed a breakthrough", -10, 48, c["hour"])
        died = p["health"] <= 0 and trib and STORYTELLERS[c["storyteller"]]["deaths"] and not p.get("master")
        if died:
            _die(c, p)
            ev = _letter(c, "bad", f"{p['name']} perished under the tribulation",
                         f"The {_ordinal(max(1, int(bolts * roll)))} bolt found a body already broken. Never send the wounded to face heaven.")
            _scene(c, kind, False, ev["title"], ev["text"], verdict="Struck down", party=[p], lines=[odds], snap=snap, first=snap["next"])
            return {"ok": True, "success": False, "event": ev}
        p["health"] = max(p["health"], 5.0)
        text = (f"Of {bolts} bolts of heavenly lightning, the last ones broke through their guard. " if trib
                else f"The attempt on {REALMS[target]} backfired. ")
        ev = _letter(c, "bad", f"{p['name']} failed {'the tribulation' if trib else 'a breakthrough'}",
                     text + "They are hurt and must gather qi again. Each failure teaches something for the next attempt.")
        _scene(c, kind, False, ev["title"], ev["text"], verdict="The bottleneck held", party=[p],
               lines=[odds, (p["name"], f"{int(p['bt_tries'])} failed attempt{'s' if p['bt_tries'] != 1 else ''}: the next try gets +{min(20, 6 * int(p['bt_tries']))}", None)], snap=snap)
        return {"ok": True, "success": False, "event": ev}
    grade = dao.bt_grade(c, p)[0]                    # how well it was prepared, decided before the roll
    perfect = grade >= 4
    p["bt_tries"] = 0
    p["qi"] = 0.0
    p["step"] += 1
    _think(p, "bt", "Broke through to a new realm", 15, 72, c["hour"])
    for o in c["pawns"]:
        if o is not p:
            b = bond(c, p, o)
            if is_rival(c, p, o):
                _think(o, "bt_other", f"Envious of {p['name']}", -6, 72, c["hour"])
                o["resolve_until"] = max(o["resolve_until"], c["hour"] + 48)       # and spurred on
            else:
                _think(o, "bt_other", f"{p['name']}, a friend, ascended" if b >= 30 else "A fellow disciple ascended", 9 if b >= 30 else 5, 48, c["hour"])
    _fame(c, 2 * target)
    _annal(c, f"{p['name']} reached {REALMS[target]}" + (" under heavenly tribulation." if trib else "."))
    text = (f"{bolts} bolts of heavenly lightning fell on the peak, and {p['name']} stood through every one. " if trib
            else "The bottleneck gave way. ")
    ev = _letter(c, "good", f"{p['name']} reached {REALMS[target]}", text + "The whole sect feels it.")
    ev["text"] = text + dao.after_breakthrough(c, p, grade) + "The whole sect feels it."
    _promote(c, p)
    dao.on_bt(c, p, True, perfect, trib)
    _scene(c, kind, True, ev["title"], ev["text"], verdict="Heaven was weathered" if trib else "Breakthrough", party=[p],
           lines=[odds, (p["name"], f"a {dao.GRADES[grade][0].lower()} breakthrough", grade >= 2)], snap=snap)
    if p["step"] // 4 == len(REALMS) - 1 and p.get("master") and not c["flags"].get("ascended"):
        c["flags"]["ascended"] = 1
        _fame(c, 100)
        _letter(c, "good", "The heavens open",
                f"{p['name']} has stepped into Immortal Ascension. The {c['name']} will be spoken of for ten thousand years. "
                "The sect carries on for as long as you care to guide it.")
        dao.succession(c)
    return {"ok": True, "success": True, "perfect": perfect, "event": ev}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def gift(st: dict, sect_id: str, now: float) -> dict:
    c = _c(st, now)
    s = _sect(c, sect_id)
    if not s:
        return {"ok": False, "error": "Unknown sect."}
    if c["res"]["stones"] < 10:
        return {"ok": False, "error": "A fitting gift costs 10 spirit stones."}
    c["res"]["stones"] -= 10
    _rel(s, 8)
    return {"ok": True, "event": _letter(c, "info", f"Gifts sent to the {s['name']}", f"Relations are now {stance(s['rel']).lower()}.")}


def burn_manual(st: dict, manual: str, now: float) -> dict:
    c = _c(st, now)
    if manual not in c["manuals"] or not lore.MANUALS[manual].get("demonic"):
        return {"ok": False, "error": "Only a forbidden manual can be burned."}
    c["manuals"].remove(manual)
    for s in c["sects"]:
        _rel(s, 6 if s["kind"] == "righteous" else 0)
    return {"ok": True, "event": _letter(c, "info", f"The {lore.MANUALS[manual]['name']} was burned", "The whispers stop. The righteous sects take note.")}


# ---------------------------------------------------------------------------
# storyteller: threats
# ---------------------------------------------------------------------------
def _ask(c: dict, kind: str, title: str, text: str, options: list[tuple[str, str]], **data) -> None:
    c["pending"] = {"kind": kind, "title": tidy(title), "text": tidy(text), "options": [{"id": i, "label": tidy(lab)} for i, lab in options], **data}
    c["last_event_day"] = _day(c)          # a decision: the storyteller measures quiet spells from here


THEFT_SAFE = 1.3                   # raiders held off at this ratio or better take nothing from the stores
LOOTABLE = ("rice", "wood", "stone", "herbs")


def strength_word(ratio: float) -> str:
    """How a threat looks, worded to match the numbers beside it."""
    return ("They look far weaker than us." if ratio >= 2.0 else "They look weaker than us." if ratio >= 1.35
            else "We should hold them." if ratio >= 1.1 else "It will be close." if ratio >= 0.85
            else "They are stronger than us." if ratio >= 0.6 else "They are far stronger than us.")


def battle_strength(c: dict, how: str, src: dict | None = None) -> float:
    """The sect's strength in a battle fought this way (before the roll): what _battle measures against the foe."""
    ward = ward_power(c)
    d = ward * 2 + (defense(c) - ward) * 0.5 if how == "wards" else defense(c) * (1.3 if how == "berserk" else 1.0)
    return d + dao.ally_aid(c, src)


def loot_target(c: dict) -> str:
    """Raiders go for the fullest store."""
    return max(LOOTABLE, key=lambda k: c["res"][k] / _cap(c))


def theft_share(ratio: float, how: str) -> float:
    """The share of the targeted store raiders carry off: nothing from THEFT_SAFE up, more the worse the fight goes;
    guarding the storehouse doors keeps most of it."""
    if how == "tribute" or ratio >= THEFT_SAFE:
        return 0.0
    return min(0.45, 0.6 * (THEFT_SAFE - ratio)) * (0.35 if how == "guard" else 1.0)


def _omen(c: dict, r: random.Random, kind: str, src: dict | None = None, boost: float = 1.0, why: str = "") -> None:
    """A threat is seen coming: the player chooses how to meet it."""
    tell = STORYTELLERS[c["storyteller"]]
    strength = (wealth(c) / 22 + len(c["pawns"]) * 9 + min(_day(c), 48) * 1.1 + c["fame"] * 0.5) * r.uniform(0.7, 1.35) \
        * max(tell["threat"], 0.6) * c["adapt"] * boost
    if kind == "raid" and src:
        strength *= src["power"]
    if kind == "beasts" and "beast_bell" in c["treasures"]:
        strength *= 0.67
    ours = defense(c)
    ratio = ours / max(strength, 1.0)
    who = "A beast tide" if kind == "beasts" else f"Raiders of the {src['name']}" if src else "Mountain bandits"
    bits = [f"disciples {int(sum(combat_power(c, p) for p in c['pawns']))}"]
    if ward_power(c):
        bits.append(f"wards {int(ward_power(c))}")
    if c["beast"]:
        bits.append(f"{c['beast']['name']} {int(beast_power(c))}")
    if dao.defense_extra(c) >= 1:
        bits.append(f"formation masters {int(dao.defense_extra(c))}")
    parts = (f"Their strength is about {int(strength)}; ours is {int(ours)} ({', '.join(bits)}), "
             f"{ratio:.1f} to 1.")
    opts = [("fight", "Meet them at the gate")]
    wards = bool(_lvl(c, "ward"))
    if wards:
        opts.append(("wards", f"Seal the gates and hold behind the wards (our strength {int(battle_strength(c, 'wards', src))}, fewer wounds)"))
    cost = max(5, int(strength / 10))
    target = loot_target(c) if kind == "raid" else ""
    plunder = ""
    if target:
        def at_risk(how: str) -> int:
            return int(c["res"][target] * theft_share(battle_strength(c, how, src) / max(strength, 1.0), how))
        f_risk, g_risk = at_risk("fight"), at_risk("guard")
        opts[0] = ("fight", f"Meet them at the gate ({f_risk} {target} at risk)" if f_risk else "Meet them at the gate")
        if f_risk:
            opts.insert(1, ("guard", f"Guard the storehouse doors (about {g_risk} {target} at risk; no spoils, no fame)"))
        plunder = (f" They want our {target} ({int(c['res'][target])}), the fullest store"
                   + (f": about {f_risk} could go unless we hold them at {THEFT_SAFE:.1f} to 1." if f_risk else ", and will not get near it."))
    if c["elixirs"]["berserk"] >= 1:
        opts.append(("berserk", "Hand out Berserk Pills and charge (+30% strength, then wounds)"))
    if kind == "raid" and c["res"]["stones"] >= cost:
        opts.append(("tribute", f"Pay them off ({cost} spirit stones)"))
    how = "The gate wins fame and spoils" + ("; the wards are safer but win nothing" if wards else "")
    _ask(c, "omen", f"{who} approach{'es' if kind == 'beasts' else ''}",
         (why + " " if why else "") + f"{parts} {strength_word(ratio)}{plunder} {how}"
         + ("; tribute costs face." if kind == "raid" and c["res"]["stones"] >= cost else "."),
         opts, threat=kind, strength=float(strength), src=src["id"] if src else "", cost=cost, target=target)


def _threat(c: dict, r: random.Random, kind: str, strength: float, how: str = "fight", src: dict | None = None) -> dict:
    """A threat is met. The battle itself is _battle; this frames its result as a scene."""
    snap = _snap(c)
    siege = copy.deepcopy(c.get("siege"))
    fighters = [] if how == "tribute" else [p for p in _home(c) if combat_power(c, p) > 0]
    stolen = float(c["tally"].get("stolen", 0.0))
    ratio = battle_strength(c, how, src) / max(strength, 1.0)      # what _battle measures, before it runs
    ev = _battle(c, r, kind, strength, how, src)
    stolen = float(c["tally"].get("stolen", 0.0)) - stolen
    won = ev["kind"] != "bad" and how != "tribute"
    foe = "Beast tide" if kind == "beasts" else f"{src['name']} raiders" if src else "Mountain bandits"
    lines = [("", f"{foe}: strength about {int(strength)}. The sect "
              + ("paid them off" if how == "tribute" else "held behind the wards" if how == "wards"
                 else "charged on Berserk Pills" if how == "berserk" else "guarded the storehouse doors" if how == "guard"
                 else "met them at the gate") + ".", None)]
    # the verdict says what the letter says: _battle's bands are 1.4 (clean), 0.9 (with wounds), 0.55 (a costly win), below that overrun
    verdict = ("Tribute paid" if how == "tribute" else "Victory" if ev["kind"] == "good" else "Victory, with wounds" if won
               else "A costly win" if ratio >= 0.55 else "Defeat")
    title = ev["title"]
    if siege and src and siege.get("src") == src["id"]:
        if c.get("siege") is None and won:
            title, verdict = f"The {src['name']} is broken", "The siege is lifted"
            lines.append(("", "Three battles, three victories. The siege is over.", True))
        elif c.get("siege") is None:
            verdict = "The gate fell"
            lines.append(("", "The siege ended in defeat.", False))
        else:
            lines.append(("", f"Siege: battle {siege.get('stage', 1)} of three won.", True))
    unhurt = [p["name"] for p in fighters if p in c["pawns"] and p["health"] > snap["pawns"].get(p["id"], (0.0,))[0] - 1]
    if unhurt:
        lines.append(("", f"Came through unhurt: {', '.join(unhurt)}.", True))
    if stolen >= 1:
        lines.append(("", f"Carried off from the stores: {int(stolen)}", False))
    _scene(c, "theft" if stolen >= 1 else "raid", won, title, ev["text"], verdict=verdict, party=fighters, lines=lines, snap=snap, first=snap["next"])
    return ev


def _battle(c: dict, r: random.Random, kind: str, strength: float, how: str = "fight", src: dict | None = None) -> dict:
    tell = STORYTELLERS[c["storyteller"]]
    who = "The beast tide" if kind == "beasts" else f"The {src['name']} raid" if src else "The bandit raid"
    c["last_threat_day"] = _day(c)
    if how == "tribute":
        cost = max(5, int(strength / 10))
        c["res"]["stones"] = max(0.0, c["res"]["stones"] - cost)
        _rel(src, 5)
        _fame(c, -2)
        for p in c["pawns"]:
            _think(p, "tribute", "The sect paid tribute", -4, 48, c["hour"])
        return _letter(c, "info", "Tribute was paid", f"{cost} spirit stones bought peace. The disciples keep their eyes on the ground.")
    berserk = how == "berserk"
    plan = how
    d = battle_strength(c, how, src)
    if berserk:
        how = "fight"
        c["elixirs"]["berserk"] = max(0, c["elixirs"]["berserk"] - 1)
    aid = dao.ally_aid(c, src)
    ratio = d / max(strength, 1.0)
    soft = 0.5 if how == "wards" else 0.7 if how == "guard" else 1.0
    fighters = [p for p in _home(c) if combat_power(c, p) > 0]
    for p in fighters:
        _xp(p, "combat", 12 * soft)
        if berserk:
            p["health"] = max(10.0, p["health"] - 12)
            p["toxin"] += 1.5
    dao.after_fight(c, fighters, ratio, how, src, kind)
    if aid:
        _letter(c, "info", "Allied disciples stood with you", "Your allies kept their oath and sent swords to the gate.")

    def wound(lo: int, hi: int, n: int) -> list[str]:
        pool = fighters or _home(c) or c["pawns"]
        hit = r.sample(pool, min(max(1, int(n * soft)), len(pool)))
        sev = min(1.7, 1.0 / max(ratio, 0.45)) if ratio < 0.9 else 1.0      # outmatched fighters are hit harder
        for p in hit:
            _hurt(p, r.randint(lo, hi) * soft * sev, c)
        return [p["name"] for p in hit]

    def plunder() -> str:
        """Raiders who get past the gate carry off part of the fullest store."""
        if kind != "raid" or ratio < 0.55:
            return ""
        target = loot_target(c)
        n = c["res"][target] * theft_share(ratio, plan)
        if n < 1:
            return ""
        c["res"][target] -= n
        c["tally"]["stolen"] = float(c["tally"].get("stolen", 0.0)) + n
        return (f" They broke into the storehouse and carried off {int(n)} {target}"
                + (", though the guards on the doors kept the rest." if plan == "guard" else "."))
    if ratio >= 0.9:
        c["flags"]["first_win"] = 1
        if how == "fight":
            for i, a in enumerate(fighters):
                for b in fighters[i + 1:]:
                    _bond(c, a, b, 5)                 # they stood shoulder to shoulder
    _annal(c, f"{who} was {'beaten off' if ratio >= 0.9 else 'survived, at a cost' if ratio >= 0.55 else 'a defeat'}.")
    held = "Your disciples" + (" and the wards" if ward_power(c) else "") + (f", with the {c['beast']['name']}," if c["beast"] else "")
    if ratio >= 1.4:
        loot = r.randint(3, 8) if kind == "raid" and how == "fight" else 0
        _add(c, "stones", loot)
        if how == "fight":
            _fame(c, 5)
            _rel(src, -5)
            if src:
                src["power"] = round(max(0.6, src["power"] * 0.95), 2)
        c["adapt"] = min(1.5, c["adapt"] + 0.06)
        for p in c["pawns"]:
            _think(p, "fought", "Drove off an attack", 5 if how == "fight" else 2, 36, c["hour"])
        return _letter(c, "good", f"{who} was driven off", f"{held} held without a scratch."
                       + (f" The raiders dropped {loot} spirit stones." if loot else "")
                       + (f" Their leader left behind the {_new_artifact(c, r, f'taken from {who[0].lower() + who[1:]}')['name']}."
                          if kind == "raid" and how == "fight" and r.random() < 0.35 else ""))
    if ratio >= 0.9:
        names = wound(15, 35, 2)
        text = f"The sect won, but {_and(names)} took wounds. Pills and rest will mend them." + plunder()
        kind_ = "info"
        if how == "fight":
            _fame(c, 3)
        c["adapt"] = min(1.5, c["adapt"] + 0.04)
    elif ratio >= 0.55:
        names = wound(20, 50, max(2, len(c["pawns"]) // 2))
        if kind == "raid":
            text = f"A costly win. {_and(names)} {_be(names)} wounded." + plunder()
        else:
            for res in LOOTABLE:
                c["res"][res] *= 0.9
            text = f"A costly win. {_and(names)} {_be(names)} wounded and a tenth of the stores were trampled."
        kind_ = "bad"
    else:
        wound(30, 70, len(c["pawns"]))
        before = sum(c["res"][k] for k in LOOTABLE)
        for res in LOOTABLE + ("stones",):
            c["res"][res] *= 0.65
        if kind == "raid":
            c["tally"]["stolen"] = float(c["tally"].get("stolen", 0.0)) + before - sum(c["res"][k] for k in LOOTABLE)
        text = ("The sect was overrun. A third of the stores are gone and nearly everyone is hurt. Train"
                + (", and raise the Ward Formation." if ward_power(c) else ", and raise a Ward Formation."))
        kind_ = "bad"
        _fame(c, -3)
    if ratio < 0.9:
        # The world eases off a sect that has just been beaten.
        c["adapt"] = max(0.55, c["adapt"] - 0.2)
        c["last_threat_day"] = _day(c) + min(10, int(tell["threat_gap"]))
    dead = []
    for p in list(c["pawns"]):
        if p["health"] <= 0:
            if p.get("master") or not tell["deaths"] or p not in fighters or dao.saved_by_companion(c, p, fighters):
                p["health"] = max(p["health"], 6.0)
            else:
                dead.append(p["name"])
                _die(c, p)
    if dead:
        text += f" {' and '.join(dead)} did not survive."
    for p in c["pawns"]:
        _think(p, "fought", "Fought for the sect" if ratio >= 0.9 else "The sect was beaten", 4 if ratio >= 0.9 else -8, 36, c["hour"])
    return _letter(c, kind_, f"{who} struck", text)


# ---------------------------------------------------------------------------
# storyteller: the day's event
# ---------------------------------------------------------------------------
def _others(c: dict) -> list[dict]:
    return [p for p in _home(c) if not p.get("master")]


EVENT_COOLDOWN = 16                              # days before the same daily event can come up again
EVENT_REPEATS = frozenset({"beasts", "raid", "wanderer"})   # threats keep their own spacing; each wanderer is someone new
YEAR = DAYS_PER_SEASON * 4
# Stories wait longer: a second cave abode or a second plague in the river towns inside a year reads as a bug.
EVENT_COOLDOWNS = {"cave": YEAR, "secret_realm": YEAR, "demonic_offer": YEAR, "spy": YEAR, "village": YEAR, "infiltrator": YEAR,
                   "cliff": 30, "auction": 24, "elder": 24, "plague": 40, "blight": 30, "young_master": 28, "lord": 20, "thief": 20, "feud": 10}
QUEST_COOLDOWN = YEAR                            # the same request (the river-town plague, the bridge) at most once a year
PRESSURE = frozenset({"beasts", "raid", "plague", "blight", "infiltrator", "young_master", "thief"})
LETTERS = frozenset({"herbs", "meteor", "elder", "harvest", "sickness", "weevils", "cold", "cliff", "epiphany", "furnace", "rare_herb", "beast_bond"})


def _quests_open(c: dict, day: int) -> list[str]:
    seen = c["flags"].get("quests") if isinstance(c["flags"].get("quests"), dict) else {}
    return [k for k in QUESTS if not isinstance(seen.get(k), (int, float)) or day - seen[k] >= QUEST_COOLDOWN]


def _daily_event(c: dict) -> None:
    tell = STORYTELLERS.get(c["storyteller"], STORYTELLERS["balanced"])
    day = _day(c)
    year = day // YEAR + 1
    doy = day % YEAR
    r = _rng(c, "event", day)
    if c["pending"]:
        return
    home, others = _home(c), _others(c)
    if day >= 4 and not c["flags"].get("first_threat"):
        c["flags"]["first_threat"] = 1
        _omen(c, r, "beasts", boost=0.4, why="A lone, half-starved spirit wolf is circling the terraces. A first test for the sect.")
        return
    fid = f"{year}-{_season(c)}"
    fest = festival_of(day)
    if fest and day % DAYS_PER_SEASON >= FESTIVAL_DAY and c["festival"] != fid:
        c["festival"] = fid
        _offer_festival(c, fest)
        return
    # --- the calendar: recruitment in spring, the tournament in autumn
    if year >= 2 and 1 <= doy < DAYS_PER_SEASON and c["recruit_year"] != year and len(c["pawns"]) < pawn_cap(c):
        c["recruit_year"] = year
        cands = []
        for _ in range(3):
            cands.append(_make_pawn(c, c["next_pawn"], lucky=c["fame"] >= 20))
            c["next_pawn"] += 1
        def line(p):
            best = max(SKILLS, key=lambda s: p["skills"][s]["lv"])
            return f"{p['name']}: {p['root']} root, {' and '.join(p['traits']).lower()}, {SKILL_NAMES[best].lower()} {p['skills'][best]['lv']}"
        _ask(c, "recruit", "The spring entrance trial",
             "Youths from the villages below have climbed the ten thousand steps to have their spirit roots tested. "
             "You may take one. " + " / ".join(line(p) for p in cands) + ".",
             [(f"pick{i}", f"Take {p['name']}") for i, p in enumerate(cands)] + [("decline", "Take no one this year")], cands=cands)
        return
    if 30 <= doy < 3 * DAYS_PER_SEASON and c["tournament_year"] != year and len(home) >= 2 and c["sects"]:
        c["tournament_year"] = year
        champs = _strongest(c, 3, master=False) or _strongest(c, 1, master=True)
        if champs:
            foes = tournament_field(c)
            watcher = champs[0]
            _ask(c, "tournament", "The Hundred Sects Tournament",
                 f"Each autumn every sect sends a young champion (this year's bracket: up to {realm_label(tournament_cap(c) + len(foes) - 1)}). "
                 f"{len(foes)} rounds, weakest first; a loss ends the run; "
                 "fame and prizes for every win. The champions' strength, round by round: "
                 + ", ".join(f"{ch['name']} {int(fp)}" for _, ch, fp in foes) + ". Whom do you send?",
                 [(p["id"], f"Send {p['name']} ({tournament_odds(c, p)})") for p in champs]
                 + [("observe", f"Send {watcher['name']} only to watch and learn (+40 combat practice, +1 fame, no risk)"),
                    ("decline", "Stay home this year")], watcher=watcher["id"])
            return
    if dao.calendar(c, r, day, year, doy):
        return
    # A quiet spell is filled: after `quiet` days with nothing happening, the storyteller sends something, and leans to trouble.
    fill = day - int(c["last_event_day"]) >= tell.get("quiet", 99)
    if not fill and r.random() > tell["event"] * (1.3 if _lvl(c, "market") else 1.0):
        return
    rival = _rival(c)
    fl = c["flags"]
    room_left = pawn_cap(c) - len(c["pawns"])
    season = _season(c)
    table = [("wanderer", 0 if room_left <= 0 else 30 if len(c["pawns"]) < 4 else 6 if room_left == 1 else 14),
             ("quest", 10 if not c["quest"] and day >= 7 and _quests_open(c, day) else 0), ("merchant", 12 + 6 * _lvl(c, "market")),
             ("herbs", 8), ("meteor", 6), ("elder", 6), ("harvest", 7 if season != 3 and not blight_left(c) else 0),
             ("sickness", 6), ("weevils", 3 if c["res"]["rice"] >= 30 else 0), ("cold", 8 if season == 3 else 0),
             # the mid-game troubles
             ("plague", 7 if day >= 14 and len(others) >= 3 else 0),
             ("blight", 7 if day >= 10 and _lvl(c, "fields") and season != 3 and not blight_left(c) else 0),
             ("infiltrator", 10 if day >= 16 and len(others) >= 2 and c["sects"] else 0),
             ("thief", 9 if day >= 12 and max(c["res"][k] for k in LOOTABLE) >= 30 else 0),
             ("feud", 12 if rival_pairs(c) else 0),
             # the tropes
             ("young_master", 11 if rival and others and day >= 4 else 0),
             ("auction", 8 if c["res"]["stones"] >= 15 and day >= 8 else 0),
             ("secret_realm", 8 if len(others) >= 2 and day >= 10 else 0),
             ("fallen_genius", 9 if not fl.get("genius") and day >= 6 and len(c["pawns"]) < pawn_cap(c) else 0),
             ("beast_cub", 7 if not c["beast"] and day >= 5 else 0),
             ("demonic_offer", 5 if "blood_sutra" not in c["manuals"] and day >= 12 else 0),
             ("cave", 7 if day >= 8 and others else 0),
             ("engagement", 6 if not fl.get("engagement") and others and day >= 9 and c["sects"] else 0),
             ("spy", 4 if rival and rival["rel"] < 0 and len(others) >= 3 and day >= 14 else 0),
             ("village", 8 if others and day >= 5 else 0),
             ("cliff", 5 if len(others) >= 3 and day >= 8 else 0), ("epiphany", 6), ("furnace", 5 if _lvl(c, "alchemy") else 0)]
    table += dao.table(c, day, others)
    if tell["threat"] > 0 and day >= 6 and day - c["last_threat_day"] >= tell["threat_gap"] and not c["siege"]:
        table += [("beasts", 16), ("raid", 12 if day >= 12 else 0)]
    if fill:
        # a quiet spell is broken by something to decide, not another letter; past the opening it leans to trouble
        table = [(k, 0 if k in LETTERS else w * 3 if k in PRESSURE and tell["threat"] > 0 and day >= 12 else w) for k, w in table]
    # The same story twice in a short while reads as a bug: a kind that came up recently waits its turn.
    seen = fl["seen"] = fl["seen"] if isinstance(fl.get("seen"), dict) else {}
    fresh = [(k, w) for k, w in table if w > 0 and (k in EVENT_REPEATS or not isinstance(seen.get(k), (int, float))
                                                  or day - seen[k] >= EVENT_COOLDOWNS.get(k, EVENT_COOLDOWN))]
    kinds, weights = zip(*(fresh or [(k, w) for k, w in table if w > 0]))
    kind = r.choices(kinds, weights)[0]
    seen[kind] = day
    if dao.raise_event(c, r, kind):
        return
    if kind == "plague":
        _raise_plague(c, r) or _letter(c, "info", "A cough in the valley", "A fever is going round the villages below. None of it has climbed the steps yet.")
    elif kind == "blight":
        _raise_blight(c, r) or _letter(c, "info", "Blight in the valley", "The lowland farms are burning blighted rice. The terraces look clean.")
    elif kind == "infiltrator":
        _raise_infiltrator(c, r) or _letter(c, "info", "Footprints on the wall", "Someone climbed in and out again in the night. Nothing seems to be missing.")
    elif kind == "thief":
        _raise_thief(c, r) or _letter(c, "info", "Footprints on the wall", "Someone climbed in and out again in the night. Nothing seems to be missing.")
    elif kind == "feud":
        _raise_feud(c, r)
    elif kind == "quest":
        _offer_quest(c, r)
    elif kind == "wanderer":
        cand = _make_pawn(c, c["next_pawn"], lucky=c["fame"] >= 20)
        c["next_pawn"] += 1
        best = max(SKILLS, key=lambda s: cand["skills"][s]["lv"])
        _ask(c, "wanderer", "A wanderer at the gate",
             f"{cand['name']}, {cand['age']}, asks to join. {cand['origin']} {cand['root']} spirit root; "
             f"{' and '.join(cand['traits']).lower()}; best at {SKILL_NAMES[best].lower()} ({cand['skills'][best]['lv']}). "
             "Another mouth, another pair of hands.", [("accept", "Welcome them"), ("decline", "Turn them away")], cand=cand)
    elif kind == "merchant":
        rate = 1.0 + 0.25 * _lvl(c, "market")
        opts = []
        if c["res"]["rice"] >= 40:
            opts.append(("sell_rice", f"Sell 25 rice for {int(6 * rate)} spirit stones"))
        if c["res"]["herbs"] >= 10:
            opts.append(("sell_herbs", f"Sell 8 herbs for {int(7 * rate)} spirit stones"))
        if c["res"]["pills"] >= 3:
            opts.append(("sell_pills", f"Sell 2 pills for {int(8 * rate)} spirit stones"))
        if c["res"]["stones"] >= 6:
            opts += [("buy_rice", "Buy 30 rice for 6 spirit stones"), ("buy_wood", "Buy 40 wood for 6 spirit stones")]
        if c["res"]["stones"] >= 10:
            opts.append(("buy_pills", "Buy 2 pills for 10 spirit stones"))
        if not opts:
            _letter(c, "info", "A merchant caravan passed", "You had nothing they wanted, and no spirit stones to spend.")
            return
        _ask(c, "merchant", "A merchant caravan", "Traders have stopped at the gate for the day.", opts + [("decline", "Send them on")], rate=rate)
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
        if not home:
            return
        p = r.choice(home)
        p["sick_until"] = c["hour"] + r.randint(30, 60)
        _hurt(p, 15)
        _letter(c, "bad", f"{p['name']} has fallen ill", "They will rest for a day or two. A pill speeds it up.")
    elif kind == "weevils":
        lost = c["res"]["rice"] * 0.15
        c["res"]["rice"] -= lost
        _letter(c, "bad", "Weevils in the granary", f"{int(lost)} rice had to be thrown out.")
    elif kind == "cold":
        burn = min(c["res"]["wood"], 6.0 * len(c["pawns"]))
        c["res"]["wood"] -= burn
        short = burn < 6.0 * len(c["pawns"])
        for p in c["pawns"]:
            if short and "Ascetic" not in p["traits"]:
                _think(p, "cold", "Shivered through a cold snap", -8, 48, c["hour"])
        _letter(c, "bad" if short else "info", "A cold snap", f"The sect burned {int(burn)} wood to keep warm."
                + (" It was not enough." if short else ""))
    elif kind == "young_master":
        # The same young master stopping the same disciple again reads as a loop: the next one comes from another unfriendly
        # sect when there is one, picks on someone he has not met, and says something new.
        last = fl["ym"] if isinstance(fl.get("ym"), dict) else {}
        met = [str(x) for x in last.get("pawns", [])][-3:] if isinstance(last.get("pawns"), list) else []
        sects = [s for s in c["sects"] if s["rel"] < 20 and s["id"] != last.get("src")] or [rival]
        rival = min(sects, key=lambda s: s["rel"])
        p = r.choice([o for o in others if o["id"] not in met] or others)
        fl["ym"] = {"src": rival["id"], "pawns": met + [p["id"]], "n": int(last.get("n", 0)) + 1 if isinstance(last.get("n"), int) else 1}
        taunt = lore.YOUNG_TAUNTS[int(fl["ym"]["n"] - 1) % len(lore.YOUNG_TAUNTS)].format(realm=realm_label(p["step"]).split(" · ")[0])
        _ask(c, "young_master", "A young master blocks the road",
             f"{rival['young']}, young master of the {rival['name']}, has stopped {p['name']} on the mountain path with a dozen lackeys. "
             + taunt,
             [("slap", f"Have {p['name']} teach him a lesson (strength {int(duel_power(c, p))} against about {int(young_master_foe(c, rival))}: "
                       f"{win_odds(duel_power(c, p), young_master_foe(c, rival), 0.7, 1.3)}% to win)"),
              ("endure", "Swallow the insult and walk away")]
             + ([("pay", "Smooth it over with 8 spirit stones")] if c["res"]["stones"] >= 8 else []),
             pawn=p["id"], src=rival["id"])
    elif kind == "auction":
        lots = []
        mids = [k for k, m in lore.MANUALS.items() if k not in c["manuals"] and not m.get("demonic") and m["grade"] <= min(3, _max_grade(c) + 1)]
        if mids:
            mid = r.choice(mids)
            lots.append({"what": "manual", "id": mid, "price": (15, 30, 55, 90)[lore.MANUALS[mid]["grade"]], "label": _manual_name(mid)})
        tids = [k for k in lore.TREASURES if k not in c["treasures"]]
        if tids:
            tid = r.choice(tids)
            lots.append({"what": "treasure", "id": tid, "price": 40, "label": f"{lore.TREASURES[tid]['name']}: {lore.TREASURES[tid]['text']}"})
        lots.append({"what": "pills", "id": "", "price": 12, "label": "A jade bottle of 3 pills"})
        if not c["beast"]:
            lots.append({"what": "egg", "id": "", "price": 25, "label": "A warm spirit-beast egg"})
        _ask(c, "auction", "The Golden Pavilion auction",
             "An auction house in the valley town has sent an invitation in gold leaf. Rival bidders glare from the private boxes. You can win one lot.",
             [(f"lot{i}", f"{lot['label']} — {lot['price']} spirit stones") for i, lot in enumerate(lots)] + [("decline", "Bid on nothing")], lots=lots)
    elif kind == "secret_realm":
        _ask(c, "secret_realm", "A secret realm opens",
             "Light pours from a tear in the sky above the Misty Marsh: the Azure Emperor's secret realm, open for two days once in sixty years. "
             "Every sect is sending disciples in. There are manuals, herbs and treasures inside, and rivals with drawn swords.",
             [("send3", "Send the three strongest disciples"), ("send1", "Send only the strongest"), ("decline", "Keep everyone home")])
    elif kind == "fallen_genius":
        fl["genius"] = 1
        cand = _make_pawn(c, c["next_pawn"])
        c["next_pawn"] += 1
        cand.update(root="Crippled", root_mult=0.6, hidden=True, age=r.randint(15, 17),
                    origin="Once the pride of a great clan; crippled, his engagement annulled, cast out.")
        _ask(c, "wanderer", "A fallen genius at the gate",
             f"{cand['name']}, {cand['age']}, was the pride of a great clan until his meridians were crippled three years ago. "
             "His engagement was annulled in front of the whole clan and he was cast out. He wears a plain black ring and has nowhere to go. "
             "He would be a mouth to feed, and he will gather qi slowly.",
             [("accept", "Give him a place"), ("decline", "Turn him away")], cand=cand)
    elif kind == "beast_cub":
        name = r.choice(lore.BEASTS)
        _ask(c, "beast_cub", "A wounded spirit beast",
             f"Foragers found a {name} with an arrow in its flank, too weak to run. Raised in the sect it would guard the gate one day. It will eat a little rice.",
             [("adopt", "Nurse it and raise it (10 rice)"), ("sell", "Sell it to a beast tamer (8 spirit stones)"), ("decline", "Leave it be")], beast=name)
    elif kind == "demonic_offer":
        _ask(c, "demonic_offer", "A stranger in a black cloak",
             "He leaves no footprints in the snow. “Your disciples crawl where they could fly. This sutra asks only a little blood, "
             "and never the reader's own.” He holds out a manual bound in something that is not leather. Any rank can practise it, "
             "it gathers qi faster than anything you own, and it darkens the heart. The righteous sects will hear of it.",
             [("accept", "Take the Blood Sutra"), ("refuse", "Refuse and send him away"), ("fight", "Drive the demon out")])
    elif kind == "cave":
        p = max(others, key=lambda x: x["skills"]["scholar"]["lv"])
        _ask(c, "cave", "A sealed cave abode",
             f"A quarry wall fell away onto a stone door carved with a dead immortal's seal. Beyond it, by the old stories, is an inheritance "
             f"and the trial that guards it. {p['name']} reads the seal script best (scholarship {p['skills']['scholar']['lv']}).",
             [("enter", f"Send {p['name']} to take the trial"), ("decline", "Seal it up again")], pawn=p["id"])
    elif kind == "engagement":
        fl["engagement"] = 1
        p = r.choice(others)
        s = r.choice(c["sects"])
        _ask(c, "engagement", "An engagement is annulled",
             f"A lady of the {s['name']} has come with her elders to break her childhood engagement to {p['name']}, in front of the whole sect. "
             "“We walk different roads now. Take these spirit stones for your trouble.” "
             f"{p['name']}'s knuckles are white.",
             [("pact", f"“Twelve days from now, I will come to your sect.” (a pact to duel: {p['name']} {int(duel_power(c, p))} today, "
                       f"their champion about {int(pact_foe(c, s, 12))} by then)"), ("stones", "Take the 15 spirit stones")],
             pawn=p["id"], src=s["id"])
    elif kind == "spy":
        p = r.choice(others)
        _ask(c, "spy", "A spy in the sect",
             f"{p['name']} was caught passing notes on the ward formation to the {rival['name']}. They kneel in the Main Hall and say their family is held hostage.",
             [("banish", "Cast them out"), ("forgive", "Forgive them"), ("turn", "Send false notes back through them")], pawn=p["id"], src=rival["id"])
    elif kind == "village":
        p = _strongest(c, 1)
        if not p:
            return
        _ask(c, "village", "The village below begs for help",
             f"A demon boar has been tearing up the fields of Willow Village. The headman kneels at the gate. {p[0]['name']} could deal with it in a day.",
             [("send", f"Send {p[0]['name']}"), ("decline", "The sect does not meddle with mortals")], pawn=p[0]["id"])
    elif kind == "cliff":
        p = r.choice(others)
        p["away_until"], p["away_kind"] = c["hour"] + r.randint(36, 72), "missing"
        c["later"].append({"at": p["away_until"], "kind": "cliff_return", "pawn": p["id"]})
        _letter(c, "bad", f"{p['name']} fell from a cliff", "A ledge gave way while they were gathering herbs. The others searched until dark and found nothing but mist.")
    elif kind == "epiphany":
        if not home:
            return
        p = r.choice(home)
        _gain_qi(c, p, step_need(p["step"]) * 0.3)
        p["inspired_until"] = c["hour"] + 24
        _letter(c, "good", f"{p['name']} had an epiphany", "Watching a leaf fall into the pond, they sat down and did not move for a day. Their qi surged.")
    elif kind == "furnace":
        if r.random() < 0.5:
            _add(c, "pills", 2)
            _letter(c, "good", "A pill with pill-lines", "The furnace sang at midnight. Two flawless pills came out of an ordinary batch.")
        else:
            c["res"]["herbs"] = max(0.0, c["res"]["herbs"] - 3)
            brewer = max(home, key=lambda x: x["skills"]["craft"]["lv"]) if home else None
            if brewer:
                _hurt(brewer, 10, c)
            _letter(c, "bad", "The pill furnace exploded", f"{brewer['name'] if brewer else 'Someone'} is singed, and three herbs are ash.")
    else:
        _omen(c, r, kind, rival if kind == "raid" and rival and rival["rel"] < 20 else None)


# ---------------------------------------------------------------------------
# answering an event
# ---------------------------------------------------------------------------
def win_odds(me: float, foe: float, lo: float, hi: float) -> int:
    """Percent chance that `me` beats `foe` drawn uniformly between foe*lo and foe*hi: the roll the resolvers make."""
    if foe <= 0:
        return 100
    return _f(100 * max(0.0, min(1.0, (me / foe - lo) / (hi - lo))))


TOURNEY_ROLL = (0.75, 1.25)          # a champion fights between these times their strength: a good day, or a bad one


def tournament_cap(c: dict) -> int:
    """The highest stage allowed in round one of this year's tournament (each later round allows one more). It is a contest
    of the young generation: the bracket opens at early Qi Condensation in the first year and widens two stages a year, and never sits
    more than one stage below the sect's own best disciple, so a careful sect always meets its own generation."""
    year = _day(c) // YEAR + 1
    ours = max((int(p["step"]) for p in c["pawns"] if not p.get("master")), default=0)
    return max(4 + 2 * (year - 1), ours - 1)


def tournament_field(c: dict) -> list[tuple[dict, dict, float]]:
    """(sect, entrant, strength before the roll), in the order the rounds are fought. A sect sends its strongest
    champion inside the bracket; if both of its champions are past it, a junior at the bracket's limit."""
    out = []
    for i, s in enumerate(sorted(c["sects"], key=lambda x: x["power"])):
        cap = tournament_cap(c) + i
        dao.road.champion(c, s)                           # makes the sect's champions on first sight
        fits = [ch for ch in s["champs"] if int(ch["step"]) <= cap]
        if fits:
            ch = max(fits, key=lambda x: x["step"])
        else:
            r = _rng(c, "junior", s["id"], _day(c) // YEAR)
            ch = {"name": f"{r.choice(SURNAMES)} {r.choice(GIVEN)}", "step": cap, "role": "junior disciple"}
        out.append((s, ch, dao.road.champ_power(ch)))
    return out


def tournament_odds(c: dict, p: dict) -> str:
    me = duel_power(c, p)
    each = [win_odds(me, fp, *TOURNEY_ROLL) / 100.0 for _, _, fp in tournament_field(c)]
    first = _f(100 * each[0]) if each else 100
    return f"strength {int(me)}: {first}% to win round one, {_f(100 * math.prod(each))}% to win every round"


def young_master_foe(c: dict, s: dict) -> float:
    """The young master's strength before the roll (it varies 0.7 to 1.3 times this)."""
    return (14 + _day(c) * 0.7) * s["power"]


def pact_foe(c: dict, s: dict | None, days_ahead: int = 0) -> float:
    """The pact duel's opponent before the roll (it varies 0.8 to 1.2 times this), `days_ahead` days from now."""
    return (16 + (_day(c) + days_ahead) * 0.65) * (float(s["power"]) if s else 1.0)


def _res_pact_duel(c, ev, opt, r):
    p, s = _p(c, ev.get("pawn", "")), _sect(c, ev.get("src", ""))
    if not p:
        return None
    where = f"the {s['name']}" if s else "the rival sect"
    if opt == "forfeit":
        _fame(c, -3)
        _think(p, "pact", "Withdrew from the pact duel", -10, 96, c["hour"])
        return _letter(c, "bad", f"{p['name']} withdrew from the pact", f"Word went down to {where}. The laughter came back up the mountain.")
    if p["away_until"] > c["hour"]:
        return ("err", f"{p['name']} is away from the sect.")
    snap = _snap(c)
    me, base = duel_power(c, p), pact_foe(c, s)
    foe = base * r.uniform(0.8, 1.2)
    ok = me >= foe
    line = (p["name"], f"strength {int(me)} against {int(foe)} ({win_odds(me, base, 0.8, 1.2)}% before the duel)", ok)
    if ok:
        _fame(c, 8)
        _think(p, "pact", "Kept the pact and won", 15, 120, c["hour"])
        p["title"] = p.get("title") or "the Unbowed"
        out = _letter(c, "good", f"{p['name']} won the pact duel",
                      f"On {where}'s own arena, before all its elders. “The engagement? I annul it.” Nobody in the stands breathes.")
    else:
        _hurt(p, 20, c)
        p["health"] = max(p["health"], 5.0)
        _think(p, "pact", "Lost the pact duel", -8, 72, c["hour"])
        out = _letter(c, "bad", f"{p['name']} lost the pact duel", "They bowed, and walked home alone. There is always a higher mountain.")
    _scene(c, "tournament", ok, out["title"], out["text"], verdict="The pact is kept" if ok else "Defeated in the duel", party=[p],
           lines=[line] + ([(p["name"], f"known now as {p['title']}", True)] if ok and p.get("title") else []), snap=snap)
    return out


def duel_power(c: dict, p: dict) -> float:
    return (10 + 4 * p["skills"]["combat"]["lv"]) * (1 + 0.07 * p["step"]) * (1 + _manual(c, p, "sword")[0]) * (1 + _art(c, p, "sword")) * max(0.3, p["health"] / 100.0)


def _res_wanderer(c, ev, opt, r):
    if opt != "accept":
        return None
    if len(c["pawns"]) >= pawn_cap(c):
        return ("err", "The sect is full. Raise the Main Hall to take in more, or turn them away.")
    p = ev["cand"]
    p["joined"] = c["hour"]
    c["pawns"].append(p)
    if p.get("hidden"):
        c["later"].append({"at": c["hour"] + 24 * r.randint(8, 14), "kind": "ring", "pawn": p["id"]})
    _annal(c, f"{p['name']} joined the sect. {p.get('origin', '')}")
    return _letter(c, "good", f"{p['name']} joined the sect", "Set their work priorities in Work.")


def _res_recruit(c, ev, opt, r):
    if not opt.startswith("pick"):
        return None
    if len(c["pawns"]) >= pawn_cap(c):
        return ("err", "The sect is full. Raise the Main Hall to take in more.")
    p = ev["cands"][int(opt[4:])]
    p["joined"] = c["hour"]
    c["pawns"].append(p)
    _annal(c, f"{p['name']} passed the entrance trial. {p.get('origin', '')}")
    return _letter(c, "good", f"{p['name']} passed the entrance trial", "A new outer disciple bows to the Sect Master.")


def _res_merchant(c, ev, opt, r):
    rate = float(ev.get("rate", 1.0))
    trades = {"sell_rice": ("rice", -25, int(6 * rate)), "sell_herbs": ("herbs", -8, int(7 * rate)), "sell_pills": ("pills", -2, int(8 * rate)),
              "buy_rice": ("rice", 30, -6), "buy_wood": ("wood", 40, -6), "buy_pills": ("pills", 2, -10)}
    if opt not in trades:
        return None
    what, qty, stones = trades[opt]
    res = c["res"]
    if res[what] + qty < 0 or res["stones"] + stones < 0:
        return ("err", "You no longer have enough for that trade.")
    res[what] += qty
    res["stones"] += stones
    return _letter(c, "info", "A trade was struck", next(o["label"] for o in ev["options"] if o["id"] == opt) + ".")


def _res_omen(c, ev, opt, r):
    return _threat(c, r, ev["threat"], float(ev["strength"]), opt, _sect(c, ev.get("src", "")))


def _res_young_master(c, ev, opt, r):
    p, s = _p(c, ev["pawn"]), _sect(c, ev["src"])
    if not p or not s:
        return None
    if opt == "pay":
        if c["res"]["stones"] < 8:
            return ("err", "You do not have 8 spirit stones.")
        c["res"]["stones"] -= 8
        _rel(s, 8)
        _fame(c, -1)
        return _letter(c, "info", "The matter was smoothed over", f"{s['young']} weighs the pouch, sneers and lets {p['name']} pass.")
    if opt == "endure":
        _think(p, "insult", "Swallowed an insult", -10, 48, c["hour"])
        _xp(p, "combat", 25)
        _rel(s, 3)
        return _letter(c, "info", f"{p['name']} walked away", "They said nothing, and trained until dawn. A gentleman's revenge can wait ten years.")
    foe = young_master_foe(c, s) * r.uniform(0.7, 1.3)
    if duel_power(c, p) >= foe:
        _think(p, "slap", "Slapped a young master's face", 12, 72, c["hour"])
        for o in c["pawns"]:
            if o is not p:
                _think(o, "slap_seen", "Saw an arrogant young master humbled", 4, 48, c["hour"])
        _fame(c, 5)
        _rel(s, -20)
        if not p.get("title"):
            p["title"] = r.choice(lore.EPITHETS)
        c["later"].append({"at": c["hour"] + 24 * r.randint(3, 5), "kind": "elder", "src": s["id"]})
        return _letter(c, "good", f"{p['name']} slapped {s['young']}'s face",
                       "One palm, and the young master spun three times before he hit the ground. His lackeys carried him off shouting "
                       "“You will regret this! My father will not let this go!” Beat the young, and the old will come.")
    _hurt(p, 30, c)
    _think(p, "beaten", "Beaten in front of everyone", -10, 48, c["hour"])
    _rel(s, -5)
    _fame(c, -2)
    return _letter(c, "bad", f"{p['name']} was beaten by {s['young']}",
                   "The young master had a protective treasure from his father. “Courting death!” Train harder before picking the next fight.")


def _res_auction(c, ev, opt, r):
    if not opt.startswith("lot"):
        return None
    lot = ev["lots"][int(opt[3:])]
    if c["res"]["stones"] < lot["price"]:
        return ("err", "You do not have the spirit stones for that lot.")
    c["res"]["stones"] -= lot["price"]
    if lot["what"] == "manual" and lot["id"] in lore.MANUALS and lot["id"] not in c["manuals"]:
        c["manuals"].append(lot["id"])
    elif lot["what"] == "treasure" and lot["id"] in lore.TREASURES and lot["id"] not in c["treasures"]:
        c["treasures"].append(lot["id"])
    elif lot["what"] == "pills":
        _add(c, "pills", 3)
    elif lot["what"] == "egg":
        c["beast"] = {"name": r.choice(lore.BEASTS), "born": c["hour"]}
    return _letter(c, "good", "The hammer falls", f"Sold to the {c['name']}: {lot['label'].rstrip('.')}. A rival bidder crushes his teacup.")


def _res_secret_realm(c, ev, opt, r):
    if opt == "decline":
        return None
    team = _strongest(c, 3 if opt == "send3" else 1)
    if not team:
        return ("err", "No disciple is fit to go.")
    back = c["hour"] + 48
    for p in team:
        p["away_until"], p["away_kind"] = back, "in the secret realm"
    c["later"].append({"at": back, "kind": "realm_return", "pawns": [p["id"] for p in team]})
    return _letter(c, "info", "Into the secret realm", f"{', '.join(p['name'] for p in team)} stepped through the tear in the sky. They will be gone two days.")


def _res_beast_cub(c, ev, opt, r):
    if opt == "adopt":
        if c["res"]["rice"] < 10:
            return ("err", "You do not have 10 rice to spare.")
        c["res"]["rice"] -= 10
        c["beast"] = {"name": str(ev["beast"]), "born": c["hour"]}
        for p in c["pawns"]:
            _think(p, "cub", "The sect has a spirit beast", 5, 72, c["hour"])
        return _letter(c, "good", f"The {ev['beast']} stays", "It sleeps by the kitchen fire and growls at strangers. It will grow.")
    if opt == "sell":
        _add(c, "stones", 8)
        return _letter(c, "info", "The beast was sold", "A tamer from Hundred Beasts Mountain paid 8 spirit stones.")
    return None


def _res_demonic_offer(c, ev, opt, r):
    if opt == "accept":
        c["manuals"].append("blood_sutra")
        for s in c["sects"]:
            _rel(s, -15 if s["kind"] == "righteous" else 10 if s["kind"] == "demonic" else -5)
        return _letter(c, "bad", "The Blood Sutra is in the pavilion",
                       "Every disciple gathers qi far faster, and sleeps worse. You can burn it from the World tab.")
    if opt == "fight":
        _fame(c, 2)
        for s in c["sects"]:
            _rel(s, 4 if s["kind"] == "righteous" else -8 if s["kind"] == "demonic" else 0)
        return _letter(c, "good", "The demon was driven out", "He laughed as the wards flared, and was gone. The righteous sects approve.")
    return None


def _res_cave(c, ev, opt, r):
    p = _p(c, ev["pawn"])
    if opt != "enter" or not p:
        return None
    if r.random() < 0.4 + 0.03 * p["skills"]["scholar"]["lv"]:
        mid = _loot_manual(c, r, min(3, _max_grade(c) + 1))
        _gain_qi(c, p, step_need(p["step"]) * 0.5)
        _xp(p, "scholar", 40)
        _think(p, "inherit", "Received an immortal's inheritance", 12, 96, c["hour"])
        return _letter(c, "good", f"{p['name']} passed the trial",
                       "A remnant soul looked them over for a long time. “You will do.” "
                       + (f"They came out with the {_manual_name(mid)}." if mid else "They came out with a surge of qi."))
    _hurt(p, 25, c)
    _add(c, "stones", 4)
    return _letter(c, "bad", f"{p['name']} failed the trial", "The puppet guardians threw them out with four spirit stones clutched in one fist.")


def _res_engagement(c, ev, opt, r):
    p, s = _p(c, ev["pawn"]), _sect(c, ev["src"])
    if not p:
        return None
    if opt == "stones":
        _add(c, "stones", 15)
        _think(p, "annulled", "Sold their pride for spirit stones", -8, 72, c["hour"])
        return _letter(c, "info", "The stones were taken", f"{p['name']} does not come out of their room that night.")
    p["resolve_until"] = c["hour"] + 24 * 12
    c["later"].append({"at": c["hour"] + 24 * 12, "kind": "pact_duel", "pawn": p["id"], "src": s["id"] if s else ""})
    return _letter(c, "good", f"{p['name']} made a pact to duel",
                   "“Do not bully the young for being poor.” For the next twelve days they gather qi half again as fast. Then the duel.")


def _res_spy(c, ev, opt, r):
    p, s = _p(c, ev["pawn"]), _sect(c, ev["src"])
    if not p:
        return None
    if opt == "banish":
        c["pawns"].remove(p)
        _rel(s, -5)
        return _letter(c, "info", f"{p['name']} was cast out", "The gate closed behind them.")
    if opt == "forgive":
        _think(p, "mercy", "Was shown mercy", 12, 120, c["hour"])
        for sk in SKILLS:
            _xp(p, sk, 10)
        return _letter(c, "good", f"{p['name']} was forgiven", "They work like someone with a debt to repay.")
    c["adapt"] = max(0.55, c["adapt"] - 0.15)
    _think(p, "double", "Living a double life", -6, 96, c["hour"])
    return _letter(c, "good", "False notes were sent", f"The {s['name'] if s else 'enemy'} now has a very wrong map of the wards. Their next raid will be weaker.")


def _res_village(c, ev, opt, r):
    p = _p(c, ev["pawn"])
    if opt != "send" or not p:
        _fame(c, -2)
        return _letter(c, "info", "The headman was sent away", "Word gets around the villages.")
    p["away_until"], p["away_kind"] = c["hour"] + 24, "hunting a demon boar"
    c["later"].append({"at": p["away_until"], "kind": "village_return", "pawn": p["id"]})
    return _letter(c, "info", f"{p['name']} went down the mountain", "They will be back tomorrow.")


def _res_tournament(c, ev, opt, r):
    p = _p(c, opt)
    p_name = p["name"] if p else ""
    if opt == "observe":
        w = _p(c, ev.get("watcher", "")) or (_others(c) or _home(c) or c["pawns"])[0]
        _xp(w, "combat", 40)
        _fame(c, 1)
        _think(w, "tourney", "Watched the champions fight", 4, 48, c["hour"])
        return _letter(c, "info", f"{w['name']} watched the tournament",
                       "From the stands, every form of every champion. They came home quiet and went straight to the training ground.")
    if not p:
        for o in c["pawns"]:
            _think(o, "no_tourney", "The sect skipped the tournament", -3, 48, c["hour"])
        return None
    wins, lines, rounds = 0, [], []
    snap = _snap(c)
    me = duel_power(c, p)
    for i, (s, champ, fp) in enumerate(tournament_field(c)):
        foe = fp * r.uniform(*TOURNEY_ROLL)                  # the same roll tournament_odds prices
        if me >= foe:
            wins += 1
            _rel(s, -3)
            lines.append(f"beat {champ['name']} of the {s['name']} ({realm_label(int(champ['step'])).split(' · ')[0]})")
            rounds.append((f"Round {i + 1}", f"{lines[-1]}: {int(me)} against {int(foe)}", True))
        else:
            lines.append(f"fell to {champ['name']} of the {s['name']} ({realm_label(int(champ['step'])).split(' · ')[0]})")
            rounds.append((f"Round {i + 1}", f"{lines[-1]}: {int(me)} against {int(foe)}", False))
            _hurt(p, 15, c)
            break
    _fame(c, 4 * wins)
    _xp(p, "combat", 30 + 20 * wins)
    prize = ""
    if wins:
        _add(c, "stones", 8 * wins)
        prize = f" Prize: {8 * wins} spirit stones"
    if wins == len(c["sects"]):
        mid = _loot_manual(c, r, min(3, _max_grade(c) + 1))
        prize += f" and the {_manual_name(mid)}" if mid else ""
        p["title"] = "Tournament Champion"
        prize += f", and the {_new_artifact(c, r, f'won by {p_name} at the Hundred Sects Tournament', quality=1)['name']}"
    for o in c["pawns"]:
        _think(o, "tourney", "Our champion won the tournament" if wins == len(c["sects"]) else "Our champion fought in the tournament",
               10 if wins == len(c["sects"]) else 2 + 2 * wins, 72, c["hour"])
    ev = _letter(c, "good" if wins else "info", f"{p['name']} at the Hundred Sects Tournament",
                 f"{p['name']} {', then '.join(lines)}.{prize}{'.' if prize else ''}")
    champion = wins == len(c["sects"])
    _scene(c, "tournament", wins > 0, ev["title"], f"{p['name']} carried the banner of the {c['name']} into the ring against the champions of {len(c['sects'])} sects.",
           verdict="Champion" if champion else f"{wins} of {len(c['sects'])} rounds won" if wins else "Out in the first round",
           party=[p], lines=rounds + ([("", prize.strip() + ".", True)] if prize else []), snap=snap)
    return ev


_RESOLVERS = {"wanderer": _res_wanderer, "recruit": _res_recruit, "merchant": _res_merchant, "omen": _res_omen,
              "young_master": _res_young_master, "auction": _res_auction, "secret_realm": _res_secret_realm,
              "beast_cub": _res_beast_cub, "demonic_offer": _res_demonic_offer, "cave": _res_cave, "engagement": _res_engagement,
              "spy": _res_spy, "village": _res_village, "tournament": _res_tournament, "pact_duel": _res_pact_duel}


def resolve(st: dict, option: str, now: float) -> dict:
    c = _c(st, now)
    ev = c["pending"]
    if not ev:
        return {"ok": False, "error": "Nothing is waiting for a decision."}
    if option not in {o["id"] for o in ev["options"]}:
        return {"ok": False, "error": "That is not one of the choices."}
    c["pending"] = None
    saved = copy.deepcopy([(p["id"], p["thoughts"]) for p in c["pawns"]]), dict(c["bonds"]), copy.deepcopy(c["siege"])
    dao.before_choice(c, ev, option)
    fn = _RESOLVERS.get(ev["kind"])
    out = fn(c, ev, option, _rng(c, "res", ev["kind"], c["hour"])) if fn else None
    if isinstance(out, tuple):
        c["pending"] = ev
        for pid, th in saved[0]:                      # the choice did not happen: nobody reacts to it
            q = _p(c, pid)
            if q:
                q["thoughts"] = th
        c["bonds"], c["siege"] = saved[1], saved[2]
        return {"ok": False, "error": out[1]}
    return {"ok": True, "event": out} if out else {"ok": True}


def _later(c: dict, item: dict) -> bool:
    """A consequence that was set in motion earlier comes due. False = try again later."""
    r = _rng(c, "later", item["kind"], c["hour"])
    kind = item["kind"]
    if kind in dao.LATER:
        return dao.later(c, item, r)
    if kind == "elder":
        s = _sect(c, item.get("src", ""))
        if c["pending"]:
            return False
        if s:
            _omen(c, r, "raid", s, boost=1.25, why=f"An elder of the {s['name']} has come to avenge {s['young']}'s face.")
    elif kind == "realm_return":
        team = [p for p in (_p(c, i) for i in item.get("pawns", [])) if p]
        if not team:
            return True
        snap = _snap(c)
        power = sum(duel_power(c, p) for p in team)
        need = (30 + _day(c) * 1.2) * r.uniform(0.7, 1.3)
        luck = power / max(need, 1.0)
        found = []
        n = r.randint(6, 14) * len(team)
        _add(c, "stones", n * min(1.5, luck))
        found.append(f"{int(n * min(1.5, luck))} spirit stones")
        herbs = r.randint(5, 10) * len(team)
        _add(c, "herbs", herbs)
        found.append(f"{herbs} spirit herbs")
        if r.random() < 0.35 * luck:
            mid = _loot_manual(c, r)
            if mid:
                found.append(f"the {_manual_name(mid)}")
        if r.random() < 0.15 * luck:
            tid = _loot_treasure(c, r)
            if tid:
                found.append(f"the {lore.TREASURES[tid]['name']}")
        hurt = []
        for i, a in enumerate(team):
            for b in team[i + 1:]:
                _bond(c, a, b, 8)
        for p in team:
            _xp(p, "combat", 30)
            _gain_qi(c, p, step_need(p["step"]) * 0.2)
            if r.random() < max(0.1, 0.7 - 0.4 * luck):
                _hurt(p, r.randint(15, 40), c)
                p["health"] = max(p["health"], 8.0)
                hurt.append(p["name"])
        _fame(c, 2 if luck >= 1 else 0)
        ev = _letter(c, "good" if not hurt else "info", "The disciples return from the secret realm",
                     f"They brought back {', '.join(found)}." + (f" {' and '.join(hurt)} crossed swords with rival disciples and came back wounded." if hurt else ""))
        _scene(c, "realm", not hurt, ev["title"], ev["text"], verdict="Back unharmed" if not hurt else "Back, bloodied", party=team,
               lines=[("", f"Brought back {', '.join(found)}.", True), ("", "Each gathered a fifth of a stage of qi, and they grew closer (+8 bond)", True)],
               snap=snap)
    elif kind == "trip_return":
        _trip_return(c, item, r)
    elif kind == "plague_tick":
        _plague_tick(c, item, r)
    elif kind == "cliff_return":
        p = _p(c, item.get("pawn", ""))
        if p:
            _gain_qi(c, p, step_need(p["step"]) * 0.6)
            _think(p, "fortune", "Survived a fall and found a fortune", 10, 96, c["hour"])
            _add(c, "herbs", 8)
            _letter(c, "good", f"{p['name']} walked back through the gate",
                    "At the foot of the cliff was a cave, and in the cave a skeleton sitting in meditation, with a spirit fruit growing from its lap. "
                    "They ate the fruit. Those who survive a great disaster are bound for good fortune.")
    elif kind == "ring":
        p = _p(c, item.get("pawn", ""))
        if p and p.get("hidden"):
            p.update(hidden=False, root="Heaven-Defying", root_mult=2.3)
            _think(p, "ring", "An old voice in the ring is teaching him", 12, 240, c["hour"])
            _letter(c, "good", f"The ring on {p['name']}'s finger woke",
                    f"“Little fellow, you have fed this old man's soul for long enough. Your meridians were never crippled, they were sealed.” "
                    f"{lore.RING_LINES[0]} {p['name']} now has a Heaven-Defying spirit root.")
    elif kind == "pact_duel":
        p, s = _p(c, item.get("pawn", "")), _sect(c, item.get("src", ""))
        if p:
            if c["pending"]:
                return False
            me, foe = duel_power(c, p), pact_foe(c, s)
            where = f"the {s['name']}" if s else "the rival sect"
            _ask(c, "pact_duel", "The day of the pact duel",
                 f"Twelve days are up. {p['name']} stands at the gate of {where} with the whole valley watching. "
                 f"Their champion's strength is about {int(foe)}; {p['name']}'s is {int(me)}.",
                 [("fight", f"Keep the pact (strength {int(me)} against about {int(foe)}: {win_odds(me, foe, 0.8, 1.2)}% to win; a loss is a wound)"),
                  ("forfeit", "Send word that the pact is withdrawn (no wound, but the valley will laugh)")],
                 pawn=p["id"], src=s["id"] if s else "")
    elif kind == "village_return":
        p = _p(c, item.get("pawn", ""))
        if p:
            _xp(p, "combat", 25)
            _add(c, "rice", 20)
            _fame(c, 4)
            _think(p, "hero", "Thanked by a whole village", 8, 72, c["hour"])
            youth = ""
            if len(c["pawns"]) < pawn_cap(c):
                q = _make_pawn(c, c["next_pawn"])
                c["next_pawn"] += 1
                q.update(joined=c["hour"], origin="A farmer's child from Willow Village who watched the boar fall.")
                c["pawns"].append(q)
                _annal(c, f"{q['name']} came up from Willow Village to join the sect.")
                youth = f" {q['name']}, the headman's youngest, came with it and asked to stay: {q['root'].lower()} spirit root. Set their work in Work."
            else:
                youth = " A youth came up too, hoping to stay, but the sect has no room; the Main Hall must grow first."
            _letter(c, "good", f"{p['name']} slew the demon boar", "The villagers sent 20 rice up the mountain." + youth)
    return True


# ---------------------------------------------------------------------------
# bonds: disciples form opinions of each other, and those colour everything
# ---------------------------------------------------------------------------
def _bkey(a: str, b: str) -> str:
    return "|".join(sorted((str(a), str(b))))


def bond(c: dict, a: dict, b: dict) -> float:
    return float(c["bonds"].get(_bkey(a["id"], b["id"]), 0.0))


def bond_kind(v: float) -> str:
    return "sworn sibling" if v >= 70 else "friend" if v >= 30 else "rival" if v <= -30 else ""


RIVAL_AT, RIVAL_UNTIL = -30, -20    # a pair falls out at -30 and stays rivals until the bond climbs past -20


RIVAL_PER = 4                       # at most one rival pair for every this many disciples (and always room for one)
RIVAL_MEND = 1.0                    # a sour bond climbs this much a day on its own: grudges fade unless fed


def rival_cap(c: dict) -> int:
    return max(1, len(c["pawns"]) // RIVAL_PER)


def _mend_grudges(c: dict) -> None:
    """Once a day: every bond below zero eases a little toward it (old insults fade); a rivalry that eases past
    RIVAL_UNTIL ends with its own letter (_bond)."""
    ps = c["pawns"]
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            v = bond(c, a, b)
            if v < 0:
                _bond(c, a, b, min(RIVAL_MEND, -v))


def _rivals(c: dict) -> dict:
    r = c["flags"].get("rivals")
    if not isinstance(r, dict):
        r = c["flags"]["rivals"] = {}
    return r


def is_rival(c: dict, a: dict, b: dict) -> bool:
    """The one rule for rivalry: mood, envy, the disciple's page, Great Works and the chronicle all ask this.
    It has a margin so a pair hovering at -30 is not announced as rivals, then not, then rivals again."""
    v = bond(c, a, b)
    return a is not b and (v <= RIVAL_AT or (v <= RIVAL_UNTIL and _bkey(a["id"], b["id"]) in _rivals(c)))


def pair_kind(c: dict, a: dict, b: dict) -> str:
    return "rival" if is_rival(c, a, b) else "" if bond_kind(bond(c, a, b)) == "rival" else bond_kind(bond(c, a, b))


def _bond(c: dict, a: dict, b: dict, delta: float) -> None:
    if a is b:
        return
    k = _bkey(a["id"], b["id"])
    old = float(c["bonds"].get(k, 0.0))
    new = max(-100.0, min(100.0, old + delta))
    was_rival = is_rival(c, a, b)
    if not was_rival and new <= RIVAL_AT and len(rival_pairs(c)) >= rival_cap(c):
        new = RIVAL_AT + 1.0               # a sect has room for only so many feuds: this pair stays merely cool
    if was_rival:
        _rivals(c)[k] = 1
    c["bonds"][k] = new
    if new <= RIVAL_AT:
        _rivals(c)[k] = 1
    elif new > RIVAL_UNTIL:
        _rivals(c).pop(k, None)
    rival_now = is_rival(c, a, b)
    was, now_ = bond_kind(old), bond_kind(new)
    seen = c["flags"].setdefault("bonds_told", {})
    told = seen.get(k, "") if isinstance(seen.get(k, ""), str) else ""
    if rival_now != was_rival:
        if rival_now:
            _letter(c, "bad", f"{a['name']} and {b['name']} are now rivals", "They cannot stand each other. Each will resent the other's success, and try to outdo it.")
            if "rival" not in told.split(","):
                seen[k] = told = f"{told},rival".strip(",")
                _annal(c, f"{a['name']} and {b['name']} became rivals.")
        else:
            # A rivalry that ends is news too: otherwise the toast and the Great Works disagree with no word why.
            _letter(c, "info", f"{a['name']} and {b['name']} are no longer rivals", "Not friends, but they can share a room again.")
    if now_ and now_ != "rival" and now_ != was and now_ not in told.split(",") and not (was == "sworn sibling" and now_ == "friend"):
        seen[k] = f"{told},{now_}".strip(",")          # each turn in a friendship is announced once
        if now_ == "friend" and was != "sworn sibling":
            _letter(c, "good", f"{a['name']} and {b['name']} have become friends", "They look out for one another. Losing one would hit the other hard.")
        elif now_ == "sworn sibling":
            for x in (a, b):
                _think(x, "sworn", "Swore an oath of siblinghood", 10, 120, c["hour"])
            _letter(c, "good", f"{a['name']} and {b['name']} swore an oath in the peach garden",
                    "“We ask not to be born on the same day, but to die on the same day.” They are sworn siblings now.")
        _annal(c, f"{a['name']} and {b['name']} became {now_}s.")


def _friends(c: dict, p: dict, sign: int = 1) -> list[dict]:
    return [o for o in c["pawns"] if o is not p and (bond(c, p, o) >= 30 if sign > 0 else is_rival(c, p, o))]


def _socialise(c: dict, quiet: bool) -> None:
    """Disciples doing the same thing talk; talk builds friendships and, now and then, feuds."""
    groups: dict[str, list[dict]] = {}
    for p in _home(c):
        if p["doing"] not in ("sleeping", "recovering", "wandering in a daze"):
            groups.setdefault(p["doing"], []).append(p)
    r = _rng(c, "talk", c["hour"])
    for doing, ps in groups.items():
        if len(ps) < 2 or r.random() > 0.3:
            continue
        a, b = r.sample(ps, 2)
        cur = bond(c, a, b)
        roll = r.random()
        # Some pairs simply rub each other the wrong way; that is fixed for the pair.
        chem = _rng(c, "chem", _bkey(a["id"], b["id"])).uniform(-1, 1)
        temper = 2.0 if "Volatile" in a["traits"] or "Volatile" in b["traits"] else 0.6 if "Optimist" in a["traits"] else 1.0
        temper *= 2.6 if chem < -0.35 else 0.5 if chem > 0.35 else 1.0
        if roll < 0.05 * temper and not quiet:
            _bond(c, a, b, -10)
            _think(b, "insulted", f"Insulted by {a['name']}", -5, 48, c["hour"])
        elif roll < 0.05 * temper + 0.13 * temper * (1.4 if cur < 0 else 1.0):
            _bond(c, a, b, -4)
        elif roll < 0.6 and cur > 5 and chem > -0.35:
            _bond(c, a, b, 4)
        else:
            _bond(c, a, b, 1.0 if chem > -0.35 else 0.3)


def _annal(c: dict, text: str) -> None:
    c["annals"] = (c["annals"] + [{"hour": c["hour"], "text": text}])[-300:]


def renown(fame: float) -> str:
    return ("Nameless sect" if fame < 20 else "Known in the valley" if fame < 50 else "Regional power" if fame < 120
            else "Great Sect" if fame < 300 else "Holy Land")


# ---------------------------------------------------------------------------
# the guided opening: one goal at a time, each teaching one thing
# ---------------------------------------------------------------------------
GUIDE = [
    ("prio", "Open Work and change one disciple's priority. Set someone's Farm to 1 and they tend the fields before anything else.", lambda c: bool(c["flags"].get("prio"))),
    ("library", "Raise the Main Hall to level 2 (it needs three rooms first: build a Storehouse or a Ward Formation), then queue a Scripture Pavilion in Build. Builders raise them; disciples with Build as a priority help.", lambda c: _lvl(c, "library") > 0 or any(b["room"] == "library" for b in c["builds"])),
    ("research", "Choose something to research. Terraced irrigation pays for itself.", lambda c: bool(c["research"]["current"] or c["research"]["done"])),
    ("rice", "Store 70 rice. Nothing grows in winter, and everyone eats.", lambda c: c["res"]["rice"] >= 70),
    ("defend", "Build Training Grounds or a Ward Formation before something comes up the mountain.", lambda c: _lvl(c, "training") + _lvl(c, "ward") > 0),
    ("fight", "Drive off your first attacker.", lambda c: bool(c["flags"].get("first_win"))),
    ("pills", "Build an Alchemy Hall and hold two pills. Pills heal, and steady a breakthrough.", lambda c: _lvl(c, "alchemy") > 0 and c["res"]["pills"] >= 2),
    ("fourth", "Take in a fourth disciple.", lambda c: len(c["pawns"]) >= 4),
    ("realm", "Guide someone through a great-realm breakthrough. Open their page when they stand at the bottleneck.", lambda c: any(p["step"] >= 4 for p in c["pawns"])),
    ("friend", "Let two disciples become friends. Work them side by side and keep moods up.", lambda c: any(v >= 30 for v in c["bonds"].values())),
]


GUIDE_DONE = {"prio": "work set by priority", "library": "a Scripture Pavilion begun", "research": "research chosen",
              "rice": "a granary for winter", "defend": "the sect can defend itself", "fight": "the first attacker driven off",
              "pills": "pills in the stores", "fourth": "a fourth disciple", "realm": "a great realm crossed", "friend": "the first friendship"}


def _guide(c: dict) -> None:
    g = c["guide"]
    done = []
    while not g["skip"] and g["i"] < len(GUIDE) and GUIDE[g["i"]][2](c):
        done.append(GUIDE_DONE.get(GUIDE[g["i"]][0], "a lesson"))
        g["i"] += 1
    if not done:
        return
    n = len(done)
    _add(c, "stones", 3 * n)
    # One line per batch, named for what was learned, so the chronicle does not fill with the same nod.
    _letter(c, "good", f"The elder's lesson{'s' if n > 1 else ''}: {', '.join(done)}",
            f"He leaves {3 * n} spirit stones on the table ({g['i']} of {len(GUIDE)} lessons)."
            + (" “You no longer need me. The Great Works are yours to attempt.”" if g["i"] == len(GUIDE) else ""))


def _new_artifact(c: dict, r: random.Random, origin: str, quality: int | None = None, kind: str = "") -> dict:
    kind = kind if kind in lore.ARTIFACT_KINDS else r.choice(list(lore.ARTIFACT_KINDS))
    q = quality if quality is not None else r.choices([0, 1, 2], [60, 30, 10])[0]
    a = {"id": f"a{c['next_art']}", "name": f"{r.choice(lore.ARTIFACT_ADJ)} {r.choice(lore.ARTIFACT_NOUN[kind])}", "kind": kind, "q": int(q),
         "origin": f"{origin[:1].upper()}{origin[1:]}, day {_day(c) + 1}.", "owner": ""}
    c["next_art"] += 1
    c["artifacts"] = (c["artifacts"] + [a])[-40:]
    if q == 2:
        _annal(c, f"The masterwork {a['name']} came to the sect.")
    return a


def _unequip(c: dict, p: dict) -> None:
    for a in c["artifacts"]:
        if a["owner"] == p["id"]:
            a["owner"] = ""


def artifact_text(a: dict) -> str:
    what, tiers = lore.ARTIFACT_KINDS[a["kind"]]
    v = tiers[a["q"]]
    return f"{lore.ARTIFACT_QUALITY[a['q']]}. " + (f"+{v} points of {what}" if a["kind"] == "charm" else f"{'-' if a['kind'] == 'armour' else '+'}{int(round(v * 100))}% {what.replace(', reduced', '')}") + "."


FORGE_COST = {"stone": 40.0, "wood": 20.0, "stones": 8.0}


def forge(st: dict, now: float) -> dict:
    """The sect's best crafter makes an artifact. Skill decides how good it is."""
    c = _c(st, now)
    home = _home(c)
    if not _lvl(c, "alchemy"):
        return {"ok": False, "error": "The furnaces of an Alchemy Hall are needed to forge."}
    if not home:
        return {"ok": False, "error": "Nobody is home to work the forge."}
    if any(c["res"][k] < v for k, v in FORGE_COST.items()):
        return {"ok": False, "error": "Forging needs 40 stone, 20 wood and 8 spirit stones."}
    for k, v in FORGE_COST.items():
        c["res"][k] -= v
    smith = max(home, key=lambda x: x["skills"]["craft"]["lv"])
    r = _rng(c, "forge", c["hour"], c["next_art"])
    lv = smith["skills"]["craft"]["lv"]
    q = r.choices([0, 1, 2], [max(5, 70 - 4 * lv), 25 + 2 * lv, 2 + 2 * lv])[0]
    a = _new_artifact(c, r, f"forged by {smith['name']}", quality=q)
    _xp(smith, "craft", 40)
    if q == 2:
        _think(smith, "masterwork", "Forged a masterwork", 12, 120, c["hour"])
        smith["title"] = smith.get("title") or "the Artificer"
    return {"ok": True, "event": _letter(c, "good", f"{smith['name']} forged the {a['name']}", artifact_text(a) + " Give it to a disciple from their page.")}


def equip(st: dict, pawn_id: str, art_id: str, now: float) -> dict:
    """Give an artifact to a disciple (or take theirs back with an empty id). Rivals notice who is favoured."""
    c = _c(st, now)
    p = _p(c, pawn_id)
    if not p:
        return {"ok": False, "error": "Unknown disciple."}
    old = artifact_of(c, p)
    if not art_id:
        if old:
            old["owner"] = ""
        return {"ok": True}
    a = next((x for x in c["artifacts"] if x["id"] == art_id), None)
    if not a:
        return {"ok": False, "error": "That artifact is not in the vault."}
    prev = _p(c, a["owner"]) if a["owner"] else None
    if prev and prev is not p:
        _think(prev, "stripped", f"The {a['name']} was taken from them", -8, 72, c["hour"])
        _bond(c, prev, p, -10)
    if old and old is not a:
        old["owner"] = ""
    a["owner"] = p["id"]
    dao.on_equip(c, p, a)
    for o in _friends(c, p, -1):
        _think(o, "passed_over", f"Passed over for {p['name']}", -6, 48, c["hour"])
    return {"ok": True, "event": _letter(c, "info", f"{p['name']} received the {a['name']}", artifact_text(a))}


def direct_cap(c: dict) -> int:
    """One direct disciple for every three who still do the sect's work."""
    return sum(1 for p in c["pawns"] if not p.get("master")) // 4


def set_direct(st: dict, pawn_id: str, on: bool, now: float) -> dict:
    c = _c(st, now)
    p = _p(c, pawn_id)
    if not p or p.get("master"):
        return {"ok": False, "error": "Choose a disciple."}
    if on and not p.get("direct") and sum(1 for x in c["pawns"] if x.get("direct")) >= direct_cap(c):
        return {"ok": False, "error": "The sect can spare one direct disciple for every three who work. Take in more disciples first."}
    if bool(on) != bool(p.get("direct")):
        p["direct"] = bool(on)
        if on:
            for o in _friends(c, p, -1):
                _think(o, "passed_over", f"{p['name']} was chosen over them", -6, 72, c["hour"])
        else:
            _think(p, "demoted", "No longer a direct disciple", -8, 72, c["hour"])
    return {"ok": True}


def skip_guide(st: dict, now: float) -> dict:
    _c(st, now)["guide"]["skip"] = True
    return {"ok": True}


# ---------------------------------------------------------------------------
# Great Works: long goals with no deadline
# ---------------------------------------------------------------------------
def rival_pairs(c: dict) -> list[tuple[dict, dict]]:
    """Every pair of disciples who are rivals right now, by the same rule as the disciple's own page."""
    ps = c["pawns"]
    return [(a, b) for i, a in enumerate(ps) for b in ps[i + 1:] if is_rival(c, a, b)]


def _no_rivals_line(c: dict) -> tuple[str, bool]:
    pairs = rival_pairs(c)
    if not pairs:
        return ("No rivals within the walls", True)
    names = "; ".join(f"{a['name']} and {b['name']}" for a, b in pairs[:3]) + ("; and more" if len(pairs) > 3 else "")
    return (f"No rivals within the walls (still rivals: {names})", False)


def works(c: dict) -> list[dict]:
    m = _master(c)
    out = [
        {"id": "ascension", "name": "Ascension", "text": "The Sect Master steps beyond the mortal world.",
         "lines": [("The Sect Master reaches Immortal Ascension", bool(m) and m["step"] // 4 >= len(REALMS) - 1)]},
        {"id": "great", "name": "A Great Sect", "text": "A name spoken in every valley.",
         "lines": [("Main Hall at level 5", _lvl(c, "main_hall") >= 5), ("Nine disciples", len(c["pawns"]) >= 9),
                   ("Fame of 150", c["fame"] >= 150), ("An Elder besides yourself", any(rank_of(p) >= 3 and not p.get("master") for p in c["pawns"]))]},
        {"id": "peace", "name": "Peace Under Heaven", "text": "No sect in the region lifts a hand against you.",
         "lines": [(f"The {s['name']} is friendly (+15)", s["rel"] >= 15) for s in c["sects"]]},
        {"id": "canon", "name": "The Sect Canon", "text": "Everything worth knowing, under one roof.",
         "lines": [("All research complete", len(c["research"]["done"]) >= len(RESEARCH)), ("Ten manuals in the pavilion", len(c["manuals"]) >= 10),
                   ("A Heaven-grade manual", any(lore.MANUALS[k]["grade"] == 3 and not lore.MANUALS[k].get("demonic") for k in c["manuals"] if k in lore.MANUALS))]},
        {"id": "family", "name": "One Family", "text": "A sect is its people.",
         "lines": [("A pair of sworn siblings", any(v >= 70 for v in c["bonds"].values())), _no_rivals_line(c),
                   ("Six disciples or more", len(c["pawns"]) >= 6)]},
    ]
    for w in out:
        w["done"] = bool(w["lines"]) and all(ok for _, ok in w["lines"])
    return out


def _check_works(c: dict) -> None:
    for w in works(c):
        if w["done"] and not c["flags"].get("work_" + w["id"]):
            c["flags"]["work_" + w["id"]] = 1
            dao.poem(c, c["name"])
            _fame(c, 25)
            for p in c["pawns"]:
                _think(p, "work", f"The sect achieved {w['name']}", 12, 120, c["hour"])
            _letter(c, "good", f"A Great Work is complete: {w['name']}", w["text"] + " Every disciple will remember this day.")
            _annal(c, f"Great Work completed: {w['name']}.")


# ---------------------------------------------------------------------------
# quests: a request with a deadline and a reward you choose
# ---------------------------------------------------------------------------
QUESTS = {
    "rice":  ("Willow Village is starving", "The harvest failed in the valley. The headman asks for {n} rice within {d} days.", "rice"),
    "pills": ("Plague in the river towns", "A physician begs for {n} pills within {d} days. People are dying.", "pills"),
    "herbs": ("A request from the {sect}", "Their alchemists ask for {n} herbs within {d} days, sect to sect.", "herbs"),
    "wood":  ("The bridge is out", "Villagers ask for {n} wood within {d} days to rebuild the gorge bridge that brings you merchants.", "wood"),
}


def _offer_quest(c: dict, r: random.Random) -> None:
    kind = r.choice(_quests_open(c, _day(c)) or list(QUESTS))
    if not isinstance(c["flags"].get("quests"), dict):
        c["flags"]["quests"] = {}
    c["flags"]["quests"][kind] = _day(c)
    n ={"rice": r.choice([40, 50, 60]), "pills": r.choice([3, 4]), "herbs": r.choice([15, 20]), "wood": r.choice([60, 80])}[kind]
    days = r.randint(6, 9)
    s = r.choice(c["sects"]) if c["sects"] else None
    title, text, res = QUESTS[kind]
    _ask(c, "quest_offer", title.format(sect=s["name"] if s else "neighbours"),
         text.format(n=n, d=days, sect=s["name"] if s else "neighbours") + " You choose the reward when you deliver. Breaking a promise costs fame.",
         [("accept", "Give your word"), ("decline", "Decline")], quest={"kind": kind, "res": res, "n": n, "days": days, "src": s["id"] if s and kind == "herbs" else "",
                                                                         "title": title.format(sect=s["name"] if s else "neighbours")})


def _res_quest_offer(c, ev, opt, r):
    if opt != "accept":
        return None
    q = dict(ev["quest"])
    q["due"] = c["hour"] + 24 * int(q["days"])
    c["quest"] = q
    return _letter(c, "info", "A promise was made", f"{q['title']}: deliver {q['n']} {q['res']} within {q['days']} days. Deliver from the World tab.")


def deliver(st: dict, now: float) -> dict:
    c = _c(st, now)
    q = c["quest"]
    if not q:
        return {"ok": False, "error": "No promise is outstanding."}
    if c["pending"]:
        return {"ok": False, "error": "Answer what is waiting first."}
    if c["res"][q["res"]] < q["n"]:
        return {"ok": False, "error": f"You need {q['n']} {q['res']}."}
    c["res"][q["res"]] -= q["n"]
    c["quest"] = None
    opts = [("stones", f"{6 + q['n'] // (1 if q['res'] == 'pills' else 6)} spirit stones"), ("fame", "Their gratitude, told in every market (+8 fame)")]
    if len(c["pawns"]) < pawn_cap(c):
        opts.append(("recruit", "A promising youth they will vouch for"))
    else:
        opts.append(("manual", "An old manual from a family chest"))
    _ask(c, "quest_reward", "The promise is kept", "They ask how they can repay the sect.", opts, quest=q)
    return {"ok": True}


def _res_quest_reward(c, ev, opt, r):
    q = ev["quest"]
    _rel(_sect(c, q.get("src", "")), 12)
    for p in c["pawns"]:
        _think(p, "kept", "The sect kept its word", 4, 48, c["hour"])
    if opt == "stones":
        n = 6 + q["n"] // (1 if q["res"] == "pills" else 6)
        _add(c, "stones", n)
        return _letter(c, "good", "Repaid in spirit stones", f"{n} spirit stones, and thanks.")
    if opt == "fame":
        _fame(c, 8)
        return _letter(c, "good", "The sect's name travels", "Merchants tell the story in every market town.")
    if opt == "recruit" and len(c["pawns"]) < pawn_cap(c):
        p = _make_pawn(c, c["next_pawn"], lucky=True)
        c["next_pawn"] += 1
        p["joined"] = c["hour"]
        c["pawns"].append(p)
        _annal(c, f"{p['name']} joined, vouched for by grateful villagers.")
        return _letter(c, "good", f"{p['name']} joined the sect", f"{p['origin']} {p['root']} spirit root.")
    mid = _loot_manual(c, r)
    return _letter(c, "good", "A gift from a family chest", f"They gave you the {_manual_name(mid)}." if mid else "It turned out to be a cookbook. A good one.")


def _quest_tick(c: dict) -> None:
    q = c["quest"]
    if q and q["due"] <= c["hour"]:
        c["quest"] = None
        _fame(c, -5)
        _rel(_sect(c, q.get("src", "")), -10)
        for p in c["pawns"]:
            _think(p, "broke_word", "The sect broke its word", -5, 72, c["hour"])
        _letter(c, "bad", "A promise was broken", f"{q['title']}: the deadline passed. People will remember.")
        dao.on_broken_promise(c)


# ---------------------------------------------------------------------------
# mid-game troubles: a spreading fever, a blighted harvest, a demonic infiltrator
# ---------------------------------------------------------------------------
# care -> (days it runs, damage a day to each of the sick (lo, hi), chance a day that each other disciple at home catches it)
PLAGUE_CARE = {"herbs": (1, (3, 8), 0.03), "quarantine": (3, (8, 14), 0.06), "nothing": (4, (14, 24), 0.22)}
PLAGUE_HERBS = 3                                    # fever tea, per sick disciple
PLAGUE_HEAL = 7.0                                   # what a day in bed mends between bouts


def _names(ps: list[dict]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    n = [p["name"] for p in ps]
    return " and ".join(n) if len(n) < 3 else ", ".join(n[:-1]) + " and " + n[-1]


def _can_die(c: dict, p: dict) -> bool:
    return bool(STORYTELLERS[c["storyteller"]]["deaths"]) and not p.get("master")


def plague_care(c: dict, care: str) -> tuple[int, tuple[int, int], float]:
    days, dmg, spread = PLAGUE_CARE[care]
    if care == "quarantine" and _lvl(c, "ward"):
        spread = 0.0                                # the Ward Formation seals the sickroom
    return days, dmg, spread


def plague_odds(c: dict, sick: list[dict], care: str) -> tuple[int, float]:
    """(percent chance that someone dies, expected new cases): the same rolls the fever makes, played out 300 times."""
    if care == "pills":
        return 0, 0.0
    days, (lo, hi), spread = plague_care(c, care)
    r = random.Random(f"{c['seed']}:plague_odds:{c['hour']}:{care}")
    well = [p for p in _home(c) if p not in sick]
    deaths = caught = 0
    for _ in range(300):
        hp = {p["id"]: (p["health"], hurt_mult(p, c), _can_die(c, p)) for p in sick}
        healthy = list(well)
        died = False
        for _ in range(days):
            for pid, (h, m, mortal) in list(hp.items()):
                h -= r.randint(lo, hi) * m
                if h <= 0 and mortal:
                    died = True
                    del hp[pid]
                    continue
                hp[pid] = (min(100.0, max(h, 6.0) + PLAGUE_HEAL), m, mortal)
            for o in list(healthy):
                if r.random() < spread:
                    healthy.remove(o)
                    caught += 1
                    hp[o["id"]] = (o["health"] - 10 * hurt_mult(o, c), hurt_mult(o, c), _can_die(c, o))
        deaths += died
    return round(100 * deaths / 300), caught / 300


def _raise_plague(c: dict, r: random.Random) -> bool:
    home = _others(c)
    if len(home) < 2:
        return False
    sick = r.sample(home, 2 if len(home) < 6 else 3)
    for p in sick:
        p["sick_until"] = max(p["sick_until"], c["hour"] + 48)
        _hurt(p, 10, c)
        _think(p, "fever", "Burning with fever", -6, 48, c["hour"])
    names = _names(sick)
    n = len(sick)
    opts = []
    if c["res"]["pills"] >= n:
        opts.append(("pills", f"{'A pill each' if n > 1 else 'A pill'} ({_n(n, 'pill')}): they are well tomorrow, and it spreads no further"))
    if c["res"]["herbs"] >= PLAGUE_HERBS * n:
        d, _ = plague_odds(c, sick, "herbs")
        opts.append(("herbs", f"Brew fever tea ({PLAGUE_HERBS * n} herbs): a day in bed; {d}% that someone dies"))
    d, k = plague_odds(c, sick, "quarantine")
    opts.append(("quarantine", f"Seal them in the sickroom{' behind the Ward Formation' if _lvl(c, 'ward') else ''} for three days, no medicine: "
                               f"{d}% that someone dies, about {k:.1f} more fall ill"))
    d, k = plague_odds(c, sick, "nothing")
    opts.append(("nothing", f"Let it run its course among the others (four days): {d}% that someone dies, about {k:.1f} more fall ill"))
    _ask(c, "plague", "A fever in the dormitory",
         f"{names} woke burning and could not stand: marsh fever, which goes through a sect like fire through dry grass. Pills cure it; "
         "fever tea nearly so. A sealed sickroom stops " + ("it spreading" if _lvl(c, "ward") else "most of the spread")
         + ", but the sick suffer longer. Each day of fever costs health; the wounded may not survive it.",
         opts, sick=[p["id"] for p in sick])
    return True


def _res_plague(c, ev, opt, r):
    sick = [p for p in (_p(c, i) for i in ev.get("sick", [])) if p]
    if not sick:
        return _letter(c, "info", "The fever broke", "By the time anyone decided, it had passed.")
    n = len(sick)
    if opt == "pills":
        if c["res"]["pills"] < n:
            return ("err", f"You need {_n(n, 'pill')}.")
        snap = _snap(c)
        c["res"]["pills"] -= n
        for p in sick:
            p["sick_until"] = c["hour"] + 12
            _think(p, "fever", "Cured of a fever", 2, 24, c["hour"])
        out = _letter(c, "good", "The fever was cut short", f"A pill {'each' if len(sick) > 1 else 'was enough'}, and {_names(sick)} {_be(sick, 'was', 'were')} sitting up by evening.")
        _scene(c, "sickness", True, out["title"], out["text"], verdict="Cured", party=sick,
               lines=[("", f"{_n(n, 'pill')} used. Nobody else fell ill.", True)], snap=snap)
        return out
    if opt == "herbs":
        if c["res"]["herbs"] < PLAGUE_HERBS * n:
            return ("err", f"You need {PLAGUE_HERBS * n} herbs.")
        c["res"]["herbs"] -= PLAGUE_HERBS * n
    days = plague_care(c, opt)[0]
    for p in sick:
        p["sick_until"] = max(p["sick_until"], c["hour"] + 24 * days)
    c["later"].append({"at": c["hour"] + 24, "kind": "plague_tick", "care": opt, "left": days, "sick": [p["id"] for p in sick],
                       "all": [p["id"] for p in sick], "dead": [], "health": {p["id"]: p["health"] for p in sick}})
    word = {"herbs": "The kitchen smells of bitter tea.", "quarantine": "The sickroom door is barred; food goes in through a hatch.",
            "nothing": "The sick lie in the dormitory while the others step around them."}[opt]
    return _letter(c, "info", "The fever runs its course", f"{word} It will take {days} day{'s' if days != 1 else ''}.")


def _plague_tick(c: dict, item: dict, r: random.Random) -> None:
    care = item.get("care") if item.get("care") in PLAGUE_CARE else "nothing"
    for k in ("sick", "all", "dead"):                 # a loaded save may have mangled these
        item[k] = [str(x) for x in item[k]] if isinstance(item.get(k), list) else []
    item["health"] = {str(k): float(v) for k, v in item["health"].items() if isinstance(v, (int, float))} \
        if isinstance(item.get("health"), dict) else {}
    _, (lo, hi), spread = plague_care(c, care)
    first = int(c.get("next_scene", 0))
    sick = [p for p in (_p(c, i) for i in item.get("sick", [])) if p]
    for p in sick:
        _hurt(p, r.randint(lo, hi), c)
        _think(p, "fever", "Burning with fever", -6, 30, c["hour"])
        if p["health"] <= 0 and _can_die(c, p):
            item.setdefault("dead", []).append(p["name"])
            c["tally"]["plague_dead"] = int(c["tally"].get("plague_dead", 0)) + 1
            _die(c, p)
            continue
        p["health"] = max(p["health"], 6.0)
        p["sick_until"] = max(p["sick_until"], c["hour"] + 24)
    sick = [p for p in sick if p in c["pawns"]]
    for o in _home(c):
        if o not in sick and o["id"] not in item.get("all", []) and r.random() < spread:
            item.setdefault("health", {})[o["id"]] = o["health"]
            o["sick_until"] = max(o["sick_until"], c["hour"] + 48)
            _hurt(o, 10, c)
            _think(o, "fever", "Burning with fever", -6, 48, c["hour"])
            sick.append(o)
            item.setdefault("all", []).append(o["id"])
    left = int(item.get("left", 1)) - 1
    if left > 0 and sick:
        c["later"].append({**item, "at": c["hour"] + 24, "left": left, "sick": [p["id"] for p in sick]})
        return
    for p in sick:
        p["sick_until"] = min(p["sick_until"], c["hour"] + 12)
    every = [p for p in (_p(c, i) for i in item.get("all", [])) if p]
    dead = list(item.get("dead", []))
    lines = []
    for p in every:
        before = float((item.get("health") or {}).get(p["id"], p["health"]))
        lines.append((p["name"], f"came through it ({int(round(max(0.0, before - p['health'])))} health lost)", True))
    for name in dead:
        lines.append((name, "died of the fever", False))
    caught = len(every) + len(dead)
    how = {"herbs": "fever tea", "quarantine": "a sealed sickroom", "nothing": "nothing but rest"}[care]
    out = _letter(c, "bad" if dead else "info", "The fever has passed" if not dead else "The fever took its toll",
                  f"{caught} fell ill, treated with {how}." + (f" {' and '.join(dead)} did not survive." if dead else " Everyone lived."))
    _scene(c, "sickness", not dead, out["title"], out["text"], verdict="Everyone lived" if not dead else f"{len(dead)} dead of the fever",
           party=every, lines=lines, extra=[("Fell ill", caught, False, False)] + ([("Dead", len(dead), False, False)] if dead else []),
           first=first)


def _raise_blight(c: dict, r: random.Random) -> bool:
    if not _lvl(c, "fields") or _season(c) == 3:
        return False
    left = (DAYS_PER_SEASON - _day(c) % DAYS_PER_SEASON) + DAYS_PER_SEASON * (2 - _season(c))     # until the winter frost
    seed = 6 * _lvl(c, "fields")
    farmer = max(_home(c) or c["pawns"], key=lambda p: p["skills"]["farm"]["lv"])
    pct = int(min(85, 40 + 4 * farmer["skills"]["farm"]["lv"]))
    per_hour = math.prod(m for _, m in farm_rows(c))
    opts = [("burn", f"Burn the blighted rows and replant ({seed} rice of seed): half yield for 4 days, then clean"),
            ]
    if c["res"]["herbs"] >= 6:
        opts.append(("ash", f"Dust the terraces with herb ash (6 herbs; {farmer['name']}, farming {farmer['skills']['farm']['lv']}): "
                            f"{pct}% it is stopped in 3 days, otherwise it runs on"))
    opts.append(("endure", f"Let it run its course: half yield for {_n(min(left, DAYS_PER_SEASON), 'day')}"))
    _ask(c, "blight", "Blight on the terraces",
         f"Black spots on the rice leaves, spreading from row to row. A farmer-hour on the terraces brings {per_hour:.2f} rice now; "
         f"with the blight, half that. It will burn itself out in {_n(min(left, DAYS_PER_SEASON), 'day')} or at the winter frost. "
         "The sect's alerts show it while it lasts.", opts, seed=seed, pct=pct, days=min(left, DAYS_PER_SEASON))
    return True


def _res_blight(c, ev, opt, r):
    snap = _snap(c)
    before = math.prod(m for _, m in farm_rows(c))
    days = int(ev.get("days", DAYS_PER_SEASON))
    if opt == "burn":
        seed = int(ev.get("seed", 6))
        if c["res"]["rice"] < seed:
            return ("err", f"You need {seed} rice of seed.")
        c["res"]["rice"] -= seed
        days, verdict, ok = 4, "Burned and replanted", True
    elif opt == "ash":
        if c["res"]["herbs"] < 6:
            return ("err", "You need 6 herbs.")
        c["res"]["herbs"] -= 6
        ok = r.random() * 100 < int(ev.get("pct", 50))
        days, verdict = (3, "The ash worked") if ok else (days, "The ash did not take")
    else:
        verdict, ok = "The blight runs its course", False
    c["blight"] = {"until": c["hour"] + 24 * days, "x": 0.5}
    after = math.prod(m for _, m in farm_rows(c))
    out = _letter(c, "bad" if not ok else "info", "Blight on the terraces",
                  f"Rice per farmer-hour falls from {before:.2f} to {after:.2f} for {days} day{'s' if days != 1 else ''}."
                  + (" Plan for a thinner granary." if days > 4 else ""))
    _scene(c, "blight", ok, out["title"], out["text"], verdict=verdict, party=[],
           lines=[("", f"Rice per farmer-hour: {before:.2f} now {after:.2f} (half) for {_n(days, 'day')}", False)]
           + ([("", "The burned rows will come back clean.", True)] if opt == "burn" else []), snap=snap)
    return out


def infiltrator_foe(c: dict, s: dict) -> float:
    """The infiltrator's strength before the roll (it varies 0.8 to 1.2 times this)."""
    return (18 + _day(c) * 0.75) * float(s["power"])


def ward_odds(c: dict, foe: float) -> int:
    """Percent chance the wards flush an infiltrator of this strength out of hiding."""
    return int(min(90, max(10, 100 * ward_power(c) / (foe * 1.5))))


def _raise_infiltrator(c: dict, r: random.Random) -> bool:
    others = _others(c)
    hunters = [s for s in c["sects"] if s["kind"] == ("righteous" if c["demonic"] else "demonic")]
    if len(others) < 2 or not hunters:
        return False
    s = r.choice(hunters)
    victim = r.choice(others)
    foe = infiltrator_foe(c, s)
    scholar = max(_home(c) or c["pawns"], key=lambda p: p["skills"]["scholar"]["lv"])
    bait = _strongest(c, 1, master=True)
    hunt = int(min(90, max(10, 30 + 3 * scholar["skills"]["scholar"]["lv"] + 5 * _lvl(c, "ward"))))
    sutra = "blood_sutra" in c["manuals"] and not c["demonic"]
    what = (f"a hunter from the {s['name']}, come for proof of your demonic arts" if c["demonic"]
            else f"a blood cultivator of the {s['name']}" + (", come for the Blood Sutra" if sutra else ""))
    opts = [("hunt", f"Have {scholar['name']} follow the blood trail (scholarship {scholar['skills']['scholar']['lv']}: {hunt}% to unmask them)")]
    if bait:
        b = bait[0]
        opts.append(("bait", f"Let {b['name']} sleep alone as bait (strength {int(duel_power(c, b))} against about {int(foe)}: "
                             f"{win_odds(duel_power(c, b), foe, 0.8, 1.2)}% to win; a loss is a bad wound)"))
    if _lvl(c, "ward"):
        w = ward_odds(c, foe)
        opts.append(("wards", f"Light the wards at midnight and flush them out (wards {int(ward_power(c))}: {w}%)"))
    opts.append(("wait", "Bar the dormitory doors and wait for them to leave (three nights of drained qi, and they take what they came for)"))
    _ask(c, "infiltrator", "Something walks the halls at night",
         f"{victim['name']} woke grey-faced with two small marks on the wrist and a third of a stage of qi gone. "
         f"Someone has slipped in among the porters: {what}. Their strength is about {int(foe)}. "
         "Left alone they will feed for three nights and leave with whatever they can carry.",
         opts, src=s["id"], victim=victim["id"], hunt=hunt, ward=ward_odds(c, foe), pawn=bait[0]["id"] if bait else "", scholar=scholar["id"])
    victim["qi"] = max(0.0, victim["qi"] - step_need(victim["step"]) * 0.3)
    _think(victim, "drained", "Drained in the night", -8, 48, c["hour"])
    return True


def _res_infiltrator(c, ev, opt, r):
    s = _sect(c, ev.get("src", ""))
    if not s:
        return None
    snap = _snap(c)
    foe = infiltrator_foe(c, s) * r.uniform(0.8, 1.2)
    party, lines = [], []
    if opt == "hunt":
        p = _p(c, ev.get("scholar", "")) or (_home(c) or c["pawns"])[0]
        party = [p]
        ok = r.random() * 100 < int(ev.get("hunt", 30))
        lines.append((p["name"], f"followed the trail ({int(ev.get('hunt', 30))}% to unmask them)", ok))
        if ok:
            _xp(p, "scholar", 30)
    elif opt == "bait":
        p = _p(c, ev.get("pawn", ""))
        if not p:
            return ("err", "Nobody is fit to be the bait.")
        party = [p]
        ok = duel_power(c, p) >= foe
        lines.append((p["name"], f"strength {int(duel_power(c, p))} against {int(foe)}", ok))
        _xp(p, "combat", 30)
        if not ok:
            _hurt(p, r.randint(50, 85), c)
    elif opt == "wards":
        ok = r.random() * 100 < int(ev.get("ward", 30))
        lines.append(("", f"The wards ({int(ward_power(c))}) against about {int(infiltrator_foe(c, s))}: {int(ev.get('ward', 30))}% to flush them out", ok))
    else:
        ok = False
    thief = "the demon-hunter" if c["demonic"] else "the blood cultivator"
    if ok:
        _fame(c, 5)
        _rel(s, -10)
        _add(c, "stones", 6)
        for o in c["pawns"]:
            _think(o, "caught", "Caught the thing in the halls", 5, 48, c["hour"])
        text = f"Cornered behind the kitchens: {thief}, wearing a porter's face. The {s['name']} will deny everything. Six spirit stones were in their sleeves."
    else:
        took = int(c["res"]["stones"] * (0.3 if opt == "wait" else 0.25))
        c["res"]["stones"] -= took
        c["tally"]["stolen"] = float(c["tally"].get("stolen", 0.0)) + took
        drained = r.sample(_others(c), min(3 if opt == "wait" else 1, len(_others(c))))
        for o in drained:
            o["qi"] = max(0.0, o["qi"] - step_need(o["step"]) * 0.25)
            _think(o, "drained", "Drained in the night", -8, 48, c["hour"])
        lost = ""
        if "blood_sutra" in c["manuals"] and not c["demonic"]:
            c["manuals"].remove("blood_sutra")
            lost = " The Blood Sutra went with them."
        lines.append(("", f"Drained in the night: {', '.join(o['name'] for o in drained) or 'nobody'} (a quarter of a stage of qi each)", False))
        if took:
            lines.append(("", f"{took} spirit stones gone from the vault", False))
        text = f"{thief[0].upper() + thief[1:]} slipped away over the wall." + lost
    for p in party:
        if p in c["pawns"] and p["health"] <= 0:
            if _can_die(c, p):
                text += f" {p['name']} did not survive the night."
                _die(c, p)
            else:
                p["health"] = 6.0
    out = _letter(c, "good" if ok else "bad", "The infiltrator is caught" if ok else "The infiltrator escaped", text)
    _scene(c, "infiltrator", ok, out["title"], out["text"], verdict="Unmasked" if ok else "Gone over the wall", party=party, lines=lines, snap=snap,
           first=snap["next"])
    return out


# A thief in the night: walls and swords keep raiders out, not a sneak with a sack. It comes to a strong sect too.
def thief_foe(c: dict) -> float:
    """The thief's strength before the roll (it varies 0.7 to 1.3 times this): a runner has to catch and beat them."""
    return 12 + _day(c) * 0.6


def thief_track(c: dict, p: dict) -> int:
    """Percent chance a tracker follows the thief's trail to where the goods were dropped."""
    return int(min(85, max(10, 20 + 3 * p["skills"]["gather"]["lv"] + 5 * _lvl(c, "ward"))))


def _raise_thief(c: dict, r: random.Random) -> bool:
    home = [p for p in _home(c) if p["health"] >= 40]
    if not home:
        return False
    target = loot_target(c)
    n = int(min(60.0, c["res"][target] * r.uniform(0.15, 0.25)))
    if n < 5:
        return False
    c["res"][target] -= n                              # it is already gone: the choice is whether it comes back
    runner = (_strongest(c, 1) or _strongest(c, 1, master=True) or home)[0]
    tracker = max(home, key=lambda p: p["skills"]["gather"]["lv"])
    foe = thief_foe(c)
    me = duel_power(c, runner)
    _ask(c, "thief", "A thief in the storehouse",
         f"At first light the storehouse door stood open and {n} {target} were gone. Wet footprints lead down the back stair "
         f"toward the forest. Whoever it was is quick: about {int(foe)} strength, and an hour ahead.",
         [("chase", f"Send {runner['name']} after them (strength {int(me)} against about {int(foe)}: {win_odds(me, foe, 0.7, 1.3)}% to catch them; "
                    "a loss is a wound)"),
          ("track", f"Have {tracker['name']} follow the trail (gathering {tracker['skills']['gather']['lv']}: {thief_track(c, tracker)}% to find the sacks)"),
          ("let_go", f"Let it go and fit a better lock (the {n} {target} are lost)")],
         res=target, n=n, runner=runner["id"], tracker=tracker["id"])
    return True


def _res_thief(c, ev, opt, r):
    target, n = str(ev.get("res", "rice")), int(ev.get("n", 0))
    if target not in LOOTABLE:
        return None
    snap = _snap(c)
    party, lines, ok = [], [], False
    if opt == "chase":
        p = _p(c, ev.get("runner", ""))
        if not p or p["away_until"] > c["hour"]:
            return ("err", "They are not at the sect to give chase.")
        party = [p]
        base = thief_foe(c)
        foe = base * r.uniform(0.7, 1.3)
        ok = duel_power(c, p) >= foe
        lines.append((p["name"], f"strength {int(duel_power(c, p))} against {int(foe)} ({win_odds(duel_power(c, p), base, 0.7, 1.3)}% before the chase)", ok))
        _xp(p, "combat", 20)
        if not ok:
            _hurt(p, r.randint(10, 25), c)
            p["health"] = max(p["health"], 5.0)
    elif opt == "track":
        p = _p(c, ev.get("tracker", ""))
        if not p or p["away_until"] > c["hour"]:
            return ("err", "They are not at the sect to follow the trail.")
        party = [p]
        chance = thief_track(c, p)
        ok = r.random() * 100 < chance
        lines.append((p["name"], f"followed the trail ({chance}% to find the sacks)", ok))
        _xp(p, "gather", 20)
    if ok:
        c["res"][target] += n                          # the store's own goods coming home, even past the storehouse limit
        _fame(c, 2)
        lines.append(("", f"All {n} {target} carried back up the stair", True))
        text = f"The sacks were found under a fallen pine, the thief's sandals beside them. The {n} {target} are back in the storehouse."
    else:
        c["tally"]["stolen"] = float(c["tally"].get("stolen", 0.0)) + n
        for o in c["pawns"]:
            _think(o, "robbed", "The storehouse was robbed", -3, 36, c["hour"])
        lines.append(("", f"Carried off from the stores: {n} {target}", False))
        text = ("The trail went cold at the river." if opt == "track" else "They were too quick on the forest paths." if opt == "chase"
                else "The door has a new bronze lock.") + f" The {n} {target} are gone."
    out = _letter(c, "good" if ok else "bad", "The thief was caught" if ok else "The thief got away", text)
    _scene(c, "theft", ok, out["title"], out["text"], verdict="The stores are safe" if ok else "Robbed", party=party, lines=lines, snap=snap)
    return out


# A feud inside the walls: the player can end it, not only wait it out.
def _raise_feud(c: dict, r: random.Random) -> bool:
    pairs = rival_pairs(c)
    if not pairs:
        return False
    a, b = min(pairs, key=lambda ab: bond(c, ab[0], ab[1]))
    m = _master(c)
    opts = []
    if m and m["away_until"] <= c["hour"] and c["res"]["rice"] >= FEUD_MEAL:
        opts.append(("mediate", f"{m['name']} sits them down over a shared meal ({int(FEUD_MEAL)} rice; it ends the rivalry)"))
    opts += [("spar", f"Let them settle it in a formal spar (+{FEUD_MEND['spar']} bond and combat practice; the loser takes a bruising)"),
             ("apart", f"Keep them on different work and let it lie (+{FEUD_MEND['apart']} bond)")]
    _ask(c, "feud", f"{a['name']} and {b['name']} came to blows",
         f"Words in the dining hall, then fists. {a['name']} and {b['name']} have been rivals for a while now (bond {int(bond(c, a, b))}), "
         "and the rest of the sect is taking sides. Each resents the other's every success.",
         opts, a=a["id"], b=b["id"])
    return True


FEUD_MEAL = 10.0
FEUD_MEND = {"mediate": 35, "spar": 22, "apart": 6}


def _res_feud(c, ev, opt, r):
    a, b = _p(c, ev.get("a", "")), _p(c, ev.get("b", ""))
    if not a or not b or opt not in FEUD_MEND:
        return None
    if opt == "mediate":
        if c["res"]["rice"] < FEUD_MEAL:
            return ("err", f"You need {int(FEUD_MEAL)} rice for the meal.")
        c["res"]["rice"] -= FEUD_MEAL
    mend = FEUD_MEND[opt]
    if opt == "mediate":                                   # the Master's word ends it, however deep it ran
        mend = max(mend, RIVAL_UNTIL + 5 - bond(c, a, b))
    _bond(c, a, b, mend)
    if opt == "mediate":
        for p in (a, b):
            _think(p, "mediated", "Made peace before the Sect Master", 4, 72, c["hour"])
        return _letter(c, "good", f"{a['name']} and {b['name']} made peace",
                       "Neither spoke for the first bowl. By the third they were arguing about sword forms instead of each other.")
    if opt == "spar":
        win, lose = sorted((a, b), key=lambda p: -duel_power(c, p) * r.uniform(0.8, 1.2))
        for p in (a, b):
            _xp(p, "combat", 25)
        _hurt(lose, r.randint(8, 18), c)
        lose["health"] = max(lose["health"], 5.0)
        _think(win, "spar", f"Beat {lose['name']} fair and square", 4, 48, c["hour"])
        return _letter(c, "info", f"{win['name']} won the spar",
                       f"{lose['name']} got up, bowed, and meant it. A beating given by the rules is easier to forgive than an insult.")
    return _letter(c, "info", "The rivals were kept apart", f"{a['name']} and {b['name']} work at opposite ends of the sect for now.")


# ---------------------------------------------------------------------------
# festivals: two a year, each its own, and a real choice each time
# ---------------------------------------------------------------------------
# key -> (name, season, flavour, the second choice: (id, label))
FESTIVALS = {
    "lantern": ("Lantern Festival", 0, "The first full moon of the year. Paper lanterns climb the ten thousand steps, each with a riddle tucked inside.",
                ("riddles", "Lantern riddles only ({half} rice): +6 mood for 2 days, and 30 scholarship practice each")),
    "ghost": ("Ghost Festival", 1, "The gates of the underworld stand open this month. Hungry ghosts walk the valley roads looking for someone to remember them.",
              ("offer", "Burn paper offerings at the crossroads (6 wood): +6 mood for 3 days, and heaven notices (+2 karma)")),
    "moon": ("Mid-Autumn Moon Festival", 2, "The fullest moon of the year hangs over the peak. Mooncakes, and the old story of the lady who flew to the moon.",
             ("moon", "Sit under the moon together (free): a tenth of a stage of qi each, +5 mood for 2 days")),
    "solstice": ("Winter Solstice", 3, "The longest night. Everyone sits up together over dumplings until the light turns.",
                 ("vigil", "Keep the night vigil with stories (free): +4 mood for 3 days, every pair +3 bond, everyone tired tomorrow")),
}
FESTIVAL_YEARS = (("lantern", "moon"), ("ghost", "solstice"))     # odd years, even years: at most two a year
FESTIVAL_DAY = 5                                                 # the day of its season a festival falls on
FESTIVAL_SCENE = {"lantern": "festival_spring", "moon": "festival_moon", "ghost": "festival_ghost", "solstice": "festival_winter"}


def festival_of(day: int) -> str:
    """The festival that falls in this day's season, if this year has one then."""
    year, season = day // (DAYS_PER_SEASON * 4), day // DAYS_PER_SEASON % 4
    return next((k for k in FESTIVAL_YEARS[year % 2] if FESTIVALS[k][1] == season), "")


def _offer_festival(c: dict, key: str) -> None:
    name, _, flavour, (alt, alt_label) = FESTIVALS[key]
    cost = 4 * len(c["pawns"])
    skip = "-6 mood for 3 days, and the forgotten dead are restless" if key == "ghost" else "-4 mood for 2 days"
    _ask(c, "festival", name, f"{flavour} A feast ({cost} rice) lifts every heart (+10 mood for 3 days) and draws the disciples closer. "
         f"Skipping it: {skip}.",
         [("hold", f"Hold the feast ({cost} rice)"), (alt, alt_label.format(half=cost // 2)), ("skip", "There is work to do")],
         name=name, flavour=flavour, cost=cost, fest=key)


def _res_festival(c, ev, opt, r):
    name = ev["name"]
    home = _home(c)
    if opt == "hold":
        if c["res"]["rice"] < ev["cost"]:
            return ("err", f"A feast needs {ev['cost']} rice.")
        snap = _snap(c)
        c["res"]["rice"] -= ev["cost"]
        _fame(c, 2)                                   # the whole valley sees the lanterns
        for p in home:
            _think(p, "festival", f"Celebrated the {name}", 10, 72, c["hour"])
            p["joy"] = 100.0
        for i, a in enumerate(home):
            for b in home[i + 1:]:
                _bond(c, a, b, 4)
        out = _letter(c, "good", f"The {name}", ev["flavour"] + " Everyone is closer for it.")
        away = len(c["pawns"]) - len(home)
        _scene(c, FESTIVAL_SCENE.get(ev.get("fest"), "festival"), True, out["title"], out["text"], verdict="The feast is held", party=home,
               lines=[("", f"{len(home)} disciple{'s' if len(home) != 1 else ''} feasted: joy full, +10 mood for 3 days", True),
                      ("", "Every pair at the table grew closer (+4 bond)", True),
                      ("", "The valley saw the lanterns (+2 fame)", True)]
               + ([("", f"{away} away from the sect missed it", None)] if away else []),
               snap=snap, extra=[("Mood, 3 days", 10, True, True)])
        return out
    snap = _snap(c)
    if opt == "riddles":
        half = int(ev["cost"]) // 2
        if c["res"]["rice"] < half:
            return ("err", f"The riddle night needs {half} rice for the sweet dumplings.")
        c["res"]["rice"] -= half
        for p in home:
            _think(p, "festival", f"Solved lantern riddles at the {name}", 6, 48, c["hour"])
            _xp(p, "scholar", 30)
        out = _letter(c, "good", f"Riddles at the {name}", "Lanterns on every eave, a riddle in each. The pavilion's scholars were insufferable all night.")
        lines = [("", f"{_n(len(home), 'disciple')}: +6 mood for 2 days and 30 scholarship practice each", True)]
        extra = [("Mood, 2 days", 6, True, True)]
    elif opt == "offer":
        if c["res"]["wood"] < 6:
            return ("err", "The offerings need 6 wood for the fires.")
        c["res"]["wood"] -= 6
        c["karma"] = max(-100.0, min(100.0, float(c.get("karma", 0.0)) + 2))
        for p in home:
            _think(p, "festival", f"Remembered the dead at the {name}", 6, 72, c["hour"])
        out = _letter(c, "good", f"Offerings at the {name}", "Paper money and paper houses burned at the crossroads. The night was very quiet, and nobody minded.")
        lines = [("", f"{_n(len(home), 'disciple')}: +6 mood for 3 days", True), ("", "Heaven remembers kindness to the forgotten (+2 karma)", True)]
        extra = [("Mood, 3 days", 6, True, True)]
    elif opt == "moon":
        for p in home:
            _gain_qi(c, p, step_need(p["step"]) * 0.1)
            _think(p, "festival", f"Watched the moon at the {name}", 5, 48, c["hour"])
        out = _letter(c, "good", f"Moon-viewing at the {name}", "They sat on the cold stone of the terrace until the moon set, breathing in its light.")
        lines = [("", f"{_n(len(home), 'disciple')} gathered a tenth of a stage of qi each", True), ("", "+5 mood for 2 days", True)]
        extra = [("Mood, 2 days", 5, True, True)]
    elif opt == "vigil":
        for p in home:
            _think(p, "festival", f"Kept the vigil of the {name}", 4, 72, c["hour"])
            p["rest"] = min(p["rest"], 30.0)
        for i, a in enumerate(home):
            for b in home[i + 1:]:
                _bond(c, a, b, 3)
        out = _letter(c, "good", f"The vigil of the {name}", "Stories until dawn: ghosts, first loves, the elder who fell in the latrine. Nobody got much work done the next day.")
        lines = [("", f"{_n(len(home), 'disciple')}: +4 mood for 3 days, every pair +3 bond", True), ("", "Everyone is tired today", False)]
        extra = [("Mood, 3 days", 4, True, True)]
    else:
        ghost = ev.get("fest") == "ghost"
        for p in c["pawns"]:
            _think(p, "festival", f"The {name} was skipped", -6 if ghost else -4, 72 if ghost else 48, c["hour"])
        out = _letter(c, "info", f"The {name} passed unmarked", "There was work to do." + (" At night something knocked on the shutters." if ghost else ""))
        _scene(c, FESTIVAL_SCENE.get(ev.get("fest"), "festival"), False, out["title"], out["text"], verdict="No festival this year", party=c["pawns"],
               lines=[("", "Every disciple is disappointed: " + ("-6 mood for 3 days" if ghost else "-4 mood for 2 days"), False)],
               extra=[("Mood", -6 if ghost else -4, False, True)])
        return out
    _scene(c, FESTIVAL_SCENE.get(ev.get("fest"), "festival"), True, out["title"], out["text"], verdict="A quiet festival", party=home, lines=lines, snap=snap, extra=extra)
    return out


# ---------------------------------------------------------------------------
# expeditions: send a party out and see what comes back
# ---------------------------------------------------------------------------
PLACES = {
    "valley": {"name": "Herb Valley", "hours": 24, "risk": 0.15, "text": "A day's walk. Herbs, and little danger."},
    "forest": {"name": "Beast Forest", "hours": 36, "risk": 0.4, "text": "Spirit stones in the beasts' dens. They fight for them."},
    "ruins":  {"name": "Ruined Sect", "hours": 48, "risk": 0.6, "text": "Manuals and treasures under the rubble, and whatever killed the sect."},
}


def expedition(st: dict, place: str, now: float, pawns: list[str] | None = None, stance: str = "balanced") -> dict:
    """Send a party out. Name the disciples and how they should travel, or leave it to the two strongest."""
    return dao.road.expedition(st, place, list(pawns or []), stance, now)


def _trip_return(c: dict, item: dict, r: random.Random) -> None:
    team = [p for p in (_p(c, i) for i in item.get("pawns", [])) if p]
    pl = PLACES.get(item.get("place"), PLACES["valley"])
    if not team:
        return
    snap = _snap(c)
    power = sum(duel_power(c, p) for p in team)
    luck = min(1.6, power / max(1.0, (26 + _day(c) * 0.9) * (0.6 + pl["risk"]))) * float(item.get("loot_x", 1.0))
    found = []
    if item.get("place") == "valley":
        n = int(r.randint(14, 24) * min(1.3, luck + 0.3))
        _add(c, "herbs", n)
        found.append(f"{n} herbs")
        rare = r.randint(1, 2)
        c["rare"] += rare
        found.append(f"{rare} hundred-year spirit herb{'s' if rare > 1 else ''}")
    elif item.get("place") == "forest":
        n = int(r.randint(8, 16) * luck)
        _add(c, "stones", n)
        found.append(f"{n} spirit stones")
        if not c["beast"] and r.random() < 0.15 * luck:
            c["beast"] = {"name": r.choice(lore.BEASTS), "born": c["hour"]}
            found.append("an orphaned spirit-beast cub, which followed them home")
    else:
        n = int(r.randint(4, 10) * luck)
        _add(c, "stones", n)
        found.append(f"{n} spirit stones")
        if r.random() < 0.45 * luck:
            mid = _loot_manual(c, r, min(3, _max_grade(c) + 1))
            if mid:
                found.append(f"the {_manual_name(mid)}")
        if r.random() < 0.2 * luck:
            tid = _loot_treasure(c, r)
            if tid:
                found.append(f"the {lore.TREASURES[tid]['name']}")
        if r.random() < 0.35 * luck:
            found.append(f"the {_new_artifact(c, r, 'dug out of the Ruined Sect')['name']}")
    hurt = []
    for p in team:
        _xp(p, "combat", 20 * pl["risk"] * 2)
        _xp(p, "gather", 15)
        if r.random() < pl["risk"] * float(item.get("risk_x", 1.0)) / max(0.5, luck):
            _hurt(p, r.randint(15, 45), c)
            p["health"] = max(p["health"], 8.0)
            hurt.append(p["name"])
    dao.road.trip_bonus(c, item, r, found, team)
    c["later"] = [x for x in c["later"] if x.get("kind") != "trip_mid"]
    for i, a in enumerate(team):
        for b in team[i + 1:]:
            _bond(c, a, b, 10 if hurt else 6)
    ev = _letter(c, "good" if not hurt else "info", f"The party is back from the {pl['name']}",
                 f"They brought {', '.join(found)}." + (f" {' and '.join(hurt)} came back wounded." if hurt else "") + " The road brought them closer.")
    st_name = dao.road.STANCES.get(item.get("stance"), dao.road.STANCES["balanced"])["name"]
    _scene(c, "realm", not hurt, ev["title"], ev["text"], verdict="Back unharmed" if not hurt else "Back, bloodied", party=team,
           lines=[("", f"{pl['name']}, travelling {st_name.lower()}: {pl['hours']} hours on the road.", None),
                  ("", f"Brought back {', '.join(found)}.", True)],
           snap=snap)


_RESOLVERS.update(quest_offer=_res_quest_offer, quest_reward=_res_quest_reward, festival=_res_festival,
                  plague=_res_plague, blight=_res_blight, infiltrator=_res_infiltrator, thief=_res_thief, feud=_res_feud)


# ---------------------------------------------------------------------------
# the clock
# ---------------------------------------------------------------------------
def _hour(c: dict, quiet: bool) -> None:
    c["hour"] += 1
    taken: dict = {}
    for p in list(c["pawns"]):
        _tick_pawn(c, p, taken, quiet)
    _tick_builds(c)
    _socialise(c, quiet)
    dao.hourly(c, quiet)
    if c["hour"] % 24 == 5:
        dao.daily(c, quiet)
        _mend_grudges(c)
    if c["hour"] % 24 == READ_HOUR:
        _evening_reading(c)
    if not quiet:
        _quest_tick(c)
        _guide(c)
        if c["hour"] % 24 == 7:
            _check_works(c)
        for item in list(c["later"]):
            if item not in c["later"]:                 # dropped by an earlier item this hour (a party home cancels its midway word)
                continue
            if item.get("at", 0) <= c["hour"]:
                if _later(c, item):
                    c["later"].remove(item)
                else:
                    item["at"] = c["hour"] + 6
    if c["hour"] % 24 == 6:
        c["adapt"] = min(1.5, c["adapt"] + 0.006)
        _upkeep(c, quiet)                                     # firewood, repairs, spoilage, the beast's rice
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
    _builders_wait(c, now)               # ...all but the builders, who work on at the away rate while an event waits
    c["last_real"] = now
    return {"ok": True, "hours": n}


def catch_up(st: dict, now: float) -> int:
    """Quiet progress for time spent away. Returns the sim hours advanced."""
    c = _c(st, now)
    if not c["name"] or c["seclusion"] or c["pending"]:
        c["built_away"] = []
        built = _builders_wait(c, now) if c["name"] else 0     # an event waiting: only the builders work on
        if built and c["built_away"]:
            _letter(c, "info", "The builders worked on", f"While the sect waited for your answer, the builders finished: {_and(c['built_away'])}.")
        c.pop("built_away", None)
        c["last_real"] = now             # sealed gates, or someone waiting for your answer: time waits
        return 0
    hours = int(min(max(0.0, now - c["last_real"]) / SECS_PER_HOUR_OFFLINE, MAX_OFFLINE_HOURS))
    if hours < 1:
        return 0
    c["built_away"] = []
    for _ in range(hours):
        _hour(c, quiet=True)
    c["last_real"] = now
    built = c.pop("built_away", [])
    if hours >= 6 or built:
        _letter(c, "info", "While you were away", f"The sect carried on quietly for {_n(hours, 'hour')}. No one came to harm."
                + (f" The builders finished: {_and(built)}." if built else ""))
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
    if p["prio"][job] != 1 and job in POSTS.get(p.get("post", ""), ()):
        p["post"] = ""                                # moved off their post's work in the detailed grid
    c["flags"]["prio"] = 1
    _guide(c)
    return {"ok": True}


def queue_build(st: dict, room: str, now: float) -> dict:
    c = _c(st, now)
    if room not in ROOMS:
        return {"ok": False, "error": "Unknown room."}
    level = _lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
    if level >= ROOMS[room]["max"]:
        return {"ok": False, "error": "Already at its highest level."}
    why = build_block(c, room, level)
    if why:
        return {"ok": False, "error": why}
    if len(c["builds"]) >= builders(c):
        n = builders(c)
        return {"ok": False, "error": f"{'Both' if n == 2 else f'All {n}'} builders are busy. One comes free when a job finishes."}
    cost = room_cost(c, room, level)
    short = [f"{math.ceil(v - c['res'][k])} more {RES_NAMES[k].lower()}" for k, v in cost.items() if c["res"][k] < v]
    if short:
        return {"ok": False, "error": "Needs " + " and ".join(short) + "."}
    for k, v in cost.items():
        c["res"][k] -= v
    c["builds"].append({"room": room, "need": build_hours(room, level + 1), "done": 0.0, "cost": cost, "at": c["hour"], "crew": [], "slotted": 1})
    return {"ok": True}


def use_blueprint(st: dict, index: int, now: float) -> dict:
    """Spend a Master's Blueprint (drawn from a day's study) on one running job: BLUEPRINT_CUT off the time it has left."""
    c = _c(st, now)
    run = _running(c)
    if not 0 <= int(index) < len(run):
        return {"ok": False, "error": "No builder is on that job."}
    bp = c["blueprints"]
    if bp["n"] < 1:
        return {"ok": False, "error": "No blueprint in hand. The Master draws one on a day you study."}
    b = run[int(index)]
    cut = BLUEPRINT_CUT * max(0.0, b["need"] - b["done"])
    b["done"] += cut
    b["blue"] = float(b.get("blue", 0.0)) + cut
    bp["n"] -= 1
    if b["done"] >= b["need"] - 1e-9:
        _finish_build(c, b)
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
    p["toxin"] += 1.0                                  # pills are not rice
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
        friend = bond(c, p, o) >= 30
        _think(o, "banish", f"{p['name']}, a friend, was sent away" if friend else "A disciple was sent away", -12 if friend else -4, 96 if friend else 48, c["hour"])
    c["bonds"] = {k: v for k, v in c["bonds"].items() if p["id"] not in k.split("|")}
    _unequip(c, p)
    _annal(c, f"{p['name']} was sent away from the sect.")
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
    if practice or not enabled(st):
        return {"qi": 0, "insight": 0, "events": []}       # study only: qi and insight do not accrue
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
        events.append({"kind": "info", "text": "You studied, so the gates are open again. Your streak was kept." if enabled(st)
                       else "You studied, so your holiday is over. Your streak was kept."})
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
        events += _mark_study_day(st, c, now)              # the streak is study's own, sect or not
    if counted and enabled(st):
        good = answers >= 8 and correct / max(answers, 1) >= 0.8
        for p in c["pawns"]:
            _think(p, "lecture", "The Master lectured brilliantly" if good else "The Master lectured", 10 if good else 6, 24, c["hour"])
        m = _master(c)
        for p in _home(c):
            if m and p is not m:
                _bond(c, m, p, 2)                    # teaching binds master and disciple
        if c["pawns"]:
            events.append({"kind": "good", "text": "Your disciples gathered to hear what you learned. Their mood lifts for a day."})
        events += _study_builds(st, c, now)
    return {"stones": 0, "events": events, "streak": c["streak"]}


def _study_builds(st: dict, c: dict, now: float) -> list[dict]:
    """Study helps the builders and never gates them: a counted session draws a Master's Blueprint (one per real day,
    up to BLUEPRINT_BANK kept), and meeting the weekly goal lends the Master as one more builder for a day."""
    out = []
    today = _today(st, now)
    bp = c["blueprints"]
    if bp["day"] != today:
        bp["day"] = today
        if bp["n"] < BLUEPRINT_BANK:
            bp["n"] += 1
            out.append({"kind": "good", "text": f"The Master drew a blueprint from today's study: {int(BLUEPRINT_CUT * 100)}% off the time left "
                                                f"on one build ({_n(bp['n'], 'blueprint')} in hand)."})
    wk = c["week"]
    if wk["id"] and len(wk["days"]) >= WEEK_GOAL and wk.get("lent") != wk["id"]:
        wk["lent"] = wk["id"]
        c["master_builds_until"] = c["hour"] + MASTER_BUILDER_HOURS
        out.append({"kind": "good", "text": f"A week of study: the Master joins the builders for {MASTER_BUILDER_HOURS} sect hours."})
    return out


def on_trial(st: dict, course: str, *, passed: bool, pct: int, now: float) -> dict:
    c = _c(st, now)
    events: list[dict] = []
    if passed and not enabled(st):
        events.append({"kind": "good", "text": f"Trial passed with {pct}%."})
    elif passed:
        for p in c["pawns"]:
            _gain_qi(c, p, step_need(p["step"]) * 0.15)
            _think(p, "trial", "The Master passed a trial", 8, 48, c["hour"])
        events.append({"kind": "good", "text": f"Trial passed with {pct}%. Every disciple feels a surge of qi."})
    else:
        events.append({"kind": "info", "text": f"Trial attempt: {pct}%. What you missed is back in your review queue."})
    return {"stones": 0, "events": events}


def enabled(st: dict) -> bool:
    """The sect is optional (settings.sect_enabled). Off = study only: the sim does not tick, study pays it nothing."""
    return (st.get("settings") or {}).get("sect_enabled", True) is not False


def set_enabled(st: dict, on: bool, now: float, name: str = "", master: str = "") -> dict:
    """Turn the sect on or off. Off pauses it (nothing is deleted). On founds it first if founding was
    skipped, and restarts its clock from now, so the paused weeks never come back as a catch-up."""
    c = _c(st, now)
    s = st["settings"]
    if on:
        if not c["name"]:
            setup(st, name or s.get("sect_name", ""), master or s.get("sect_master", ""), now)
        s["sect_enabled"] = True
    else:
        s["sect_enabled"] = False
    c["last_real"] = now
    return {"ok": True, "sect_enabled": s["sect_enabled"], "founded": bool(c["name"])}


def ensure(st: dict, now: float, ctx: dict | None = None) -> list[dict]:
    if not enabled(st):
        _c(st, now)["last_real"] = now       # paused: the sect's clock stands still with it
        return []
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


def _whole(v) -> int:
    """A stock as the player may count on it: rounded down, so 54.6 wood never shows as the 55 a build needs."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0
    return int(math.floor(v)) if math.isfinite(v) else 0


# ---------------------------------------------------------------------------
# what work actually made over the last day of sect time (the net rates on the
# resource chips, and why nobody is building). Recorded, not estimated.
# ---------------------------------------------------------------------------
MADE_HOURS = 24


def _note_work(c: dict, p: dict, job: str, before: dict) -> None:
    """Record one disciple's hour of work: the hour itself, and what it added to or took from the stores."""
    made = c["made"]
    c.setdefault("made_from", c["hour"])
    key = str(c["hour"])
    if key not in made:
        for k in [k for k in made if int(k) <= c["hour"] - MADE_HOURS]:
            del made[k]
        made[key] = {}
    b = made[key]
    k = f"h|{job}|{p['id']}"
    b[k] = b.get(k, 0.0) + 1.0
    for res in RES:
        d = c["res"][res] - before.get(res, 0.0)
        if abs(d) > 1e-9:
            k = f"{res}|{job}|{p['id']}"
            b[k] = b.get(k, 0.0) + d


def _repair_made(c: dict, num) -> None:
    made = c.get("made") if isinstance(c.get("made"), dict) else {}
    c["made"] = {str(int(h)): {str(k): num(v, -1e6, 1e6) for k, v in b.items() if str(k).count("|") == 2}
                 for h, b in made.items() if str(h).lstrip("-").isdigit() and isinstance(b, dict)
                 and c["hour"] - MADE_HOURS < int(h) <= c["hour"]}
    if "made_from" in c:
        c["made_from"] = int(num(c["made_from"], 0, c["hour"], c["hour"]))


def _made(c: dict, hours: int = MADE_HOURS) -> tuple[dict, int]:
    """Totals over the last `hours` sect hours: ({(kind, job, pawn): amount}, hours actually measured)."""
    out: dict = {}
    for h, b in c["made"].items():
        if c["hour"] - hours < int(h) <= c["hour"]:
            for k, v in b.items():
                kind, job, pid = k.split("|")
                out[(kind, job, pid)] = out.get((kind, job, pid), 0.0) + v
    span = max(0, min(hours, c["hour"] - int(c.get("made_from", c["hour"] + 1)) + 1))
    return out, span


# Room play (SECT_OVERHAUL_PLAN 3.6, stage 4): posts by drag, trays to tap, rushes at a shown risk.
# A tray shows what a room's work made since dawn, or since the Master last looked. It is already in the stores
# (nothing waits in a tray, so nothing is lost by never tapping); tapping is the Master's inspection, which cheers
# the crew once a room a day (decided by the owner: +3 mood, nothing else).
TRAY_OF = {"fields": (("farm", "rice"),), "alchemy": (("craft", "pills"),), "spirit_vein": (("mine", "stones"),),
           "storehouse": (("wood", "wood"), ("mine", "stone"), ("forage", "herbs"))}
TRAY_DAWN = 6                       # the hour a tray's count starts again
TRAY_FULL_HOURS = 8                 # a tray this many hours in the making reads as full on the map
INSPECT_MOOD, INSPECT_HOURS = 3, 12  # the crew's thought when the Master inspects a tray (once a room a day)
POSTS = {"fields": ("farm",), "storehouse": ("wood", "mine", "forage"), "library": ("research",), "training": ("train",),
         "meditation": ("meditate",), "alchemy": ("craft",), "spirit_vein": ("mine",), "main_hall": ("build",)}
RUSH_BASE, RUSH_STEP, RUSH_DECAY, RUSH_WINDOW = 10, 15, 0.15, 48   # incident %: base, +15 a recent rush (less 15% a day), for 2 days
RUSH_CAP = 70                       # the riskiest a rush can be
RUSH_HOURS = 6                      # a rushed room delivers this many hours of its work now
RUSH_IDLE = 6                       # a room whose rush went wrong stands idle this many hours
RUSH_WOUND = (5, 15)                # health each of the crew loses when an incident is not contained (never a death)
RUSH_BUILD_BACK, RUSH_BUILD_LOSS = 2.0, 0.10   # a failed build rush: 2 hours more work, and a tenth of its materials gone


def _last_dawn(c: dict) -> int:
    return c["hour"] - ((c["hour"] - TRAY_DAWN) % 24)


def _tray_since(c: dict, room: str) -> int:
    return max(_last_dawn(c), int(c["tray_seen"].get(room, -1)))


def _room_made(c: dict, room: str, since: int) -> tuple[dict, set]:
    """What a room's jobs made after hour `since`: ({res: amount}, {pawn ids who worked there})."""
    pairs = TRAY_OF.get(room, ())
    jobs = {job for job, _ in pairs} | set(POSTS.get(room, ()))
    got: dict = {}
    who: set = set()
    for h, b in c["made"].items():
        if since < int(h) <= c["hour"]:
            for k, v in b.items():
                kind, job, pid = k.split("|")
                if (job, kind) in pairs:
                    got[kind] = got.get(kind, 0.0) + v
                if kind == "h" and job in jobs:
                    who.add(pid)
    return got, who


def trays(c: dict) -> dict:
    """{room: [(res, amount), ...]} made by that room's work since dawn (or the last inspection), largest first,
    whole units only."""
    out = {}
    for room, pairs in TRAY_OF.items():
        if not _lvl(c, room):
            continue
        got, _ = _room_made(c, room, _tray_since(c, room))
        rows = sorted(((res, got.get(res, 0.0)) for _, res in pairs), key=lambda x: -x[1])
        rows = [(res, n) for res, n in rows if n >= 1]
        if rows:
            out[room] = rows
    return out


def tray_full(c: dict, room: str) -> bool:
    return c["hour"] - _tray_since(c, room) >= TRAY_FULL_HOURS


def inspect_tray(st: dict, room: str, now: float) -> dict:
    """Tap a tray: the Master looks over what the room made. The count starts again; the crew who made it take heart
    (+INSPECT_MOOD for INSPECT_HOURS), once a room a day. Nothing is added to the stores: it is there already."""
    c = _c(st, now)
    t = trays(c).get(room)
    if not t:
        return {"ok": False, "error": "Nothing made here since the last look."}
    _, who = _room_made(c, room, _tray_since(c, room))
    crew = [p for p in c["pawns"] if p["id"] in who]
    c["tray_seen"][room] = c["hour"]
    day = _day(c)
    cheered = []
    if c["inspected"].get(room) != day and crew:
        c["inspected"][room] = day
        for p in crew:
            _think(p, "inspect_" + room, "The Master inspected our work", INSPECT_MOOD, INSPECT_HOURS, c["hour"])
        cheered = [p["name"] for p in crew]
    made = ", ".join(f"{_whole(n)} {RES_NAMES[res].lower()}" for res, n in t)
    text = (f"{_and(cheered)} {_be(len(cheered), 'is', 'are')} pleased the Master came to look (+{INSPECT_MOOD} mood for {INSPECT_HOURS} h)."
            if cheered else "The crew already showed you their work today.")
    return {"ok": True, "made": [{"res": res, "name": RES_NAMES[res].lower(), "n": _whole(n)} for res, n in t],
            "event": {"kind": "good", "title": f"{ROOMS[room]['name']}: {made} since {'dawn' if _tray_since(c, room) == c['hour'] else 'the last look'}. {text}"}}


def room_slots(c: dict, room: str) -> int:
    """How many disciples a room takes as their post."""
    lv = _lvl(c, room)
    if not lv or room not in POSTS:
        return 0
    if room == "fields":
        return 2 * lv                                  # the farmers the terraces hold (_job_open)
    if room == "main_hall":
        return HELPERS_PER_SITE * builders(c)          # helpers, two to a builder
    return 2 + lv


def posted(c: dict, room: str) -> list[dict]:
    return [p for p in c["pawns"] if p.get("post") == room]


def post_fit(c: dict, p: dict, room: str) -> str:
    """How well a disciple suits a room, for the glow while dragging: "good", "fair" or "poor"."""
    if room == "meditation":
        return "good" if p.get("root_mult", 1.0) >= 1.2 else "fair"
    skill = JOBS[POSTS[room][0]][1]
    sk = p["skills"][skill]
    return "good" if sk["lv"] >= 7 or (sk["passion"] and sk["lv"] >= 4) else "fair" if sk["lv"] >= 3 or sk["passion"] else "poor"


def set_post(st: dict, pawn_id: str, room: str, now: float) -> dict:
    """Drop a disciple on a room: that room's work becomes their first priority (their old post's falls to second),
    the rest of their priorities unchanged. An empty room clears the post."""
    c = _c(st, now)
    p = _p(c, pawn_id)
    if not p:
        return {"ok": False, "error": "Unknown disciple."}
    if not room:
        p["post"] = ""
        return {"ok": True}
    if room not in POSTS or not _lvl(c, room):
        return {"ok": False, "error": "No one can be posted there."}
    if p.get("post") == room:
        return {"ok": True}
    n = room_slots(c, room)
    if len(posted(c, room)) >= n:
        return {"ok": False, "error": f"The {ROOMS[room]['name']} is full ({n} of {n})."}
    old = p.get("post")
    for j in POSTS.get(old, ()):
        if p["prio"].get(j) == 1 and j not in POSTS[room]:
            p["prio"][j] = 2
    for j in POSTS[room]:
        p["prio"][j] = 1
    p["post"] = room
    c["flags"]["prio"] = 1
    _guide(c)
    jobs = _and([JOBS[j][0] for j in POSTS[room]])
    return {"ok": True, "event": {"kind": "good", "title": f"{p['name']} now works at the {ROOMS[room]['name']} ({jobs} first)."}}


def rush_crew(c: dict, target: str) -> list[dict]:
    """Who a rush leans on: the room's posted disciples at home, else whoever worked there today. For a build, the
    disciples with Build as a first or second priority."""
    home = [p for p in c["pawns"] if p["away_until"] <= c["hour"]]
    if target == "build":
        return [p for p in home if p["prio"].get("build") in (1, 2)]
    crew = [p for p in home if p.get("post") == target]
    if not crew:
        _, who = _room_made(c, target, c["hour"] - 24)
        crew = [p for p in home if p["id"] in who]
    return crew


def _crew_skill(c: dict, target: str, crew: list[dict]) -> float:
    skill = "build" if target == "build" else JOBS[POSTS[target][0]][1]
    return sum(p["skills"][skill]["lv"] for p in crew) / len(crew) if crew else 7.0


def rush_rows(c: dict, target: str) -> list[tuple[str, int]]:
    """The chance of an incident if `target` (a room, or "build") is rushed now, as a ledger of percentage points."""
    rows = [("Any rush risks an incident", RUSH_BASE)]
    for r in c["rushes"]:
        ago = c["hour"] - int(r["h"])
        if r["k"] == target and 0 <= ago < RUSH_WINDOW:
            rows.append((f"Rushed {_n(ago, 'hour')} ago", int(round(RUSH_STEP * (1 - RUSH_DECAY * ago / 24.0)))))
    crew = rush_crew(c, target)
    above = _crew_skill(c, target, crew) - 7
    if crew and above >= 1:
        rows.append((f"A skilled crew (skill {_f(above + 7)})", -int(above)))
    total = sum(v for _, v in rows)
    if total > RUSH_CAP:
        rows.append(("The risk goes no higher", RUSH_CAP - total))
    elif total < 0:
        rows.append(("Never below nothing", -total))
    return rows


def rush_chance(c: dict, target: str) -> int:
    return int(sum(v for _, v in rush_rows(c, target)))


def contain_rows(c: dict, target: str) -> list[tuple[str, int]]:
    """If an incident comes, the chance the crew contain it (the rush then pays, and they are proud of it)."""
    crew = rush_crew(c, target)
    rows = [("A crew keeps its head", 40)]
    if crew:
        rows.append((f"{_n(len(crew), 'pair of hands', 'pairs of hands')}", 5 * min(len(crew), 4)))
        d = int(round(4 * (_crew_skill(c, target, crew) - 7)))
        if d:
            rows.append((f"Their skill ({_f(_crew_skill(c, target, crew))})", d))
    total = sum(v for _, v in rows)
    if total > 90:
        rows.append(("Nothing is certain", 90 - total))
    elif total < 10:
        rows.append(("Someone always tries", 10 - total))
    return rows


def contain_chance(c: dict, target: str) -> int:
    return int(sum(v for _, v in contain_rows(c, target)))


def rush_output(c: dict, room: str) -> dict:
    """What a rushed room delivers now: RUSH_HOURS of what its work made an hour over the last day."""
    got, _ = _room_made(c, room, c["hour"] - MADE_HOURS)
    _, span = _made(c)
    return {res: v * RUSH_HOURS / max(span, 1) for res, v in got.items() if v > 0}


INCIDENTS = {"fields": ("A beast in the terraces", "boar"), "alchemy": ("A pill-furnace fire", "fire"),
             "spirit_vein": ("A qi deviation at the vein", "qi"), "storehouse": ("A stack gives way in the yard", "stack"),
             "build": ("The scaffolding gives way", "scaffold")}


def rush(st: dict, room: str, now: float, index: int = -1) -> dict:
    """Rush a room (RUSH_HOURS of its work now) or a running build (index >= 0: finished now), at the odds shown by
    rush_rows and contain_rows: the same rolls are made here. A player action only, so never while away."""
    c = _c(st, now)
    if c["seclusion"]:
        return {"ok": False, "error": "The gates are sealed."}
    if index >= 0:
        run = _running(c)
        if not 0 <= index < len(run):
            return {"ok": False, "error": "No builder is on that job."}
        b, target = run[index], "build"
        out: dict = {}
    else:
        if room not in TRAY_OF or not _lvl(c, room):
            return {"ok": False, "error": "That room cannot be rushed."}
        if int(c["room_idle"].get(room, 0)) > c["hour"]:
            return {"ok": False, "error": f"The {ROOMS[room]['name']} is still putting things right."}
        out = rush_output(c, room)
        if not out:
            return {"ok": False, "error": "No one has worked here today: there is nothing to hurry."}
        b, target = None, room
    chance, keep = rush_chance(c, target), contain_chance(c, target)
    crew = rush_crew(c, target)
    r = _rng(c, "rush", c["hour"], target, len(c["rushes"]))
    incident = r.random() * 100 < chance
    contained = incident and r.random() * 100 < keep
    c["rushes"] = [x for x in c["rushes"] if c["hour"] - int(x["h"]) < RUSH_WINDOW][-20:] + [{"k": target, "h": c["hour"]}]
    name, _ = INCIDENTS[target]
    what = ROOMS[b["room"]]["name"] if b else ROOMS[room]["name"]
    snap = _snap(c)
    if not incident or contained:
        if b:
            b["done"] = b["need"]
            _finish_build(c, b)
        for res, v in out.items():
            _add(c, res, v)
        if contained:
            for p in crew:
                _xp(p, "build" if b else JOBS[POSTS[room][0]][1], 6.0)
                _think(p, "proud", "Proud of the work", 4, 24, c["hour"])
            _scene(c, "incident", True, f"{name}, and the crew held", f"The {what} was rushed. {name}, but the crew kept their heads and saw it through.",
                   verdict="Contained", party=crew, snap=snap)
            return {"ok": True, "incident": True, "contained": True}
        got = ", ".join(f"{_whole(v)} {RES_NAMES[k].lower()}" for k, v in out.items())
        return {"ok": True, "incident": False, "event": {"kind": "good", "title": f"{what} rushed" + (f": {got}" if got else ": finished")}}
    # the incident was not contained
    if b:
        b["need"] = min(100.0, b["need"] + RUSH_BUILD_BACK)
        b["cost"] = {k: v * (1 - RUSH_BUILD_LOSS) for k, v in b.get("cost", {}).items()}
        text = f"The {what} loses ground: {_n(int(RUSH_BUILD_BACK), 'hour')} more work, and a tenth of its materials are spoiled."
    else:
        c["room_idle"][room] = c["hour"] + RUSH_IDLE
        text = f"The rushed work is lost and the {what} stands idle for {RUSH_IDLE} hours."
    for p in crew:
        p["health"] = max(min(p["health"], 5.0), p["health"] - r.uniform(*RUSH_WOUND) * hurt_mult(p, c))
    if crew:
        text += f" {_and([p['name'] for p in crew])} {_be(len(crew), 'was', 'were')} hurt. No one died."
    _scene(c, "incident", False, name, text, verdict="An incident", party=crew, snap=snap)
    _letter(c, "bad", name, text)
    return {"ok": True, "incident": True, "contained": False}


def hall_opens(c: dict, target: int) -> list[str]:
    """What raising the Main Hall to `target` opens, from HALL_LADDER (and the builders and beds that come with it)."""
    x = HALL_LADDER[target]
    opens = [f"Room for {_n(2, 'more disciple', 'more disciples')}: {3 + 2 * target} in all, from {3 + 2 * (target - 1)}"]
    if x.get("rooms"):
        opens.append("New rooms: " + _and([ROOMS[k]["name"] for k in x["rooms"]]))
    if target in BUILDER_HALLS:
        opens.append(f"A builder more: {BUILDERS + sum(1 for h in BUILDER_HALLS if h <= target)} in all")
    was = HALL_LADDER[target - 1]["cap"]
    if x["cap"] > was:
        held = [ROOMS[k]["name"] for k in ROOMS
                if k != "main_hall" and _lvl(c, k) + sum(1 for b in c["builds"] if b["room"] == k) >= was and was < ROOMS[k]["max"]]
        opens.append(f"Other rooms up to level {x['cap']}" + (f" ({_and(held)} {_be(len(held))} waiting on it)" if held else ""))
    opens.extend(x.get("more", ()))
    opens.append("+4 fame as the valley sees it rise")
    return opens


def hall_next(c: dict) -> dict:
    """The next Main Hall level, what it opens and the three-rooms checklist, for the card on the home view. At the
    top of the ladder the card says so ("top") and lists what the Hall gave."""
    lvl = _lvl(c, "main_hall")
    top = ROOMS["main_hall"]["max"]
    if lvl >= top:
        return {"level": top, "top": True, "opens": [f"{builders(c)} builders, room for {pawn_cap(c)} disciples, other rooms up to level {room_cap(c)}"],
                "check": [], "cost": {}, "queued": False, "hours": 0, "left": 0.0, "free": False, "pct": 100.0, "affordable": False,
                "short": {}, "ready": False}
    queued = [b for b in c["builds"] if b["room"] == "main_hall"]
    target = lvl + 1
    check = [] if queued else hall_rooms_check(c, target)
    ready = all(ok for _, _, ok in check)
    cost = queued[0]["cost"] if queued else room_cost(c, "main_hall", lvl)
    short = {k: v - c["res"][k] for k, v in cost.items() if c["res"][k] < v}
    free = len(c["builds"]) < builders(c)
    return {"level": target, "top": False, "opens": hall_opens(c, target), "check": check, "need_lv": target - 1, "ready": ready,
            "cost": cost, "queued": bool(queued), "hours": build_hours("main_hall", target),
            "left": build_left(c, queued[0]) if queued else 0.0, "free": free,
            "pct": 100.0 * queued[0]["done"] / queued[0]["need"] if queued else 0.0,
            "affordable": not queued and ready and not short and free, "short": short}


def _id_names(c: dict, ids) -> str:
    known = [str((_p(c, i) or {}).get("name") or "") for i in ids]
    names = [n for n in known if n]
    gone = len(known) - len(names)
    return ", ".join(names + ([f"{gone} who left"] if gone else []))


def res_rates(c: dict) -> dict:
    """Per resource: what work made (or used) in the last day, by job and by whom, what upkeep spends a day, and the net."""
    totals, span = _made(c)
    spend = {res: [] for res in RES}
    for res, label, n in upkeep(c):
        spend[res].append((label, n))
    out = {}
    for res in RES:
        jobs: dict = {}
        for (kind, job, pid), v in totals.items():
            if kind == res and job in JOBS:
                who = jobs.setdefault(job, {})
                who[pid] = who.get(pid, 0.0) + v
        made = sorted(((f"{JOBS[j][0]}: {_id_names(c, sorted(w, key=lambda i: -abs(w[i])))}", sum(w.values())) for j, w in jobs.items()),
                      key=lambda x: -x[1])
        made_n = sum(v for _, v in made)
        spent_n = sum(n for _, n in spend[res])
        out[res] = {"made": made, "spent": spend[res], "made_n": made_n, "spent_n": spent_n, "net": made_n - spent_n,
                    "hours": span, "full": span >= MADE_HOURS}
    return out


def _pawn_view(c: dict, p: dict) -> dict:
    hour = c["hour"]
    need = step_need(int(p["step"]))
    # A direct disciple only meditates, trains and researches, with meditation always first: work gathers its
    # trickle of qi only when Train or Research is set level with it (priority 1) and can be done.
    direct = bool(p.get("direct"))
    trickle = not direct or any(p["prio"].get(j) == 1 and _job_open(c, j, {}) for j in ("train", "research"))
    rank = ("Sect Master" if p.get("master") else "Direct Disciple" if direct and rank_of(p) < 2
            else lore.RANKS[rank_of(p)])
    return {
        "id": str(p["id"]), "name": str(p["name"]), "age": _f(p["age"]), "master": bool(p.get("master")),
        "root": str(p["root"]), "traits": [{"name": str(t), "text": TRAITS.get(t, "")} for t in p["traits"]],
        "skills": [{"id": s, "name": SKILL_NAMES[s], "lv": _f(p["skills"][s]["lv"]), "passion": _f(p["skills"][s]["passion"])} for s in SKILLS],
        "food": _f(p["food"]), "rest": _f(p["rest"]), "joy": _f(p["joy"]), "mood": _f(p["mood"]), "health": _f(p["health"]),
        "thoughts": [{"label": str(t["label"]), "v": _f(t["v"])} for t in p["thoughts"] if t["until"] > hour],
        "step": _f(p["step"]), "realm": REALMS[int(p["step"]) // 4], "stage": STAGES[int(p["step"]) % 4],
        "qi": _f(p["qi"]), "qi_need": _f(need), "qi_pct": _f(min(100.0, 100.0 * float(p["qi"]) / need)),
        "prio": {j: _f(p["prio"].get(j, 0)) for j in JOBS}, "doing": str(p["doing"]),
        "post": str(p.get("post") or ""), "fit": {r: post_fit(c, p, r) for r in POSTS if _lvl(c, r)},
        "broken": p["break_until"] > hour, "inspired": p["inspired_until"] > hour, "sick": p["sick_until"] > hour,
        "power": _f(combat_power(c, p)),
        "rank": rank, "realm_rank": lore.RANKS[rank_of(p)], "title": str(p.get("title") or ""),
        "away": p["away_until"] > hour, "ready": ready(p),
        "tribulation": int(p["step"]) // 4 + 1 >= 3, "next_realm": REALMS[min(len(REALMS) - 1, int(p["step"]) // 4 + 1)],
        "chance": _f(bt_chance(c, p)) if ready(p) else 0,
        "odds": [{"label": str(a), "v": _f(b)} for a, b in bt_odds(c, p)] if ready(p) else [],
        "mood_why": [{"label": str(a), "v": _f(b)} for a, b in mood_mods(c, p)],
        "arts": [lore.MANUALS[m]["name"] for m in (_manual(c, p, k)[1] for k in lore.MANUAL_BONUS) if m],
        **dao.pawn_view(c, p),
        "origin": str(p.get("origin") or ""), "element": str(p["element"]), "direct": bool(p.get("direct")),
        "qi_why": [{"label": str(a), "x": _f(b, 2)} for a, b in qi_rate(c, p)], "qi_x": _f(math.prod(b for _, b in qi_rate(c, p)), 2),
        "qi_work": _f(WORK_QI, 2) if trickle else 0,
        "qi_work_label": ("An hour of training or research instead of meditation gathers a share of this" if direct
                          else "An hour of work instead of meditation gathers a share of this"),
        "artifact": ({"id": str(artifact_of(c, p)["id"]), "name": str(artifact_of(c, p)["name"]), "text": artifact_text(artifact_of(c, p))}
                     if artifact_of(c, p) else None),
        "bonds": sorted(({"name": str(o["name"]), "v": _f(bond(c, p, o)), "kind": pair_kind(c, p, o)}
                         for o in c["pawns"] if o is not p and abs(bond(c, p, o)) >= 8), key=lambda x: -abs(x["v"]))[:8],
    }


def stalled_days(c: dict, p: dict) -> int:
    """Whole days since a disciple last sat down to meditate."""
    return max(0, (c["hour"] - int(p["sat_at"])) // 24) if p["sat_at"] >= 0 else 0


def stall_advice(c: dict, p: dict) -> tuple[str, int]:
    """What would get a stalled disciple meditating, said exactly: (advice, the Meditate priority to set; 0 = none)."""
    if p.get("direct"):
        return "As a direct disciple they meditate first whenever they are fit to work; rest, food and a bed will bring them back to it.", 0
    # their standing work: building comes and goes with the queue, so it is not what to measure meditation against
    chores = {j: lv for j, lv in p["prio"].items() if j in JOBS and j not in ("meditate", "build") and lv and _job_open(c, j, {})}
    med = int(p["prio"].get("meditate", 0))
    work = p.get("work") if p.get("work") in chores else _best_chore(c, p, chores, {})      # the chore that has been taking their hours
    if not work:
        if med:
            return "They have nothing else to do, so they have been too hurt, tired or unhappy to sit. Food, a bed and rest come first.", 0
        return "Their Meditate priority is off: set it to 1 in Work.", 1
    lv, name = chores[work], JOBS[work][0]
    if not med or med > lv:
        return (f"Their Meditate is {med or 'off'}, behind their {name} at {lv}. Set Meditate to {lv} in Work: at the same priority as "
                f"their work they meditate {med_share(0)} their working hours, one step higher {med_share(1)}, two or more {med_share(2)}. "
                f"A store under {int(LOW_STORE_DAYS)} days of use always comes first.", lv)
    if work in STORE_OF and store_days(c, STORE_OF[work]) < LOW_STORE_DAYS:
        res = STORE_OF[work]
        return (f"Their Meditate ({med}) is level with their {name} ({lv}), but {RES_NAMES[res].lower()} is under {int(LOW_STORE_DAYS)} days of use "
                f"({_f(store_days(c, res), 1)}), and a short store always comes first. Put more hands on {name}.", 0)
    return "Their Meditate is already level with their work; they have been too hurt, tired or unhappy to sit. Food, a bed and rest come first.", 0


def _alerts(c: dict) -> list[dict]:
    """What needs the player's eye right now, most urgent first."""
    out = []
    eat = max(0.5, sum(v for res, label, v in upkeep(c) if res == "rice" and "spoiling" not in label))
    days = c["res"]["rice"] / eat
    if days < 3:
        out.append({"kind": "bad", "text": f"About {int(days)} day{'s' if int(days) != 1 else ''} of rice left."})
    fever = [x for x in c["later"] if x.get("kind") == "plague_tick"]
    if fever:
        ill = [p["name"] for p in (_p(c, i) for i in fever[0].get("sick", [])) if p]
        if ill:
            out.append({"kind": "bad", "text": f"Fever: {', '.join(ill[:3])}{' and others' if len(ill) > 3 else ''} in bed, "
                                               f"{int(fever[0].get('left', 1))} more day{'s' if int(fever[0].get('left', 1)) != 1 else ''} of it."})
    if blight_left(c):
        rows = farm_rows(c)
        now = math.prod(x for _, x in rows)
        out.append({"kind": "bad", "text": f"Blight on the terraces: {now:.2f} rice per farmer-hour instead of {now / rows[-1][1]:.2f}, "
                                           f"{_f(blight_left(c) / 24.0, 1)} more days."})
    day = _day(c)
    to_winter = (3 * DAYS_PER_SEASON - day % (4 * DAYS_PER_SEASON)) % (4 * DAYS_PER_SEASON)
    if 0 < to_winter <= 6 and c["res"]["rice"] < eat * WINTER_HUNGER * DAYS_PER_SEASON:
        out.append({"kind": "bad", "text": f"Winter is {to_winter} day{'s' if to_winter != 1 else ''} away and the granary will not last it. Nothing grows in winter."})
    for p in c["pawns"]:
        if ready(p):
            out.append({"kind": "good", "text": f"{p['name']} is ready to attempt {REALMS[p['step'] // 4 + 1]}.", "pawn": str(p["id"])})
    stalled = sorted((p for p in c["pawns"] if stalled_days(c, p) >= STALL_DAYS and not ready(p)), key=lambda p: -stalled_days(c, p))
    for p in stalled[:2]:
        d = stalled_days(c, p)
        advice, level = stall_advice(c, p)
        out.append({"kind": "info", "pawn": str(p["id"]), "prio": level,
                    "text": f"{p['name']} has not meditated in {d} days and is gathering only a trickle of qi from work. {advice}"})
    if len(stalled) > 2:
        out.append({"kind": "info", "text": f"{len(stalled) - 2} more disciple{'s have' if len(stalled) > 3 else ' has'} not meditated in {STALL_DAYS}+ days."})
    low = [p["name"] for p in c["pawns"] if p["mood"] < 25 and p["break_until"] <= c["hour"]]
    if low:
        out.append({"kind": "bad", "text": f"{' and '.join(low[:3])} {'is' if len(low) == 1 else 'are'} close to a qi deviation (very low mood)."})
    if len(c["pawns"]) > beds(c):
        out.append({"kind": "info", "text": f"{len(c['pawns']) - beds(c)} disciple{'s' if len(c['pawns']) - beds(c) != 1 else ''} without a bed. Raise the Dormitory."})
    if _lvl(c, "library") and not c["research"]["current"] and len(c["research"]["done"]) < len(RESEARCH):
        out.append({"kind": "info", "text": "The Scripture Pavilion is idle. Choose something to research."})
    return (dao.alerts(c) + out)[:7]


def view(st: dict, now: float) -> dict:
    c = _c(st, now)
    today = _today(st, now)
    day = _day(c)
    rooms = []
    tray = trays(c)
    free = len(c["builds"]) < builders(c)
    for rid, r in ROOMS.items():
        level = _lvl(c, rid)
        queued = sum(1 for b in c["builds"] if b["room"] == rid)
        nxt = level + queued
        cost = room_cost(c, rid, nxt) if nxt < r["max"] else None
        locked = build_block(c, rid, nxt) if cost else ""
        rooms.append({"id": rid, "name": r["name"], "effect": r["effect"], "level": level, "max": r["max"], "open": level > 0,
                      "hours": _f(build_hours(rid, nxt + 1)) if cost else 0,
                      "queued": queued, "cost": {k: _f(v) for k, v in cost.items()} if cost else None, "locked": locked,
                      "lock_short": build_block_short(c, rid, nxt) if locked else "",
                      "affordable": bool(cost) and not locked and free and all(c["res"][k] >= v for k, v in cost.items()),
                      "tray": [{"res": res, "name": RES_NAMES[res].lower(), "n": _whole(n)} for res, n in tray.get(rid, [])],
                      "tray_full": bool(tray.get(rid)) and tray_full(c, rid),
                      "slots": room_slots(c, rid), "posted": [str(p["id"]) for p in posted(c, rid)],
                      "post_jobs": [JOBS[j][0] for j in POSTS.get(rid, ())] if level else [],
                      "rush": _rush_view(c, rid) if rid in TRAY_OF and level else None})
    last = c["last_study_day"]
    gap = (_date(today) - _date(last)).days if last else 0
    lost = bool(last) and not c["seclusion"] and gap > 1 and c["grace"] < gap - 1
    pending = c["pending"]
    cur = c["research"]["current"]
    m = _master(c)
    rates = res_rates(c)
    return {
        "name": str(c["name"]), "founded": bool(c["name"]), "master": str(m["name"]) if m else "",
        "hour": _f(c["hour"]), "day": day + 1, "when": calendar_label(day), "hod": _f(c["hour"] % 24), "season": SEASONS[_season(c)],
        "year": day // (DAYS_PER_SEASON * 4) + 1, "season_day": day % DAYS_PER_SEASON + 1,
        "storyteller": str(c["storyteller"]),
        "storytellers": [{"id": k, "name": v["name"], "blurb": v["blurb"]} for k, v in STORYTELLERS.items()],
        "res": [{"id": k, "name": RES_NAMES[k], "n": _whole(c["res"][k]),
                 "cap": _f(_cap(c)) if k in ("rice", "wood", "stone", "herbs") else None,
                 "made": [{"label": str(a), "n": _f(b, 1)} for a, b in rates[k]["made"]],
                 "spent": [{"label": str(a), "n": _f(b, 1)} for a, b in rates[k]["spent"]],
                 "made_n": _f(rates[k]["made_n"], 1), "spent_n": _f(rates[k]["spent_n"], 1), "net": _f(rates[k]["net"], 1),
                 "hours": _f(rates[k]["hours"]), "full": bool(rates[k]["full"])} for k in RES],
        "insight": _f(c["insight"]), "wealth": _f(wealth(c)), "defense": _f(defense(c)),
        **dao.view(c),
        "fame": _f(c["fame"]), "alerts": _alerts(c), "scenes": [_scene_view(x) for x in c["scenes"][-SCENE_CAP:]], "faces": list(FACES), "renown": renown(float(c["fame"])),
        "guide": ({"text": GUIDE[c["guide"]["i"]][1], "n": _f(c["guide"]["i"]) + 1, "total": len(GUIDE)}
                  if not c["guide"]["skip"] and c["guide"]["i"] < len(GUIDE) and c["name"] else None),
        "works": [{"id": w["id"], "name": w["name"], "text": w["text"], "done": bool(w["done"]),
                   "lines": [{"text": str(t), "ok": bool(ok)} for t, ok in w["lines"]]} for w in works(c)],
        "quest": ({"title": str(c["quest"]["title"]), "res": RES_NAMES[c["quest"]["res"]].lower(), "n": _f(c["quest"]["n"]),
                   "have": _whole(c["res"][c["quest"]["res"]]), "days_left": max(0, _f((c["quest"]["due"] - c["hour"]) / 24.0, 1)),
                   "ready": c["res"][c["quest"]["res"]] >= c["quest"]["n"]} if c["quest"] else None),
        "places": [{"id": k, "name": v["name"], "hours": v["hours"], "text": v["text"]} for k, v in PLACES.items()],
        "trip": any(x["kind"] == "trip_return" for x in c["later"]),
        "artifacts": [{"id": str(a["id"]), "name": str(a["name"]), "text": artifact_text(a), "origin": str(a["origin"]),
                       "owner": str((_p(c, a["owner"]) or {}).get("name", "")) if a["owner"] else ""} for a in c["artifacts"]],
        "can_forge": _lvl(c, "alchemy") > 0 and all(c["res"][k] >= v for k, v in FORGE_COST.items()), "has_forge": _lvl(c, "alchemy") > 0,
        "direct_cap": direct_cap(c), "direct_n": sum(1 for x in c["pawns"] if x.get("direct")),
        "season_element": lore.SEASON_ELEMENT[_season(c)],
        "annals": [{"year": _f(e["hour"]) // (24 * DAYS_PER_SEASON * 4) + 1, "day": _f(e["hour"]) // 24 + 1, "when": calendar_label(_f(e["hour"]) // 24), "text": str(e["text"])}
                   for e in reversed(c["annals"][-80:])],
        "sects": [{"id": str(x["id"]), "name": str(x["name"]), "kind": str(x["kind"]), "rel": _f(x["rel"]), "stance": stance(float(x["rel"])),
                   "young": str(x["young"]), "ally": bool(x.get("ally"))} for x in c["sects"]],
        "manuals": [{"id": k, "name": lore.MANUALS[k]["name"], "grade": lore.GRADES[lore.MANUALS[k]["grade"]],
                     "kind": lore.MANUAL_KIND[lore.MANUALS[k]["kind"]], "demonic": bool(lore.MANUALS[k].get("demonic")),
                     "bonus": _f(100 * lore.MANUAL_BONUS[lore.MANUALS[k]["kind"]][lore.MANUALS[k]["grade"]]),
                     "rank": "Any rank" if lore.MANUALS[k].get("demonic") else lore.RANKS[lore.MANUALS[k]["grade"]]}
                    for k in c["manuals"] if k in lore.MANUALS],
        "treasures": [{"id": k, "name": lore.TREASURES[k]["name"], "text": lore.TREASURES[k]["text"]} for k in c["treasures"] if k in lore.TREASURES],
        "beast": {"name": str(c["beast"]["name"]), "power": _f(beast_power(c))} if c["beast"] else None,
        "beds": beds(c), "pawn_cap": pawn_cap(c), "graves": _f(c["graves"]),
        "food_days": _f(c["res"]["rice"] / max(1, len(c["pawns"])), 1),
        "upkeep": [{"res": res, "label": str(label), "n": _f(n, 1)} for res, label, n in upkeep(c)],
        "farm_yield": {"rows": [{"label": str(label), "x": _f(x, 2)} for label, x in farm_rows(c)],
                       "per_hour": _f(math.prod(x for _, x in farm_rows(c)), 2), "blight_days": _f(blight_left(c) / 24.0, 1)},
        "rooms": rooms,
        "hall_next": _hall_view(hall_next(c)),
        "builds": [_build_view(c, i, b) for i, b in enumerate(c["builds"])],
        "builders": {"n": builders(c), "busy": len(_running(c)), "rows": [{"label": str(a), "n": _f(b)} for a, b in builder_rows(c)],
                     "next_hall": next((h for h in BUILDER_HALLS if h > _lvl(c, "main_hall")), 0),
                     "master_hours": max(0, _f(c["master_builds_until"] - c["hour"])), "blueprints": _f(c["blueprints"]["n"]),
                     "blueprint_cut": _f(BLUEPRINT_CUT * 100), "away_secs": _f(SECS_PER_HOUR_OFFLINE)},
        "pawns": [_pawn_view(c, p) for p in c["pawns"]],
        "jobs": [{"id": j, "name": v[0], "skill": SKILL_NAMES[v[1]]} for j, v in JOBS.items()],
        "research": {"current": str(cur), "progress": _f(c["research"]["progress"]),
                     "items": [{"id": k, "name": v["name"], "cost": v["cost"], "effect": v["effect"], "done": k in c["research"]["done"]}
                               for k, v in RESEARCH.items()],
                     "has_library": _lvl(c, "library") > 0,
                     "rows": [{"label": str(a), "v": str(b)} for a, b in research_rows(c)]},
        "pending": ({"title": str(pending["title"]), "text": str(pending["text"]), "kind": str(pending["kind"]),
                     "options": dao.annotate(c, pending)} if pending else None),
        "log": [{"hour": _f(e["hour"]), "day": _f(e["hour"]) // 24 + 1, "when": calendar_label(_f(e["hour"]) // 24), "kind": str(e["kind"]), "title": str(e["title"]), "text": str(e["text"])}
                for e in reversed(c["log"][-30:])],
        # study habit
        "streak": 0 if lost else _f(c["streak"]), "best_streak": _f(c["best_streak"]), "studied_today": last == today,
        "streak_at_risk": bool(last) and not c["seclusion"] and gap >= 1 and not lost and c["streak"] > 0,
        "grace": _f(c["grace"]), "seclusion": bool(c["seclusion"]),
        "week": {"days": len(c["week"]["days"]) if c["week"]["id"] else 0, "goal": WEEK_GOAL},
        "realm": REALMS[int(m["step"]) // 4] if m else REALMS[0], "stage": STAGES[int(m["step"]) % 4] if m else STAGES[0],
    }


def _build_view(c: dict, i: int, b: dict) -> dict:
    running = i < builders(c)
    rows = build_rate_rows(c, b) if running else []
    return {"room": b["room"], "name": ROOMS[b["room"]]["name"], "level": _lvl(c, b["room"]) + 1 + sum(1 for x in c["builds"][:i] if x["room"] == b["room"]),
            "pct": _f(100.0 * b["done"] / b["need"]), "need": _f(b["need"], 1), "done": _f(min(b["done"], b["need"]), 1),
            "running": running, "left": _f(build_left(c, b), 1), "rate": _f(sum(x for _, x in rows), 2) if rows else 0,
            "rows": [{"label": str(a), "x": _f(x, 2)} for a, x in rows], "blue": _f(b.get("blue", 0.0), 1),
            "rush": _rush_view(c, "build") if running else None}


def _rush_view(c: dict, target: str) -> dict:
    out = rush_output(c, target) if target != "build" else {}
    return {"chance": _f(rush_chance(c, target)), "rows": [{"label": str(a), "v": _f(v)} for a, v in rush_rows(c, target)],
            "contain": _f(contain_chance(c, target)), "contain_rows": [{"label": str(a), "v": _f(v)} for a, v in contain_rows(c, target)],
            "out": [{"res": k, "name": RES_NAMES[k].lower(), "n": _whole(v)} for k, v in out.items() if v >= 1],
            "crew": [str(p["name"]) for p in rush_crew(c, target)],
            "idle": max(0, _f(int(c["room_idle"].get(target, 0)) - c["hour"])) if target != "build" else 0,
            "incident": INCIDENTS[target][0]}


def _hall_view(h: dict) -> dict:
    return {"level": _f(h["level"]), "top": bool(h["top"]), "opens": [str(x) for x in h["opens"]], "cost": {k: _f(v) for k, v in h["cost"].items()},
            "check": [{"name": str(n), "lv": _f(lv), "ok": bool(ok)} for n, lv, ok in h["check"]], "need_lv": _f(h.get("need_lv", 0)),
            "ready": bool(h["ready"]),
            "queued": bool(h["queued"]), "pct": _f(h["pct"]), "affordable": bool(h["affordable"]), "hours": _f(h["hours"]),
            "left": _f(h["left"], 1), "free": bool(h["free"]),
            "short": {k: _f(math.ceil(v)) for k, v in h["short"].items()}}


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
        shell = {"colony": c, "settings": {"tz_offset_min": 0}}
        _c(shell, now)
        _repair(c)
        probe = {"colony": copy.deepcopy(c), "settings": {"tz_offset_min": 0}}
        pc = _c(probe, now)
        if pc["pending"]:
            try:
                for o in pc["pending"]["options"]:
                    trial = {"colony": copy.deepcopy(c), "settings": {"tz_offset_min": 0}}
                    resolve(trial, o["id"], now)
                    view(trial, now)
            except Exception:
                c["pending"] = pc["pending"] = None
        for _ in range(26):
            _hour(pc, quiet=True)
        pc["seclusion"] = False
        for _ in range(60):
            if pc["pending"]:
                resolve(probe, pc["pending"]["options"][-1]["id"], now)
            _hour(pc, quiet=False)
        view(probe, now)
    except Exception:
        return {}
    c.setdefault("last_real", now)
    c["last_real"] = min(float(c["last_real"]), now)
    return c


def _repair(c: dict) -> None:
    """Force a loaded colony into shapes the sim can run. Raises on anything hopeless."""
    def num(v, lo, hi, default=0.0):
        return max(lo, min(hi, float(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else default
    if c.get("storyteller") not in STORYTELLERS:
        c["storyteller"] = "balanced"
    c["hour"] = int(c["hour"])
    if not isinstance(c["pawns"], list) or len(c["pawns"]) > 60 or not all(isinstance(p, dict) for p in c["pawns"]):
        raise ValueError("pawns")
    for p in c["pawns"]:
        p["step"] = int(num(p.get("step"), 0, MAX_STEP))
        p["traits"] = [t for t in p.get("traits", []) if t in TRAITS][:3]
        sk = p.get("skills") if isinstance(p.get("skills"), dict) else {}
        p["skills"] = {k: {"lv": int(num((sk.get(k) or {}).get("lv"), 0, 20)), "xp": num((sk.get(k) or {}).get("xp"), 0, 1e6),
                           "passion": int(num((sk.get(k) or {}).get("passion"), 0, 2))} for k in SKILLS}
        for k in ("food", "rest", "joy", "mood", "health"):
            p[k] = num(p.get(k), 0, 100, 50.0)
        for k in ("qi", "break_until", "inspired_until", "sick_until", "away_until", "resolve_until", "bt_tries", "age"):
            p[k] = num(p.get(k), 0, 1e9)
        p["sat_at"] = int(num(p.get("sat_at"), -1, 1e9, -1))
        p["work"] = p.get("work") if p.get("work") in JOBS else ""
        p["post"] = p.get("post") if p.get("post") in POSTS else ""
        p["root_mult"] = num(p.get("root_mult"), 0.3, 3.0, 1.0)
        p["prio"] = {j: int(num((p.get("prio") or {}).get(j), 0, 4)) for j in JOBS}
        p["thoughts"] = [t for t in p.get("thoughts", []) if isinstance(t, dict) and isinstance(t.get("k"), str)
                         and isinstance(t.get("v"), (int, float)) and isinstance(t.get("until"), (int, float))][:40]
        p["direct"] = bool(p.get("direct")) and not p.get("master")
        p["element"] = p.get("element") if p.get("element") in lore.ELEMENTS else "earth"
        for k in ("id", "name", "root", "doing", "away_kind", "title", "origin"):
            p[k] = str(p.get(k) or "")
    if c["pawns"] and not any(p.get("master") for p in c["pawns"]):
        c["pawns"][0]["master"] = True
    pd = c.get("pending")
    if not (isinstance(pd, dict) and pd.get("kind") in _RESOLVERS and isinstance(pd.get("title"), str) and isinstance(pd.get("text"), str)
            and isinstance(pd.get("options"), list) and pd["options"]
            and all(isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("label"), str) for o in pd["options"])):
        c["pending"] = None
    c["manuals"] = [m for m in c["manuals"] if m in lore.MANUALS] if isinstance(c["manuals"], list) else ["breathing"]
    c["treasures"] = [t for t in c["treasures"] if t in lore.TREASURES] if isinstance(c["treasures"], list) else []
    b = c.get("beast")
    c["beast"] = {"name": str(b.get("name") or "Spirit beast"), "born": int(num(b.get("born"), 0, 1e9))} if isinstance(b, dict) else None
    c["later"] = [x for x in c["later"] if isinstance(x, dict) and isinstance(x.get("at"), (int, float)) and isinstance(x.get("kind"), str)][:40] \
        if isinstance(c["later"], list) else []
    ok = isinstance(c["sects"], list) and all(
        isinstance(x, dict) and isinstance(x.get("id"), str) and isinstance(x.get("name"), str) and isinstance(x.get("young"), str)
        and x.get("kind") in lore.KIND_START_REL and isinstance(x.get("rel"), (int, float)) and isinstance(x.get("power"), (int, float))
        for x in c["sects"])
    if not ok:
        c["sects"] = []
    for x in c["sects"]:
        x["power"] = num(x["power"], 0.5, 2.0, 1.0)
    c["flags"] = c["flags"] if isinstance(c["flags"], dict) else {}
    c["bonds"] = {str(k): num(v, -100, 100) for k, v in c["bonds"].items() if "|" in str(k)} if isinstance(c["bonds"], dict) else {}
    c["annals"] = [{"hour": int(num(x.get("hour"), 0, 1e9)), "text": str(x.get("text") or "")} for x in c["annals"] if isinstance(x, dict)][-300:] \
        if isinstance(c["annals"], list) else []
    g = c["guide"] if isinstance(c["guide"], dict) else {}
    c["guide"] = {"i": int(num(g.get("i"), 0, len(GUIDE))), "skip": bool(g.get("skip"))}
    q = c.get("quest")
    c["quest"] = ({"kind": str(q.get("kind") or ""), "res": q["res"], "n": num(q.get("n"), 1, 1e5, 1.0), "due": num(q.get("due"), 0, 1e9),
                   "days": int(num(q.get("days"), 1, 99, 7.0)), "src": str(q.get("src") or ""), "title": str(q.get("title") or "A promise")}
                  if isinstance(q, dict) and q.get("res") in RES else None)
    c["festival"] = str(c.get("festival") or "")
    b = c.get("blight")
    c["blight"] = {"until": int(num(b.get("until"), 0, 1e9)), "x": num(b.get("x"), 0.2, 1.0, 0.5)} if isinstance(b, dict) else None
    t = c.get("tally") if isinstance(c.get("tally"), dict) else {}
    c["tally"] = {"stolen": num(t.get("stolen"), 0, 1e9), "plague_dead": int(num(t.get("plague_dead"), 0, 1e6))}
    _repair_scenes(c, num)
    _repair_made(c, num)
    dao.repair(c, num)
    ids = {p["id"] for p in c["pawns"]}
    c["artifacts"] = [{"id": str(a.get("id") or f"a{i}"), "name": str(a.get("name") or "Nameless artifact"), "kind": a["kind"], "q": int(num(a.get("q"), 0, 2)),
                       "origin": str(a.get("origin") or ""), "owner": a.get("owner") if a.get("owner") in ids else ""}
                      for i, a in enumerate(c["artifacts"]) if isinstance(a, dict) and a.get("kind") in lore.ARTIFACT_KINDS][:40] \
        if isinstance(c.get("artifacts"), list) else []
    c["next_art"] = int(num(c.get("next_art"), 0, 1e6)) + len(c["artifacts"])
    c["fame"] = num(c.get("fame"), 0, 1e7)
    c["adapt"] = num(c.get("adapt"), 0.55, 1.25, 0.85)
    r = c["research"]
    r["done"] = [t for t in r.get("done", []) if t in RESEARCH]
    r["current"] = r.get("current") if r.get("current") in RESEARCH else ""
    r["progress"] = num(r.get("progress"), 0, 1e6)
    r["banked"] = {k: num(v, 0, 1e6) for k, v in (r.get("banked") or {}).items() if k in RESEARCH}
    c["rooms"] = {k: int(num(v, 0, ROOMS[k]["max"])) for k, v in c["rooms"].items() if k in ROOMS}
    c["builds"] = [x for x in c["builds"] if isinstance(x, dict) and x.get("room") in ROOMS
                   and isinstance(x.get("need"), (int, float)) and x["need"] > 0 and isinstance(x.get("done"), (int, float))][:20]
    for i, x in enumerate(c["builds"]):
        # a job from before builders (`need` in disciple work-hours) keeps the share it had done, on the builders' clock
        lv = _lvl(c, x["room"]) + 1 + sum(1 for y in c["builds"][:i] if y["room"] == x["room"])
        need = build_hours(x["room"], lv)
        if not x.get("slotted"):
            x["done"] = need * max(0.0, min(1.0, float(x["done"]) / float(x["need"])))
            x["need"], x["slotted"] = need, 1
        x["need"] = num(x["need"], 0.5, 100.0, need)
        x["done"] = num(x["done"], 0.0, x["need"])
        x["blue"] = num(x.get("blue"), 0.0, 100.0)
        x["crew"] = [[str(a[0]), int(num(a[1], 0, 20)), num(a[2], 0, 5)] for a in x.get("crew", []) if isinstance(a, list) and len(a) == 3][:6]
        x["crew_all"] = [[str(a[0])] for a in x.get("crew_all", []) if isinstance(a, list) and a][:12]
        x.pop("boost", None), x.pop("crew_now", None)
        x["cost"] = {k: num(v, 0, 1e6) for k, v in x.get("cost", {}).items() if k in RES} if isinstance(x.get("cost"), dict) else {}
    bp = c.get("blueprints") if isinstance(c.get("blueprints"), dict) else {}
    c["blueprints"] = {"n": int(num(bp.get("n"), 0, BLUEPRINT_BANK)), "day": str(bp.get("day") or "")[:10]}
    c["master_builds_until"] = int(num(c.get("master_builds_until"), 0, 1e9))
    c[HELD_SECS] = num(c.get(HELD_SECS), 0, MAX_OFFLINE_HOURS * SECS_PER_HOUR_OFFLINE)
    for k in ("tray_seen", "inspected", "room_idle"):
        d = c.get(k) if isinstance(c.get(k), dict) else {}
        c[k] = {r: int(num(v, -1, 1e9, -1)) for r, v in d.items() if r in ROOMS}
    rushes = c.get("rushes") if isinstance(c.get("rushes"), list) else []
    c["rushes"] = [{"k": str(x["k"]), "h": int(num(x.get("h"), 0, 1e9))} for x in rushes
                   if isinstance(x, dict) and (x.get("k") in ROOMS or x.get("k") == "build")][-20:]
    c["res"] = {k: num(c["res"].get(k), 0, 1e7) for k in RES}


from . import dao  # noqa: E402  (dao needs this module; it is imported last so every name above exists)

PAWN_EXTRA.update(dao.PAWN)
_RESOLVERS.update(dao.RESOLVERS)
