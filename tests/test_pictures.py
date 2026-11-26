"""Picture lessons: shared pictures, per-pin cards, the three exercises, and the hold-back
of a lesson whose painting has not been made yet."""
import textwrap

import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, fsrs, packs, state
from sect_academy.app import app

T0 = 1_800_000_000.0

PIC = textwrap.dedent("""
    id: tbody
    title: The test body
    pins:
      - {id: head, x: 50, y: 10, en: head}
      - {id: arm, x: 30, y: 40, en: arm}
      - {id: hand, x: 20, y: 55, en: hand}
      - {id: knee, x: 45, y: 75, en: knee}
      - {id: foot, x: 45, y: 95, en: foot}
      - {id: back, x: 80, y: 40, en: back}
""")
PIC2 = textwrap.dedent("""
    id: tsky
    title: The test sky
    pins:
      - {id: sun, x: 10, y: 10, en: sun}
      - {id: moon, x: 90, y: 10, en: moon}
      - {id: rain, x: 50, y: 50, en: rain}
      - {id: snow, x: 70, y: 60, en: snow}
""")
LANG = textwrap.dedent("""
    id: picish
    title: Picish — Pictures
    kind: language
    language: Spanish
    lang: es-ES
    hall: tongues_south
    blurb: Pictures.
    units:
      - id: pc-01
        title: "Picture: the body"
        goal: I can name the body.
        notes: Body parts take the article.
        items:
          - id: pc-body
            type: picture
            picture: tbody
            pins:
              head: {l2: la cabeza}
              arm: {l2: el brazo}
              hand: {l2: la mano, note: Feminine.}
              knee: {l2: la rodilla}
              foot: {l2: el pie}
              back: {l2: la espalda}
      - id: pc-02
        title: "Picture: the sky"
        goal: I can name the sky.
        notes: Weather.
        items:
          - id: pc-sky
            type: picture
            picture: tsky
            pins:
              sun: {l2: el sol}
              moon: {l2: la luna}
              rain: {l2: la lluvia}
              snow: {l2: la nieve}
""")
CJK = textwrap.dedent("""
    id: cjkish
    title: CJK — Pictures
    kind: language
    language: Mandarin
    lang: zh-CN
    hall: tongues_west
    blurb: Pictures.
    units:
      - id: cj-01
        title: "Picture: the body"
        goal: I can.
        notes: Notes.
        items:
          - id: zh-body
            type: picture
            picture: tbody
            pins:
              head: {l2: 头, rom: tóu}
              arm: {l2: 胳膊, rom: gēbo, alt: [手臂, shǒubì]}
              hand: {l2: 手, rom: shǒu}
              knee: {l2: 膝盖, rom: xīgài}
          - id: ja-body
            type: picture
            picture: tsky
            pins:
              sun: {l2: たいよう, rom: taiyou, alt: [太陽, taiyō]}
              moon: {l2: つき, rom: tsuki, alt: [月]}
              rain: {l2: あめ, rom: ame}
              snow: {l2: 눈, rom: nun}
""")


@pytest.fixture(autouse=True)
def academy(tmp_path, monkeypatch):
    (tmp_path / "pictures").mkdir()
    (tmp_path / "pictures" / "tbody.yaml").write_text(PIC, encoding="utf-8")
    (tmp_path / "pictures" / "tsky.yaml").write_text(PIC2, encoding="utf-8")
    (tmp_path / "lang.yaml").write_text(LANG, encoding="utf-8")
    (tmp_path / "cjk.yaml").write_text(CJK, encoding="utf-8")
    art = tmp_path / "art"
    art.mkdir()
    (art / "pic_tbody.webp").write_bytes(b"RIFF....WEBP")          # the body is painted; the sky is not
    (art / "pic_tsky.webp").write_bytes(b"RIFF....WEBP")
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.setattr(packs, "PACK_DIR", tmp_path)
    monkeypatch.setattr(packs, "ART_DIR", art)
    packs.load_all(force=True)
    state.reset_for_tests()
    yield art
    monkeypatch.undo()
    packs.load_all(force=True)
    state.reset_for_tests()


def _reload():
    packs.load_all(force=True)


# ---------------------------------------------------------------- schema
def test_pins_become_items_with_stable_ids():
    p = packs.get("picish")
    ids = [it["id"] for it in p["units"][0]["items"]]
    assert ids == ["pc-body-head", "pc-body-arm", "pc-body-hand", "pc-body-knee", "pc-body-foot", "pc-body-back"]
    hand = packs.item_index()["pc-body-hand"]
    assert hand["type"] == "pin" and hand["l2"] == "la mano" and hand["l1"] == "hand" and hand["n"] == 3
    assert (hand["x"], hand["y"], hand["picture"], hand["group"], hand["note"]) == (20.0, 55.0, "tbody", "pc-body", "Feminine.")
    # a subset of a picture's pins is allowed: numbers follow the picture's order
    assert [it["n"] for it in packs.get("cjkish")["units"][0]["items"] if it["group"] == "zh-body"] == [1, 2, 3, 4]


def test_the_shipped_pictures_and_pin_ids_never_change():
    """Pin ids are progress keys: <item id>-<pin id>. Renaming one loses the learner's cards."""
    real = packs.Path(packs.__file__).parent / "packs"
    pics = {p.stem: [q["id"] for q in packs._read(p)["pins"]] for p in sorted((real / "pictures").glob("*.yaml"))}
    assert pics == {
        "body": ["head", "neck", "shoulder", "arm", "elbow", "hand", "finger", "chest", "stomach", "back", "leg", "knee", "foot", "toe"],
        "skeleton": ["skull", "collarbone", "breastbone", "ribs", "spine", "pelvis", "thighbone", "kneecap", "shinbone"],
        "face": ["hair", "forehead", "eyebrow", "eye", "ear", "nose", "cheek", "mouth", "teeth", "tongue", "chin"],
        "house": ["roof", "chimney", "bedroom", "bathroom", "window", "stairs", "living_room", "kitchen", "door", "garden"],
        "kitchen": ["fridge", "stove", "sink", "chair", "table", "fork", "plate", "knife", "spoon", "cup"],
        "clothes": ["hat", "scarf", "shirt", "jacket", "belt", "trousers", "shoes", "gloves", "skirt", "socks"],
        "town": ["bank", "hospital", "school", "station", "shop", "restaurant", "park", "traffic_light", "bus_stop", "crosswalk"],
        "classroom": ["clock", "blackboard", "teacher", "window", "student", "book", "pen", "pencil", "desk", "bag"],
        "meal": ["bread", "rice", "fish", "meat", "egg", "apple", "vegetables", "soup", "water", "tea"],
        "sky": ["sun", "cloud", "rainbow", "lightning", "rain", "wind", "star", "moon", "snow"],
    }
    for lang, prefix in (("spanish", "es"), ("french", "fr"), ("mandarin", "zh"), ("japanese", "ja"), ("korean", "ko")):
        pack = packs._read(real / f"{lang}_pictures.yaml")
        items = [it for u in pack["units"] for it in u["items"]]
        order = ["body", "skeleton", "face", "house", "kitchen", "clothes", "town", "classroom", "meal", "sky"]
        assert [it["id"] for it in items] == [f"{prefix}-pic-{p}" for p in order], lang
        for it in items:
            assert set(it["pins"]) <= set(pics[it["picture"]]) and len(it["pins"]) >= 8, it["id"]


def test_bad_pictures_and_picture_items_are_refused():
    assert packs.validate_picture({"id": "x", "title": "t", "pins": []})                    # id too short, no pins
    errs = "\n".join(packs.validate_picture({"id": "bad", "title": "T", "extra": 1, "pins": [
        {"id": "a", "x": 10, "y": 10, "en": "a"}, {"id": "a", "x": 10, "y": 10, "en": "a"},
        {"id": "b", "x": 101, "y": 10, "en": "b"}, {"id": "c", "x": True, "y": 10, "en": "c"},
        {"id": "d", "x": 5, "y": -1, "en": ""}, {"id": "../e", "x": 5, "y": 5, "en": "e"}]}))
    for bit in ("unknown keys", "duplicate pin id 'a'", "pin b: x and y", "pin c: x and y", "pin d: needs en", "'../e'"):
        assert bit in errs, bit

    def pack(items, kind="language"):
        p = {"id": "bad-pics", "title": "t", "blurb": "b", "hall": "h", "kind": kind, "language": "L", "lang": "fr-FR",
             "units": [{"id": "u1", "title": "t", "goal": "g", "notes": "n", "items": items}]}
        if kind == "cert":
            p["exam"] = {"name": "n", "code": "c", "questions": 1, "minutes": 1, "pass_pct": 80,
                         "domains": [{"id": "1", "title": "d", "weight": 100}]}
            p["units"][0]["domain"] = "1"
        return "\n".join(packs.validate_pack(p))

    four = {"head": {"l2": "a"}, "arm": {"l2": "b"}, "hand": {"l2": "c"}, "knee": {"l2": "d"}}
    assert pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": four}]) == ""
    assert "not defined" in pack([{"id": "p1", "type": "picture", "picture": "../../etc", "pins": four}])
    assert "not a pin of picture" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {**four, "tail": {"l2": "e"}}}])
    assert "at least 4" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {"head": {"l2": "a"}}}])
    assert "used by another pin" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {**four, "foot": {"l2": "A"}}}])
    assert "rom is required" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {**four, "foot": {"l2": "脚"}}}])
    assert "unknown keys" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {**four, "foot": {"l2": "e", "x": 3}}}])
    assert "alt must be" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": {**four, "foot": {"l2": "e", "alt": "e"}}}])
    assert "belong in language packs" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": four}], kind="cert")
    # a pin's item id may not collide with another item
    assert "'p1-head'" in pack([{"id": "p1", "type": "picture", "picture": "tbody", "pins": four},
                                   {"id": "p1-head", "type": "vocab", "l2": "x", "l1": "y"}])


# ---------------------------------------------------------------- painting missing
def test_a_lesson_waits_for_its_painting(academy):
    (academy / "pic_tsky.webp").unlink()
    _reload()
    p = packs.get("picish")
    assert [u["id"] for u in p["units"]] == ["pc-01"]
    assert p["soon"] == [{"id": "pc-02", "title": "Picture: the sky", "goal": "I can name the sky.", "pictures": ["tsky"]}]
    assert "pc-sky-sun" not in packs.item_index()
    stats = engine.courses(T0)
    me = next(c for c in stats if c["id"] == "picish")
    assert me["total"] == 6 and me["soon"][0]["title"] == "Picture: the sky"
    # a course with nothing painted has no units, cannot be placement-tested, and nothing asks for an image
    (academy / "pic_tbody.webp").unlink()
    _reload()
    assert packs.get("picish")["units"] == [] and len(packs.get("picish")["soon"]) == 2
    engine.enroll("picish")
    assert engine.placement_start("picish")["ok"] is False
    s = engine.build_session("picish", now=T0)
    assert s["exercises"] == []
    assert not packs.painted("../tbody") and not packs.painted("nope")


def test_shipped_lessons_are_shown_only_with_their_painting(monkeypatch):
    real = packs.Path(packs.__file__).parent
    monkeypatch.setattr(packs, "PACK_DIR", real / "packs")
    monkeypatch.setattr(packs, "ART_DIR", real / "static" / "art")
    packs.load_all(force=True)
    for pid in ("spanish-pictures", "french-pictures", "mandarin-pictures", "japanese-pictures", "korean-pictures"):
        p = packs.get(pid)
        assert len(p["units"]) + len(p["soon"]) == 10
        for u in p["soon"]:
            assert not any(packs.painted(x) for x in u["pictures"])
        for u in p["units"]:
            assert all(packs.painted(it["picture"]) for it in u["items"] if it["type"] == "pin")


# ---------------------------------------------------------------- the drag exercise
def _session():
    engine.enroll("picish")
    return engine.build_session("picish", now=T0)


def test_new_pins_are_one_drag_exercise_but_each_pin_is_its_own_card():
    s = _session()
    modes = [e["mode"] for e in s["exercises"]]
    assert modes == ["intro", "pic_drag"]                                # one picture intro, one exercise
    intro, drag = s["exercises"]
    assert intro["card"]["type"] == "picture" and len(intro["card"]["pins"]) == 6
    assert drag["picture"] == {"id": "tbody", "src": "/art/pic_tbody.webp", "title": "The test body"}
    assert [p["item"] for p in drag["pins"]] == [f"pc-body-{q}" for q in ("head", "arm", "hand", "knee", "foot", "back")]
    assert sorted(c["l2"] for c in drag["chips"]) == sorted(packs.item_index()[p["item"]]["l2"] for p in drag["pins"])
    rec = state.get()["sessions"][s["session"]]
    assert sorted(rec["items"]) == sorted(p["item"] for p in drag["pins"])   # every pin issued, the intro not

    placements = [{"item": p["item"], "answer": packs.item_index()[p["item"]]["l2"]} for p in drag["pins"]]
    placements[1]["answer"] = "la mano"                                  # arm and hand swapped
    placements[2]["answer"] = "el brazo"
    res = engine.answer_picture(placements, session=s["session"], now=T0 + 60)
    assert res["ok"] and (res["right"], res["total"]) == (4, 6) and not res["correct"]
    assert res["rewards"]["insight"] == 4                                # paid per pin, like any item
    assert [r["correct"] for r in res["pins"]] == [True, False, False, True, True, True]
    assert res["pins"][1]["expected"] == "el brazo" and res["pins"][1]["explain"]["pin"]["n"] == 2
    cards = state.get()["cards"]
    assert all(cards[p["item"]]["reps"] == 1 for p in drag["pins"])
    assert cards["pc-body-arm"]["lapses"] == 0 and cards["pc-body-arm"]["due"] < cards["pc-body-head"]["due"]
    assert set(state.get()["mistakes"]) == {"pc-body-arm", "pc-body-hand"}
    # the same answers again (a retry, or a replay) schedule and pay nothing
    before = {k: dict(v) for k, v in cards.items()}
    again = engine.answer_picture(placements, session=s["session"], now=T0 + 120)
    assert again["ok"] and again["rewards"]["insight"] == 0 and state.get()["cards"] == before
    # a pin this session did not issue is graded, never scheduled or paid
    other = engine.answer_picture([{"item": "pc-sky-sun", "answer": "el sol"}], session=s["session"], now=T0 + 130)
    assert other["ok"] and other["correct"] and other["rewards"]["qi"] == 0 and "pc-sky-sun" not in state.get()["cards"]
    assert engine._day(state.get(), T0)["answers"] == 6
    fin = engine.finish_session(session=s["session"], now=T0 + 200)
    assert fin["ok"]


def test_drag_answers_are_scheduled_exactly_like_single_answers():
    """Six pins through answer_picture leave the same cards as six one-by-one answers."""
    s = _session()
    drag = s["exercises"][1]
    placements = [{"item": p["item"], "answer": packs.item_index()[p["item"]]["l2"]} for p in drag["pins"]]
    engine.answer_picture(placements, session=s["session"], now=T0 + 60)
    via_picture = {k: (v["s"], v["d"], v["due"]) for k, v in state.get()["cards"].items()}
    state.reset_for_tests()
    s = _session()
    for p in placements:
        r = engine.answer(p["item"], "pic_drag", p["answer"], session=s["session"], now=T0 + 60)
        assert r["ok"] and r["correct"]
    assert {k: (v["s"], v["d"], v["due"]) for k, v in state.get()["cards"].items()} == via_picture


def test_hostile_picture_answers():
    s = _session()
    drag = s["exercises"][1]
    one = {"item": drag["pins"][0]["item"], "answer": "la cabeza"}
    bad = [
        [], [one] * 2, [{"item": "pc-body-head"}] * 17, ["pc-body-head"], [{"item": 5}],
        [{"item": "../../etc/passwd", "answer": "x"}], [{"item": "pc-sky-sun", "answer": "el sol"}, one],
        [{"item": "t-01-a", "answer": "x"}],
    ]
    for b in bad:
        assert engine.answer_picture(b, session=s["session"], now=T0)["ok"] is False, b
    assert engine.answer_picture([one], session="nope", now=T0)["ok"] is False
    r = engine.answer_picture([{"item": one["item"], "answer": ["la cabeza"]}], session=s["session"], now=T0)
    assert r["ok"] and not r["correct"]                                  # a list is not an answer
    r = engine.answer_picture([{"item": drag["pins"][1]["item"], "answer": "x" * 5000}], session=s["session"], now=T0)
    assert r["ok"] and len(r["pins"][0]["given"]) <= 200
    assert not state.get()["cards"].get(drag["pins"][2]["item"])        # nothing else was touched
    # through HTTP
    client = TestClient(app)
    for body in ({"session": s["session"], "pins": [{"item": "pc-body-knee", "answer": 3}]},
                 {"session": s["session"], "pins": "x"}, {"pins": []}):
        assert client.post("/api/answer/picture", json=body).status_code == 422
    assert client.post("/api/answer/picture", json={"session": s["session"], "pins": []}).status_code == 400
    r = client.post("/api/answer/picture", json={"session": s["session"], "pins": [{"item": "pc-body-knee", "answer": "la rodilla"}]})
    assert r.status_code == 200 and r.json()["correct"]
    assert client.get("/pictures.js").status_code == 200


# ---------------------------------------------------------------- tap and typed
def _met(iid, reps):
    card = fsrs.new_card()
    for _ in range(reps):
        card = fsrs.review(card, fsrs.GOOD, T0 - 30 * 86400)
    card["due"] = T0 - 3600
    card["seen"] = T0 - 30 * 86400
    state.get()["cards"][iid] = card


def test_tap_the_word_names_a_pin_by_number_only():
    it = packs.item_index()["pc-body-knee"]
    assert engine._mode_for(it, {"reps": 1}, packs.get("picish")) == "pic_tap"
    ex = engine.build_exercise(it, "pic_tap", packs.get("picish"))
    assert ex["prompt"] == "la rodilla" and [p["n"] for p in ex["pins"]] == [1, 2, 3, 4, 5, 6]
    others = {o["l2"] for o in packs.get("picish")["units"][0]["items"]} - {"la rodilla"}
    assert not any(w in str(ex) for w in others)                         # the other words are not given away
    assert engine.check(it, "pic_tap", "4")["correct"] and not engine.check(it, "pic_tap", "3")["correct"]
    assert not engine.check(it, "pic_tap", ["4"])["correct"]
    # in a real session, a pin met once comes back as a tap, scheduled once
    engine.enroll("picish")
    for q in ("head", "arm", "hand", "knee", "foot", "back"):
        _met(f"pc-body-{q}", 1)
    s = engine.build_session("picish", now=T0)
    taps = [e for e in s["exercises"] if e["mode"] == "pic_tap"]
    assert len(taps) == 6 and all(e["picture"]["src"] == "/art/pic_tbody.webp" for e in taps)
    knee = next(e for e in taps if e["item"] == "pc-body-knee")
    r = engine.answer("pc-body-knee", "pic_tap", "4", session=s["session"], now=T0 + 5)
    assert r["correct"] and r["explain"]["pin"] == {"n": 4, "x": 45.0, "y": 75.0} and r["rewards"]["qi"] > 0
    assert engine.answer("pc-body-knee", "pic_tap", "4", session=s["session"], now=T0 + 6)["rewards"] == {}
    assert knee["say"] == "la rodilla"


def test_typed_pins_light_one_pin_and_grade_like_any_typed_answer():
    it = packs.item_index()["pc-body-knee"]
    pack = packs.get("picish")
    assert engine._mode_for(it, {"reps": 2}, pack) == "type_l2"
    ex = engine.build_exercise(it, "type_l2", pack)
    assert ex["pins"] == [{"n": 4, "x": 45.0, "y": 75.0, "lit": True}] and ex["picture"]["id"] == "tbody"
    assert ex["prompt"] == "knee" and "article" in ex["sub"]
    assert engine.check(it, "type_l2", "la rodilla")["correct"]
    assert engine.check(it, "type_l2", "La rodilla.")["correct"]
    assert not engine.check(it, "type_l2", "el rodilla")["correct"]       # the article is the thing learned
    assert engine.check(it, "type_l2", "la rodila")["flag"] == "typo"
    back = packs.item_index()["pc-body-back"]
    assert engine.check(back, "type_l2", "la espalda")["correct"]
    # CJK: script or romanisation, tone numbers, alt spelled in the script
    zh = packs.item_index()["zh-body-arm"]
    for typed in ("胳膊", "gēbo", "ge1bo", "手臂", "shǒubì", "shou3bi4"):
        assert engine.check(zh, "type_l2", typed)["correct"], typed
    assert not engine.check(zh, "type_l2", "ge2bo")["correct"]
    ja = packs.item_index()["ja-body-sun"]
    for typed in ("たいよう", "太陽", "taiyou", "taiyō"):
        assert engine.check(ja, "type_l2", typed)["correct"], typed
    assert engine.check(ja, "type_l2", "taiyo")["flag"] == "tone"        # a missing macron is a slip, as in the courses
    ko = packs.item_index()["ja-body-snow"]
    assert engine.check(ko, "type_l2", "눈")["correct"] and engine.check(ko, "type_l2", "nun")["correct"]
    # trials, placement and the mistakes session ask a pin typed, with its picture
    assert engine._typed_mode(it, __import__("random").Random(1)) == "type_l2"
    engine.enroll("picish")
    pl = engine.placement_start("picish")
    assert pl["ok"] and {q["mode"] for q in pl["questions"]} == {"type_l2"} and all(q["picture"] for q in pl["questions"])


def test_drag_check_takes_the_exact_word():
    it = packs.item_index()["pc-body-hand"]
    assert engine.check(it, "pic_drag", "la mano")["correct"]
    assert not engine.check(it, "pic_drag", "el brazo")["correct"]
    assert engine.check(it, "choose_l1", "hand").get("error") == "bad mode"
