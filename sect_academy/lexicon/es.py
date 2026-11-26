"""Spanish -> English lookup (data: ``sect_academy/dict/es/``; Wiktionary via doozan/spanish_data, CC BY-SA 4.0).

``lookup`` finds a tapped word the way the owner's Aprende app did — lower case,
punctuation off, the form table (``F`` lines), Spanish endings (plurals, verb
endings) — and adds what that app left to the form table: pronouns attached to
a verb ("cúrale", "dímelo") and a missing accent ("dimelo"). A gloss that is
only "surname"/"given name" counts as weak: the compiled data sometimes kept the
name where a common word shares its spelling, so lookup keeps looking.
"""
from __future__ import annotations

import gzip
import re
import threading
import unicodedata
from bisect import bisect_left
from pathlib import Path

from . import generic_norm, simple_segment

LANG, NAME, SPEECH = "es", "Spanish", "es-ES"
DICT_DIR = Path(__file__).parent.parent / "dict" / "es"
CREDIT = "Source: Wiktionary data (CC BY-SA), compiled by doozan/spanish_data."


def fold(s: str) -> str:
    """Without accents (and ñ as n): only ever a fallback, since "año" and "ano" are different words."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def norm_word(w) -> str:
    """A tapped or typed word as a dictionary key: one word, lower case, no punctuation around it."""
    return generic_norm(w)


def segment(text: str) -> list[dict]:
    """Spanish is written with spaces: split on them and on punctuation."""
    return simple_segment(text)


# ---------------------------------------------------------------------------
# the dictionary
# ---------------------------------------------------------------------------
class _Dict:
    def __init__(self) -> None:
        self.lem: dict[str, str] = {}       # lemma -> gloss (Wiktionary)
        self.frm: dict[str, str] = {}       # form -> lemma
        self.core: dict[str, str] = {}      # lemma -> gloss (the owner's core word list)
        self.folded: dict[str, list[str]] = {}   # fold(key) -> keys whose spelling has accents
        self.keys: list[str] = []           # every lemma, sorted (prefix search)
        self.low: list[tuple[str, str]] = []     # (lemma, gloss.lower()) for English -> Spanish search

    def load(self) -> _Dict:
        with gzip.open(DICT_DIR / "es_en.tsv.gz", "rt", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 3:
                    continue
                if parts[0] == "L":
                    self.lem[parts[1]] = parts[2]
                elif parts[0] == "F":
                    self.frm[parts[1]] = parts[2]
        core = DICT_DIR / "core_es_en.tsv"
        if core.exists():
            for line in core.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) == 3 and parts[0] == "L":
                    self.core[parts[1]] = parts[2]
        for k in (*self.lem, *self.frm, *self.core):
            f = fold(k)
            if f != k:
                self.folded.setdefault(f, [])
                if k not in self.folded[f]:
                    self.folded[f].append(k)
        self.keys = sorted(set(self.lem) | set(self.core))
        self.low = [(k, g.lower()) for k, g in self.lem.items()]
        return self


_dict: _Dict | None = None
_dict_lock = threading.Lock()


def dictionary() -> _Dict:
    """The dictionary, loaded on first use (about a second) and kept."""
    global _dict
    if _dict is None:
        with _dict_lock:
            if _dict is None:
                _dict = _Dict().load()
    return _dict


# Aprende's ending rules, in its order: a plural or a verb ending -> the dictionary form it may come from.
_ENDINGS = [("ces", "z"), ("es", ""), ("s", ""), ("a", "o"), ("as", "o"), ("os", "o"), ("ando", "ar"), ("iendo", "er"),
            ("iendo", "ir"), ("ado", "ar"), ("ido", "er"), ("ido", "ir"), ("amos", "ar"), ("emos", "er"), ("imos", "ir"),
            ("aron", "ar"), ("ieron", "er"), ("ieron", "ir"), ("aba", "ar"), ("ía", "er"), ("ía", "ir"), ("an", "ar"),
            ("en", "er"), ("as", "ar"), ("es", "er"), ("a", "ar"), ("e", "er"), ("o", "ar"), ("o", "er"), ("o", "ir"),
            ("ó", "ar"), ("ó", "er")]
# Pronouns written onto the end of a verb (dímelo, cúrale, levántate, decírselo, vámonos).
_CLITIC = re.compile(r"(?:(me|te|se|nos|os)(lo|la|los|las|le|les)?|(lo|la|los|las|le|les))$")
_WEAK = re.compile(r"^(?:(?:a )?(?:male |female )?(?:given name|surname)(?:; )?)+$", re.I)


def _endings(w: str) -> list[str]:
    return [w[: -len(a)] + b for a, b in _ENDINGS if w.endswith(a) and len(w) > len(a) + 1]


def _clitic_stems(w: str) -> list[str]:
    """The verb under attached pronouns, accent removed: dímelo -> di, cúrale -> cura, decírselo -> decir."""
    m = _CLITIC.search(w)
    if not m or len(w) - len(m.group(0)) < 2:
        return []
    stem = w[: m.start()]
    plain = "".join(ch for ch in unicodedata.normalize("NFD", stem) if ch not in "́")   # acute only: keep ñ, ü
    plain = unicodedata.normalize("NFC", plain)
    out = [plain]
    if m.group(1) == "nos" and plain.endswith("mo"):
        out.append(plain + "s")                     # vámonos -> vamos
    if m.group(1) == "os" and len(plain) > 2 and plain[-1] in "aei":
        out.append(plain + "d")                     # sentaos -> sentad
    if not (plain.endswith(("r", "ndo")) or plain[-1:] in "aeiouds"):
        return []                                   # pronouns attach to an infinitive, a gerund or a command
    return out


def candidates(word: str) -> list[tuple[str, str]]:
    """(key, how) pairs to try, best first, for a normalised word."""
    d = dictionary()
    out: list[tuple[str, str]] = [(word, "exact")]
    # a plural is the surest guess (casas -> casa, luces -> luz), before any accent variant (casás)
    out += [(word[: -len(a)] + b, "ending") for a, b in _ENDINGS[:3] if word.endswith(a) and len(word) > len(a) + 1]
    out += [(k, "accent") for k in d.folded.get(fold(word), [])]        # dimelo -> dímelo
    for stem in _clitic_stems(word):
        if stem[-1:] in ("a", "e", "i"):
            out.append((stem + "r", "pronouns"))                         # cúrale -> cura -> curar (the verb, not "cura")
        out.append((stem, "pronouns"))
        out += [(c, "pronouns") for c in _endings(stem)]
    out += [(c, "ending") for c in _endings(word)]
    if fold(word) != word:
        out.append((fold(word), "accent"))
    seen: set[str] = set()
    return [(k, h) for k, h in out if k and not (k in seen or seen.add(k))]


def _senses(key: str, mine: dict) -> list[dict]:
    d = dictionary()
    out = []
    if key in mine:
        out.append({"src": "mine", "text": mine[key]})
    if key in d.core:
        out.append({"src": "core", "text": d.core[key]})
    if key in d.lem:
        out.append({"src": "wiktionary", "text": d.lem[key]})
    return out


def _strong(senses: list[dict]) -> bool:
    return any(s["src"] != "wiktionary" or not _WEAK.match(s["text"]) for s in senses)


def lookup(raw, mine: dict | None = None) -> dict:
    """Look a word up. -> {found, word, lemma, path, how, senses, also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    d = dictionary()
    hit = None
    also: list[dict] = []
    for key, how in candidates(word):
        tries = [(key, [word] if key == word else [word, key], how)]
        lemma = d.frm.get(key)
        if lemma and lemma != key:
            tries.append((lemma, [word, lemma] if key == word else [word, key, lemma], "form" if how == "exact" else how))
        for lem, path, h in tries:
            senses = _senses(lem, mine)
            if not senses:
                continue
            if hit is None and _strong(senses):
                hit = {"lemma": lem, "path": path, "how": h, "senses": senses}
            elif all(lem != x["lemma"] for x in also) and (hit is None or lem != hit["lemma"]):
                also.append({"lemma": lem, "path": path, "how": h, "senses": senses})
        if hit is not None:
            break
    if hit is None and also:
        hit, also = also[0], also[1:]                # only a weak entry (a surname): show it, say so
    out = {"ok": True, "word": word, "found": hit is not None, "also": also[:3], "credit": CREDIT}
    if hit:
        out.update(hit)
        out["weak"] = not _strong(hit["senses"])
    else:
        out.update(lemma="", path=[word], how="", senses=[], weak=False)
    return out


def search(q, direction: str = "from", mine: dict | None = None, limit: int = 40) -> list[dict]:
    """Spanish -> English by headword (prefix, then contains), or English -> Spanish by gloss."""
    q = re.sub(r"\s+", " ", q if isinstance(q, str) else "")[:60].strip().lower()
    if not q:
        return []
    mine = mine or {}
    d = dictionary()
    rows: list[tuple[str, str, str]] = []           # (es, en, src)
    if direction == "en":
        pat = re.compile(r"(?:^|[^a-z])" + re.escape(q) + r"(?:$|[^a-z])")
        scored = []
        for src, pairs in (("mine", [(k, v.lower()) for k, v in mine.items()]), ("core", [(k, v.lower()) for k, v in d.core.items()]),
                           ("wiktionary", d.low)):
            for es, gl in pairs:
                if q not in gl or (src == "wiktionary" and _WEAK.match(gl)):
                    continue
                senses = [s.strip() for s in gl.split(";")]
                score = 0 if (q in senses or f"to {q}" in senses) else 1 if pat.search(gl) else 2
                scored.append((src != "mine", score, src != "core", len(gl), es, src))     # your own entries first
        scored.sort()
        for *_, es, src in scored[: limit * 3]:
            en = mine.get(es) if src == "mine" else d.core.get(es) if src == "core" else d.lem.get(es, "")
            rows.append((es, en, src))
    else:
        w = norm_word(q) or q
        look = lookup(w, mine) if norm_word(q) else None
        if look and look["found"]:
            rows.append((look["lemma"], look["senses"][0]["text"], look["senses"][0]["src"]))
        for k, v in mine.items():
            if k.startswith(w):
                rows.append((k, v, "mine"))
        i = bisect_left(d.keys, w)
        while i < len(d.keys) and d.keys[i].startswith(w) and len(rows) < limit * 2:
            k = d.keys[i]
            rows.append((k, d.core.get(k) or d.lem.get(k, ""), "core" if k in d.core else "wiktionary"))
            i += 1
        if len(rows) < limit:
            for k in d.keys:
                if w in k and not k.startswith(w):
                    rows.append((k, d.core.get(k) or d.lem.get(k, ""), "core" if k in d.core else "wiktionary"))
                    if len(rows) >= limit * 2:
                        break
    seen: set[str] = set()
    out = []
    for es, en, src in rows:
        if es in seen:
            continue
        seen.add(es)
        out.append({"w": es, "en": en[:300], "src": src})
        if len(out) >= limit:
            break
    return out

