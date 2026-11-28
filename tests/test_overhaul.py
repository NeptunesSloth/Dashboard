"""The sect overhaul (docs/SECT_OVERHAUL_PLAN.md), stage by stage.

Stage 1, map polish: no gold badges on the map (a soft glow and a "+" instead), a room whose crew
made something since dawn says so (visual only), and the next Main Hall level is always shown with
what it opens.
"""
from pathlib import Path

import pytest

from sect_academy import colony, state

T0 = 1_800_000_000.0
STATIC = Path(__file__).resolve().parents[1] / "sect_academy" / "static"


@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony._c(s, T0)["seed"] = 12345
    colony.setup(s, "Azure Lantern", "Jay", T0)
    return s


def _room(v, rid):
    return next(r for r in v["rooms"] if r["id"] == rid)


# ---------------------------------------------------------------------------
# stage 1: map polish
# ---------------------------------------------------------------------------
def test_the_map_has_no_upgrade_badges_but_keeps_the_spoken_label():
    js = (STATIC / "sect.js").read_text(encoding="utf-8")
    css = (STATIC / "academy.css").read_text(encoding="utf-8")
    assert 'class="can"' not in js and "↑" not in js
    assert ".room .can" not in css and ".room.can" in css
    assert "you can afford the next level" in js          # the aria-label stays


def test_a_tray_shows_what_a_room_made_since_dawn_and_changes_nothing(st):
    c = st["colony"]
    c["rooms"]["storehouse"] = 1
    c["made"] = {str(24 * 3 + 2): {"rice|farm|x": 50.0},  # before dawn: not counted
                 str(24 * 3 + 8): {"rice|farm|x": 7.6, "herbs|forage|y": 2.0, "wood|wood|y": 0.4},
                 str(24 * 3 + 9): {"rice|farm|x": 4.0, "stone|mine|z": 3.0, "stones|mine|z": 1.0}}
    c["hour"] = 24 * 3 + 10
    c["made_from"] = 0
    res = dict(c["res"])
    t = colony.trays(c)
    assert t["fields"] == [("rice", pytest.approx(11.6))]
    assert [r for r, _ in t["storehouse"]] == ["stone", "herbs"]           # largest first; under 1 wood is not shown
    assert "spirit_vein" not in t and "alchemy" not in t                  # not built: no tray
    v = colony.view(st, T0)
    assert _room(v, "fields")["tray"] == [{"res": "rice", "name": "rice", "n": 11}]
    assert all(isinstance(x["n"], int) for r in v["rooms"] for x in r["tray"])
    assert c["res"] == res                                                # looking is not collecting
    c["hour"] = 24 * 4 + 7                                                # the next morning: an empty tray
    assert colony.trays(c) == {}


def test_the_next_main_hall_level_says_what_it_opens(st):
    c = st["colony"]
    c["rooms"].update(storehouse=2, library=1)
    h = colony.hall_next(c)
    assert h["level"] == 2
    assert any("2 more disciples" in o and "7 in all" in o for o in h["opens"])
    rooms_line = next(o for o in h["opens"] if o.startswith("Other rooms up to level 3"))
    assert "Storehouse" in rooms_line and "Scripture Pavilion" not in rooms_line      # only the ones held back by the Hall
    assert h["cost"] == colony.room_cost(c, "main_hall", 1)
    c["res"].update(wood=0.0, stone=0.0)
    v = colony.view(st, T0)["hall_next"]
    assert not v["affordable"] and v["short"]["wood"] == v["cost"]["wood"]
    c["res"].update(wood=500.0, stone=500.0)
    assert colony.view(st, T0)["hall_next"]["affordable"]
    assert colony.queue_build(st, "main_hall", T0)["ok"]
    v = colony.view(st, T0)["hall_next"]
    assert v["queued"] and v["level"] == 2 and not v["affordable"] and isinstance(v["pct"], int)
    c["rooms"]["main_hall"] = 3
    c["builds"] = []
    assert any(o.startswith("Branch sects") for o in colony.hall_next(c)["opens"])
    c["rooms"]["main_hall"] = colony.ROOMS["main_hall"]["max"]
    top = colony.view(st, T0)["hall_next"]                       # the card stays at the top of the ladder, and says so
    assert top["top"] and top["level"] == 10 and not top["affordable"] and top["opens"]


# ---------------------------------------------------------------------------
# stage 2: builders and short timers
# ---------------------------------------------------------------------------
DAY = 86400.0


def _ready_for_hall(c, level):
    """Three other rooms at `level`, so the Hall may rise to level+1."""
    c["rooms"].update(main_hall=level, dormitory=max(level, 1), fields=max(level, 1), storehouse=max(level, 1))


def _idle_all(c):
    for p in c["pawns"]:
        p["prio"] = {j: 0 for j in colony.JOBS}


def test_no_build_takes_more_than_36_sim_hours():
    assert max(colony.ROOM_HOURS.values()) <= 36 and max(colony.HALL_HOURS.values()) <= 36
    assert colony.build_hours("library", 1) == colony.ROOM_HOURS[1] and colony.build_hours("main_hall", 2) == colony.HALL_HOURS[2]
    assert colony.MAX_OFFLINE_HOURS >= max(colony.HALL_HOURS.values())


def test_a_builder_finishes_with_nobody_helping(st):
    c = st["colony"]
    _idle_all(c)
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    c["rooms"]["fields"] = 1
    assert colony.queue_build(st, "fields", T0)["ok"]              # to level 2
    colony.advance(st, 1, T0)
    assert c["builds"] and c["builds"][0]["done"] == pytest.approx(1.0)
    assert colony.view(st, T0)["builds"][0]["rows"] == [{"label": "The builder", "x": 1}]
    colony.advance(st, colony.ROOM_HOURS[2] - 1, T0)
    assert not c["builds"] and c["rooms"]["fields"] == 2
    assert c["log"][-1]["title"] == "Rice Terraces raised to level 2"


def test_helpers_speed_a_job_by_what_the_ledger_says(st):
    c = st["colony"]
    _idle_all(c)
    c["hour"] = 24 + 9                                              # mid-morning: awake
    for p in c["pawns"]:
        p.update(rest=100.0, food=100.0, joy=100.0, mood=60.0, thoughts=[])
    helper = c["pawns"][1]
    helper["prio"]["build"] = 1
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    _ready_for_hall(c, 3)
    assert colony.queue_build(st, "main_hall", T0)["ok"]           # level 4
    colony.advance(st, 1, T0)
    b = c["builds"][0]
    rows = colony.build_rate_rows(c, b)
    assert rows[0] == ("The builder", 1.0) and helper["name"] in rows[1][0] and len(rows) == 2
    assert b["done"] == pytest.approx(sum(x for _, x in rows))     # the hour moved by exactly the ledger
    assert rows[1][1] == pytest.approx(colony.HELPER_X * colony._skill_mult(helper, "build") * colony._work_mult(helper, c["hour"]), rel=0.02)
    v = colony.view(st, T0)["builds"][0]
    assert v["rate"] == pytest.approx(sum(r["x"] for r in v["rows"]), abs=0.02) and v["left"] < b["need"] - b["done"]


def test_builder_slots_grow_with_the_hall_and_a_full_crew_refuses_more(st):
    c = st["colony"]
    c["res"].update(wood=9999.0, stone=9999.0, stones=999.0)
    assert colony.builders(c) == 2
    assert colony.queue_build(st, "fields", T0)["ok"] and colony.queue_build(st, "dormitory", T0)["ok"]
    err = colony.queue_build(st, "storehouse", T0)
    assert not err["ok"] and "builders are busy" in err["error"]
    assert not next(r for r in colony.view(st, T0)["rooms"] if r["id"] == "storehouse")["affordable"]
    c["rooms"]["main_hall"] = 3
    assert colony.builders(c) == 3 and [label for label, _ in colony.builder_rows(c)][-1] == "Main Hall level 3"
    assert colony.queue_build(st, "storehouse", T0)["ok"]
    v = colony.view(st, T0)["builders"]
    assert v["n"] == 3 and v["busy"] == 3 and sum(r["n"] for r in v["rows"]) == 3


def test_away_the_builders_finish_and_the_letter_says_so(st):
    c = st["colony"]
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    assert colony.queue_build(st, "ward", T0)["ok"]
    c["last_real"] = T0
    hours = colony.catch_up(st, T0 + 7 * colony.SECS_PER_HOUR_OFFLINE)
    assert hours == 7 and c["rooms"].get("ward") == 1
    assert not any(e["kind"] == "bad" for e in c["log"])
    away = [e for e in c["log"] if e["title"] == "While you were away"][-1]
    assert "Ward Formation built" in away["text"] and "No one came to harm" in away["text"]
    assert "built_away" not in c


def test_builders_work_on_while_an_event_waits_and_nothing_else_moves(st):
    c = st["colony"]
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    _ready_for_hall(c, 2)
    assert colony.queue_build(st, "main_hall", T0)["ok"]           # to level 3
    colony._ask(c, "festival", "Feast", "x", [("hold", "h"), ("skip", "s")], name="Feast", flavour="f", cost=12)
    hour, rice = c["hour"], c["res"]["rice"]
    c["last_real"] = T0
    colony.advance(st, 5, T0 + 3 * colony.SECS_PER_HOUR_OFFLINE + 10)   # watching, with the event open
    assert c["hour"] == hour and c["res"]["rice"] == rice
    assert c["builds"][0]["done"] == pytest.approx(3.0)            # three builder hours at the away rate
    colony.catch_up(st, c["last_real"] + (colony.HALL_HOURS[3] - 3) * colony.SECS_PER_HOUR_OFFLINE)   # away, event still open
    assert c["hour"] == hour and c["rooms"]["main_hall"] == 3 and not c["builds"]
    assert any(e["title"] == "The builders worked on" for e in c["log"])
    c["seclusion"] = True                                          # sealed gates: everything waits, builders too
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    assert colony.queue_build(st, "library", T0)["ok"]
    colony.catch_up(st, c["last_real"] + 6 * colony.SECS_PER_HOUR_OFFLINE)
    assert c["builds"][0]["done"] == 0


def test_study_draws_blueprints_and_lends_the_master_but_never_gates(st):
    c = st["colony"]
    c["res"].update(wood=999.0, stone=999.0, stones=99.0)
    _ready_for_hall(c, 3)
    assert colony.queue_build(st, "main_hall", T0)["ok"]           # to level 4
    ev = colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0)
    assert c["blueprints"]["n"] == 1 and any("blueprint" in e["text"] for e in ev["events"])
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 60)
    assert c["blueprints"]["n"] == 1                               # one a real day
    for d in range(1, 6):
        colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + d * DAY)
    assert c["blueprints"]["n"] == colony.BLUEPRINT_BANK            # banked up to the cap
    b = c["builds"][0]
    assert colony.use_blueprint(st, 0, T0)["ok"]
    assert b["done"] == pytest.approx(colony.HALL_HOURS[4] * colony.BLUEPRINT_CUT) and b["blue"] == pytest.approx(colony.HALL_HOURS[4] * colony.BLUEPRINT_CUT)
    assert colony.view(st, T0)["builds"][0]["blue"] == colony.HALL_HOURS[4] * colony.BLUEPRINT_CUT               # shown in the job's ledger
    assert not colony.use_blueprint(st, 5, T0)["ok"]                   # only a job a builder is on
    # with the sect off, study pays the builders nothing
    st["settings"]["sect_enabled"] = False
    n = c["blueprints"]["n"]
    colony.on_session(st, answers=10, correct=9, counted=True, due_left=0, now=T0 + 9 * DAY)
    assert c["blueprints"]["n"] == n


def test_the_master_is_lent_for_a_day_by_a_week_of_study(st):
    c = st["colony"]
    c["week"] = {"id": "2027-W02", "days": ["a", "b", "c", "d"]}
    colony._study_builds(st, c, T0)
    assert colony.builders(c) == 2
    c["week"]["days"].append("e")
    colony._study_builds(st, c, T0)
    assert colony.builders(c) == 3 and c["master_builds_until"] == c["hour"] + colony.MASTER_BUILDER_HOURS
    until = c["master_builds_until"]
    colony._study_builds(st, c, T0 + DAY)
    assert c["master_builds_until"] == until                         # once a week
    c["hour"] = until
    assert colony.builders(c) == 2


def test_an_old_save_keeps_the_share_its_build_had_done(st):
    c = st["colony"]
    c["builds"] = [{"room": "library", "need": 16.0, "done": 8.0, "cost": {"wood": 10}}]   # disciple work-hours, half done
    colony._repair(c)
    b = c["builds"][0]
    assert b["need"] == colony.build_hours("library", 1) and b["done"] == pytest.approx(b["need"] / 2) and b["slotted"]
    colony._repair(c)                                                # a second load changes nothing
    assert b["done"] == pytest.approx(b["need"] / 2)


# ---------------------------------------------------------------------------
# stage 3: the Main Hall ladder, 1 to 10
# ---------------------------------------------------------------------------
def test_the_ladder_reaches_ten_and_every_unlock_is_a_real_room():
    assert colony.ROOMS["main_hall"]["max"] == 10 and sorted(colony.HALL_LADDER) == list(range(1, 11))
    opened = [k for x in colony.HALL_LADDER.values() for k in x.get("rooms", ())]
    assert sorted(opened) == sorted(k for k in colony.ROOMS if k != "main_hall")          # each room opens exactly once
    caps = [colony.HALL_LADDER[h]["cap"] for h in range(1, 11)]
    assert caps == sorted(caps) and all(cap <= h + 1 for h, cap in enumerate(caps, 1))    # never more than one above the Hall
    assert caps[-1] == max(r["max"] for k, r in colony.ROOMS.items() if k not in ("market", "main_hall")) == 8
    for room in colony.ROOMS:
        assert colony.room_opens_at(room) <= colony.ROOMS["main_hall"]["max"]
    assert colony.room_cost({"research": {"done": []}}, "fields", 3)["wood"] == int(round(colony.ROOMS["fields"]["wood"] * 1.6 ** 3 / 5)) * 5


def test_rooms_open_with_the_hall_and_stay_under_its_cap(st):
    c = st["colony"]
    c["res"].update(wood=9999.0, stone=9999.0, stones=999.0)
    err = colony.queue_build(st, "library", T0)
    assert not err["ok"] and "Opens at Main Hall level 2" in err["error"]
    lib = next(r for r in colony.view(st, T0)["rooms"] if r["id"] == "library")
    assert lib["locked"].startswith("Opens at Main Hall level 2") and not lib["affordable"]
    c["rooms"]["fields"] = 2                                          # at the Hall 1 cap
    err = colony.queue_build(st, "fields", T0)
    assert not err["ok"] and "Main Hall to level 2" in err["error"]
    c["rooms"].update(main_hall=2)
    assert colony.queue_build(st, "library", T0)["ok"] and colony.queue_build(st, "fields", T0)["ok"]
    c["builds"] = []
    c["rooms"].update(main_hall=3, fields=3)                        # Hall 3 still holds rooms at 3
    assert "Main Hall to level 4" in colony.queue_build(st, "fields", T0)["error"]


def test_the_hall_waits_for_three_rooms_and_the_card_says_which(st):
    c = st["colony"]
    c["res"].update(wood=9999.0, stone=9999.0, stones=999.0)
    c["rooms"] = {"main_hall": 1, "dormitory": 1, "fields": 1}
    h = colony.view(st, T0)["hall_next"]
    assert h["need_lv"] == 1 and [x["ok"] for x in h["check"]] == [True, True, False] and not h["ready"] and not h["affordable"]
    err = colony.queue_build(st, "main_hall", T0)
    assert not err["ok"] and "3 other rooms at level 1" in err["error"]
    c["rooms"]["storehouse"] = 1
    assert colony.view(st, T0)["hall_next"]["ready"] and colony.queue_build(st, "main_hall", T0)["ok"]
    c["builds"] = []
    c["rooms"].update(main_hall=4, fields=4, storehouse=4, dormitory=3)
    h = colony.hall_next(c)
    assert h["level"] == 5 and not h["ready"] and [x[1] for x in h["check"]] == [4, 4, 3]
    assert any(o.startswith("New rooms: Trade Post") for o in h["opens"])


def test_the_ladder_card_lists_builders_and_room_levels_as_they_come(st):
    c = st["colony"]
    c["rooms"]["main_hall"] = 2
    opens = colony.hall_next(c)["opens"]
    assert any(o.startswith("A builder more: 3 in all") for o in opens) and any(o.startswith("New rooms: Alchemy Hall") for o in opens)
    assert not any(o.startswith("Other rooms up to") for o in opens)              # Hall 3 opens no room levels
    c["rooms"]["main_hall"] = 9
    opens = colony.hall_next(c)["opens"]
    assert any("up to level 8" in o for o in opens) and any("summit" in o for o in opens)


def test_an_old_save_over_the_new_caps_keeps_its_rooms(st):
    c = st["colony"]
    c["rooms"].update(main_hall=1, library=3, alchemy=2)            # built under the old one-above rule
    s2 = {"colony": colony.sanitize(c, T0), "settings": {"tz_offset_min": 0}}
    assert s2["colony"]["rooms"]["library"] == 3 and s2["colony"]["rooms"]["alchemy"] == 2
    assert colony.view(s2, T0)["rooms"]


# ---------------------------------------------------------------------------
# stage 4: posts by drag, trays to tap, rushes at a shown risk
# ---------------------------------------------------------------------------
def test_a_post_sets_first_priority_and_respects_the_slots(st):
    c = st["colony"]
    a, b, m = c["pawns"][1], c["pawns"][2], c["pawns"][0]
    prio = dict(a["prio"])
    assert colony.set_post(st, a["id"], "fields", T0)["ok"]
    assert a["prio"]["farm"] == 1 and a["post"] == "fields"
    assert {j: v for j, v in a["prio"].items() if j != "farm"} == {j: v for j, v in prio.items() if j != "farm"}   # the rest unchanged
    assert colony.room_slots(c, "fields") == 2
    assert colony.set_post(st, b["id"], "fields", T0)["ok"]
    err = colony.set_post(st, m["id"], "fields", T0)
    assert not err["ok"] and "full (2 of 2)" in err["error"]
    assert not colony.set_post(st, a["id"], "library", T0)["ok"]                  # not built
    assert colony.set_post(st, a["id"], "storehouse", T0)["ok"] is False          # not built either
    c["rooms"]["storehouse"] = 1
    assert colony.set_post(st, a["id"], "storehouse", T0)["ok"]
    assert a["prio"]["farm"] == 2 and all(a["prio"][j] == 1 for j in ("wood", "mine", "forage"))
    v = colony.view(st, T0)
    room = next(r for r in v["rooms"] if r["id"] == "storehouse")
    assert room["posted"] == [a["id"]] and room["slots"] == 3
    assert next(p for p in v["pawns"] if p["id"] == a["id"])["fit"]["fields"] in ("good", "fair", "poor")
    colony.set_priority(st, a["id"], "wood", 3, T0)                               # the detailed grid wins: the post is gone
    assert a["post"] == ""


def _made_today(c, room_job="farm", res="rice", pid=None, n=12.0):
    c["hour"] = 24 * 3 + 14
    c["made_from"] = 0
    pid = pid or c["pawns"][1]["id"]
    c["made"] = {str(24 * 3 + 9): {f"{res}|{room_job}|{pid}": n, f"h|{room_job}|{pid}": 1.0}}


def test_tapping_a_tray_cheers_the_crew_once_a_day_and_adds_nothing(st):
    c = st["colony"]
    _made_today(c)
    res = dict(c["res"])
    assert colony.trays(c)["fields"] == [("rice", 12.0)]
    out = colony.inspect_tray(st, "fields", T0)
    assert out["ok"] and out["made"][0]["n"] == 12 and c["res"] == res               # nothing added: it is in the stores already
    p = c["pawns"][1]
    t = next(t for t in p["thoughts"] if t["k"] == "inspect_fields")
    assert t["v"] == colony.INSPECT_MOOD and t["until"] == c["hour"] + colony.INSPECT_HOURS
    assert "fields" not in colony.trays(c)                                          # the count starts again
    c["made"][str(c["hour"] + 1)] = {f"rice|farm|{p['id']}": 3.0, f"h|farm|{p['id']}": 1.0}
    c["hour"] += 2
    p["thoughts"] = []
    assert colony.inspect_tray(st, "fields", T0)["ok"] and not p["thoughts"]        # once a room a day
    assert not colony.inspect_tray(st, "fields", T0)["ok"]                          # nothing new to look at


def test_a_tray_reads_full_after_a_working_morning(st):
    c = st["colony"]
    _made_today(c)
    assert colony.tray_full(c, "fields")                                            # 8 hours since dawn
    v = next(r for r in colony.view(st, T0)["rooms"] if r["id"] == "fields")
    assert v["tray_full"] and v["tray"]


def test_never_tapping_changes_nothing_in_the_sim(st):
    import copy
    c = st["colony"]
    c["res"].update(wood=200.0, stone=200.0)
    twin = {"colony": copy.deepcopy(c), "settings": copy.deepcopy(st["settings"])}
    for h in range(48):
        colony.advance(st, 1, T0)
        colony.advance(twin, 1, T0)
        if h % 6 == 0:
            for room in list(colony.trays(c)):
                colony.inspect_tray(st, room, T0)
        for s_ in (st, twin):
            if s_["colony"]["pending"]:
                colony.resolve(s_, s_["colony"]["pending"]["options"][-1]["id"], T0)
    assert {k: round(v, 3) for k, v in c["res"].items()} == {k: round(v, 3) for k, v in twin["colony"]["res"].items()}


def test_rush_odds_are_a_ledger_and_the_roll_matches(st):
    c = st["colony"]
    _made_today(c, n=24.0)
    rows = colony.rush_rows(c, "fields")
    assert rows[0] == ("Any rush risks an incident", colony.RUSH_BASE) and colony.rush_chance(c, "fields") == sum(v for _, v in rows)
    c["rushes"] = [{"k": "fields", "h": c["hour"] - 24}, {"k": "fields", "h": c["hour"] - 2}]
    rows = colony.rush_rows(c, "fields")
    assert [v for label, v in rows if label.startswith("Rushed")] == [round(15 * 0.85), round(15 * (1 - 0.15 * 2 / 24))]
    assert colony.rush_chance(c, "fields") == sum(v for _, v in rows)
    c["rushes"] = [{"k": "fields", "h": c["hour"]}] * 8
    assert colony.rush_chance(c, "fields") == colony.RUSH_CAP
    c["rushes"] = []
    # the roll: same seed, same chance -> the resolver's draw decides exactly as the shown odds say
    out = colony.rush_output(c, "fields")
    assert out["rice"] > 0
    chance = colony.rush_chance(c, "fields")
    r = colony._rng(c, "rush", c["hour"], "fields", 0)
    incident = r.random() * 100 < chance
    rice = c["res"]["rice"]
    res = colony.rush(st, "fields", T0)
    assert res["ok"] and res["incident"] == incident
    if not incident:
        assert c["res"]["rice"] > rice
    assert c["rushes"][-1]["k"] == "fields"


def test_a_failed_rush_wounds_but_never_kills_and_idles_the_room(st, monkeypatch):
    c = st["colony"]
    _made_today(c, n=24.0)
    p = c["pawns"][1]
    p["health"] = 6.0
    monkeypatch.setattr(colony, "rush_chance", lambda c_, t: 100)
    monkeypatch.setattr(colony, "contain_chance", lambda c_, t: 0)
    rice = c["res"]["rice"]
    res = colony.rush(st, "fields", T0)
    assert res["ok"] and res["incident"] and not res["contained"]
    assert c["res"]["rice"] == rice and p in c["pawns"] and p["health"] > 0
    assert c["room_idle"]["fields"] == c["hour"] + colony.RUSH_IDLE and not colony._job_open(c, "farm", {})
    assert not colony.rush(st, "fields", T0)["ok"]                                 # still idle
    assert c["scenes"][-1]["kind"] == "incident" and not c["scenes"][-1]["ok"]


def test_rushing_a_build_finishes_it_or_sets_it_back(st, monkeypatch):
    c = st["colony"]
    c["res"].update(wood=999.0, stone=999.0)
    assert colony.queue_build(st, "ward", T0)["ok"]
    monkeypatch.setattr(colony, "rush_chance", lambda c_, t: 0)
    assert colony.rush(st, "", T0, 0)["ok"] and c["rooms"]["ward"] == 1 and not c["builds"]
    assert colony.queue_build(st, "ward", T0)["ok"]
    b = c["builds"][0]
    need, wood = b["need"], b["cost"]["wood"]
    monkeypatch.setattr(colony, "rush_chance", lambda c_, t: 100)
    monkeypatch.setattr(colony, "contain_chance", lambda c_, t: 0)
    assert colony.rush(st, "", T0, 0)["ok"]
    assert b["need"] == need + colony.RUSH_BUILD_BACK and b["cost"]["wood"] == pytest.approx(wood * 0.9)
    assert colony.view(st, T0)["builds"][0]["rush"]["chance"] >= 0


def test_no_rush_or_tray_moves_while_away(st):
    c = st["colony"]
    c["last_real"] = T0
    colony.catch_up(st, T0 + 10 * colony.SECS_PER_HOUR_OFFLINE)
    assert c["rushes"] == [] and c["room_idle"] == {} and c["tray_seen"] == {}


def test_room_play_state_survives_a_bad_save(st):
    c = st["colony"]
    c["rushes"] = [{"k": "fields", "h": 5}, {"k": "nope", "h": 1}, "x"]
    c["tray_seen"] = {"fields": "x", "nope": 3}
    c["pawns"][1]["post"] = "dungeon"
    s2 = colony.sanitize(c, T0)
    assert s2["rushes"] == [{"k": "fields", "h": 5}] and s2["tray_seen"] == {"fields": -1} and s2["pawns"][1]["post"] == ""


# ---------------------------------------------------------------------------
# stage 5: the grid (5 floors of 6 alcoves) and merging
# ---------------------------------------------------------------------------
def _cells(c):
    out = []
    for p in c["plots"].values():
        out += [(p["f"], p["s"] + i) for i in range(p["w"])]
    return out


def _rich(c, hall=5):
    c["rooms"].update(main_hall=hall, dormitory=2, fields=2, storehouse=2)
    c["res"].update(wood=5000.0, stone=5000.0, stones=500.0)
    c["master_builds_until"] = c["hour"] + 10_000                    # a spare builder, so the tests never wait for one


def test_a_new_sect_stands_on_the_grid(st):
    v = colony.view(st, T0)
    plots = {r["id"]: r["plot"] for r in v["rooms"]}
    assert plots["main_hall"] == {"f": 0, "s": 2, "w": 2} and plots["fields"] == {"f": 0, "s": 0, "w": 1} and plots["dormitory"] == {"f": 0, "s": 4, "w": 1}
    assert plots["storehouse"] is None and plots["market"] is None      # not built: no alcove, the alcoves stay empty
    g = v["grid"]
    assert (g["floors"], g["slots"], g["open"], g["next_floor"]) == (5, 6, 2, 2) and g["vault"] == {"f": 1, "s": 5, "w": 1}
    assert len(g["free"]) == 12 - 5 and all(f < 2 for f, _ in g["free"])   # two floors open: 12 alcoves, 5 in use
    assert all(isinstance(x, int) for cell in g["free"] for x in cell)


def test_an_old_save_lands_on_the_grid_with_every_room_and_the_same_levels(st):
    c = st["colony"]
    old = dict(main_hall=4, dormitory=4, fields=3, storehouse=3, library=2, meditation=1, alchemy=2, training=2, ward=3, spirit_vein=1, market=1)
    c["rooms"] = dict(old)
    c.pop("plots")                                                    # a save from before the grid
    a = colony.sanitize(c, T0)
    b = colony.sanitize(c, T0)
    assert a["plots"] == b["plots"]                                   # the same save always lands the same way
    assert a["rooms"] == old and all(colony._lvl(a, k) == v for k, v in old.items())
    assert set(a["plots"]) == set(old) | {"vault"}                    # no room lost, and the vault has its alcove
    cells = _cells(a)
    assert len(cells) == len(set(cells)) == 13 and all(0 <= f < 5 and 0 <= s < 6 for f, s in cells)
    assert all(p["w"] == (2 if k == "main_hall" else 1) for k, p in a["plots"].items())
    assert {k: (p["f"], p["s"]) for k, p in a["plots"].items()} == colony.DEFAULT_CELL
    v = colony.view({"colony": a, "settings": {"tz_offset_min": 0}}, T0)
    assert all(r["plot"] for r in v["rooms"]) and colony.beds(a) == 12 and colony.room_slots(a, "fields") == 6


def test_a_damaged_layout_is_repaired_on_load(st):
    c = st["colony"]
    c["rooms"].update(storehouse=1, ward=1)
    c["plots"] = {"main_hall": {"f": 0, "s": 5, "w": 9}, "fields": {"f": 0, "s": 0, "w": 2}, "dormitory": {"f": 0, "s": 1, "w": 1},
                  "storehouse": "nonsense", "ward": {"f": 7, "s": 0, "w": 1}, "market": {"f": 2, "s": 2, "w": 1}, "bogus": {"f": 1, "s": 1, "w": 1}}
    c["builds"] = [{"room": "fields", "wing": [3, 3], "need": 3.0, "done": 0.0, "cost": {"wood": 10.0}, "slotted": 1}]
    wood = c["res"]["wood"]
    a = colony.sanitize(c, T0)
    cells = _cells(a)
    assert len(cells) == len(set(cells)) and set(a["plots"]) == {"main_hall", "vault", "fields", "dormitory", "storehouse", "ward"}
    assert a["plots"]["main_hall"]["w"] == 2 and a["plots"]["fields"] == {"f": 0, "s": 0, "w": 2}
    assert not a["builds"] and a["res"]["wood"] == wood + 10          # a wing with nowhere to stand: the materials come back


def test_a_new_room_takes_the_empty_alcove_you_choose(st):
    c = st["colony"]
    c["res"].update(wood=500.0, stone=500.0)
    assert not colony.queue_build(st, "storehouse", T0, [0, 2])["ok"]       # the Hall stands there
    assert not colony.queue_build(st, "storehouse", T0, [2, 0])["ok"]       # the third floor opens at Hall 2
    assert not colony.queue_build(st, "storehouse", T0, [9, 9])["ok"] and not colony.queue_build(st, "storehouse", T0, "x")["ok"]
    assert c["res"]["wood"] == 500 and not c["builds"]                     # nothing was paid for a refusal
    assert colony.queue_build(st, "storehouse", T0, [1, 2])["ok"]
    assert c["plots"]["storehouse"] == {"f": 1, "s": 2, "w": 1}
    v = _room(colony.view(st, T0), "storehouse")
    assert v["plot"] == {"f": 1, "s": 2, "w": 1} and not v["open"] and v["queued"] == 1
    assert colony.queue_build(st, "ward", T0)["ok"] and c["plots"]["ward"] == {"f": 1, "s": 3, "w": 1}   # no alcove given: its usual place
    assert colony.cancel_build(st, 0, T0)["ok"]
    assert "storehouse" not in colony._c(st, T0)["plots"]                 # cancelled before it stood: the alcove is empty again
    assert [1, 2] in colony.view(st, T0)["grid"]["free"]


def test_floors_open_with_the_hall(st):
    c = st["colony"]
    assert [colony.floors_open(c | {"rooms": {"main_hall": h}}) for h in range(1, 11)] == [2, 3, 4, 4, 5, 5, 5, 5, 5, 5]
    assert any("new floor" in o for o in colony.hall_opens(c, 2)) and not any("new floor" in o for o in colony.hall_opens(c, 4))
    assert any("two alcoves wide" in o for o in colony.hall_opens(c, 3)) and any("three alcoves wide" in o for o in colony.hall_opens(c, 5))


def test_merge_rules_same_room_beside_it_and_the_hall_sets_the_width(st):
    c = st["colony"]
    _rich(c, hall=2)
    colony._c(st, T0)
    assert "Main Hall level 3" in colony.wing_block(c, "fields")           # two wide from Hall 3
    assert not colony.widen(st, "fields", T0)["ok"]
    c["rooms"]["main_hall"] = 3
    assert colony.wing_block(c, "main_hall") and colony.wing_block(c, "vault") and colony.wing_block(c, "library")   # never, never, not built
    assert colony.wing_cells(c, "fields") == [(0, 1)]                      # beside it, on its floor (the wall is on its left)
    assert not colony.widen(st, "fields", T0, [1, 0])["ok"] and not colony.widen(st, "fields", T0, [0, 3])["ok"]
    wood = c["res"]["wood"]
    cost = colony.wing_cost(c, "fields")
    assert cost == {k: sum(colony.room_cost(c, "fields", lv)[k] for lv in range(2)) for k in ("wood", "stone")}   # a second hall at the same level
    assert colony.widen(st, "fields", T0)["ok"] and c["res"]["wood"] == wood - cost["wood"]
    b = c["builds"][0]
    assert b["wing"] == [0, 1] and b["need"] == colony.build_hours("fields", 2)
    assert not colony.queue_build(st, "fields", T0)["ok"]                  # the halls must match: no level while the wing is built
    assert not colony.queue_build(st, "ward", T0, [0, 1])["ok"]            # the wing's alcove is taken
    assert colony._w(c, "fields") == 1 and colony.room_slots(c, "fields") == 4
    v = _room(colony.view(st, T0), "fields")
    assert v["wing"] == {"f": 0, "s": 1} and v["queued"] == 0 and v["locked"]
    bv = colony.view(st, T0)["builds"][0]
    assert bv["wing"] is True and bv["level"] == 2
    colony.advance(st, int(b["need"]) + 1, T0)
    assert not c["builds"] and c["plots"]["fields"] == {"f": 0, "s": 0, "w": 2} and c["rooms"]["fields"] == 2
    assert "Main Hall level 5" in colony.wing_block(c, "fields")           # three wide from Hall 5
    c["rooms"]["main_hall"] = 5
    assert not colony.wing_block(c, "fields") is None and colony.wing_cells(c, "fields") == []    # the Hall stands beside it
    assert "No empty alcove" in colony.wing_block(c, "fields")
    assert colony.move_room(st, "fields", [2, 0], T0)["ok"] and c["plots"]["fields"] == {"f": 2, "s": 0, "w": 2}
    assert colony.widen(st, "fields", T0, [2, 2])["ok"]
    colony.advance(st, 12, T0)
    assert c["plots"]["fields"]["w"] == 3 and "as wide as a room goes" in colony.wing_block(c, "fields")
    assert not colony.widen(st, "fields", T0)["ok"]


def test_a_wing_on_the_left_moves_the_rooms_first_alcove(st):
    c = st["colony"]
    _rich(c, hall=3)
    colony._c(st, T0)
    assert colony.wing_cells(c, "dormitory") == [(0, 5)]
    assert colony.move_room(st, "dormitory", [1, 2], T0)["ok"]
    assert colony.wing_cells(c, "dormitory") == [(1, 3), (1, 1)]
    assert colony.widen(st, "dormitory", T0, [1, 1])["ok"]
    assert not colony.move_room(st, "dormitory", [1, 0], T0)["ok"]         # not while the builders are on it
    colony.advance(st, 8, T0)
    assert c["plots"]["dormitory"] == {"f": 1, "s": 1, "w": 2} and colony.beds(c) == 3 * 2 * 2


def test_merged_rooms_give_what_the_ledger_says(st):
    c = st["colony"]
    _rich(c, hall=5)
    c["rooms"].update(library=2, ward=2, meditation=1, market=1)
    colony._c(st, T0)
    single = {"slots": colony.room_slots(c, "fields"), "cap": colony._cap(c), "ward": colony.ward_power(c), "lib": colony._library_x(c),
              "farm": colony.farm_rows(c), "cost": colony.room_cost(c, "fields", 2), "hours": colony.build_hours("fields", 3, colony._w(c, "fields"))}
    rows = {a: (b, d) for a, b, d in colony.merge_rows(c, "fields")}
    assert rows == {"Places for posted disciples": ("4", "8"), "Rice per farmer-hour": ("×1", "×1.1"),
                    "Cost of each later level": ("×1", "×1.5"), "Time of each later level": ("×1", "×1.25")}
    assert colony.merge_rows(c, "dormitory")[0] == ("Beds", "6", "12")
    for room in ("fields", "storehouse", "ward", "library", "meditation"):
        c["plots"][room]["w"] = 2
    assert colony.room_slots(c, "fields") == 2 * single["slots"] and colony._job_open(c, "farm", {"farm": single["slots"]})
    assert colony._cap(c) == pytest.approx(150 + (single["cap"] - 150) * 1.1)
    assert colony.ward_power(c) == pytest.approx(single["ward"] * 1.1) and colony._library_x(c) == pytest.approx(single["lib"] * 1.1)
    assert colony.farm_rows(c) == single["farm"][:2] + [("The Terraces are two alcoves wide", 1.1)] + single["farm"][2:]   # its own ledger row
    assert any("two alcoves wide" in a for a, _ in colony.research_rows(c)) and any("two alcoves wide" in a for a, _ in colony.qi_rate(c, c["pawns"][0]))
    cost = colony.room_cost(c, "fields", 2)
    assert cost["wood"] == pytest.approx(single["cost"]["wood"] * 1.5, abs=5) and cost["wood"] < 2 * single["cost"]["wood"]
    assert colony.build_hours("fields", 3, 2) == single["hours"] * 1.25
    c["plots"]["fields"]["w"] = 3
    assert colony.merge_rows(c, "fields") == []                        # as wide as it goes: nothing more to offer
    assert colony.room_slots(c, "fields") == 3 * single["slots"] and colony.farm_rows(c)[2] == ("The Terraces are three alcoves wide", 1.2)
    assert max(colony.build_hours(r, lv, 3) for r in colony.ROOMS for lv in range(1, 11)) <= 36     # no timer over 36 h, merged or not
    v = _room(colony.view(st, T0), "fields")
    assert v["wide"]["w"] == 3 and v["wide"]["x"] == 1.2 and not v["wide"]["rows"] and v["plot"]["w"] == 3
    assert _room(colony.view(st, T0), "main_hall")["wide"] is None


def test_merging_keeps_an_alcove_for_every_room_not_built(st):
    c = st["colony"]
    _rich(c, hall=3)                                                  # four floors: 24 alcoves; Hall, vault, three rooms
    colony._c(st, T0)
    used = set(_cells(c))
    spare = [(f, s) for f in range(4) for s in range(6) if (f, s) not in used and (f, s) != (0, 1)]
    for i, cell in enumerate(spare[:len(spare) - 6]):                  # fill the grid until 7 alcoves are left: 7 rooms are not built
        c["plots"][f"x{i}"] = {"f": cell[0], "s": cell[1], "w": 1}
    assert len(colony.free_cells(c)) == 7 and sum(1 for k in colony.ROOMS if k not in c["plots"]) == 7
    assert "Keep an alcove" in colony.wing_block(c, "fields")
    c["rooms"]["ward"] = 1
    c["plots"]["ward"] = c["plots"].pop("x0")                          # one more room stands: one alcove to spare
    assert colony.wing_block(c, "fields") == ""


def test_moving_a_room_needs_empty_alcoves_on_an_open_floor(st):
    c = st["colony"]
    _rich(c, hall=3)
    colony._c(st, T0)
    c["plots"]["storehouse"] = {"f": 1, "s": 0, "w": 2}
    assert not colony.move_room(st, "storehouse", [4, 0], T0)["ok"]        # the top floor opens at Hall 5
    assert not colony.move_room(st, "storehouse", [0, 2], T0)["ok"]        # the Hall is there
    assert not colony.move_room(st, "library", [2, 0], T0)["ok"]           # not built: nothing to move
    assert colony.move_room(st, "storehouse", [0, 1], T0)["ok"] is False   # one empty alcove between the Terraces and the Hall: too narrow
    assert colony.move_room(st, "storehouse", [2, 5], T0)["ok"] and c["plots"]["storehouse"] == {"f": 2, "s": 4, "w": 2}   # slides to fit
    assert colony.move_room(st, "storehouse", [2, 5], T0)["ok"] and c["plots"]["storehouse"]["s"] == 4                    # onto itself is fine
    assert colony.move_room(st, "vault", [3, 0], T0)["ok"] and colony.view(st, T0)["grid"]["vault"] == {"f": 3, "s": 0, "w": 1}
    assert colony.move_room(st, "main_hall", [1, 0], T0)["ok"] and c["plots"]["main_hall"] == {"f": 1, "s": 0, "w": 2}


def test_the_grid_keeps_the_sect_optional_and_takes_orders_over_the_api(monkeypatch):
    from fastapi.testclient import TestClient

    from sect_academy.app import app
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony.setup(s, "Azure Lantern", "Jay", T0)
    s["colony"]["res"].update(wood=500.0, stone=500.0)
    client = TestClient(app)
    r = client.post("/api/sect/build", json={"room": "storehouse", "cell": [1, 1]}).json()
    assert r["ok"] and next(x for x in r["sect"]["rooms"] if x["id"] == "storehouse")["plot"] == {"f": 1, "s": 1, "w": 1}
    assert client.post("/api/sect/build", json={"room": "ward", "cell": [1, 2, 3]}).status_code == 422       # a cell is two numbers
    assert client.post("/api/sect/move-room", json={"room": "vault", "cell": [1, 4]}).json()["ok"]
    assert not client.post("/api/sect/widen", json={"room": "fields", "cell": [0, 1]}).json()["ok"]         # Hall 1: no merging yet
    s["settings"]["sect_enabled"] = False
    assert client.post("/api/sect/widen", json={"room": "fields"}).status_code == 409                        # study only: no orders


def test_the_map_is_the_painted_grid_not_the_old_painting():
    js = (STATIC / "sect.js").read_text(encoding="utf-8")
    art = (STATIC / "art.js").read_text(encoding="utf-8")
    assert "hq_grid.webp" in art and "hq.webp" not in art and "SITES" not in art and "siteCrop" not in js
    assert not (STATIC / "art" / "hq.webp").exists() and (STATIC / "art" / "hq_grid.webp").exists()
    for room in list(colony.ROOMS) + ["vault"]:
        assert (STATIC / "art" / f"room_{room}.webp").exists(), room
        assert f"'{room}'" in art
