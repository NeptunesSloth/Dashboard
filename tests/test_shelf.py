"""The starter shelf (sect_academy/shelf/): public-domain texts and poems shipped with the app.

Every entry must be valid, public domain by the shelf's rule (with its evidence), present, clean UTF-8
with no archive licence text left in it, and reachable through the books API under a safe id — and no
hostile id may reach a file or the state."""
import re
import unicodedata
import urllib.parse

import pytest
import yaml
from fastapi.testclient import TestClient

from sect_academy import reader, state
from sect_academy.app import app

client = TestClient(app)
SHELF = reader.SHELF_DIR
MANIFEST = yaml.safe_load((SHELF / "manifest.yaml").read_text(encoding="utf-8"))
ENTRIES = reader.load_shelf()["entries"]
POEM_FILES = {lang: yaml.safe_load((SHELF / rel).read_text(encoding="utf-8")) for lang, rel in MANIFEST["poems"].items()}


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    monkeypatch.delenv("SECT_ACADEMY_TOKEN", raising=False)
    state.reset_for_tests()
    reader.reset_for_tests()
    yield
    state.reset_for_tests()


def test_the_shelf_loads_clean():
    assert reader.load_shelf()["errors"] == []


def test_every_language_has_three_to_five_texts_and_its_poems():
    for lang in reader.SHELF_LANGS:
        texts = [e for e in ENTRIES if e["lang"] == lang and e["kind"] == "text"]
        assert 3 <= len(texts) <= 5, lang
        poems = sum(len([x for x in p["lines"] if x]) if p["slug"].startswith("haiku") else 1
                    for p in POEM_FILES[lang]["poems"])
        assert poems >= 8, lang        # the haiku set counts one per haiku


def test_every_listed_text_file_exists_and_every_file_is_listed():
    listed = {f"{t['lang']}/{t['slug']}.txt" for t in MANIFEST["texts"]}
    on_disk = {str(p.relative_to(SHELF)) for p in SHELF.glob("*/*.txt")}
    assert listed == on_disk
    assert {str(p.relative_to(SHELF)) for p in SHELF.glob("*/*.yaml")} == set(MANIFEST["poems"].values())


def _all_records():
    for t in MANIFEST["texts"]:
        yield t
    for lang, doc in POEM_FILES.items():
        for p in doc["poems"]:
            yield dict(p, lang=lang)


@pytest.mark.parametrize("rec", list(_all_records()), ids=lambda r: f"{r['lang']}:{r['slug']}")
def test_public_domain_evidence(rec):
    for f in ("title", "author", "died", "published", "first_published_in", "source", "public_domain", "level"):
        assert rec.get(f) not in (None, ""), f
    assert isinstance(rec["died"], int) and isinstance(rec["published"], int)
    assert rec["died"] < 1955
    if rec["published"] >= 1931:                         # outside the safe rule: the case must be argued
        assert len(rec.get("pd_exception") or "") > 80
    host = urllib.parse.urlsplit(rec["source"]).hostname
    assert host in {"es.wikisource.org", "fr.wikisource.org", "zh.wikisource.org", "ja.wikisource.org",
                    "ko.wikisource.org", "www.aozora.gr.jp"}
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", rec["slug"])


@pytest.mark.parametrize("path", sorted(SHELF.glob("*/*.txt")), ids=lambda p: p.name)
def test_texts_are_clean_utf8_with_no_archive_boilerplate(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8")                           # strict: raises on anything not UTF-8
    assert not raw.startswith(b"\xef\xbb\xbf") and "\ufeff" not in text and "\r" not in text
    assert all(ch in "\n\t" or not unicodedata.category(ch).startswith("C") for ch in text)
    low = text.lower()
    for bad in ("gutenberg", "project gutenberg", "licence", "license", "wikisource", "creative commons", "www.", "http",
                "青空文庫", "底本", "入力：", "校正：", "라이선스", "위키문헌", "维基文库", "維基文庫", "［＃"):
        assert bad not in low, bad
    if path.parent.name == "ja":
        assert "《" not in text and "｜" not in text        # Aozora ruby markup is gone
    assert 300 <= len(text) <= reader.SHELF_TEXT_MAX
    assert sum(p.stat().st_size for p in SHELF.rglob("*") if p.is_file()) < 3 * 1024 * 1024


def test_poem_lines_have_a_translation_and_readings_where_needed():
    for lang, doc in POEM_FILES.items():
        for p in doc["poems"]:
            width = 3 if lang in ("zh", "ja", "ko") else 2
            lines = [x for x in p["lines"] if x]
            assert lines and all(len(x) == width and all(isinstance(s, str) and s.strip() for s in x) for x in lines), p["slug"]
            if lang == "zh":       # pinyin: one syllable per character
                for t, r, _ in lines:
                    assert len(re.findall(r"[\u4e00-\u9fff]", t)) == len(re.findall(r"[^\W\d_]+", r)), t
            if lang == "ja":       # kana | rōmaji
                assert all(" | " in r for _, r, _ in lines), p["slug"]


def test_ids_are_safe_and_unique():
    ids = [e["id"] for e in ENTRIES]
    assert len(ids) == len(set(ids)) and len(ids) <= reader.SHELF_MAX
    for i in ids:
        assert reader._SHELF_ID.match(i) and "/" not in i and ".." not in i


def test_the_api_lists_the_shelf_apart_from_the_users_books():
    r = client.get("/api/books").json()
    assert r["books"] == [] and r["used"] == 0                  # not counted against the user's caps
    assert {e["id"] for e in r["shelf"]} == {e["id"] for e in ENTRIES}
    assert all("text" not in e for e in r["shelf"])
    assert reader._dir() is None or not reader._dir().exists()  # nothing was copied anywhere


def test_a_text_opens_with_lookup_and_keeps_its_position():
    sid = "shelf:es:quiroga-la-tortuga-gigante"
    r = client.get(f"/api/books/{urllib.parse.quote(sid)}").json()
    assert r["book"]["readonly"] and r["book"]["lang"] == "es" and r["book"]["lookup"]
    assert r["text"].startswith("Había una vez") and "lines" not in r
    assert client.put(f"/api/books/{urllib.parse.quote(sid)}/pos", json={"pos": 1500}).json()["pos"] == 1500
    assert state.get()["book_pos"][sid] == 1500
    assert client.get(f"/api/books/{sid}").json()["book"]["pos"] == 1500
    assert {e["id"]: e["pos"] for e in client.get("/api/books").json()["shelf"]}[sid] == 1500
    st = state.sanitize({"cards": {}, "book_pos": dict(state.get()["book_pos"])})
    assert st["book_pos"][sid] == 1500                           # survives a reload of the state


def test_a_poem_opens_with_its_lines():
    r = client.get("/api/books/shelf:zh:li-bai-jing-ye-si").json()
    assert r["book"]["kind"] == "poem"
    assert r["text"] == "\n".join(x["t"] for x in r["lines"])
    assert r["lines"][0] == {"t": "床前明月光，", "r": "chuáng qián míng yuè guāng,", "en": "Before my bed, bright moonlight;"}
    fr = client.get("/api/books/shelf:fr:verlaine-chanson-d-automne").json()
    assert fr["lines"][6] == {"t": "", "r": "", "en": ""}        # a stanza break
    assert all(x["r"] == "" for x in fr["lines"])


@pytest.mark.parametrize("bad", [
    "shelf:es:../../etc/passwd", "shelf:es:..%2F..%2Fmanifest", "shelf:xx:quiroga-la-tortuga-gigante",
    "shelf:es:Quiroga", "shelf:es:no-such-text", "shelf:es:", "shelf::x", "shelf:es:a--b", "shelf:es:x/y",
    "shelf:es:quiroga-la-tortuga-gigante.txt", "shelf%3Aes%3Aquiroga-la-tortuga-gigante%00",
])
def test_hostile_shelf_ids_are_refused(bad):
    assert client.get(f"/api/books/{bad}").status_code == 404
    assert client.put(f"/api/books/{bad}/pos", json={"pos": 1}).status_code == 404
    assert reader.get_book(urllib.parse.unquote(bad)) is None


def test_shelf_entries_cannot_be_renamed_or_deleted():
    sid = "shelf:fr:maupassant-la-parure"
    assert client.put(f"/api/books/{sid}/title", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/books/{sid}").status_code == 404
    assert client.get(f"/api/books/{sid}").json()["book"]["title"] == "La Parure"


def test_state_sanitising_keeps_only_safe_position_keys():
    st = state.sanitize({"cards": {}, "book_pos": {
        "shelf:es:quiroga-la-abeja-haragana": 40, "shelf:es:../x": 1, "shelf:zz:a": 1, "shelf:es:A": 1,
        "shelf:ja:" + "a" * 300: 1, "0123456789ab": 3, "shelf:ko:x": True}})
    assert st["book_pos"] == {"shelf:es:quiroga-la-abeja-haragana": 40, "0123456789ab": 3}
