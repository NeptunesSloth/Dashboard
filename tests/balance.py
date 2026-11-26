"""A scripted player for tuning the sect by simulation (CLAUDE.md: "Difficulty is tuned by
simulation, not by feel").

``play(storyteller, profile, days, seed)`` founds a sect, plays it hour by hour and returns the
numbers the balance is judged by. Two profiles:

* ``idle``: never builds, researches or reassigns anyone; clicks the first button on every event.
* ``careful``: builds and researches in a sensible order, keeps a food reserve, fights only when
  the odds are good, heals the wounded, takes breakthroughs at good odds, and acts on the
  sect's alerts (a disciple who has stopped cultivating gets meditation time).

Run ``python tests/balance.py`` for the full table (150 days, every storyteller x profile).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sect_academy import colony, state  # noqa: E402

T0 = 1_800_000_000.0
BUILD_ORDER = ["fields", "storehouse", "training", "library", "dormitory", "main_hall", "ward", "alchemy",
               "meditation", "dormitory", "storehouse", "training", "main_hall", "fields", "ward", "spirit_vein", "meditation",
               "library", "alchemy", "dormitory", "main_hall", "ward", "storehouse", "meditation", "training"]
RESEARCH_ORDER = ["irrigation", "masonry", "granary", "sword_forms", "qi_array", "refinement", "ward_ii", "dao_heart"]


def _careful_choice(c: dict, ev: dict) -> str:
    ids = [o["id"] for o in ev["options"]]
    kind = ev["kind"]
    n = len(c["pawns"])
    rice = c["res"]["rice"]
    if kind == "omen":
        ratio = colony.defense(c) / max(float(ev.get("strength", 1)), 1.0)
        if ratio >= 1.1:
            return "fight"
        if "wards" in ids and ratio < 0.9:
            return "wards"
        if "tribute" in ids and ratio < 0.7:
            return "tribute"
        return "fight"
    if kind == "festival":
        return "hold" if rice >= ev["cost"] + n * 1.2 * 8 else "skip"
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
    if kind == "tournament":
        return ids[0]
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
    if len(c["builds"]) < 2:
        built: dict = {}
        for room in BUILD_ORDER:
            built[room] = built.get(room, 0) + 1
            have = colony._lvl(c, room) + sum(1 for b in c["builds"] if b["room"] == room)
            if have >= built[room]:
                continue
            if colony.queue_build(st, room, T0)["ok"]:
                break
            break                   # wait for the materials for the next thing in the plan
    # the wounded get pills
    for p in c["pawns"]:
        if p["health"] < 40 and c["res"]["pills"] >= 2:
            colony.use_pill(st, p["id"], T0)
    # breakthroughs at good odds
    for p in list(c["pawns"]):
        if colony.ready(p) and colony.bt_chance(c, p) >= 60:
            colony.attempt(st, p["id"], T0)
    # a careful player reads the alerts
    for a in colony._alerts(c):
        if "not meditated" in a["text"] and a.get("pawn") and a["text"] not in seen_alerts:
            seen_alerts.add(a["text"])
            p = colony._p(c, a["pawn"])
            if p and p["prio"].get("meditate", 4) > 3:
                colony.set_priority(st, p["id"], "meditate", 3, T0)


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
    out = {"deaths": 0, "min_rice": 1e9, "min_food_days": 1e9, "lean_days": 0, "cap_days": 0, "rice_cap_days": 0, "short_days": 0,
           "mood": (100, 0), "rice_by_month": [], "raids": 0, "raid_losses": 0, "renown_day": None, "pop_max": 0, "qi60": {},
           "steps60": {}, "fame60": 0, "others_up60": 0}
    try:
        for _ in range(days * 24):
            colony.advance(st, 1, T0)
            for _ in range(4):
                ev = c["pending"]
                if not ev:
                    break
                opt = ev["options"][0]["id"] if profile == "idle" else _careful_choice(c, ev)
                if not colony.resolve(st, opt, T0)["ok"]:
                    colony.resolve(st, ev["options"][-1]["id"], T0)
            if profile == "careful":
                _careful_orders(st, c, seen_alerts)
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
    finally:
        colony._battle = real_battle
    out["fights"] = fights
    out["hurt"] = sum(1 for f in fights if f[3] != "good")
    out["deaths"] = c["graves"]
    out["raids"] = sum(1 for e in c["annals"] if "beaten off" in e["text"] or "at a cost" in e["text"] or "a defeat" in e["text"])
    out["raid_losses"] = sum(1 for e in c["annals"] if "at a cost" in e["text"] or "a defeat" in e["text"])
    out["fame"] = round(c["fame"])
    out["pop"] = len(c["pawns"])
    out["rooms"] = sum(c["rooms"].values())
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
                      f"short={r['short_days']} up60={r.get('others_up60')} qi60={list(qi.values())} hurt={r['hurt']} mood={r['mood']} ({time.time() - t:.1f}s)", flush=True)
                if "-v" in sys.argv:
                    print("   ", r["fights"])
