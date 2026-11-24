"""Sect Academy: content packs, FSRS scheduler, study engine and the sect game."""
import textwrap

import pytest

from maybot_control_center.academy import engine, fsrs, game, packs, state

T0 = 1_800_000_000.0     # a fixed "now" (UTC)
DAY = 86400.0

LANG = textwrap.dedent("""
    id: testish-a1
    title: Testish A1
    kind: language
    language: Testish
    lang: fr-FR
    hall: tongues_west
    blurb: A tiny language.
    units:
      - id: t-01
        title: One
        goal: I can greet.
        notes: "Say **hello**."
        items:
          - {id: t-01-a, type: vocab, l2: bonjour, l1: hello}
          - {id: t-01-b, type: vocab, l2: merci, l1: thank you}
          - {id: t-01-c, type: vocab, l2: le café, l1: the coffee}
          - {id: t-01-d, type: vocab, l2: la bibliothèque, l1: the library}
          - {id: t-01-e, type: phrase, l2: "Comment ça va ?", l1: "How are you?", alt: ["Ça va ?"]}
          - {id: t-01-f, type: cloze, text: "Je ___ étudiant.", answer: suis, l1: I am a student.}
          - {id: t-01-g, type: cloze, text: "Tu ___ ici.", answer: es, l1: You are here.}
      - id: t-02
        title: Two
        goal: I can count.
        notes: Numbers.
        items:
          - {id: t-02-a, type: vocab, l2: un, l1: one}
          - {id: t-02-b, type: vocab, l2: deux, l1: two}
          - {id: t-02-c, type: vocab, l2: trois, l1: three}
          - {id: t-02-d, type: vocab, l2: quatre, l1: four}
""")


def _cert() -> str:
    units = []
    for dom, uid in (("1", "c-1"), ("2", "c-2")):
        items = [f"      - {{id: {uid}-k{i}, type: concept, term: Term {uid}{i}, def: Definition number {uid}{i}.}}"
                 for i in range(5)]
        items += [f"      - {{id: {uid}-q{i}, type: mcq, q: 'Question {uid}{i}?', choices: [right{i}, wrongA{i}, wrongB{i}, wrongC{i}], "
                  f"answer: 0, why: Because {i}.}}" for i in range(10)]
        units.append(f"  - id: {uid}\n    title: Unit {dom}\n    goal: I can.\n    notes: Notes.\n    domain: '{dom}'\n    items:\n"
                     + "\n".join(items))
    return ("id: testcert\ntitle: Test Cert\nkind: cert\nhall: ward_hall\nblurb: A tiny cert.\n"
            "exam: {name: Test Cert, code: TC-1, questions: 10, minutes: 10, pass_pct: 80,\n"
            "       domains: [{id: '1', title: One, weight: 70}, {id: '2', title: Two, weight: 30}]}\n"
            "units:\n" + "\n".join(units) + "\n")


@pytest.fixture(autouse=True)
def academy(tmp_path, monkeypatch):
    (tmp_path / "lang.yaml").write_text(LANG, encoding="utf-8")
    (tmp_path / "cert.yaml").write_text(_cert(), encoding="utf-8")
    monkeypatch.setenv("MAYBOT_ACADEMY_FILE", ":memory:")
    monkeypatch.setattr(packs, "PACK_DIR", tmp_path)
    packs.load_all(force=True)
    state.reset_for_tests()
    yield
    monkeypatch.undo()
    packs.load_all(force=True)
    state.reset_for_tests()


def _truth(ex):
    """The right answer for an exercise, read from the pack (as a perfect learner)."""
    it = packs.item_index()[ex["item"]]
    if ex["mode"] in ("type_l2", "listen"):
        return it["l2"]
    if ex["mode"] == "cloze_type":
        return it["answer"]
    return engine._truth(it, ex["mode"])


def _play(session, now, wrong=()):
    n = c = 0
    for ex in session["exercises"]:
        if ex["mode"] == "intro":
            continue
        ans = "zzz" if ex["item"] in wrong else _truth(ex)
        r = engine.answer(ex["item"], ex["mode"], ans, now=now)
        assert r["ok"]
        n += 1
        c += r["correct"]
    return n, c


# ---------------------------------------------------------------- packs
def test_fixture_packs_valid_and_bad_pack_rejected():
    assert set(packs.load_all()) == {"testish-a1", "testcert"}
    bad = {"id": "x1", "title": "t", "blurb": "b", "hall": "h", "kind": "cert", "units": []}
    assert packs.validate_pack(bad)
    errs = packs.validate_pack({"id": "ok-id", "title": "t", "blurb": "b", "hall": "h", "kind": "language",
                                "language": "L", "lang": "fr-FR",
                                "units": [{"id": "u1", "title": "t", "goal": "g", "notes": "n", "items": [
                                    {"id": "i1", "type": "cloze", "text": "no blank", "answer": "x", "l1": "y"},
                                    {"id": "i1", "type": "vocab", "l2": "a", "l1": "b"},
                                    {"id": "i3", "type": "mcq", "q": "?", "choices": ["a", "b", "c", "d"], "answer": 0, "why": "w"},
                                    {"id": "i4", "type": "vocab", "l2": "", "l1": "b"}]}]})
    text = "\n".join(errs)
    assert "exactly one ___" in text and "duplicate item id" in text and "belong in cert packs" in text and "needs l2" in text


def test_shipped_packs_all_validate():
    """Every pack that ships in the repo must pass the validator."""
    import yaml
    real = packs.Path(packs.__file__).parent / "packs"
    files = sorted(real.glob("*.yaml"))
    assert files, "no content packs shipped"
    seen = {}
    for f in files:
        pack = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert packs.validate_pack(pack, f.name) == []
        for u in pack["units"]:
            for it in u["items"]:
                assert it["id"] not in seen, f"{it['id']} in both {f.name} and {seen[it['id']]}"
                seen[it["id"]] = f.name


# ---------------------------------------------------------------- fsrs
def test_fsrs_first_intervals_and_growth():
    days = [round((fsrs.review(fsrs.new_card(), g, 0)["due"]) / DAY) for g in (1, 2, 3, 4)]
    assert days == [0, 1, 2, 8]                       # FSRS-6 defaults at 0.9 retention
    c = fsrs.review(fsrs.new_card(), fsrs.GOOD, 0)
    prev = c["s"]
    for _ in range(4):
        c = fsrs.review(c, fsrs.GOOD, c["due"])
        assert c["s"] > prev
        prev = c["s"]
    assert abs(fsrs.retrievability(c["s"], c["s"]) - 0.9) < 1e-9
    lapsed = fsrs.review(c, fsrs.AGAIN, c["due"])
    assert lapsed["s"] < c["s"] and lapsed["lapses"] == 1 and lapsed["d"] > c["d"]
    assert fsrs.next_interval(10, 0.95) < fsrs.next_interval(10, 0.9) < fsrs.next_interval(10, 0.8)


# ---------------------------------------------------------------- grading
@pytest.mark.parametrize("given,correct,flag", [
    ("la bibliothèque", True, None),
    ("  La Bibliothèque. ", True, None),
    ("la bibliotheque", True, "accent"),
    ("la bibliothèqe", True, "typo"),
    ("le bibliothèque", False, None),       # wrong article is never forgiven
    ("bibliothèque", False, None),
    ("", False, None),
])
def test_typed_grading(given, correct, flag):
    r = engine.check_typed(given, ["la bibliothèque"])
    assert (r["correct"], r["flag"]) == (correct, flag)


def test_typed_grading_short_words_and_alternates():
    assert not engine.check_typed("as", ["es"])["correct"]              # no typo slack on short answers
    assert not engine.check_typed("ou", ["où"])["correct"]              # on tiny words the accent is the word
    assert engine.fill_cloze({"text": "___ livres sont ici.", "answer": "les"}) == "Les livres sont ici."
    assert engine.check_typed("ca va", ["Comment ça va ?", "Ça va ?"]) == {"correct": True, "flag": "accent", "expected": "Ça va ?"}
    assert engine.check_typed("comment ca va", ["Comment ça va ?"])["correct"]


# ---------------------------------------------------------------- sessions
def test_first_session_introduces_then_tests_and_schedules():
    engine.enroll("testish-a1")
    s = engine.build_session(now=T0)
    assert s["ok"] and s["new"] == 7 and s["reviews"] == 0       # stays inside unit 1 (7 items; limit is 8)
    assert s["notes"] and s["notes"][0]["unit"] == "t-01"
    modes = [e["mode"] for e in s["exercises"]]
    assert modes.count("intro") == 7
    # every intro is followed (later) by a check of the same item
    for i, e in enumerate(s["exercises"]):
        if e["mode"] == "intro":
            assert any(x["item"] == e["item"] and x["mode"] != "intro" for x in s["exercises"][i + 1:])
    for e in s["exercises"]:
        if "choices" in e:
            assert len(e["choices"]) == len(set(e["choices"])) and _truth(e) in e["choices"]
    n, c = _play(s, T0, wrong={"t-01-a"})
    assert (n, c) == (7, 6)
    st = state.get()
    assert st["cards"]["t-01-b"]["due"] == pytest.approx(T0 + 2 * DAY)
    assert st["cards"]["t-01-a"]["due"] == T0                   # missed -> due again right away
    ov = engine.overview(now=T0)
    assert ov["today"]["due"] == 1 and ov["today"]["new"] == 7
    course = next(c for c in ov["courses"] if c["id"] == "testish-a1")
    assert course["seen"] == 7 and course["units"][0]["done"] and course["units"][1]["unlocked"]
    assert course["new_left"] == 1                              # 8/day minus the 7 learned


def test_retry_and_practice_do_not_reschedule():
    engine.enroll("testish-a1")
    _play(engine.build_session(now=T0), T0)
    before = dict(state.get()["cards"]["t-01-a"])
    r = engine.answer("t-01-a", "choose_l2", "bonjour", retry=True, now=T0 + 60)
    assert r["correct"] and state.get()["cards"]["t-01-a"] == before
    p = engine.build_practice(now=T0 + 120)
    assert p["ok"] and p["practice"]
    qi0 = state.get()["game"]["qi"]
    engine.answer("t-01-a", "choose_l2", "bonjour", practice=True, now=T0 + 120)
    assert state.get()["cards"]["t-01-a"] == before
    assert state.get()["game"]["qi"] == qi0 + 1                 # practice pays ~10%


def test_formats_harden_as_cards_mature_and_reviews_come_due():
    engine.enroll("testish-a1")
    _play(engine.build_session(now=T0), T0)
    assert engine.build_session(now=T0 + 3600)["reviews"] == 0  # nothing due yet today; 1 new left
    t = T0 + 2 * DAY
    s = engine.build_session(now=t)
    assert s["reviews"] == 7
    by_item = {e["item"]: e["mode"] for e in s["exercises"] if e["mode"] != "intro"}
    assert by_item["t-01-a"] == "choose_l2" and by_item["t-01-f"] == "cloze_type"
    _play(s, t)
    card = state.get()["cards"]["t-01-a"]
    s3 = engine.build_session(now=card["due"] + 1)
    assert {e["item"]: e["mode"] for e in s3["exercises"]}["t-01-a"] == "type_l2"


def test_claiming_prior_knowledge_needs_a_typed_proof():
    engine.enroll("testish-a1")
    r = engine.answer("t-01-b", "type_l2", "merci", claim=True, now=T0)
    assert r["correct"] and r["next_days"] == 8                 # Easy
    r = engine.answer("t-01-c", "choose_l1", "the coffee", claim=True, now=T0)
    assert r["next_days"] == 2                                  # a multiple-choice hit is not proof


def test_review_debt_holds_back_new_items_and_learn_more():
    engine.enroll("testish-a1")
    engine.set_settings({"session_size": 5, "new_per_day": 2})
    st = state.get()
    for iid in ("t-01-a", "t-01-b", "t-01-c", "t-01-d", "t-01-e", "t-01-f", "t-01-g", "t-02-a", "t-02-b", "t-02-c", "t-02-d"):
        st["cards"][iid] = fsrs.review(fsrs.new_card(), 3, T0 - 5 * DAY)
    s = engine.build_session(now=T0)
    assert s["due_total"] == 11 and s["reviews"] == 5 and s["new"] == 0
    st["cards"].clear()
    assert engine.build_session(now=T0)["new"] == 2
    engine.learn_more("testish-a1", 3, now=T0)
    assert engine.build_session(now=T0)["new"] == 5


def test_local_day_follows_the_learners_timezone():
    engine.set_settings({"tz_offset_min": -480})                # UTC-8
    st = state.get()
    # T0 is 08:00 UTC = local midnight at UTC-8
    assert engine.day_of(st, T0 - 60) == "2027-01-14" and engine.day_of(st, T0) == "2027-01-15"
    assert engine.end_of_day(st, T0) - T0 == pytest.approx(24 * 3600)
    assert engine.end_of_day(st, T0 - 60) == pytest.approx(T0)


# ---------------------------------------------------------------- trials
def test_cert_trial_sampled_by_domain_weight_and_graded():
    engine.enroll("testcert")
    info = engine.trial_info("testcert", now=T0)
    assert info["ready"] and info["questions"] == 10
    tr = engine.start_trial("testcert", now=T0)
    assert tr["ok"] and len(tr["questions"]) == 10
    doms = [packs.item_index()[q["item"]]["unit"] for q in tr["questions"]]
    assert doms.count("c-1") == 7 and doms.count("c-2") == 3
    answers = [_truth(q) for q in tr["questions"]]
    answers[0] = "nope"
    res = engine.submit_trial(tr["trial"], answers, now=T0 + 300)
    assert res["pct"] == 90 and res["passed"] and len(res["domains"]) == 2
    missed = tr["questions"][0]["item"]
    assert state.get()["cards"][missed]["due"] < T0 + DAY        # a miss joins the review queue
    assert not engine.submit_trial(tr["trial"], answers, now=T0 + 301)["ok"]   # single use


def test_trial_overtime_fails_and_language_trial_needs_material():
    engine.enroll("testcert")
    tr = engine.start_trial("testcert", now=T0)
    res = engine.submit_trial(tr["trial"], [_truth(q) for q in tr["questions"]], now=T0 + 3600)
    assert res["pct"] == 100 and res["overtime"] and not res["passed"]
    engine.enroll("testish-a1")
    assert not engine.trial_info("testish-a1", now=T0)["ready"]
    assert not engine.start_trial("testish-a1", now=T0)["ok"]


# ---------------------------------------------------------------- the game
def test_qi_pays_reviews_over_new_and_stage_breakthrough():
    engine.enroll("testish-a1")
    r = engine.answer("t-01-a", "choose_l1", "hello", now=T0)
    assert r["rewards"]["qi"] == 6                               # new item
    r = engine.answer("t-01-a", "choose_l2", "bonjour", now=T0 + 3 * DAY)
    assert r["rewards"]["qi"] == 10                              # due review
    r = engine.answer("t-01-a", "type_l2", "bonjour", now=T0 + 20 * DAY)
    assert r["rewards"]["qi"] == 12                              # typed recall bonus
    g = state.get()["game"]
    g["qi"] = game.step_cost(0) - 1
    r = engine.answer("t-01-b", "choose_l1", "thank you", now=T0)
    assert state.get()["game"]["step"] == 1 and any(e["kind"] == "stage" for e in r["rewards"]["events"])


def test_major_realm_needs_a_passed_trial():
    engine.enroll("testcert")
    g = game._g(state.get(), T0)
    g["step"] = 3
    g["qi"] = game._cum(4) + 50
    engine.answer("c-1-q0", "mcq", "right0", now=T0)
    v = engine.overview(now=T0)["game"]
    assert v["step"] == 3 and v["tribulation"] and v["qi_pct"] == 100
    tr = engine.start_trial("testcert", now=T0)
    res = engine.submit_trial(tr["trial"], [_truth(q) for q in tr["questions"]], now=T0 + 60)
    assert res["passed"] and any(e["kind"] == "realm" for e in res["events"])
    v = engine.overview(now=T0)["game"]
    assert v["step"] == 4 and v["realm"] == "Qi Condensation" and not v["tribulation"]
    assert v["recruit_tokens"] == 2                              # first pass in a course


def test_session_rewards_diminish_and_streak_with_grace():
    engine.enroll("testish-a1")
    _play(engine.build_session(now=T0), T0)
    st = state.get()
    st["days"][engine.day_of(st, T0)]["answers"] = 30
    a = engine.finish_session(10, 10, 300, now=T0)
    b = engine.finish_session(10, 10, 300, now=T0 + 60)
    c = engine.finish_session(10, 10, 300, now=T0 + 120)
    assert a["counted"] and a["stones"] == 15 + 10 + 25 + 15     # base + accuracy + first of day + cleared
    assert b["stones"] == 12 and c["stones"] == 2                # 50%, then 10%
    assert not engine.finish_session(3, 3, 30, now=T0 + 180)["counted"]
    g = st["game"]
    assert g["streak"] == 1 and g["mission_tokens"] == 3
    st["days"].setdefault(engine.day_of(st, T0 + 3 * DAY), {"answers": 30, "correct": 30, "reviews": 0, "new": 0, "sessions": 0,
                                                             "secs": 0, "new_by_course": {}, "courses": [], "typed": 0})
    r = engine.finish_session(10, 10, 300, now=T0 + 3 * DAY)     # two days missed, two grace pills
    assert r["streak"] == 2 and g["grace"] == 0
    st["days"][engine.day_of(st, T0 + 6 * DAY)] = dict(st["days"][engine.day_of(st, T0 + 3 * DAY)], sessions=0)
    flow = g["flow"]
    r = engine.finish_session(10, 10, 300, now=T0 + 6 * DAY)     # no pills left: streak restarts, nothing destroyed
    assert r["streak"] == 1 and g["best_streak"] == 2 and g["flow"] < flow + 0.1 and g["stones"] > 0


def test_seclusion_protects_the_streak():
    engine.enroll("testish-a1")
    st = state.get()
    g = game._g(st, T0)
    g.update(streak=5, last_study_day=engine.day_of(st, T0), grace=0)
    game.set_seclusion(st, True, T0 + DAY)
    assert game.view(st, T0 + 9 * DAY)["streak"] == 5
    game.set_seclusion(st, False, T0 + 10 * DAY)
    game._mark_study_day(st, g, T0 + 10 * DAY)
    assert g["streak"] == 6


def test_rooms_income_is_capped_and_scaled_by_memory():
    engine.enroll("testish-a1")
    st = state.get()
    g = game._g(st, T0)
    assert not game.upgrade(st, "treasury", T0)["ok"]            # tier-locked
    assert not game.upgrade(st, "tongues_west", T0)["ok"]        # course halls grow by study only
    assert game.upgrade(st, "spirit_vein", T0)["ok"] and g["stones"] == 0
    assert not game.upgrade(st, "spirit_vein", T0)["error"] == ""
    g["rooms"]["spirit_vein"] = 5                                # 1 stone/hour
    assert game.view(st, T0 + 2 * 3600)["pending"] == 2
    assert game.view(st, T0 + 100 * 3600)["pending"] == 8        # capped at 8h of storage
    assert game.collect(st, T0 + 100 * 3600)["stones"] == 8 and game.view(st, T0 + 100 * 3600)["pending"] == 0
    # a disciple in a course hall earns in proportion to how well the course is remembered
    t = T0 + 100 * 3600
    game.recruit_offer(st, t)
    d = game.recruit_pick(st, g["candidates"][0]["id"], t)["disciple"]
    assert game.assign(st, d["id"], "tongues_west", t)["ok"]
    base = game._rate(st, g, t)
    st["cards"]["t-01-a"] = fsrs.review(fsrs.new_card(), 3, t)
    fresh = game._rate(st, g, t)
    stale = game._rate(st, g, t + 60 * DAY)
    assert fresh > stale > base
    assert not game.upgrade(st, "grand_hall", t)["ok"]           # gated on learned items, not just stones


def test_recruit_capacity_missions_and_quests():
    engine.enroll("testish-a1")
    st = state.get()
    g = game._g(st, T0)
    g["recruit_tokens"] = 5
    for _ in range(2):
        offer = game.recruit_offer(st, T0)
        assert len(offer["candidates"]) == 3
        game.recruit_pick(st, offer["candidates"][1]["id"], T0)
    assert not game.recruit_offer(st, T0)["ok"]                  # quarters full (2)
    did = g["disciples"][0]["id"]
    assert not game.dispatch(st, did, "herbs", T0)["ok"]         # no mission hall yet
    g["rooms"]["mission_hall"] = 1
    g["mission_tokens"] = 1
    assert game.dispatch(st, did, "herbs", T0)["ok"]
    assert not game.assign(st, did, "spirit_vein", T0)["ok"]     # away
    stones = g["stones"]
    ev = game.ensure(st, T0 + 2 * 3600 + 1)
    assert ev and g["stones"] > stones and not g["missions"]
    ov = engine.overview(now=T0)
    quests = ov["game"]["quests"]
    assert quests and quests[0]["id"] == "session" and all(not q["done"] for q in quests)
    _play(engine.build_session(now=T0), T0)
    engine.finish_session(7, 7, 60, now=T0)                      # under 8 answers: not a counted session
    assert not engine.overview(now=T0)["game"]["quests"][0]["done"]


def test_state_roundtrip_on_disk(tmp_path, monkeypatch):
    p = tmp_path / "academy.json"
    monkeypatch.setenv("MAYBOT_ACADEMY_FILE", str(p))
    engine.enroll("testish-a1")
    engine.answer("t-01-a", "choose_l1", "hello", now=T0)
    assert p.exists()
    state._state = None                                          # simulate a restart
    assert state.get()["cards"]["t-01-a"]["reps"] == 1 and state.get()["settings"]["courses"] == ["testish-a1"]
    p.write_text("{corrupt", encoding="utf-8")
    state._state = None
    assert state.get()["cards"] == {}                            # a corrupt file never crashes the app
