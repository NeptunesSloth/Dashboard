"""Content packs: load + validate the curated YAML courses in ``packs/``.

A pack is one course (a language level or a certification). Schema — see
``docs/ACADEMY_CONTENT.md`` for the authoring guide:

    id, title, kind (language|cert), blurb, hall
    language packs:  language, lang (BCP-47 speech tag, e.g. fr-FR),
                     track? + (level? | addon?)  — see "Tracks" below
    cert packs:      exam {name, code, questions, minutes, pass_pct,
                           domains: [{id, title, weight}]}
    units: [{id, title, goal, notes, domain?, items: [...]}]

Item types:
    vocab / phrase  {id, type, l2, l1, alt?, note?, ex?, ex_l1?}
    cloze           {id, type, text (one ``___``), answer, alt?, l1?, note?}
    concept         {id, type, term, def, note?}
    dialogue        {id, type, title, scene, you (A|B), lines [{who, l2, l1, alt?}]}
    mcq             {id, type, q, choices[4], answer (index), why, best?, whys?}
    multi           {id, type, q, choices[5-6], answers [2-3 indices], why}   "choose TWO/THREE"
    order           {id, type, q, steps [3-6, in the correct order], why}
    picture         {id, type, picture (an id in packs/pictures/), pins {pin id: {l2, rom?, alt?, l1?, note?}}}
                    Each pin is expanded at load time into its own scheduled item, type ``pin``,
                    id ``<item id>-<pin id>``. A unit holding a picture whose painting
                    (static/art/pic_<picture>.webp) is missing is held back as "coming soon".

A course can be split over several files: a *part* file holds only
``part_of: <pack id>`` and ``units: [...]``; its units are appended to that pack
(in filename order). This is how large courses are authored in parallel.

Tracks: the levels of one language are one long course to the learner. A language
pack with ``track: french`` and ``level: A1`` (A1, A2, B1, B2, C1, C2) is a *stage* of
the track ``french``; stages are ordered by level. A pack with ``track: french`` and
``addon: talk`` is an *add-on* of the track (conversations, picture lessons): it is
taken up on its own and is never a stage. Pack and item ids are unchanged by this —
a track is only a grouping (``tracks()``); enrolment and progress stay per pack.

Run ``python -m sect_academy.packs`` to validate every pack.
"""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

import yaml

PACK_DIR = Path(__file__).parent / "packs"
KINDS = ("language", "cert")
ITEM_TYPES = ("vocab", "phrase", "cloze", "dialogue", "glyph", "concept", "mcq", "multi", "order", "picture")
CERT_TYPES = ("concept", "mcq", "multi", "order")
_ID = re.compile(r"^[a-z0-9][a-z0-9_.\-]{1,63}$")
_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)      # the C loader is ~10x faster when present
_lock = threading.Lock()
_files: dict[str, dict] | None = None      # the courses in packs/*.yaml
_cache: dict[str, dict] | None = None      # those plus the personal course (see set_personal)
_index: dict[str, dict] | None = None
_personal_fn = None
_personal_token = None
_personal: dict[str, dict] = {}
PERSONAL_PREFIX = "my-"                    # item ids the YAML courses may not use: they belong to personal courses
ART_DIR = Path(__file__).parent / "static" / "art"     # where a picture's painting (pic_<id>.webp) lives
_PIC_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_PIN_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_PIN_KEYS = {"l2", "rom", "alt", "l1", "note"}
_pictures_cache: tuple | None = None       # (PACK_DIR, pictures, errors)
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")     # the stages of a track, in order
_TRACK_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_ADDON_ID = re.compile(r"^[a-z][a-z0-9_]{1,23}$")
_tracks: dict[str, dict] | None = None     # built from _files (see tracks())


def _s(v) -> str:
    return v.strip() if isinstance(v, str) else ""


# ---------------------------------------------------------------------------
# picture lessons: shared pictures (packs/pictures/<id>.yaml) and the per-language
# ``picture`` items that name each pin
# ---------------------------------------------------------------------------
def _script(s: str) -> bool:
    """Chinese characters, kana or hangul (the same test as engine.is_script)."""
    return any(ord(ch) >= 0x2E80 for ch in str(s or ""))


def _coord(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100


def validate_picture(pic, source: str = "") -> list[str]:
    """A shared picture: {id, title, brief?, pins: [{id, x, y, en}]} (x, y in percent of the image)."""
    w = f"{source}: " if source else ""
    if not isinstance(pic, dict):
        return [w + "picture is not a mapping"]
    errs: list[str] = []
    pid = _s(pic.get("id"))
    if not _PIC_ID.match(pid):
        errs.append(w + f"bad picture id {pid!r} (lowercase letters, digits, _)")
    if not _s(pic.get("title")):
        errs.append(w + f"picture {pid}: missing title")
    extra = set(pic) - {"id", "title", "brief", "pins"}
    if extra:
        errs.append(w + f"picture {pid}: unknown keys {sorted(extra)}")
    if "brief" in pic and not _s(pic.get("brief")):
        errs.append(w + f"picture {pid}: brief must be text")
    pins = pic.get("pins")
    if not isinstance(pins, list) or not 4 <= len(pins) <= 16:
        return errs + [w + f"picture {pid}: needs 4-16 pins"]
    seen: set[str] = set()
    for pin in pins:
        if not isinstance(pin, dict):
            errs.append(w + f"picture {pid}: a pin is not a mapping")
            continue
        qid = _s(pin.get("id"))
        if not _PIN_ID.match(qid) or qid in seen:
            errs.append(w + f"picture {pid}: bad/duplicate pin id {qid!r}")
        seen.add(qid)
        if not _coord(pin.get("x")) or not _coord(pin.get("y")):
            errs.append(w + f"picture {pid}: pin {qid}: x and y must be numbers from 0 to 100 (percent of the image)")
        if not _s(pin.get("en")):
            errs.append(w + f"picture {pid}: pin {qid}: needs en (the English word)")
        if set(pin) - {"id", "x", "y", "en"}:
            errs.append(w + f"picture {pid}: pin {qid}: unknown keys {sorted(set(pin) - {'id', 'x', 'y', 'en'})}")
    return errs


def pictures() -> dict[str, dict]:
    """The shared picture definitions (valid ones only), by id."""
    return _load_pictures()[0]


def _load_pictures() -> tuple[dict[str, dict], list[str]]:
    global _pictures_cache
    if _pictures_cache is not None and _pictures_cache[0] == PACK_DIR:
        return _pictures_cache[1], _pictures_cache[2]
    out: dict[str, dict] = {}
    errs: list[str] = []
    for path in sorted((PACK_DIR / "pictures").glob("*.yaml")):
        pic = _read(path)
        e = validate_picture(pic, f"pictures/{path.name}")
        if not e and pic["id"] != path.stem:
            e = [f"pictures/{path.name}: the file must be named after the picture id ({pic['id']}.yaml)"]
        errs += e
        if not e:
            out[pic["id"]] = pic
    _pictures_cache = (PACK_DIR, out, errs)
    return out, errs


def painted(picture_id: str) -> bool:
    """Is this picture's painting in static/art? Only a known picture id is ever made into a path."""
    return picture_id in pictures() and (ART_DIR / f"pic_{picture_id}.webp").is_file()


def _validate_picture_item(it: dict, iid: str, kind, err, seen_items: set[str]) -> None:
    """Check a ``picture`` item against its shared definition."""
    if kind != "language":
        err(f"item {iid}: picture items belong in language packs")
        return
    extra = set(it) - {"id", "type", "picture", "pins"}
    if extra:
        err(f"item {iid}: a picture item has only id, type, picture and pins (found {sorted(extra)})")
    pic = pictures().get(_s(it.get("picture")))
    if pic is None:
        err(f"item {iid}: picture {it.get('picture')!r} is not defined in packs/pictures/")
        return
    pins = it.get("pins")
    if not isinstance(pins, dict) or len(pins) < 4:
        err(f"item {iid}: pins must map at least 4 pin ids of picture {pic['id']} to their words")
        return
    known = {p["id"] for p in pic["pins"]}
    words: set[str] = set()
    for qid, pin in pins.items():
        where = f"item {iid}: pin {qid!r}"
        if qid not in known:
            err(f"{where}: not a pin of picture {pic['id']} ({', '.join(sorted(known))})")
            continue
        pid = f"{iid}-{qid}"
        if not _ID.match(pid) or pid in seen_items:
            err(f"{where}: item id {pid!r} is too long or already used")
        seen_items.add(pid)
        if not isinstance(pin, dict) or not _s(pin.get("l2")):
            err(f"{where}: needs l2 (the word in the language)")
            continue
        if set(pin) - _PIN_KEYS:
            err(f"{where}: unknown keys {sorted(set(pin) - _PIN_KEYS)}")
        l2 = _s(pin["l2"])
        if l2.lower() in words:
            err(f"{where}: l2 {l2!r} is used by another pin of this picture")
        words.add(l2.lower())
        for key in ("rom", "l1", "note"):
            if key in pin and not _s(pin.get(key)):
                err(f"{where}: {key} must be a non-empty string")
        if _script(l2) and not _s(pin.get("rom")):
            err(f"{where}: rom is required when l2 is written in Chinese, Japanese or Korean script")
        alt = pin.get("alt", [])
        if not isinstance(alt, list) or not all(isinstance(a, str) and a.strip() for a in alt):
            err(f"{where}: alt must be a list of strings")


def item_ids(it) -> list[str]:
    """The scheduled item ids an authored item becomes (a picture: one per pin)."""
    if isinstance(it, dict) and it.get("type") == "picture" and isinstance(it.get("pins"), dict):
        return [f"{_s(it.get('id'))}-{q}" for q in it["pins"]]
    return [it.get("id")] if isinstance(it, dict) else []


def _expand_pictures(pack: dict) -> dict:
    """Replace each ``picture`` item by its pins: one ``pin`` item each, numbered in picture order."""
    defs = pictures()
    for u in pack["units"]:
        out = []
        for it in u["items"]:
            if it.get("type") != "picture":
                out.append(it)
                continue
            pic = defs[it["picture"]]
            n = 0
            for p in pic["pins"]:
                mine = it["pins"].get(p["id"])
                if mine is None:
                    continue
                n += 1
                pin = {"id": f"{it['id']}-{p['id']}", "type": "pin", "l2": _s(mine["l2"]),
                       "l1": _s(mine.get("l1")) or p["en"], "alt": [a.strip() for a in mine.get("alt", [])],
                       "picture": pic["id"], "picture_title": pic["title"], "group": it["id"], "pin": p["id"],
                       "n": n, "x": float(p["x"]), "y": float(p["y"])}
                for key in ("rom", "note"):
                    if _s(mine.get(key)):
                        pin[key] = _s(mine[key])
                out.append(pin)
        u["items"] = out
    return pack


def _hold_back_unpainted(pack: dict) -> dict:
    """A unit with a picture that has not been painted yet is taken out of the course and
    listed in ``pack["soon"]``, so nothing ever asks for an image that does not exist.
    Progress is keyed by item id, so the unit's cards wait untouched until the painting lands."""
    keep, soon = [], []
    for u in pack["units"]:
        missing = sorted({it["picture"] for it in u["items"] if it["type"] == "pin" and not painted(it["picture"])})
        if missing:
            soon.append({"id": u["id"], "title": u["title"], "goal": u.get("goal", ""), "pictures": missing})
        else:
            keep.append(u)
    for i, u in enumerate(keep):
        u["index"] = i
    pack["units"] = keep
    pack["soon"] = soon
    return pack


def _validate_units(units, kind, domains: set[str], err, seen_units: set[str], seen_items: set[str]) -> None:
    if not isinstance(units, list) or not units:
        err("no units")
        return
    for u in units:
        if not isinstance(u, dict):
            err("unit is not a mapping")
            continue
        uid = _s(u.get("id"))
        if not _ID.match(uid) or uid in seen_units:
            err(f"bad/duplicate unit id {uid!r}")
        seen_units.add(uid)
        for key in ("title", "goal", "notes"):
            if not _s(u.get(key)):
                err(f"unit {uid}: missing {key}")
        if kind == "cert" and str(u.get("domain", "")) not in domains:
            err(f"unit {uid}: domain {u.get('domain')!r} not in exam.domains")
        items = u.get("items")
        if not isinstance(items, list) or sum(len(item_ids(it)) for it in items) < 4:
            err(f"unit {uid}: needs at least 4 items")
            continue
        for it in items:
            if not isinstance(it, dict):
                err(f"unit {uid}: item is not a mapping")
                continue
            iid = _s(it.get("id"))
            if not _ID.match(iid) or iid in seen_items:
                err(f"unit {uid}: bad/duplicate item id {iid!r}")
            elif iid.startswith(PERSONAL_PREFIX):
                err(f"item {iid}: ids starting {PERSONAL_PREFIX!r} are kept for the learner's own words")
            seen_items.add(iid)
            t = it.get("type")
            if t not in ITEM_TYPES:
                err(f"item {iid}: type must be one of {ITEM_TYPES}")
                continue
            if t == "picture":
                _validate_picture_item(it, iid, kind, err, seen_items)
                continue
            if kind == "language" and t in CERT_TYPES:
                err(f"item {iid}: {t} items belong in cert packs")
            if kind == "cert" and t not in CERT_TYPES:
                err(f"item {iid}: {t} items belong in language packs")
            if "rom" in it and not _s(it.get("rom")):
                err(f"item {iid}: rom must be a non-empty string (the romanisation of l2)")
            if t == "glyph":
                if kind != "language" or not _s(it.get("l2")) or not _s(it.get("rom")):
                    err(f"item {iid}: glyph needs l2 (the character) and rom (how it is read), in a language pack")
            if t in ("vocab", "phrase"):
                if not _s(it.get("l2")) or not _s(it.get("l1")):
                    err(f"item {iid}: needs l2 and l1")
            elif t == "cloze":
                text = _s(it.get("text"))
                if text.count("___") != 1:
                    err(f"item {iid}: text needs exactly one ___ blank")
                if not _s(it.get("answer")):
                    err(f"item {iid}: needs answer")
                if not _s(it.get("l1")):
                    err(f"item {iid}: needs l1 (English meaning of the full sentence)")
            elif t == "dialogue":
                lines = it.get("lines")
                if not _s(it.get("title")) or not _s(it.get("scene")) or it.get("you") not in ("A", "B"):
                    err(f"item {iid}: needs title, scene and you (A or B)")
                if not isinstance(lines, list) or not 4 <= len(lines) <= 12 or not all(
                        isinstance(ln, dict) and ln.get("who") in ("A", "B") and _s(ln.get("l2")) and _s(ln.get("l1"))
                        and isinstance(ln.get("alt", []), list) and all(isinstance(a, str) and a.strip() for a in ln.get("alt", []))
                        for ln in lines):
                    err(f"item {iid}: needs 4-12 lines, each with who (A|B), l2 and l1 (alt optional)")
                elif sum(1 for ln in lines if ln["who"] == it.get("you")) < 2:
                    err(f"item {iid}: the learner needs at least two lines")
            elif t == "concept":
                if not _s(it.get("term")) or not _s(it.get("def")):
                    err(f"item {iid}: needs term and def")
            elif t in ("mcq", "multi"):
                ch = it.get("choices")
                lo, hi = (4, 4) if t == "mcq" else (5, 6)
                if not _s(it.get("q")) or not isinstance(ch, list) or not lo <= len(ch) <= hi \
                        or not all(str(c).strip() for c in ch):
                    err(f"item {iid}: needs q and {'exactly 4' if t == 'mcq' else '5-6'} choices")
                elif len({str(c).strip().lower() for c in ch}) != len(ch):
                    err(f"item {iid}: duplicate choices")
                if t == "mcq":
                    if not isinstance(it.get("answer"), int) or isinstance(it.get("answer"), bool) \
                            or not 0 <= it.get("answer", -1) <= 3:
                        err(f"item {iid}: answer must be a 0-3 index")
                else:
                    ans = it.get("answers")
                    n = len(ch) if isinstance(ch, list) else 0
                    if not isinstance(ans, list) or not 2 <= len(ans) <= 3 or len(set(ans)) != len(ans) \
                            or not all(isinstance(a, int) and not isinstance(a, bool) and 0 <= a < n for a in ans):
                        err(f"item {iid}: answers must be 2-3 distinct choice indices")
                if not _s(it.get("why")):
                    err(f"item {iid}: needs why (the explanation)")
                whys = it.get("whys")
                if whys is not None and not (isinstance(whys, list) and isinstance(ch, list) and len(whys) == len(ch)
                                             and all(isinstance(x, str) and x.strip() for x in whys)):
                    err(f"item {iid}: whys must give one explanation per choice, in choice order")
                if it.get("best") and whys is None:
                    err(f"item {iid}: a best-answer question needs whys (why each choice is weaker or best)")
            elif t == "order":
                steps = it.get("steps")
                if not _s(it.get("q")) or not isinstance(steps, list) or not 3 <= len(steps) <= 6 \
                        or not all(isinstance(x, str) and x.strip() for x in steps):
                    err(f"item {iid}: needs q and 3-6 steps (strings, in the correct order)")
                elif len({x.strip().lower() for x in steps}) != len(steps):
                    err(f"item {iid}: duplicate steps")
                if not _s(it.get("why")):
                    err(f"item {iid}: needs why (the explanation)")
            alt = it.get("alt", [])
            if not isinstance(alt, list) or not all(isinstance(a, str) and a.strip() for a in alt):
                err(f"item {iid}: alt must be a list of strings")


def _validate_track_fields(pack: dict, kind, err) -> None:
    """``track`` with exactly one of ``level`` (a stage) or ``addon`` (an add-on), language packs only."""
    has = [k for k in ("track", "level", "addon") if k in pack]
    if not has:
        return
    if kind != "language":
        err("track, level and addon belong to language packs")
        return
    if pack.get("personal"):
        err("a personal course is never part of a track")
    track = pack.get("track")
    if not isinstance(track, str) or not _TRACK_ID.match(track):
        err(f"track must be a short lowercase id (e.g. french), not {track!r}")
    if ("level" in pack) == ("addon" in pack):
        err("a track pack needs exactly one of level (a stage: A1-C2) or addon (e.g. talk)")
    if "level" in pack and pack.get("level") not in LEVELS:
        err(f"level must be one of {LEVELS}, not {pack.get('level')!r}")
    if "addon" in pack and not (isinstance(pack.get("addon"), str) and _ADDON_ID.match(pack["addon"])):
        err(f"addon must be a short lowercase id (e.g. talk), not {pack.get('addon')!r}")


def build_tracks(all_packs: dict[str, dict]) -> tuple[dict[str, dict], list[str]]:
    """Group the packs that name a ``track`` into ordered tracks. Returns (tracks, problems).

    A track is {id, language, lang, stages: [pack ids by level], levels: [...], addons: [pack ids]}.
    A pack that would clash (a second pack at the same level, another language, a track id that
    is also a pack id) is left out of the track and reported, so a bad file never breaks the rest."""
    out: dict[str, dict] = {}
    errs: list[str] = []
    for pid in sorted(all_packs):
        p = all_packs[pid]
        tid = p.get("track")
        if p.get("kind") != "language" or p.get("personal") or not isinstance(tid, str) or not _TRACK_ID.match(tid):
            continue
        if tid in all_packs:
            errs.append(f"{pid}: track {tid!r} is also a pack id")
            continue
        t = out.setdefault(tid, {"id": tid, "language": p.get("language", ""), "lang": p.get("lang", ""),
                                 "stages": [], "levels": [], "addons": []})
        if p.get("lang") != t["lang"] or p.get("language") != t["language"]:
            errs.append(f"{pid}: track {tid} is {t['language']} ({t['lang']}), this pack is {p.get('language')} ({p.get('lang')})")
            continue
        level, addon = p.get("level"), p.get("addon")
        if level in LEVELS and not addon:
            if level in t["levels"]:
                errs.append(f"{pid}: track {tid} already has a level {level} stage")
                continue
            t["levels"].append(level)
            t["stages"].append(pid)
        elif isinstance(addon, str) and level is None:
            t["addons"].append(pid)
    for t in out.values():
        order = sorted(range(len(t["levels"])), key=lambda i: LEVELS.index(t["levels"][i]))
        t["levels"] = [t["levels"][i] for i in order]
        t["stages"] = [t["stages"][i] for i in order]
    return {k: v for k, v in out.items() if v["stages"] or v["addons"]}, errs


def tracks() -> dict[str, dict]:
    """The language tracks (see "Tracks" above), by track id, from the YAML courses."""
    global _tracks
    load_all()
    with _lock:
        if _tracks is None:
            _tracks = build_tracks(_files or {})[0]
        return _tracks


def track_of(pack_id: str) -> tuple[dict | None, str]:
    """(track, "stage" | "addon") for a pack in a track, else (None, "")."""
    for t in tracks().values():
        if pack_id in t["stages"]:
            return t, "stage"
        if pack_id in t["addons"]:
            return t, "addon"
    return None, ""


def validate_pack(pack, source: str = "", base: dict | None = None) -> list[str]:
    """Return a list of human-readable problems (empty = valid).

    A part file (``part_of``) is validated against its ``base`` pack's kind and
    exam domains; pass the loaded base pack."""
    errs: list[str] = []
    w = f"{source}: " if source else ""

    def err(msg: str) -> None:
        errs.append(w + msg)

    if not isinstance(pack, dict):
        return [w + "pack is not a mapping"]
    if "part_of" in pack:
        if not isinstance(base, dict):
            return [w + f"part_of {pack.get('part_of')!r}: base pack not found"]
        extra = set(pack) - {"part_of", "units"}
        if extra:
            err(f"a part file may only contain part_of and units (found {sorted(extra)})")
        domains = {str(d["id"]) for d in (base.get("exam") or {}).get("domains", [])}
        seen_units = {u["id"] for u in base.get("units", [])}
        seen_items = {iid for u in base.get("units", []) for it in u["items"] for iid in item_ids(it)}
        _validate_units(pack.get("units"), base.get("kind"), domains, err, seen_units, seen_items)
        return errs
    pid = _s(pack.get("id"))
    if not _ID.match(pid):
        err(f"bad pack id {pid!r}")
    for key in ("title", "blurb", "hall"):
        if not _s(pack.get(key)):
            err(f"missing {key}")
    kind = pack.get("kind")
    if kind not in KINDS:
        err(f"kind must be one of {KINDS}")
    if kind == "language":
        if not _s(pack.get("language")) or not re.match(r"^[a-z]{2}-[A-Z]{2}$", _s(pack.get("lang"))):
            err("language packs need language + lang (e.g. fr-FR)")
    _validate_track_fields(pack, kind, err)
    domains: set[str] = set()
    if kind == "cert":
        exam = pack.get("exam")
        if not isinstance(exam, dict):
            err("cert packs need an exam block")
        else:
            for key in ("name", "code"):
                if not _s(exam.get(key)):
                    err(f"exam.{key} missing")
            for key in ("questions", "minutes", "pass_pct"):
                if not isinstance(exam.get(key), int) or exam.get(key) <= 0:
                    err(f"exam.{key} must be a positive int")
            full = exam.get("full")
            if full is not None and not (isinstance(full, dict) and all(
                    isinstance(full.get(k), int) and full.get(k) > 0 for k in ("questions", "minutes"))):
                err("exam.full must be {questions, minutes}")
            doms = exam.get("domains") or []
            if not doms:
                err("exam.domains missing")
            for d in doms:
                if not isinstance(d, dict) or not _s(str(d.get("id", ""))) or not _s(d.get("title")) \
                        or not isinstance(d.get("weight"), (int, float)):
                    err(f"bad exam domain {d!r}")
                else:
                    domains.add(str(d["id"]))
            total = sum(d.get("weight", 0) for d in doms if isinstance(d, dict))
            if doms and abs(total - 100) > 0.5:
                err(f"exam domain weights sum to {total}, not 100")
    _validate_units(pack.get("units"), kind, domains, err, set(), set())
    return errs


def _normalise(pack: dict) -> dict:
    """Stamp each item with its unit/pack so lookups are O(1) and uniform."""
    for ui, u in enumerate(pack["units"]):
        u["index"] = ui
        u["domain"] = str(u.get("domain", "")) if pack["kind"] == "cert" else ""
        for it in u["items"]:
            it["unit"] = u["id"]
            it["pack"] = pack["id"]
            it.setdefault("alt", [])
            if it["type"] in ("mcq", "multi"):
                it["choices"] = [str(c) for c in it["choices"]]
    return pack


def _read(path: Path):
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 (a Safe loader)
    except Exception:
        return None


def set_personal(fn) -> None:
    """Register the source of personal courses (reader.py: "My words").

    ``fn(token)`` returns ``(token, None)`` when nothing changed since ``token``, else
    ``(new_token, {pack_id: pack})`` with packs already in normalised shape. It is
    called outside this module's lock, because it reads the state (which has its own)."""
    global _personal_fn, _personal_token, _personal
    _personal_fn, _personal_token, _personal = fn, None, {}


def _refresh_personal() -> bool:
    global _personal_token, _personal
    if _personal_fn is None:
        return False
    token, new = _personal_fn(_personal_token)
    if new is None:
        return False
    _personal_token, _personal = token, new
    return True


def load_all(force: bool = False) -> dict[str, dict]:
    """All valid packs by id (and the learner's personal course, when there is one).
    Invalid packs and parts are skipped, never a crash."""
    global _files, _cache, _index, _pictures_cache, _tracks
    changed = _refresh_personal()
    with _lock:
        if _files is None or force:
            if force:
                _pictures_cache = None
            _files = _load_files()
            _tracks = None
            changed = True
        if changed or _cache is None:
            _cache = {**_files, **{k: v for k, v in _personal.items() if k not in _files}}
            _index = None
        return _cache


def _load_files() -> dict[str, dict]:
    out: dict[str, dict] = {}
    parts: list[tuple[str, dict]] = []
    for path in sorted(PACK_DIR.glob("*.yaml")):
        pack = _read(path)
        if isinstance(pack, dict) and "part_of" in pack:
            parts.append((path.name, pack))
        elif not validate_pack(pack, path.name):
            out[pack["id"]] = pack
    for name, part in parts:                       # filename order
        base = out.get(str(part.get("part_of")))
        if base is None or validate_pack(part, name, base):
            continue
        base["units"] = base["units"] + part["units"]
    ids: set[str] = set()
    for pid in list(out):                          # item ids are global: drop a pack that collides
        out[pid] = _expand_pictures(out[pid])
        mine = {it.get("id") for u in out[pid]["units"] for it in u["items"]}
        if ids & mine:
            out.pop(pid)
            continue
        ids |= mine
        out[pid] = _hold_back_unpainted(_normalise(out[pid]))
    return out


def get(pack_id: str) -> dict | None:
    return load_all().get(pack_id)


def item_index() -> dict[str, dict]:
    """item_id -> item, across every pack (cached until the packs are reloaded)."""
    global _index
    all_packs = load_all()
    index = _index
    if index is None:
        index = _index = {it["id"]: it for p in all_packs.values() for u in p["units"] for it in u["items"]}
    return index


def main(argv: list[str]) -> int:
    """Validate packs. With file arguments, only those are reported (bases are still loaded)."""
    only = {Path(a).name for a in argv}
    bad = 0
    ids: dict[str, str] = {}
    bases: dict[str, dict] = {}
    defs, pic_errs = _load_pictures()
    for e in pic_errs:
        print("FAIL", e)
    bad += bool(pic_errs)
    if not only and not pic_errs and defs:
        print(f"ok   pictures/: {len(defs)} shared pictures, {sum(len(p['pins']) for p in defs.values())} pins, "
              f"{sum(painted(p) for p in defs)} painted")
    loaded = [(p, _read(p)) for p in sorted(PACK_DIR.glob("*.yaml"))]
    for path, pack in sorted(loaded, key=lambda t: (isinstance(t[1], dict) and "part_of" in t[1], t[0].name)):
        show = not only or path.name in only
        if pack is None:
            bad += show
            if show:
                print(f"FAIL {path.name}: YAML error")
            continue
        is_part = isinstance(pack, dict) and "part_of" in pack
        base = bases.get(str(pack.get("part_of"))) if is_part else None
        errs = validate_pack(pack, path.name, base)
        if isinstance(pack, dict):
            for u in pack.get("units") or []:
                for it in (u.get("items") or []) if isinstance(u, dict) else []:
                    for iid in item_ids(it):
                        if iid in ids and ids[iid] != path.name:
                            errs.append(f"{path.name}: item id {iid!r} also used in {ids[iid]}")
                        if iid:
                            ids[iid] = path.name
        if not errs and not is_part:
            bases[pack["id"]] = {**pack, "units": list(pack["units"])}
        elif not errs and base is not None:
            base["units"] = base["units"] + pack["units"]
        if not show:
            continue
        if errs:
            bad += 1
            print(f"FAIL {path.name} ({len(errs)} problems)")
            for e in errs[:40]:
                print("   ", e)
        else:
            n = sum(len(item_ids(it)) for u in pack["units"] for it in u["items"])
            kinds: dict[str, int] = {}
            for u in pack["units"]:
                for it in u["items"]:
                    t = "pin" if it["type"] == "picture" else it["type"]
                    kinds[t] = kinds.get(t, 0) + len(item_ids(it))
            label = f"part of {pack['part_of']}" if is_part else pack["id"]
            print(f"ok   {path.name} [{label}]: {len(pack['units'])} units, {n} items {kinds}")
    if not only:
        found, terrs = build_tracks(bases)
        for e in terrs:
            print("FAIL", e)
        bad += bool(terrs)
        for t in found.values():
            print(f"ok   track {t['id']}: {' > '.join(t['levels']) or 'no stages'}"
                  + (f" + add-ons {', '.join(t['addons'])}" if t["addons"] else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
