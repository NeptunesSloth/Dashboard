"""French -> English lookup (data: ``sect_academy/dict/fr/``; English Wiktionary via kaikki.org, CC BY-SA 4.0).

``lookup`` takes a tapped word to its dictionary entry: lower case, punctuation off; elisions split
("l'homme" -> homme, "qu'il" -> il, "jusqu'à" -> à); inverted verbs freed of their pronouns ("dit-il" -> dire,
"va-t-on" -> aller); the form table (every conjugation, plural and feminine Wiktionary lists); then plural and
feminine endings (-s, -x, -es, -aux -> -al, -euse -> -eur, -ive -> -if ...) and, last, the word without accents.

A word that is both a headword and a form of one of the commonest verbs is read as the verb ("est" is être
before it is "east", "fut" être before "fût"), unless an article stands elided in front of it ("l'été" is the
summer); the other reading is listed under "also" unless it is far rarer (a word frequency list says so) or
only a name or an abbreviation. A gloss that only says "surname", "spelling of …" or names a letter is weak:
lookup keeps looking.

A conjugated form says what it is in ``gram`` ("aller, present, 1st person plural (nous)", from Wiktionary's
conjugation tables), and then shows only its verb's senses ("lue" is lire, to read, not the lira). Function
words (le, de, du, y, en, que, lui ...) lead with a short learner's gloss from ``dict/fr/function_fr_en.tsv``
(src "core"). An elided pronoun pair ("qu'elle", "s'il") is read as both words: the pronoun, then que / si.

``segment`` splits the same way, so "l'", "homme", "dit", "-", "il" are separate tappable words, while words
the dictionary knows whole ("aujourd'hui", "peut-être", "quelqu'un") stay whole.
"""
from __future__ import annotations

import re
import unicodedata

from . import generic_norm, kaikki, simple_segment

LANG, NAME, SPEECH = "fr", "French", "fr-FR"
CREDIT = "Source: English Wiktionary (CC BY-SA 4.0), Wiktionary contributors, via kaikki.org."


def fold(s: str) -> str:
    """Without accents (ç as c, œ kept): only ever a fallback, since "pêche" and "péché" are different words."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


TABLE = kaikki.Table(LANG, fold)

# an elided word and what it stands for
ELISION = {"l'": "le / la (the; him, her, it)", "d'": "de (of, from)", "j'": "je (I)", "qu'": "que (that, than, what)",
           "n'": "ne (not)", "s'": "se / si (oneself; if)", "m'": "me (me, myself)", "t'": "te (you, yourself)",
           "c'": "ce (it, that)", "jusqu'": "jusque", "lorsqu'": "lorsque", "puisqu'": "puisque", "quoiqu'": "quoique"}
_ELISION_KEY = {"l'": "le", "d'": "de", "j'": "je", "qu'": "que", "n'": "ne", "s'": "se", "m'": "me", "t'": "te",
                "c'": "ce", "jusqu'": "jusque", "lorsqu'": "lorsque", "puisqu'": "puisque", "quoiqu'": "quoique"}
_ARTICLE = {"l'", "d'"}         # after these the next word is a noun far more often than a verb
_ELIDE = re.compile(r"^(jusqu|lorsqu|puisqu|quoiqu|qu|[ldjnsmtc])['’]", re.I)
PRONOUNS = {"je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "le", "la", "les", "lui", "leur", "moi", "toi",
            "y", "en", "ce", "t", "m'", "t'", "l'"}
# the commonest verbs: a word that is a form of one of these is read as that verb first
TOP_VERBS = {"être", "avoir", "aller", "faire", "dire", "pouvoir", "vouloir", "savoir", "voir", "devoir", "venir",
             "prendre", "mettre", "falloir", "croire", "parler", "donner", "tenir", "partir", "vivre", "connaître",
             "comprendre", "attendre", "répondre", "rester", "arriver", "penser", "aimer", "demander", "laisser",
             "appeler", "devenir", "revenir", "mourir", "naître", "boire", "manger", "recevoir", "pleuvoir", "suivre"}
OWN_FIRST = {"bus"}             # the headword first all the same: "bus" is a bus before it is "drank" (boire)
# plural and feminine endings -> what the masculine singular may end in (longest first)
_ENDINGS = [("eaux", "eau"), ("aux", "al"), ("euses", "eur"), ("euse", "eur"), ("trices", "teur"), ("trice", "teur"),
            ("ives", "if"), ("ive", "if"), ("elles", "el"), ("elle", "el"), ("ennes", "en"), ("enne", "en"),
            ("onnes", "on"), ("onne", "on"), ("ettes", "et"), ("ette", "et"), ("ères", "er"), ("ère", "er"),
            ("ses", "x"), ("se", "x"), ("es", ""), ("s", ""), ("x", ""), ("e", "")]
_WEAK = re.compile(r"^(?:(?:[^;]*\b(?:given name|surname|family name)\b[^;]*|[^;]*name of the [^;]*letter[^;]*|"
                   r"[^;]*\b(?:spelling|abbreviation|initialism|acronym|clipping|contraction) of\b[^;]*|"
                   r"indicating a surname[^;]*|[^;]*\bletter of the [^;]*alphabet[^;]*)(?:; |$))+$", re.I)


# a short learner's gloss for the function words, shown first (src "core")
CORE: dict[str, str] = {}
for _line in (kaikki.DICT_ROOT / LANG / "function_fr_en.tsv").read_text(encoding="utf-8").splitlines():
    _p = _line.split("\t")
    if len(_p) == 3 and _p[0] == "L":
        CORE[_p[1]] = _p[2]
_PAIR = {"qu'": "qu'", "s'": "s'", "lorsqu'": "qu'", "puisqu'": "qu'", "quoiqu'": "qu'", "jusqu'": "qu'"}
_PAIR_WORD = {"il", "elle", "on", "ils", "elles", "un", "une"}     # qu'elle, s'il, jusqu'à l'... read as two words


def norm_word(w) -> str:
    """A word as a dictionary key; an elided word keeps its apostrophe ("l'", "qu'")."""
    if isinstance(w, str):
        m = re.fullmatch(r"\s*(jusqu|lorsqu|puisqu|quoiqu|qu|[ldjnsmtc])['’]\s*", w[:20], re.I)
        if m:
            return m.group(1).lower() + "'"
    return generic_norm(w)


def dictionary() -> kaikki.Table:
    return TABLE.load()


def _known(k: str) -> bool:
    return TABLE.load().known(k)


def _whole(k: str) -> bool:
    """An elided word the dictionary knows as a word of its own ("aujourd'hui", "quelqu'un"), not one that is only a
    contraction ("qu'elle: que + elle") or a place name ("L'Hôpital")."""
    d = TABLE.load()
    if k not in d.lem or d.flags.get(k) or _WEAK.match(d.text(k)):
        return False
    return any(pos != "contraction" for pos, _ in d.senses(k))


def _split_word(t: str) -> list[str]:
    """One written word as the pieces a reader taps: elisions and inverted pronouns apart, known compounds whole."""
    k = generic_norm(t)
    m = _ELIDE.match(t)
    if not k or (_whole(k) if m else _known(k)):   # "aujourd'hui" whole, "qu'il" in two
        return [t]
    if m and len(t) > m.end():
        return [t[: m.end()], *_split_word(t[m.end():])]
    if "-" in t:
        parts = t.split("-")
        out: list[str] = []
        for i, p in enumerate(parts):
            if p.lower() == "t" and 0 < i < len(parts) - 1:              # va-t-on: the euphonic t is not a word
                out.append("-t-")
                continue
            if i and out[-1:] != ["-t-"]:
                out.append("-")
            if p:
                out.extend(_split_word(p))
        return out
    return [t]


def segment(text: str) -> list[dict]:
    """French is written with spaces: split on them and on punctuation, then elisions and inversions apart."""
    out: list[dict] = []
    for tok in simple_segment(text):
        if not tok["k"]:
            out.append(tok)
            continue
        for piece in _split_word(tok["t"]):
            k = norm_word(piece) if re.search(r"\w", piece) and piece != "-t-" else ""
            out.append({"t": piece, "k": k or None})
    return out


def _ending_keys(w: str) -> list[str]:
    return [w[: -len(a)] + b for a, b in _ENDINGS if w.endswith(a) and len(w) > len(a) + 1]


def candidates(word: str) -> list[tuple[str, str, bool]]:
    """(key, how, after an article) to try, best first, for a normalised word."""
    d = dictionary()
    out: list[tuple[str, str, bool]] = []
    if word in _ELISION_KEY:
        return [(_ELISION_KEY[word], "elision", False)]
    m = _ELIDE.match(word)
    # "qu'il" is listed only as "contraction of que + il": read it as il; "aujourd'hui" stays whole
    whole = not m or _whole(word)
    if whole:
        out.append((word, "exact", False))
    if m and len(word) > m.end():
        el = m.group(0).lower().replace("’", "'")
        rest = word[m.end():]
        out += [(k, "elision", el in _ARTICLE) for k, _h, _a in candidates(rest)]
    if not whole:
        out.append((word, "exact", False))
    if "-" in word:
        parts = [p for p in word.split("-") if p]
        while len(parts) > 1 and parts[-1] in PRONOUNS:
            parts.pop()                                                 # dit-il, va-t-on, donne-moi
        if parts:
            head = "-".join(parts)
            if head != word:
                out += [(k, "inversion", a) for k, _h, a in candidates(head)]
            out += [(p, "inversion", False) for p in word.split("-") if p and p not in PRONOUNS]
    out += [(k, "ending", False) for k in _ending_keys(word)]
    out += [(k, "accent", False) for k in d.folded.get(fold(word), [])]
    if fold(word) != word:
        out.append((fold(word), "accent", False))
    seen: set[str] = set()
    return [(k, h, a) for k, h, a in out if k and not (k in seen or seen.add(k))]


def _senses(key: str, mine: dict) -> list[dict]:
    d = dictionary()
    out = []
    if key in mine:
        out.append({"src": "mine", "text": mine[key]})
    if key in CORE:
        out.append({"src": "core", "text": CORE[key]})
    wik = [{"src": "wiktionary", "text": t, "pos": pos} for pos, t in d.senses(key)]
    if any(not _WEAK.match(x["text"]) for x in wik):
        wik = [x for x in wik if not _WEAK.match(x["text"])]       # elle: not also "the name of the letter L"
    out += wik
    return out


def _also_ok(row: dict, hit: dict) -> bool:
    """Whether another reading is worth showing beside the answer: not only a name or an abbreviation, and not a
    word ten times rarer than the answer ("étaient" is être; étayer, to prop up, is left out)."""
    d = dictionary()
    lem = row["lemma"]
    if lem in CORE or any(s["src"] == "mine" for s in row["senses"]):
        return True
    if d.flags.get(lem):
        return False
    z_hit = d.zipf.get(hit["lemma"])
    return z_hit is None or d.zipf.get(lem, -1) >= z_hit - 1


def _verb_only(row: dict) -> None:
    """A conjugated form: its verb's senses only ("lue" -> lire: to read, not "lira (unit of currency)")."""
    if row.get("codes") and any(s.get("pos") == "verb" for s in row["senses"]):
        row["senses"] = [s for s in row["senses"] if s["src"] != "wiktionary" or s.get("pos") == "verb"]


def _strong(senses: list[dict]) -> bool:
    return any(s["src"] != "wiktionary" or not _WEAK.match(s["text"]) for s in senses)


def lookup(raw, mine: dict | None = None) -> dict:
    """Look a word up. -> {found, word, lemma, path, how, gram, senses, also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    d = dictionary()
    hit = None
    also: list[dict] = []
    for key, how, after_article in candidates(word):
        path0 = [word] if key == word else [word, key]
        own = [(key, path0, how)]
        forms = [(lem, path0 + [lem], "form" if how == "exact" else how) for lem in d.lemmas_of(key) if lem != key]
        if not after_article and key not in mine and key not in OWN_FIRST and any(f[0] in TOP_VERBS for f in forms):
            tries = [f for f in forms if f[0] in TOP_VERBS] + own + [f for f in forms if f[0] not in TOP_VERBS]
        else:
            tries = own + forms
        for lem, path, h in tries:
            senses = _senses(lem, mine)
            if not senses:
                continue
            row = {"lemma": lem, "path": path, "how": h, "senses": senses}
            if lem != key and d.codes(key, lem):
                row["codes"] = [(x, d.codes(key, x)) for x in [lem, *(y for y in d.lemmas_of(key) if y != lem)]
                                if d.codes(key, x)]
                z = d.zipf.get(lem)
                row["codes"] = [c for c in row["codes"] if c[0] == lem or z is None or d.zipf.get(c[0], -1) >= z - 1][:2]
            if h == "elision":
                el = _ELIDE.match(word)
                row["gram"] = f"{el.group(0).lower()} = {ELISION.get(el.group(0).lower(), '')}" if el else \
                    f"{word} = {ELISION.get(word, '')}"
                if el and el.group(0).lower() in _PAIR and word[el.end():] in _PAIR_WORD:
                    first = "si" if el.group(0).lower() == "s'" else "que"
                    row["gram"] = f"{el.group(0).lower()} = {first} + {word[el.end():]}"
                    row["senses"] = senses + [{"src": "core", "text": f"{first} — {CORE.get(first, '')}",
                                               "lemma": first}]
            if hit is None and _strong(senses):
                hit = row
            elif all(lem != x["lemma"] for x in also) and (hit is None or lem != hit["lemma"]):
                also.append(row)
        if hit is not None:
            break
    if hit is None and also:
        hit, also = also[0], also[1:]
    if hit:
        also = [a for a in also if _also_ok(a, hit)]
        for row in (hit, *also):
            _verb_only(row)
            conj = kaikki.gram_text(row.pop("codes", []), LANG)
            if conj:
                row["gram"] = f"{row['gram']} · {conj}" if row.get("gram") else conj
        if word in CORE and hit["lemma"] != word and not any(s["src"] == "core" for s in hit["senses"]):
            hit["senses"] = [{"src": "core", "text": CORE[word]}, *hit["senses"]]      # l' -> le: the l' gloss
    out = {"ok": True, "word": word, "found": hit is not None, "also": also[:3], "credit": CREDIT}
    if hit:
        out.update(hit)
        out.setdefault("gram", "")
        out["weak"] = not _strong(hit["senses"])
    else:
        out.update(lemma="", path=[word], how="", gram="", senses=[], weak=False)
    return out


def search(q, direction: str = "from", mine: dict | None = None, limit: int = 40) -> list[dict]:
    """French -> English by headword (prefix, then contains), or English -> French by gloss."""
    return kaikki.search(dictionary(), q, direction, mine or {}, limit, norm_word, lookup, _WEAK)
