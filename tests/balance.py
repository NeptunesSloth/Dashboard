"""A scripted player for tuning the sect by simulation (CLAUDE.md: "Difficulty is tuned by
simulation, not by feel").

``play(storyteller, profile, days, seed)`` founds a sect, plays it hour by hour and returns the
numbers the balance is judged by. Two profiles:

* ``idle``: never builds, researches or reassigns anyone; clicks the first button on every event.
* ``collect``: careful, and taps every tray twice a sect day (SECT_OVERHAUL_PLAN 3.6: tapping must be optional).
* ``careful``: builds and researches in a sensible order, keeps a food reserve, fights only when
  the odds are good, heals the wounded, takes breakthroughs at good odds, and acts on the
  sect's alerts (a disciple who has stopped cultivating gets meditation time).

Run ``python tests/balance.py`` for the full table (150 days, every storyteller x profile).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sect_academy import colony, state  # noqa: E402

T0 = 1_800_000_000.0
# The order a careful player raises rooms in: the n-th mention of a room is its n-th level. An entry the Main Hall
# ladder does not allow yet (not open, over the cap, or the Hall's three-rooms rule unmet) is passed over for now.
BUILD_ORDER = (["fields", "storehouse", "main_hall", "training", "library", "dormitory", "ward", "fields", "storehouse", "main_hall",
                "alchemy", "meditation", "dormitory", "training", "library", "main_hall", "spirit_vein", "ward", "fields", "storehouse",
                "meditation", "dormitory", "alchemy", "main_hall", "library", "training", "ward", "market"]
               + ["main_hall", "fields", "storehouse", "dormitory", "meditation", "library", "training", "ward", "spirit_vein", "alchemy"] * 5)
GATHER_RICE_DAYS = 8                     # a careful player sends someone for wood or stone with this many days of rice in hand
RESEARCH_ORDER = ["irrigation", "masonry", "granary", "sword_forms", "qi_array", "refinement", "ward_ii", "dao_heart"]


def _legal(c: dict, room: str) -> bool:
    have = colony._lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
    return have < colony.ROOMS[room]["max"] and not colony.build_block(c, room, have)


def _afford(c: dict, room: str) -> bool:
    have = colony._lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
    return all(c["res"][k] >= v for k, v in colony.room_cost(c, room, have).items())


def _careful_choice(c: dict, ev: dict) -> str:
    ids = [o["id"] for o in ev["options"]]
    kind = ev["kind"]
    n = len(c["pawns"])
    rice = c["res"]["rice"]
    if kind == "omen":
        ratio = colony.defense(c) / max(float(ev.get("strength", 1)), 1.0)
        if ratio >= colony.THEFT_SAFE or (ratio >= 1.1 and "guard" not in ids):
            return "fight"
        if "guard" in ids and ratio >= 0.9:
            return "guard"
        if "wards" in ids and ratio < 0.9:
            return "wards"
        if "tribute" in ids and ratio < 0.7:
            return "tribute"
        return "guard" if "guard" in ids else "fight"
    if kind == "festival":
        if rice >= ev["cost"] + n * 1.2 * 8:
            return "hold"
        return ids[1] if ids[1] in ("moon", "vigil") or (ids[1] == "offer" and c["res"]["wood"] >= 20) else "skip"
    if kind == "plague":
        return next(o for o in ("pills", "herbs", "quarantine") if o in ids)
    if kind == "blight":
        if "burn" in ids and rice >= ev.get("seed", 6) + n * 1.2 * 6:
            return "burn"
        return "ash" if "ash" in ids else "endure"
    if kind == "infiltrator":
        best = max((int(m.group(1)), o["id"]) for o in ev["options"] if (m := re.search(r"(\d+)% to", o["label"])))
        return best[1] if best[0] >= 35 else "wait"
    if kind == "thief":
        best = max((int(m.group(1)), o["id"]) for o in ev["options"] if (m := re.search(r"(\d+)% to", o["label"])))
        return best[1] if best[0] >= 30 else "let_go"
    if kind == "feud":
        return "mediate" if "mediate" in ids else "spar"
    if kind == "pact_duel":
        m = re.search(r"(\d+)% to win", ev["options"][0]["label"])
        return "fight" if m and int(m.group(1)) >= 35 else "forfeit"
    if kind == "tournament":
        m = re.search(r"(\d+)% to win round one", ev["options"][0]["label"])
        return ids[0] if m and int(m.group(1)) >= 40 else "observe" if "observe" in ids else ids[-1]
    if kind in ("wanderer", "recruit"):
        room = len(c["pawns"]) < colony.beds(c) + 1 and rice >= (n + 1) * 1.2 * 10
        if kind == "recruit":
            return "pick0" if room else "decline"
        return "accept" if room else "decline"
    if kind == "merchant":
        if "buy_rice" in ids and rice < n * 1.2 * 6:
            return "buy_rice"
        if "sell_rice" in ids and rice > colony._cap(c) * 0.8:
            return "sell_rice"
        return "decline"
    if kind == "quest_offer":
        return "accept"
    if kind == "quest_reward":
        return "fame" if "fame" in ids else ids[0]
    if kind == "village":
        return "send"
    if kind == "beast_cub":
        return "adopt" if "adopt" in ids and rice > 30 else ids[-1]
    if kind == "young_master":
        p = colony._p(c, ev.get("pawn", ""))
        return "slap" if p and colony.duel_power(c, p) >= 20 + colony._day(c) * 0.7 else "endure"
    if kind == "qingming":
        return "visit"
    if kind == "lord":
        return "send" if "send" in ids else "honest" if "honest" in ids else ids[-1]
    if kind == "demonic_offer":
        return "refuse"
    if kind == "fate":
        return ids[0]
    if kind == "taxes":
        return "pay" if rice > 40 and c["res"]["stones"] >= 5 else "refuse"
    return ids[-1]                  # the cautious option: decline, keep everyone home


def _careful_orders(st: dict, c: dict, seen_alerts: set) -> None:
    if c["hour"] % 6:
        return
    # research
    if colony._lvl(c, "library") and not c["research"]["current"]:
        nxt = next((t for t in RESEARCH_ORDER if t not in c["research"]["done"]), "")
        if nxt:
            colony.set_research(st, nxt, T0)
    # build: one job at a time, next in the plan, keeping some stock back
    short: set = set()
    eat = sum(v for res, label, v in colony.upkeep(c) if res == "rice" and "spoiling" not in label)
    farmers = sum(1 for p in c["pawns"] if p["work"] == "farm" and p["prio"].get("farm"))
    # the winter alert (or a thin granary in autumn): the harvest comes before new building and before the cushion
    winter_soon = any(a["text"].startswith("Winter is") for a in colony._alerts(c)) \
        or (colony._season(c) == 2 and c["res"]["rice"] < eat * colony.WINTER_HUNGER * colony.DAYS_PER_SEASON * 1.2)
    if colony._season(c) != 3 and c["res"]["rice"] < eat * 8 and farmers >= 2 * colony._lvl(c, "fields") \
            and not any(b["room"] == "fields" for b in c["builds"]):
        colony.queue_build(st, "fields", T0)            # the terraces are full and the granary is thin: more terraces
    slots = colony.builders(c) if hasattr(colony, "builders") else 2
    while len(c["builds"]) < slots and not winter_soon:      # every free builder takes the next thing in the plan
        built: dict = {}
        queued = False
        for room in BUILD_ORDER:
            built[room] = built.get(room, 0) + 1
            have = colony._lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
            if have >= built[room] or have >= colony.ROOMS[room]["max"]:
                continue
            if hasattr(colony, "build_block") and colony.build_block(c, room, have):
                continue            # the ladder does not allow it yet: the next thing in the plan
            queued = colony.queue_build(st, room, T0)["ok"]
            if not queued:
                short = {k for k, v in colony.room_cost(c, room, have).items() if c["res"][k] < v}
            break                   # wait for the materials for the next thing in the plan
        if not queued:
            break
    # farmers put the harvest ahead of the cushion until the snow, then sit again
    for p in c["pawns"]:
        if winter_soon and p["prio"].get("farm") == 2 and p["prio"].get("meditate") == 2 and not p.get("master"):
            colony.set_priority(st, p["id"], "meditate", 3, T0)
            p["_harvest"] = 1
        elif p.get("_harvest") and (colony._season(c) == 3 or not winter_soon) and c["res"]["rice"] > eat * 4:
            colony.set_priority(st, p["id"], "meditate", 2, T0)
            p.pop("_harvest")
    # the plan waits on wood or stone and the granary is comfortable: put one disciple on it, and back when it is not
    for job, res in (("wood", "wood"), ("mine", "stone")):
        others = [p for p in c["pawns"] if not p.get("master") and not p.get("direct")]
        on = [p for p in others if p["prio"].get(job) == 2]
        if res in short and c["res"]["rice"] > eat * GATHER_RICE_DAYS and not on and others:
            p = max(others, key=lambda x: (x["prio"].get("farm") != 2 or x["work"] != "farm", x["skills"]["gather"]["lv"]))
            colony.set_priority(st, p["id"], job, 2, T0)
        elif on and (res not in short or c["res"]["rice"] < eat * 5):
            for p in on:
                colony.set_priority(st, p["id"], job, 3, T0)
    # the wounded get pills
    for p in c["pawns"]:
        if p["health"] < 40 and c["res"]["pills"] >= 2:
            colony.use_pill(st, p["id"], T0)
    # breakthroughs at good odds
    for p in list(c["pawns"]):
        if colony.ready(p) and colony.bt_chance(c, p) >= 60:
            colony.attempt(st, p["id"], T0)
    # a careful player reads the alerts
    # (the alert names the Meditate priority that would put them back on the cushion half their working hours;
    # the sect shows two by name and counts the rest, and a careful player fixes those too)
    for p in c["pawns"]:
        if colony.stalled_days(c, p) >= colony.STALL_DAYS and not colony.ready(p):
            level = colony.stall_advice(c, p)[1]
            if level and p["prio"].get("meditate") != level:
                colony.set_priority(st, p["id"], "meditate", level, T0)


def play(storyteller: str = "balanced", profile: str = "careful", days: int = 150, seed: int = 12345) -> dict:
    st = state.reset_for_tests()
    colony._c(st, T0)["seed"] = seed
    colony.setup(st, "Azure Lantern", "Jay", T0)
    c = st["colony"]
    c["storyteller"] = storyteller
    seen_alerts: set = set()
    fights: list = []
    real_battle = colony._battle

    def battle(c_, r_, kind, strength, how="fight", src=None):
        ratio = colony.defense(c_) / max(strength, 1.0)
        ev = real_battle(c_, r_, kind, strength, how, src)
        fights.append((colony._day(c_) + 1, how, round(ratio, 2), ev["kind"]))
        return ev
    colony._battle = battle
    real_attempt = colony.attempt
    bts: list = []                         # (great realm aimed at, odds, success)

    def attempt(st_, pid, now):
        p = colony._p(st_["colony"], pid)
        odds, target = (colony.bt_chance(st_["colony"], p), p["step"] // 4 + 1) if p and colony.ready(p) else (0, 0)
        res = real_attempt(st_, pid, now)
        if res.get("ok"):
            bts.append((target, odds, bool(res.get("success"))))
        return res
    colony.attempt = attempt
    stolen_was = 0.0
    slot_hours = [0, 0, 0]                 # builder-slot hours to day 60; of those, empty; and empty for want of materials
    event_days: set = set()              # days with something to decide (a letter alone does not count)
    work_jobs = {v[0].lower() for v in colony.JOBS.values()}
    hours: dict = {}                       # pawn id -> [working hours, of which meditating, name]
    out = {"deaths": 0, "min_rice": 1e9, "min_food_days": 1e9, "lean_days": 0, "cap_days": 0, "rice_cap_days": 0, "short_days": 0,
           "mood": (100, 0), "rice_by_month": [], "raids": 0, "raid_losses": 0, "renown_day": None, "pop_max": 0, "qi60": {},
           "steps60": {}, "fame60": 0, "others_up60": 0, "qc80": 0, "others80": 0, "steps80": {}, "infil": 0, "thefts": 0, "hall_by_day": {}}
    try:
        for _ in range(days * 24):
            colony.advance(st, 1, T0)
            for p in c["pawns"]:
                if p["doing"] in work_jobs and not p.get("master"):
                    h = hours.setdefault(p["id"], [0, 0, p["name"]])
                    h[0] += 1
                    h[1] += p["doing"] == "meditate"
            for _ in range(4):
                ev = c["pending"]
                if not ev:
                    break
                event_days.add(colony._day(c))
                out["infil"] += ev["kind"] == "infiltrator"
                opt = ev["options"][0]["id"] if profile == "idle" else _careful_choice(c, ev)
                if not colony.resolve(st, opt, T0)["ok"]:
                    colony.resolve(st, ev["options"][-1]["id"], T0)
            if profile in ("careful", "collect"):
                _careful_orders(st, c, seen_alerts)
            if profile == "collect" and c["hour"] % 24 in (9, 17):     # taps every tray twice a sect day
                for room in list(colony.trays(c)):
                    colony.inspect_tray(st, room, T0)
            if hasattr(colony, "builders") and colony._day(c) < 60:
                free = max(0, colony.builders(c) - len(c["builds"]))
                slot_hours[0] += colony.builders(c)
                slot_hours[1] += free
                if free and hasattr(colony, "build_block"):
                    legal = [r for r in colony.ROOMS if _legal(c, r)]
                    if legal and not any(_afford(c, r) for r in legal):
                        slot_hours[2] += free          # empty for want of materials: something could be built, nothing affordable
            if c["hour"] % 24 == 0 and colony._day(c) in (30, 60, 90, 150):
                out["hall_by_day"][colony._day(c)] = colony._lvl(c, "main_hall")
            if c["tally"]["stolen"] > stolen_was + 0.5:          # a raid or a thief carried something off
                out["thefts"] += 1
            stolen_was = c["tally"]["stolen"]
            if c["hour"] % 24 == 12:
                day = colony._day(c)
                if day >= 6:
                    out["min_rice"] = min(out["min_rice"], c["res"]["rice"])
                    eat = (sum(v for res, label, v in colony.upkeep(c) if res == "rice" and "spoiling" not in label)
                           if hasattr(colony, "upkeep") else len(c["pawns"]) * 2.2 * 24 / 38)     # (older builds, for comparison)
                    out["min_food_days"] = min(out["min_food_days"], c["res"]["rice"] / max(eat, 0.5))
                    if c["res"]["rice"] < eat * 3:
                        out["lean_days"] += 1
                cap = colony._cap(c)
                if sum(c["res"][k] >= cap * 0.9 for k in ("rice", "wood", "stone")) >= 2:
                    out["cap_days"] += 1
                if c["res"]["rice"] >= cap * 0.9:
                    out["rice_cap_days"] += 1
                if any(t["k"] in ("repairs", "no_fire") for p in c["pawns"] for t in p["thoughts"]):
                    out["short_days"] += 1
                if (day + 1) % 30 == 0:
                    out["rice_by_month"].append(round(c["res"]["rice"]))
                out["pop_max"] = max(out["pop_max"], len(c["pawns"]))
                if day >= 10:
                    m = sum(p["mood"] for p in c["pawns"]) / max(1, len(c["pawns"]))
                    out["mood"] = (min(out["mood"][0], round(m)), max(out["mood"][1], round(m)))
                if out["renown_day"] is None and colony.renown(c["fame"]) != colony.renown(0):
                    out["renown_day"] = day + 1
                if day + 1 == 60:
                    others = [p for p in c["pawns"] if not p.get("master")]
                    out["qi60"] = {p["name"]: round(p["qi"] + sum(colony.step_need(s) for s in range(p["step"]))) for p in c["pawns"]}
                    out["steps60"] = {p["name"]: p["step"] for p in c["pawns"]}
                    out["others_up60"] = sum(1 for p in others if p["step"] >= 1)
                    out["fame60"] = round(c["fame"])
                out["rivals_max"] = max(out.get("rivals_max", 0), len(colony.rival_pairs(c)))
                if day + 1 == 70:
                    out["techs70"] = len(c["research"]["done"])
                if day + 1 == 80:
                    out["risk80"] = out["infil"] + out["thefts"]
                    others = [p for p in c["pawns"] if not p.get("master") and p.get("joined", 0) <= 24 * 25]   # in the sect since the first month
                    out["steps80"] = {p["name"]: p["step"] for p in c["pawns"]}
                    out["others80"] = len(others)
                    out["qc80"] = sum(1 for p in others if p["step"] >= 4)
    finally:
        colony._battle = real_battle
        colony.attempt = real_attempt
    out["bts"] = bts
    out["idle_builder"] = round(slot_hours[1] / slot_hours[0], 2) if slot_hours[0] else None
    out["idle_builder_hours"] = round(slot_hours[2] / slot_hours[0], 2) if slot_hours[0] else None
    out["hall_by_day"].setdefault(days, colony._lvl(c, "main_hall"))
    out.setdefault("risk80", out["infil"] + out["thefts"])
    out.setdefault("techs70", len(c["research"]["done"]))
    gaps, last = [], 4                        # counted from the first threat (day 5) on
    for d in sorted(x for x in event_days if x >= 4) + [days]:
        gaps.append(d - last - 1)
        last = d
    out["gap"] = max(gaps)
    out["med_share"] = {h[2]: round(h[1] / h[0], 2) for h in hours.values() if h[0] >= 48}
    out["stolen"] = round(c["tally"]["stolen"])
    out["plague_dead"] = c["tally"]["plague_dead"]
    out["fights"] = fights
    out["hurt"] = sum(1 for f in fights if f[3] != "good")
    out["deaths"] = c["graves"]
    out["raids"] = sum(1 for e in c["annals"] if "beaten off" in e["text"] or "at a cost" in e["text"] or "a defeat" in e["text"])
    out["raid_losses"] = sum(1 for e in c["annals"] if "at a cost" in e["text"] or "a defeat" in e["text"])
    out["fame"] = round(c["fame"])
    out["pop"] = len(c["pawns"])
    out["rooms"] = sum(c["rooms"].values())
    out["loss"] = out["deaths"] > 0 or out["stolen"] >= 10 or out["min_food_days"] < 4      # lost something that mattered
    return out


if __name__ == "__main__":
    import time
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seeds = [int(s) for s in sys.argv[2].split(",")] if len(sys.argv) > 2 else [12345]
    for tell in ("calm", "balanced", "harsh"):
        for prof in ("idle", "careful"):
            for seed in seeds:
                t = time.time()
                r = play(tell, prof, days, seed)
                qi = r["qi60"]
                print(f"{tell:8} {prof:7} s{seed:<6} deaths={r['deaths']} pop={r['pop']}/{r['pop_max']} min_rice={r['min_rice']:.0f} ({r['min_food_days']:.1f}d) "
                      f"lean={r['lean_days']} cap_days={r['cap_days']}/{r['rice_cap_days']} rice={r['rice_by_month']} raids={r['raids']} lost={r['raid_losses']} "
                      f"renown_day={r['renown_day']} fame60={r['fame60']} fame={r['fame']} rooms={r['rooms']} "
                      f"short={r['short_days']} up60={r.get('others_up60')} qi60={list(qi.values())} hurt={r['hurt']} mood={r['mood']} "
                      f"qc80={r['qc80']}/{r['others80']} gap={r['gap']} med={sorted(r['med_share'].values())} stolen={r['stolen']} "
                      f"plague_dead={r['plague_dead']} techs70={r['techs70']} rivals={r['rivals_max']} infil={r['infil']} thefts={r['thefts']} "
                      f"risk80={r['risk80']} bt_fail={sum(1 for b in r['bts'] if not b[2])}/{len(r['bts'])} "
                      f"bt_fail_fe+={sum(1 for b in r['bts'] if not b[2] and b[0] >= 2)}/{sum(1 for b in r['bts'] if b[0] >= 2)} "
                      f"idle_builder={r['idle_builder']} want_mat={r['idle_builder_hours']} hall={r['hall_by_day']} loss={r['loss']} ({time.time() - t:.1f}s)", flush=True)
                if "-v" in sys.argv:
                    print("   ", r["fights"])
