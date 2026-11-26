"""Mandarin and Japanese lookup: segmenting unspaced text, readings, conjugations, search, My words."""
import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, lexicon, packs, reader, state
from sect_academy.app import app
from sect_academy.lexicon import cjk, ja, ja_rules, zh

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    state.reset_for_tests()
    reader.reset_for_tests()
    packs.load_all()                  # cached: the YAML courses do not change between these tests
    yield
    state.reset_for_tests()
    reader.reset_for_tests()


def words(lang, text):
    r = client.post("/api/dict/segment", json={"lang": lang, "text": text}).json()
    assert r["available"] and "".join(t["t"] for t in r["tokens"]) == text
    return [t["t"] for t in r["tokens"] if t["k"]]


def look(w, lang, **kw):
    return client.get("/api/dict", params={"w": w, "lang": lang, **kw}).json()


def test_registered_with_the_contract():
    assert {"zh", "ja"} <= set(client.get("/api/dict/langs").json()["lookup"])
    for code in ("zh", "ja"):
        mod = lexicon.get(code)
        for name in ("LANG", "NAME", "SPEECH", "CREDIT", "norm_word", "lookup", "search", "segment", "romanise"):
            assert hasattr(mod, name), (code, name)
    assert zh.SPEECH == "zh-CN" and ja.SPEECH == "ja-JP"
    assert "CC-CEDICT" in zh.CREDIT and "CC BY-SA" in zh.CREDIT
    assert "JMdict" in ja.CREDIT and "Electronic Dictionary Research and Development Group" in ja.CREDIT
    assert "https://www.edrdg.org/edrdg/licence.html" in ja.CREDIT


# ---------------------------------------------------------------- Mandarin
@pytest.mark.parametrize("text,want", [
    ("我喜欢学习中文", ["我", "喜欢", "学习", "中文"]),
    ("你好吗？", ["你好", "吗"]),
    ("他们在图书馆。", ["他们", "在", "图书馆"]),
    ("我们已经学了三年中文了。", ["我们", "已经", "学", "了", "三", "年", "中文", "了"]),
    ("研究生命的起源", ["研究", "生命", "的", "起源"]),
    ("他今年四十五岁。", ["他", "今年", "四十五", "岁"]),
    ("我在2024年买了iPhone。", ["我", "在", "2024", "年", "买", "了", "iPhone"]),
])
def test_chinese_segmentation(text, want):
    r = client.post("/api/dict/segment", json={"lang": "zh", "text": text}).json()
    toks = [t["t"] for t in r["tokens"] if cjk.kind(t["t"][0])]
    assert toks == want
    assert [t["k"] for t in r["tokens"] if t["t"] == "2024"] in ([], [None])          # a number is not looked up


def test_chinese_lookup_pinyin_and_traditional():
    r = look("学习", "zh")
    assert r["found"] and r["reading"] == "xuéxí" and r["senses"][0]["read"] == "xuéxí"
    assert "study" in r["senses"][0]["text"] and r["forms"] == ["學習"]
    assert {a["lemma"] for a in r["also"] if a["how"] == "character"} == {"学", "习"}
    t = look("學習", "zh")
    assert t["found"] and t["reading"] == "xuéxí" and t["forms"] == ["学习"]
    assert words("zh", "學習中文") == ["學習", "中文"]
    # several readings: the usual one first, all shown
    de = look("的", "zh")
    assert de["senses"][0]["read"] == "de" and len(de["senses"]) > 1
    assert look("了", "zh")["senses"][0]["read"] == "le"
    assert zh.pinyin_marks("Xi1 an1") == "Xī'ān" and zh.pinyin_marks("lv4 se4") == "lǜsè" and zh.mark_syllable("r5") == "r"


def test_chinese_longer_compound_and_variants():
    r = look("图书", "zh", post="馆里")
    assert r["also"][0]["lemma"] == "图书馆" and r["also"][0]["how"] == "compound"
    v = zh.lookup("着")
    assert v["found"] and not v["weak"] and v["senses"][0]["read"] == "zhe"         # its own entries are all "variant of 著"
    assert look("四十五", "zh")["senses"][0]["text"].startswith("45")


@pytest.mark.parametrize("q", ["xue2xi2", "xuéxí", "xuexi", "xue2 xi2", "Xué xí"])
def test_chinese_search_by_pinyin(q):
    r = client.get("/api/dict/search", params={"q": q, "lang": "zh"}).json()
    assert r["results"][0]["w"] == "学习" and r["results"][0]["read"] == "xuéxí"


def test_chinese_search_by_tone_keeps_the_tone():
    got = [x["w"] for x in zh.search("xue4")]
    assert "血" in got[:3] and "学" not in got
    assert zh.search("学")[0]["w"] == "学" and any(x["w"] == "学习" for x in zh.search("学"))


@pytest.mark.parametrize("q,first", [("library", "图书馆"), ("you", "你"), ("I", "我"), ("eat", "吃"), ("house", "房")])
def test_english_to_chinese(q, first):
    got = [x["w"] for x in client.get("/api/dict/search", params={"q": q, "lang": "zh", "dir": "en"}).json()["results"]]
    assert first in got[:3], got[:6]


# ---------------------------------------------------------------- Japanese
@pytest.mark.parametrize("word,lemma,how", [
    ("食べました", "食べる", "polite past"),
    ("行きたくない", "行く", "want to, negative"),
    ("静かな", "静か", "na-adjective + na"),
    ("高かった", "高い", "past"),
    ("来ます", "来る", "polite"),
    ("読んでいる", "読む", "ongoing (-te iru)"),
    ("行った", "行く", "past"),
    ("きます", "くる", "polite"),
    ("しました", "する", "polite past"),
    ("食べなかった", "食べる", "negative, past"),
    ("書ける", "書く", "potential (can)"),
])
def test_japanese_deinflection(word, lemma, how):
    r = look(word, "ja")
    assert r["found"] and r["lemma"] == lemma and r["how_text"] == how, r
    assert r["path"][0] == word and r["path"][-1] == lemma


def test_japanese_suru_nouns_and_readings():
    r = look("勉強しています", "ja")
    assert r["lemma"] == "勉強" and r["path"] == ["勉強しています", "勉強する", "勉強"]
    assert "suru verb" in r["how_text"] and "ongoing" in r["how_text"] and r["reading"] == "べんきょう"
    assert r["rom"] == "benkyō" and r["rom_typed"] == "benkyou"
    t = look("食べる", "ja")
    assert t["reading"] == "たべる" and t["rom"] == "taberu" and "eat" in t["senses"][0]["text"]
    assert look("すし", "ja")["forms"][0] == "寿司"
    p = look("は", "ja")
    assert "topic" in p["senses"][0]["text"] and p["rom"] == "wa"


def test_japanese_romaji():
    assert ja_rules.romaji("がっこう") == "gakkō" and ja_rules.romaji("がっこう", macrons=False) == "gakkou"
    assert ja_rules.romaji("コーヒー") == "kōhī" and ja_rules.romaji("コーヒー", macrons=False) == "koohii"     # the course's koohii
    assert ja_rules.romaji("まっちゃ") == "matcha" and ja_rules.romaji("きんえん") == "kin'en" and ja_rules.romaji("ほんや") == "hon'ya"
    assert ja_rules.romaji("おもう", keep_final_ou=True) == "omou" and ja_rules.romaji("しゃしん") == "shashin"
    assert ja_rules.kana_from_romaji("konnichiwa") == ["こんにちわ"] and ja_rules.kana_from_romaji("gakkō")[0] == "がっこう"


@pytest.mark.parametrize("text,want", [
    ("私は学生です。", ["私", "は", "学生", "です"]),
    ("わたしはがくせいです。", ["わたし", "は", "がくせい", "です"]),
    ("日本語を勉強しています。", ["日本語", "を", "勉強しています"]),
    ("この部屋は静かな所です。", ["この", "部屋", "は", "静かな", "所", "です"]),
    ("東京から大阪まで新幹線で来ます。", ["東京", "から", "大阪", "まで", "新幹線", "で", "来ます"]),
    ("昨日、友達と映画を見ました。", ["昨日", "友達", "と", "映画", "を", "見ました"]),
    ("これはなんですか。", ["これ", "は", "なん", "です", "か"]),
    ("たなかさんはせんせいです。", ["たなか", "さん", "は", "せんせい", "です"]),
    ("わたしはさんじゅうにさいです。", ["わたし", "は", "さんじゅうにさい", "です"]),
])
def test_japanese_segmentation_and_particles(text, want):
    assert words("ja", text) == want


def test_japanese_search_both_ways():
    get = lambda q, d="from": [x["w"] for x in client.get("/api/dict/search", params={"q": q, "lang": "ja", "dir": d}).json()["results"]]  # noqa: E731
    assert get("食べる")[0] == "食べる" and get("たべる")[0] == "食べる" and get("taberu")[0] == "食べる"
    assert get("食べました")[0] == "食べる"
    assert get("gakkō")[0] == "学校" and get("gakkou")[0] == "学校"
    assert "東京" in get("tokyo")[:3]
    assert "食べる" in get("to eat", "en")[:3] and "学校" in get("school", "en")[:3]
    row = client.get("/api/dict/search", params={"q": "school", "lang": "ja", "dir": "en"}).json()["results"][0]
    assert row["read"] == "がっこう" and row["rom"] == "gakkō"


# ---------------------------------------------------------------- My words
def test_my_words_for_chinese_and_japanese():
    assert client.post("/api/words", json={"lang": "zh", "word": "学习", "meaning": "to study", "ctx": "我喜欢学习中文。"}).json()["ok"]
    assert client.post("/api/words", json={"lang": "ja", "word": "学校", "meaning": "school"}).json()["ok"]
    a, b = reader.my_item_id("zh", "学习"), reader.my_item_id("ja", "学校")
    assert a.startswith("my-zh-") and b.startswith("my-ja-") and len(a.split("-")[-1]) == 8
    assert reader.my_item_id("zh", "学习") == a and reader.my_item_id("zh", "學習") != a          # stable, and by the exact word
    zi = packs.item_index()[a]
    assert zi["l2"] == "学习" and zi["rom"] == "xuéxí" and packs.get("my-zh")["lang"] == "zh-CN"
    ji = packs.item_index()[b]
    assert ji["rom"] == "gakkou" and ji["alt"] == ["gakkō"] and packs.get("my-ja")["title"] == "My words (Japanese)"
    # typed answers: the script or its romanisation, tone numbers accepted
    assert engine.check_typed("xue2xi2", engine._accepted(zi))["correct"]
    assert engine.check_typed("学习", engine._accepted(zi))["correct"]
    assert engine.check_typed("gakkō", engine._accepted(ji))["correct"] and engine.check_typed("がっこう", engine._accepted(ji))["correct"] is False
    assert look("学习", "zh")["saved"] is True
    rows = client.get("/api/words", params={"lang": "ja"}).json()["words"]
    assert rows[0]["word"] == "学校" and rows[0]["rom"] == "gakkou"


# ---------------------------------------------------------------- hostile input and caps
@pytest.mark.parametrize("bad", ["", " ", "<script>", "a" * 300, "12345", "two words", "\x00\x01", "../../etc/passwd", "学" * 41,
                                 "‮食べる", "ｶﾀｶﾅ"])
@pytest.mark.parametrize("lang", ["zh", "ja"])
def test_hostile_lookups_are_harmless(bad, lang):
    r = client.get("/api/dict", params={"w": bad[:200], "lang": lang, "pre": "<b>" * 5, "post": "x" * 40})
    assert r.status_code == 200 and r.json()["ok"] and "<" not in r.json()["word"]
    assert client.get("/api/dict", params={"w": "x", "lang": lang, "post": "x" * 41}).status_code == 422
    s = client.get("/api/dict/search", params={"q": bad[:200], "lang": lang})
    assert s.status_code == 200 and len(s.json()["results"]) <= 40
    assert client.get("/api/dict/search", params={"q": bad[:200], "lang": lang, "dir": "en"}).status_code == 200


def test_half_width_katakana_is_normalised():
    assert ja.norm_word("ｶﾀｶﾅ") == "カタカナ" and zh.norm_word("　学习！") == "学习"


@pytest.mark.parametrize("lang", ["zh", "ja"])
def test_segment_caps_and_odd_text(lang):
    assert client.post("/api/dict/segment", json={"lang": lang, "text": "学" * (reader.MAX_SEGMENT + 1)}).status_code == 413
    for text in ["", "\x00\x07", "👍🏽" * 50, "ー" * 100, "っっっ", "１２３ＡＢＣ", "a" * 500, "\n\n" * 20, "《》［＃］" * 10]:
        r = client.post("/api/dict/segment", json={"lang": lang, "text": text})
        assert r.status_code == 200
        toks = r.json()["tokens"]
        assert "".join(t["t"] for t in toks) == reader.clean_text(text, reader.MAX_SEGMENT)


def test_a_full_page_segments_quickly():
    import time
    page = ("吾輩は猫である。名前はまだ無い。どこで生れたかとんと見当がつかぬ。何でも薄暗いじめじめした所でニャーニャー泣いていた事だけは記憶している。" * 12)[:1500]
    t = time.time()
    ja.segment(page)
    zh.segment(("从前有座山，山里有座庙，庙里有个老和尚在给小和尚讲故事。" * 60)[:1500])
    assert time.time() - t < 5


# ---------------------------------------------------------------- the courses' own sentences (a fixed subset)
def test_course_sentences_hit_rate():
    """``python tests/lexicon_quality.py`` measures every course sentence; this pins a fast subset."""
    import tests.lexicon_quality as q
    for lang, floor in (("zh", 0.95), ("ja", 0.90)):
        sents = q.sentences(lang)[:150]
        tok = hit = 0
        for text, _ in sents:
            src = text.replace(" ", "")
            for t in (zh if lang == "zh" else ja).segment(src):
                if t["k"] and any(cjk.kind(ch) in ("h", "H", "K") for ch in t["t"]):
                    tok += 1
                    r = (zh if lang == "zh" else ja).lookup(t["k"])
                    hit += bool(r["found"] and not r.get("weak"))
        assert tok > 100 and hit / tok >= floor, (lang, hit / tok)


# ---------------------------------------------------------------- compact tables (memory)
def test_compact_tables_answer_as_before():
    from sect_academy.lexicon import fr
    m = cjk.IdMap()
    for k, i in (("a", 3), ("b", 5), ("b", 2), ("c", 7), ("c", 7)):
        m.add(k, i)
    m.freeze(sort_key=lambda i: i)
    assert m.get("a") == (3,) and m["b"] == (2, 5) and m["c"] == (7, 7) and m.get("z", []) == [] and "a" in m
    assert dict.__getitem__(m, "a") == 3                                   # stored as a bare int
    d = ja.dictionary()
    assert isinstance(d.lines[0], bytes) and d.kanji[d.index["食べる"][0]].startswith("食べる")
    assert sum(type(v) is int for v in dict.values(d.index)) > 0.9 * len(d.index)
    assert type(dict.__getitem__(zh.dictionary().head, "图书馆")) is int
    tb = fr.dictionary()
    one = next(f for f, v in tb.frm.items() if type(v) is str)
    assert tb.lemmas_of(one) == (tb.frm[one],) and tb.lemmas_of("zzzz-not-a-form") == ()
    assert all(type(v) in (str, tuple) for v in list(tb.frm.values())[:1000])
