"""The balance, checked by simulation (tests/balance.py plays the game; ~1 s per 150-day run).

These pin the shape of the difficulty, not exact numbers: an idle sect starves or loses people on
the storytellers that allow it; a careful one survives balanced but loses something that matters on
most seeds (stores carried off by raiders, or a lean stretch under four days of rice), is never left
more than six days without something to decide, and its disciples (not only the Master) meditate a
fair share of their hours and mostly stand in Qi Condensation by day 80. Retune by running
``python tests/balance.py 150 12345,7,99`` and reading the table.
"""
import copy

import pytest
from balance import play

from sect_academy import colony, state

T0 = 1_800_000_000.0
SEEDS = (12345, 7, 99)


@pytest.fixture(scope="module")
def runs():
    return {s: play("balanced", "careful", 150, s) for s in SEEDS}


@pytest.fixture(scope="module")
def careful(runs):
    return runs[12345]


@pytest.mark.parametrize("tell", ["balanced", "harsh"])
def test_an_idle_sect_starves_or_loses_people(tell):
    r = play(tell, "idle", 150, 12345)
    assert r["deaths"] >= 1 or r["lean_days"] >= 10, r
    assert r["gap"] <= 6, r                                           # even a sect nobody steers hears from the world


def test_a_careful_sect_survives_balanced_but_feels_it(careful):
    r = careful
    assert r["deaths"] <= 1 and r["pop"] >= 6, r
    assert r["hurt"] >= 1 or r["lean_days"] >= 1, r                  # a raid that hurts, or a lean stretch
    assert r["rice_cap_days"] < 50 and r["cap_days"] < 50, r          # the granary is not pinned at its limit
    assert r["min_food_days"] < 10, r                                 # winter bites into the stores


def test_a_careful_sect_loses_something_on_most_seeds_and_is_never_left_idle(runs):
    for r in runs.values():
        assert r["deaths"] <= 1 and r["pop"] >= 6, r                   # it survives
        assert r["gap"] <= 6, r                                       # no week without something to decide
    assert sum(r["loss"] for r in runs.values()) >= 2, [(r["deaths"], r["stolen"], round(r["min_food_days"], 1)) for r in runs.values()]
    assert sum(r["stolen"] for r in runs.values()) > 0                # raiders do reach the stores


def test_the_second_month_still_has_teeth(runs):
    """The third playtest: after day 40 nothing went wrong. A careful sect still meets a thief or an infiltrator by
    day 80, its great-realm attempts are capped by realm and sometimes fail, and feuds do not pile up."""
    assert sum(r["risk80"] >= 1 for r in runs.values()) >= 2, [r["risk80"] for r in runs.values()]
    bts = [b for r in runs.values() for b in r["bts"]]
    assert all(odds <= colony.bt_cap(target) for target, odds, _ in bts), bts
    assert sum(1 for b in bts if not b[2]) >= 2, bts
    for r in runs.values():
        assert r["rivals_max"] <= max(1, r["pop_max"] // colony.RIVAL_PER), r["rivals_max"]


def test_research_moves_without_study(runs):
    for r in runs.values():
        assert 5 <= r["techs70"] <= 8, r["techs70"]                   # no study at all in the scripted game


def test_careful_disciples_meditate_and_reach_qi_condensation(runs):
    for r in runs.values():
        assert r["others_up60"] >= 2, r["steps60"]
        shares = sorted(r["med_share"].values())
        assert shares[len(shares) // 2] >= 0.3, shares                # meditation level with the chores: a fair share
        assert 2 * r["qc80"] >= r["others80"] >= 1, r["steps80"]      # most of the first month's disciples, by day 80
    assert sum(r["qc80"] for r in runs.values()) > sum(r["others80"] for r in runs.values()) / 2


def test_a_careful_sect_is_known_in_the_valley_by_the_second_month(careful):
    assert careful["renown_day"] and 25 <= careful["renown_day"] <= 50, careful


# ---------------------------------------------------------------------------
# the pieces, one at a time
# ---------------------------------------------------------------------------
@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony._c(s, T0)["seed"] = 12345
    colony.setup(s, "Azure Lantern", "Jay", T0)
    return s


def test_upkeep_is_a_ledger_and_is_what_is_taken(st):
    c = st["colony"]
    c["rooms"].update(main_hall=3, storehouse=2, training=2, ward=1)          # 10 levels: 7 to keep up
    c["res"].update(wood=100.0, stone=100.0, rice=0.9 * colony._cap(c))
    rows = colony.upkeep(c)
    labels = [label for _, label, _ in rows]
    assert any(label.startswith("Repairs: 7 room levels") for label in labels)
    assert any("spoiling" in label for label in labels) and not any("Winter" in label for label in labels)
    wood = sum(n for res, _, n in rows if res == "wood")
    rice = c["res"]["rice"]
    c["hour"] = 24 * 3 + 5
    colony._hour(c, quiet=False)                                              # 06:00, the morning's upkeep
    assert c["res"]["wood"] == pytest.approx(100.0 - wood, abs=0.01)
    assert c["res"]["rice"] < rice - 1                                        # surplus spoils
    v = colony.view(st, T0)
    assert {u["res"] for u in v["upkeep"]} >= {"rice", "wood", "stone"} and all(isinstance(u["n"], (int, float)) for u in v["upkeep"])
    # winter: the cold makes everyone hungrier and burns firewood, and the ledger says so
    w = copy.deepcopy(c)
    w["hour"] = 24 * 3 * colony.DAYS_PER_SEASON + 3
    p = w["pawns"][1]
    assert colony.appetite(w, p) == pytest.approx(colony.appetite(c, p) * colony.WINTER_HUNGER)
    assert any(label.startswith("Winter: firewood") for _, label, _ in colony.upkeep(w))
    # away, nothing spoils
    q = copy.deepcopy(c)
    q["hour"] = 24 * 4 + 5
    q["res"]["rice"] = rice
    colony._hour(q, quiet=True)
    assert q["res"]["rice"] >= rice - 3 * len(q["pawns"])                  # breakfast, but no rot


def test_work_gathers_a_trickle_of_qi_and_a_stalled_disciple_is_named(st):
    c = st["colony"]
    a, b = c["pawns"][1], c["pawns"][2]
    a["prio"] = {j: 0 for j in colony.JOBS} | {"wood": 1}
    b["prio"] = {j: 0 for j in colony.JOBS} | {"meditate": 1}
    a["qi"] = b["qi"] = 0.0
    for _ in range(24 * (colony.STALL_DAYS + 1)):
        colony.advance(st, 1, T0)
        if c["pending"]:
            colony.resolve(st, c["pending"]["options"][-1]["id"], T0)
    worked = a["qi"] + sum(colony.step_need(s) for s in range(a["step"]))
    sat = b["qi"] + sum(colony.step_need(s) for s in range(b["step"]))
    assert 0 < worked < sat / 3
    v = colony.view(st, T0)
    stalled = [x for x in v["alerts"] if x.get("pawn") == a["id"] and "not meditated" in x["text"]]
    assert stalled and a["name"] in stalled[0]["text"]
    assert not any(x.get("pawn") == b["id"] and "not meditated" in x["text"] for x in v["alerts"])
    pv = next(x for x in v["pawns"] if x["id"] == a["id"])
    assert pv["qi_work"] == colony.WORK_QI
    # a save from before the trickle existed starts counting from now, not from hour zero
    old = copy.deepcopy(c)
    for p in old["pawns"]:
        p.pop("sat_at")
    s2 = {"colony": colony.sanitize(old, T0), "settings": {"tz_offset_min": 0}}
    assert not any("not meditated" in x["text"] for x in colony.view(s2, T0)["alerts"])


def test_fame_for_a_raised_hall_and_a_held_festival(st):
    c = st["colony"]
    c["builds"] = [{"room": "main_hall", "need": 0.01, "done": 0.0}]
    p = c["pawns"][1]
    p["prio"] = {j: 0 for j in colony.JOBS} | {"build": 1}
    p["rest"], p["joy"], c["hour"] = 100.0, 100.0, 24 * 2 + 9
    colony._do_job(c, p, "build", False)
    assert c["fame"] == 4 and c["rooms"]["main_hall"] == 2
    c["res"]["rice"] = 100.0
    colony._ask(c, "festival", "Feast", "x", [("hold", "h"), ("skip", "s")], name="Feast", flavour="f", cost=12)
    colony.resolve(st, "hold", T0)
    assert c["fame"] == 6
    assert colony.renown(19) == "Nameless sect" and colony.renown(20) == "Known in the valley"


def test_new_disciples_do_not_share_fates_or_meridians(st):
    c = st["colony"]
    a, b = colony._make_pawn(c, 50), colony._make_pawn(c, 51)
    a["fates"].append("steady_flame")
    a["meridians"].append("linked")
    assert b["fates"] == [] and b["meridians"] == [] and colony.PAWN_EXTRA["fates"] == []
