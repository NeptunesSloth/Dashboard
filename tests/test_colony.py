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


def test_a_great_realm_is_a_gamble_and_pills_help(st):
    c = st["colony"]
    p = c["pawns"][1]
    p["step"], p["qi"] = 2, 0.0
    colony._gain_qi(c, p, colony.step_need(2) + 1)
    assert p["step"] == 3                                                           # minor stages just happen
    outcomes = set()
    for seed in range(40):
        cc = copy.deepcopy(c)
        cc["seed"] = seed
        cc["res"]["pills"] = 0
        q = cc["pawns"][1]
        colony._gain_qi(cc, q, colony.step_need(3) + 1)
        outcomes.add(q["step"])
        if q["step"] == 3:
            assert q["health"] < 100 and q["qi"] < colony.step_need(3)
    assert outcomes == {3, 4}
    with_pill = sum(1 for seed in range(60) if _attempt(c, seed, pills=1) == 4)
    without = sum(1 for seed in range(60) if _attempt(c, seed, pills=0) == 4)
    assert with_pill > without


def _attempt(c, seed, pills):
    cc = copy.deepcopy(c)
    cc["seed"] = seed
    cc["res"]["pills"] = pills
    q = cc["pawns"][1]
    q["step"], q["qi"] = 3, 0.0
    colony._gain_qi(cc, q, colony.step_need(3) + 1)
    return q["step"]


def test_raids_scale_and_defences_matter(st):
    import random
    c = st["colony"]
    c["hour"] = 24 * 120
    for p in c["pawns"]:
        p["skills"]["combat"]["lv"] = 0
    weak = copy.deepcopy(c)
    colony._threat(weak, random.Random(1), "raid")
    strong = copy.deepcopy(c)
    strong["rooms"]["ward"] = 5
    for p in strong["pawns"]:
        p["skills"]["combat"]["lv"] = 18
    colony._threat(strong, random.Random(1), "raid")
    assert "driven off" in strong["log"][-1]["title"] and all(p["health"] == 100 for p in strong["pawns"])
    assert "driven off" not in weak["log"][-1]["title"]
    assert sum(p["health"] for p in weak["pawns"]) < 300
    assert next((p for p in weak["pawns"] if p["master"]), None) is not None       # the Sect Master never dies
    assert colony.defense(strong) > colony.defense(c) * 3


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
