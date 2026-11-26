"""My words teach: question types by FSRS state, typed answers, the cloze from the saved sentence,
borrowed distractors, and books renamed on the shelf."""
import json

import pytest
from fastapi.testclient import TestClient

from sect_academy import engine, packs, reader, state
from sect_academy.app import app

client = TestClient(app)
BOOK = "Había una vez un pueblo junto al mar. " * 20


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


def _item(lang, word):
    return packs.item_index()[reader.my_item_id(lang, word)]


def _post(lang, word, meaning, form, ctx):
    r = client.post("/api/words", json={"lang": lang, "word": word, "meaning": meaning, "form": form, "ctx": ctx})
    assert r.status_code == 200, r.text


def _card(reps, s):
    return {"s": s, "d": 5.0, "due": 1.0, "last": 1.0, "reps": reps, "lapses": 0, "seen": 1.0}


def test_personal_modes_follow_the_fsrs_state():
    _post("es", "rascar", "to scratch", "rascaba", "El gato rascaba la puerta.")
    _post("es", "luz", "light", "luz", "")
    it, bare, pack = _item("es", "rascar"), _item("es", "luz"), packs.get("my-es")
    assert engine._mode_for(it, None, pack) == "choose_l1"                    # new: recognise it
    assert engine._mode_for(it, _card(1, 0.4), pack) == "choose_l2"          # shaky (or just lapsed): still recognition
    assert engine._mode_for(it, _card(2, 0.4), pack) == "choose_l1"
    assert engine._mode_for(it, _card(3, 6.0), pack) == "cloze_type"         # learned: recall, in its sentence ...
    assert engine._mode_for(it, _card(4, 6.0), pack) == "type_l2"            # ... or from its meaning
    assert engine._mode_for(bare, _card(3, 6.0), pack) == "type_l2"          # no sentence saved: no cloze
    fr_pack = packs.get("french-a1")                                         # a course's own vocab is untouched
    fr = next(i for u in fr_pack["units"] for i in u["items"] if i["type"] == "vocab")
    assert engine._mode_for(fr, _card(3, 6.0), fr_pack) != "cloze_type"


def test_personal_cloze_blanks_the_form_met():
    _post("es", "rascar", "to scratch", "rascaba", "El gato rascaba la puerta.")
    it = _item("es", "rascar")
    assert it["cloze"] == "El gato ___ la puerta." and it["cloze_ans"] == "rascaba"
    ex = engine.build_exercise(it, "cloze_type", packs.get("my-es"), 1)
    assert ex["prompt"] == "El gato ___ la puerta." and ex["sub"] == "to scratch" and "choices" not in ex
    assert engine.check(it, "cloze_type", "rascaba")["correct"]
    assert engine.check(it, "cloze_type", "Rascaba")["correct"]
    assert not engine.check(it, "cloze_type", "rascava")["correct"]          # no typo forgiven in a blank
    assert not engine.check(it, "cloze_type", "rascar")["correct"]           # the form, not the dictionary word
    # whole words only: "gato" is not blanked inside "gatos"; a word missing from its sentence has no cloze
    assert reader._cloze("Dos gatos y un gato.", ["gato"]) == {"cloze": "Dos gatos y un ___.", "cloze_ans": "gato"}
    assert reader._cloze("Dos gatos.", ["gato"]) == {}
    # the final-letter accent is the grammar in a blank (hablo / habló)
    _post("es", "hablar", "to speak", "habló", "Ella habló ayer.")
    h = _item("es", "hablar")
    assert engine.check(h, "cloze_type", "habló")["correct"] and not engine.check(h, "cloze_type", "hablo")["correct"]
    # a saved word without a sentence refuses the mode
    _post("es", "luz", "light", "luz", "")
    assert engine.check(_item("es", "luz"), "cloze_type", "luz").get("error") == "bad mode"


def test_personal_typed_answers_follow_the_course_rules():
    _post("es", "canción", "song", "canción", "")
    it = _item("es", "canción")
    assert engine.check(it, "type_l2", "canción") == {"correct": True, "flag": None, "expected": "canción"}
    assert engine.check(it, "type_l2", "cancion")["flag"] == "accent"         # a missing accent: right, but Hard
    assert engine.check(it, "type_l2", "cancoin")["flag"] == "typo"
    assert not engine.check(it, "type_l2", "camión")["correct"]
    _post("es", "tú", "you", "tú", "")
    assert not engine.check(_item("es", "tú"), "type_l2", "tu")["correct"]    # on a short word the accent is the word


def test_personal_cjk_answers_accept_the_romanisation():
    _post("zh", "学习", "to study", "学习", "我学习中文。")
    zh = _item("zh", "学习")
    for ans in ("学习", "xuéxí", "xue2xi2", "xue2 xi2"):
        assert engine.check(zh, "type_l2", ans)["correct"], ans
    assert not engine.check(zh, "type_l2", "xue4xi2")["correct"]               # the wrong tone is the wrong word
    assert zh["cloze"] == "我___中文。" and engine.check(zh, "cloze_type", "xue2xi2")["correct"]
    _post("ja", "食べる", "to eat", "食べました", "パンを食べました。")
    ja = _item("ja", "食べる")
    assert ja["cloze_ans"] == "食べました" and ja["cloze_rom"] == "tabemashita"
    assert engine.check(ja, "cloze_type", "tabemashita")["correct"] and engine.check(ja, "cloze_type", "食べました")["correct"]
    assert not engine.check(ja, "cloze_type", "taberu")["correct"]            # the dictionary form is not the blank
    assert engine.check(ja, "type_l2", "taberu")["correct"]
    _post("ko", "먹다", "to eat", "먹었어요", "밥을 먹었어요.")
    ko = _item("ko", "먹다")
    assert engine.check(ko, "cloze_type", "meogeosseoyo")["correct"] and engine.check(ko, "cloze_type", "먹었어요")["correct"]
    assert engine.check(ko, "type_l2", "meokda")["correct"]
    assert "romanised" in engine.build_exercise(ko, "cloze_type", packs.get("my-ko"), 1)["ask"]


def test_a_small_deck_borrows_distractors_from_the_courses():
    _post("es", "rascar", "to scratch", "rascaba", "El gato rascaba la puerta.")
    it, pack = _item("es", "rascar"), packs.get("my-es")
    course_l1 = {i["l1"] for p in packs.load_all().values() if p.get("lang") == "es-ES" and not p.get("personal")
                 for u in p["units"] for i in u["items"] if i["type"] == "vocab"}
    for seed in range(5):
        ex = engine.build_exercise(it, "choose_l1", pack, seed)
        assert len(set(ex["choices"])) == len(ex["choices"]) == 4 and "to scratch" in ex["choices"]
        wrong = [c for c in ex["choices"] if c != "to scratch"]
        assert all(c in course_l1 for c in wrong)
        assert all(c.startswith("to ") for c in wrong)                         # a verb is confused with verbs
        ex = engine.build_exercise(it, "choose_l2", pack, seed)
        assert len(set(ex["choices"])) == 4 and "rascar" in ex["choices"]
    assert engine.check(it, "choose_l2", "rascar")["correct"] and not engine.check(it, "choose_l2", "x")["correct"]
    _post("ko", "가방", "bag", "가방", "")                                        # Korean borrows Korean
    ex = engine.build_exercise(_item("ko", "가방"), "choose_l2", packs.get("my-ko"), 1)
    assert len(ex["choices"]) == 4 and all(engine.is_script(c) for c in ex["choices"])


def test_personal_cloze_over_http_is_scheduled_only_when_issued():
    _post("es", "rascar", "to scratch", "rascaba", "El gato rascaba la puerta.")
    _post("es", "gato", "cat", "gato", "El gato duerme.")
    assert client.post("/api/enroll", json={"course": "my-es", "on": True}).json()["ok"]
    a = reader.my_item_id("es", "rascar")
    st = state.get()
    for iid in (a, reader.my_item_id("es", "gato")):
        st["cards"][iid] = _card(3, 6.0)
    s = client.post("/api/session", json={"course": "my-es"}).json()
    ex = next(e for e in s["exercises"] if e["item"] == a)
    assert ex["mode"] == "cloze_type" and ex["prompt"] == "El gato ___ la puerta."
    r = client.post("/api/answer", json={"session": s["session"], "item": a, "mode": "cloze_type", "answer": "rascaba"}).json()
    assert r["correct"] and r["rewards"] and r["expected"] == "rascaba"
    assert state.get()["cards"][a]["reps"] == 4
    again = client.post("/api/answer", json={"session": s["session"], "item": a, "mode": "cloze_type", "answer": "rascaba"}).json()
    assert again["rewards"] == {} and state.get()["cards"][a]["reps"] == 4  # only the first answer counts
    _post("es", "perro", "dog", "perro", "Mi perro come.")                    # saved after the session was issued
    c = reader.my_item_id("es", "perro")
    r = client.post("/api/answer", json={"session": s["session"], "item": c, "mode": "cloze_type", "answer": "perro"}).json()
    assert r["correct"] and r["rewards"] == {} and c not in state.get()["cards"]
    wrong = client.post("/api/answer", json={"session": s["session"], "item": c, "mode": "cloze_type", "answer": "gato"}).json()
    assert not wrong["correct"] and c not in state.get()["cards"]


def test_rename_a_book(tmp_path, monkeypatch):
    b = client.post("/api/books", json={"title": "x", "text": BOOK}).json()["book"]
    assert client.put(f"/api/books/{b['id']}/title", json={"title": "  El\x07 mar  "}).json()["title"] == "El mar"
    assert client.get("/api/books").json()["books"][0]["title"] == "El mar"
    assert client.put(f"/api/books/{b['id']}/title", json={"title": "  "}).status_code == 400
    assert client.put("/api/books/0123456789ab/title", json={"title": "y"}).status_code == 404
    assert client.put("/api/books/ABCDEFABCDEF/title", json={"title": "y"}).status_code == 404
    r = client.put(f"/api/books/{b['id']}/title", json={"title": "z"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    monkeypatch.setenv("SECT_ACADEMY_FILE", str(tmp_path / "s.json"))
    state.reset_for_tests()
    d = client.post("/api/books", json={"title": "Uno", "text": BOOK}).json()["book"]
    assert client.put(f"/api/books/{d['id']}/title", json={"title": "Dos"}).json()["ok"]
    meta = json.loads((tmp_path / "s.json.books" / f"{d['id']}.json").read_text())
    assert meta["title"] == "Dos" and meta["chars"] == d["chars"]
    assert client.get(f"/api/books/{d['id']}").json()["text"] == BOOK.strip()
