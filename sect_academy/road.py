"""Six things the best cultivation games do that the sect lacked (see
docs/research/notes/competitors_cultivation_games.md): expeditions you staff and steer, a
master-disciple trust track, named rival cultivators who advance by a visible rule, a meridian
chart, one requirement per great realm (always with two routes), and standing orders.

dao.py calls the hooks here the same way colony.py calls dao's.
"""
from __future__ import annotations

import random

from . import colony as C
from . import dao as D
from . import lore

PAWN = {"trust": 0.0, "stations": 0, "meridians": []}


def defaults() -> dict:
    return {"standing": {"pills": 0, "repeat": False}, "presets": {}, "trip_plan": None}


# ---------------------------------------------------------------------------
# meridians: a small chart per disciple; one point per stage reached
# ---------------------------------------------------------------------------
NODES = {
    "sea":    {"name": "Sea of Qi", "cost": 1, "text": "+4% cultivation speed.", "qi": 1.04},
    "pillow": {"name": "Jade Pillow", "cost": 1, "needs": ["sea"], "text": "+4% cultivation speed.", "qi": 1.04},
    "crown":  {"name": "Hundred Meetings", "cost": 2, "needs": ["pillow"], "text": "+6% cultivation speed.", "qi": 1.06},
    "wrist":  {"name": "Iron Wrist", "cost": 1, "text": "+5% fighting strength.", "combat": 1.05},
    "tiger":  {"name": "Tiger's Mouth", "cost": 2, "needs": ["wrist"], "text": "+8% fighting strength.", "combat": 1.08},
    "lake":   {"name": "Calm Lake", "cost": 1, "text": "+3 mood.", "mood": 3},
    "still":  {"name": "Still Heart", "cost": 2, "needs": ["lake"], "text": "+4 to every breakthrough.", "bt": 4},
    "skin":   {"name": "Stone Skin", "cost": 1, "text": "Takes 6% less damage.", "hurt": 0.94},
    "belly":  {"name": "Empty Belly", "cost": 1, "needs": ["skin"], "text": "Eats 10% less.", "hunger": 0.9},
    "linked": {"name": "Linked Hearts", "cost": 1, "cond": "friend", "text": "+6% cultivation speed while a friend is home. Needs a friend to open.", "qi_friend": 1.06},
    "gate":   {"name": "Gate of the Root", "cost": 1, "cond": "suited", "text": "+6% cultivation speed. Needs a cultivation method well suited to their element.", "qi": 1.06},
    "heaven": {"name": "Heaven's Door", "cost": 3, "needs": ["crown", "still"], "text": "+5 to every breakthrough and +5% cultivation speed.", "bt": 5, "qi": 1.05},
}


def points(p: dict) -> int:
    return max(0, int(p["step"]) - sum(NODES[n]["cost"] for n in p.get("meridians", []) if n in NODES))


def _nodes(p: dict) -> list[dict]:
    return [NODES[n] for n in p.get("meridians", []) if n in NODES]


def _node_blocked(c: dict, p: dict, nid: str) -> str:
    n = NODES[nid]
    missing = [NODES[x]["name"] for x in n.get("needs", []) if x not in p["meridians"]]
    if missing:
        return f"Open {' and '.join(missing)} first."
    if n.get("cond") == "friend" and not C._friends(c, p):
        return "They need a friend in the sect."
    if n.get("cond") == "suited":
        mid = C._manual(c, p, "qi")[1]
        if not mid or C.suit(p, mid)[0] != "well suited":
            return f"They need a cultivation method of the {p['element']} element."
    if points(p) < n["cost"]:
        return f"Needs {n['cost']} point{'s' if n['cost'] > 1 else ''}; they have {points(p)}. One point comes with every stage reached."
    return ""


def open_node(st: dict, pawn_id: str, nid: str, now: float) -> dict:
    c = C._c(st, now)
    p = C._p(c, pawn_id)
    if not p or nid not in NODES or nid in p["meridians"]:
        return {"ok": False, "error": "Unknown disciple or meridian, or it is already open."}
    why = _node_blocked(c, p, nid)
    if why:
        return {"ok": False, "error": why}
    p["meridians"].append(nid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# hooks: numbers (called from dao's)
# ---------------------------------------------------------------------------
def qi_rows(c: dict, p: dict) -> list[tuple[str, float]]:
    rows = [(f"Meridian: {n['name']}", n["qi"]) for n in _nodes(p) if "qi" in n]
    if "linked" in p["meridians"] and any(D._is_home(c, o) for o in C._friends(c, p)):
        rows.append(("Meridian: Linked Hearts", NODES["linked"]["qi_friend"]))
    if p["stations"] >= 2:
        rows.append(("Their master's private teaching", 1.08))
    return rows


def mood_rows(c: dict, p: dict) -> list[tuple[str, int]]:
    return [(f"Meridian: {n['name']}", n["mood"]) for n in _nodes(p) if "mood" in n]


def bt_rows(c: dict, p: dict) -> list[tuple[str, int]]:
    rows = [(f"Meridian: {n['name']}", n["bt"]) for n in _nodes(p) if "bt" in n]
    if p["stations"] >= 3:
        rows.append(("Heir to their master's line", 5))
    return rows


def _nx(p: dict, key: str) -> float:
    out = 1.0
    for n in _nodes(p):
        out *= n.get(key, 1.0)
    return out


# ---------------------------------------------------------------------------
# the trust between master and disciple: three stations, each a scene and a gift
# ---------------------------------------------------------------------------
STATIONS = [(30, "told the story of how they came to the mountain"), (60, "passed on a teaching they have shown no one else"), (90, "named them heir to the line")]


def _trust(c: dict, p: dict, delta: float) -> None:
    m = D._mentor(c, p)
    if not m:
        return
    p["trust"] = max(0.0, min(100.0, p["trust"] + delta))
    while p["stations"] < len(STATIONS) and p["trust"] >= STATIONS[p["stations"]][0]:
        p["stations"] += 1
        n = p["stations"]
        if n == 1:
            best = max(C.SKILLS, key=lambda s: m["skills"][s]["lv"])
            p["skills"][best]["lv"] = min(20, p["skills"][best]["lv"] + 2)
            gift = f"{p['name']} gained two levels of {C.SKILL_NAMES[best].lower()}, the skill {m['name']} knows best."
        elif n == 2:
            gift = f"{p['name']} will gather qi 8% faster for life."
        else:
            p["title"] = p.get("title") or f"Heir of {m['name'].split(' ')[0]}"
            gift = f"{p['name']} gains +5 to every breakthrough."
        C._think(p, "station", f"{m['name']} {STATIONS[n - 1][1]}", 10, 120, c["hour"])
        C._letter(c, "good", f"{m['name']} {STATIONS[n - 1][1]}", f"A long evening, the two of them and one lamp. {gift}")
        C._annal(c, f"{m['name']} {STATIONS[n - 1][1].replace('them', p['name'])}.")


# ---------------------------------------------------------------------------
# named rival cultivators: two per sect, advancing by a rule you can read
# ---------------------------------------------------------------------------
def _ensure_champs(c: dict) -> None:
    for s in c["sects"]:
        if not isinstance(s.get("champs"), list) or not s["champs"]:
            r = C._rng(c, "champs", s["id"])
            s["champs"] = [{"name": s["young"], "step": 3, "role": "young master"},
                           {"name": f"{r.choice(C.SURNAMES)} {r.choice(C.GIVEN)}", "step": 6, "role": "first disciple"}]
            s["champ_tick"] = 0.0


def champ_days(s: dict) -> int:
    """Days between a rival cultivator's stages. Stronger sects raise their people faster."""
    return max(4, round(10 / max(0.4, float(s["power"]))))


def champ_power(ch: dict) -> float:
    step = int(ch["step"])
    return (10 + 4 * min(20.0, 5 + 0.6 * step)) * (1 + 0.07 * step)


def champion(c: dict, s: dict) -> dict:
    _ensure_champs(c)
    return max(s["champs"], key=lambda ch: ch["step"])


def tournament_foe(c: dict, s: dict, r: random.Random) -> float:
    return champ_power(champion(c, s)) * r.uniform(0.85, 1.15)


# ---------------------------------------------------------------------------
# each great realm asks for one thing, and there are always two ways to have it
# ---------------------------------------------------------------------------
def realm_gate(c: dict, p: dict) -> tuple[bool, str]:
    target = int(p["step"]) // 4 + 1
    b, mid = C._manual(c, p, "qi")
    grade = lore.MANUALS[mid]["grade"] if mid else -1
    vigil = any(D._is_home(c, o) for o in C._friends(c, p)) or D._is_home(c, D._mentor(c, p)) or D._is_home(c, D._companion(c, p))
    if target == 2:
        return (c["res"]["pills"] >= 1 or C._lvl(c, "meditation") >= 1), "Foundation Establishment needs a pill in the stores, or a Meditation Chamber."
    if target == 3:
        return (grade >= 1 or vigil), "Core Formation needs a Mystic-grade (or better) cultivation method, or someone to keep vigil: a friend, master or dao companion at home."
    if target == 4:
        return (bool(C.artifact_of(c, p)) or C._lvl(c, "ward") >= 3), "Nascent Soul needs an artifact to anchor the soul, or a Ward Formation of level 3."
    if target == 5:
        return (not p["demon"] and (bool(D._companion(c, p)) or p["stations"] >= 2 or c["fame"] >= 100)), \
            "Soul Transformation needs a heart free of demons, and a deep tie: a dao companion, a master's private teaching, or a sect of renown (fame 100)."
    if target == 6:
        return (grade >= 3 or "lightning_rod" in c["treasures"]), "Void Refinement needs a Heaven-grade cultivation method, or the Tribulation Lightning Pearl."
    if target == 7:
        return (any(k.startswith("work_") for k in c["flags"]) or c["fame"] >= 200), "Immortal Ascension needs a Great Work completed, or fame of 200."
    return True, ""


# ---------------------------------------------------------------------------
# expeditions you staff and steer
# ---------------------------------------------------------------------------
STANCES = {"careful": {"name": "Careful", "risk": 0.6, "loot": 0.8, "text": "Less danger, less brought home."},
           "balanced": {"name": "Balanced", "risk": 1.0, "loot": 1.0, "text": "As the road allows."},
           "bold": {"name": "Bold", "risk": 1.4, "loot": 1.3, "text": "More brought home, more blood."}}


def expedition(st: dict, place: str, ids: list[str], stance: str, now: float) -> dict:
    c = C._c(st, now)
    if place not in C.PLACES:
        return {"ok": False, "error": "Unknown destination."}
    if any(x["kind"] == "trip_return" for x in c["later"]):
        return {"ok": False, "error": "A party is already out."}
    stance = stance if stance in STANCES else "balanced"
    if ids:
        team = [p for p in (C._p(c, i) for i in dict.fromkeys(ids)) if p]
        if not 1 <= len(team) <= 3 or len(team) != len(set(ids)):
            return {"ok": False, "error": "Choose one to three disciples."}
        for p in team:
            if p.get("master") or not D._is_home(c, p) or p["health"] < 40:
                return {"ok": False, "error": f"{p['name']} cannot go: the Sect Master stays, and travellers must be home and in fair health."}
    else:
        team = C._strongest(c, 2)
        if len(team) < 2:
            return {"ok": False, "error": "You need two healthy disciples besides yourself."}
    pl = C.PLACES[place]
    back = c["hour"] + pl["hours"]
    for p in team:
        p["away_until"], p["away_kind"] = back, f"travelling to the {pl['name']}"
    tids = [p["id"] for p in team]
    c["later"].append({"at": back, "kind": "trip_return", "place": place, "pawns": tids, "stance": stance,
                       "loot_x": STANCES[stance]["loot"] * (0.75 + 0.25 * len(team) / 2), "risk_x": STANCES[stance]["risk"]})
    c["later"].append({"at": c["hour"] + pl["hours"] // 2, "kind": "trip_mid", "place": place, "pawns": tids})
    c["trip_plan"] = {"place": place, "pawns": tids, "stance": stance}
    return {"ok": True, "event": C._letter(c, "info", f"A party left for the {pl['name']}",
                                           f"{' and '.join(p['name'] for p in team)}, travelling {STANCES[stance]['name'].lower()}. "
                                           f"They will be gone {pl['hours']} hours and cannot work or defend the sect until then.")}


def _best(team: list[dict], skill: str) -> dict:
    return max(team, key=lambda p: p["skills"][skill]["lv"])


def _trip_mid(c: dict, item: dict) -> bool:
    if c["pending"]:
        return False
    team = [p for p in (C._p(c, i) for i in item.get("pawns", [])) if p]
    if not team or not any(x["kind"] == "trip_return" for x in c["later"]):
        return True
    place = item.get("place")
    who = ", ".join(p["name"] for p in team)
    if place == "valley":
        g = _best(team, "gather")
        C._ask(c, "trip_choice", "Word from Herb Valley", f"{who} found another sect's gatherers already working the best slopes. A runner asks what you want done.",
               [("share", "Share the slopes and part as friends"), ("drive", "Drive them off and take everything"),
                ("night", f"Slip past and pick by night ({g['name']} leads: gathering {g['skills']['gather']['lv']}, needs 8)")], place=place)
    elif place == "forest":
        h = _best(team, "craft")
        C._ask(c, "trip_choice", "Word from the Beast Forest", f"{who} tracked the spirit stones to a den. A wounded beast mother lies across the entrance, cubs behind her.",
               [("kill", "Kill her and take the den"), ("heal", f"Tend her wounds ({h['name']}: alchemy {h['skills']['craft']['lv']}, needs 6)"), ("leave", "Leave the den alone")], place=place)
    else:
        sc = _best(team, "scholar")
        C._ask(c, "trip_choice", "Word from the Ruined Sect", f"{who} cleared the outer halls. The inner door is sealed with script nobody has written for a thousand years.",
               [("force", "Force the door"), ("read", f"Read the seal ({sc['name']}: scholarship {sc['skills']['scholar']['lv']}, needs 8)"), ("offer", "Leave an offering and take only what lies outside")],
               place=place)
    return True


def _res_trip_choice(c, ev, opt, r):
    item = next((x for x in c["later"] if x["kind"] == "trip_return"), None)
    if not item:
        return None
    team = [p for p in (C._p(c, i) for i in item.get("pawns", [])) if p]

    def tune(loot=1.0, risk=1.0, bonus=""):
        item["loot_x"] = float(item.get("loot_x", 1.0)) * loot
        item["risk_x"] = float(item.get("risk_x", 1.0)) * risk
        if bonus:
            item["bonus"] = bonus
    text = ""
    if opt == "share":
        tune(0.9)
        c["karma"] = min(100.0, c["karma"] + 1)
        C._rel(r.choice(c["sects"]) if c["sects"] else None, 3)
        text = "They shared rice at one fire. Word of it will travel."
    elif opt == "drive":
        tune(1.3, 1.3)
        C._rel(C._rival(c), -5)
        text = "Blades came out. The slopes are yours, for now."
    elif opt == "night":
        ok = team and _best(team, "gather")["skills"]["gather"]["lv"] >= 8
        tune(1.15 if ok else 1.0, 1.0 if ok else 1.2)
        text = "Nobody saw them come or go." if ok else "A dog barked. They had to run for it."
    elif opt == "kill":
        tune(1.25, 1.4)
        c["karma"] = max(-100.0, c["karma"] - 2)
        text = "It was done quickly. The cubs watched."
    elif opt == "heal":
        ok = team and _best(team, "craft")["skills"]["craft"]["lv"] >= 6
        c["karma"] = min(100.0, c["karma"] + 2)
        tune(1.0, 1.0 if ok else 1.3, "beast" if ok else "")
        text = "She let them near. By morning she could stand." if ok else "She did not understand, and struck."
    elif opt == "force":
        tune(1.2, 1.5, "treasure")
        text = "The door gave. So did something behind it."
    elif opt == "read":
        ok = team and _best(team, "scholar")["skills"]["scholar"]["lv"] >= 8
        tune(1.0, 1.0, "manual" if ok else "")
        text = "The seal was a riddle, and the answer was a courtesy. The door opened by itself." if ok else "The script would not give up its meaning. They took what lay outside."
    elif opt == "offer":
        tune(0.8, 0.6)
        c["karma"] = min(100.0, c["karma"] + 2)
        text = "Incense for the dead of a sect nobody remembers."
    return C._letter(c, "info", "The party's answer", text + " They are on their way home.")


def trip_bonus(c: dict, item: dict, r: random.Random, found: list[str], team: list[dict]) -> None:
    b = item.get("bonus")
    if b == "manual":
        mid = C._loot_manual(c, r, min(3, C._max_grade(c) + 1))
        if mid:
            found.append(f"from behind the sealed door, the {C._manual_name(mid)}")
    elif b == "treasure" and r.random() < 0.6:
        tid = C._loot_treasure(c, r)
        if tid:
            found.append(f"from the inner hall, the {lore.TREASURES[tid]['name']}")
    elif b == "beast":
        free = [p for p in team if not p.get("beast")]
        if free:
            p = _best(free, "craft")
            p["beast"] = {"name": r.choice(lore.BEASTS), "born": c["hour"]}
            found.append(f"a cub the beast mother pushed toward {p['name']}, who it now follows everywhere")


# ---------------------------------------------------------------------------
# standing orders: say it once
# ---------------------------------------------------------------------------
def set_standing(st: dict, pills: int, repeat: bool, now: float) -> dict:
    c = C._c(st, now)
    c["standing"] = {"pills": max(0, min(20, int(pills))), "repeat": bool(repeat)}
    return {"ok": True}


def preset_save(st: dict, name: str, now: float) -> dict:
    c = C._c(st, now)
    if name not in ("peace", "war"):
        return {"ok": False, "error": "Presets are 'peace' and 'war'."}
    c["presets"][name] = {p["id"]: dict(p["prio"]) for p in c["pawns"]}
    return {"ok": True, "event": C._letter(c, "info", f"Work priorities saved as “{name}”", "Recall them from the Work tab at any time.")}


def preset_apply(st: dict, name: str, now: float) -> dict:
    c = C._c(st, now)
    saved = c["presets"].get(name)
    if not saved:
        return {"ok": False, "error": "Nothing is saved under that name yet."}
    for p in c["pawns"]:
        if p["id"] in saved:
            p["prio"] = {j: int(saved[p["id"]].get(j, 0)) for j in C.JOBS}
    return {"ok": True, "event": C._letter(c, "info", f"Work priorities set to “{name}”", "Disciples who joined since it was saved keep their own.")}


def forced_job(c: dict, p: dict, taken: dict) -> str:
    """A standing order can put the best alchemist on pills until the stock is back."""
    want = int(c["standing"].get("pills", 0))
    if want and c["res"]["pills"] < want and not taken.get("craft") and C._job_open(c, "craft", taken) and not p.get("direct"):
        home = [o for o in C._home(c) if not o.get("direct")]
        if home and p is max(home, key=lambda o: o["skills"]["craft"]["lv"]):
            if not c["marks"].get("brewing"):
                c["marks"]["brewing"] = 1
                C._letter(c, "info", "Standing order: brewing", f"The stock fell below {want} pills. {p['name']} is at the furnace until it is back.")
            return "craft"
    return ""


# ---------------------------------------------------------------------------
# time
# ---------------------------------------------------------------------------
def daily(c: dict, quiet: bool) -> None:
    _ensure_champs(c)
    for s in c["sects"]:
        s["champ_tick"] = float(s.get("champ_tick", 0.0)) + 1.0 / champ_days(s)
        while s["champ_tick"] >= 1.0:
            s["champ_tick"] -= 1.0
            for ch in s["champs"]:
                ch["step"] = min(C.MAX_STEP - 4, int(ch["step"]) + 1)
    for p in c["pawns"]:
        m = D._mentor(c, p)
        if m and D._is_home(c, m) and D._is_home(c, p):
            _trust(c, p, 1.2)
    if c["res"]["pills"] >= int(c["standing"].get("pills", 0)):
        c["marks"]["brewing"] = 0
    if quiet:
        return
    plan = c["trip_plan"]
    if c["standing"].get("repeat") and plan and not any(x["kind"] == "trip_return" for x in c["later"]) and not c["pending"]:
        team = [C._p(c, i) for i in plan["pawns"]]
        if all(p and D._is_home(c, p) and p["health"] >= 60 for p in team):
            st = {"colony": c, "settings": {"tz_offset_min": 0}}
            if expedition(st, plan["place"], plan["pawns"], plan["stance"], 0.0)["ok"]:
                c["log"][-1]["title"] = "Standing order: " + c["log"][-1]["title"][0].lower() + c["log"][-1]["title"][1:]


def on_guard(c: dict, p: dict) -> None:
    """A breakthrough the master watched over deepens the tie."""
    _trust(c, p, 8)


# ---------------------------------------------------------------------------
# view and repair
# ---------------------------------------------------------------------------
def pawn_view(c: dict, p: dict) -> dict:
    ok, text = realm_gate(c, p) if C.ready(p) else (True, "")
    return {
        "trust": C._f(p["trust"]), "stations": C._f(p["stations"]),
        "station_marks": [{"at": at, "text": text_, "done": p["stations"] > i} for i, (at, text_) in enumerate(STATIONS)],
        "points": points(p),
        "meridians": [{"id": k, "name": n["name"], "text": n["text"], "cost": n["cost"], "open": k in p["meridians"],
                       "blocked": "" if k in p["meridians"] else _node_blocked(c, p, k)} for k, n in NODES.items()],
        "gate": {"ok": bool(ok), "text": str(text)} if text else None,
    }


def view(c: dict) -> dict:
    _ensure_champs(c)
    return {
        "champs": {str(s["id"]): {"every": champ_days(s), "list": [{"name": str(ch["name"]), "role": str(ch.get("role", "")), "realm": C.realm_label(int(ch["step"])),
                                                                     "power": C._f(champ_power(ch))} for ch in s["champs"]]} for s in c["sects"]},
        "stances": [{"id": k, "name": v["name"], "text": v["text"]} for k, v in STANCES.items()],
        "standing": {"pills": C._f(c["standing"].get("pills", 0)), "repeat": bool(c["standing"].get("repeat"))},
        "presets": sorted(c["presets"]),
        "trip_plan": ({"place": C.PLACES[c["trip_plan"]["place"]]["name"], "stance": STANCES[c["trip_plan"]["stance"]]["name"],
                       "who": [str(p["name"]) for p in (C._p(c, i) for i in c["trip_plan"]["pawns"]) if p]} if c["trip_plan"] else None),
    }


def repair(c: dict, num) -> None:
    s_ = c["standing"] if isinstance(c.get("standing"), dict) else {}
    c["standing"] = {"pills": int(num(s_.get("pills"), 0, 20)), "repeat": bool(s_.get("repeat"))}
    ids = {p["id"] for p in c["pawns"]}
    pr = c["presets"] if isinstance(c.get("presets"), dict) else {}
    c["presets"] = {k: {pid: {j: int(num((v or {}).get(j), 0, 4)) for j in C.JOBS} for pid, v in pr[k].items() if pid in ids and isinstance(v, dict)}
                    for k in ("peace", "war") if isinstance(pr.get(k), dict)}
    tp = c.get("trip_plan")
    c["trip_plan"] = ({"place": tp["place"], "pawns": [i for i in tp.get("pawns", []) if i in ids][:3], "stance": tp.get("stance") if tp.get("stance") in STANCES else "balanced"}
                      if isinstance(tp, dict) and tp.get("place") in C.PLACES and isinstance(tp.get("pawns"), list) else None)
    if c["trip_plan"] and not c["trip_plan"]["pawns"]:
        c["trip_plan"] = None
    for p in c["pawns"]:
        p["trust"] = num(p.get("trust"), 0, 100)
        p["stations"] = int(num(p.get("stations"), 0, 3))
        p["meridians"] = [n for n in dict.fromkeys(p.get("meridians", [])) if n in NODES] if isinstance(p.get("meridians"), list) else []
    for s in c["sects"]:
        ch = s.get("champs")
        s["champs"] = [{"name": str(x.get("name") or "A rival"), "step": int(num(x.get("step"), 0, C.MAX_STEP)), "role": str(x.get("role") or "")}
                       for x in ch if isinstance(x, dict)][:4] if isinstance(ch, list) else []
        s["champ_tick"] = num(s.get("champ_tick"), 0, 5)
    for x in c["later"]:
        if x.get("kind") == "trip_return":
            x["loot_x"], x["risk_x"] = num(x.get("loot_x"), 0.3, 3.0, 1.0), num(x.get("risk_x"), 0.3, 3.0, 1.0)


RESOLVERS = {"trip_choice": _res_trip_choice}
LATER = {"trip_mid"}


def later(c: dict, item: dict, r: random.Random) -> bool:
    return _trip_mid(c, item)
