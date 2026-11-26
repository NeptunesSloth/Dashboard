"""The dictionary table shared by the modules built from English Wiktionary via kaikki.org (Spanish, French, Korean).

``dict/<lang>/<lang>_en.tsv.gz`` (built by ``scripts/build_dict_kaikki.py``) holds

    L <tab> lemma <tab> gloss [<tab> romanisation <tab> flags <tab> frequency]
    F <tab> form  <tab> lemma[|lemma...]                         an inflected form and the lemma(s) it belongs to
    C <tab> lemma <tab> form=code[/code],...                     a verb's conjugation (tense and person of each form)
    P <tab> headword                                             a set phrase or interjection: read it whole

A gloss is one or more sections, ``pos: sense; sense | pos: sense`` (one per Wiktionary entry, best first).
Flags: ``p`` only a proper noun, ``a`` only an abbreviation. Frequency: log10 of the word's count in a
subtitle corpus (Spanish, French), absent for a rare word. A conjugation code is ``mood.tense.person``
(``ind.pret.3s``), turned into words by ``describe``.

This module loads one such file (lazily, once) and answers the dictionary-wide questions: senses for a key,
the lemmas behind a form, a form's tense and person, and search by headword or by English gloss.
"""
from __future__ import annotations

import gzip
import re
import sys
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
        self.frm: dict[str, str | tuple[str, ...]] = {}  # form -> its lemma (a bare string), or a tuple of several
        self.phrases: set[str] = set()            # headwords that are set phrases or interjections (감사합니다)
        self.conj: dict[str, str] = {}            # verb lemma -> its C line (form=code,...), read when asked
        self.flags: dict[str, str] = {}           # lemma -> "p" / "a" (only those that have one)
        self.zipf: dict[str, int] = {}            # lemma -> log10 frequency (only words in the frequency list)
        self.folded: dict[str, list[str]] = {}    # fold(key) -> keys spelled with accents
        self.keys: list[str] = []                 # every lemma, sorted (prefix search)
        self.by_rom: list[tuple[str, str]] = []   # (romanisation without spaces, lemma), sorted
        self._low: list[tuple[str, str]] | None = None   # (lemma, gloss.lower()), made on the first English search
        self._loaded = False
        self._lock = threading.Lock()

    def load(self) -> Table:
        if self._loaded:
            return self
        with self._lock:
            if self._loaded:
                return self
            lem, rom, frm, phrases, conj, flags, zipf = {}, {}, {}, set(), {}, {}, {}
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) == 2 and parts[0] == "P":
                        phrases.add(parts[1])
                    elif len(parts) < 3:
                        continue
                    elif parts[0] == "L":
                        k = sys.intern(parts[1])
                        lem[k] = parts[2]
                        if len(parts) > 3 and parts[3]:
                            rom[k] = parts[3]
                        if len(parts) > 4 and parts[4]:
                            flags[k] = sys.intern(parts[4])
                        if len(parts) > 5 and parts[5].isdigit():
                            zipf[k] = int(parts[5])
                    elif parts[0] == "C":
                        conj[sys.intern(parts[1])] = parts[2]
                    elif parts[0] == "F":
                        # the lemma strings are interned, so 330,000 forms share one copy of each lemma
                        lemmas = parts[2].split("|")
                        frm[parts[1]] = sys.intern(lemmas[0]) if len(lemmas) == 1 else tuple(map(sys.intern, lemmas))
            self.lem, self.rom, self.frm, self.phrases = lem, rom, frm, phrases
            self.conj, self.flags, self.zipf = conj, flags, zipf
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
            self._loaded = True
        return self

    @property
    def low(self) -> list[tuple[str, str]]:
        """(lemma, gloss.lower()) for English -> language search, made when first needed."""
        if self._low is None:
            self._low = [(k, display(g).lower()) for k, g in self.load().lem.items()]
        return self._low

    def text(self, lemma: str) -> str:
        """A lemma's gloss as one line of senses ("to read; to play; lira"), "" if it has none."""
        g = self.lem.get(lemma)
        return display(g) if g else ""

    def senses(self, lemma: str) -> list[tuple[str, str]]:
        """A lemma's sections, best first: [(part of speech, "sense; sense")]."""
        g = self.lem.get(lemma)
        return sections(g) if g else []

    def codes(self, form: str, lemma: str) -> list[str]:
        """The tense/person codes of ``form`` as a form of the verb ``lemma`` ([] if it is not one of its forms)."""
        row = self.conj.get(lemma)
        if not row:
            return []
        i = row.find(form + "=")
        while i > 0 and row[i - 1] != ",":
            i = row.find(form + "=", i + 1)
        if i < 0:
            return []
        j = row.find(",", i)
        return row[i + len(form) + 1: j if j >= 0 else len(row)].split("/")

    def rare(self, lemma: str) -> bool:
        """Not in the frequency list (only where the language has one)."""
        return bool(self.zipf) and lemma not in self.zipf

    def lemmas_of(self, form: str) -> tuple[str, ...]:
        v = self.frm.get(form)
        return () if v is None else (v,) if type(v) is str else v

    def known(self, key: str) -> bool:
        return key in self.lem or key in self.frm


_SECTION = re.compile(r"^([a-z_]+): ")


def sections(gloss: str) -> list[tuple[str, str]]:
    """"verb: to read; to play | noun: lira" -> [("verb", "to read; to play"), ("noun", "lira")]."""
    out = []
    for part in gloss.split(" | "):
        m = _SECTION.match(part)
        out.append((m.group(1), part[m.end():]) if m else ("", part))
    return out


def display(gloss: str) -> str:
    """A stored gloss as one line of senses, sections joined by "; "."""
    return "; ".join(t for _, t in sections(gloss)) if ": " in gloss else gloss


# ---------------------------------------------------------------------------
# tense and person, in words
# ---------------------------------------------------------------------------
_TENSE = {"ind.pres": "present", "ind.pret": "preterite", "ind.impf": "imperfect", "ind.fut": "future",
          "ind.ph": "simple past (passé simple)", "cond.pres": "conditional", "subj.pres": "present subjunctive",
          "subj.impf": "imperfect subjunctive", "imp": "imperative"}
_NONFINITE = {"pp": "past participle", "pp.fs": "past participle, feminine singular", "pp.mp": "past participle, plural",
              "pp.fp": "past participle, feminine plural", "ger": "gerund", "prp": "present participle"}
_ORD = {"1": "1st", "2": "2nd", "3": "3rd"}
PRONOUNS = {
    "es": {"1s": "yo", "2s": "tú", "3s": "él, ella, usted", "1p": "nosotros", "2p": "vosotros", "3p": "ellos, ustedes"},
    "fr": {"1s": "je", "2s": "tu", "3s": "il, elle, on", "1p": "nous", "2p": "vous", "3p": "ils, elles"},
}


def describe(code: str, lang: str = "") -> str:
    """"ind.pret.3s" -> "preterite, 3rd person singular (él, ella, usted)"; "" for a code it does not know."""
    if code in _NONFINITE:
        return _NONFINITE[code]
    parts = code.split(".")
    head, pn = (parts[0], parts[1] if len(parts) > 1 else "") if parts[0] == "imp" else \
        (".".join(parts[:2]), parts[2] if len(parts) > 2 else "")
    tense = _TENSE.get(head)
    if not tense or len(pn) < 2 or pn[-1] not in "sp" or any(ch not in _ORD for ch in pn[:-1]):
        return ""
    who = "/".join(_ORD[ch] for ch in pn[:-1]) + " person " + ("singular" if pn[-1] == "s" else "plural")
    names = PRONOUNS.get(lang, {})
    if parts[-1] == "f" and lang == "es":
        pron = "usted" if pn[-1] == "s" else "ustedes"
    else:
        pron = "; ".join(names[ch + pn[-1]] for ch in pn[:-1] if ch + pn[-1] in names)
    return f"{tense}, {who}" + (f" ({pron})" if pron else "")


def gram_text(readings: list[tuple[str, list[str]]], lang: str) -> str:
    """[(lemma, codes)] -> "ser / ir, preterite, 3rd person singular (él, ella, usted)": lemmas that share their
    codes are named together; at most three readings of each."""
    groups: list[tuple[list[str], list[str]]] = []
    for lemma, codes in readings:
        words = list(dict.fromkeys(t for t in (describe(c, lang) for c in codes) if t))[:3]
        if not words:
            continue
        for g in groups:
            if g[1] == words:
                g[0].append(lemma)
                break
        else:
            groups.append(([lemma], words))
    return " · ".join(f"{' / '.join(ls)}, {'; '.join(ws)}" for ls, ws in groups[:3])


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
            rows.append((w, mine.get(w) if src == "mine" else t.text(w), src))
    else:
        w = norm(q) or q
        if ascii_rom and re.fullmatch(r"[a-z' -]+", q):
            rq = re.sub(r"[ '-]", "", q)
            i = bisect_left(t.by_rom, (rq, ""))
            while i < len(t.by_rom) and t.by_rom[i][0].startswith(rq) and len(rows) < limit * 2:
                k = t.by_rom[i][1]
                rows.append((k, t.text(k), "wiktionary"))
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
                rows.append((t.keys[i], t.text(t.keys[i]), "wiktionary"))
                i += 1
            if len(rows) < limit:
                for k in t.keys:
                    if w in k and not k.startswith(w):
                        rows.append((k, t.text(k), "wiktionary"))
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
