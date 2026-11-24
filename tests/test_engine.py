"""Content packs, the FSRS scheduler and the study engine (on small fixture packs)."""
import textwrap

import pytest

from sect_academy import engine, fsrs, packs, state

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
        items += [f"      - {{id: {uid}-m0, type: multi, q: 'Choose TWO for {uid}.', choices: [yes1, yes2, no1, no2, no3], "
                  f"answers: [0, 1], why: Because.}}",
                  f"      - {{id: {uid}-o0, type: order, q: 'Order {uid}.', steps: [first, second, third, fourth], why: Because.}}"]
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
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
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
    if ex["mode"] in ("type_l2", "listen", "build_l2"):
        return it["l2"]
    if ex["mode"] == "cloze_type":
        return it["answer"]
    if ex["mode"] in engine.LIST_MODES:
        return engine.truth_list(it)
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


def test_shipped_packs_all_validate(monkeypatch, capsys):
    """Every pack and part that ships in the repo must pass the validator, with no id used twice."""
    real = packs.Path(packs.__file__).parent / "packs"
    monkeypatch.setattr(packs, "PACK_DIR", real)
    assert sorted(real.glob("*.yaml")), "no content packs shipped"
    rc = packs.main([])
    assert rc == 0, capsys.readouterr().out


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
    r = engine.answer("t-01-a", "choose_l2", "bonjour", practice=True, now=T0 + 120)
    assert state.get()["cards"]["t-01-a"] == before and r["rewards"]["qi"] == 0     # practice changes nothing


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
    assert {q["mode"] for q in tr["questions"]} <= {"mcq", "multi", "order"}
    answers = [_truth(q) for q in tr["questions"]]
    answers[0] = ["nope"] if tr["questions"][0]["mode"] in engine.LIST_MODES else "nope"
    res = engine.submit_trial(tr["trial"], answers, now=T0 + 300)
    assert res["pct"] == 90 and res["passed"] and len(res["domains"]) == 2
    missed = tr["questions"][0]["item"]
    assert missed not in state.get()["cards"]                    # never met: a trial must not mark it learned
    assert not engine.submit_trial(tr["trial"], answers, now=T0 + 301)["ok"]   # single use
    # a wrong answer on a card you do have sends it back to the queue; a blank changes nothing
    st = state.get()
    tr = engine.start_trial("testcert", now=T0)
    a, b = tr["questions"][0]["item"], tr["questions"][1]["item"]
    for iid in (a, b):
        st["cards"][iid] = fsrs.review(fsrs.new_card(), 3, T0 - 30 * DAY)
    keep = dict(st["cards"][b])
    answers = [_truth(q) for q in tr["questions"]]
    answers[0] = ["nope"] if tr["questions"][0]["mode"] in engine.LIST_MODES else "nope"
    answers[1] = None
    engine.submit_trial(tr["trial"], answers, now=T0 + 60)
    assert st["cards"][a]["lapses"] == 1 and st["cards"][a]["due"] <= T0 + 60
    assert st["cards"][b] == keep
    tr = engine.start_trial("testcert", now=T0)
    assert engine.abandon_trial(tr["trial"])["abandoned"] and not engine.submit_trial(tr["trial"], [], now=T0)["ok"]


def test_trial_overtime_fails_and_language_trial_needs_material():
    engine.enroll("testcert")
    tr = engine.start_trial("testcert", now=T0)
    res = engine.submit_trial(tr["trial"], [_truth(q) for q in tr["questions"]], now=T0 + 3600)
    assert res["pct"] == 100 and res["overtime"] and not res["passed"]
    engine.enroll("testish-a1")
    assert not engine.trial_info("testish-a1", now=T0)["ready"]
    assert not engine.start_trial("testish-a1", now=T0)["ok"]


# ---------------------------------------------------------------- the game












def test_state_roundtrip_on_disk(tmp_path, monkeypatch):
    p = tmp_path / "academy.json"
    monkeypatch.setenv("SECT_ACADEMY_FILE", str(p))
    engine.enroll("testish-a1")
    engine.answer("t-01-a", "choose_l1", "hello", now=T0)
    assert p.exists()
    state._state = None                                          # simulate a restart
    assert state.get()["cards"]["t-01-a"]["reps"] == 1 and state.get()["settings"]["courses"] == ["testish-a1"]
    # A damaged file is never overwritten: it is moved aside and the backup restored.
    assert (tmp_path / "academy.json.bak").exists()
    p.write_text("{corrupt", encoding="utf-8")
    state._state = None
    assert state.get()["cards"]["t-01-a"]["reps"] == 1
    kept = list(tmp_path.glob("academy.json.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_text() == "{corrupt"
    assert "damaged" in engine.overview(now=T0)["problem"]
    # ... and with no backup either, the evidence still survives a later save.
    (tmp_path / "academy.json.bak").unlink()
    p.write_text("", encoding="utf-8")
    state._state = None
    state.last_error = ""
    assert state.get()["cards"] == {}
    engine.enroll("testish-a1")
    assert len(list(tmp_path.glob("academy.json.corrupt-*"))) == 2
    # a failed save is reported, not swallowed
    monkeypatch.setenv("SECT_ACADEMY_FILE", str(tmp_path / "missing" / "x" / "a.json"))
    monkeypatch.setattr(state.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    state._state = None
    engine.enroll("testish-a1")
    assert "could not be saved" in state.take_error()


# ---------------------------------------------------------------- review findings
def test_single_word_typo_is_forgiven_but_not_a_wrong_article():
    assert engine.check_typed("bibliotheqe", ["bibliothèque"])["flag"] == "typo"
    assert engine.check_typed("ordinateu", ["ordinateur"])["correct"]
    assert engine.check_typed("comant ça va", ["Comment ça va ?"])["correct"] is False     # two slips
    assert engine.check_typed("coment ça va", ["Comment ça va ?"])["flag"] == "typo"       # first word, not an article
    assert not engine.check_typed("le bibliothèque", ["la bibliothèque"])["correct"]
    assert not engine.check_typed("el mesa grande", ["la mesa grande"])["correct"]


def test_next_morning_review_uses_calendar_days_not_24_hours():
    engine.enroll("testish-a1")
    evening = T0 + 13 * 3600                                    # 21:00 UTC
    engine.answer("t-01-a", "choose_l1", "hello", now=evening)
    s1 = state.get()["cards"]["t-01-a"]["s"]
    engine.answer("t-01-a", "choose_l2", "bonjour", now=evening + 11 * 3600)   # 08:00 next day
    s2 = state.get()["cards"]["t-01-a"]["s"]
    assert s2 > 2 * s1                                          # long-term growth, not the same-day formula
    engine.answer("t-01-b", "choose_l1", "thank you", now=evening)
    engine.answer("t-01-b", "choose_l2", "merci", now=evening + 600)            # truly same day
    assert state.get()["cards"]["t-01-b"]["s"] < s2


def test_sessions_are_recorded_server_side():
    engine.enroll("testish-a1")
    s = engine.build_session(now=T0)
    sid = s["session"]
    ex = next(e for e in s["exercises"] if e["mode"] != "intro")
    r1 = engine.answer(ex["item"], ex["mode"], _truth(ex), session=sid, now=T0)
    card = dict(state.get()["cards"][ex["item"]])
    insight = state.get()["colony"]["insight"]
    r2 = engine.answer(ex["item"], ex["mode"], _truth(ex), session=sid, now=T0 + 5)      # replayed
    assert r1["rewards"]["qi"] > 0 and r2["rewards"] == {} and state.get()["cards"][ex["item"]] == card
    r3 = engine.answer("t-02-d", "choose_l1", "four", session=sid, now=T0)               # never issued
    assert r3["correct"] and "t-02-d" not in state.get()["cards"] and state.get()["colony"]["insight"] == insight
    assert not engine.answer(ex["item"], ex["mode"], "x", session="nope", now=T0)["ok"]
    for e in s["exercises"]:
        if e["mode"] != "intro":
            engine.answer(e["item"], e["mode"], _truth(e), session=sid, now=T0)
    f1 = engine.finish_session(session=sid, now=T0)
    f2 = engine.finish_session(session=sid, now=T0)                                      # one-shot
    assert f1["counted"] and f1["streak"] == 1 and f2["already"] and not f2["counted"]
    assert state.get()["days"][engine.day_of(state.get(), T0)]["sessions"] == 1










def test_concurrent_answers_keep_the_state_consistent():
    import threading
    engine.enroll("testish-a1")
    engine.enroll("testcert")
    s = engine.build_session(now=T0)
    todo = [e for e in s["exercises"] if e["mode"] != "intro"]
    errors = []

    def work(e):
        try:
            for _ in range(3):                                   # replays must not double-pay
                engine.answer(e["item"], e["mode"], _truth(e), session=s["session"], now=T0)
                engine.overview(now=T0)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(e,)) for e in todo]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    st = state.get()
    assert not errors and st["sessions"][s["session"]]["n"] == len(todo)
    assert st["days"][engine.day_of(st, T0)]["answers"] == len(todo)
    assert all(st["cards"][e["item"]]["reps"] == 1 for e in todo)


# ---------------------------------------------------------------- new question types
def test_multi_and_order_items_are_graded_all_or_nothing():
    idx = packs.item_index()
    multi, order = idx["c-1-m0"], idx["c-1-o0"]
    ex = engine.build_exercise(multi, "multi", packs.get("testcert"), 3)
    assert ex["pick"] == 2 and sorted(ex["choices"]) == sorted(multi["choices"])
    assert engine.check(multi, "multi", ["yes2", "yes1"])["correct"]                 # any order
    assert not engine.check(multi, "multi", ["yes1"])["correct"]                     # all of them
    assert not engine.check(multi, "multi", ["yes1", "yes2", "no1"])["correct"]      # and only them
    assert not engine.check(multi, "multi", "yes1")["correct"]
    ex = engine.build_exercise(order, "order", packs.get("testcert"), 3)
    assert ex["steps"] != order["steps"] and sorted(ex["steps"]) == sorted(order["steps"])
    assert engine.check(order, "order", ["first", "second", "third", "fourth"])["correct"]
    assert not engine.check(order, "order", ["second", "first", "third", "fourth"])["correct"]
    assert engine.check(order, "order", [])["expected"] == "first → second → third → fourth"
    engine.enroll("testcert")
    r = engine.answer("c-1-o0", "order", ["first", "second", "third", "fourth"], now=T0)
    assert r["correct"] and state.get()["cards"]["c-1-o0"]["reps"] == 1


def test_course_parts_are_merged_and_bad_parts_skipped(tmp_path):
    (tmp_path / "lang_x.yaml").write_text(textwrap.dedent("""
        part_of: testish-a1
        units:
          - id: t-03
            title: Three
            goal: I can.
            notes: More.
            items:
              - {id: t-03-a, type: vocab, l2: cinq, l1: five}
              - {id: t-03-b, type: vocab, l2: six, l1: six}
              - {id: t-03-c, type: vocab, l2: sept, l1: seven}
              - {id: t-03-d, type: vocab, l2: huit, l1: eight}
    """), encoding="utf-8")
    (tmp_path / "lang_y.yaml").write_text("part_of: testish-a1\nunits:\n  - {id: t-01, title: dup, goal: g, notes: n, items: []}\n", encoding="utf-8")
    (tmp_path / "orphan.yaml").write_text("part_of: nope\nunits: []\n", encoding="utf-8")
    packs.load_all(force=True)
    assert [u["id"] for u in packs.get("testish-a1")["units"]] == ["t-01", "t-02", "t-03"]
    assert "t-03-d" in packs.item_index() and packs.main(["lang_y.yaml"]) == 1 and packs.main(["lang_x.yaml"]) == 0


# ---------------------------------------------------------------- placement
def test_placement_finds_the_level_and_skips_what_you_know():
    engine.enroll("testish-a1")
    p = engine.placement_start("testish-a1", now=T0)
    assert p["ok"] and p["unit"] == 0 and len(p["questions"]) == 3
    assert all(q["mode"] in ("type_l2", "cloze_type") for q in p["questions"])       # typed: no lucky guesses
    r = engine.placement_answer(p["placement"], [_truth(q) for q in p["questions"]], now=T0)
    assert not r["done"] and r["passed_unit"] and r["unit"] == 1
    r = engine.placement_answer(p["placement"], ["zzz"] * len(r["questions"]), now=T0)
    assert r["done"] and r["passed_units"] == 1 and r["units"] == 2 and r["placed"] == 7 and r["start_at"] == "Two"
    st = state.get()
    assert all(st["cards"][f"t-01-{x}"]["reps"] == 1 for x in "abcdefg") and "t-02-a" not in st["cards"]
    dues = [st["cards"][f"t-01-{x}"]["due"] for x in "abcdefg"]
    assert T0 + 2 * DAY <= min(dues) and max(dues) <= T0 + 14 * DAY and len(set(dues)) > 3   # spread out, soon
    s = engine.build_session(now=T0)                                                  # study starts at unit two
    assert {e["unit"] for e in s["exercises"]} == {"t-02"}
    assert st["days"][engine.day_of(st, T0)]["new"] == 0                             # placement is not "study"
    assert engine.overview(now=T0)["placements"]["testish-a1"]["passed_units"] == 1
    assert not engine.placement_answer(p["placement"], [], now=T0)["ok"]


def test_cert_placement_samples_every_unit_and_readiness_is_strict():
    engine.enroll("testcert")
    p = engine.placement_start("testcert", now=T0)
    r = engine.placement_answer(p["placement"], ["wrong"] * 2, now=T0)               # fail unit one …
    assert not r["done"] and not r["passed_unit"]
    r = engine.placement_answer(p["placement"], [_truth(q) for q in r["questions"]], now=T0)   # … still tests unit two
    assert r["done"] and r["passed_units"] == 1 and r["start_at"] == "Unit 1"
    info = engine.trial_info("testcert", now=T0)
    assert not info["readiness"]["ready"] and len(info["readiness"]["checks"]) == 4
    assert info["full"] is None                                                       # fixture pack has no full mock
