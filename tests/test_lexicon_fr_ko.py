"""French and Korean lookup: elisions, inversions, inflections, particles, endings, romanisation, My words."""
import re
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from sect_academy import lexicon, packs, reader, state
from sect_academy.app import app
from sect_academy.lexicon import fr, ko

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import lexicon_hit_rate  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    state.reset_for_tests()
    reader.reset_for_tests()
    yield
    state.reset_for_tests()
    reader.reset_for_tests()


def look(w, lang):
    r = client.get("/api/dict", params={"w": w, "lang": lang})
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------- French
@pytest.mark.parametrize("word,lemma", [
    ("l'homme", "homme"), ("L’homme", "homme"), ("qu'il", "il"), ("lorsqu'elle", "elle"), ("d'être", "être"),
    ("s'appelle", "appeler"), ("l'", "le"), ("qu'", "que"),                        # elisions
    ("dit-il", "dire"), ("va-t-on", "aller"), ("allez-vous", "aller"), ("donne-moi", "donner"),   # inversions
    ("chevaux", "cheval"), ("nationaux", "national"), ("belles", "beau"), ("heureuse", "heureux"),
    ("heureuses", "heureux"), ("chats", "chat"), ("enfants", "enfant"),              # plurals and feminines
    ("allons", "aller"), ("fut", "être"), ("irons", "aller"), ("faisaient", "faire"), ("est", "être"),
    ("suis", "être"), ("vais", "aller"), ("mangé", "manger"),                       # conjugated verbs
    ("aujourd'hui", "aujourd'hui"), ("peut-être", "peut-être"),                      # known whole
    ("ecole", "école"), ("Ça", "ça"),                                                # accents, case
])
def test_french_lookup_finds_the_dictionary_form(word, lemma):
    r = look(word, "fr")
    assert r["available"] and r["found"] and r["lemma"] == lemma, r
    assert r["senses"] and not r["weak"]
    assert "Wiktionary" in r["credit"] and "CC BY-SA" in r["credit"]


def test_french_readings_and_alternatives():
    est = look("est", "fr")
    assert est["how"] == "form" and est["path"] == ["est", "être"] and "est" in [a["lemma"] for a in est["also"]]
    assert look("l'été", "fr")["lemma"] == "été" and "summer" in look("l'été", "fr")["senses"][0]["text"]
    assert look("l'homme", "fr")["how"] == "elision" and "le / la" in look("l'homme", "fr")["gram"]
    assert look("dit-il", "fr")["how"] == "inversion"
    assert look("plus", "fr")["lemma"] == "plus"                    # not plaire
    assert not look("xyzzyqq", "fr")["found"]


def test_french_segment_splits_elisions_and_inversions():
    text = "L'homme dit-il : « Va-t-on chez l'ami qu'il aime aujourd'hui ? » Peut-être."
    toks = client.post("/api/dict/segment", json={"lang": "fr", "text": text}).json()["tokens"]
    assert "".join(t["t"] for t in toks) == text
    assert [t["k"] for t in toks if t["k"]] == ["l'", "homme", "dit", "il", "va", "on", "chez", "l'", "ami", "qu'", "il",
                                               "aime", "aujourd'hui", "peut-être"]
    assert {"t": "-t-", "k": None} in toks


def test_french_search_both_ways():
    r = client.get("/api/dict/search", params={"q": "house", "dir": "en", "lang": "fr"}).json()
    assert r["available"] and r["results"][0]["w"] == "maison"
    assert client.get("/api/dict/search", params={"q": "dog", "dir": "en", "lang": "fr"}).json()["results"][0]["w"] == "chien"
    r = client.get("/api/dict/search", params={"q": "chev", "lang": "fr"}).json()
    assert any(x["w"] == "cheval" for x in r["results"]) and len(r["results"]) <= 40
    assert client.get("/api/dict/search", params={"q": "chevaux", "lang": "fr"}).json()["results"][0]["w"] == "cheval"


# ---------------------------------------------------------------- Korean
@pytest.mark.parametrize("word,lemma,how", [
    ("학교에서", "학교", "particle"), ("친구를", "친구", "particle"), ("사람이에요", "사람", "particle"),
    ("친구들에게는", "친구", "particle"), ("나는", "나", "particle"), ("저는", "저", "particle"),
    ("먹었어요", "먹다", "form"), ("공부했습니다", "공부하다", "form"), ("가요", "가다", "form"),
    ("더워요", "덥다", "form"), ("몰라요", "모르다", "form"), ("써요", "쓰다", "form"), ("봐요", "보다", "form"),
    ("줘요", "주다", "form"), ("해요", "하다", "form"), ("돼요", "되다", "form"), ("들어요", "듣다", "form"),
    ("가셨어요", "가다", "form"), ("마셔요", "마시다", "form"), ("감사합니다", "감사합니다", "exact"),
])
def test_korean_lookup_takes_off_particles_and_endings(word, lemma, how):
    r = look(word, "ko")
    assert r["found"] and r["lemma"] == lemma and r["how"] == how, r
    assert r["senses"] and not r["weak"]


def test_korean_rules_without_the_form_table(monkeypatch):
    """The ending rules alone (the form table emptied) still reach the dictionary form, with the grammar named."""
    d = ko.dictionary()
    monkeypatch.setattr(d, "frm", {})
    for word, lemma, gram in [("먹었어요", "먹다", "past polite"), ("공부했습니다", "공부하다", "past formal polite"),
                              ("더워요", "덥다", "ㅂ irregular"), ("몰라요", "모르다", "르 irregular"),
                              ("써요", "쓰다", "ㅡ dropped"), ("나아요", "낫다", "ㅅ irregular"),
                              ("먹고", "먹다", "and"), ("만드세요", "만들다", "ㄹ dropped"), ("그래서", "그렇다", "ㅎ irregular")]:
        r = ko.lookup(word, {})
        hit = [r] + r["also"]
        assert any(h["lemma"] == lemma and gram in h["gram"] for h in hit), (word, r)
    both = ko.lookup("들어요", {})                   # ㄷ irregular: both readings, the usual one first
    assert both["lemma"] == "듣다" and "들다" in [a["lemma"] for a in both["also"]]


def test_korean_grammar_note_and_romanisation():
    r = look("먹었어요", "ko")
    assert r["path"] == ["먹었어요", "먹다"] and r["gram"].startswith("past polite")
    assert r["rom"] == "meogeosseoyo" and r["lemma_rom"] == "meokda"
    assert "에서" in look("학교에서", "ko")["gram"]
    assert look("오천", "ko")["senses"][0]["text"] == "5,000" and ko.sino_number("이십오") == 25


def test_romanisation_matches_the_course():
    """Revised Romanization with sound changes, against every rom / ex_rom the Korean course gives."""
    pairs = []

    def walk(o):
        if isinstance(o, dict):
            for a, b in (("l2", "rom"), ("ex", "ex_rom")):
                if isinstance(o.get(a), str) and isinstance(o.get(b), str) and len(o[a]) > 1:
                    pairs.append((o[a], o[b]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(yaml.safe_load((Path(packs.PACK_DIR) / "korean_a1.yaml").read_text(encoding="utf-8")))
    key = lambda s: re.sub(r"[^a-z]", "", s.lower())                       # noqa: E731
    bad = [(a, b, ko.romanise(a)) for a, b in pairs if key(ko.romanise(a)) != key(b)]
    assert len(pairs) > 300 and not bad, bad[:5]
    for w, r in [("국립", "gungnip"), ("신라", "silla"), ("같이", "gachi"), ("좋다", "jota"), ("싫어해요", "sireohaeyo")]:
        assert ko.romanise(w) == r


def test_korean_search_both_ways():
    r = client.get("/api/dict/search", params={"q": "to eat", "dir": "en", "lang": "ko"}).json()
    assert r["results"][0]["w"] == "먹다" and r["results"][0]["rom"] == "meokda"
    r = client.get("/api/dict/search", params={"q": "학교", "lang": "ko"}).json()
    assert r["results"][0]["w"] == "학교" and len(r["results"]) <= 40
    r = client.get("/api/dict/search", params={"q": "hakgyo", "lang": "ko"}).json()    # by romanisation
    assert r["results"][0]["w"] == "학교"
    assert client.get("/api/dict/search", params={"q": "먹었어요", "lang": "ko"}).json()["results"][0]["w"] == "먹다"


# ---------------------------------------------------------------- both
def test_registry_and_speech():
    langs = client.get("/api/dict/langs").json()
    assert {"es", "fr", "ko"} <= set(langs["lookup"])
    for mod, speech in ((fr, "fr-FR"), (ko, "ko-KR")):
        for name in ("LANG", "NAME", "SPEECH", "CREDIT", "norm_word", "lookup", "search", "segment"):
            assert hasattr(mod, name), name
        assert mod.SPEECH == speech == lexicon.SPEECH[mod.LANG]
    assert "fr: 'fr-FR'" in client.get("/reader.js").text and "ko: 'ko-KR'" in client.get("/reader.js").text


def test_my_words_ids_and_decks():
    packs.load_all(force=True)
    assert reader.my_item_id("fr", "chat") == "my-fr-chat"
    a, b = reader.my_item_id("fr", "été"), reader.my_item_id("fr", "ete")
    assert a != b and a.startswith("my-fr-ete-") and reader.my_item_id("fr", "été") == a
    k = reader.my_item_id("ko", "먹다")
    assert re.fullmatch(r"my-ko-[0-9a-f]{8}", k) and k == reader.my_item_id("ko", "먹다") != reader.my_item_id("ko", "가다")
    for lang, word, meaning in (("fr", "cheval", "horse"), ("ko", "먹다", "to eat")):
        r = client.post("/api/words", json={"lang": lang, "word": word, "meaning": meaning, "form": word, "ctx": ""})
        assert r.status_code == 200 and r.json()["course"] == f"my-{lang}"
    deck = packs.get("my-ko")
    item = deck["units"][0]["items"][0]
    assert deck["title"] == "My words (Korean)" and deck["lang"] == "ko-KR"
    assert item["l2"] == "먹다" and item["rom"] == "meokda"
    assert packs.get("my-fr")["units"][0]["items"][0]["id"] == "my-fr-cheval"
    assert look("먹었어요", "ko")["saved"] and look("chevaux", "fr")["saved"]


@pytest.mark.parametrize("lang", ["fr", "ko"])
@pytest.mark.parametrize("bad", ["", " ", "<script>", "a" * 300, "12345", "two words", "\x00\x01", "../../etc/passwd",
                                 "l'", "-", "'''", "---t---", "ㅂ니다", "​", "가" * 39])
def test_hostile_lookups_are_harmless(lang, bad):
    r = client.get("/api/dict", params={"w": bad[:200], "lang": lang})
    assert r.status_code == 200 and r.json()["ok"] and "<" not in r.json()["word"]
    s = client.get("/api/dict/search", params={"q": bad[:200], "lang": lang, "dir": "en"})
    assert s.status_code == 200
    seg = client.post("/api/dict/segment", json={"lang": lang, "text": bad}).json()
    assert "".join(t["t"] for t in seg["tokens"]) == reader.clean_text(bad, reader.MAX_SEGMENT)


# ---------------------------------------------------------------- real text
@pytest.mark.parametrize("lang,floor", [("fr", 0.97), ("ko", 0.95)])
def test_hit_rate_on_the_course_sentences(lang, floor):
    """Measured at 99.9% (fr) and 99.7% (ko) when built; a fall below the floor means lookup or data broke."""
    texts = lexicon_hit_rate.sentences(lang)[::3]
    rate, n, misses = lexicon_hit_rate.hit_rate(lang, texts)
    assert n > 300 and rate >= floor, (rate, misses.most_common(10))
