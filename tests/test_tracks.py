"""Tracks: a language's levels are one long course (packs.tracks(), engine track_* helpers)."""
import pytest

from sect_academy import engine, packs, state

T0 = 1_800_000_000.0
DAY = 86400.0
WORDS = ["chat", "chien", "maison", "pomme", "livre", "table", "porte", "arbre", "fleur", "soleil",
         "lune", "pluie", "neige", "vent", "mer", "route", "ville", "train", "avion", "ecole"]


def _pack(pid: str, units: list[tuple[str, int]], extra: str = "", lang: str = "fr-FR", language: str = "Testish") -> str:
    """A language pack: units [(unit id, n items)], each item a distinct vocab word."""
    out = [f"id: {pid}", f"title: Testish {pid}", "kind: language", f"language: {language}", f"lang: {lang}",
           "hall: tongues_west", "blurb: A tiny language.", *([extra] if extra else []), "units:"]
    for uid, n in units:
        out += [f"  - id: {uid}", f"    title: Unit {uid}", "    goal: I can.", "    notes: Notes.", "    items:"]
        out += [f"      - {{id: {uid}-{i}, type: vocab, l2: {WORDS[i]} {uid}, l1: meaning {uid} {i}}}" for i in range(n)]
    return "\n".join(out) + "\n"


# Pack ids deliberately do not sort in level order: the level decides.
FILES = {
    "a.yaml": _pack("tl-one", [("u-a2a", 4), ("u-a2b", 4)], "track: testish\nlevel: A2"),
    "b.yaml": _pack("tl-zero", [("u-a1a", 4), ("u-a1b", 4)], "track: testish\nlevel: A1"),
    "c.yaml": _pack("tl-two", [("u-b1a", 4)], "track: testish\nlevel: B1"),
    "d.yaml": _pack("tl-talk", [("u-tk", 6)], "track: testish\naddon: talk"),
    "e.yaml": _pack("solo-a1", [("u-solo", 5)]),
}
STAGES = ["tl-zero", "tl-one", "tl-two"]


@pytest.fixture(autouse=True)
def academy(tmp_path, monkeypatch):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.setattr(packs, "PACK_DIR", tmp_path)
    packs.load_all(force=True)
    state.reset_for_tests()
    yield
    monkeypatch.undo()
    packs.load_all(force=True)
    state.reset_for_tests()


def _truth(ex):
    it = packs.item_index()[ex["item"]]
    return it["l2"] if ex["mode"] in ("type_l2", "listen", "build_l2") else engine._truth(it, ex["mode"])


def _play(s, now):
    for ex in s["exercises"]:
        if ex["mode"] != "intro":
            assert engine.answer(ex["item"], ex["mode"], _truth(ex), session=s["session"], now=now)["ok"]


def _new_items(s):
    return [ex["item"] for ex in s["exercises"] if ex["mode"] == "intro"]


def _seen(*unit_ids):
    st = state.get()
    for uid in unit_ids:
        u = next(u for p in packs.load_all().values() for u in p["units"] if u["id"] == uid)
        for it in u["items"]:
            st["cards"][it["id"]] = engine._review(st, None, 3, T0 - 30 * DAY)


def _track(ov):
    return next(t for t in ov["tracks"] if t["id"] == "testish")


# ---------------------------------------------------------------- the track itself
def test_tracks_are_ordered_by_level_and_addons_are_not_stages():
    t = packs.tracks()["testish"]
    assert t["stages"] == STAGES and t["levels"] == ["A1", "A2", "B1"] and t["addons"] == ["tl-talk"]
    assert packs.track_of("tl-one") == (t, "stage") and packs.track_of("tl-talk") == (t, "addon")
    assert packs.track_of("solo-a1") == (None, "") and "solo" not in packs.tracks()
    ov = engine.overview(now=T0)
    tv = _track(ov)
    assert tv["span"] == "A1 → B1" and tv["total"] == 20 and tv["units"] == 5 and not tv["enrolled"]
    assert [s["level"] for s in tv["stages"]] == ["A1", "A2", "B1"] and [a["id"] for a in tv["addons"]] == ["tl-talk"]


def test_item_ids_and_pack_ids_are_unchanged_by_tracks():
    idx = packs.item_index()
    assert idx["u-a1a-0"]["pack"] == "tl-zero" and idx["u-a2a-0"]["pack"] == "tl-one"
    assert set(packs.load_all()) == {"tl-zero", "tl-one", "tl-two", "tl-talk", "solo-a1"}


def test_real_language_tracks_keep_their_pack_and_item_ids(monkeypatch):
    monkeypatch.undo()
    packs.load_all(force=True)
    tr = packs.tracks()
    assert tr["french"]["stages"] == ["french-a1", "french-a2", "french-b1", "french-b2"]
    assert tr["spanish"]["stages"] == ["spanish-a1", "spanish-a2", "spanish-b1", "spanish-b2"]
    for lang in ("mandarin", "japanese", "korean"):
        assert tr[lang]["stages"] == [f"{lang}-a1", f"{lang}-a2"]
        assert sorted(tr[lang]["addons"]) == [f"{lang}-pictures", f"{lang}-swear", f"{lang}-talk"]
    assert packs.item_index()["fr-01-bonjour"]["pack"] == "french-a1"
    assert all(p.get("track") is None for p in packs.load_all().values() if p["kind"] == "cert")


def test_every_language_has_the_swearing_addon_and_it_stays_off_unless_chosen(monkeypatch):
    monkeypatch.undo()
    packs.load_all(force=True)
    state.reset_for_tests()
    tr = packs.tracks()
    for lang in ("spanish", "french", "mandarin", "japanese", "korean"):
        sw = f"{lang}-swear"
        assert sw in tr[lang]["addons"] and sw not in tr[lang]["stages"]
        assert packs.load_all()[sw]["addon"] == "swear"
        assert sw not in engine.enroll(lang)["courses"]                 # taking up the language leaves it off
    ov = engine.overview(now=T0)
    for t in ov["tracks"]:
        if t["id"] in ("spanish", "french", "mandarin", "japanese", "korean"):
            sw = next(a for a in t["addons"] if a["addon"] == "swear")
            assert not sw["enrolled"] and sw["total"] >= 40
    assert f"{lang}-swear" in engine.enroll(f"{lang}-swear")["courses"]   # and it can be turned on
    # a My words deck never borrows its wrong options from the swearing add-on
    rude = {it["l2"] for u in packs.load_all()["spanish-swear"]["units"] for it in u["items"]}
    rude -= {it["l2"] for p in packs.load_all().values() if p["id"] != "spanish-swear"
             for u in p["units"] for it in u["items"] if it.get("l2")}      # coger is also A2's 'to take'
    pool, _ = engine._course_vocab({"lang": "es-ES"}, {"l1": "the house"}, "l2")
    assert pool and not rude & set(pool)


# ---------------------------------------------------------------- enrolment
def test_enrolling_any_stage_or_the_track_enrols_the_whole_track_but_not_its_addons():
    assert engine.enroll("tl-one")["courses"] == STAGES
    assert engine.enroll("testish", False)["courses"] == []
    assert engine.enroll("testish")["courses"] == STAGES
    assert engine.enroll("tl-talk")["courses"] == STAGES + ["tl-talk"]
    # setting the language aside sets its add-ons aside too; an add-on alone is fine
    assert engine.enroll("tl-zero", False)["courses"] == []
    assert engine.enroll("tl-talk")["courses"] == ["tl-talk"]


def test_old_state_with_some_levels_enrolled_is_migrated_to_the_track():
    st = state.get()
    st["settings"]["courses"] = ["solo-a1", "tl-two", "tl-zero"]       # B1 and A1, not A2, out of order
    _seen("u-b1a")                                                      # B1 was being studied
    ov = engine.overview(now=T0)
    assert st["settings"]["courses"] == ["solo-a1"] + STAGES
    tv = _track(ov)
    assert tv["enrolled"] and tv["current"] == "tl-zero"                # A1 is not done: it is the current stage
    s = engine.build_session(now=T0)
    assert {packs.item_index()[i]["pack"] for i in _new_items(s)} == {"tl-zero", "solo-a1"}
    # reviews still come from every stage
    s2 = engine.build_session(now=T0 + 60 * DAY)
    assert "tl-two" in {ex["course"] for ex in s2["exercises"] if not ex.get("new")}
    # a state sanitised from disk keeps working (placements by stage are still read)
    clean = state.sanitize({"cards": {}, "settings": {"courses": ["tl-one"]},
                            "placements": {"tl-zero": {"passed_units": 1, "units": 2, "level": "<b>", "stage": 7}}})
    assert clean["placements"]["tl-zero"]["level"] == "<b>" and clean["placements"]["tl-zero"]["stage"] == ""


# ---------------------------------------------------------------- new items
def test_only_the_current_stage_introduces_new_items():
    engine.enroll("testish")
    s = engine.build_session(now=T0)
    assert s["new"] == 4 and {packs.item_index()[i]["unit"] for i in _new_items(s)} == {"u-a1a"}
    ov = engine.overview(now=T0)
    by = {c["id"]: c for c in ov["courses"]}
    assert by["tl-zero"]["current_stage"] and by["tl-zero"]["new_left"] == 8
    assert by["tl-one"]["new_left"] == 0 and by["tl-two"]["new_left"] == 0 and not by["tl-one"]["current_stage"]
    assert _track(ov)["level"] == "A1" and _track(ov)["new_left"] == 8 and ov["today"]["new_left"] == 8


def test_the_next_stage_begins_when_the_current_one_is_fully_introduced():
    engine.enroll("testish")
    _seen("u-a1a")
    engine.set_settings({"new_per_day": 10})
    s = engine.build_session(size=40, now=T0)
    # A1's last unit (4 items) then, with room left, A2's first unit in the same session
    units = [packs.item_index()[i]["unit"] for i in _new_items(s)]
    assert units[:4] == ["u-a1b"] * 4 and set(units[4:]) == {"u-a2a"} and len(units) == 8
    _play(s, T0)
    ov = engine.overview(now=T0)
    assert _track(ov)["current"] == "tl-one" and _track(ov)["level"] == "A2"
    assert _track(ov)["new_left"] == 2                                  # 10 a day for the track, 8 used
    # the next day: A2's second unit first; B1 only once A2 has nothing left to introduce
    s = engine.build_session(size=40, now=T0 + DAY)
    units = [packs.item_index()[i]["unit"] for i in _new_items(s)]
    assert units == ["u-a2b"] * 4 + ["u-b1a"] * 4


def test_the_daily_new_limit_is_per_track_not_per_stage():
    engine.enroll("testish")
    engine.set_settings({"new_per_day": 6})
    _seen("u-a1a")
    total = 0
    for k in range(4):
        s = engine.build_session(size=40, now=T0 + k * 600)
        total += len(_new_items(s))
        _play(s, T0 + k * 600)
    assert total == 6                                                   # 4 from A1, 2 from A2: one allowance
    ov = engine.overview(now=T0 + 3000)
    assert sum(c["new_left"] for c in ov["courses"] if c["track"] == "testish" and not c["addon"]) == 0
    # "learn 5 more" on any stage (or the track) raises the track's one allowance
    assert engine.learn_more("tl-two", 5, now=T0 + 3000)["ok"]
    assert _track(engine.overview(now=T0 + 3000))["new_left"] == 5
    assert state.get()["extra_new"][engine.day_of(state.get(), T0)] == {"testish": 5}


def test_addons_have_their_own_allowance_only_when_turned_on():
    engine.enroll("testish")
    s = engine.build_session(size=40, now=T0)
    assert "tl-talk" not in {ex["course"] for ex in s["exercises"]}
    engine.enroll("tl-talk")
    engine.set_settings({"new_per_day": 8})
    s = engine.build_session(size=40, now=T0 + 60)
    by = {}
    for i in _new_items(s):
        by.setdefault(packs.item_index()[i]["pack"], 0)
        by[packs.item_index()[i]["pack"]] += 1
    assert by == {"tl-zero": 4, "tl-talk": 6}
    _play(s, T0 + 60)
    by = {c["id"]: c for c in engine.overview(now=T0 + 120)["courses"]}
    assert by["tl-talk"]["new_left"] == 0 and by["tl-zero"]["new_left"] == 4       # 8 - 6 talk; 8 - 4 track
    assert by["tl-talk"]["addon"] == "talk" and by["tl-talk"]["track"] == "testish"


def test_a_session_for_one_track_draws_on_all_its_stages_and_nothing_else():
    engine.enroll("testish")
    engine.enroll("solo-a1")
    for course in ("testish", "tl-two"):
        s = engine.build_session(course=course, now=T0)
        assert s["courses"] == STAGES and {ex["course"] for ex in s["exercises"]} == {"tl-zero"}
    assert engine.build_session(course="solo-a1", now=T0)["courses"] == ["solo-a1"]


# ---------------------------------------------------------------- placement
def _answer_block(p, know: bool):
    ans = [_truth(q) for q in p["questions"]] if know else ["zzz"] * len(p["questions"])
    r = engine.placement_answer(p["placement"], ans, now=T0, unit=p["unit"])
    return {**r, "placement": p["placement"]}


def test_one_placement_walks_on_into_the_next_stage_and_stops_at_the_level():
    engine.enroll("testish")
    p = engine.placement_start("testish", now=T0)
    assert p["ok"] and p["course"] == "testish" and p["level"] == "A1" and p["units"] == 5 and p["unit"] == 0
    p = _answer_block(p, True)
    assert not p["done"] and p["level"] == "A1" and p["unit"] == 1
    p = _answer_block(p, True)                                          # all of A1 known: on into A2
    assert not p["done"] and p["level"] == "A2" and p["stage"] == "tl-one" and p["unit"] == 2
    p = _answer_block(p, True)                                          # A2 unit one known
    p = _answer_block(p, False)                                         # A2 unit two not
    assert p["done"] and p["passed_units"] == 3 and p["units"] == 5 and p["placed"] == 12
    assert p["level"] == "A2" and p["stage"] == "tl-one" and p["start_at"] == "Unit u-a2b"
    ov = engine.overview(now=T0)
    assert ov["placements"]["testish"]["level"] == "A2" and _track(ov)["placement"]["passed_units"] == 3
    assert _track(ov)["current"] == "tl-one"
    s = engine.build_session(now=T0)
    assert [packs.item_index()[i]["unit"] for i in _new_items(s)][:4] == ["u-a2b"] * 4


def test_placement_does_not_cross_a_stage_that_was_not_fully_known():
    engine.enroll("testish")
    p = engine.placement_start("tl-one", now=T0)                        # a stage id: the track's one test
    assert p["course"] == "testish" and p["level"] == "A1"
    p = _answer_block(p, False)                                         # A1 unit one unknown …
    p = _answer_block(p, True)                                          # … unit two known: the end of A1
    assert p["done"] and p["passed_units"] == 1 and p["level"] == "A1" and p["start_at"] == "Unit u-a1a"
    assert not any((state.get()["cards"].get(f"u-a2a-{i}") or {}).get("reps") for i in range(4))


def test_placement_starts_at_the_current_stage_and_reaches_the_end_of_the_track():
    engine.enroll("testish")
    _seen("u-a1a", "u-a1b")
    p = engine.placement_start("testish", now=T0)
    assert p["level"] == "A2" and p["units"] == 3
    for _ in range(3):
        p = _answer_block(p, True)
    assert p["done"] and p["passed_units"] == 3 and p["start_at"] is None and p["level"] == ""


def test_placement_caps_questions_per_stage_and_over_the_track(monkeypatch):
    engine.enroll("testish")
    monkeypatch.setattr(engine, "PLACEMENT_TRACK_MAX", 6)
    p = engine.placement_start("testish", now=T0)
    p = _answer_block(p, True)
    p = _answer_block(p, True)                                          # 6 asked: the track cap
    assert p["done"] and p["asked"] == 6 and p["passed_units"] == 2
    monkeypatch.setattr(engine, "PLACEMENT_TRACK_MAX", 150)
    monkeypatch.setattr(engine, "PLACEMENT_MAX_QUESTIONS", 3)
    state.get()["cards"].clear()
    p = engine.placement_start("testish", now=T0)
    p = _answer_block(p, True)                                          # the stage cap stops it mid-stage
    assert p["done"] and p["asked"] == 3


def test_addon_and_plain_course_placement_are_their_own():
    engine.enroll("tl-talk")
    p = engine.placement_start("tl-talk", now=T0)
    assert p["ok"] and p["course"] == "tl-talk" and p["level"] == "" and p["units"] == 1
    p = engine.placement_answer(p["placement"], [_truth(q) for q in p["questions"]], now=T0)
    assert p["done"] and "tl-talk" in state.get()["placements"]


# ---------------------------------------------------------------- hostile inputs
@pytest.mark.parametrize("course", ["", "nope", "../tl-zero", "TESTISH", "testish ", "my-fr"])
def test_unknown_courses_and_tracks_are_refused(course):
    assert engine.enroll(course)["ok"] is False
    assert engine.placement_start(course)["ok"] is False
    assert engine.learn_more(course)["ok"] is False
    assert state.get()["settings"]["courses"] == []


def test_placement_answers_of_any_shape_and_stale_units_are_safe():
    engine.enroll("testish")
    p = engine.placement_start("testish", now=T0)
    assert engine.placement_answer(p["placement"], [], now=T0, unit=5)["ok"] is False      # not this block
    r = engine.placement_answer(p["placement"], [None, ["a", "b"], 7], now=T0, unit=0)
    assert r["ok"] and not r["passed_unit"]
    assert engine.placement_answer("nope", [], now=T0)["ok"] is False
    state.get()["open_placements"]["old"] = {"course": "tl-zero", "started": T0, "unit": 0}   # a record from before tracks
    assert engine.placement_answer("old", [], now=T0)["ok"] is False


@pytest.mark.parametrize("extra, problem", [
    ("track: testish", "exactly one of level"),
    ("level: A1", "track must be"),
    ("track: testish\nlevel: A9", "level must be one of"),
    ("track: testish\nlevel: A1\naddon: talk", "exactly one of level"),
    ("track: Bad Id\nlevel: A1", "track must be"),
    ("track: [x]\nlevel: A1", "track must be"),
    ("track: testish\naddon: 7", "addon must be"),
])
def test_bad_track_fields_are_rejected(extra, problem):
    import yaml
    pack = yaml.safe_load(_pack("bad-pack", [("u-x", 4)], extra))
    assert any(problem in e for e in packs.validate_pack(pack)), packs.validate_pack(pack)


def test_cert_packs_cannot_join_a_track_and_clashes_are_left_out():
    cert = {"id": "c1", "title": "t", "blurb": "b", "hall": "h", "kind": "cert", "track": "x", "level": "A1"}
    assert any("belong to language packs" in e for e in packs.validate_pack(cert))
    base = {"kind": "language", "language": "L", "lang": "fr-FR", "track": "tt"}
    tracks, errs = packs.build_tracks({
        "p1": {**base, "id": "p1", "level": "A1"}, "p2": {**base, "id": "p2", "level": "A1"},
        "p3": {**base, "id": "p3", "level": "A2", "lang": "es-ES"},
        "tt2": {**base, "id": "tt2", "level": "B1", "track": "p1"},
    })
    assert tracks["tt"]["stages"] == ["p1"] and len(errs) == 3
