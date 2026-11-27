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
