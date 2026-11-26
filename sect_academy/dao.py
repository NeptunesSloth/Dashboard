"""The deeper life of the sect: lineages, dao companions, heart demons, precepts, merit,
discipline, the elder council, alchemy, paths, seclusion, the mortal kingdom, alliances and
sieges, the demonic path, succession, rumours, verses and the graveyard.

colony.py owns the clock and the core rules and calls the small hooks below; everything here
reads and writes the same ``st["colony"]`` dict. (colony imports this module at its end, so
``C.<name>`` is always resolved at call time.)
"""
from __future__ import annotations

import random

from . import colony as C
from . import lore

# extra fields on every disciple, and on the colony
PAWN = {"mentor": "", "companion": "", "demon": 0, "merit": 0.0, "path": "", "toxin": 0.0, "marrow": False, "ancient": 0, "xp_x": 1.0, "beast": None, "fates": [], "fate_due": -1}


def defaults() -> dict:
    return {**road.defaults(), "precepts": [], "kingdom": 0.0, "elixirs": {"marrow": 0, "berserk": 0}, "rare": 0.0, "recipe": "pill", "demonic": False,
            "blessings": [], "dead": [], "siege": None, "sutra_days": 0, "marks": {},
            "karma": 0.0, "branches": [], "style": {"colour": "gold", "motto": ""}}


PRECEPTS = {
    "compassion":  {"name": "Compassion", "text": "Turn away no one in need. +4 mood; the mortal kingdom's favour grows half again as fast.",
                    "breaks": [("village", "decline"), ("quest_offer", "decline"), ("beast_cub", "sell"), ("beast_cub", "decline"), ("lord", "refuse")]},
    "strength":    {"name": "Strength above all", "text": "Never bow. +10% fighting strength.",
                    "breaks": [("young_master", "endure"), ("young_master", "pay"), ("omen", "tribute"), ("tournament", "decline"),
                               ("engagement", "stones"), ("taxes", "pay")]},
    "hospitality": {"name": "The open gate", "text": "Every traveller is a guest. Wanderers come more often.",
                    "breaks": [("wanderer", "decline"), ("recruit", "decline"), ("ally_call", "refuse")]},
    "scholarship": {"name": "Knowledge before all", "text": "+20% research, and skills grow 10% faster.",
                    "breaks": [("cave", "decline"), ("embrace", "burn")]},
    "frugality":   {"name": "Waste nothing", "text": "Disciples eat 15% less.", "breaks": [("festival", "hold"), ("auction", "lot")]},
}
PATHS = {
    "sword":     {"name": "Sword path", "text": "+20% fighting strength, 5% slower cultivation."},
    "body":      {"name": "Body path", "text": "Takes 20% less damage, eats 10% more."},
    "formation": {"name": "Formation path", "text": "Each adds 12% to the Ward Formation while home."},
}
RECIPES = {
    "pill":    {"name": "Healing pills", "text": "The ordinary pill: heals, cures sickness, steadies a breakthrough."},
    "marrow":  {"name": "Marrow-Cleansing Pill", "herbs": 6, "rare": 2, "text": "Once per disciple: their spirit root gathers qi 8% faster for life."},
    "berserk": {"name": "Berserk Pill", "herbs": 4, "rare": 1, "text": "Handed out before a fight: +30% strength for that battle, then wounds and pill toxin."},
}
BLESSINGS = {"enduring": "Blessing of the Ascended: +10% cultivation speed.", "renowned": "Renown of the Ascended: fame draws finer recruits.",
             "harmonious": "Harmony of the Ascended: +5 mood for everyone.", "dread": "Dread of the Ascended: +15% fighting strength."}
GRADES = [("Flawed", 0.0), ("Common", 0.02), ("Fine", 0.04), ("Superior", 0.07), ("Heaven-defying", 0.10)]
# A fate is chosen at each great realm: one of three, fixed for that disciple and realm. Each is a trade.
FATES = {
    "iron_bones":   {"name": "Iron Bones", "text": "Takes 15% less damage.", "hurt": 0.85},
    "sword_heart":  {"name": "Sword Heart", "text": "+15% fighting strength, -2 mood: they see enemies everywhere.", "combat": 1.15, "mood": -2},
    "clear_mind":   {"name": "Clear Mind", "text": "+5 to every later breakthrough.", "bt": 5},
    "hungry_ghost": {"name": "Hungry Ghost Meridians", "text": "+12% cultivation speed, eats 20% more.", "qi": 1.12, "hunger": 1.2},
    "hermit":       {"name": "Hermit's Bearing", "text": "+18% cultivation speed while they have no friends in the sect, -2 mood.", "qi_alone": 1.18, "mood": -2},
    "warm_heart":   {"name": "Warm Heart", "text": "+5 mood, always.", "mood": 5},
    "quick_study":  {"name": "Quick Study", "text": "Skills grow 25% faster.", "xp": 1.25},
    "fasting_body": {"name": "Fasting Body", "text": "Eats 20% less, -5% fighting strength.", "hunger": 0.8, "combat": 0.95},
    "storm_tested": {"name": "Storm-Tested", "text": "+8 to later breakthroughs, takes 10% more damage.", "bt": 8, "hurt": 1.1},
    "steady_flame": {"name": "Steady Flame", "text": "+7% cultivation speed. No catch.", "qi": 1.07},
    # only a Superior or Heaven-defying breakthrough can draw these
    "heaven_chosen": {"name": "Heaven's Chosen", "text": "+20% cultivation speed.", "qi": 1.2, "rare": True},
    "dao_body":      {"name": "Innate Dao Body", "text": "Takes 25% less damage and fights 10% harder.", "hurt": 0.75, "combat": 1.1, "rare": True},
}
COLOURS = {"gold": "#e9b44c", "azure": "#5fa8e0", "jade": "#3fae82", "vermilion": "#e0563f", "violet": "#a58af0", "white": "#e8e2d4"}
# what heaven keeps count of: (event kind, option prefix) -> karma
KARMA = {("village", "send"): 3, ("village", "decline"): -3, ("quest_offer", "accept"): 2, ("beast_cub", "adopt"): 2, ("beast_cub", "sell"): -1,
         ("spy", "forgive"): 2, ("spy", "banish"): -1, ("wanderer", "accept"): 1, ("lord", "flatter"): -2, ("lord", "honest"): 1, ("lord", "send"): 2,
         ("demonic_offer", "accept"): -5, ("demonic_offer", "fight"): 2, ("embrace", "embrace"): -12, ("embrace", "burn"): 4,
         ("qingming", "visit"): 2, ("qingming", "skip"): -2, ("quest_reward", ""): 3, ("ally_call", "send"): 2, ("ally_call", "refuse"): -3,
         ("branch_call", "send"): 2, ("branch_call", "refuse"): -3, ("festival", "hold"): 1, ("discipline", "forgive"): 1}
# the country around the mountain: (name, what it is, x%, y% on the painted map)
PLACES_ON_MAP = [("Herb Valley", "A day's walk east. Herbs, and the rare hundred-year kind.", 78, 70), ("Beast Forest", "A day and a half north. Spirit stones in the dens.", 30, 22),
                 ("Ruined Sect", "Two days west. Manuals and artifacts under the rubble.", 12, 58), ("Misty Marsh", "Where the secret realm opens.", 62, 28),
                 ("Willow Village", "Mortals at the mountain's foot. They ask for help, and remember it.", 44, 84), ("The lord's seat", "The lowland kingdom.", 86, 88)]
POEMS = [
    "Lanterns on ten thousand steps; one more is lit tonight for {name}.",
    "The mountain did not bow to the storm. Neither did {name}.",
    "Snow on the roof tiles, thunder in the meridians: {name} passed this way.",
    "Ask the pines who held the gate. They will say: {name}.",
    "A sword is a brief thing and a name is brief. The sect remembers {name} anyway.",
]


def has(c: dict, precept: str) -> bool:
    return precept in c["precepts"]


def _mentor(c: dict, p: dict) -> dict | None:
    return C._p(c, p["mentor"]) if p.get("mentor") else None


def _companion(c: dict, p: dict) -> dict | None:
    return C._p(c, p["companion"]) if p.get("companion") else None


def _is_home(c: dict, p: dict | None) -> bool:
    return bool(p) and p["away_until"] <= c["hour"]


def _elders(c: dict) -> list[dict]:
    return [p for p in c["pawns"] if not p.get("master") and C.rank_of(p) >= 2]


# ---------------------------------------------------------------------------
# hooks: numbers
# ---------------------------------------------------------------------------
def qi_rows(c: dict, p: dict) -> list[tuple[str, float]]:
    rows = []
    m, d = _mentor(c, p), _companion(c, p)
    if _is_home(c, m):
        rows.append((f"Taught by {m['name']}", 1.1))
    if _is_home(c, d):
        rows.append((f"Cultivates beside their dao companion, {d['name']}", 1.15))
    if p.get("ancient") == 2:
        rows.append(("Has walked this road before", 1.8))
    elif p.get("ancient") == 1:
        rows.append(("Uncanny comprehension", 1.4))
    if p.get("path") == "sword":
        rows.append(("The sword leaves less time to sit", 0.95))
    if c["demonic"]:
        rows.append(("The demonic path", 1.25))
    if "enduring" in c["blessings"]:
        rows.append(("Blessing of the Ascended", 1.1))
    if p["toxin"] > 3:
        rows.append(("Pill toxin clogs the meridians", 0.9))
    for f in _fates(p):
        if "qi" in f:
            rows.append((f"Fate: {f['name']}", f["qi"]))
        if "qi_alone" in f and not C._friends(c, p):
            rows.append((f"Fate: {f['name']}", f["qi_alone"]))
    return rows + road.qi_rows(c, p)


def mood_rows(c: dict, p: dict) -> list[tuple[str, int]]:
    rows = []
    if p["demon"]:
        rows.append(("Heart demon", -3 * int(p["demon"])))
    if p["toxin"] > 3:
        rows.append(("Pill toxin", -4))
    if has(c, "compassion"):
        rows.append(("A compassionate sect", 4))
    if "harmonious" in c["blessings"]:
        rows.append(("Harmony of the Ascended", 5))
    if _companion(c, p):
        rows.append(("Has a dao companion", 4))
    if c["demonic"] and "Iron will" not in p["traits"]:
        rows.append(("The path is dark", -3))
    if p.get("beast"):
        rows.append((f"{p['beast']['name']} at their heel", 3))
    rows += [(f"Fate: {f['name']}", f["mood"]) for f in _fates(p) if "mood" in f]
    return rows + road.mood_rows(c, p)


def bt_rows(c: dict, p: dict) -> list[tuple[str, int]]:
    rows = []
    if p["demon"]:
        rows.append(("Heart demon", -8 * int(p["demon"])))
    m = _mentor(c, p)
    if _is_home(c, m):
        rows.append((f"{m['name']} watches over their disciple", 4))
    if _is_home(c, _companion(c, p)):
        rows.append(("Their dao companion keeps vigil", 5))
    if c["karma"] >= 20:
        rows.append(("Heaven remembers the sect's kindness", 4))
    elif c["karma"] <= -20:
        rows.append(("The sect's karmic debt", -6))
    rows += [(f"Fate: {f['name']}", f["bt"]) for f in _fates(p) if "bt" in f]
    return rows + road.bt_rows(c, p)


def _fates(p: dict) -> list[dict]:
    return [FATES[k] for k in p.get("fates", []) if k in FATES]


def _fx(p: dict, key: str) -> float:
    out = 1.0
    for f in _fates(p):
        out *= f.get(key, 1.0)
    return out


def bt_grade(c: dict, p: dict) -> tuple[int, list[tuple[str, bool]]]:
    """How well prepared a breakthrough is. Nothing here is luck: every line is something you can arrange."""
    b, mid = C._manual(c, p, "qi")
    checks = [
        ("A calm heart (mood 70 or more)", p["mood"] >= 70),
        ("In full health (95 or more)", p["health"] >= 95),
        ("A pill ready to steady the meridians", c["res"]["pills"] >= 1),
        ("Someone keeping vigil: a friend, master or dao companion at home",
         any(_is_home(c, o) for o in C._friends(c, p)) or _is_home(c, _mentor(c, p)) or _is_home(c, _companion(c, p))),
        ("The season favours their element", p["element"] == lore.SEASON_ELEMENT[C._season(c)]),
        ("No heart demon and no pill toxin", not p["demon"] and p["toxin"] <= 3),
        ("A Meditation Chamber of level 2 or more", C._lvl(c, "meditation") >= 2),
        ("A cultivation method well suited to their root", bool(mid) and C.suit(p, mid)[0] == "well suited"),
    ]
    return min(4, sum(1 for _, ok in checks if ok) // 2), checks


def offer_fate(c: dict, p: dict, grade: int) -> None:
    """After a great realm: choose one of three fates. The three are fixed for this disciple and realm."""
    if c["pending"]:
        p["fate_due"] = grade                       # something else is waiting; the choice comes after it
        return
    p["fate_due"] = -1
    realm = p["step"] // 4
    r = C._rng(c, "fate", p["id"], realm)
    pool = [k for k, f in FATES.items() if k not in p["fates"] and (grade >= 3 or not f.get("rare"))]
    r.shuffle(pool)
    picks = pool[:3]
    if not picks:
        return
    C._ask(c, "fate", f"{p['name']} at the threshold of {C.REALMS[realm]}",
           f"A {GRADES[grade][0].lower()} breakthrough. In the stillness afterwards three roads open, and only one can be walked. "
           "The choice is for life." + (" A breakthrough this well prepared opens roads most never see." if grade >= 3 else ""),
           [(k, f"{FATES[k]['name']}: {FATES[k]['text']}") for k in picks], pawn=p["id"])


def after_breakthrough(c: dict, p: dict, grade: int) -> str:
    bonus = GRADES[grade][1]
    p["root_mult"] = round(p["root_mult"] + bonus, 2)
    offer_fate(c, p, grade)
    return (f"A {GRADES[grade][0].lower()} foundation" + (f": they will gather qi {int(round(bonus * 100))}% faster for life. " if bonus else ": nothing gained beyond the realm itself. "))


def _res_fate(c, ev, opt, r):
    p = C._p(c, ev["pawn"])
    if not p or opt not in FATES:
        return None
    p["fates"].append(opt)
    C._annal(c, f"{p['name']} took the fate “{FATES[opt]['name']}”.")
    return C._letter(c, "good", f"{p['name']}: {FATES[opt]['name']}", FATES[opt]["text"])


def beast_x(c: dict, p: dict) -> float:
    b = p.get("beast")
    return min(1.3, 1.08 + (c["hour"] - b["born"]) / 24.0 * 0.004) if b else 1.0


def combat_x(c: dict, p: dict) -> float:
    return road._nx(p, "combat") * beast_x(c, p) * _fx(p, "combat") * (1.2 if p.get("path") == "sword" else 1.0) * (1.1 if has(c, "strength") else 1.0) * (1.15 if "dread" in c["blessings"] else 1.0)


def hurt_x(c: dict, p: dict) -> float:
    return (0.8 if p.get("path") == "body" else 1.0) * _fx(p, "hurt") * road._nx(p, "hurt")


def hunger_x(c: dict, p: dict) -> float:
    return (0.85 if has(c, "frugality") else 1.0) * (1.1 if p.get("path") == "body" else 1.0) * _fx(p, "hunger") * road._nx(p, "hunger")


def research_x(c: dict) -> float:
    return 1.2 if has(c, "scholarship") else 1.0


def defense_extra(c: dict) -> float:
    n = sum(1 for p in C._home(c) if p.get("path") == "formation")
    return 0.12 * n * C.ward_power(c)


def ally_aid(c: dict, src: dict | None) -> float:
    allies = [s for s in c["sects"] if s.get("ally") and s is not src]
    return 0.2 * C.defense(c) * min(2, len(allies))


# ---------------------------------------------------------------------------
# hooks: time
# ---------------------------------------------------------------------------
_WORK = {v[0].lower() for v in C.JOBS.values()}


def hourly(c: dict, quiet: bool) -> None:
    for p in C._home(c):
        if p["doing"] in _WORK and not p.get("direct"):
            p["merit"] += 0.06


def daily(c: dict, quiet: bool) -> None:
    road.daily(c, quiet)
    for p in c["pawns"]:
        m = _mentor(c, p)
        if p.get("mentor") and not m:
            p["mentor"] = ""
        if p.get("companion") and not _companion(c, p):
            p["companion"] = ""
        p["xp_x"] = (1.3 if m else 1.0) * (1.1 if has(c, "scholarship") else 1.0) * _fx(p, "xp")
        if p.get("fate_due", -1) >= 0 and not c["pending"] and not quiet:
            offer_fate(c, p, int(p["fate_due"]))
        p["toxin"] = max(0.0, p["toxin"] - 0.2)
        if m and _is_home(c, m) and _is_home(c, p):
            C._bond(c, m, p, 0.6)
    for s in c["sects"]:
        if s.get("ally") and s["rel"] < 30:
            s["ally"] = False
            C._letter(c, "bad", f"The alliance with the {s['name']} has lapsed", "Relations cooled too far. Their envoy took down the banner.")
        if c["demonic"]:
            C._rel(s, -0.5 if s["kind"] == "righteous" else 0.2 if s["kind"] == "demonic" else 0)
    day = C._day(c)
    for br in c["branches"]:
        if br.get("sulking", 0) <= day and day % 12 == br["founded"] % 12 and day > br["founded"]:
            C._add(c, "rice", 15)
            C._add(c, "stones", 5)
            if not quiet:
                C._letter(c, "good", f"Tribute from the {br['name']}", "Fifteen rice and five spirit stones, with the branch master's respects.")
    if quiet:
        return
    # merit buys what the vault holds: the best artifact goes to whoever has earned it
    for a in sorted((x for x in c["artifacts"] if not x["owner"]), key=lambda x: -x["q"]):
        cost = (15, 30, 50)[a["q"]]
        want = [p for p in C._home(c) if not C.artifact_of(c, p) and p["merit"] >= cost and not p.get("master")]
        if want:
            p = max(want, key=lambda x: x["merit"])
            p["merit"] -= cost
            a["owner"] = p["id"]
            C._letter(c, "info", f"{p['name']} redeemed merit for the {a['name']}", f"{cost} contribution points, earned by work and at the gate. Nobody can say it was favouritism.")
            break
    if "blood_sutra" in c["manuals"] and not c["demonic"]:
        c["sutra_days"] += 1
    else:
        c["sutra_days"] = 0


def after_fight(c: dict, fighters: list[dict], ratio: float, how: str, src: dict | None, kind: str) -> None:
    c["marks"]["last_foe"] = src["id"] if src else ""
    for p in fighters:
        if _mentor(c, p) in fighters:
            road._trust(c, p, 8)                       # they stood at the gate together
        p["merit"] += 4 + (3 if ratio >= 0.9 else 0)
        if c["demonic"] and ratio >= 0.9:
            C._gain_qi(c, p, C.step_need(p["step"]) * 0.08)
    sg = c["siege"]
    if sg and src and sg["src"] == src["id"]:
        day = C._day(c)
        if ratio >= 0.9:
            sg["stage"] += 1
            sg["next"] = day + 3
            if sg["stage"] > 3:
                c["siege"] = None
                src.update(power=0.5, rel=-10.0, broken_until=day + 48)
                C._add(c, "stones", 40)
                mid = C._loot_manual(c, C._rng(c, "siege", day), 3)
                C._fame(c, 20)
                for p in c["pawns"]:
                    C._think(p, "siege", f"Broke the {src['name']}", 15, 168, c["hour"])
                C._letter(c, "good", f"The {src['name']} is broken", "Three battles, three victories. Their master sued for peace: forty spirit stones"
                          + (f", the {C._manual_name(mid)}" if mid else "") + ", and a year of quiet.")
                C._annal(c, f"The feud with the {src['name']} ended in victory after a three-stage siege.")
                poem(c, c["name"])
        else:
            c["siege"] = None
            src["power"] = round(min(1.6, src["power"] + 0.1), 2)
            src["broken_until"] = day + 12
            C._fame(c, -5)
            C._letter(c, "bad", f"The siege by the {src['name']} broke the gate", "They took what they wanted and withdrew. They will be bolder now.")


def saved_by_companion(c: dict, p: dict, fighters: list[dict]) -> bool:
    d = _companion(c, p)
    if not d or d not in fighters or d["health"] < 30:
        return False
    p["health"] = 8.0
    d["health"] = max(5.0, d["health"] - 25)
    C._bond(c, p, d, 10)
    C._letter(c, "info", f"{d['name']} took the blow meant for {p['name']}", "Dao companions do not let each other fall.")
    return True


def on_death(c: dict, p: dict) -> None:
    foe = C._sect(c, c["marks"].get("last_foe", ""))
    c["dead"] = (c["dead"] + [{"name": p["name"], "realm": C.realm_label(p["step"]), "day": C._day(c) + 1}])[-60:]
    if p.get("beast"):
        C._annal(c, f"{p['beast']['name']} lay on {p['name']}'s grave for nine days, then walked into the forest.")
    for o in c["pawns"]:
        if o is p:
            continue
        if o.get("mentor") == p["id"]:
            o["mentor"] = ""
            best = max(C.SKILLS, key=lambda s: p["skills"][s]["lv"])
            o["skills"][best]["lv"] = min(20, o["skills"][best]["lv"] + 2)
            o["resolve_until"] = c["hour"] + 24 * 30
            C._think(o, "master_dead", "Their master died", -20, 240, c["hour"])
            if foe:
                C._rel(foe, -20)
                o["title"] = o.get("title") or "the Avenger"
            C._letter(c, "bad", f"{o['name']} swore revenge for their master",
                      f"They knelt at {p['name']}'s grave for a day and a night. " + (f"The {foe['name']} has made an enemy for life. " if foe else "")
                      + "For thirty days they will gather qi half again as fast.")
        if o.get("companion") == p["id"]:
            o["companion"] = ""
            o["demon"] = min(3, o["demon"] + 1)
            C._think(o, "companion_dead", "Their dao companion died", -25, 300, c["hour"])
        elif C.bond(c, p, o) >= 70:
            o["demon"] = min(3, o["demon"] + 1)


def on_bt(c: dict, p: dict, success: bool, perfect: bool, trib: bool) -> None:
    if not success and trib:
        p["demon"] = min(3, p["demon"] + 1)
    if success and p.get("ancient") == 1:
        p["ancient"] = 2
        c["later"].append({"at": c["hour"] + 24 * C._rng(c, "nemesis").randint(18, 28), "kind": "nemesis", "pawn": p["id"]})
        C._letter(c, "good", f"{p['name']} remembered",
                  "The breakthrough tore a seal. Nine hundred years of memories came back at once: a throne, a betrayal, a fall. "
                  f"“This old one is {p['name']} only in this life.” They cultivate like someone retracing a road. Their old enemies will feel it too.")
        C._annal(c, f"{p['name']} was revealed as a reincarnated ancient.")
    if success and perfect:
        poem(c, p["name"])
    if _is_home(c, _mentor(c, p)):
        road.on_guard(c, p)


def on_broken_promise(c: dict) -> None:
    c["karma"] = max(-100.0, c["karma"] - 4)
    m = C._master(c)
    if m:
        m["demon"] = min(3, m["demon"] + 1)


def on_equip(c: dict, p: dict, a: dict) -> None:
    others = [o for o in C._home(c) if o is not p and not o.get("master") and not C.artifact_of(c, o)]
    if others:
        top = max(others, key=lambda o: o["merit"])
        if top["merit"] >= p["merit"] + 10:
            C._think(top, "merit_ignored", f"Earned more merit than {p['name']}, and was passed over", -6, 72, c["hour"])


def poem(c: dict, name: str) -> None:
    home = C._home(c)
    if not home:
        return
    scribe = max(home, key=lambda x: x["skills"]["scholar"]["lv"])
    line = C._rng(c, "poem", c["hour"]).choice(POEMS).format(name=name)
    C._annal(c, f"{scribe['name']} carved on the cliff face: “{line}”")
    for p in c["pawns"]:
        C._think(p, "verse", "A verse was carved for the sect", 3, 48, c["hour"])


# ---------------------------------------------------------------------------
# precepts and the council: what a choice costs beyond itself
# ---------------------------------------------------------------------------
def breaks(c: dict, kind: str, option: str) -> str:
    for pid in c["precepts"]:
        for k, o in PRECEPTS[pid]["breaks"]:
            if k == kind and option.startswith(o):
                return PRECEPTS[pid]["name"]
    return ""


def counsel(c: dict, ev: dict) -> str:
    """What the elders would do, if there are elders to ask."""
    if len(_elders(c)) < 2:
        return ""
    ids = [o["id"] for o in ev["options"]]
    kind = ev["kind"]
    pick = ""
    if kind == "omen":
        ratio = C.defense(c) / max(float(ev.get("strength", 1)), 1.0)
        pick = "fight" if ratio >= 1.0 else "wards" if "wards" in ids else "tribute" if "tribute" in ids else "fight"
    elif kind == "demonic_offer":
        pick = "refuse"
    elif kind == "embrace":
        pick = "burn"
    elif kind == "spy":
        pick = "turn"
    elif kind == "festival":
        pick = "hold"
    elif kind == "young_master":
        p = C._p(c, ev.get("pawn", ""))
        pick = "slap" if p and C.duel_power(c, p) >= 20 + C._day(c) * 0.7 else "endure"
    elif kind == "ally_call":
        pick = "send"
    return pick if pick in ids else ""


def before_choice(c: dict, ev: dict, option: str) -> None:
    for (k, o), v in KARMA.items():
        if k == ev["kind"] and option.startswith(o):
            c["karma"] = max(-100.0, min(100.0, c["karma"] + v))
    broke = breaks(c, ev["kind"], option)
    if broke:
        for p in c["pawns"]:
            C._think(p, "precept", f"The sect broke its precept: {broke}", -6, 72, c["hour"])
    want = counsel(c, ev)
    m = C._master(c)
    if want and m:
        for e in _elders(c):
            if option == want:
                C._bond(c, m, e, 2)
            else:
                C._think(e, "overruled", "Overruled by the Sect Master", -5, 48, c["hour"])
                C._bond(c, m, e, -5)
    if ev["kind"] == "omen" and option == "tribute" and c["siege"]:
        c["siege"] = None                          # paying them off ends the siege, and not in your favour


def annotate(c: dict, ev: dict) -> list[dict]:
    want = counsel(c, ev)
    return [{"id": str(o["id"]), "label": str(o["label"]), "warn": breaks(c, ev["kind"], o["id"]), "counsel": o["id"] == want} for o in ev["options"]]


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------
def calendar(c: dict, r: random.Random, day: int, year: int, doy: int) -> bool:
    """Fixed and forced events. True if one was raised."""
    marks = c["marks"]
    if c["dead"] and 2 <= doy < 12 and marks.get("qingming") != year:
        marks["qingming"] = year
        C._ask(c, "qingming", "Tomb-sweeping day",
               f"The graves on the north slope need tending: {', '.join(d['name'] for d in c['dead'][-4:])}. "
               "An offering of rice and a morning's silence lets the living set their grief down.",
               [("visit", "Sweep the graves together (5 rice)"), ("skip", "The dead do not need rice")])
        return True
    if c["kingdom"] >= 30 and doy >= 26 and marks.get("lord_gift") != year:
        marks["lord_gift"] = year
        C._add(c, "rice", 40)
        C._letter(c, "good", "The lord's harvest gift", "Forty rice, carried up the mountain by the lord's own bearers. The kingdom remembers its friends.")
    if c["sutra_days"] >= 20 and not marks.get("embrace_asked"):
        marks["embrace_asked"] = 1
        C._ask(c, "embrace", "The sutra asks for more",
               "Twenty nights the Blood Sutra has sat in the pavilion. The disciples who read it have started to finish each other's sentences. "
               "Go further, and the sect walks the demonic path: faster cultivation for everyone, qi taken from every enemy beaten at the gate, "
               "and the hatred of every righteous sect, for good.",
               [("embrace", "Walk the demonic path"), ("burn", "Burn it, now")])
        return True
    sg = c["siege"]
    if sg:
        s = C._sect(c, sg["src"])
        if not s:
            c["siege"] = None
        elif day >= sg["next"]:
            sg["next"] = day + 99
            C._omen(c, r, "raid", s, boost=(1.0, 1.3, 1.6)[min(3, sg["stage"]) - 1],
                    why=f"The siege of the {s['name']}: battle {sg['stage']} of three. Win all three and the feud ends on your terms.")
            return True
        return False
    for s in c["sects"]:
        if s["rel"] <= -60 and day >= 30 and s.get("broken_until", 0) <= day:
            c["siege"] = {"src": s["id"], "stage": 1, "next": day + 2}
            C._letter(c, "bad", f"The {s['name']} has declared a siege", "Their war banners are on the valley road. Three battles are coming, each harder than the last. "
                      "Beat all three and they are broken for a year; lose one and they take their spoils.")
            C._annal(c, f"The {s['name']} declared a siege.")
            break
    return False


def table(c: dict, day: int, others: list[dict]) -> list[tuple[str, int]]:
    marks = c["marks"]
    room = len(c["pawns"]) < C.pawn_cap(c)
    return [
        ("lord", 7 if day >= 10 and others else 0),
        ("taxes", 10 if c["kingdom"] <= -30 else 0),
        ("ally_call", 6 if any(s.get("ally") for s in c["sects"]) and len(others) >= 3 else 0),
        ("prodigy", 6 if not marks.get("prodigy") and day >= 15 and room else 0),
        ("wanderer", 10 if has(c, "hospitality") and room else 0),
        ("rare_herb", 5),
        ("beast_bond", 5 if day >= 8 and any(not p.get("beast") for p in others) else 0),
        ("branch_call", 6 if c["branches"] and len(others) >= 3 else 0),
        ("wanderer", 6 if c["karma"] >= 20 and room else 0),
    ]


def raise_event(c: dict, r: random.Random, kind: str) -> bool:
    others = C._others(c)
    if kind == "lord":
        what = r.choice(["rain", "guard", "heir"])
        if what == "rain":
            p = max(others, key=lambda x: x["skills"]["scholar"]["lv"])
            C._ask(c, "lord", "The lord begs for rain", f"Three months without rain in the lowlands. The lord's envoy asks for a cultivator to perform the rite. "
                   f"{p['name']} knows the old forms best and would be gone a day.",
                   [("send", f"Send {p['name']}"), ("refuse", "The heavens are not ours to command")], what=what, pawn=p["id"])
        elif what == "guard":
            p = C._strongest(c, 1)
            if not p:
                return True
            C._ask(c, "lord", "The lord asks for a guardian", f"Bandits have been at the tax caravans. The lord asks to borrow a cultivator for three days. {p[0]['name']} would do.",
                   [("send", f"Lend {p[0]['name']}"), ("refuse", "We are not sell-swords")], what=what, pawn=p[0]["id"])
        else:
            C._ask(c, "lord", "The lord's heir is brought to be tested", "A boy of nine in silk, a nervous tutor, and the lord himself, who very much wants to hear that his son has a spirit root.",
                   [("honest", "Test him honestly"), ("flatter", "Tell the lord what he wants to hear"), ("refuse", "The sect tests no one on demand")], what=what)
    elif kind == "taxes":
        C._ask(c, "taxes", "The lord's tax collectors", "Forty soldiers and a man with a ledger. “The mountain is the lord's, and so is a share of what grows on it.”",
               [("pay", "Pay (20 rice, 5 spirit stones)"), ("refuse", "Cultivators pay no tax")])
    elif kind == "ally_call":
        s = r.choice([x for x in c["sects"] if x.get("ally")])
        C._ask(c, "ally_call", f"The {s['name']} calls for aid", "Their envoy arrives on a winded horse. Beasts have broken into their lower halls. They ask for two of your strongest for two days.",
               [("send", "Send two disciples"), ("refuse", "We cannot spare anyone")], src=s["id"])
    elif kind == "prodigy":
        c["marks"]["prodigy"] = 1
        cand = C._make_pawn(c, c["next_pawn"])
        c["next_pawn"] += 1
        cand.update(age=12, ancient=1, origin="A village child who never cried, and who corrects the elders' calligraphy.")
        C._ask(c, "wanderer", "A strange child at the gate",
               f"{cand['name']}, twelve, walked up the ten thousand steps alone. {cand['root']} spirit root, the stone says. "
               "The child looks at the sect's formations the way a carpenter looks at someone else's joinery.",
               [("accept", "Take the child in"), ("decline", "Send the child home")], cand=cand)
    elif kind == "beast_bond":
        p = r.choice([x for x in others if not x.get("beast")])
        name = r.choice(lore.BEASTS)
        p["beast"] = {"name": name, "born": c["hour"]}
        C._think(p, "beast", f"A {name} chose them", 8, 120, c["hour"])
        C._letter(c, "good", f"A {name} followed {p['name']} home", "It will not leave their side. It fights beside them, and it will grow.")
    elif kind == "branch_call":
        br = r.choice(c["branches"])
        C._ask(c, "branch_call", f"The {br['name']} asks for help", f"{br['leader']} writes that bandits are testing the branch's walls. Two disciples for two days would settle it.",
               [("send", "Send two disciples"), ("refuse", "They must stand on their own")], branch=br["name"])
    elif kind == "rare_herb":
        c["rare"] += 1
        C._letter(c, "good", "A hundred-year spirit herb", "A forager found it under a fallen pine, glowing faintly. It is in the stores for the alchemists.")
    else:
        return False
    return True


def _fav(c: dict, delta: float) -> None:
    c["kingdom"] = max(-100.0, min(100.0, c["kingdom"] + delta * (1.5 if has(c, "compassion") and delta > 0 else 1.0)))


def _res_lord(c, ev, opt, r):
    what = ev["what"]
    if opt == "refuse":
        _fav(c, -15)
        return C._letter(c, "info", "The envoy left unsatisfied", "The lord will remember.")
    if what == "heir":
        if opt == "flatter":
            _fav(c, 15)
            C._fame(c, -2)
            return C._letter(c, "info", "The lord is delighted", "“A rare root, slow to show itself.” The tutor would not meet your eye.")
        if r.random() < 0.3 and len(c["pawns"]) < C.pawn_cap(c):
            p = C._make_pawn(c, c["next_pawn"], lucky=True)
            c["next_pawn"] += 1
            p.update(age=9, origin="Heir of the lowland lord, given to the mountain.", joined=c["hour"])
            c["pawns"].append(p)
            _fav(c, 25)
            C._annal(c, f"{p['name']}, the lord's heir, entered the sect.")
            return C._letter(c, "good", "The boy has a spirit root", f"A true one, {p['root']}. The lord wept, and left his son on the mountain as {p['name']}.")
        _fav(c, -10)
        C._fame(c, 3)
        return C._letter(c, "info", "No spirit root", "You said so plainly. The lord left in silence. In the market towns they say the sect cannot be bought.")
    p = C._p(c, ev.get("pawn", ""))
    if not p:
        return None
    hours = 24 if what == "rain" else 72
    p["away_until"], p["away_kind"] = c["hour"] + hours, "performing the rain rite" if what == "rain" else "guarding the lord's caravans"
    c["later"].append({"at": p["away_until"], "kind": "lord_return", "pawn": p["id"], "what": what})
    return C._letter(c, "info", f"{p['name']} went down to the lowlands", f"They will be gone {hours // 24} day{'s' if hours > 24 else ''}.")


def _res_taxes(c, ev, opt, r):
    if opt == "pay":
        if c["res"]["rice"] < 20 or c["res"]["stones"] < 5:
            return ("err", "You do not have 20 rice and 5 spirit stones.")
        c["res"]["rice"] -= 20
        c["res"]["stones"] -= 5
        _fav(c, 10)
        return C._letter(c, "info", "The tax was paid", "The man with the ledger made a neat mark.")
    _fav(c, -10)
    C._omen(c, r, "raid", None, boost=0.8, why="The lord's soldiers have been ordered to collect by force.")
    return C._letter(c, "bad", "The collectors were refused", "The soldiers are forming up below the gate.")


def _res_ally_call(c, ev, opt, r):
    s = C._sect(c, ev["src"])
    if not s:
        return None
    if opt != "send":
        C._rel(s, -25)
        s["ally"] = False
        return C._letter(c, "bad", f"The alliance with the {s['name']} is over", "An ally who does not come is no ally.")
    team = C._strongest(c, 2)
    if len(team) < 2:
        return ("err", "You do not have two healthy disciples to send.")
    for p in team:
        p["away_until"], p["away_kind"] = c["hour"] + 48, f"fighting beside the {s['name']}"
    c["later"].append({"at": c["hour"] + 48, "kind": "ally_return", "pawns": [p["id"] for p in team], "src": s["id"]})
    return C._letter(c, "info", f"Aid sent to the {s['name']}", f"{' and '.join(p['name'] for p in team)} rode out with the envoy.")


def _res_qingming(c, ev, opt, r):
    if opt == "visit":
        if c["res"]["rice"] < 5:
            return ("err", "Even the offering needs 5 rice.")
        c["res"]["rice"] -= 5
        for p in c["pawns"]:
            p["thoughts"] = [t for t in p["thoughts"] if t["k"] not in ("death", "companion_dead", "master_dead")]
            C._think(p, "qingming", "Swept the graves", 4, 72, c["hour"])
            p["demon"] = max(0, p["demon"] - 1)
        return C._letter(c, "good", "The graves were swept", "Incense, rice wine, and a long quiet morning. Grief sits lighter, and some heart demons with it.")
    for p in c["pawns"]:
        C._think(p, "qingming", "The dead were not honoured", -4, 72, c["hour"])
    return None


def _res_embrace(c, ev, opt, r):
    if opt == "burn":
        if "blood_sutra" in c["manuals"]:
            c["manuals"].remove("blood_sutra")
        for s in c["sects"]:
            C._rel(s, 6 if s["kind"] == "righteous" else 0)
        return C._letter(c, "good", "The Blood Sutra burned", "It screamed, a little. The pavilion smells of ash and relief.")
    c["demonic"] = True
    for s in c["sects"]:
        C._rel(s, -40 if s["kind"] == "righteous" else 40 if s["kind"] == "demonic" else -15)
        if s["kind"] == "righteous":
            s["ally"] = False
    C._annal(c, f"The {c['name']} turned to the demonic path.")
    return C._letter(c, "bad", "The sect walks the demonic path", "Every disciple cultivates a quarter faster, and takes qi from enemies beaten at the gate. "
                     "The righteous sects have sworn to end you.")


def _res_discipline(c, ev, opt, r):
    a, b = C._p(c, ev["a"]), C._p(c, ev["b"])
    pair = [p for p in (a, b) if p]
    if opt == "confine":
        for p in pair:
            p["away_until"], p["away_kind"] = c["hour"] + 24, "confined in the punishment hall"
            C._think(p, "punished", "Confined for brawling", -6, 48, c["hour"])
        if len(pair) == 2:
            C._bond(c, a, b, 8)
        for o in c["pawns"]:
            if o not in pair:
                C._think(o, "order", "Order is kept in the sect", 2, 48, c["hour"])
        return C._letter(c, "info", "A day in the punishment hall", "Bread, water, and the same four walls. They came out quieter.")
    if opt == "fine":
        for p in pair:
            p["merit"] = max(0.0, p["merit"] - 10)
            C._think(p, "punished", "Fined contribution points", -3, 48, c["hour"])
        return C._letter(c, "info", "Merit was docked", "Ten points each. The ledger does not forget.")
    for p in pair:
        C._think(p, "forgiven", "Forgiven by the Sect Master", 4, 48, c["hour"])
    if len(pair) == 2:
        C._bond(c, a, b, -6)
    return C._letter(c, "info", "The matter was let go", "Nothing was settled between them.")


def _res_demon(c, ev, opt, r):
    p = C._p(c, ev["pawn"])
    if not p:
        return None
    if opt == "pill":
        if c["res"]["pills"] < 1:
            return ("err", "No pills in the stores.")
        c["res"]["pills"] -= 1
        p["toxin"] += 1
        p["demon"] = max(0, p["demon"] - 1)
        return C._letter(c, "info", f"{p['name']} pressed the demon down", "A calming pill. It is quieter, not gone." if p["demon"] else "A calming pill, and it is gone.")
    friend = next((o for o in C._friends(c, p) if _is_home(c, o)), None)
    chance = 0.35 + 0.03 * p["skills"]["scholar"]["lv"] + p["mood"] / 400.0
    if opt == "friend" and friend:
        chance = 0.8
        C._bond(c, p, friend, 8)
    if r.random() < chance:
        p["demon"] = 0
        C._think(p, "demon_slain", "Faced their heart demon and won", 12, 120, c["hour"])
        return C._letter(c, "good", f"{p['name']} slew their heart demon",
                         (f"{friend['name']} sat outside the door all night, talking through it. " if opt == "friend" and friend else "Three days in a sealed room. ")
                         + "They came out lighter than they have been in a long time.")
    C._hurt(p, 15, c)
    C._think(p, "demon_lost", "The heart demon won this time", -8, 72, c["hour"])
    return C._letter(c, "bad", f"{p['name']} could not face it", "They came out grey and shaking. It can be tried again.")


def _res_succession(c, ev, opt, r):
    heir, old = C._p(c, opt), C._master(c)
    if not heir or not old:
        return None
    friends = sum(1 for v in c["bonds"].values() if v >= 30)
    gift = "dread" if c["demonic"] else "renowned" if c["fame"] >= 150 else "harmonious" if friends >= 3 else "enduring"
    if gift not in c["blessings"]:
        c["blessings"].append(gift)
    C._unequip(c, old)
    c["pawns"].remove(old)
    c["bonds"] = {k: v for k, v in c["bonds"].items() if old["id"] not in k.split("|")}
    for p in c["pawns"]:
        if p.get("mentor") == old["id"]:
            p["mentor"] = ""
        C._think(p, "ascension", "Watched the founder ascend", 15, 240, c["hour"])
    heir.update(master=True, direct=False, mentor="")
    C._annal(c, f"{old['name']} ascended. {heir['name']} became Sect Master. {BLESSINGS[gift]}")
    poem(c, old["name"])
    return C._letter(c, "good", f"{heir['name']} is Sect Master", f"{old['name']} stepped into the light and was gone. What they left behind: {BLESSINGS[gift]} "
                     "Your study now strengthens the new master.")


def _res_branch_call(c, ev, opt, r):
    br = next((b for b in c["branches"] if b["name"] == ev["branch"]), None)
    if not br:
        return None
    if opt != "send":
        br["sulking"] = C._day(c) + 24
        return C._letter(c, "info", f"The {br['name']} was left to itself", "They held, barely. No tribute will come for a while.")
    team = C._strongest(c, 2)
    if len(team) < 2:
        return ("err", "You do not have two healthy disciples to send.")
    for p in team:
        p["away_until"], p["away_kind"] = c["hour"] + 48, f"defending the {br['name']}"
    c["later"].append({"at": c["hour"] + 48, "kind": "ally_return", "pawns": [p["id"] for p in team], "src": ""})
    return C._letter(c, "info", f"Help sent to the {br['name']}", f"{' and '.join(p['name'] for p in team)} went down the mountain.")


RESOLVERS = {"fate": _res_fate, "branch_call": _res_branch_call, "lord": _res_lord, "taxes": _res_taxes, "ally_call": _res_ally_call, "qingming": _res_qingming, "embrace": _res_embrace,
             "discipline": _res_discipline, "demon": _res_demon, "succession": _res_succession}
LATER = {"nemesis", "lord_return", "ally_return", "retreat_return"}


def later(c: dict, item: dict, r: random.Random) -> bool:
    kind = item["kind"]
    if kind in road.LATER:
        return road.later(c, item, r)
    if kind == "nemesis":
        if c["pending"]:
            return False
        p = C._p(c, item.get("pawn", ""))
        if p:
            C._omen(c, r, "raid", None, boost=1.5, why=f"Hunters from the Nine Nether Palace have crossed half the world for {p['name']}, whom they killed once before.")
    elif kind == "lord_return":
        p = C._p(c, item.get("pawn", ""))
        if p:
            _fav(c, 15)
            p["merit"] += 6
            if item.get("what") == "rain":
                C._add(c, "rice", 30)
                C._letter(c, "good", "It rained in the lowlands", f"{p['name']} is back, soaked and pleased. The lord sent thirty rice.")
            else:
                C._add(c, "stones", 10)
                C._xp(p, "combat", 30)
                C._letter(c, "good", "The caravans came through", f"{p['name']} is back with ten spirit stones and the lord's thanks.")
    elif kind == "ally_return":
        team = [p for p in (C._p(c, i) for i in item.get("pawns", [])) if p]
        s = C._sect(c, item.get("src", ""))
        C._rel(s, 10)
        C._add(c, "stones", 10)
        for p in team:
            C._xp(p, "combat", 30)
            p["merit"] += 6
        if len(team) == 2:
            C._bond(c, team[0], team[1], 8)
        C._letter(c, "good", "The disciples are back", f"The {s['name'] if s else 'branch'} sent ten spirit stones and its thanks.")
    elif kind == "retreat_return":
        p = C._p(c, item.get("pawn", ""))
        if p:
            C._gain_qi(c, p, C.step_need(p["step"]) * 1.2)
            roll = r.random()
            if roll < 0.25:
                C._gain_qi(c, p, C.step_need(p["step"]) * 0.5)
                p["inspired_until"] = c["hour"] + 48
                C._think(p, "retreat", "An epiphany in seclusion", 12, 120, c["hour"])
                C._letter(c, "good", f"{p['name']} came out of seclusion changed", "The door opened by itself. An epiphany, they said, and would not say more.")
            elif roll > 0.92 - (0.1 if p["mood"] < 40 else 0) - 0.05 * p["demon"]:
                C._hurt(p, 30, c)
                p["demon"] = min(3, p["demon"] + 1)
                C._letter(c, "bad", f"{p['name']}'s seclusion went wrong", "Qi deviation in the dark, with nobody to pull them out. They are hurt, and something followed them out.")
            else:
                C._letter(c, "info", f"{p['name']} came out of seclusion", "Thinner, calmer, and a good deal further along.")
    return True


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------
def brawl(c: dict, a: dict, b: dict) -> None:
    """Two disciples came to blows: the Sect Master decides what follows."""
    if not c["pending"]:
        C._ask(c, "discipline", f"{a['name']} and {b['name']} before the punishment hall",
               "Both are bruised and neither is sorry. The other disciples are watching to see what the sect's rules are worth.",
               [("confine", "A day's confinement for both"), ("fine", "Dock their merit"), ("forgive", "Let it go")], a=a["id"], b=b["id"])


def apprentice(st: dict, pawn_id: str, mentor_id: str, now: float) -> dict:
    c = C._c(st, now)
    p, m = C._p(c, pawn_id), C._p(c, mentor_id)
    if not p or not m or p is m or p.get("master"):
        return {"ok": False, "error": "Choose a disciple and a master."}
    if not (m.get("master") or C.rank_of(m) >= 2):
        return {"ok": False, "error": "Only the Sect Master, a Core Disciple or an Elder may take a personal disciple."}
    if m["step"] <= p["step"]:
        return {"ok": False, "error": "A master must stand higher than the disciple."}
    if any(o.get("mentor") == m["id"] for o in c["pawns"]):
        return {"ok": False, "error": f"{m['name']} already has a personal disciple."}
    p["mentor"] = m["id"]
    C._bond(c, p, m, 15)
    C._think(p, "accepted", f"Accepted as {m['name']}'s personal disciple", 8, 120, c["hour"])
    C._annal(c, f"{p['name']} knelt and offered tea to {m['name']} as their master.")
    return {"ok": True, "event": C._letter(c, "good", f"{p['name']} is now {m['name']}'s disciple",
                                           "Three bows and a cup of tea. Their skills will grow faster, and their master will stand guard at breakthroughs.")}


def companion(st: dict, pawn_id: str, other_id: str, now: float) -> dict:
    c = C._c(st, now)
    a, b = C._p(c, pawn_id), C._p(c, other_id)
    if not a or not b or a is b:
        return {"ok": False, "error": "Choose two disciples."}
    if C.bond(c, a, b) < 70:
        return {"ok": False, "error": "Only sworn siblings are close enough to become dao companions."}
    if a.get("companion") or b.get("companion"):
        return {"ok": False, "error": "One of them already has a dao companion."}
    a["companion"], b["companion"] = b["id"], a["id"]
    for p in (a, b):
        C._think(p, "dao", "Bound to a dao companion", 12, 168, c["hour"])
    C._annal(c, f"{a['name']} and {b['name']} became dao companions.")
    return {"ok": True, "event": C._letter(c, "good", f"{a['name']} and {b['name']} are dao companions",
                                           "They will walk the long road together: faster cultivation side by side, and each will take a blow meant for the other.")}


def face_demon(st: dict, pawn_id: str, now: float) -> dict:
    c = C._c(st, now)
    p = C._p(c, pawn_id)
    if not p or not p["demon"]:
        return {"ok": False, "error": "They carry no heart demon."}
    if c["pending"]:
        return {"ok": False, "error": "Answer what is waiting first."}
    opts = [("confront", "Face it alone in a sealed room")]
    if c["res"]["pills"] >= 1:
        opts.append(("pill", "Quiet it with a pill (weakens it by one)"))
    if any(_is_home(c, o) for o in C._friends(c, p)):
        opts.append(("friend", "Ask a friend to sit vigil"))
    C._ask(c, "demon", f"{p['name']}'s heart demon", "It has a face they know. It drags at every breakthrough and sours every day until it is faced.", opts, pawn=p["id"])
    return {"ok": True}


def set_precept(st: dict, precept: str, on: bool, now: float) -> dict:
    c = C._c(st, now)
    if precept not in PRECEPTS:
        return {"ok": False, "error": "Unknown precept."}
    if on and precept not in c["precepts"]:
        if len(c["precepts"]) >= 3:
            return {"ok": False, "error": "A sect lives by three precepts at most."}
        c["precepts"].append(precept)
        C._annal(c, f"The sect took the precept “{PRECEPTS[precept]['name']}”.")
    elif not on and precept in c["precepts"]:
        c["precepts"].remove(precept)
        for p in c["pawns"]:
            C._think(p, "precept_drop", f"The sect abandoned “{PRECEPTS[precept]['name']}”", -5, 96, c["hour"])
    return {"ok": True}


def set_path(st: dict, pawn_id: str, path: str, now: float) -> dict:
    c = C._c(st, now)
    p = C._p(c, pawn_id)
    if not p or path not in PATHS:
        return {"ok": False, "error": "Unknown disciple or path."}
    if p["step"] < 8:
        return {"ok": False, "error": "A path is chosen at Foundation Establishment."}
    if p.get("path"):
        return {"ok": False, "error": "A path, once chosen, is walked to the end."}
    p["path"] = path
    return {"ok": True, "event": C._letter(c, "info", f"{p['name']} chose the {PATHS[path]['name'].lower()}", PATHS[path]["text"])}


def retreat(st: dict, pawn_id: str, now: float) -> dict:
    c = C._c(st, now)
    p = C._p(c, pawn_id)
    if not p or p.get("master") or not _is_home(c, p):
        return {"ok": False, "error": "Choose a disciple who is home."}
    if c["res"]["rice"] < 10:
        return {"ok": False, "error": "Seclusion needs 10 rice sealed in with them."}
    c["res"]["rice"] -= 10
    p["away_until"], p["away_kind"] = c["hour"] + 288, "in closed-door seclusion"
    c["later"].append({"at": p["away_until"], "kind": "retreat_return", "pawn": p["id"]})
    return {"ok": True, "event": C._letter(c, "info", f"{p['name']} entered closed-door seclusion",
                                           "Twelve days behind a sealed door. They cannot work or fight; they will come out much further along, or changed.")}


def set_recipe(st: dict, recipe: str, now: float) -> dict:
    c = C._c(st, now)
    if recipe not in RECIPES:
        return {"ok": False, "error": "Unknown recipe."}
    c["recipe"] = recipe
    return {"ok": True}


def brew(c: dict, p: dict) -> None:
    """A batch is ready: the alchemist makes whatever the hall is set to, if the herbs allow."""
    rec = RECIPES.get(c["recipe"], RECIPES["pill"])
    special = c["recipe"] != "pill" and c["res"]["herbs"] >= rec.get("herbs", 0) and c["rare"] >= rec.get("rare", 0)
    if not special:
        C._add(c, "herbs", -(2 if C._has(c, "refinement") else 3))
        C._add(c, "pills", 1)
        return
    C._add(c, "herbs", -rec["herbs"])
    c["rare"] -= rec["rare"]
    if C._rng(c, "brew", c["hour"]).random() < max(0.04, 0.28 - 0.016 * p["skills"]["craft"]["lv"]):
        C._letter(c, "bad", "A batch was ruined", f"{p['name']} misjudged the flame. The {rec['name']} is slag, and the rare herbs with it.")
        return
    c["elixirs"][c["recipe"]] += 1
    p["merit"] += 5
    C._letter(c, "good", f"{p['name']} brewed a {rec['name']}", rec["text"])


def take_marrow(st: dict, pawn_id: str, now: float) -> dict:
    c = C._c(st, now)
    p = C._p(c, pawn_id)
    if not p or c["elixirs"]["marrow"] < 1:
        return {"ok": False, "error": "No Marrow-Cleansing Pill in the stores."}
    if p.get("marrow"):
        return {"ok": False, "error": "It only works once."}
    c["elixirs"]["marrow"] -= 1
    p["marrow"] = True
    p["root_mult"] = round(p["root_mult"] + 0.08, 2)
    p["toxin"] += 2
    return {"ok": True, "event": C._letter(c, "good", f"{p['name']} took the Marrow-Cleansing Pill", "A night of black sweat, and in the morning their meridians ran clear.")}


def ally(st: dict, sect_id: str, now: float) -> dict:
    c = C._c(st, now)
    s = C._sect(c, sect_id)
    if not s or s.get("ally"):
        return {"ok": False, "error": "No such sect, or already an ally."}
    if s["rel"] < 50:
        return {"ok": False, "error": "They must think very well of you first (+50)."}
    if c["demonic"] and s["kind"] == "righteous":
        return {"ok": False, "error": "No righteous sect allies with the demonic path."}
    if c["res"]["stones"] < 20:
        return {"ok": False, "error": "An oath of alliance is sealed with 20 spirit stones."}
    c["res"]["stones"] -= 20
    s["ally"] = True
    C._annal(c, f"The sect swore an alliance with the {s['name']}.")
    return {"ok": True, "event": C._letter(c, "good", f"Alliance with the {s['name']}", "They will send disciples when you are attacked, and will expect the same of you.")}


def found_branch(st: dict, pawn_id: str, now: float) -> dict:
    """Send an elder and two disciples away for good to raise a branch sect. It pays tribute, and sometimes calls for help."""
    c = C._c(st, now)
    leader = C._p(c, pawn_id)
    if not leader or leader.get("master") or C.rank_of(leader) < 2:
        return {"ok": False, "error": "A branch needs a Core Disciple or an Elder to lead it."}
    if len(c["branches"]) >= 3:
        return {"ok": False, "error": "Three branches is as far as one mountain's name reaches."}
    if C._lvl(c, "main_hall") < 4 or len(c["pawns"]) < 8 or c["res"]["stones"] < 100:
        return {"ok": False, "error": "A branch needs Main Hall level 4, eight disciples, and 100 spirit stones to endow it."}
    followers = sorted((p for p in C._home(c) if p is not leader and not p.get("master") and not p.get("direct")), key=lambda p: p["step"])[:2]
    if len(followers) < 2:
        return {"ok": False, "error": "Two disciples must be home to go with them."}
    c["res"]["stones"] -= 100
    name = f"{c['name']}, {('Eastern', 'Southern', 'Western')[len(c['branches'])]} Branch"
    for p in [leader, *followers]:
        C._unequip(c, p)
        c["pawns"].remove(p)
        c["bonds"] = {k: v for k, v in c["bonds"].items() if p["id"] not in k.split("|")}
    for p in c["pawns"]:
        C._think(p, "branch", "The sect founded a branch", 8, 120, c["hour"])
    c["branches"].append({"name": name, "leader": leader["name"], "founded": C._day(c), "sulking": 0})
    C._fame(c, 20)
    C._annal(c, f"{leader['name']} left with {followers[0]['name']} and {followers[1]['name']} to found the {name}.")
    poem(c, leader["name"])
    return {"ok": True, "event": C._letter(c, "good", f"The {name} is founded", f"{leader['name']} bowed nine times at the gate and did not look back. "
                                           "Tribute will come every twelve days, and sometimes a call for help.")}


def set_style(st: dict, colour: str, motto: str, now: float) -> dict:
    c = C._c(st, now)
    if colour and colour not in COLOURS:
        return {"ok": False, "error": "Unknown colour."}
    if colour:
        c["style"]["colour"] = colour
    c["style"]["motto"] = " ".join(str(motto or "").split())[:60]
    return {"ok": True}


def succession(c: dict) -> None:
    heirs = sorted((p for p in c["pawns"] if not p.get("master")), key=lambda p: -p["step"])[:3]
    if heirs and not c["pending"]:
        C._ask(c, "succession", "The founder is leaving", "The sky has opened for the Sect Master. Before stepping through, one last duty: name who leads the sect now.",
               [(p["id"], f"{p['name']} ({C.realm_label(p['step'])})") for p in heirs])


# ---------------------------------------------------------------------------
# view and repair
# ---------------------------------------------------------------------------
def rumours(c: dict) -> list[str]:
    out = []
    day, hour = C._day(c), c["hour"]
    doy = day % (C.DAYS_PER_SEASON * 4)
    for x in c["later"]:
        if x["at"] - hour <= 72:
            if x["kind"] == "elder":
                s = C._sect(c, x.get("src", ""))
                out.append(f"Riders in the colours of the {s['name'] if s else 'a rival sect'} were seen on the valley road.")
            elif x["kind"] == "nemesis":
                out.append("Strangers in black have been asking the ferrymen about a child with old eyes.")
            elif x["kind"] == "ring":
                out.append("The kitchen girl swears she heard an old man's voice from the new boy's room.")
    if c["siege"]:
        out.append("The war banners below have not moved. The next battle is days away at most.")
    to_winter = (3 * C.DAYS_PER_SEASON - doy) % (4 * C.DAYS_PER_SEASON)
    if 0 < to_winter <= 4:
        out.append(f"The geese went south early. Winter in {to_winter} day{'s' if to_winter != 1 else ''}.")
    if 26 <= doy < 30:
        out.append("Every inn in the valley is full: the Hundred Sects Tournament is days away.")
    if day % C.DAYS_PER_SEASON in (C.FESTIVAL_DAY - 2, C.FESTIVAL_DAY - 1) and C.festival_of(day):
        out.append("The cooks are counting rice sacks and looking hopeful. A festival is near.")
    if c["sutra_days"] >= 14 and not c["demonic"]:
        out.append("Disciples who read the Blood Sutra have started to dream the same dream.")
    if c["kingdom"] <= -20:
        out.append("The lord's stewards have been measuring the mountain road.")
    if c["karma"] >= 20:
        out.append("Beggars at the temple gate bless the sect by name.")
    elif c["karma"] <= -20:
        out.append("Mothers in the valley hush their children with the sect's name.")
    return out[:4]


def alerts(c: dict) -> list[dict]:
    out = []
    for p in c["pawns"]:
        if p["step"] >= 8 and not p.get("path") and not p.get("master"):
            out.append({"kind": "good", "text": f"{p['name']} has reached Foundation Establishment and can choose a path.", "pawn": str(p["id"])})
        if p["demon"] >= 2:
            out.append({"kind": "bad", "text": f"{p['name']}'s heart demon is growing.", "pawn": str(p["id"])})
    return out[:3]


def pawn_view(c: dict, p: dict) -> dict:
    m, d = _mentor(c, p), _companion(c, p)
    student = next((o for o in c["pawns"] if o.get("mentor") == p["id"]), None)
    mentors = [o for o in c["pawns"] if o is not p and (o.get("master") or C.rank_of(o) >= 2) and o["step"] > p["step"]
               and not any(x.get("mentor") == o["id"] for x in c["pawns"])]
    return {
        "mentor": str(m["name"]) if m else "", "student": str(student["name"]) if student else "",
        "mentors": [{"id": str(o["id"]), "name": str(o["name"])} for o in mentors] if not m and not p.get("master") else [],
        "companion": str(d["name"]) if d else "",
        "can_bind": [{"id": str(o["id"]), "name": str(o["name"])} for o in c["pawns"]
                     if o is not p and C.bond(c, p, o) >= 70 and not o.get("companion")] if not d else [],
        "demon": C._f(p["demon"]), "merit": C._f(p["merit"]), "toxin": C._f(p["toxin"], 1),
        "path": PATHS[p["path"]]["name"] if p.get("path") in PATHS else "", "can_path": p["step"] >= 8 and not p.get("path"),
        "can_marrow": c["elixirs"]["marrow"] >= 1 and not p.get("marrow"),
        **road.pawn_view(c, p),
        "can_retreat": not p.get("master") and _is_home(c, p),
        "fates": [{"name": f["name"], "text": f["text"]} for f in _fates(p)],
        "grade": ({"name": GRADES[bt_grade(c, p)[0]][0], "bonus": C._f(100 * GRADES[bt_grade(c, p)[0]][1]),
                   "checks": [{"label": str(a), "ok": bool(b)} for a, b in bt_grade(c, p)[1]]} if C.ready(p) else None),
        "beast": ({"name": str(p["beast"]["name"]), "bonus": C._f(100 * (beast_x(c, p) - 1))} if p.get("beast") else None),
        "can_lead_branch": not p.get("master") and C.rank_of(p) >= 2,
    }


def view(c: dict) -> dict:
    return {
        "precepts": [{"id": k, "name": v["name"], "text": v["text"], "on": k in c["precepts"]} for k, v in PRECEPTS.items()],
        "paths": [{"id": k, "name": v["name"], "text": v["text"]} for k, v in PATHS.items()],
        "recipes": [{"id": k, "name": v["name"], "text": v["text"], "on": c["recipe"] == k,
                     "cost": f"{v['herbs']} herbs, {v['rare']} rare herb{'s' if v['rare'] != 1 else ''}" if "rare" in v else ""} for k, v in RECIPES.items()],
        "elixirs": {"marrow": C._f(c["elixirs"]["marrow"]), "berserk": C._f(c["elixirs"]["berserk"])}, "rare": C._f(c["rare"]),
        "kingdom": {"favour": C._f(c["kingdom"]), "stance": "Grateful" if c["kingdom"] >= 30 else "Resentful" if c["kingdom"] <= -30 else "Indifferent"},
        "demonic": bool(c["demonic"]), "blessings": [BLESSINGS[b] for b in c["blessings"] if b in BLESSINGS],
        "tombs": [{"name": str(d["name"]), "realm": str(d["realm"]), "day": C._f(d["day"]), "when": C.calendar_label(C._f(d["day"]) - 1)} for d in reversed(c["dead"][-20:])],
        "siege": ({"sect": str((C._sect(c, c["siege"]["src"]) or {}).get("name", "")), "stage": C._f(min(3, c["siege"]["stage"]))} if c["siege"] else None),
        **road.view(c),
        "rumours": rumours(c), "council": len(_elders(c)) >= 2,
        "branches": [{"name": str(b["name"]), "leader": str(b["leader"]), "sulking": b.get("sulking", 0) > C._day(c)} for b in c["branches"]],
        "style": {"colour": str(c["style"]["colour"]), "hex": COLOURS.get(c["style"]["colour"], COLOURS["gold"]), "motto": str(c["style"]["motto"])},
        "colours": list(COLOURS),
        "map": [{"name": str(c["name"]), "text": "Home.", "x": 50, "y": 52, "kind": "home"}]
               + [{"name": n, "text": t, "x": x, "y": y, "kind": "place"} for n, t, x, y in PLACES_ON_MAP]
               + [{"name": str(s["name"]), "text": f"{s['kind'].capitalize()} sect. {C.stance(float(s['rel']))}.", "kind": "ally" if s.get("ally") else "foe" if s["rel"] <= -15 else "sect",
                   "x": (18, 84, 60)[i % 3], "y": (36, 44, 10)[i % 3]} for i, s in enumerate(c["sects"])]
               + [{"name": str(b["name"]), "text": f"Led by {b['leader']}.", "kind": "branch", "x": (70, 36, 22)[i % 3], "y": (50, 66, 80)[i % 3]} for i, b in enumerate(c["branches"])],
    }


def repair(c: dict, num) -> None:
    c["precepts"] = [p for p in c["precepts"] if p in PRECEPTS][:3] if isinstance(c["precepts"], list) else []
    c["kingdom"] = num(c.get("kingdom"), -100, 100)
    e = c["elixirs"] if isinstance(c["elixirs"], dict) else {}
    c["elixirs"] = {"marrow": int(num(e.get("marrow"), 0, 999)), "berserk": int(num(e.get("berserk"), 0, 999))}
    c["rare"] = num(c.get("rare"), 0, 1e5)
    c["recipe"] = c["recipe"] if c.get("recipe") in RECIPES else "pill"
    c["demonic"] = bool(c.get("demonic"))
    c["blessings"] = [b for b in c["blessings"] if b in BLESSINGS] if isinstance(c["blessings"], list) else []
    c["dead"] = [{"name": str(d.get("name") or ""), "realm": str(d.get("realm") or ""), "day": int(num(d.get("day"), 0, 1e7))}
                 for d in c["dead"] if isinstance(d, dict)][-60:] if isinstance(c["dead"], list) else []
    sg = c.get("siege")
    c["siege"] = ({"src": str(sg.get("src") or ""), "stage": int(num(sg.get("stage"), 1, 4, 1.0)), "next": int(num(sg.get("next"), 0, 1e7))}
                  if isinstance(sg, dict) else None)
    c["sutra_days"] = int(num(c.get("sutra_days"), 0, 1e5))
    c["marks"] = {str(k): (v if isinstance(v, (int, float, str)) else 0) for k, v in c["marks"].items()} if isinstance(c["marks"], dict) else {}
    c["karma"] = num(c.get("karma"), -100, 100)
    road.repair(c, num)
    c["branches"] = [{"name": str(b.get("name") or "Branch"), "leader": str(b.get("leader") or ""), "founded": int(num(b.get("founded"), 0, 1e7)),
                      "sulking": int(num(b.get("sulking"), 0, 1e7))} for b in c["branches"] if isinstance(b, dict)][:3] if isinstance(c["branches"], list) else []
    st_ = c["style"] if isinstance(c["style"], dict) else {}
    c["style"] = {"colour": st_.get("colour") if st_.get("colour") in COLOURS else "gold", "motto": str(st_.get("motto") or "")[:60]}
    ids = {p["id"] for p in c["pawns"]}
    for p in c["pawns"]:
        b = p.get("beast")
        p["beast"] = {"name": str(b.get("name") or "Spirit beast"), "born": int(num(b.get("born"), 0, 1e9))} if isinstance(b, dict) else None
        p["fates"] = [f for f in p.get("fates", []) if f in FATES][:8] if isinstance(p.get("fates"), list) else []
        p["fate_due"] = int(num(p.get("fate_due"), -1, 4, -1.0))
        p["mentor"] = p.get("mentor") if p.get("mentor") in ids else ""
        p["companion"] = p.get("companion") if p.get("companion") in ids else ""
        p["demon"] = int(num(p.get("demon"), 0, 3))
        p["merit"] = num(p.get("merit"), 0, 1e6)
        p["toxin"] = num(p.get("toxin"), 0, 99)
        p["path"] = p.get("path") if p.get("path") in PATHS else ""
        p["marrow"] = bool(p.get("marrow"))
        p["ancient"] = int(num(p.get("ancient"), 0, 2))
        p["xp_x"] = num(p.get("xp_x"), 0.5, 3.0, 1.0)
    for s in c["sects"]:
        s["ally"] = bool(s.get("ally"))
        s["broken_until"] = int(num(s.get("broken_until"), 0, 1e7))


from . import road  # noqa: E402  (road needs this module; imported last, like dao in colony)

PAWN.update(road.PAWN)
RESOLVERS.update(road.RESOLVERS)
LATER |= road.LATER
