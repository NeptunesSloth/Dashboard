"""The second playtest (66 days, balanced): meditation that never happened, a mid-game with nothing in it,
stories that came back too soon, and texts that did not match the sect."""
import copy
import random

import pytest

from sect_academy import colony, state

T0 = 1_800_000_000.0


@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony._c(s, T0)["seed"] = 12345
    colony.setup(s, "Azure Lantern", "Jay", T0)
    return s


def _force(monkeypatch, c, kind, day=26):
    """Raise one particular daily event on a quiet day."""
    c["hour"] = 24 * day + 5
    c["flags"]["first_threat"] = 1
    c["festival"] = f"{day // 48 + 1}-{colony._season(c)}"
    c["pending"] = None
    monkeypatch.setitem(colony.STORYTELLERS[c["storyteller"]], "event", 5.0)
    real = random.Random.choices
    monkeypatch.setattr(random.Random, "choices", lambda self, pop, weights=None, **kw: [kind] if kind in pop else real(self, pop, weights, **kw))
    colony._daily_event(c)
    monkeypatch.setattr(random.Random, "choices", real)
    return c["pending"]


def _grow(c, n=4):
    c["rooms"].update(main_hall=3, dormitory=3, fields=2, storehouse=2)
    for i in range(n):
        c["pawns"].append(colony._make_pawn(c, 20 + i))
    c["next_pawn"] = 30


def _hours(c, p, n=48):
    """What a disciple picks over n working hours (the store and the hour move on; nothing else does)."""
    out = []
    for _ in range(n):
        c["hour"] += 1
        out.append(colony._pick_job(c, p, {}))
    return out


# ---------------------------------------------------------------------------
# 1. meditation at the same priority as the chores actually happens
# ---------------------------------------------------------------------------
def test_meditation_level_with_the_chores_takes_half_the_hours_even_with_a_big_storehouse(st):
    c = st["colony"]
    c["rooms"]["storehouse"] = 3                                   # the playtest: capacity 150 -> 405, rice 84 of it
    c["res"].update(rice=84.0, wood=200.0, stone=200.0, herbs=50.0)
    p = c["pawns"][1]
    p["prio"] = {j: 0 for j in colony.JOBS} | {"farm": 2, "meditate": 2}
    picks = _hours(c, p)
    assert picks.count("meditate") == 24 and picks.count("farm") == 24
    # one step higher: two thirds; lower: none
    p["prio"]["meditate"] = 1
    assert _hours(c, p, 48).count("meditate") == 32
    p["prio"]["meditate"] = 3
    assert "meditate" not in _hours(c, p)
    # a store that is genuinely low (in days of eating, not share of the storehouse) takes the hours back
    p["prio"]["meditate"] = 2
    eat = sum(v for res, label, v in colony.upkeep(c) if res == "rice" and "spoiling" not in label)
    c["res"]["rice"] = eat * (colony.LOW_STORE_DAYS - 1)
    assert set(_hours(c, p)) == {"farm"}


def test_a_queued_build_wins_a_tie_while_the_stores_hold(st):
    c = st["colony"]
    p = c["pawns"][1]
    p["prio"] = {j: 0 for j in colony.JOBS} | {"farm": 1, "build": 1}         # the elder's first lesson
    c["res"].update(rice=30.0, wood=200.0, stone=200.0)                       # under half the store, but days of food
    assert colony.queue_build(st, "library", T0)["ok"]
    assert colony._pick_job(c, p, {}) == "build"
    c["res"]["rice"] = 1.0                                                   # nearly out: the harvest comes first
    assert colony._pick_job(c, p, {}) == "farm"


def test_the_stall_alert_names_the_priority_that_works(st):
    c = st["colony"]
    a = c["pawns"][1]
    a["prio"] = {j: 0 for j in colony.JOBS} | {"wood": 2, "mine": 3, "meditate": 4}
    c["res"].update(rice=200.0)
    for _ in range(24 * (colony.STALL_DAYS + 1)):
        colony.advance(st, 1, T0)
        if c["pending"]:
            colony.resolve(st, c["pending"]["options"][-1]["id"], T0)
    alert = next(x for x in colony.view(st, T0)["alerts"] if x.get("pawn") == a["id"] and "not meditated" in x["text"])
    assert alert["prio"] == 2 and "Set Meditate to 2" in alert["text"] and "Cut wood" in alert["text"]
    assert colony.set_priority(st, a["id"], "meditate", alert["prio"], T0)["ok"]
    for _ in range(30):
        colony.advance(st, 1, T0)
        if c["pending"]:
            colony.resolve(st, c["pending"]["options"][-1]["id"], T0)
    assert colony.stalled_days(c, a) == 0                                     # the advice was true


# ---------------------------------------------------------------------------
# 2. mid-game threats
# ---------------------------------------------------------------------------
def test_raiders_carry_off_the_fullest_store_and_guards_keep_most_of_it(st):
    c = st["colony"]
    _grow(c)
    c["hour"] = 24 * 30
    c["res"].update(rice=60.0, wood=180.0, stone=20.0, herbs=5.0)
    assert colony.loot_target(c) == "wood"
    strength = colony.defense(c) / 1.0                                        # an even fight: a win, with a break-in
    out = {}
    for how in ("fight", "guard"):
        s = copy.deepcopy(st)
        colony._ask(s["colony"], "omen", "Raiders", "x", [("fight", "f"), ("guard", "g")], threat="raid", strength=strength, src="", cost=5)
        colony.resolve(s, how, T0)
        out[how] = 180.0 - s["colony"]["res"]["wood"]
        assert s["colony"]["tally"]["stolen"] == pytest.approx(out[how])
        assert "carried off" in s["colony"]["log"][-1]["text"] and s["colony"]["scenes"][-1]["kind"] == "theft"
    assert out["fight"] > 0 and 0 < out["guard"] < out["fight"] * 0.5
    # the omen says what is at stake, with numbers, and offers the guard
    colony._omen(c, random.Random(4), "raid", colony._rival(c))
    ev = c["pending"]
    assert "wood (180)" in ev["text"] and any(o["id"] == "guard" and "wood at risk" in o["label"] for o in ev["options"]) \
        or "will not get near it" in ev["text"]


def test_a_fever_spreads_and_kills_if_ignored_and_pills_stop_it(st, monkeypatch):
    c = st["colony"]
    _grow(c)
    c["res"].update(herbs=0.0, pills=0.0)
    ev = _force(monkeypatch, c, "plague")
    assert ev["kind"] == "plague" and [o["id"] for o in ev["options"]] == ["quarantine", "nothing"]
    sick = [colony._p(c, i) for i in ev["sick"]]
    assert all(p["sick_until"] > c["hour"] for p in sick) and all(any(t["k"] == "fever" for t in p["thoughts"]) for p in sick)
    risk = next(o["label"] for o in ev["options"] if o["id"] == "nothing")
    assert "% that someone dies" in risk and "more fall ill" in risk
    # ignored, with the sick already wounded, it kills on balanced (and the ledger of what happened is a scene)
    for p in sick:
        p["health"] = 30.0
    dead = 0
    for seed in range(6):
        s = copy.deepcopy(st)
        sc = s["colony"]
        sc["seed"] = seed
        colony.resolve(s, "nothing", T0)
        for _ in range(24 * 5):
            colony.advance(s, 1, T0)
            if sc["pending"]:
                colony.resolve(s, sc["pending"]["options"][-1]["id"], T0)
        assert any(x["kind"] == "sickness" for x in sc["scenes"]) or sc["tally"]["plague_dead"]
        dead += sc["tally"]["plague_dead"]
    assert dead >= 1
    # pills: cured at once, a scene, nobody else falls ill
    s = copy.deepcopy(st)
    s["colony"]["res"]["pills"] = 5.0
    s["colony"]["pending"]["options"].insert(0, {"id": "pills", "label": "p"})
    colony.resolve(s, "pills", T0)
    assert s["colony"]["res"]["pills"] == 5.0 - len(sick) and s["colony"]["scenes"][-1]["kind"] == "sickness"
    assert not any(x["kind"] == "plague_tick" for x in s["colony"]["later"])


def test_the_fever_odds_are_the_fevers_own(st):
    c = st["colony"]
    _grow(c)
    sick = c["pawns"][1:3]
    for p in sick:
        p["health"] = 40.0
    stated, _ = colony.plague_odds(c, sick, "nothing")
    died = 0
    for seed in range(60):
        s = copy.deepcopy(st)
        sc = s["colony"]
        sc["seed"] = seed
        colony._ask(sc, "plague", "Fever", "x", [("nothing", "n")], sick=[p["id"] for p in sick])
        colony.resolve(s, "nothing", T0)
        for _ in range(4):
            sc["hour"] += 24
            for item in list(sc["later"]):
                if item["kind"] == "plague_tick":
                    sc["later"].remove(item)
                    colony._later(sc, item)
        died += sc["tally"]["plague_dead"] > 0
    assert abs(100 * died / 60 - stated) < 25, (died, stated)


def test_blight_halves_the_harvest_and_the_yield_ledger_says_so(st, monkeypatch):
    c = st["colony"]
    _grow(c)
    before = colony.farm_rows(c)
    ev = _force(monkeypatch, c, "blight", day=14)
    assert ev["kind"] == "blight" and {"burn", "endure"} <= {o["id"] for o in ev["options"]}
    colony.resolve(st, "endure", T0)
    rows = colony.farm_rows(c)
    assert len(rows) == len(before) + 1 and rows[-1][0].startswith("Blight on the terraces") and rows[-1][1] == 0.5
    assert c["scenes"][-1]["kind"] == "blight"
    assert any(r["label"].startswith("Blight") for r in colony.view(st, T0)["farm_yield"]["rows"])
    p = c["pawns"][1]
    rice = c["res"]["rice"]
    colony._do_job(c, p, "farm", False)
    blighted = c["res"]["rice"] - rice
    c["blight"] = None
    rice = c["res"]["rice"]
    colony._do_job(c, p, "farm", False)
    assert blighted == pytest.approx((c["res"]["rice"] - rice) / 2, rel=0.01)
    # it dies with the winter frost
    c["blight"] = {"until": c["hour"] + 24 * 99, "x": 0.5}
    c["hour"] = 24 * 40
    assert colony.blight_left(c) == 0


def test_an_infiltrator_can_be_caught_or_gets_away_with_something(st, monkeypatch):
    c = st["colony"]
    _grow(c)
    c["res"]["stones"] = 40.0
    ev = _force(monkeypatch, c, "infiltrator")
    assert ev["kind"] == "infiltrator" and {"hunt", "wait"} <= {o["id"] for o in ev["options"]}
    assert all("%" in o["label"] for o in ev["options"] if o["id"] in ("hunt", "bait", "wards"))
    victim = colony._p(c, ev["victim"])
    assert any(t["k"] == "drained" for t in victim["thoughts"])
    s = copy.deepcopy(st)
    colony.resolve(s, "wait", T0)
    assert s["colony"]["res"]["stones"] < 40 and s["colony"]["scenes"][-1]["kind"] == "infiltrator" and not s["colony"]["scenes"][-1]["ok"]
    outcomes = set()
    for seed in range(12):
        s = copy.deepcopy(st)
        s["colony"]["hour"] += seed                                          # a different roll each time
        colony.resolve(s, "hunt", T0)
        outcomes.add(s["colony"]["scenes"][-1]["ok"])
    assert outcomes == {True, False}


def test_quiet_spells_are_filled_on_balanced(st):
    c = st["colony"]
    c["storyteller"] = "balanced"
    days = set()
    for _ in range(24 * 60):
        colony.advance(st, 1, T0)
        if c["pending"]:
            days.add(colony._day(c))
            colony.resolve(st, c["pending"]["options"][-1]["id"], T0)
    days = sorted(d for d in days if d >= 4)
    assert max(b - a for a, b in zip(days, days[1:])) <= colony.STORYTELLERS["balanced"]["quiet"] + 1, days


# ---------------------------------------------------------------------------
# 3. stories do not come back too soon; festivals are few and each its own
# ---------------------------------------------------------------------------
def test_the_same_request_comes_at_most_once_a_year(st):
    c = st["colony"]
    seen: dict = {}
    for day in range(0, 200, 4):
        c["hour"] = 24 * day
        c["pending"] = None
        colony._offer_quest(c, random.Random(day))
        kind = c["pending"]["quest"]["kind"]
        if kind in seen:
            assert day - seen[kind] >= colony.QUEST_COOLDOWN or len(colony._quests_open(c, day)) == 0, (kind, seen[kind], day)
        seen[kind] = day


def test_two_festivals_a_year_each_with_its_own_choice(st):
    c = st["colony"]
    held = []
    for day in range(0, 48 * 2):
        f = colony.festival_of(day)
        if f and (not held or held[-1][1] != f):
            held.append((day, f))
    assert [f for _, f in held] == ["lantern", "moon", "ghost", "solstice"]
    alts = set()
    for key in colony.FESTIVALS:
        c["pending"] = None
        colony._offer_festival(c, key)
        ids = [o["id"] for o in c["pending"]["options"]]
        assert ids[0] == "hold" and ids[-1] == "skip"
        alts.add(ids[1])
        s = copy.deepcopy(st)
        s["colony"]["res"].update(rice=200.0, wood=50.0)
        assert colony.resolve(s, ids[1], T0)["ok"] and s["colony"]["scenes"][-1]["kind"] == colony.FESTIVAL_SCENE[key]
    assert len(alts) == 4


# ---------------------------------------------------------------------------
# 4. texts that match the sect
# ---------------------------------------------------------------------------
def test_threat_words_match_the_numbers_and_wards_are_only_named_when_built(st):
    assert colony.strength_word(171 / 100) == "They look weaker than us."
    assert colony.strength_word(2.1) == "They look far weaker than us."
    assert colony.strength_word(0.95) == "It will be close." and colony.strength_word(0.5) == "They are far stronger than us."
    c = st["colony"]
    colony._omen(c, random.Random(1), "beasts", boost=0.4)
    ev = c["pending"]
    assert "ward" not in ev["text"].lower() and "to 1" in ev["text"]
    colony.resolve(st, "fight", T0)
    assert "ward" not in c["log"][-1]["text"].lower()
    c["rooms"]["ward"] = 1
    colony._omen(c, random.Random(1), "beasts", boost=0.4)
    assert "wards" in c["pending"]["text"] and any(o["id"] == "wards" for o in c["pending"]["options"])


def test_the_slain_boar_brings_the_youth_it_promises(st):
    c = st["colony"]
    p = c["pawns"][1]
    n = len(c["pawns"])
    c["later"].append({"at": c["hour"], "kind": "village_return", "pawn": p["id"]})
    colony._later(c, c["later"].pop())
    assert len(c["pawns"]) == n + 1 and c["pawns"][-1]["name"] in c["log"][-1]["text"]
    c["rooms"]["main_hall"] = 0                                             # no room: the letter says so, nobody appears
    colony._later(c, {"at": c["hour"], "kind": "village_return", "pawn": p["id"]})
    assert len(c["pawns"]) == n + 1 and "no room" in c["log"][-1]["text"]


def test_a_weak_sect_can_send_an_observer_to_the_tournament(st):
    c = st["colony"]
    c["hour"] = 24 * 31 + 5
    c["flags"]["first_threat"] = 1
    c["festival"] = f"1-{colony._season(c)}"
    colony._daily_event(c)
    ev = c["pending"]
    assert ev["kind"] == "tournament" and "observe" in [o["id"] for o in ev["options"]]
    w = colony._p(c, ev["watcher"])
    xp, fame = w["skills"]["combat"]["xp"] + 20 * w["skills"]["combat"]["lv"], c["fame"]
    colony.resolve(st, "observe", T0)
    assert c["fame"] == fame + 1 and w["skills"]["combat"]["xp"] + 20 * w["skills"]["combat"]["lv"] > xp
    assert not any(t["k"] == "no_tourney" for p in c["pawns"] for t in p["thoughts"])
