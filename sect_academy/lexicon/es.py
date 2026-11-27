"""Spanish -> English lookup (data: ``sect_academy/dict/es/``; English Wiktionary via kaikki.org, CC BY-SA 4.0).

``lookup`` finds a tapped word the way the owner's Aprende app did — lower case, punctuation off, the form
table (``F`` lines), Spanish endings (plurals, verb endings) — and adds what that app left to the form table:
pronouns attached to a verb ("cúrale", "dímelo") and a missing accent ("dimelo").

Every part of speech Wiktionary has for a word is kept, one sense per entry, the usual one first ("ido" is
an adjective, a verb form and a language); names and abbreviations go last and count as weak. The function
words (lo, le, su, al, me, nos, que ...) lead with a short learner's gloss (``dict/es/function_es_en.tsv``,
src "core"), as do the everyday words of the owner's core list (``core_es_en.tsv``). A conjugated form says
what it is in ``gram`` ("ser / ir, preterite, 3rd person singular (él, ella, usted)") and shows its verb's
senses; a form of one of the commonest verbs is read as that verb before any headword it is spelled like
("ido" -> ir, "fue" -> ser and ir, "haya" -> haber), the headword then listed under "also".
"""
from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left

from . import generic_norm, kaikki, simple_segment

LANG, NAME, SPEECH = "es", "Spanish", "es-ES"
DICT_DIR = kaikki.DICT_ROOT / LANG
CREDIT = "Source: English Wiktionary (CC BY-SA 4.0), Wiktionary contributors, via kaikki.org."


def fold(s: str) -> str:
    """Without accents (and ñ as n): only ever a fallback, since "año" and "ano" are different words."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


TABLE = kaikki.Table(LANG, fold)


def _tsv(name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    path = DICT_DIR / name
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            p = line.split("\t")
            if len(p) == 3 and p[0] == "L":
                out.setdefault(p[1], p[2])
    return out


# a short learner's gloss for the function words, then the owner's core list (año = year): shown first, src "core"
CORE: dict[str, str] = {**_tsv("core_es_en.tsv"), **_tsv("function_es_en.tsv")}
_CORE_FOLDED: dict[str, list[str]] = {}
for _k in CORE:
    if fold(_k) != _k:
        _CORE_FOLDED.setdefault(fold(_k), []).append(_k)

# the commonest verbs, in the order an ambiguous form is read (fue: ser, then ir); their forms win over a
# headword spelled the same, except the participles and the few headwords below
VERB_FIRST = ["ser", "estar", "haber", "ir", "tener", "hacer", "poder", "decir", "ver", "dar", "saber", "querer",
              "venir", "poner", "salir", "llegar", "pasar", "deber", "parecer", "quedar", "creer", "hablar",
              "llevar", "dejar", "seguir", "encontrar", "llamar", "pensar", "volver", "conocer", "vivir", "sentir",
              "tomar", "mirar", "esperar", "buscar", "entender", "pedir", "comer", "beber", "dormir", "gustar"]
_VERB_RANK = {v: i for i, v in enumerate(VERB_FIRST)}
OWN_FIRST = {"vino", "vinos", "fuera", "vista", "como", "para", "entre", "sobre", "bajo", "cara", "trabajo",
             "parte", "cuenta", "paso", "llama", "pregunta", "ayuda", "cambio", "juego", "estudio", "espera",
             "hecho", "dicho", "puesto", "dado", "visto", "pasado", "sentido", "seguido", "estado", "llegada",
             "salida", "entrada", "vuelta", "ida", "muerto", "abierto", "escrito", "creo", "siento", "sé", "ve",
             "di", "da"}
VERB_FIRST_FORMS = {"ido", "sido", "habido", "son", "era", "eras", "haya", "hayas", "he", "ha", "han", "has", "va",
                    "voy", "vaya", "sea", "seas", "fue", "fui", "fuimos", "fueron", "fuiste", "soy", "es", "está",
                    "estoy", "están", "estás", "vas", "van", "vamos", "tengo", "tiene", "tienes", "puedo", "puede"}


def norm_word(w) -> str:
    """A tapped or typed word as a dictionary key: one word, lower case, no punctuation around it."""
    return generic_norm(w)


def segment(text: str) -> list[dict]:
    """Spanish is written with spaces: split on them and on punctuation."""
    return simple_segment(text)


def dictionary() -> kaikki.Table:
    """The dictionary, loaded on first use (about a second) and kept."""
    return TABLE.load()


# Aprende's ending rules, in its order: a plural or a verb ending -> the dictionary form it may come from.
_ENDINGS = [("ces", "z"), ("es", ""), ("s", ""), ("a", "o"), ("as", "o"), ("os", "o"), ("ando", "ar"), ("iendo", "er"),
            ("iendo", "ir"), ("ado", "ar"), ("ido", "er"), ("ido", "ir"), ("amos", "ar"), ("emos", "er"), ("imos", "ir"),
            ("aron", "ar"), ("ieron", "er"), ("ieron", "ir"), ("aba", "ar"), ("ía", "er"), ("ía", "ir"), ("an", "ar"),
            ("en", "er"), ("as", "ar"), ("es", "er"), ("a", "ar"), ("e", "er"), ("o", "ar"), ("o", "er"), ("o", "ir"),
            ("ó", "ar"), ("ó", "er")]
# Pronouns written onto the end of a verb (dímelo, cúrale, levántate, decírselo, vámonos).
_CLITIC = re.compile(r"(?:(me|te|se|nos|os)(lo|la|los|las|le|les)?|(lo|la|los|las|le|les))$")
_WEAK = re.compile(r"^(?:(?:a )?(?:male |female )?(?:given name|surname)(?:; )?)+$|"
                   r"^(?:[^;]*\b(?:initialism|abbreviation|acronym) of\b[^;]*(?:; |$))+$", re.I)


_SHORT_COMMANDS = {"pon", "ten", "ven", "haz", "sal", "mantén", "detén", "propón", "supón", "compón"}   # ponlo, hazme, ven


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
    if not (plain.endswith(("r", "ndo")) or plain[-1:] in "aeiouds" or plain in _SHORT_COMMANDS):
        return []                                   # pronouns attach to an infinitive, a gerund or a command
    return out


def candidates(word: str) -> list[tuple[str, str]]:
    """(key, how) pairs to try, best first, for a normalised word."""
    d = dictionary()
    out: list[tuple[str, str]] = [(word, "exact")]
    # a plural is the surest guess (casas -> casa, luces -> luz), before any accent variant (casás)
    out += [(word[: -len(a)] + b, "ending") for a, b in _ENDINGS[:3] if word.endswith(a) and len(word) > len(a) + 1]
    out += [(k, "accent") for k in (*d.folded.get(fold(word), []), *_CORE_FOLDED.get(fold(word), []))]   # dimelo -> dímelo
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
    if key in CORE:
        out.append({"src": "core", "text": CORE[key]})
    wik = [{"src": "wiktionary", "text": t, "pos": pos} for pos, t in d.senses(key)]
    if any(not _WEAK.match(x["text"]) for x in wik):
        wik = [x for x in wik if not _WEAK.match(x["text"])]
    return out + wik


def _strong(senses: list[dict]) -> bool:
    return any(s["src"] != "wiktionary" or not _WEAK.match(s["text"]) for s in senses)


def _finite(codes: list[str]) -> bool:
    return any(not c.startswith(("pp", "ger", "prp")) for c in codes)


def _also_ok(row: dict, hit: dict) -> bool:
    """Not only a name or an abbreviation, and not a word ten times rarer than the answer."""
    d = dictionary()
    lem = row["lemma"]
    if lem in CORE or any(s["src"] == "mine" for s in row["senses"]):
        return True
    if d.flags.get(lem):
        return False
    z_hit = d.zipf.get(hit["lemma"])
    return z_hit is None or d.zipf.get(lem, -1) >= z_hit - 1


def _codes(key: str, lem: str) -> list[tuple[str, list[str]]]:
    """The conjugation readings of ``key``: its lemma's first, then other common verbs it is also a form of."""
    d = dictionary()
    if not d.codes(key, lem):
        return []                                    # casas is casa's plural: casar's "you marry" is not said
    z = d.zipf.get(lem)
    out = []
    for x in [lem, *sorted((y for y in d.lemmas_of(key) if y != lem), key=lambda y: _VERB_RANK.get(y, 99))]:
        c = d.codes(key, x)
        if c and (x == lem or z is None or d.zipf.get(x, -1) >= z - 1):
            out.append((x, c))
    return out[:2]


def lookup(raw, mine: dict | None = None) -> dict:
    """Look a word up. -> {found, word, lemma, path, how, gram, senses, also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    d = dictionary()
    hit = None
    also: list[dict] = []
    for key, how in candidates(word):
        path0 = [word] if key == word else [word, key]
        own = [(key, path0, how)]
        lems = sorted((x for x in d.lemmas_of(key) if x != key), key=lambda x: _VERB_RANK.get(x, 99))
        forms = [(lem, path0 + [lem], "form" if how == "exact" else how) for lem in lems]
        first = [f for f in forms if f[0] in _VERB_RANK and (_finite(d.codes(key, f[0])) or key in VERB_FIRST_FORMS)]
        if how == "pronouns":
            # under attached pronouns there is a verb: di|melo is decir, not the particle "di"
            verbs = [f for f in forms if d.codes(key, f[0])]
            tries = verbs + [f for f in forms if f not in verbs] + \
                [o for o in own if any(p == "verb" for p, _ in d.senses(key)) or not verbs]
        elif first and key not in mine and key not in OWN_FIRST and (key not in CORE or key in VERB_FIRST_FORMS):
            tries = first + own + [f for f in forms if f not in first]
        else:
            tries = own + forms
        for lem, path, h in tries:
            senses = _senses(lem, mine)
            if not senses:
                continue
            row = {"lemma": lem, "path": path, "how": h, "senses": senses}
            if lem != key:
                row["codes"] = _codes(key, lem)
                if h == "pronouns":       # pronouns go on a command, an infinitive or a gerund: not on "di" (I gave)
                    row["codes"] = [(x, c2) for x, c2 in ((x, [c for c in cs if c.startswith(("imp", "ger"))])
                                                          for x, cs in row["codes"]) if c2]
                    if d.codes(key, lem) and not any(x == lem for x, _ in row["codes"]):
                        continue
            if (row.get("codes") or h == "pronouns") and any(s.get("pos") == "verb" for s in senses):
                row["senses"] = [s for s in senses if s["src"] != "wiktionary" or s.get("pos") == "verb"]
            elif key in CORE and not d.lem.get(key):  # hay (there is): also say it is haber's
                row["codes"] = next(([(x, d.codes(key, x))] for x in lems if d.codes(key, x)), [])
            if h == "pronouns":
                m = _CLITIC.search(word)
                row["attached"] = " + ".join(x for x in (m.group(1), m.group(2), m.group(3)) if x) if m else ""
            if hit is None and _strong(row["senses"]):
                hit = row
            elif all(lem != x["lemma"] for x in also) and (hit is None or lem != hit["lemma"]):
                also.append(row)
        if hit is not None:
            break
    if hit is None and also:
        hit, also = also[0], also[1:]                # only a weak entry (a surname): show it, say so
    if hit:
        also = [a for a in also if _also_ok(a, hit)]
        for row in (hit, *also):
            gram = kaikki.gram_text(row.pop("codes", []), LANG)
            attached = row.pop("attached", "")
            if attached:
                gram = f"{gram} + {attached} (pronouns attached)" if gram else f"+ {attached} (pronouns attached)"
            row["gram"] = gram
    out = {"ok": True, "word": word, "found": hit is not None, "also": also[:3], "credit": CREDIT}
    if hit:
        out.update(hit)
        out["weak"] = not _strong(hit["senses"])
    else:
        out.update(lemma="", path=[word], how="", gram="", senses=[], weak=False)
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
        for src, pairs in (("mine", [(k, v.lower()) for k, v in mine.items()]), ("core", [(k, v.lower()) for k, v in CORE.items()]),
                           ("wiktionary", d.low)):
            for es, gl in pairs:
                if q not in gl or (src == "wiktionary" and _WEAK.match(gl)):
                    continue
                senses = [re.sub(r"\s*\([^()]*\)", "", s).strip() for s in gl.split(";")]
                score = 0 if (q in senses or f"to {q}" in senses) else 1 if pat.search(gl) else 2
                # among equals: a word the frequency list knows, then more senses (common words have many)
                scored.append((src != "mine", score, -d.zipf.get(es, 0), src != "core", -gl.count(";"), len(gl), es, src))
        scored.sort()
        for *_, es, src in scored[: limit * 3]:
            en = mine.get(es) if src == "mine" else CORE.get(es) if src == "core" else d.text(es)
            rows.append((es, en, src))
    else:
        keys = _keys()
        w = norm_word(q) or q
        look = lookup(w, mine) if norm_word(q) else None
        if look and look["found"]:
            rows.append((look["lemma"], look["senses"][0]["text"], look["senses"][0]["src"]))
        for k, v in mine.items():
            if k.startswith(w):
                rows.append((k, v, "mine"))
        i = bisect_left(keys, w)
        while i < len(keys) and keys[i].startswith(w) and len(rows) < limit * 2:
            k = keys[i]
            rows.append((k, CORE.get(k) or d.text(k), "core" if k in CORE else "wiktionary"))
            i += 1
        if len(rows) < limit:
            for k in keys:
                if w in k and not k.startswith(w):
                    rows.append((k, CORE.get(k) or d.text(k), "core" if k in CORE else "wiktionary"))
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


_all_keys: list[str] = []


def _keys() -> list[str]:
    """Every headword and core word, sorted (prefix search)."""
    global _all_keys
    if not _all_keys:
        d = dictionary()
        _all_keys = sorted(set(d.keys) | set(CORE))
    return _all_keys
