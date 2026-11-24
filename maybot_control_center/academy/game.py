"""Raising the sect: the game that study sessions drive.

You are the Sect Master. Rules that keep the best *game* strategy equal to the
best *study* strategy (see docs/research/sect-academy-design-inputs.md):

* Qi (your cultivation) comes only from graded answers — and the schedule, not
  the player, decides how many of those exist each day. Due reviews pay most,
  typed recall pays a little extra, off-schedule practice pays ~10%.
* Spirit stones come from finishing sessions (with daily diminishing returns:
  100% / 50% / 10%), daily quests, trials, and a *capped* passive trickle from
  halls and disciples that is scaled by how well you currently remember each
  course — neglect a course and its hall goes quiet.
* A major realm breakthrough needs a tribulation: passing a trial (mock exam).
* Missing a day never destroys anything. Grace pills cover gaps automatically,
  seclusion pauses the sect for holidays, and the qi-flow multiplier only eases
  down 10% per missed day (floor 0.5x).

All functions take the academy ``st`` dict and mutate ``st["game"]``; the engine
owns locking and saving.
"""
from __future__ import annotations

import datetime as _dt
import random

from . import fsrs, packs

REALMS = ["Mortal", "Qi Condensation", "Foundation Establishment", "Core Formation",
          "Nascent Soul", "Soul Transformation", "Void Refinement", "Immortal Ascension"]
STAGES = ["Early", "Middle", "Late", "Peak"]
TIERS = ["Nameless Hut", "Hidden Hermitage", "Mountain Gate Sect", "Rising Cloud Sect",
         "Azure Peak Sect", "Heavenly Sect", "Immortal Holy Land"]
# Items you must have learned before the Sect Master's hall can reach each level.
TIER_GATES = [0, 40, 120, 250, 450, 700, 1000]

# Rooms of the sect (rects are % of the cut-away HQ artwork: x, y, w, h).
ROOMS = {
    "grand_hall":    {"name": "Hall of the Sect Master", "rect": [0, 0, 100, 22.6], "base": 250, "growth": 2.0, "max": 7,
                      "tier": 0, "effect": "Raises the sect's rank and unlocks rooms. Each level needs more learned items."},
    "tongues_west":  {"name": "Pavilion of the West Wind", "rect": [0, 23.2, 50, 16.2], "course_hall": True, "tier": 0,
                      "effect": "French is cultivated here. Grows as you complete units."},
    "tongues_south": {"name": "Sun Court Pavilion", "rect": [50, 23.2, 50, 16.2], "course_hall": True, "tier": 0,
                      "effect": "Spanish is cultivated here. Grows as you complete units."},
    "quarters":      {"name": "Disciple Quarters", "rect": [2.5, 40, 31.3, 17], "base": 120, "growth": 1.7, "max": 6,
                      "tier": 1, "effect": "+2 disciple capacity per level."},
    "ward_hall":     {"name": "Ward Formation Hall", "rect": [34.2, 40, 30, 17], "course_hall": True, "tier": 0,
                      "effect": "Security arts (certifications) are cultivated here. Grows as you complete units."},
    "mission_hall":  {"name": "Mission Hall", "rect": [64.5, 40, 35.5, 17], "base": 150, "growth": 1.7, "max": 5,
                      "tier": 2, "effect": "Send disciples on expeditions. +20% expedition rewards per level."},
    "alchemy":       {"name": "Alchemy Hall", "rect": [2.5, 57.7, 31.3, 18.1], "base": 150, "growth": 1.7, "max": 5,
                      "tier": 2, "effect": "Brew grace pills (cover a missed day). Cheaper and more storage per level."},
    "trial_grounds": {"name": "Trial Grounds", "rect": [34.2, 57.7, 30, 18.1], "base": 120, "growth": 1.6, "max": 5,
                      "tier": 1, "effect": "+20 spirit stones for every trial you pass, per level."},
    "treasury":      {"name": "Treasure Vault", "rect": [64.5, 57.7, 35.5, 18.1], "base": 100, "growth": 1.6, "max": 8,
                      "tier": 2, "effect": "Holds more idle income: +2 hours of storage per level (base 8h, max 24h)."},
    "spirit_vein":   {"name": "Spirit Vein", "rect": [0, 76.5, 42.8, 23], "base": 60, "growth": 1.6, "max": 10,
                      "tier": 0, "effect": "+1.5 spirit stones per hour per level."},
    "meditation":    {"name": "Meditation Chamber", "rect": [43.2, 76.5, 56.8, 23], "base": 100, "growth": 1.6, "max": 10,
                      "tier": 1, "effect": "+5% qi from every answer, per level."},
}
ASSIGNABLE = ("tongues_west", "tongues_south", "ward_hall", "spirit_vein")

ROOTS = [("Common", 1.0, 55), ("Good", 1.2, 28), ("Superior", 1.45, 12), ("Heaven Grade", 1.7, 4), ("Saint Grade", 2.0, 1)]
PORTRAITS = ["disciple", "researcher", "analyst", "engineer", "architect", "trader", "elder"]
SURNAMES = ["Lin", "Zhao", "Mo", "Yun", "Feng", "Bai", "Xiao", "Shen", "Luo", "Han", "Qin", "Su", "Ye", "Gu", "Jiang", "Tang"]
GIVEN = ["Wei", "Yan", "Chen", "Xue", "Ling", "Hao", "Mei", "Rou", "Jin", "Tian", "Qing", "Yu", "An", "Zhi", "Lan", "Shuo",
         "Feiyan", "Wuji", "Ruoxi", "Changge", "Yichen", "Suyin"]
TRAITS = ["Hardworking", "Curious", "Patient", "Disciplined", "Bookworm", "Brave", "Quiet", "Competitive",
          "Dreamer", "Eccentric", "Loyal", "Perfectionist"]
DISCIPLE_RANKS = ["Outer Disciple", "Inner Disciple", "Core Disciple", "Elder"]

MISSIONS = {
    "herbs":  {"name": "Gather spirit herbs", "hours": 2},
    "escort": {"name": "Escort a merchant caravan", "hours": 4},
    "ruins":  {"name": "Explore ancient ruins", "hours": 8},
}

START_STONES = 60
MAX_FLOW, MIN_FLOW = 2.0, 0.5
WEEK_GOAL = 5


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def _blank(now: float) -> dict:
    return {
        "name": "", "master": "", "seed": random.randrange(1 << 30),
        "qi": 0, "step": 0, "tribulation": False,
        "stones": START_STONES, "rooms": {"grand_hall": 1},
        "disciples": [], "recruit_tokens": 1, "mission_tokens": 0, "recruit_n": 0, "candidates": [],
        "missions": [], "grace": 2,
        "streak": 0, "best_streak": 0, "last_study_day": "", "flow": 1.0,
        "seclusion": False, "collected_at": now,
        "quests": {"day": "", "list": []}, "week": {"id": "", "days": [], "paid": False},
        "chronicle": [], "learned_tokens": 0, "trials_passed": {}, "practice_qi": {"day": "", "n": 0},
        "daily": {"day": "", "sessions": 0, "cleared": False},
    }


def _g(st: dict, now: float) -> dict:
    g = st.get("game")
    if not g or "step" not in g:
        g = _blank(now)
        st["game"] = g
    else:
        for k, v in _blank(now).items():
            g.setdefault(k, v)
    return g


def _log(g: dict, now: float, kind: str, text: str) -> dict:
    ev = {"ts": now, "kind": kind, "text": text}
    g["chronicle"] = (g["chronicle"] + [ev])[-120:]
    return ev


def _today(st: dict, now: float) -> str:
    off = int(st["settings"].get("tz_offset_min", 0)) * 60
    return _dt.datetime.fromtimestamp(now + off, _dt.timezone.utc).strftime("%Y-%m-%d")


def _date(day: str) -> _dt.date:
    return _dt.date.fromisoformat(day)


# ---------------------------------------------------------------------------
# cultivation ladder
# ---------------------------------------------------------------------------
MAX_STEP = len(REALMS) * len(STAGES) - 1


def step_cost(step: int) -> int:
    return 250 + 200 * step


def _cum(step: int) -> int:
    return sum(step_cost(i) for i in range(step))


def _realm_label(step: int) -> str:
    return f"{REALMS[step // 4]} · {STAGES[step % 4]}"


def _advance(g: dict, now: float) -> list[dict]:
    """Spend banked qi on stage-ups. A Peak stage waits for a tribulation."""
    events = []
    while g["step"] < MAX_STEP and g["qi"] - _cum(g["step"]) >= step_cost(g["step"]):
        if g["step"] % 4 == 3:
            if not g["tribulation"]:
                g["tribulation"] = True
                events.append(_log(g, now, "tribulation",
                                   f"Your qi brims at {_realm_label(g['step'])}. Pass a trial to break through to "
                                   f"{REALMS[g['step'] // 4 + 1]}."))
            break
        g["step"] += 1
        events.append(_log(g, now, "stage", f"Breakthrough: you reached {_realm_label(g['step'])}."))
    return events


# ---------------------------------------------------------------------------
# rooms
# ---------------------------------------------------------------------------
def _lvl(g: dict, room: str) -> int:
    return int(g["rooms"].get(room, 0))


def _learned(st: dict) -> int:
    return sum(1 for c in st["cards"].values() if c.get("reps"))


def _course_halls(st: dict, now: float) -> dict[str, dict]:
    """hall id -> {level, strength (0..1), courses} from enrolled courses."""
    out: dict[str, dict] = {}
    enrolled = st["settings"].get("courses", [])
    for pack in packs.load_all().values():
        if pack["id"] not in enrolled:
            continue
        h = out.setdefault(pack.get("hall", ""), {"units": 0, "seen": 0, "r": 0.0, "courses": []})
        h["courses"].append(pack["title"])
        for u in pack["units"]:
            n = 0
            for it in u["items"]:
                c = st["cards"].get(it["id"])
                if c and c.get("reps"):
                    n += 1
                    h["seen"] += 1
                    h["r"] += fsrs.retrievability(max(0.0, (now - c["last"]) / fsrs.DAY), c["s"])
            if n >= len(u["items"]):
                h["units"] += 1
    for h in out.values():
        h["level"] = min(1 + h["units"], 12)
        h["strength"] = (h["r"] / h["seen"]) if h["seen"] else 0.0
    return out


def room_cost(room: str, level: int) -> int:
    r = ROOMS[room]
    return int(round(r["base"] * r["growth"] ** level / 10.0)) * 10


def _room_capacity(g: dict, room: str, halls: dict) -> int:
    if room == "spirit_vein":
        return (1 + _lvl(g, room) // 4) if _lvl(g, room) else 0
    h = halls.get(room)
    return min(3, 1 + h["level"] // 3) if h else 0


def disciple_cap(g: dict) -> int:
    return 2 + 2 * _lvl(g, "quarters")


def grace_cap(g: dict) -> int:
    return 2 + _lvl(g, "alchemy") // 2


def pill_cost(g: dict) -> int:
    return max(30, 90 - 10 * _lvl(g, "alchemy"))


def storage_hours(g: dict) -> int:
    return min(24, 8 + 2 * _lvl(g, "treasury"))


def _rate(st: dict, g: dict, now: float, halls: dict | None = None) -> float:
    """Passive spirit stones per hour (before the qi-flow multiplier)."""
    halls = halls if halls is not None else _course_halls(st, now)
    vein = 1.5 * _lvl(g, "spirit_vein")
    total = 0.0
    for d in g["disciples"]:
        if d.get("away_until", 0) > now or not d.get("room"):
            continue
        power = d["talent"] * (1 + 0.1 * d["level"])
        if d["room"] == "spirit_vein" and _lvl(g, "spirit_vein"):
            vein *= 1 + 0.25 * power
        elif d["room"] in halls:
            h = halls[d["room"]]
            total += 1.0 * power * h["strength"] * (1 + 0.1 * h["level"])
    return total + vein


def _pending(st: dict, g: dict, now: float, halls: dict | None = None) -> float:
    if g["seclusion"]:
        return 0.0
    hours = min(max(0.0, (now - g["collected_at"]) / 3600.0), storage_hours(g))
    return hours * _rate(st, g, now, halls) * g["flow"]


def collect(st: dict, now: float) -> dict:
    g = _g(st, now)
    amount = max(0, int(_pending(st, g, now)))
    g["stones"] += amount
    g["collected_at"] = now       # always restart the clock, so a new room never back-pays
    return {"ok": True, "stones": amount}


def upgrade(st: dict, room: str, now: float) -> dict:
    g = _g(st, now)
    r = ROOMS.get(room)
    if not r or r.get("course_hall"):
        return {"ok": False, "error": "That hall grows through study, not spirit stones."}
    level = _lvl(g, room)
    if level >= r["max"]:
        return {"ok": False, "error": "Already at its highest level."}
    if room != "grand_hall" and _lvl(g, "grand_hall") <= r["tier"] and r["tier"] > 0:
        return {"ok": False, "error": f"Raise the Hall of the Sect Master to level {r['tier'] + 1} first."}
    if room == "grand_hall":
        need = TIER_GATES[level] if level < len(TIER_GATES) else TIER_GATES[-1]
        if _learned(st) < need:
            return {"ok": False, "error": f"Learn {need} items first (you know {_learned(st)})."}
    cost = room_cost(room, level)
    if g["stones"] < cost:
        return {"ok": False, "error": f"Needs {cost} spirit stones."}
    collect(st, now)                      # bank income at the old rate first
    g["stones"] -= cost
    g["rooms"][room] = level + 1
    verb = "built" if level == 0 else f"raised to level {level + 1}"
    text = f"{r['name']} {verb}."
    if room == "grand_hall":
        text = f"The sect ascends: you are now a {TIERS[min(level, len(TIERS) - 1)]}."
    return {"ok": True, "room": room, "level": level + 1, "event": _log(g, now, "build", text)}


# ---------------------------------------------------------------------------
# disciples
# ---------------------------------------------------------------------------
def _make_candidate(g: dict, n: int) -> dict:
    rng = random.Random(f"{g['seed']}:{n}")
    roll = rng.uniform(0, sum(w for _, _, w in ROOTS))
    acc = 0.0
    root, talent = ROOTS[0][0], ROOTS[0][1]
    for name, mult, w in ROOTS:
        acc += w
        if roll <= acc:
            root, talent = name, mult
            break
    return {"id": f"d{n}", "name": f"{rng.choice(SURNAMES)} {rng.choice(GIVEN)}", "root": root,
            "talent": talent, "portrait": rng.choice(PORTRAITS[:-1]),
            "traits": rng.sample(TRAITS, 2), "level": 0, "xp": 0, "room": None, "away_until": 0}


def recruit_offer(st: dict, now: float) -> dict:
    g = _g(st, now)
    if len(g["disciples"]) >= disciple_cap(g):
        return {"ok": False, "error": "The Disciple Quarters are full. Build or upgrade them first."}
    if not g["candidates"]:
        if g["recruit_tokens"] <= 0:
            return {"ok": False, "error": "No recruitment tokens. Earn them by learning new items and passing trials."}
        g["recruit_tokens"] -= 1
        g["candidates"] = [_make_candidate(g, g["recruit_n"] + i) for i in range(3)]
        g["recruit_n"] += 3
    return {"ok": True, "candidates": g["candidates"]}


def recruit_pick(st: dict, cand_id: str, now: float) -> dict:
    g = _g(st, now)
    cand = next((c for c in g["candidates"] if c["id"] == cand_id), None)
    if not cand:
        return {"ok": False, "error": "That candidate has left."}
    if len(g["disciples"]) >= disciple_cap(g):
        return {"ok": False, "error": "The Disciple Quarters are full."}
    cand = dict(cand, joined=now)
    g["disciples"].append(cand)
    g["candidates"] = []
    return {"ok": True, "disciple": cand,
            "event": _log(g, now, "recruit", f"{cand['name']} ({cand['root']} spirit root) joined the sect.")}


def assign(st: dict, disciple_id: str, room: str | None, now: float) -> dict:
    g = _g(st, now)
    d = next((x for x in g["disciples"] if x["id"] == disciple_id), None)
    if not d:
        return {"ok": False, "error": "Unknown disciple."}
    if d.get("away_until", 0) > now:
        return {"ok": False, "error": f"{d['name']} is away on an expedition."}
    if room:
        if room not in ASSIGNABLE:
            return {"ok": False, "error": "Disciples cannot be posted there."}
        halls = _course_halls(st, now)
        cap = _room_capacity(g, room, halls)
        if cap <= 0:
            return {"ok": False, "error": "That room is not open yet."}
        if sum(1 for x in g["disciples"] if x.get("room") == room and x["id"] != d["id"]) >= cap:
            return {"ok": False, "error": "That room is full."}
    collect(st, now)
    d["room"] = room or None
    return {"ok": True}


def dismiss(st: dict, disciple_id: str, now: float) -> dict:
    g = _g(st, now)
    d = next((x for x in g["disciples"] if x["id"] == disciple_id), None)
    if not d:
        return {"ok": False, "error": "Unknown disciple."}
    collect(st, now)
    g["disciples"] = [x for x in g["disciples"] if x["id"] != disciple_id]
    g["missions"] = [m for m in g["missions"] if m["disciple"] != disciple_id]
    return {"ok": True, "event": _log(g, now, "leave", f"{d['name']} left the sect to wander the world.")}


def _rank(d: dict) -> str:
    return DISCIPLE_RANKS[min(d["level"] // 4, len(DISCIPLE_RANKS) - 1)]


def _disciple_xp(g: dict, amount: float, now: float) -> list[dict]:
    events = []
    for d in g["disciples"]:
        d["xp"] += amount * d["talent"]
        while d["xp"] >= 50 * (d["level"] + 1):
            d["xp"] -= 50 * (d["level"] + 1)
            before = _rank(d)
            d["level"] += 1
            if _rank(d) != before:
                events.append(_log(g, now, "disciple", f"{d['name']} was promoted to {_rank(d)}."))
    return events


# ---------------------------------------------------------------------------
# missions (expeditions)
# ---------------------------------------------------------------------------
def dispatch(st: dict, disciple_id: str, kind: str, now: float) -> dict:
    g = _g(st, now)
    if not _lvl(g, "mission_hall"):
        return {"ok": False, "error": "Build the Mission Hall first."}
    m = MISSIONS.get(kind)
    d = next((x for x in g["disciples"] if x["id"] == disciple_id), None)
    if not m or not d:
        return {"ok": False, "error": "Unknown disciple or mission."}
    if d.get("away_until", 0) > now:
        return {"ok": False, "error": f"{d['name']} is already away."}
    if g["mission_tokens"] <= 0:
        return {"ok": False, "error": "No mission orders. Each study session you complete earns one."}
    collect(st, now)
    g["mission_tokens"] -= 1
    ends = now + m["hours"] * 3600
    d["away_until"] = ends
    g["missions"].append({"disciple": d["id"], "kind": kind, "ends": ends})
    return {"ok": True, "ends": ends,
            "event": _log(g, now, "mission", f"{d['name']} set out to {m['name'].lower()} ({m['hours']}h).")}


def _resolve_missions(st: dict, g: dict, now: float) -> list[dict]:
    events, keep = [], []
    for m in g["missions"]:
        if m["ends"] > now:
            keep.append(m)
            continue
        d = next((x for x in g["disciples"] if x["id"] == m["disciple"]), None)
        if not d:
            continue
        spec = MISSIONS[m["kind"]]
        rng = random.Random(f"{g['seed']}:{m['ends']}:{d['id']}")
        stones = int(12 * spec["hours"] ** 0.8 * d["talent"] * (1 + 0.1 * d["level"])
                     * (1 + 0.2 * _lvl(g, "mission_hall")) * rng.uniform(0.85, 1.25))
        g["stones"] += stones
        text = f"{d['name']} returned from the expedition with {stones} spirit stones."
        if spec["hours"] >= 8 and rng.random() < 0.15:
            g["recruit_tokens"] += 1
            text += " A wanderer they met asks to join — you gained a recruitment token."
        d["away_until"] = 0
        d["xp"] += 10 * spec["hours"]
        events.append(_log(g, now, "mission", text))
    g["missions"] = keep
    return events


# ---------------------------------------------------------------------------
# pills, seclusion, setup
# ---------------------------------------------------------------------------
def brew_pill(st: dict, now: float) -> dict:
    g = _g(st, now)
    if not _lvl(g, "alchemy"):
        return {"ok": False, "error": "Build the Alchemy Hall first."}
    if g["grace"] >= grace_cap(g):
        return {"ok": False, "error": "Your pill cabinet is full."}
    cost = pill_cost(g)
    if g["stones"] < cost:
        return {"ok": False, "error": f"Needs {cost} spirit stones."}
    g["stones"] -= cost
    g["grace"] += 1
    return {"ok": True, "grace": g["grace"], "event": _log(g, now, "pill", "A Meridian-Guarding Pill was brewed.")}


def set_seclusion(st: dict, on: bool, now: float) -> dict:
    """Closed-door seclusion = holiday mode: streak and qi flow are frozen."""
    g = _g(st, now)
    if on and not g["seclusion"]:
        collect(st, now)
        g["seclusion"] = True
        _log(g, now, "seclusion", "The sect sealed its gates. Your streak is safe until you return.")
    elif not on and g["seclusion"]:
        g["seclusion"] = False
        g["collected_at"] = now
        if g["last_study_day"]:
            # Returning: the gap spent in seclusion does not count against the streak.
            g["last_study_day"] = (_date(_today(st, now)) - _dt.timedelta(days=1)).isoformat()
        _log(g, now, "seclusion", "The sect reopened its gates.")
    return {"ok": True, "seclusion": g["seclusion"]}


def setup(st: dict, name: str, master: str, now: float) -> dict:
    g = _g(st, now)
    first = not g["name"]
    g["name"] = (name or "").strip()[:40] or "Nameless Sect"
    g["master"] = (master or "").strip()[:30] or "Sect Master"
    if first:
        g["collected_at"] = now
        _log(g, now, "founding", f"{g['master']} founded the {g['name']}.")
    return {"ok": True}


# ---------------------------------------------------------------------------
# rewards (called by the engine)
# ---------------------------------------------------------------------------
def on_answer(st: dict, course: str, *, correct: bool, is_new: bool, practice: bool, typed: bool, now: float) -> dict:
    g = _g(st, now)
    if practice:
        day = _today(st, now)
        if g["practice_qi"]["day"] != day:
            g["practice_qi"] = {"day": day, "n": 0}
        qi = 1 if correct and g["practice_qi"]["n"] < 30 else 0
        g["practice_qi"]["n"] += qi
    elif is_new:
        qi = 6 if correct else 2
    else:
        qi = 10 if correct else 3
    if typed and correct and not practice:
        qi += 2
    qi = int(round(qi * (1 + 0.05 * _lvl(g, "meditation"))))
    g["qi"] += qi
    events = _advance(g, now)
    # A recruitment token for every 30 items learned.
    if is_new and not practice:
        learned = _learned(st)
        while learned >= (g["learned_tokens"] + 1) * 30:
            g["learned_tokens"] += 1
            g["recruit_tokens"] += 1
            events.append(_log(g, now, "token",
                               f"Word of your sect spreads ({g['learned_tokens'] * 30} items learned): +1 recruitment token."))
    return {"qi": qi, "events": events}


def _mark_study_day(st: dict, g: dict, now: float) -> list[dict]:
    events = []
    today = _today(st, now)
    if g["last_study_day"] == today:
        return events
    if g["last_study_day"]:
        missed = max(0, (_date(today) - _date(g["last_study_day"])).days - 1)
    else:
        missed = 0
    if missed and g["grace"] >= missed:
        g["grace"] -= missed
        g["streak"] += 1
        events.append(_log(g, now, "pill", f"{missed} Meridian-Guarding Pill{'s' if missed > 1 else ''} "
                                           f"covered your absence. The streak holds."))
    elif missed:
        g["flow"] = max(MIN_FLOW, round(g["flow"] * 0.9 ** missed, 2))
        g["streak"] = 1
        events.append(_log(g, now, "return", "You returned to cultivation. A new streak begins."))
    else:
        g["streak"] += 1
    g["flow"] = min(MAX_FLOW, round(g["flow"] + 0.1, 2))
    g["best_streak"] = max(g["best_streak"], g["streak"])
    g["last_study_day"] = today
    if g["streak"] % 7 == 0 and g["grace"] < grace_cap(g):
        g["grace"] += 1
        events.append(_log(g, now, "pill", f"{g['streak']}-day streak: you were gifted a Meridian-Guarding Pill."))
    # weekly goal
    iso = _date(today).isocalendar()
    wid = f"{iso[0]}-W{iso[1]:02d}"
    if g["week"]["id"] != wid:
        g["week"] = {"id": wid, "days": [], "paid": False}
    if today not in g["week"]["days"]:
        g["week"]["days"].append(today)
    if len(g["week"]["days"]) >= WEEK_GOAL and not g["week"]["paid"]:
        g["week"]["paid"] = True
        g["stones"] += 100
        events.append(_log(g, now, "week", f"Weekly goal met ({WEEK_GOAL} days of cultivation): +100 spirit stones."))
    return events


def on_session(st: dict, *, answers: int, correct: int, counted: bool, due_left: int, now: float) -> dict:
    g = _g(st, now)
    events: list[dict] = []
    stones = 0
    if counted:
        today = _today(st, now)
        if g["daily"]["day"] != today:
            g["daily"] = {"day": today, "sessions": 0, "cleared": False}
        n = g["daily"]["sessions"]
        scale = 1.0 if n == 0 else 0.5 if n == 1 else 0.1          # daily diminishing returns
        base = 15 + (10 if answers >= 10 and correct / max(answers, 1) >= 0.9 else 0)
        stones = int(round(base * scale))
        if n == 0:
            stones += 25                                            # the day's first offering
        if due_left == 0 and not g["daily"]["cleared"]:
            g["daily"]["cleared"] = True
            stones += 15
        g["daily"]["sessions"] = n + 1
        g["stones"] += stones
        g["mission_tokens"] = min(3, g["mission_tokens"] + 1)
        events += _mark_study_day(st, g, now)
        events += _disciple_xp(g, 10, now)
    events += _eval_quests(st, g, now)
    return {"stones": stones, "events": events, "streak": g["streak"]}


def on_trial(st: dict, course: str, *, passed: bool, pct: int, now: float) -> dict:
    g = _g(st, now)
    events: list[dict] = []
    stones = 0
    pack = packs.get(course) or {}
    if passed:
        stones = 120 + 20 * _lvl(g, "trial_grounds")
        today = _today(st, now)
        if g["trials_passed"].get(course) == today:
            stones = stones // 4                                    # same course, same day: token reward
        elif course not in g["trials_passed"]:
            g["recruit_tokens"] += 1
            events.append(_log(g, now, "token", f"First trial passed in {pack.get('title', course)}: +1 recruitment token."))
        g["trials_passed"][course] = today
        g["stones"] += stones
        events.append(_log(g, now, "trial", f"Trial passed with {pct}% ({pack.get('title', course)})."))
        if g["tribulation"] and g["step"] < MAX_STEP:
            g["tribulation"] = False
            g["step"] += 1
            events.append(_log(g, now, "realm", f"You survived the tribulation and entered {_realm_label(g['step'])}!"))
            events += _advance(g, now)
    else:
        events.append(_log(g, now, "trial", f"Trial attempt: {pct}% ({pack.get('title', course)}). "
                                            f"The missed questions joined your review queue."))
    return {"stones": stones, "events": events}


# ---------------------------------------------------------------------------
# daily quests (progress is derived from the day's counters — nothing to grind)
# ---------------------------------------------------------------------------
QUEST_REWARD = 20


def _quest_defs(ctx: dict) -> list[dict]:
    pool = []
    if ctx.get("due", 0) >= 10:
        pool.append({"id": "reviews", "text": "Review 10 items", "goal": 10})
        pool.append({"id": "clear", "text": "Clear every due review", "goal": 1})
    if ctx.get("new_left", 0) >= 5:
        pool.append({"id": "new", "text": "Learn 5 new items", "goal": 5})
    if ctx.get("typed_possible"):
        pool.append({"id": "typed", "text": "Type 8 answers from memory", "goal": 8})
    if ctx.get("courses", 0) >= 2:
        pool.append({"id": "two", "text": "Cultivate two different arts today", "goal": 2})
    pool.append({"id": "accuracy", "text": "Answer 15 items at 85% accuracy or better", "goal": 15})
    return pool


def _roll_quests(st: dict, g: dict, now: float, ctx: dict) -> None:
    today = _today(st, now)
    if g["quests"]["day"] == today:
        return
    rng = random.Random(f"{g['seed']}:{today}")
    pool = _quest_defs(ctx)
    picks = rng.sample(pool, min(2, len(pool)))
    quests = [{"id": "session", "text": "Complete a cultivation session", "goal": 1}] + picks
    g["quests"] = {"day": today, "list": [dict(q, progress=0, done=False) for q in quests]}


def _eval_quests(st: dict, g: dict, now: float) -> list[dict]:
    today = _today(st, now)
    if g["quests"]["day"] != today:
        return []
    d = st["days"].get(today, {})
    events = []
    for q in g["quests"]["list"]:
        if q["done"]:
            continue
        qid = q["id"]
        if qid == "session":
            p = d.get("sessions", 0)
        elif qid == "reviews":
            p = d.get("reviews", 0)
        elif qid == "new":
            p = d.get("new", 0)
        elif qid == "typed":
            p = d.get("typed", 0)
        elif qid == "two":
            p = len(d.get("courses", []))
        elif qid == "clear":
            p = 1 if g["daily"].get("day") == today and g["daily"].get("cleared") else 0
        else:   # accuracy
            a, c = d.get("answers", 0), d.get("correct", 0)
            p = a if (a < q["goal"] or c / max(a, 1) >= 0.85) else q["goal"] - 1
        q["progress"] = min(p, q["goal"])
        if p >= q["goal"]:
            q["done"] = True
            g["stones"] += QUEST_REWARD
            events.append(_log(g, now, "quest", f"Quest complete — {q['text']}: +{QUEST_REWARD} spirit stones."))
    if g["quests"]["list"] and all(q["done"] for q in g["quests"]["list"]) and not g["quests"].get("bonus"):
        g["quests"]["bonus"] = True
        g["stones"] += 30
        events.append(_log(g, now, "quest", "All daily quests complete: +30 spirit stones."))
    return events


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------
def ensure(st: dict, now: float, ctx: dict | None = None) -> list[dict]:
    """Bring the game up to date: finished missions, today's quests."""
    g = _g(st, now)
    events = _resolve_missions(st, g, now)
    if ctx is not None:
        _roll_quests(st, g, now, ctx)
        events += _eval_quests(st, g, now)
    return events


def view(st: dict, now: float) -> dict:
    g = _g(st, now)
    halls = _course_halls(st, now)
    today = _today(st, now)
    step = g["step"]
    into = g["qi"] - _cum(step)
    need = step_cost(step)
    gh = _lvl(g, "grand_hall")
    learned = _learned(st)
    rooms = []
    for rid, r in ROOMS.items():
        row = {"id": rid, "name": r["name"], "rect": r["rect"], "effect": r["effect"], "course_hall": bool(r.get("course_hall"))}
        if r.get("course_hall"):
            h = halls.get(rid)
            row.update(level=h["level"] if h else 0, max=12, open=bool(h), cost=None,
                       strength=round(100 * h["strength"]) if h else 0, courses=h["courses"] if h else [],
                       locked="" if h else "Enrol in a course to open this hall.")
        else:
            level = _lvl(g, rid)
            locked = ""
            if rid != "grand_hall" and r["tier"] > 0 and gh <= r["tier"]:
                locked = f"Needs Hall of the Sect Master level {r['tier'] + 1}."
            if rid == "grand_hall" and level < r["max"]:
                gate = TIER_GATES[min(level, len(TIER_GATES) - 1)]
                if learned < gate:
                    locked = f"Learn {gate} items to ascend (you know {learned})."
            row.update(level=level, max=r["max"], open=level > 0, locked=locked,
                       cost=room_cost(rid, level) if level < r["max"] else None)
        if rid in ASSIGNABLE:
            row["capacity"] = _room_capacity(g, rid, halls)
            row["staff"] = [d["id"] for d in g["disciples"] if d.get("room") == rid]
        rooms.append(row)
    last = g["last_study_day"]
    gap = (_date(today) - _date(last)).days if last else 0
    at_risk = bool(last) and not g["seclusion"] and gap >= 1 and g["streak"] > 0
    lost = bool(last) and not g["seclusion"] and gap > 1 and g["grace"] < gap - 1
    disciples = [dict(d, rank=_rank(d), xp_need=50 * (d["level"] + 1), away=d.get("away_until", 0) > now)
                 for d in g["disciples"]]
    return {
        "name": g["name"], "master": g["master"], "founded": bool(g["name"]),
        "tier": TIERS[min(gh - 1, len(TIERS) - 1)], "tier_level": gh,
        "realm": REALMS[step // 4], "stage": STAGES[step % 4], "step": step,
        "next_realm": REALMS[min(step // 4 + 1, len(REALMS) - 1)],
        "qi": g["qi"], "qi_into": min(into, need), "qi_need": need,
        "qi_pct": min(100, round(100 * into / need)), "tribulation": g["tribulation"],
        "stones": g["stones"], "pending": int(_pending(st, g, now, halls)),
        "rate": round(_rate(st, g, now, halls) * g["flow"], 1), "storage_hours": storage_hours(g),
        "flow": g["flow"], "streak": 0 if lost else g["streak"], "best_streak": g["best_streak"],
        "studied_today": last == today, "streak_at_risk": at_risk and not lost and last != today,
        "grace": g["grace"], "grace_cap": grace_cap(g), "pill_cost": pill_cost(g), "seclusion": g["seclusion"],
        "week": {"days": len(g["week"]["days"]) if g["week"]["id"] else 0, "goal": WEEK_GOAL},
        "quests": g["quests"]["list"] if g["quests"]["day"] == today else [],
        "rooms": rooms, "disciples": disciples, "disciple_cap": disciple_cap(g),
        "recruit_tokens": g["recruit_tokens"], "mission_tokens": g["mission_tokens"],
        "candidates": g["candidates"],
        "missions": [dict(m, name=MISSIONS[m["kind"]]["name"]) for m in g["missions"]],
        "mission_kinds": [{"id": k, **v} for k, v in MISSIONS.items()],
        "chronicle": list(reversed(g["chronicle"][-40:])),
        "learned": learned,
        "power": int(learned * 2 + sum(1 for c in st["cards"].values() if c.get("reps") and c["s"] >= 21) * 5
                     + sum(10 + 10 * d["level"] for d in g["disciples"])
                     + sum(g["rooms"].values()) * 15 + step * 20),
    }

