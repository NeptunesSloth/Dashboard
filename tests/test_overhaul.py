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
    assert colony.hall_next(c) is None and colony.view(st, T0)["hall_next"] is None
