"""Sect simulation: persistent, evolving RPG state for each sect member.

The dashboard's character dossier (spirit root, attributes, skills, traits, …)
used to be synthesised fresh on the client each load. This module makes it
*real*: a base character is generated once per member (deterministic from the
name), persisted to disk, and then evolves with the member's actual activity —
tasks completed, breakthroughs, accrued merit. Same member => same soul, growing
over time.

State is a small JSON file (MAYBOT_SECT_FILE, default sect_state.json).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

SECT_FILE = Path(os.getenv("MAYBOT_SECT_FILE", "sect_state.json"))
_lock = threading.Lock()
_state: dict | None = None

REALMS = ["Mortal", "Qi Gathering", "Foundation Establishment", "Core Formation",
          "Nascent Soul", "Soul Transformation", "Ascendant", "Immortal Ascension"]
STAGES = ["Early Stage", "Middle Stage", "Late Stage", "Peak Stage"]
GRADES = ["F", "E", "D", "C", "B", "A", "S", "SS", "SSS", "Heavenly", "Immortal"]
ATTRS = ["Strength", "Agility", "Endurance", "Intelligence", "Perception", "Willpower", "Charisma", "Luck"]
SKILL_POOL = ["Research", "Alchemy", "Trading", "Diplomacy", "Leadership", "Swordsmanship",
              "Formation Mastery", "Crafting", "Scouting", "Teaching", "Administration", "Beast Taming", "Talismancy"]
SPECIALTIES = ["Pill Genius", "Formation Savant", "Born Merchant", "Sword Prodigy", "Beast Tamer",
               "Spirit Farmer", "Talisman Expert", "Political Genius", "Master Negotiator"]
TRAITS_POS = ["Hardworking", "Loyal", "Disciplined", "Curious", "Brave", "Patient", "Wise", "Charismatic", "Perfectionist"]
TRAITS_NEG = ["Lazy", "Arrogant", "Cowardly", "Greedy", "Impulsive", "Jealous", "Vindictive", "Wasteful", "Reckless"]
TRAITS_NEU = ["Quiet", "Bookworm", "Dreamer", "Competitive", "Eccentric", "Collector"]
GOALS = ["Become Elder", "Master the Sword Dao", "Found a Personal Peak", "Reach Nascent Soul",
         "Create Legendary Pills", "Become Sect Leader", "Comprehend a Heavenly Dao", "Forge an Immortal Artifact"]
WEAPONS = [("Wooden Practice Sword", 0), ("Iron Saber", 1), ("Azure Cloud Sword", 3), ("Frostmoon Glaive", 2), ("Nine-Ring Blade", 2), ("Voidsplitter Spear", 4)]
ARMORS = [("Cotton Robe", 0), ("Spirit Silk Robe", 2), ("Jade Scale Armor", 3), ("Cloudweave Vestment", 1), ("Dragonhide Mantle", 4)]
ARTIFACTS = [("Minor Storage Ring", 1), ("Spirit Gathering Pearl", 2), ("Soul Lantern", 3), ("Heaven-Peering Mirror", 4), ("—", 0)]
ACCESSORIES = [("Jade Pendant", 1), ("Beast-Bone Talisman", 2), ("Meridian Bracelet", 2), ("Luck Coin", 3), ("—", 0)]
RARITY = ["common", "uncommon", "rare", "epic", "legendary"]
ELEM = ["Fire", "Water", "Wood", "Metal", "Earth"]
SPECIAL_ROOTS = ["Lightning", "Wind", "Ice", "Shadow", "Light", "Blood", "Beast", "Soul", "Dream", "Star", "Time", "Space", "Yin", "Yang"]
MYTHIC_ROOTS = ["Heavenly", "Immortal", "Chaos", "Primordial", "Dragon", "Phoenix", "Void", "Dao"]
ROOT_QUALITY = ["Trash", "Common", "Good", "Superior", "Earth Grade", "Heaven Grade", "Saint Grade", "Immortal Grade", "Dao Grade"]
CONSTITUTIONS = ["Pure Yang Body", "Pure Yin Body", "Heavenly Sword Body", "Nine Phoenix Body", "Dragon Blood Body", "Void Body", "Saint Body", "Starborn Physique", "Chaos Physique"]
MUTATIONS = {("Fire", "Wind"): "Lightning", ("Water", "Wind"): "Ice", ("Shadow", "Water"): "Moon", ("Fire", "Light"): "Solar", ("Earth", "Wood"): "Life"}


def _hash(s: str) -> int:
    h = 2166136261
    for ch in str(s):
        h ^= ord(ch); h = (h * 16777619) & 0xFFFFFFFF
    return h


class _Rng:
    def __init__(self, seed: int):
        self.a = seed & 0xFFFFFFFF
    def __call__(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = (t ^ (t >> 15)) * (1 | t) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296


def _pick(r, arr): return arr[int(r() * len(arr))]
def _rint(r, a, b): return a + int(r() * (b - a + 1))
def _sample(r, arr, n):
    c = list(arr); out = []
    while c and len(out) < n:
        out.append(c.pop(int(r() * len(c))))
    return out


def _spirit_root(seed: int, comprehension: int, luck: int, willpower: int) -> dict:
    r = _Rng((seed ^ 0x5C0FFEE) & 0xFFFFFFFF)
    mythic = perfect_five = False
    mutated = None
    roll = r()
    if roll < 0.04:
        roots = [_pick(r, MYTHIC_ROOTS)]; mythic = True; count = 1
    elif roll < 0.10:
        roots = list(ELEM); perfect_five = True; count = 5
    else:
        cr = r()
        count = 1 if cr < 0.12 else 2 if cr < 0.45 else 3 if cr < 0.75 else 4 if cr < 0.92 else 5
        roots = _sample(r, ELEM if r() < 0.65 else ELEM + SPECIAL_ROOTS, count)
    if count == 2:
        key = tuple(sorted(roots))
        if key in MUTATIONS and r() < 0.6:
            mutated = MUTATIONS[key]; roots = [mutated]; count = 1
    hidden = (not mythic) and r() < 0.06
    if perfect_five:
        purity = _rint(r, 80, 99)
    elif mythic or mutated:
        purity = _rint(r, 60, 99)
    else:
        purity = max(3, round(_rint(r, 10, 95) * [1, 1, 0.9, 0.75, 0.6, 0.5][min(5, count)]))
    purity = max(1, min(100, purity))
    q = int(purity / 100 * (len(ROOT_QUALITY) - 2)) + (2 if mythic else 0) + (1 if (perfect_five or mutated) else 0)
    q = max(0, min(len(ROOT_QUALITY) - 1, q))
    constitution = _pick(r, CONSTITUTIONS) if r() < 0.22 else None
    root_score = 95 if mythic else 90 if perfect_five else 80 if mutated else [70, 70, 55, 40, 28, 18][min(5, count)]
    pot = max(0, min(110, root_score * 0.45 + purity * 0.3 + comprehension * 0.15 + luck * 0.1 + (12 if constitution else 0)))
    potential = GRADES[min(len(GRADES) - 1, round(pot / 100 * (len(GRADES) - 1)))]
    # trope
    if mythic and constitution:
        trope = "Heaven's Chosen"
    elif constitution == "Heavenly Sword Body" and "Metal" in roots and any("Lightning" in x for x in roots):
        trope = "Sword Saint Candidate"
    elif purity >= 85 and comprehension >= 80 and constitution:
        trope = "Heavenly Genius"
    elif "Wood" in roots and "Fire" in roots:
        trope = "Alchemy Prodigy"
    elif hidden:
        trope = "Hidden Dragon"
    elif ROOT_QUALITY[q] in ("Trash", "Common") and willpower >= 80:
        trope = "Trash Root Protagonist"
    elif (count >= 4 or purity < 35) and willpower >= 70:
        trope = "Late Bloomer"
    elif purity >= 80 and comprehension >= 70:
        trope = "Heavenly Genius"
    else:
        trope = "Ordinary Disciple"
    bonuses = []
    spd = round((purity - 50) / 2 + (30 if mythic else 0) + (20 if perfect_five else 0) + (15 if mutated else 0))
    if spd:
        bonuses.append(f"{'+' if spd > 0 else ''}{spd}% Cultivation Speed")
    if constitution == "Heavenly Sword Body":
        bonuses.append("+25% Sword Comprehension")
    if "Wood" in roots and "Fire" in roots:
        bonuses.append("+20% Alchemy")
    if any("Lightning" in x for x in roots):
        bonuses.append("+15% Breakthrough Chance")
    if not bonuses:
        bonuses = ["No notable bonuses yet"]
    if potential in ("SS", "SSS", "Heavenly", "Immortal"):
        reaction = "The sect watches with admiration — and quiet jealousy. Elders compete to mentor them."
    elif potential in ("S", "A"):
        reaction = "Seniors take note; mentorship offers may come."
    elif potential in ("F", "E", "D"):
        reaction = "Largely overlooked by the elders — underestimated for now."
    else:
        reaction = "Regarded as a steady, unremarkable member."
    return {"roots": roots, "count": count, "mythic": mythic, "perfectFive": perfect_five, "mutated": mutated,
            "purity": purity, "quality": ROOT_QUALITY[q], "qIdx": q, "constitution": constitution,
            "potential": potential, "trope": trope, "hidden": hidden,
            "display": "Unknown Root" if hidden else " + ".join(x + " Root" for x in roots),
            "bonuses": bonuses[:4], "reaction": reaction}


def _generate(name: str, role: str = "") -> dict:
    """The immutable 'soul' of a member — born once, then persisted."""
    seed = _hash(name)
    r = _Rng(seed)
    comprehension = _rint(r, 25, 99)
    qi = _rint(r, 20, 99)
    attrs = {a: _rint(r, 18, 96) for a in ATTRS}
    root = _spirit_root(seed, comprehension, attrs["Luck"], attrs["Willpower"])
    base_skills = list(dict.fromkeys(_sample(r, SKILL_POOL, _rint(r, 3, 6))))
    skills = {s: {"lv": _rint(r, 1, 18), "xp": _rint(r, 5, 95)} for s in base_skills}
    traits = ([["pos", t] for t in _sample(r, TRAITS_POS, _rint(r, 1, 3))]
              + [["neg", t] for t in _sample(r, TRAITS_NEG, _rint(r, 0, 2))]
              + [["neu", t] for t in _sample(r, TRAITS_NEU, _rint(r, 0, 2))])
    specs = _sample(r, SPECIALTIES, _rint(r, 0, 2))
    wpn = _pick(r, WEAPONS); arm = _pick(r, ARMORS); art = _pick(r, ARTIFACTS); acc = _pick(r, ACCESSORIES)
    return {
        "seed": seed, "gender": _pick(r, ["Male", "Female"]),
        "born_age": _rint(r, 16, 22), "comprehension": comprehension, "qi": qi,
        "attrs": attrs, "root": root, "skills": skills, "traits": traits, "specs": specs,
        "goal": _pick(r, GOALS),
        "equip": [["Weapon", wpn[0], RARITY[wpn[1]]], ["Armor", arm[0], RARITY[arm[1]]],
                  ["Artifact", art[0], RARITY[art[1]]], ["Accessory", acc[0], RARITY[acc[1]]]],
        "events": [], "last_breakthroughs": 0, "created": time.time(),
    }


def _load() -> dict:
    global _state
    if _state is not None:
        return _state
    if SECT_FILE.exists():
        try:
            _state = json.loads(SECT_FILE.read_text(encoding="utf-8"))
        except Exception:
            _state = {}
    else:
        _state = {}
    return _state


def _save() -> None:
    try:
        tmp = SECT_FILE.with_name(SECT_FILE.name + ".tmp")
        tmp.write_text(json.dumps(_state or {}), encoding="utf-8")
        tmp.replace(SECT_FILE)
    except Exception:
        pass


def profile(agent: dict) -> dict:
    """Full evolving dossier for one member: persisted soul + live activity."""
    name = agent.get("name", "?")
    with _lock:
        st = _load()
        base = st.get(name)
        if base is None:
            base = st[name] = _generate(name, agent.get("role", ""))
            _save()
        cult = agent.get("cultivation", {}) or {}
        rep = agent.get("reputation", {}) or {}
        sig = rep.get("signals", {}) or {}
        tasks = int(agent.get("tasks_done") or 0)
        bts = int(cult.get("breakthroughs") or base.get("last_breakthroughs", 0))
        # growth event log: record each new breakthrough as it happens
        if bts > base.get("last_breakthroughs", 0):
            realm_name = cult.get("realm_name") or (REALMS[min(len(REALMS) - 1, cult.get("realm", 0))])
            base.setdefault("events", []).append({"y": f"+{bts}", "t": f"Broke through to {realm_name}."})
            base["last_breakthroughs"] = bts
            _save()
        # live overlay: attributes and skills grow with real work (deterministic)
        attr_bonus = min(8, tasks // 5) + min(6, bts * 2)
        attrs = [{"name": k, "val": min(100, v + attr_bonus)} for k, v in base["attrs"].items()]
        skills = []
        for nm, s in base["skills"].items():
            lv = min(60, s["lv"] + tasks // 8 + bts)
            skills.append({"name": nm, "lv": lv, "xp": (s["xp"] + tasks * 7) % 100})
        skills.sort(key=lambda x: -x["lv"])
        realm_idx = cult.get("realm", 0) or 0
        realm = cult.get("realm_name") or REALMS[min(len(REALMS) - 1, realm_idx)]
        prog = (min(99, round(cult["stones"] / (cult["stones"] + cult["stones_to_next"]) * 100))
                if cult.get("stones") and cult.get("stones_to_next") else _rint(_Rng(base["seed"] + 3), 8, 96))
        break_chance = max(5, min(98, round(prog * 0.4 + base["comprehension"] * 0.4 + base["qi"] * 0.2)))
        age = base["born_age"] + realm_idx * 7 + tasks // 12
        gradeidx = min(len(GRADES) - 1, max(0, round((base["comprehension"] + base["qi"]) / 2 / 100 * 8)))
        return {
            "name": name, "model": agent.get("model"), "role": agent.get("role") or "Disciple",
            "gender": base["gender"], "age": age, "status": agent.get("status", "idle"),
            "realm": realm, "stage": cult.get("stage") or STAGES[min(3, realm_idx % 4)],
            "prog": prog, "breakChance": break_chance, "comprehension": base["comprehension"], "qi": base["qi"],
            "grade": GRADES[gradeidx], "attrs": attrs, "skills": skills[:8], "specs": [s for s in [*( [agent.get('governance', {}).get('specialty')] if agent.get('governance', {}).get('specialty') else []), *base["specs"]] if s],
            "traits": base["traits"], "goal": base["goal"], "root": base["root"], "equip": base["equip"],
            "rank": cult.get("rank_title") or "Disciple",
            "assignment": (agent.get("current_task") if agent.get("status") == "working" and agent.get("current_task") else None),
            "sect": {
                "years": max(1, age // 4 - 2),
                "contribution": int((rep.get("merit") or 0) * 13 + tasks * 25 + base["seed"] % 400),
                "missions": tasks, "breakthroughs": bts, "techniques": len(base["skills"]),
            },
            "success": (sig.get("success_pct") if isinstance(sig.get("success_pct"), (int, float)) else None),
            "events": list(reversed(base.get("events", []))),
        }


def profiles(agents: list[dict]) -> dict:
    return {a.get("name"): profile(a) for a in agents if a.get("name")}


def reset() -> None:
    global _state
    with _lock:
        _state = {}
        _save()
