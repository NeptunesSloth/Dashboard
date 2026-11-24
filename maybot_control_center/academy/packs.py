"""Content packs: load + validate the curated YAML courses in ``packs/``.

A pack is one course (a language level or a certification). Schema — see
``docs/ACADEMY_CONTENT.md`` for the authoring guide:

    id, title, kind (language|cert), blurb, hall
    language packs:  language, lang (BCP-47 speech tag, e.g. fr-FR)
    cert packs:      exam {name, code, questions, minutes, pass_pct,
                           domains: [{id, title, weight}]}
    units: [{id, title, goal, notes, domain?, items: [...]}]

Item types:
    vocab / phrase  {id, type, l2, l1, alt?, note?, ex?, ex_l1?}
    cloze           {id, type, text (one ``___``), answer, alt?, l1?, note?}
    concept         {id, type, term, def, note?}
    mcq             {id, type, q, choices[4], answer (index), why}

Run ``python -m maybot_control_center.academy.packs`` to validate every pack.
"""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

import yaml

PACK_DIR = Path(__file__).parent / "packs"
KINDS = ("language", "cert")
ITEM_TYPES = ("vocab", "phrase", "cloze", "concept", "mcq")
_ID = re.compile(r"^[a-z0-9][a-z0-9_.\-]{1,63}$")
_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)      # the C loader is ~10x faster when present
_lock = threading.Lock()
_cache: dict[str, dict] | None = None
_index: dict[str, dict] | None = None


def _s(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def validate_pack(pack, source: str = "") -> list[str]:
    """Return a list of human-readable problems (empty = valid)."""
    errs: list[str] = []
    w = f"{source}: " if source else ""

    def err(msg: str) -> None:
        errs.append(w + msg)

    if not isinstance(pack, dict):
        return [w + "pack is not a mapping"]
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
    units = pack.get("units")
    if not isinstance(units, list) or not units:
        err("no units")
        return errs
    seen_units: set[str] = set()
    seen_items: set[str] = set()
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
        if not isinstance(items, list) or len(items) < 4:
            err(f"unit {uid}: needs at least 4 items")
            continue
        for it in items:
            if not isinstance(it, dict):
                err(f"unit {uid}: item is not a mapping")
                continue
            iid = _s(it.get("id"))
            if not _ID.match(iid) or iid in seen_items:
                err(f"unit {uid}: bad/duplicate item id {iid!r}")
            seen_items.add(iid)
            t = it.get("type")
            if t not in ITEM_TYPES:
                err(f"item {iid}: type must be one of {ITEM_TYPES}")
                continue
            if kind == "language" and t in ("concept", "mcq"):
                err(f"item {iid}: {t} items belong in cert packs")
            if kind == "cert" and t in ("vocab", "phrase", "cloze"):
                err(f"item {iid}: {t} items belong in language packs")
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
            elif t == "concept":
                if not _s(it.get("term")) or not _s(it.get("def")):
                    err(f"item {iid}: needs term and def")
            elif t == "mcq":
                ch = it.get("choices")
                if not _s(it.get("q")) or not isinstance(ch, list) or len(ch) != 4 \
                        or not all(_s(c) if isinstance(c, str) else str(c) for c in ch):
                    err(f"item {iid}: needs q and exactly 4 choices")
                elif len({str(c).strip().lower() for c in ch}) != 4:
                    err(f"item {iid}: duplicate choices")
                if not isinstance(it.get("answer"), int) or isinstance(it.get("answer"), bool) \
                        or not 0 <= it.get("answer", -1) <= 3:
                    err(f"item {iid}: answer must be a 0-3 index")
                if not _s(it.get("why")):
                    err(f"item {iid}: needs why (the explanation)")
            alt = it.get("alt", [])
            if not isinstance(alt, list) or not all(isinstance(a, str) and a.strip() for a in alt):
                err(f"item {iid}: alt must be a list of strings")
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
            if it["type"] == "mcq":
                it["choices"] = [str(c) for c in it["choices"]]
    return pack


def load_all(force: bool = False) -> dict[str, dict]:
    """All valid packs by id (invalid packs are skipped, never crash the app)."""
    global _cache, _index
    with _lock:
        if _cache is not None and not force:
            return _cache
        _index = None
        out: dict[str, dict] = {}
        for path in sorted(PACK_DIR.glob("*.yaml")):
            try:
                pack = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 (a Safe loader)
            except Exception:
                continue
            if validate_pack(pack, path.name):
                continue
            out[pack["id"]] = _normalise(pack)
        _cache = out
        return out


def get(pack_id: str) -> dict | None:
    return load_all().get(pack_id)


def item_index() -> dict[str, dict]:
    """item_id -> item, across every pack (cached until the packs are reloaded)."""
    global _index
    all_packs = load_all()
    if _index is None:
        _index = {it["id"]: it for p in all_packs.values() for u in p["units"] for it in u["items"]}
    return _index


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or sorted(PACK_DIR.glob("*.yaml"))
    bad = 0
    ids: dict[str, str] = {}
    for path in paths:
        try:
            pack = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 (a Safe loader)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {path.name}: YAML error: {e}")
            bad += 1
            continue
        errs = validate_pack(pack, path.name)
        if isinstance(pack, dict):
            for u in pack.get("units") or []:
                for it in (u.get("items") or []) if isinstance(u, dict) else []:
                    iid = it.get("id") if isinstance(it, dict) else None
                    if iid in ids and ids[iid] != path.name:
                        errs.append(f"{path.name}: item id {iid!r} also used in {ids[iid]}")
                    if iid:
                        ids[iid] = path.name
        if errs:
            bad += 1
            print(f"FAIL {path.name} ({len(errs)} problems)")
            for e in errs[:40]:
                print("   ", e)
        else:
            n = sum(len(u["items"]) for u in pack["units"])
            print(f"ok   {path.name}: {len(pack['units'])} units, {n} items")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
