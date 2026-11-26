"""The dictionary table shared by the modules built from English Wiktionary via kaikki.org (French, Korean).

``dict/<lang>/<lang>_en.tsv.gz`` (built by ``scripts/build_dict_fr_ko.py``) holds

    L <tab> lemma <tab> English gloss [<tab> romanisation]     senses separated by "; "
    F <tab> form  <tab> lemma[|lemma...]                         an inflected form and the lemma(s) it belongs to
    P <tab> headword                                             a set phrase or interjection: read it whole

This module loads one such file (lazily, once) and answers the dictionary-wide questions: senses for a key,
the lemmas behind a form, and search by headword or by English gloss.
"""
from __future__ import annotations

import gzip
import re
import threading
from bisect import bisect_left
from collections.abc import Callable
from pathlib import Path

DICT_ROOT = Path(__file__).parent.parent / "dict"
_PAREN = re.compile(r"\s*\([^()]*\)")


class Table:
    def __init__(self, lang: str, fold: Callable[[str], str] | None = None) -> None:
        self.lang = lang
        self.path = DICT_ROOT / lang / f"{lang}_en.tsv.gz"
        self.fold = fold
        self.lem: dict[str, str] = {}             # lemma -> gloss
        self.rom: dict[str, str] = {}             # lemma -> romanisation (Korean)
        self.frm: dict[str, tuple[str, ...]] = {}  # form -> lemmas
        self.phrases: set[str] = set()            # headwords that are set phrases or interjections (감사합니다)
        self.folded: dict[str, list[str]] = {}    # fold(key) -> keys spelled with accents
        self.keys: list[str] = []                 # every lemma, sorted (prefix search)
        self.by_rom: list[tuple[str, str]] = []   # (romanisation without spaces, lemma), sorted
        self.low: list[tuple[str, str]] = []      # (lemma, gloss.lower()) for English -> language search
        self._loaded = False
        self._lock = threading.Lock()

    def load(self) -> Table:
        if self._loaded:
            return self
        with self._lock:
            if self._loaded:
                return self
            lem, rom, frm, phrases = {}, {}, {}, set()
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) == 2 and parts[0] == "P":
                        phrases.add(parts[1])
                    elif len(parts) < 3:
                        continue
                    elif parts[0] == "L":
                        lem[parts[1]] = parts[2]
                        if len(parts) > 3 and parts[3]:
                            rom[parts[1]] = parts[3]
                    elif parts[0] == "F":
                        frm[parts[1]] = tuple(parts[2].split("|"))
            self.lem, self.rom, self.frm, self.phrases = lem, rom, frm, phrases
            if self.fold:
                folded: dict[str, list[str]] = {}
                for k in (*lem, *frm):
                    fk = self.fold(k)
                    if fk != k:
                        lst = folded.setdefault(fk, [])
                        if k not in lst:
                            lst.append(k)
                self.folded = folded
            self.keys = sorted(lem)
            self.by_rom = sorted((r.replace(" ", "").replace("-", "").lower(), k) for k, r in rom.items())
            self.low = [(k, g.lower()) for k, g in lem.items()]
            self._loaded = True
        return self

    def lemmas_of(self, form: str) -> tuple[str, ...]:
        return self.frm.get(form, ())

    def known(self, key: str) -> bool:
        return key in self.lem or key in self.frm


def search(table: Table, q: str, direction: str, mine: dict, limit: int, norm: Callable[[str], str],
           lookup: Callable[[str, dict], dict], weak: re.Pattern, ascii_rom: bool = False) -> list[dict]:
    """Headword search (exact lookup, then prefix, then contains) or English -> language search by gloss.
    With ``ascii_rom`` a Latin-letter query in the "from" direction is matched against the romanisation."""
    q = re.sub(r"\s+", " ", q if isinstance(q, str) else "")[:60].strip().lower()
    if not q:
        return []
    t = table.load()
    rows: list[tuple[str, str, str]] = []
    if direction == "en":
        pat = re.compile(r"(?:^|[^a-z])" + re.escape(q) + r"(?:$|[^a-z])")
        scored = []
        for src, pairs in (("mine", [(k, v.lower()) for k, v in mine.items()]), ("wiktionary", t.low)):
            for w, gl in pairs:
                if q not in gl or (src == "wiktionary" and weak.match(gl)):
                    continue
                senses = [_PAREN.sub("", s).strip() for s in gl.split(";")]
                heads = [x.strip() for x in senses[0].split(",")] if senses else []
                forms = (q, f"to {q}", f"to be {q}", f"a {q}", f"an {q}", f"the {q}")
                score = (0 if senses and senses[0] in forms else 1 if heads and heads[0] in forms
                         else 2 if any(x in forms for x in senses) or any(x in forms for x in heads) else 3 if pat.search(gl) else 4)
                # among equals, the entry with more senses first: common words have many ("chien" before "iench")
                scored.append((src != "mine", score, -gl.count(";"), len(w), w, src))
        scored.sort()
        for *_, w, src in scored[: limit * 3]:
            rows.append((w, mine.get(w) if src == "mine" else t.lem.get(w, ""), src))
    else:
        w = norm(q) or q
        if ascii_rom and re.fullmatch(r"[a-z' -]+", q):
            rq = re.sub(r"[ '-]", "", q)
            i = bisect_left(t.by_rom, (rq, ""))
            while i < len(t.by_rom) and t.by_rom[i][0].startswith(rq) and len(rows) < limit * 2:
                k = t.by_rom[i][1]
                rows.append((k, t.lem.get(k, ""), "wiktionary"))
                i += 1
            rows.sort(key=lambda r: (len(t.rom.get(r[0], "")), r[0]))
        else:
            look = lookup(w, mine) if norm(q) else None
            if look and look.get("found"):
                rows.append((look["lemma"], look["senses"][0]["text"], look["senses"][0]["src"]))
            for k, v in mine.items():
                if k.startswith(w):
                    rows.append((k, v, "mine"))
            i = bisect_left(t.keys, w)
            while i < len(t.keys) and t.keys[i].startswith(w) and len(rows) < limit * 2:
                rows.append((t.keys[i], t.lem[t.keys[i]], "wiktionary"))
                i += 1
            if len(rows) < limit:
                for k in t.keys:
                    if w in k and not k.startswith(w):
                        rows.append((k, t.lem[k], "wiktionary"))
                        if len(rows) >= limit * 2:
                            break
    seen: set[str] = set()
    out = []
    for word, en, src in rows:
        if word in seen:
            continue
        seen.add(word)
        row = {"w": word, "en": (en or "")[:300], "src": src}
        if word in t.rom:
            row["rom"] = t.rom[word]
        out.append(row)
        if len(out) >= limit:
            break
    return out
