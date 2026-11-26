"""The reader: dictionary lookup, your own words (and their deck), the book shelf."""
import json

import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, lexicon, packs, reader, state
from sect_academy.app import app
from sect_academy.lexicon import es

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    state.reset_for_tests()
    reader.reset_for_tests()
    packs.load_all(force=True)
    yield
    state.reset_for_tests()
    reader.reset_for_tests()


def look(w, lang="es"):
    return client.get("/api/dict", params={"w": w, "lang": lang}).json()


# ---------------------------------------------------------------- lookup
@pytest.mark.parametrize("word,lemma", [
    ("dímelo", "decir"), ("dimelo", "decir"),            # enclitic pronouns, with and without the accent
    ("cúrale", "curar"), ("curale", "curar"),
    ("levántate", "levantar"), ("decírselo", "decir"),
    ("cúramelas", "curar"),                              # not in the form table: found by taking the pronouns off
    ("casas", "casa"),                                   # plural (the data only knows "casas" as a surname)
    ("niñas", "niño"), ("hablábamos", "hablar"),          # F -> L
    ("¿Cómo?", "cómo"), ("CASA", "casa"),                # case and punctuation
])
def test_lookup_finds_the_dictionary_form(word, lemma):
    r = look(word)
    assert r["found"] and r["lemma"] == lemma, r
    assert r["path"][-1] == lemma and r["senses"]
    assert "Wiktionary" in r["credit"] and "CC BY-SA" in r["credit"]


def test_lookup_paths_and_kinds():
    # pronouns attached to a verb are taken off by rule (the form table keeps no dímelo, cúrale)
    assert look("cúrale")["path"] == ["cúrale", "curar"] and look("cúrale")["how"] == "pronouns"
    assert look("cúramelas")["how"] == "pronouns"
    assert look("dimelo")["path"][-1] == "decir" and look("dimelo")["how"] == "pronouns"
    assert "imperative" in look("dímelo")["gram"] and "me + lo" in look("dímelo")["gram"]
    # año and ano are different words: an accent is never dropped when the word exists as written
    assert "year" in [s["text"] for s in look("año")["senses"]]
    assert look("ano")["senses"][0]["text"] == "anus"
    assert not look("xyzzyqq")["found"]


def test_candidates_order_is_aprende_like():
    c = [k for k, _ in es.candidates("casas")]
    assert c[0] == "casas" and c[1] == "casa"           # the plural first, before any accent variant
    assert "curar" in [k for k, _ in es.candidates("cúramelas")]


@pytest.mark.parametrize("bad", ["", " ", "<script>", "a" * 300, "12345", "two words", "\x00\x01", "../../etc/passwd"])
def test_hostile_lookups_are_harmless(bad):
    r = client.get("/api/dict", params={"w": bad[:200]})
    assert r.status_code == 200
    assert r.json()["ok"] and "<" not in r.json()["word"]
    assert client.get("/api/dict", params={"w": "x" * 201}).status_code == 422


def test_search_both_ways():
    r = client.get("/api/dict/search", params={"q": "house", "dir": "en"}).json()
    assert r["results"][0]["w"] == "casa"
    r = client.get("/api/dict/search", params={"q": "cas"}).json()
    assert any(x["w"] == "casa" for x in r["results"]) and len(r["results"]) <= 40
    assert client.get("/api/dict/search", params={"q": ""}).json()["results"] == []


def test_languages_without_a_module_say_so():
    langs = client.get("/api/dict/langs").json()
    assert {"es", "fr", "zh", "ja", "ko"} <= set(langs["lookup"]) and "de" not in langs["lookup"]
    assert {"es", "fr", "zh", "ja", "ko"} <= set(langs["langs"])
    r = look("hallo", "de")
    assert r["available"] is False and not r["found"]
    assert client.get("/api/dict/search", params={"q": "x", "lang": "de"}).json()["available"] is False
    assert client.post("/api/words", json={"lang": "de", "word": "katze", "meaning": "cat"}).status_code == 400
    assert client.post("/api/dict/entry", json={"lang": "zz", "word": "x", "meaning": "y"}).status_code == 400


def test_segment_gives_the_text_back_with_keys():
    text = "¿Dímelo, Juan?\n\nSí — cúrale."
    r = client.post("/api/dict/segment", json={"lang": "es", "text": text}).json()
    assert "".join(t["t"] for t in r["tokens"]) == text
    assert [t["k"] for t in r["tokens"] if t["k"]] == ["dímelo", "juan", "sí", "cúrale"]
    other = client.post("/api/dict/segment", json={"lang": "de", "text": "Die Katze schläft."}).json()
    assert not other["available"] and [t["k"] for t in other["tokens"] if t["k"]] == ["die", "katze", "schläft"]
    assert client.post("/api/dict/segment", json={"lang": "es", "text": "a" * (reader.MAX_SEGMENT + 1)}).status_code == 413


# ---------------------------------------------------------------- your entries
def test_user_entries_come_first_and_can_be_deleted():
    assert client.post("/api/dict/entry", json={"word": "  Zorpíto! ", "meaning": "great\x00 (Venezuela)"}).json()["word"] == "zorpíto"
    r = look("zorpíto")
    assert r["found"] and r["senses"][0] == {"src": "mine", "text": "great (Venezuela)"}
    client.post("/api/dict/entry", json={"word": "casa", "meaning": "home, my place"})
    assert look("casa")["senses"][0]["src"] == "mine"
    assert client.get("/api/dict/search", params={"q": "venezuela", "dir": "en"}).json()["results"][0]["w"] == "zorpíto"
    assert client.delete("/api/dict/entry", params={"w": "zorpíto"}).json()["deleted"]
    assert not look("zorpíto")["found"]
    assert client.post("/api/dict/entry", json={"word": "", "meaning": "x"}).status_code == 400
    assert client.post("/api/dict/entry", json={"word": "<>", "meaning": "x"}).status_code == 400


def test_user_entries_are_capped(monkeypatch):
    monkeypatch.setattr(reader, "MAX_USER_ENTRIES", 3)
    for w in ("uno", "dos", "tres"):
        assert reader.add_entry("es", w, "n")["ok"]
    assert not reader.add_entry("es", "cuatro", "n")["ok"]
    assert reader.add_entry("es", "uno", "one")["ok"]                 # replacing is always allowed


def test_state_sanitises_reader_fields():
    hostile = {"cards": {}, "dict_user": {"es": {"ok": "fine", "<x>": "y", "x" * 99: "y", "dos": 5}, "../": {"a": "b"}, "fr": "no"},
               "words": {"es": {"gato": {"l1": "cat‮", "ts": "soon", "ctx": 7}, "perro": {"l1": ""}, "p": "x"}, "es2": {}},
               "book_pos": {"0123456789ab": 5, "../../x": 3, "abcdefabcdef": True, "fedcbafedcba": 10**12}}
    st = state.sanitize(hostile)
    assert st["dict_user"] == {"es": {"ok": "fine", "x": "y"}}       # "<x>" is only punctuation around a word
    assert st["words"] == {"es": {"gato": {"l1": "cat", "form": "gato", "ctx": "", "ts": 0.0}}}
    assert st["book_pos"] == {"0123456789ab": 5, "fedcbafedcba": reader.BOOK_MAX_CHARS}
    assert state.sanitize({"cards": {}, "words": ["nope"], "dict_user": None})["words"] == {}


# ---------------------------------------------------------------- my words and their deck
def test_item_ids_are_stable_and_distinct():
    assert reader.my_item_id("es", "casa") == "my-es-casa"
    a, b = reader.my_item_id("es", "año"), reader.my_item_id("es", "ano")
    assert a != b and a.startswith("my-es-ano-") and b == "my-es-ano"
    assert reader.my_item_id("es", "año") == a                      # the same word, the same id, for ever
    assert reader.my_item_id("zh", "你好").startswith("my-zh-") and len(reader.my_item_id("es", "x" * 40)) <= 64


def test_yaml_courses_may_not_use_personal_ids():
    errs = packs.validate_pack({"id": "x-test", "title": "T", "kind": "language", "language": "Spanish", "lang": "es-ES", "hall": "h",
                                "blurb": "b", "units": [{"id": "u-1", "title": "t", "goal": "g", "notes": "n",
                                                          "items": [{"id": f"my-es-w{i}", "type": "vocab", "l2": "a", "l1": "b"} for i in range(4)]}]})
    assert any("learner's own words" in e for e in errs)


def _save(words):
    for w, m in words:
        r = client.post("/api/words", json={"word": w, "meaning": m, "form": w, "ctx": f"Una frase con {w}."})
        assert r.status_code == 200, r.text


def _truth(ex):
    it = packs.item_index()[ex["item"]]
    return it["l2"] if ex["mode"] in ("type_l2", "listen", "build_l2") else engine._truth(it, ex["mode"])


def test_saved_words_become_a_scheduled_deck_that_pays():
    _save([("casa", "house"), ("perro", "dog"), ("año", "year"), ("gato", "cat"), ("luz", "light")])
    assert "my-es" in packs.load_all()
    pack = packs.get("my-es")
    assert pack["title"] == "My words (Spanish)" and len(pack["units"][0]["items"]) == 5
    assert client.post("/api/enroll", json={"course": "my-es", "on": True}).json()["ok"]
    s = client.post("/api/session", json={"course": "my-es"}).json()
    tests = [e for e in s["exercises"] if e["mode"] != "intro"]
    assert tests and all(e["item"].startswith("my-es-") for e in s["exercises"])
    ex = tests[0]
    qi_before = state.get()["colony"]["insight"]
    r = client.post("/api/answer", json={"session": s["session"], "item": ex["item"], "mode": ex["mode"], "answer": _truth(ex)}).json()
    assert r["correct"] and r["rewards"]["insight"] == 1
    assert state.get()["colony"]["insight"] == qi_before + 1
    card = state.get()["cards"][ex["item"]]
    assert card["reps"] == 1 and card["due"] > 0                      # scheduled by FSRS
    # only the first answer to an issued item counts
    again = client.post("/api/answer", json={"session": s["session"], "item": ex["item"], "mode": ex["mode"], "answer": _truth(ex)}).json()
    assert again["rewards"] == {} and state.get()["cards"][ex["item"]]["reps"] == 1
    # an item the session did not issue is graded for feedback but never scheduled
    other = next(i["id"] for i in pack["units"][0]["items"] if i["id"] not in {e["item"] for e in s["exercises"]}) \
        if len(s["exercises"]) < 10 else None
    if other:
        client.post("/api/answer", json={"session": s["session"], "item": other, "mode": "choose_l1", "answer": "x"})
        assert other not in state.get()["cards"]
    # the words list shows the card's state
    rows = {w["word"]: w for w in client.get("/api/words").json()["words"]}
    assert rows[packs.item_index()[ex["item"]]["l2"]]["state"] == "learning"


def test_deleting_and_resaving_a_word_keeps_its_progress():
    _save([("casa", "house"), ("perro", "dog"), ("gato", "cat"), ("año", "year")])
    iid = reader.my_item_id("es", "año")
    st = state.get()
    st["cards"][iid] = {"s": 3.0, "d": 5.0, "due": 1.0, "last": 1.0, "reps": 2, "lapses": 0, "seen": 1.0}
    assert client.delete("/api/words", params={"w": "año"}).json()["deleted"]
    assert iid not in packs.item_index()
    _save([("año", "year")])
    assert iid in packs.item_index() and state.get()["cards"][iid]["reps"] == 2
    client.delete("/api/words", params={"w": "casa"})
    client.delete("/api/words", params={"w": "perro"})
    client.delete("/api/words", params={"w": "gato"})
    client.delete("/api/words", params={"w": "año"})
    assert "my-es" not in packs.load_all()                             # no words, no course


def test_saved_words_are_capped_and_marked_in_lookup(monkeypatch):
    monkeypatch.setattr(reader, "MAX_SAVED_WORDS", 2)
    _save([("casa", "house"), ("perro", "dog")])
    assert client.post("/api/words", json={"word": "gato", "meaning": "cat"}).status_code == 400
    assert look("casas")["saved"] is True and look("gato")["saved"] is False
    assert client.post("/api/words", json={"word": "casa", "meaning": ""}).status_code == 400


def test_import_carries_saved_words_and_rebuilds_the_deck():
    _save([("casa", "house")])
    blob = client.get("/api/export").json()
    state.reset_for_tests()
    reader.reset_for_tests()
    assert "my-es" not in packs.load_all()
    assert client.post("/api/import", json=blob).json()["ok"]
    assert [i["l2"] for i in packs.get("my-es")["units"][0]["items"]] == ["casa"]


# ---------------------------------------------------------------- books
BOOK = "Había una vez un pueblo junto al mar. " * 20


def test_book_round_trip_and_position():
    r = client.post("/api/books", json={"title": "  El\x07 pueblo\n\n junto al mar  ", "text": BOOK, "lang": "es"}).json()
    b = r["book"]
    assert b["title"] == "El pueblo junto al mar" and b["lang"] == "es" and b["chars"] == len(BOOK.strip())
    shelf = client.get("/api/books").json()
    assert [x["id"] for x in shelf["books"]] == [b["id"]] and "es" in shelf["lookup"]
    assert client.put(f"/api/books/{b['id']}/pos", json={"pos": 120}).json()["pos"] == 120
    got = client.get(f"/api/books/{b['id']}").json()
    assert got["text"] == BOOK.strip() and got["book"]["pos"] == 120 and got["book"]["lookup"] is True
    assert client.delete(f"/api/books/{b['id']}").json()["deleted"]
    assert client.get(f"/api/books/{b['id']}").status_code == 404
    assert b["id"] not in state.get()["book_pos"]


def test_books_on_disk_beside_the_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", str(tmp_path / "s.json"))
    state.reset_for_tests()
    b = client.post("/api/books", json={"title": "Uno", "text": BOOK, "lang": "de"}).json()["book"]
    files = sorted(p.name for p in (tmp_path / "s.json.books").iterdir())
    assert files == [f"{b['id']}.json", f"{b['id']}.txt"]
    assert json.loads((tmp_path / "s.json.books" / f"{b['id']}.json").read_text())["lang"] == "de"
    (tmp_path / "s.json.books" / "evil.json").write_text("{}")             # not a book id: ignored
    (tmp_path / "s.json.books" / "aaaaaaaaaaaa.json").write_text("not json")
    (tmp_path / "s.json.books" / "aaaaaaaaaaaa.txt").write_text("x")
    assert [x["id"] for x in client.get("/api/books").json()["books"]] == [b["id"]]
    assert client.get(f"/api/books/{b['id']}").json()["book"]["lookup"] is False
    client.delete(f"/api/books/{b['id']}")
    assert not (tmp_path / "s.json.books" / f"{b['id']}.txt").exists()


def test_book_caps(monkeypatch):
    monkeypatch.setattr(reader, "BOOKS_MAX_COUNT", 2)
    monkeypatch.setattr(reader, "BOOKS_MAX_BYTES", 3 * len(BOOK.encode()))
    assert client.post("/api/books", json={"title": "1", "text": BOOK}).status_code == 200
    assert client.post("/api/books", json={"title": "2", "text": BOOK}).status_code == 200
    r = client.post("/api/books", json={"title": "3", "text": BOOK})
    assert r.status_code == 400 and "holds 2 books" in r.json()["detail"]
    monkeypatch.setattr(reader, "BOOKS_MAX_COUNT", 10)
    assert client.post("/api/books", json={"title": "big", "text": BOOK * 2}).status_code == 400   # over the byte cap
    monkeypatch.setattr(reader, "BOOK_MAX_CHARS", 100)
    assert "longer than" in client.post("/api/books", json={"title": "x", "text": BOOK}).json()["detail"]


@pytest.mark.parametrize("body,ctype,code", [
    ('{"title": "x", "text": "short"}', "application/json", 400),        # no readable text
    ('{"title": "x"}', "application/json", 400),
    ('[1, 2]', "application/json", 400),
    ('not json', "application/json", 400),
    ('title=x&text=' + "y" * 100, "application/x-www-form-urlencoded", 400),   # a form post is never a book
])
def test_bad_book_posts_are_refused(body, ctype, code):
    assert client.post("/api/books", content=body, headers={"content-type": ctype}).status_code == code


def test_oversized_book_post_is_refused_before_reading():
    r = client.post("/api/books", content=b"{}", headers={"content-type": "application/json",
                                                         "content-length": str(reader.BOOK_POST_MAX_BYTES + 1)})
    assert r.status_code == 413


def test_book_ids_are_checked():
    for bad in ("../../etc", "ABCDEFABCDEF", "0123456789abc", "nope"):
        assert client.get(f"/api/books/{bad}").status_code == 404
        assert client.delete(f"/api/books/{bad}").status_code == 404
        assert client.put(f"/api/books/{bad}/pos", json={"pos": 1}).status_code == 404
    assert client.put("/api/books/0123456789ab/pos", json={"pos": 1}).status_code == 404   # well-formed, but not on the shelf
    b = client.post("/api/books", json={"title": "t", "text": BOOK}).json()["book"]
    assert client.put(f"/api/books/{b['id']}/pos", json={"pos": -5}).json()["pos"] == 0
    assert client.put(f"/api/books/{b['id']}/pos", json={"pos": "seven"}).status_code == 422
    assert client.post("/api/books", json={"title": "", "text": BOOK, "lang": "<x>"}).json()["book"]["lang"] == "es"
    shelf = client.get("/api/books").json()["books"]
    assert {x["title"] for x in shelf} == {"t", "Untitled"} and {x["lang"] for x in shelf} == {"es"}


@pytest.mark.parametrize("method,path,kw", [
    ("post", "/api/books", {"json": {"title": "x", "text": BOOK}}),
    ("post", "/api/words", {"json": {"word": "casa", "meaning": "house"}}),
    ("post", "/api/dict/entry", {"json": {"word": "casa", "meaning": "house"}}),
    ("delete", "/api/words?w=casa", {}),
    ("put", "/api/books/0123456789ab/pos", {"json": {"pos": 1}}),
])
def test_cross_site_writes_are_refused(method, path, kw):
    for h in ({"origin": "https://evil.example"}, {"sec-fetch-site": "cross-site"}):
        r = getattr(client, method)(path, headers=h, **kw)
        assert r.status_code == 403
    assert not state.get().get("words") and not client.get("/api/books").json()["books"]


def test_reader_assets_are_local():
    for asset in ("/reader.js", "/read"):
        r = client.get(asset)
        assert r.status_code == 200
        assert "http://" not in r.text and "https://" not in r.text
    for name in ("pdf.min.js", "pdf.worker.min.js"):
        r = client.get(f"/vendor/pdfjs/{name}")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/javascript")
        assert "Apache License" in r.text[:2000]
    assert client.get("/vendor/pdfjs/LICENSE").status_code == 404
    assert client.get("/vendor/pdfjs/..%2F..%2Fapp.py").status_code == 404
    assert "default-src 'self'" in client.get("/read").headers["content-security-policy"]


def test_registry_contract():
    mod = lexicon.get("es")
    for name in ("LANG", "NAME", "SPEECH", "CREDIT", "norm_word", "lookup", "search", "segment"):
        assert hasattr(mod, name), name
    assert lexicon.get("de") is None and lexicon.get(None) is None
