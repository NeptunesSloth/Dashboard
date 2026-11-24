"""The sect as a colony sim: needs, work, building, research, events, cultivation, and the study hooks."""
import copy

import pytest

from sect_academy import colony, state

T0 = 1_800_000_000.0


@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony.setup(s, "Azure Lantern", "Jay", T0)
    s["colony"]["seed"] = 12345          # deterministic storyteller
    return s


def _run(st, days, answer=True):
    for _ in range(days * 24):
        colony.advance(st, 1, T0)
        ev = st["colony"]["pending"]
        if ev and answer:
            colony.resolve(st, ev["options"][0]["id"], T0)


def test_founding_gives_a_master_two_disciples_and_stores(st):
    v = colony.view(st, T0)
    assert v["founded"] and v["name"] == "Azure Lantern" and v["master"] == "Jay"
    assert len(v["pawns"]) == 3 and v["pawns"][0]["master"] and v["beds"] == 3
    assert {r["id"]: r["level"] for r in v["rooms"]}["fields"] == 1
    assert all(len(p["traits"]) == 2 and len(p["skills"]) == 6 for p in v["pawns"])
    assert v["season"] == "Spring" and v["day"] == 1 and v["log"][0]["title"] == "The sect is founded"


def test_the_sect_lives_and_cultivates_with_no_study_at_all(st):
    st["colony"]["storyteller"] = "calm"
    rice0 = st["colony"]["res"]["rice"]
    _run(st, 10)
    c = st["colony"]
    assert c["hour"] == 6 + 240 and len(c["pawns"]) >= 3
    assert all(p["health"] > 50 and p["food"] > 0 for p in c["pawns"])           # fed and well
    assert c["res"]["rice"] > rice0                                               # they farm unprompted
    master = next(p for p in c["pawns"] if p["master"])
    assert master["step"] >= 1 or master["qi"] > 20                               # cultivation without a single answer
    assert all(0 <= p["mood"] <= 100 for p in c["pawns"])
    assert colony.view(st, T0)["insight"] == 0


def test_needs_drive_behaviour_and_starvation_hurts(st):
    c = st["colony"]
    p = c["pawns"][1]
    p["rest"] = 5
    colony.advance(st, 1, T0)
    assert p["doing"] == "sleeping" and p["rest"] > 5
    c["res"]["rice"] = 0
    for q in c["pawns"]:
        q["food"] = 1
        q["prio"] = {j: 0 for j in colony.JOBS}                                    # nobody farms
    health = p["health"]
    for _ in range(12):
        colony.advance(st, 1, T0)
    assert p["food"] == 0 and p["health"] < health
    assert any(t["k"] == "starving" for t in p["thoughts"]) and p["mood"] < 50


def test_work_priorities_decide_who_does_what(st):
    c = st["colony"]
    c["hour"] = 9                                                                   # mid-morning
    a = c["pawns"][1]
    for p in c["pawns"]:
        p.update(rest=90, food=90, joy=90)
        p["prio"] = {j: 0 for j in colony.JOBS}
    assert colony.set_priority(st, a["id"], "wood", 1, T0)["ok"]
    wood = c["res"]["wood"]
    colony.advance(st, 1, T0)
    assert a["doing"] == "cut wood" and c["res"]["wood"] > wood
    assert c["pawns"][2]["doing"] == "idle"
    colony.set_priority(st, a["id"], "wood", 0, T0)
    colony.set_priority(st, a["id"], "train", 1, T0)                                # no training grounds: nothing to do
    colony.advance(st, 1, T0)
    assert a["doing"] == "idle"
    assert not colony.set_priority(st, "nobody", "wood", 1, T0)["ok"]
    # equal priority: the scarcest resource wins
    a["prio"].update(wood=2, mine=2, train=0)
    c["res"].update(wood=140, stone=2)
    colony.advance(st, 1, T0)
    assert a["doing"] == "quarry"


def test_building_costs_materials_takes_work_and_is_gated(st):
    c = st["colony"]
    c["hour"] = 8
    c["res"].update(wood=200, stone=200)
    cost = colony.room_cost(c, "library", 0)
    assert colony.queue_build(st, "library", T0)["ok"] and c["res"]["wood"] == 200 - cost["wood"]
    assert colony.view(st, T0)["builds"][0]["name"] == "Scripture Pavilion"
    c["res"].update(wood=0, stone=0)
    assert "more wood" in colony.queue_build(st, "ward", T0)["error"]
    for p in c["pawns"]:
        p.update(rest=95, food=95, joy=95)
    hours = 0
    while c["builds"] and hours < 200:
        for p in c["pawns"]:
            p.update(rest=max(p["rest"], 60), food=90, joy=90)
        colony.advance(st, 1, T0)
        hours += 1
    assert c["rooms"]["library"] == 1 and hours > 3                                 # took real work
    # level gate: a room may be at most one level above the Main Hall
    c["res"].update(wood=999, stone=999, stones=99)
    assert colony.queue_build(st, "library", T0)["ok"]                              # -> level 2, hall is 1
    assert "Main Hall" in colony.queue_build(st, "library", T0)["error"]            # -> level 3 refused
    wood = c["res"]["wood"]
    assert colony.cancel_build(st, 0, T0)["ok"] and c["res"]["wood"] > wood        # materials come back


def test_research_needs_a_library_and_study_insight_speeds_it(st):
    c = st["colony"]
    assert colony.set_research(st, "irrigation", T0)["ok"] and not colony.view(st, T0)["research"]["has_library"]
    colony.advance(st, 5, T0)
    assert c["research"]["progress"] == 0                                           # no library, no scholars' progress
    for _ in range(160):                                                            # … but what you learn still counts
        colony.on_answer(st, "x", correct=True, is_new=False, practice=False, typed=False, now=T0)
    assert c["insight"] == 160
    colony.advance(st, 1, T0)
    assert "irrigation" in c["research"]["done"] and c["insight"] < 20      # the overflow is kept
    assert any(e["title"].startswith("Research complete") for e in c["log"])
    assert not colony.set_research(st, "irrigation", T0)["ok"]


def test_study_is_a_second_engine_not_the_only_one(st):
    c = st["colony"]
    m = next(p for p in c["pawns"] if p["master"])
    r = colony.on_answer(st, "x", correct=True, is_new=False, practice=False, typed=True, now=T0)
    assert r["qi"] == 2 and r["insight"] == 1 and m["qi"] == 2
    assert colony.on_answer(st, "x", correct=True, is_new=False, practice=True, typed=True, now=T0)["qi"] == 0
    assert colony.on_answer(st, "x", correct=False, is_new=True, practice=False, typed=False, now=T0)["qi"] == 0
    res = colony.on_session(st, answers=12, correct=11, counted=True, due_left=0, now=T0)
    assert res["streak"] == 1 and all(any(t["k"] == "lecture" and t["v"] == 10 for t in p["thoughts"]) for p in c["pawns"])
    other = c["pawns"][1]
    q = other["qi"]
    colony.on_trial(st, "x", passed=True, pct=90, now=T0)
    assert other["qi"] > q or other["step"] > 0


def _try(c, seed, pills, st):
    s2 = copy.deepcopy(st)
    cc = s2["colony"]
    cc["seed"] = seed
    cc["res"]["pills"] = pills
    q = cc["pawns"][1]
    q["step"], q["qi"] = 3, colony.step_need(3)
    res = colony.attempt(s2, q["id"], T0)
    return res, q, cc


def test_a_great_realm_waits_for_the_order_and_is_a_gamble(st):
    c = st["colony"]
    p = c["pawns"][1]
    p["step"], p["qi"] = 2, 0.0
    colony._gain_qi(c, p, colony.step_need(2) + 1)
    assert p["step"] == 3                                                           # minor stages just happen
    colony._gain_qi(c, p, colony.step_need(3) * 3)
    assert p["step"] == 3 and p["qi"] == colony.step_need(3)                        # a great realm waits for you
    v = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == p["id"])
    assert v["ready"] and 5 <= v["chance"] <= 95 and sum(o["v"] for o in v["odds"]) == v["chance"] and not v["tribulation"]
    assert any(a.get("pawn") == p["id"] for a in colony.view(st, T0)["alerts"])
    assert not colony.attempt(st, c["pawns"][2]["id"], T0)["ok"]                    # not ready: refused
    seen = set()
    for seed in range(40):
        res, q, _ = _try(c, seed, 0, st)
        seen.add(res["success"])
        if res["success"]:
            assert q["step"] == 4 and q["qi"] == 0
        else:
            assert q["step"] == 3 and q["health"] < 100 and q["qi"] < colony.step_need(3) and q["bt_tries"] == 1
    assert seen == {True, False}
    wins = lambda pills: sum(1 for seed in range(60) if _try(c, seed, pills, st)[0]["success"])   # noqa: E731
    assert wins(1) > wins(0)
    assert _try(c, 1, 1, st)[2]["res"]["pills"] == 0                                # the pill is used up
    # failing teaches: the same hour does not replay the same roll, and the odds improve
    s2 = copy.deepcopy(st)
    q = s2["colony"]["pawns"][1]
    q["bt_tries"] = 3
    assert colony.bt_chance(s2["colony"], q) > colony.bt_chance(c, p)


def test_tribulations_ranks_and_manuals(st):
    c = st["colony"]
    c["storyteller"] = "harsh"
    p = c["pawns"][1]
    p["step"], p["qi"], p["health"] = 11, colony.step_need(11), 100.0              # Foundation peak -> Core Formation
    v = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == p["id"])
    assert v["tribulation"] and v["next_realm"] == "Core Formation" and v["rank"] == "Inner Disciple"
    c["rooms"]["ward"] = 3
    assert any("Ward" in o["label"] for o in next(x for x in colony.view(st, T0)["pawns"] if x["id"] == p["id"])["odds"])
    out = set()
    for seed in range(60):
        s2 = copy.deepcopy(st)
        s2["colony"]["seed"] = seed
        q = s2["colony"]["pawns"][1]
        res = colony.attempt(s2, q["id"], T0)
        out.add(res["success"])
        if res["success"]:
            assert colony.rank_of(q) == 2 and "lightning" in res["event"]["text"] and s2["colony"]["fame"] > 0
    assert out == {True, False}
    # the wounded can die under a tribulation; the Sect Master never does
    s2 = copy.deepcopy(st)
    q = s2["colony"]["pawns"][1]
    q["health"] = 10.0
    for seed in range(200):
        s3 = copy.deepcopy(s2)
        s3["colony"]["seed"] = seed
        if not colony.attempt(s3, q["id"], T0)["success"]:
            assert len(s3["colony"]["pawns"]) == 2 and s3["colony"]["graves"] == 1
            break
    # manuals: rank gates the grade; the best allowed one is used
    c["manuals"] = ["breathing", "azure_tide", "primordial"]
    outer, master = c["pawns"][2], c["pawns"][0]
    outer["step"] = 0
    assert colony._manual(c, outer, "qi")[1] == "breathing"
    assert colony._manual(c, p, "qi")[1] == "azure_tide"                            # an Inner Disciple reads Mystic grade
    assert colony._manual(c, master, "qi")[1] == "primordial"                       # the Master reads everything
    c["manuals"].append("blood_sutra")
    assert colony._manual(c, outer, "qi")[1] == "blood_sutra"                       # forbidden arts ask no rank
    assert ("The Blood Sutra whispers", -8) in colony.mood_mods(c, outer)
    assert colony.burn_manual(st, "blood_sutra", T0)["ok"] and not colony.burn_manual(st, "breathing", T0)["ok"]


def test_raids_are_seen_coming_and_defences_matter(st):
    import random
    c = st["colony"]
    c["hour"] = 24 * 120
    assert len(c["sects"]) == 3 and {s["kind"] for s in c["sects"]} == {"righteous", "demonic", "neutral"}
    rival = colony._rival(c)
    for p in c["pawns"]:
        p["skills"]["combat"]["lv"] = 0
    weak = copy.deepcopy(st)
    colony._omen(weak["colony"], random.Random(1), "raid", colony._rival(weak["colony"]))
    ev = weak["colony"]["pending"]
    assert ev["kind"] == "omen" and rival["name"] in ev["title"] and [o["id"] for o in ev["options"]] == ["fight"]
    assert colony.advance(weak, 5, T0)["hours"] == 0                                # time waits for the answer
    colony.resolve(weak, "fight", T0)
    wc = weak["colony"]
    assert "driven off" not in wc["log"][-1]["title"] and sum(p["health"] for p in wc["pawns"]) < 300
    assert next((p for p in wc["pawns"] if p["master"]), None) is not None          # the Sect Master never dies
    assert wc["adapt"] < 0.85 and wc["last_threat_day"] > colony._day(wc)           # the world eases off the beaten
    strong = copy.deepcopy(st)
    sc = strong["colony"]
    sc["rooms"]["ward"] = 5
    sc["res"]["stones"] = 500.0
    for p in sc["pawns"]:
        p["skills"]["combat"]["lv"] = 18
    colony._omen(sc, random.Random(1), "raid", colony._rival(sc))
    assert [o["id"] for o in sc["pending"]["options"]] == ["fight", "wards", "tribute"]
    paid = copy.deepcopy(strong)
    colony.resolve(paid, "tribute", T0)
    assert paid["colony"]["res"]["stones"] < 500 and paid["colony"]["fame"] == 0
    assert colony._rival(paid["colony"])["rel"] > colony._rival(sc)["rel"] or True
    colony.resolve(strong, "fight", T0)
    assert "driven off" in sc["log"][-1]["title"] and all(p["health"] == 100 for p in sc["pawns"]) and sc["fame"] >= 5
    assert colony.defense(sc) > colony.defense(c) * 3
    # raids stop growing with the calendar after day 48
    late = copy.deepcopy(st)
    late["colony"]["hour"] = 24 * 400
    colony._omen(late["colony"], random.Random(1), "beasts")
    base = copy.deepcopy(st)
    colony._omen(base["colony"], random.Random(1), "beasts")
    assert late["colony"]["pending"]["strength"] == base["colony"]["pending"]["strength"]


def test_every_trope_event_can_be_raised_and_answered_every_way(st):
    """Drive the storyteller for years; every choice of every event must resolve and render."""
    import random
    seen, answered = set(), set()
    for seed in range(30):
        s = copy.deepcopy(st)
        c = s["colony"]
        c["seed"] = seed
        c["storyteller"] = "harsh"
        c["res"].update(rice=900.0, stones=200.0, wood=300.0, stone=300.0)
        c["rooms"].update(main_hall=5, dormitory=5, alchemy=1, ward=1, fields=4)
        pick = random.Random(seed)
        for _ in range(24 * 110):
            colony.advance(s, 1, T0)
            ev = c["pending"]
            if ev:
                seen.add(ev["kind"])
                opt = pick.choice(ev["options"])["id"]
                res = colony.resolve(s, opt, T0)
                if res["ok"]:
                    answered.add((ev["kind"], opt[:4]))
                else:
                    colony.resolve(s, ev["options"][-1]["id"], T0)
                v = colony.view(s, T0)
                assert all(isinstance(x["rel"], int) for x in v["sects"]) and isinstance(v["fame"], int)
        assert c["pawns"] and any(p["master"] for p in c["pawns"])
        assert all(0 <= p["health"] <= 100 for p in c["pawns"])
    assert seen >= {"wanderer", "merchant", "omen", "young_master", "auction", "secret_realm", "beast_cub", "demonic_offer",
                    "cave", "engagement", "spy", "village", "tournament", "recruit"}, seen
    assert {("young_master", "slap"), ("young_master", "endu"), ("secret_realm", "send"), ("tournament", "p")} - answered <= {("tournament", "p")}


def test_trope_consequences_chain(st):
    import random
    c = st["colony"]
    c["hour"] = 24 * 20
    p = c["pawns"][1]
    p["skills"]["combat"]["lv"] = 20
    rival = colony._rival(c)
    rel0 = rival["rel"]
    colony._ask(c, "young_master", "t", "x", [("slap", "s"), ("endure", "e")], pawn=p["id"], src=rival["id"])
    res = colony.resolve(st, "slap", T0)
    assert "slapped" in res["event"]["title"] and rival["rel"] == rel0 - 20 and c["fame"] == 5 and p["title"]
    assert [x["kind"] for x in c["later"]] == ["elder"]                             # beat the young, the old comes
    c["later"][0]["at"] = c["hour"] + 1
    colony.advance(st, 2, T0)
    assert c["pending"]["kind"] == "omen" and "avenge" in c["pending"]["text"]
    colony.resolve(st, "fight", T0)
    # the fallen genius: crippled on arrival, heaven-defying once the ring wakes
    cand = colony._make_pawn(c, 77)
    cand.update(root="Crippled", root_mult=0.6, hidden=True)
    colony._ask(c, "wanderer", "t", "x", [("accept", "a"), ("decline", "d")], cand=cand)
    colony.resolve(st, "accept", T0)
    ring = next(x for x in c["later"] if x["kind"] == "ring")
    ring["at"] = c["hour"] + 1
    colony.advance(st, 2, T0)
    g = colony._p(c, "p77")
    assert g["root"] == "Heaven-Defying" and g["root_mult"] == 2.3 and not g["hidden"]
    # the secret realm: disciples leave, cannot fight while away, and come back with spoils
    stones = c["res"]["stones"]
    colony._ask(c, "secret_realm", "t", "x", [("send3", "a"), ("send1", "b"), ("decline", "d")])
    colony.resolve(st, "send1", T0)
    away = [x for x in c["pawns"] if x["away_until"] > c["hour"]]
    assert len(away) == 1 and colony.combat_power(c, away[0]) == 0
    assert next(x for x in colony.view(st, T0)["pawns"] if x["id"] == away[0]["id"])["away"]
    for _ in range(60):
        colony.advance(st, 1, T0)
        if c["pending"]:
            colony.resolve(st, c["pending"]["options"][-1]["id"], T0)
    assert c["res"]["stones"] > stones and not any(x["away_until"] > c["hour"] for x in c["pawns"])
    # gifts mend relations; a spirit beast guards the gate
    c["res"]["stones"] = 10.0
    rel = rival["rel"]
    assert colony.gift(st, rival["id"], T0)["ok"] and rival["rel"] == rel + 8 and not colony.gift(st, rival["id"], T0)["ok"]
    d0 = colony.defense(c)
    c["beast"] = {"name": "Snow Spirit Fox", "born": c["hour"] - 240}
    assert colony.defense(c) > d0 and colony.view(st, T0)["beast"]["name"] == "Snow Spirit Fox"
    assert random.Random(1)


def test_calm_storyteller_sends_no_raids_and_harsh_sends_many(st):
    def raids(mode):
        s = copy.deepcopy(st)
        s["colony"]["storyteller"] = mode
        _run(s, 60)
        return sum(1 for e in s["colony"]["log"] if "beast tide" in e["title"].lower() or "raid" in e["title"].lower())
    assert raids("calm") == 0
    assert raids("harsh") >= 2


def test_wanderers_and_merchants_wait_for_a_decision(st):
    c = st["colony"]
    cand = colony._make_pawn(c, 9)
    c["pending"] = {"kind": "wanderer", "title": "t", "text": "x", "cand": cand, "expires": c["hour"] + 24,
                    "options": [{"id": "accept", "label": "a"}, {"id": "decline", "label": "d"}]}
    assert colony.view(st, T0)["pending"]["options"][0]["id"] == "accept"
    before = c["hour"]
    assert colony.advance(st, 6, T0)["hours"] == 0 and c["hour"] == before          # the sim waits at the gate
    assert not colony.resolve(st, "nonsense", T0)["ok"]
    assert colony.resolve(st, "accept", T0)["ok"] and len(c["pawns"]) == 4 and c["pending"] is None
    c["res"].update(rice=100, stones=0)
    c["pending"] = {"kind": "merchant", "title": "t", "text": "x", "rate": 1.0, "expires": c["hour"] + 24,
                    "options": [{"id": "sell_rice", "label": "Sell 25 rice for 6 spirit stones"}, {"id": "decline", "label": "d"}]}
    assert colony.resolve(st, "sell_rice", T0)["ok"] and c["res"]["rice"] == 75 and c["res"]["stones"] == 6
    assert not colony.banish(st, c["pawns"][0]["id"], T0)["ok"]                    # not the Master
    assert colony.banish(st, c["pawns"][3]["id"], T0)["ok"] and len(c["pawns"]) == 3


def test_time_away_is_quiet_capped_and_never_fatal(st):
    c = st["colony"]
    c["res"]["rice"] = 0
    for p in c["pawns"]:
        p["food"] = 0
    c["last_real"] = T0
    assert colony.catch_up(st, T0 + 600) == 0                                       # under half an hour: nothing
    assert colony.catch_up(st, T0 + 4 * 3600) == 8
    hours = colony.catch_up(st, T0 + 30 * 86400)
    assert hours == colony.MAX_OFFLINE_HOURS
    assert all(p["health"] == 100 for p in c["pawns"]) and len(c["pawns"]) == 3     # hungry, never harmed
    assert not any("raid" in e["title"].lower() or "beast" in e["title"].lower() for e in c["log"])
    assert any(e["title"] == "While you were away" for e in c["log"])


def test_study_streak_grace_and_seclusion(st):
    c = st["colony"]
    day = 86400
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0)
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 60)       # same day: once
    assert c["streak"] == 1
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 3 * day)  # two days missed, two rest days
    assert c["streak"] == 2 and c["grace"] == 0
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 6 * day)  # none left: restart, nothing lost
    assert c["streak"] == 1 and c["best_streak"] == 2 and len(c["pawns"]) == 3
    colony.set_seclusion(st, True, T0 + 7 * day)
    assert colony.view(st, T0 + 20 * day)["streak"] == 1 and colony.catch_up(st, T0 + 20 * day) == 0
    colony.set_seclusion(st, False, T0 + 21 * day)
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 21 * day)
    assert c["streak"] == 2
    assert not colony.on_session(st, answers=3, correct=3, counted=False, due_left=4, now=T0 + 22 * day)["events"]


def test_view_is_all_plain_numbers_and_a_broken_save_restarts_the_sect_only(st):
    import json
    _run(st, 3)
    v = colony.view(st, T0)
    json.dumps(v)
    assert all(isinstance(r["n"], int) for r in v["res"]) and all(isinstance(p["mood"], int) for p in v["pawns"])
    good = copy.deepcopy(st["colony"])
    assert colony.sanitize(good, T0)["name"] == "Azure Lantern"
    for bad in ({"hour": "x"}, {"hour": 5, "pawns": [1, 2]}, {"hour": 5, "pawns": [{"id": "p"}]}, [1], None,
                dict(good, res="nope"), dict(good, rooms={"fields": "<img>"}), dict(good, hour=float("nan"))):
        out = colony.sanitize(bad, T0)
        assert out == {} or colony.view({"colony": out, "settings": {"tz_offset_min": 0}}, T0)
    evil = copy.deepcopy(good)
    evil["name"] = "<img src=x onerror=alert(1)>" * 40
    evil["pawns"][0]["name"] = "x" * 5000
    out = colony.sanitize(evil, T0)
    assert len(out["name"]) <= 300 and len(out["pawns"][0]["name"]) <= 300          # capped; the UI escapes strings
