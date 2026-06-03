from __future__ import annotations

from maybot_control_center import titles


def _ids(earned):
    return {a["id"] for a in earned}


# --- catalog / shape ---------------------------------------------------------

def test_catalog_has_all_titles_without_predicates():
    cat = titles.catalog()
    assert len(cat) == len(titles.ACHIEVEMENTS)
    for entry in cat:
        assert set(entry) == {"id", "title", "desc"}
        assert "predicate" not in entry
    # ids are unique
    assert len({e["id"] for e in cat}) == len(cat)


def test_evaluate_returns_public_shape():
    earned = titles.evaluate("x", {"realm": 9})
    assert earned
    for e in earned:
        assert set(e) == {"id", "title", "desc"}


def test_empty_stats_earns_nothing():
    assert titles.evaluate("x", {}) == []


# --- per-title thresholds ----------------------------------------------------

def test_immortal_ascendant_threshold():
    assert "immortal_ascendant" in _ids(titles.evaluate("x", {"realm": 8}))
    assert "immortal_ascendant" not in _ids(titles.evaluate("x", {"realm": 7}))


def test_tribulation_survivor_threshold():
    assert "tribulation_survivor" in _ids(titles.evaluate("x", {"breakthroughs": 3}))
    assert "tribulation_survivor" not in _ids(titles.evaluate("x", {"breakthroughs": 2}))


def test_sword_saint_needs_both_specialty_and_mastery():
    assert "sword_saint" in _ids(
        titles.evaluate("x", {"specialty": "Sword Dao", "mastery": 80})
    )
    # mastery too low
    assert "sword_saint" not in _ids(
        titles.evaluate("x", {"specialty": "Sword Dao", "mastery": 79})
    )
    # high mastery but wrong specialty
    assert "sword_saint" not in _ids(
        titles.evaluate("x", {"specialty": "Pill Dao", "mastery": 95})
    )
    # high mastery, no specialty
    assert "sword_saint" not in _ids(titles.evaluate("x", {"mastery": 95}))


def test_elder_sage_needs_elder_specialty_and_mastery():
    assert "elder_sage" in _ids(
        titles.evaluate("x", {"is_elder": True, "specialty": "Pill Dao", "mastery": 60})
    )
    assert "elder_sage" not in _ids(
        titles.evaluate("x", {"is_elder": False, "specialty": "Pill Dao", "mastery": 99})
    )
    assert "elder_sage" not in _ids(
        titles.evaluate("x", {"is_elder": True, "specialty": "Pill Dao", "mastery": 59})
    )
    assert "elder_sage" not in _ids(
        titles.evaluate("x", {"is_elder": True, "mastery": 99})
    )


def test_bane_of_bugs_threshold():
    assert "bane_of_bugs" in _ids(titles.evaluate("x", {"tools_done": 20}))
    assert "bane_of_bugs" not in _ids(titles.evaluate("x", {"tools_done": 19}))


def test_polymath_threshold():
    assert "polymath" in _ids(titles.evaluate("x", {"skills": 10}))
    assert "polymath" not in _ids(titles.evaluate("x", {"skills": 9}))


def test_sect_pillar_requires_leader():
    assert "sect_pillar" in _ids(titles.evaluate("x", {"is_leader": True}))
    assert "sect_pillar" not in _ids(titles.evaluate("x", {"is_leader": False}))


def test_trusted_hand_requires_tier():
    assert "trusted_hand" in _ids(titles.evaluate("x", {"tier": "Trusted"}))
    assert "trusted_hand" not in _ids(titles.evaluate("x", {"tier": "Standard"}))
    assert "trusted_hand" not in _ids(titles.evaluate("x", {"tier": "Probation"}))


def test_diligent_threshold():
    assert "diligent" in _ids(titles.evaluate("x", {"tasks_done": 25}))
    assert "diligent" not in _ids(titles.evaluate("x", {"tasks_done": 24}))


def test_spirit_stone_tycoon_threshold():
    assert "spirit_stone_tycoon" in _ids(titles.evaluate("x", {"stones": 1000}))
    assert "spirit_stone_tycoon" not in _ids(titles.evaluate("x", {"stones": 999}))


def test_flawless_needs_both_success_and_tasks():
    assert "flawless" in _ids(
        titles.evaluate("x", {"success_pct": 99, "tasks_done": 10})
    )
    # high success but too few tasks
    assert "flawless" not in _ids(
        titles.evaluate("x", {"success_pct": 100, "tasks_done": 9})
    )
    # enough tasks but success too low
    assert "flawless" not in _ids(
        titles.evaluate("x", {"success_pct": 98, "tasks_done": 50})
    )


# --- maxed out ---------------------------------------------------------------

def test_maxed_stats_earns_all():
    maxed = {
        "realm": 12,
        "breakthroughs": 9,
        "stones": 99999,
        "skills": 50,
        "mastery": 100.0,
        "merit": 100,
        "tier": "Trusted",
        "tasks_done": 500,
        "tools_done": 500,
        "success_pct": 100,
        "is_leader": True,
        "is_elder": True,
        "specialty": "Sword Dao",
    }
    earned = _ids(titles.evaluate("x", maxed))
    all_ids = {r["id"] for r in titles.ACHIEVEMENTS}
    assert earned == all_ids


# --- robustness --------------------------------------------------------------

def test_bad_types_do_not_crash():
    # garbage numeric values are coerced/ignored, not fatal
    earned = titles.evaluate("x", {"realm": None, "mastery": "oops", "stones": "x"})
    assert earned == []


def test_snapshot_maps_each_agent():
    # injected eval path is not used by snapshot, but it must return a dict keyed by agent.
    snap = titles.snapshot([])
    assert snap == {}
