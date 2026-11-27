"""Handwriting: stroke data coverage, the stroke matcher, and server-side grading of written glyphs."""
import json
import math
import random
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, fsrs, hand, hangul, packs, state
from sect_academy.app import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    packs.load_all(force=True)
    state.reset_for_tests()
    yield
    state.reset_for_tests()


def glyph_items():
    for p in packs.load_all().values():
        for u in p["units"]:
            for it in u["items"]:
                if it["type"] == "glyph":
                    yield p, it


def all_chars():
    return sorted({(c, p["lang"].split("-")[0]) for p, it in glyph_items() for c in it["l2"]})


def flat(strokes, scale=1.0, jitter=0.0, dx=0.0, dy=0.0, rng=None):
    rng = rng or random.Random(0)
    return [[v for x, y in s for v in (0.5 + (x - 0.5) * scale + dx + rng.gauss(0, jitter),
                                      0.5 + (y - 0.5) * scale + dy + rng.gauss(0, jitter))] for s in strokes]


def written(text, lang, **kw):
    return {"chars": [flat(hand.char_strokes(c, lang), **kw) for c in text]}


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def test_every_glyph_in_the_courses_has_stroke_data():
    items = list(glyph_items())
    assert len(items) > 350
    missing = [it["id"] for p, it in items if not hand.can_write(it["l2"], p["lang"])]
    assert not missing, f"no strokes for {missing} (rebuild: python scripts/build_strokes.py)"
    # all kana are shipped, not only those in glyph items
    for c in "あをんゃっアヲンャッー":
        assert hand.char_strokes(c, "ja"), c


def test_stroke_counts_are_the_standard_ones():
    counts = {("あ", "ja"): 3, ("ア", "ja"): 2, ("学", "ja"): 8, ("你", "zh"): 7, ("国", "zh"): 8, ("我", "zh"): 7,
              ("ㄱ", "ko"): 1, ("ㄹ", "ko"): 3, ("ㅎ", "ko"): 3, ("가", "ko"): 3, ("값", "ko"): 9, ("닭", "ko"): 8,
              ("꽃", "ko"): 7, ("ㅘ", "ko"): 4, ("ㅙ", "ko"): 5}
    for (c, lg), n in counts.items():
        assert len(hand.char_strokes(c, lg)) == n, c


def test_hangul_composes_every_syllable_and_jamo():
    for code in range(0xAC00, 0xD7A4, 97):
        s = hangul.syllable(chr(code))
        assert s and all(0 <= x <= 1 and 0 <= y <= 1 for st in s for x, y in st)
    for j in hangul.LEADS + hangul.VOWELS + "".join(hangul.TAILS):
        assert hangul.syllable(j), j
    assert hangul.syllable("A") is None


def test_licences_and_sources_are_recorded():
    ja = json.loads((ROOT / "sect_academy/strokes/ja/kanjivg.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "sect_academy/strokes/zh/makemeahanzi.json").read_text(encoding="utf-8"))
    assert "CC BY-SA 3.0" in ja["licence"] and "KanjiVG" in ja["source"]
    assert "Arphic Public License" in zh["licence"] and "MODIFIED FILE" in zh["notice"]
    assert (ROOT / "sect_academy/strokes/zh/ARPHICPL.TXT").read_text(encoding="utf-8").startswith("ARPHIC PUBLIC LICENSE")
    for lg in ("ja", "zh"):
        readme = (ROOT / f"sect_academy/strokes/{lg}/README.md").read_text(encoding="utf-8")
        assert "Licence" in readme
    assert "KanjiVG" in hand.credit("ja-JP") and "Arphic" in hand.credit("zh-CN")


# ---------------------------------------------------------------------------
# the matcher
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("scale,jitter", [(1.0, 0.0), (0.9, 0.01), (1.08, 0.01), (0.95, 0.015)])
def test_matcher_accepts_the_reference_and_near_copies(scale, jitter):
    rng = random.Random(7)
    bad = []
    for c, lg in all_chars():
        s = hand.char_strokes(c, lg)
        r = hand.grade_char(s, flat(s, scale, jitter, rng=rng))
        if not r["done"] or r["mistakes"]:
            bad.append((c, r["why"]))
    assert not bad


def test_matcher_rejects_wrong_order():
    for c, lg in all_chars():
        s = hand.char_strokes(c, lg)
        for i in range(len(s) - 1):
            att = flat(s)
            att[i], att[i + 1] = att[i + 1], att[i]
            assert hand.grade_char(s, att)["mistakes"] >= 1, (c, i)


def test_matcher_rejects_reversed_strokes():
    for c, lg in all_chars():
        s = hand.char_strokes(c, lg)
        for i, st in enumerate(s):
            if math.dist(st[0], st[-1]) < 0.15:
                continue                       # loops and ticks: checked by shape, tested below
            att = flat(s)
            att[i] = flat([st[::-1]])[0]
            assert hand.grade_char(s, att)["mistakes"] >= 1, (c, i)
    ring = hand.char_strokes("ㅇ", "ko")        # a loop drawn the wrong way round
    assert not hand.compare(ring[0][::-1], ring[0])["ok"]


def test_matcher_needs_every_stroke():
    s = hand.char_strokes("国", "zh")
    r = hand.grade_char(s, flat(s)[:-1])
    assert not r["done"] and r["matched"] == len(s) - 1


def test_check_grades_a_whole_glyph():
    it = packs.item_index()["zh1-01-g-ni"]
    good = hand.check(it, written("你", "zh"), "zh-CN")
    assert good["correct"] and good["flag"] is None
    assisted = hand.check(it, {**written("你", "zh"), "assisted": True}, "zh-CN")
    assert assisted["correct"] and assisted["flag"] == "slips"
    s = hand.char_strokes("你", "zh")
    one_slip = flat(s)
    one_slip.insert(2, [0.1, 0.9, 0.2, 0.95])  # a stray stroke, then the right one
    r = hand.check(it, {"chars": [one_slip]}, "zh-CN")
    assert r["correct"] and r["flag"] == "slips" and r["chars"][0]["mistakes"] == 1
    many = [[0.1, 0.9, 0.2, 0.95]] * 5 + flat(s)
    assert not hand.check(it, {"chars": [many]}, "zh-CN")["correct"]
    assert not hand.check(it, written("好", "zh"), "zh-CN")["correct"]       # the wrong character
    assert not hand.check(it, {"chars": []}, "zh-CN")["correct"]


def test_two_character_glyph_is_written_one_after_the_other():
    it = packs.item_index()["ja1-05-kya"]
    assert hand.check(it, written("きゃ", "ja"), "ja-JP")["correct"]
    assert not hand.check(it, written("き", "ja"), "ja-JP")["correct"]


@pytest.mark.parametrize("junk", [None, "x", 5, [], {"chars": "x"}, {"chars": [["a", "b"]]}, {"chars": [[[1, 2, 3]]]},
                                  {"chars": [[[float("nan"), 0.1, 0.2, 0.3]]]}, {"chars": [[[float("inf")] * 8]]},
                                  {"chars": [[[True, False, True, False]]]}, {"chars": [[[1e300, -1e300, 5, 5]]]}])
def test_hostile_strokes_are_wrong_not_errors(junk):
    it = packs.item_index()["zh1-01-g-ni"]
    r = hand.check(it, junk, "zh-CN")
    assert r["correct"] is False


def test_huge_point_lists_are_cut_down_quickly():
    it = packs.item_index()["zh1-01-g-ni"]
    big = [[0.5] * 200_000] * hand.MAX_ATTEMPTS * 3
    t = time.time()
    r = hand.check(it, {"chars": [big] * 20}, "zh-CN")
    assert not r["correct"] and time.time() - t < 5
    assert len(hand.clean_stroke([0.3, 0.4] * 50_000)) <= hand.MAX_POINTS + 1


# ---------------------------------------------------------------------------
# the study flow
# ---------------------------------------------------------------------------
def test_mode_is_offered_once_the_glyph_is_known_and_can_be_turned_off():
    pack = packs.get("mandarin-a1")
    it = packs.item_index()["zh1-01-g-ni"]
    assert engine._mode_for(it, {"reps": 1, "s": 9.0}, pack) == "glyph_pick"
    assert engine._mode_for(it, {"reps": 3, "s": 1.0}, pack) == "glyph_type"        # not known well enough
    assert engine._mode_for(it, {"reps": 3, "s": 9.0}, pack) == "glyph_write"
    assert engine._mode_for(it, {"reps": 4, "s": 9.0}, pack) == "glyph_type"        # mixed with typing
    engine.set_settings({"handwriting": False})
    assert engine._mode_for(it, {"reps": 3, "s": 9.0}, pack) == "glyph_type"
    assert state.clean_settings({"handwriting": "yes"})["handwriting"] is True
    assert client.put("/api/settings", json={"handwriting": False}).json()["handwriting"] is False


def _known(item_id, now):
    st = state.get()
    st["cards"][item_id] = {"s": 9.0, "d": 5.0, "due": now - 60, "last": now - 9 * fsrs.DAY, "reps": 3, "lapses": 0}


def test_a_session_issues_glyph_write_and_the_server_grades_it():
    now = time.time()
    engine.enroll("mandarin-a1", True)
    _known("zh1-01-g-ni", now)
    s = engine.build_session("mandarin-a1", now=now)
    ex = next(e for e in s["exercises"] if e["item"] == "zh1-01-g-ni")
    assert ex["mode"] == "glyph_write" and ex["prompt"] == "nǐ" and len(ex["chars"]) == 1
    assert len(ex["chars"][0]["m"]) == 7 and len(ex["chars"][0]["o"]) == 7 and "Arphic" in ex["credit"]
    before = dict(state.get()["cards"]["zh1-01-g-ni"])
    r = client.post("/api/answer/write", json={"session": s["session"], "item": "zh1-01-g-ni", **written("你", "zh")}).json()
    assert r["correct"] and r["flag"] is None and r["explain"]["l2"] == "你"
    after = state.get()["cards"]["zh1-01-g-ni"]
    assert after["reps"] == before["reps"] + 1 and after["s"] > before["s"]
    # a second answer in the same session is feedback only
    r2 = client.post("/api/answer/write", json={"session": s["session"], "item": "zh1-01-g-ni", "chars": []}).json()
    assert r2["correct"] is False and state.get()["cards"]["zh1-01-g-ni"]["reps"] == after["reps"]


def test_items_the_session_did_not_issue_are_not_scheduled():
    now = time.time()
    engine.enroll("mandarin-a1", True)
    s = engine.build_session("mandarin-a1", now=now)
    issued = {e["item"] for e in s["exercises"]}
    other = next(it["id"] for p, it in glyph_items() if p["id"] == "mandarin-a1" and it["id"] not in issued)
    r = client.post("/api/answer/write", json={"session": s["session"], "item": other, **written(packs.item_index()[other]["l2"], "zh")}).json()
    assert r["correct"] and other not in state.get()["cards"]
    assert client.post("/api/answer/write", json={"session": "nope", "item": other, "chars": []}).status_code == 400


def test_a_wrong_order_attempt_is_wrong_and_scheduled_again():
    now = time.time()
    engine.enroll("mandarin-a1", True)
    _known("zh1-01-g-ren", now)
    s = engine.build_session("mandarin-a1", now=now)
    strokes = flat(hand.char_strokes("人", "zh"))
    r = client.post("/api/answer/write", json={"session": s["session"], "item": "zh1-01-g-ren", "chars": [strokes[::-1]]}).json()
    assert r["correct"] is False
    assert state.get()["cards"]["zh1-01-g-ren"]["lapses"] == 1
    assert state.get()["mistakes"]["zh1-01-g-ren"]["given"] == "(handwriting)"


def test_self_check_is_hard_at_best():
    now = time.time()
    engine.enroll("korean-a1", True)
    ids = [it["id"] for p, it in glyph_items() if p["id"] == "korean-a1"][:2]
    for i in ids:
        _known(i, now)
    s = engine.build_session("korean-a1", now=now)
    a = client.post("/api/answer", json={"session": s["session"], "item": ids[0], "mode": "glyph_self", "answer": "right"}).json()
    b = client.post("/api/answer/write", json={"session": s["session"], "item": ids[1],
                                               **written(packs.item_index()[ids[1]]["l2"], "ko")}).json()
    assert a["correct"] and a["flag"] == "self" and b["correct"] and b["flag"] is None
    cards = state.get()["cards"]
    assert cards[ids[0]]["s"] < cards[ids[1]]["s"]          # Hard grows memory less than Good
    w = client.post("/api/answer", json={"session": s["session"], "item": ids[0], "mode": "glyph_self", "answer": "wrong"}).json()
    assert w["correct"] is False


def test_hostile_requests_over_http():
    now = time.time()
    engine.enroll("japanese-a1", True)
    _known("ja1-01-a", now) if "ja1-01-a" in packs.item_index() else None
    s = engine.build_session("japanese-a1", now=now)
    item = next(it["id"] for p, it in glyph_items() if p["id"] == "japanese-a1")
    body = '{"session": "%s", "item": "%s", "chars": [[[NaN, 0.1, Infinity, 0.2]]]}' % (s["session"], item)
    r = client.post("/api/answer/write", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 200 and r.json()["correct"] is False
    r = client.post("/api/answer/write", json={"session": s["session"], "item": item, "chars": [[[0.5] * 20_000] * 100]})
    assert r.status_code == 200 and r.json()["correct"] is False
    r = client.post("/api/answer/write", json={"session": s["session"], "item": "fr1-01-bonjour", "chars": []})
    assert r.status_code == 400                               # not a glyph: glyph_write is a bad mode for it


def test_handwriting_page_is_served_and_offline():
    r = client.get("/handwriting.js")
    assert r.status_code == 200 and "writeExercise" in r.text
    body = r.text.replace("http://www.w3.org/", "")
    assert "http://" not in body and "https://" not in body
    assert "'/handwriting.js'" in client.get("/sw.js").text


def test_js_matcher_constants_match_python():
    js = (ROOT / "sect_academy/static/handwriting.js").read_text(encoding="utf-8")
    for name, val in (("samples", hand.SAMPLES), ("end", hand.END_TOL), ("mean", hand.MEAN_TOL), ("lenLo", hand.LEN_LO),
                      ("lenHi", hand.LEN_HI), ("minLen", hand.MIN_LEN), ("dirCos", hand.DIR_COS), ("dirLong", hand.DIR_LONG),
                      ("dirShort", hand.DIR_SHORT), ("better", hand.BETTER), ("margin", hand.MARGIN), ("orderFloor", hand.ORDER_FLOOR)):
        assert f"{name}: {val}" in js, name
