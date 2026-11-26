"""The reader: dictionary lookup, your own words, and a book shelf.

* **Dictionaries** are per language: ``lexicon/`` holds a registry of lookup
  modules (Spanish today: ``lexicon/es.py``, data in ``dict/es/``, Wiktionary
  via doozan/spanish_data, CC BY-SA 4.0). This module routes to them and adds
  what the learner owns.
* **Your words** live in the state file, per language, sanitised and capped in
  ``state.py`` like everything else: ``dict_user`` ({lang: {word: meaning}},
  entries you add) and ``words`` ({lang: {word: {l1, form, ctx, ts}}}, words
  saved to learn). Each language's saved words form a personal course,
  "My words (Spanish)" (``my-es``), which ``packs`` serves next to the YAML
  courses — so FSRS schedules it, the engine grades it server-side, and it pays
  qi and insight like any other study. An item's id comes from the word itself
  (``my_item_id``), so its progress survives deleting and saving it again.
* **Books** can be megabytes, so their text never goes into the JSON state file:
  each book is two files in ``<state file>.books/`` (``<id>.txt`` and a small
  ``<id>.json``), written atomically; in ``:memory:`` mode (tests) they live in a
  dict. Only the reading position goes into the state (``book_pos``), so a phone
  and a PC open the book at the same place.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path

from . import engine, lexicon, packs, state

MAX_MEANING = 200
MAX_USER_ENTRIES = 3000       # per language
MAX_SAVED_WORDS = 3000        # per language
MAX_SEGMENT = 20000           # characters segmented in one request (a page is ~1500)

BOOK_MAX_CHARS = 4_000_000    # one book (a long novel is ~1-2 million characters)
BOOKS_MAX_BYTES = 64 * 1024 * 1024
BOOKS_MAX_COUNT = 200
BOOK_POST_MAX_BYTES = 20 * 1024 * 1024
LANGS = lexicon.LANGS
_BOOK_ID = re.compile(r"^[0-9a-f]{12}$")


def pack_id(lang: str) -> str:
    return f"my-{lang}"


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------
def clean_text(s, limit: int) -> str:
    """Untrusted text made safe to keep: no control characters (newlines and tabs stay), capped."""
    if not isinstance(s, str):
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(ch for ch in s[: limit * 2] if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return s[:limit]


def clean_line(s, limit: int) -> str:
    """One line of untrusted text (a title, a meaning): control characters out, spaces collapsed, capped."""
    return re.sub(r"\s+", " ", clean_text(s, limit * 2)).strip()[:limit]


# ---------------------------------------------------------------------------
# lookup (routed to the language's module)
# ---------------------------------------------------------------------------
def languages() -> dict:
    return {"ok": True, "langs": LANGS, "lookup": lexicon.available()}


def _mine(st: dict, lang: str) -> dict:
    return (st.get("dict_user") or {}).get(lang) or {}


def lookup(lang, raw, st: dict | None = None) -> dict:
    mod = lexicon.get(lang)
    if mod is None:
        return {"ok": True, "available": False, "found": False, "word": lexicon.generic_norm(raw), "senses": [], "also": [],
                "lang": lang if lexicon.valid_lang(lang) else "", "credit": ""}
    st = st if st is not None else state.get()
    out = mod.lookup(raw, _mine(st, lang))
    saved = (st.get("words") or {}).get(lang) or {}
    out.update(available=True, lang=lang,
               saved=bool(out.get("word")) and (out.get("lemma") in saved or out["word"] in saved))
    return out


def search(lang, q, direction: str = "from", limit: int = 40, st: dict | None = None) -> dict:
    mod = lexicon.get(lang)
    if mod is None:
        return {"ok": True, "available": False, "results": [], "credit": ""}
    st = st if st is not None else state.get()
    rows = mod.search(clean_line(q, 60), "en" if direction == "en" else "from", _mine(st, lang), limit)
    return {"ok": True, "available": True, "results": rows, "credit": mod.CREDIT}


def segment(lang, text) -> dict:
    """A page cut into tokens ({t, k}); a language without a module is split on spaces (read and hear, no lookup)."""
    text = clean_text(text, MAX_SEGMENT)
    mod = lexicon.get(lang)
    toks = mod.segment(text) if mod else lexicon.simple_segment(text)
    return {"ok": True, "available": mod is not None, "tokens": toks}


# ---------------------------------------------------------------------------
# your own entries and saved words (in the state file, per language)
# ---------------------------------------------------------------------------
def _per_lang(raw, clean_one) -> dict:
    out: dict[str, dict] = {}
    for lang, inner in (raw.items() if isinstance(raw, dict) else []):
        if lexicon.valid_lang(lang) and isinstance(inner, dict):
            got = clean_one(lang, inner)
            if got:
                out[lang] = got
    return out


def clean_user_entries(raw) -> dict:
    def one(lang, inner):
        out: dict[str, str] = {}
        for k, v in inner.items():
            w, m = lexicon.norm_word(lang, k), clean_line(v, MAX_MEANING)
            if w and m:
                out[w] = m
            if len(out) >= MAX_USER_ENTRIES:
                break
        return out
    return _per_lang(raw, one)


def clean_words(raw) -> dict:
    def one(lang, inner):
        out: dict[str, dict] = {}
        for k, v in inner.items():
            w = lexicon.norm_word(lang, k)
            if not w or not isinstance(v, dict):
                continue
            l1 = clean_line(v.get("l1"), MAX_MEANING)
            if not l1:
                continue
            ts = v.get("ts")
            out[w] = {"l1": l1, "form": lexicon.norm_word(lang, v.get("form")) or w, "ctx": clean_line(v.get("ctx"), 240),
                      "ts": float(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) and 0 <= ts < 1e11 else 0.0}
            if len(out) >= MAX_SAVED_WORDS:
                break
        return out
    return _per_lang(raw, one)


def clean_positions(raw) -> dict:
    out: dict[str, int] = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        if isinstance(k, str) and _BOOK_ID.match(k) and isinstance(v, int) and not isinstance(v, bool):
            out[k] = max(0, min(v, BOOK_MAX_CHARS))
        if len(out) >= BOOKS_MAX_COUNT * 2:
            break
    return out


_rev = [0]          # bumped on every change to saved words, so the personal courses are rebuilt


def _no_lookup(lang) -> dict | None:
    if lexicon.get(lang) is None:
        return {"ok": False, "error": "That language has no dictionary yet."}
    return None


def add_entry(lang, word, meaning) -> dict:
    bad = _no_lookup(lang)
    if bad:
        return bad
    w, m = lexicon.norm_word(lang, word), clean_line(meaning, MAX_MEANING)
    if not w or not m:
        return {"ok": False, "error": "A word and its meaning are both needed."}
    with state.LOCK:
        st = state.get()
        mine = st.setdefault("dict_user", {}).setdefault(lang, {})
        if w not in mine and len(mine) >= MAX_USER_ENTRIES:
            return {"ok": False, "error": f"You have {MAX_USER_ENTRIES} entries of your own; delete some first."}
        mine[w] = m
        state.save()
    return {"ok": True, "word": w, "meaning": m}


def delete_entry(lang, word) -> dict:
    with state.LOCK:
        st = state.get()
        mine = (st.get("dict_user") or {}).get(lang) or {}
        gone = mine.pop(lexicon.norm_word(lang, word), None) is not None
        state.save()
    return {"ok": True, "deleted": gone}


def my_item_id(lang: str, word: str) -> str:
    """A saved word's item id, stable for ever: ``my-<lang>-<word>`` when the word is plain a-z, otherwise
    an ASCII spelling (if any) plus a hash of the exact word, so "año" and "ano" never share progress."""
    if re.fullmatch(r"[a-z]{1,50}", word):
        return f"my-{lang}-{word}"
    folded = "".join(ch for ch in unicodedata.normalize("NFD", word) if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:40]
    h = hashlib.sha1(word.encode("utf-8")).hexdigest()[:8]
    return f"my-{lang}-{slug}-{h}" if slug else f"my-{lang}-{h}"


def save_word(lang, word, meaning, form="", ctx="", now: float | None = None) -> dict:
    bad = _no_lookup(lang)
    if bad:
        return bad
    w, m = lexicon.norm_word(lang, word), clean_line(meaning, MAX_MEANING)
    if not w or not m:
        return {"ok": False, "error": "A word and its meaning are both needed."}
    with state.LOCK:
        st = state.get()
        words = st.setdefault("words", {}).setdefault(lang, {})
        if w not in words and len(words) >= MAX_SAVED_WORDS:
            return {"ok": False, "error": f"You have saved {MAX_SAVED_WORDS} words; delete some first."}
        old = words.get(w) or {}
        words[w] = {"l1": m, "form": lexicon.norm_word(lang, form) or old.get("form") or w,
                    "ctx": clean_line(ctx, 240) or old.get("ctx", ""), "ts": old.get("ts") or (now or time.time())}
        _rev[0] += 1
        state.save()
    return {"ok": True, "word": w, "item": my_item_id(lang, w), "course": pack_id(lang), "count": len(words)}


def delete_word(lang, word) -> dict:
    with state.LOCK:
        st = state.get()
        words = (st.get("words") or {}).get(lang) or {}
        gone = words.pop(lexicon.norm_word(lang, word), None) is not None
        _rev[0] += 1
        state.save()
    return {"ok": True, "deleted": gone}


def list_words(lang, now: float | None = None) -> dict:
    now = now or time.time()
    with state.LOCK:
        st = state.get()
        rows = []
        mine = (st.get("words") or {}).get(lang) or {}
        for w, v in sorted(mine.items(), key=lambda kv: -kv[1]["ts"]):
            iid = my_item_id(lang, w)
            view = engine._card_view(st["cards"].get(iid), now)
            rows.append({"word": w, "l1": v["l1"], "form": v["form"], "ctx": v["ctx"], "ts": v["ts"], "item": iid,
                         "state": view["state"], "strength": view["strength"]})
        counts = {k: len(v) for k, v in (st.get("words") or {}).items() if v}
        return {"ok": True, "lang": lang, "words": rows, "course": pack_id(lang), "counts": counts,
                "enrolled": pack_id(lang) in st["settings"].get("courses", []), "max": MAX_SAVED_WORDS}


def build_pack(lang: str, words: dict) -> dict:
    """A personal course, in the shape ``packs`` gives every course (already normalised)."""
    pid, uid = pack_id(lang), f"{pack_id(lang)}-words"
    name = LANGS.get(lang, lang)
    romanise = getattr(lexicon.get(lang), "romanise", None)      # Korean: shown and accepted as an answer
    items = []
    for w, v in sorted(words.items(), key=lambda kv: (kv[1].get("ts", 0.0), kv[0])):
        it = {"id": my_item_id(lang, w), "type": "vocab", "l2": w, "l1": v["l1"], "alt": [], "unit": uid, "pack": pid}
        if romanise:
            it["rom"] = romanise(w)
        if v.get("ctx"):
            it["ex"] = v["ctx"]
            if romanise:
                it["ex_rom"] = romanise(v["ctx"])
        if v.get("form") and v["form"] != w:
            it["note"] = f"You met it as “{v['form']}”."
        items.append(it)
    return {"id": pid, "title": f"My words ({name})", "kind": "language", "language": name, "lang": lexicon.SPEECH.get(lang, ""),
            "hall": {"es": "tongues_south", "fr": "tongues_west", "ko": "tongues_west"}.get(lang, ""), "personal": True,
            "blurb": "Words you saved while reading, scheduled like any other course.",
            "units": [{"id": uid, "title": "Saved from your reading", "goal": "The words you chose to keep.",
                       "notes": "Every word here was saved from a book or the dictionary. Delete one in Read, My words.",
                       "index": 0, "domain": "", "items": items}]}


_busy = threading.local()


def _personal(prev):
    """packs' hook: (token, packs) when the saved words changed since ``prev``, else (prev, None)."""
    if getattr(_busy, "on", False):
        return prev, None
    _busy.on = True
    try:
        words = state.get().get("words")
        words = words if isinstance(words, dict) else {}
        if prev is not None and prev[0] is words and prev[1] == _rev[0]:
            return prev, None
        # The token holds the dict itself, so its identity cannot be reused while we compare against it.
        return (words, _rev[0]), {pack_id(lang): build_pack(lang, ws) for lang, ws in words.items() if ws}
    finally:
        _busy.on = False


packs.set_personal(_personal)


# ---------------------------------------------------------------------------
# books
# ---------------------------------------------------------------------------
_books_lock = threading.Lock()
_mem_books: dict[str, dict] = {}         # :memory: mode: id -> {"meta":..., "text":...}


def _dir() -> Path | None:
    p = state.path()
    return None if p == ":memory:" else Path(p + ".books")


def _clean_meta(m, bid: str) -> dict | None:
    if not isinstance(m, dict):
        return None
    lang = m.get("lang") if m.get("lang") in LANGS else "other"
    chars, size, added = m.get("chars"), m.get("bytes"), m.get("added")
    ok_num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0   # noqa: E731
    return {"id": bid, "title": clean_line(m.get("title"), 120) or "Untitled", "lang": lang,
            "chars": int(min(chars, BOOK_MAX_CHARS)) if ok_num(chars) else 0,
            "bytes": int(size) if ok_num(size) else 0, "added": float(added) if ok_num(added) else 0.0}


def _metas() -> list[dict]:
    d = _dir()
    if d is None:
        return [dict(b["meta"]) for b in _mem_books.values()]
    out = []
    if not d.is_dir():
        return out
    for f in d.glob("*.json"):
        bid = f.stem
        if not _BOOK_ID.match(bid) or not (d / f"{bid}.txt").is_file():
            continue
        try:
            meta = _clean_meta(json.loads(f.read_text(encoding="utf-8")), bid)
        except Exception:  # noqa: BLE001 — a damaged meta file hides that one book, nothing more
            continue
        if meta:
            out.append(meta)
    return out


def list_books() -> dict:
    with _books_lock:
        metas = sorted(_metas(), key=lambda m: -m["added"])
    with state.LOCK:
        pos = state.get().get("book_pos") or {}
        for m in metas:
            m["pos"] = int(pos.get(m["id"], 0))
            m["language"] = LANGS[m["lang"]]
    return {"ok": True, "books": metas, "used": sum(m["bytes"] for m in metas), "max_bytes": BOOKS_MAX_BYTES,
            "max_count": BOOKS_MAX_COUNT, "langs": LANGS, "lookup": lexicon.available()}


def _write(target: Path, text: str) -> None:
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)


def add_book(title, text, lang="es", now: float | None = None) -> dict:
    text = clean_text(text, BOOK_MAX_CHARS + 1)
    if len(text) > BOOK_MAX_CHARS:
        return {"ok": False, "error": f"That book is longer than {BOOK_MAX_CHARS:,} characters, the most one book can be."}
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(re.sub(r"\s", "", text)) < 20:
        return {"ok": False, "error": "No readable text was found in that file."}
    size = len(text.encode("utf-8"))
    meta = _clean_meta({"title": title, "lang": lang if lang in LANGS else "es", "chars": len(text), "bytes": size,
                        "added": now or time.time()}, uuid.uuid4().hex[:12])
    with _books_lock:
        metas = _metas()
        if len(metas) >= BOOKS_MAX_COUNT:
            return {"ok": False, "error": f"The shelf holds {BOOKS_MAX_COUNT} books; delete one first."}
        if sum(m["bytes"] for m in metas) + size > BOOKS_MAX_BYTES:
            return {"ok": False, "error": f"The shelf is full ({BOOKS_MAX_BYTES // (1024 * 1024)} MB of text); delete a book first."}
        d = _dir()
        if d is None:
            _mem_books[meta["id"]] = {"meta": meta, "text": text}
        else:
            try:
                d.mkdir(parents=True, exist_ok=True)
                _write(d / f"{meta['id']}.txt", text)               # the text first: a meta file never points at nothing
                _write(d / f"{meta['id']}.json", json.dumps({k: meta[k] for k in ("title", "lang", "chars", "bytes", "added")},
                                                            ensure_ascii=False))
            except OSError as e:
                return {"ok": False, "error": f"The book could not be saved ({e.strerror or e})."}
    return {"ok": True, "book": meta}


def get_book(bid: str) -> dict | None:
    if not isinstance(bid, str) or not _BOOK_ID.match(bid):
        return None
    with _books_lock:
        d = _dir()
        if d is None:
            b = _mem_books.get(bid)
            meta, text = (dict(b["meta"]), b["text"]) if b else (None, None)
        else:
            try:
                meta = _clean_meta(json.loads((d / f"{bid}.json").read_text(encoding="utf-8")), bid)
                text = clean_text((d / f"{bid}.txt").read_text(encoding="utf-8"), BOOK_MAX_CHARS)
            except Exception:  # noqa: BLE001
                return None
    if not meta:
        return None
    with state.LOCK:
        meta["pos"] = int((state.get().get("book_pos") or {}).get(bid, 0))
    meta["language"] = LANGS[meta["lang"]]
    meta["lookup"] = lexicon.get(meta["lang"]) is not None
    return {"ok": True, "book": meta, "text": text}


def set_position(bid: str, pos) -> dict:
    if not isinstance(bid, str) or not _BOOK_ID.match(bid) or not isinstance(pos, int) or isinstance(pos, bool):
        return {"ok": False, "error": "unknown book"}
    with _books_lock:
        known = {m["id"] for m in _metas()}
    if bid not in known:
        return {"ok": False, "error": "unknown book"}
    with state.LOCK:
        st = state.get()
        bp = st.setdefault("book_pos", {})
        bp[bid] = max(0, min(pos, BOOK_MAX_CHARS))
        if len(bp) > BOOKS_MAX_COUNT * 2:
            for old in list(bp)[: len(bp) - BOOKS_MAX_COUNT * 2]:
                bp.pop(old, None)
        state.save()
    return {"ok": True, "pos": bp[bid]}


def delete_book(bid: str) -> dict:
    if not isinstance(bid, str) or not _BOOK_ID.match(bid):
        return {"ok": False, "error": "unknown book"}
    with _books_lock:
        d = _dir()
        if d is None:
            found = _mem_books.pop(bid, None) is not None
        else:
            found = False
            for ext in ("json", "txt"):                        # the meta first: a half-deleted book is simply hidden
                try:
                    (d / f"{bid}.{ext}").unlink()
                    found = True
                except FileNotFoundError:
                    pass
    with state.LOCK:
        (state.get().get("book_pos") or {}).pop(bid, None)
        state.save()
    return {"ok": True, "deleted": found}


def reset_for_tests() -> None:
    with _books_lock:
        _mem_books.clear()
    _rev[0] += 1
