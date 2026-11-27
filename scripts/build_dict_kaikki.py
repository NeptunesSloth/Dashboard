"""Build the Spanish, French and Korean dictionaries for the reader from English Wiktionary (kaikki.org / wiktextract).

    python scripts/build_dict_kaikki.py                # all three languages
    python scripts/build_dict_kaikki.py ko             # one
    python scripts/build_dict_kaikki.py fr --cache /some/dir --keep   # keep the slim extract to rebuild offline

Stage 1 streams the kaikki.org JSONL (0.6-1.1 GB) line by line straight from the network and keeps only what
the reader needs (headword, part of speech, forms with their tags, romanisation, glosses with their tags) in a
small gzip "slim" file in a cache directory; the raw download is never written to disk. For Spanish and French
it also fetches a word-frequency list (FrequencyWords, OpenSubtitles 2018, top 50,000 words; CC BY-SA 4.0), used
only at build time to mark rare lemmas. Stage 2 builds ``sect_academy/dict/<lang>/<lang>_en.tsv.gz`` from the
slim file. The cache is deleted afterwards unless ``--keep`` is given (with ``--cache`` existing files are
reused, so stage 2 can be re-run offline).

Output (gzip of UTF-8 text, tab-separated, one entry per line, sorted):

    L <tab> lemma <tab> gloss <tab> romanisation (Korean) <tab> flags <tab> frequency
    F <tab> form  <tab> lemma[|lemma2...]          inflected form -> its lemma(s)
    C <tab> lemma <tab> form=code[/code],...        a verb's conjugation: each form with its tense/person code(s)
    P <tab> headword                               a set phrase / interjection (Korean)

The gloss is one or more sections, ``pos: sense; sense | pos: sense``: one per Wiktionary entry (part of speech
or homograph), best first (common words before proper nouns, abbreviations and dialect words; a handful of
Korean homographs in a curated order, since the data has no frequencies). Flags: ``p`` the headword is only a
proper noun, ``a`` only an abbreviation (or a proper noun). Frequency (Spanish, French): log10 of the best count
in the frequency list of the headword or of a form only it has; none for a rare word. A code is ``mood.tense.person`` (``ind.pret.3s``, ``subj.impf.13s``, ``imp.2p``,
``cond.pres.1p``, ``pp.fs``, ``ger``); ``lexicon/kaikki.py`` turns it into words.

Source and licence: English Wiktionary, by the Wiktionary contributors, CC BY-SA 4.0 (and GFDL), via
kaikki.org's wiktextract extracts. The built files carry that licence (see dict/<lang>/README.md).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://kaikki.org/dictionary/{name}/kaikki.org-dictionary-{name}.jsonl"
FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/{lang}/{lang}_50k.txt"
NAMES = {"es": "Spanish", "fr": "French", "ko": "Korean"}

MAX_FIRST = 4                 # senses from the first section
MAX_OTHER = 2                 # ... and from each later one
MAX_SECTIONS = 4
MAX_SENSE_CHARS = 90
MAX_GLOSS_CHARS = 320
MAX_HEAD_WORDS = 4            # multiword headwords longer than this are dropped
SKIP_POS = {"character", "symbol", "romanization", "prefix", "suffix", "infix", "interfix", "circumfix",
            "affix", "proverb", "punct", "syllable", "root"}
DROP_TAGS = {"obsolete", "archaic", "dated", "rare", "historical", "nonstandard", "misspelling", "Middle-Korean"}
NAME_GLOSS = re.compile(r"\b(?:given name|surname|family name|patronymic)\b", re.I)
FUNCTION_POS = {"article", "det", "contraction", "pron", "prep", "conj"}   # their "form of" gloss is their meaning
PHRASE_POS = {"intj", "phrase"}
SOFT_TAGS = {"dated", "rare", "neologism"}
FORM_SKIP_TAGS = {"table-tags", "inflection-template", "romanization", "hangeul", "hanja", "class",
                  "auxiliary", "multiword-construction", "canonical"}
# Spanish conjugation-table forms the reader leaves to its rules or does not need: pronouns attached (dímelo is
# taken apart by lexicon/es.py), voseo, negative imperatives (= the subjunctive) and the future subjunctive
ES_FORM_SKIP = {"with-voseo", "vos-form", "negative", "reflexive", "dative", "accusative", "object-first-person",
                "object-second-person", "object-third-person", "combined-form"}
ABBR_TAGS = {"abbreviation", "initialism", "acronym", "clipping"}
ABBR_GLOSS = re.compile(r"^(?:initialism|abbreviation|acronym|clipping|symbol) of\b", re.I)
# a sense's tags -> how far down its section it goes (0 first)
LATE_TAGS = {"colloquial": 1, "informal": 1, "figuratively": 1, "slang": 2, "vulgar": 3, "derogatory": 3,
             "offensive": 3, "pejorative": 3, "euphemistic": 2, "humorous": 2, "dialectal": 2, "uncommon": 2,
             "neologism": 3, "Internet": 2, "ironic": 2}
LETTERS = {"es": r"[a-záéíóúüñ' -]+", "fr": r"[a-zàâäæçéèêëîïôœùûüÿ'’ -]+"}

# Korean homographs share one spelling and the data has no frequencies: the usual word first (a gloss word of
# the section that should lead, in order). Everything else keeps Wiktionary's order.
KO_FIRST = {
    "시장": ["market", "mayor"], "사과": ["apple", "apology"], "다리": ["leg", "bridge"], "감": ["persimmon"],
    "김": ["laver", "steam"], "손": ["hand"], "발": ["foot"], "병": ["bottle", "illness", "disease"],
    "상": ["prize", "award", "table"], "일": ["work", "day", "one"], "이": ["this", "tooth", "two"],
    "비": ["rain"], "말": ["speech", "words", "language", "horse"], "차": ["vehicle", "car", "tea"],
    "밤": ["night", "chestnut"], "눈": ["eye", "snow"], "배": ["belly", "abdomen", "ship", "pear"],
    "전": ["before", "previous"], "방": ["room"], "길": ["road", "way"], "물": ["water"], "집": ["house", "home"],
    "돈": ["money"], "문": ["door"], "공": ["ball", "zero"], "성": ["castle", "sex"], "수": ["number", "means"],
    "약": ["medicine", "drug", "about"], "점": ["point", "dot", "spot"], "장": ["sheet", "chapter", "market"],
    "가방": ["bag"], "자": ["ruler"], "새": ["bird", "new"], "형": ["older brother"],
    "역": ["station"], "층": ["floor", "storey"], "번": ["number", "time"], "주": ["week"], "달": ["moon", "month"],
    "해": ["sun", "year"], "분": ["minute", "person"], "시": ["o'clock", "hour", "poem", "city"], "살": ["years old", "age", "flesh"],
    "책": ["book"], "옷": ["clothes"], "밥": ["rice", "meal"], "술": ["alcohol", "liquor"], "표": ["ticket"],
    "쓰다": ["write", "use", "bitter", "wear"], "타다": ["ride", "board", "burn"], "차다": ["kick", "cold", "full"],
    "맞다": ["correct", "right", "be hit"], "자다": ["sleep"], "서다": ["stand"], "들다": ["enter", "hold", "lift"],
    "싸다": ["cheap", "wrap"], "빨다": ["wash", "suck"], "묻다": ["ask", "bury"], "걷다": ["walk"],
    "있다": ["exist", "have"], "네": ["yes"], "저": ["I, me"], "제": ["my"], "명": ["counter for people"],
    "못": ["cannot"], "씨": ["Mr"], "안": ["not"], "와": ["wow"], "우리": ["we"], "천": ["thousand"],
    "개": ["general counter", "dog"], "그": ["he", "that"], "거": ["thing"], "때": ["time"], "곳": ["place"],
}


# ---------------------------------------------------------------------------
# stage 1: stream and slim
# ---------------------------------------------------------------------------
def slim(d: dict) -> dict | None:
    w, pos = d.get("word"), d.get("pos")
    if not isinstance(w, str) or not isinstance(pos, str):
        return None
    forms = []
    rom = ""
    for f in d.get("forms") or []:
        if not isinstance(f, dict) or not isinstance(f.get("form"), str):
            continue
        tags = [t for t in f.get("tags") or [] if isinstance(t, str)]
        if "romanization" in tags and not rom:
            rom = f["form"]
            continue
        forms.append([f["form"], tags, f.get("roman") if isinstance(f.get("roman"), str) else ""])
    for s in d.get("sounds") or []:
        if isinstance(s, dict) and not rom:
            for k in ("roman", "romanization"):
                if isinstance(s.get(k), str):
                    rom = s[k]
                    break
    senses = []
    for s in d.get("senses") or []:
        if not isinstance(s, dict):
            continue
        gl = [g for g in s.get("glosses") or [] if isinstance(g, str)]
        fo = [x.get("word") for x in (s.get("form_of") or []) + (s.get("alt_of") or [])
              if isinstance(x, dict) and isinstance(x.get("word"), str)]
        senses.append({"g": gl[-1] if gl else "", "t": [t for t in s.get("tags") or [] if isinstance(t, str)], "fo": fo})
    return {"w": w, "p": pos, "l": d.get("lang_code", ""), "r": rom, "f": forms, "s": senses}


def extract(lang: str, out: Path) -> None:
    url = URL.format(name=NAMES[lang])
    print(f"[{lang}] streaming {url}", file=sys.stderr)
    n = kept = 0
    req = urllib.request.Request(url, headers={"User-Agent": "dictionary-builder"})
    with urllib.request.urlopen(req, timeout=120) as resp, gzip.open(out, "wt", encoding="utf-8") as fo:   # noqa: S310
        for raw in resp:                        # line by line: the file is never held in memory or on disk
            n += 1
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("lang_code") != lang:
                continue
            s = slim(d)
            if s:
                fo.write(json.dumps(s, ensure_ascii=False) + "\n")
                kept += 1
            if n % 100000 == 0:
                print(f"[{lang}] {n:,} lines, {kept:,} kept", file=sys.stderr)
    print(f"[{lang}] done: {n:,} lines, {kept:,} kept", file=sys.stderr)


def fetch_freq(lang: str, out: Path) -> None:
    url = FREQ_URL.format(lang=lang)
    print(f"[{lang}] fetching {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "dictionary-builder"})
    with urllib.request.urlopen(req, timeout=120) as resp:                                         # noqa: S310
        out.write_bytes(resp.read())


def load_freq(path: Path | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if path is None or not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) == 2 and p[1].isdigit():
            out.setdefault(p[0].lower(), int(p[1]))
    return out


def records(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


# ---------------------------------------------------------------------------
# stage 2: build the tables
# ---------------------------------------------------------------------------
_PAREN_LONG = re.compile(r"\s*\([^()]{40,}\)")
_SPACES = re.compile(r"\s+")


def trim_gloss(g: str) -> str:
    g = _PAREN_LONG.sub("", g)
    g = _SPACES.sub(" ", g.replace("\t", " ")).strip().rstrip(".")
    if len(g) > MAX_SENSE_CHARS:
        cut = g[:MAX_SENSE_CHARS]
        for sep in ("; ", ", ", " "):
            i = cut.rfind(sep)
            if i > 30:
                cut = cut[:i]
                break
        g = cut.rstrip(",;: ") + "…"
    return g.replace(";", ",").replace("|", "/")      # "; " separates senses and " | " sections in the table


_FORM_GLOSS = re.compile(r"^(?:.*\b(?:form|participle|plural|singular|person|tense|indicative|subjunctive|imperative|"
                         r"conditional|feminine|masculine|infinitive|spelling|alternative|abbreviation|contraction)\b.*\bof\b)",
                         re.I)


_MISSPELT = re.compile(r"\b(?:misspelling|nonstandard (?:form|spelling)|eye dialect|pronunciation spelling) of\b", re.I)


def good_head(w: str) -> bool:
    return 0 < len(w) <= 40 and len(w.split()) <= MAX_HEAD_WORDS and not w.startswith("-") and not w.endswith("-")


def romanise_ko(s: str) -> str:
    sys.path.insert(0, str(ROOT))
    from sect_academy.lexicon.ko import romanise
    return romanise(s)


_PERSON = {"first-person": "1", "second-person": "2", "third-person": "3"}


def gram_codes(tags: set[str]) -> list[str]:
    """A verb form's tags -> its codes ("ind.pret.3s"); [] for anything that is not a single conjugated form."""
    if tags & {"multiword-construction", "infinitive", "future-subjunctive"} or (
            "future" in tags and "subjunctive" in tags):
        return []
    if "participle" in tags and "past" in tags:
        fem = "feminine" in tags and "masculine" not in tags
        plural = "plural" in tags and "singular" not in tags
        return ["pp" + (".fp" if fem and plural else ".fs" if fem else ".mp" if plural else "")]
    if "gerund" in tags:
        return ["ger"]
    if "participle" in tags and "present" in tags:
        return ["prp"]
    persons = "".join(sorted(_PERSON[t] for t in tags if t in _PERSON))
    num = "p" if "plural" in tags else "s" if "singular" in tags else ""
    if not persons or not num:
        return []
    pn = persons + num
    if "imperative" in tags:
        return [f"imp.{pn}" + (".f" if "formal" in tags else "")]
    if "conditional" in tags:
        return [f"cond.pres.{pn}"]
    mood = "subj" if "subjunctive" in tags else "ind"
    tenses = []
    if "historic" in tags and "past" in tags:
        tenses.append("ph")
    if "present" in tags:
        tenses.append("pres")
    if "preterite" in tags:
        tenses.append("pret")
    if "imperfect" in tags:
        tenses.append("impf")
    if "future" in tags:
        tenses.append("fut")
    return [f"{mood}.{t}.{pn}" for t in tenses]


def merge_codes(codes: list[str]) -> list[str]:
    """One code per tense and number: ind.pres.1s + ind.pres.2s + ind.pres.12s -> ind.pres.12s (order kept)."""
    out: dict[tuple, set[str]] = {}
    for c in codes:
        p = c.split(".")
        i = 1 if p[0] == "imp" else 2
        if len(p) <= i or not re.fullmatch(r"[123]+[sp]", p[i]):
            out.setdefault((c,), set())
            continue
        out.setdefault((".".join(p[:i]), p[i][-1], ".".join(p[i + 1:])), set()).update(p[i][:-1])
    res = []
    for k, persons in out.items():
        if len(k) == 1:
            res.append(k[0])
        else:
            res.append(".".join(x for x in (k[0], "".join(sorted(persons)) + k[1], k[2]) if x))
    return sorted(res, key=lambda c: next((i for i, p in enumerate(CODE_ORDER) if c.startswith(p)), len(CODE_ORDER)))


# the order a form's readings are named in: the indicative present first (mange: "I eat" before "that I eat")
CODE_ORDER = ["ind.pres", "ind.pret", "ind.impf", "ind.ph", "ind.fut", "cond", "subj.pres", "subj.impf", "imp", "pp",
              "ger", "prp"]


def _late(tags: set[str]) -> int:
    n = max((LATE_TAGS.get(t, 0) for t in tags), default=0)
    if any(t[:1].isupper() and t not in ("Internet",) for t in tags):
        n = max(n, 1)                      # a regional label (Spain, Mexico, Quebec, North-Korea)
    return n


def build(lang: str, slim_path: Path, freq: dict[str, int] | None = None) -> dict:
    freq = freq or {}
    sections: dict[str, list[dict]] = {}   # key -> [{pos, senses, flag, n}]
    rom: dict[str, str] = {}
    forms: dict[str, list[str]] = {}       # form -> lemmas
    para: dict[str, dict[str, list[str]]] = {}   # verb lemma -> form -> codes
    phrases: set[str] = set()
    letters = re.compile(LETTERS[lang]) if lang in LETTERS else None
    lower = lang in ("fr", "es")

    def add_form(form: str, lemma: str) -> None:
        if not form or form == lemma or not good_head(form) or len(form.split()) > 2:
            return
        lst = forms.setdefault(form, [])
        if lemma not in lst:
            lst.append(lemma)

    def add_code(lemma: str, form: str, tags: set[str]) -> None:
        codes = gram_codes(tags)
        if codes and form != lemma:
            lst = para.setdefault(lemma, {}).setdefault(form, [])
            lst += [c for c in codes if c not in lst]

    n_rec = 0
    for d in records(slim_path):
        w, pos = d["w"], d["p"]
        if not good_head(w):
            continue
        if lang == "ko" and not re.search(r"[가-힣]", w):
            continue                       # hanja-only headwords: the reader looks up Hangul
        key = w.lower() if lower else w
        capital = key != w
        for s in d["s"]:
            tags = set(s["t"])
            if lang == "es" and tags & ES_FORM_SKIP and pos == "verb":
                continue                   # dímelo, hablás: taken apart by rule, or voseo
            if tags & DROP_TAGS or "Internet" in tags or _MISSPELT.search(s["g"] or ""):
                continue                   # a misspelling or an obsolete form is not a reading of the word
            for lem in s["fo"]:
                if lem and lem != w and good_head(lem) and (tags & {"form-of", "alt-of"} or _FORM_GLOSS.search(s["g"] or "")):
                    if capital and (tags & ABBR_TAGS or ABBR_GLOSS.search(s["g"] or "")):
                        continue           # "NE" (abbreviation of nord-est) is not a form of lower-case "ne"
                    lem_k = lem.lower() if lower else lem
                    add_form(key, lem_k)
                    if pos == "verb" and lang != "ko":
                        add_code(lem_k, key, tags)
        if pos in SKIP_POS:
            continue
        keep, dated = [], []
        for s in d["s"]:
            tags = set(s["t"])
            if lang == "es" and {"feminine", "masculine"} <= tags:
                tags.discard("archaic")    # "fin (m or archaic f)": the archaic gender, not an archaic word
            if not s["g"] or "no-gloss" in tags or tags & (DROP_TAGS - SOFT_TAGS):
                continue
            if tags & SOFT_TAGS:           # "dated", "rare", "neologism": kept only when the word has nothing else
                if not s["fo"] and not (pos == "name" and NAME_GLOSS.search(s["g"])):
                    dated.append((trim_gloss(s["g"]), "auxiliary" in tags, tags))
                continue
            if s["fo"] and (tags & {"form-of", "alt-of"}) and pos not in FUNCTION_POS:
                continue                   # an inflected form: its meaning is its lemma's
            if pos == "name" and NAME_GLOSS.search(s["g"]):
                continue                   # people's names: places (Londres, 서울) stay
            keep.append((trim_gloss(s["g"]), "auxiliary" in tags, tags))
        soft = not keep and bool(dated)
        keep = keep or dated
        if lower and capital and not keep:
            continue
        main = [k for k in keep if not k[1]]
        keep = main or keep                # an auxiliary-verb sense only when it is the only one
        if keep:
            keep = sorted(keep, key=lambda k: _late(k[2]))     # stable: Wiktionary's order among equals
            senses = []
            for g, _aux, _t in keep:
                if g not in senses:
                    senses.append(g)
            abbr = all((t & ABBR_TAGS and "contraction" not in t) or ABBR_GLOSS.search(g) for g, _a, t in keep)
            regional = all(_late(t) >= 2 or (lang == "ko" and _late(t) >= 1) for _g, _a, t in keep)
            flag = "a" if abbr else "p" if (pos == "name" or capital) else "r" if (soft or regional) else ""
            sections.setdefault(key, []).append({"pos": pos, "senses": senses, "flag": flag, "n": n_rec, "cap": capital})
            n_rec += 1
            if pos in PHRASE_POS and lang == "ko":
                phrases.add(key)
        if lang == "ko" and key not in rom:
            rom[key] = d["r"] or ""
        if lower and pos not in ("noun", "adj", "verb"):
            continue                       # a pronoun's "forms" are its relatives (je -> nous), not inflections
        for form, ftags, _froman in d["f"]:
            ft = set(ftags)
            if ft & FORM_SKIP_TAGS or ft & DROP_TAGS:
                continue
            if lang == "es" and (ft & ES_FORM_SKIP or ("future" in ft and "subjunctive" in ft)):
                continue
            form = form.lower() if lower else form
            if lang == "ko" and not re.fullmatch(r"[가-힣]+", form):
                continue
            if letters and not letters.fullmatch(form):
                continue
            form = form.replace("’", "'")
            add_form(form, key)
            if pos == "verb" and lower and not capital:
                add_code(key, form, ft)

    # ---- the gloss of each lemma: its sections, best first
    rank = {"": 0, "r": 1, "p": 2, "a": 3}
    gloss: dict[str, str] = {}
    lflags: dict[str, str] = {}
    zipf: dict[str, str] = {}
    for key, secs in sections.items():
        prefer = KO_FIRST.get(key, []) if lang == "ko" else []

        def order(s: dict) -> tuple:
            text = " ".join(s["senses"]).lower()
            hit = next((i for i, p in enumerate(prefer) if re.search(r"\b" + re.escape(p) + r"\b", text, re.I)), len(prefer))
            return (rank[s["flag"]], hit, s["n"])
        if not all(s["cap"] for s in secs):
            secs = [s for s in secs if not s["cap"]]                 # "CE" or "NE" never adds to "ce" or "ne": only fills a gap
        secs = sorted(secs, key=order)
        if any(s["flag"] == "" for s in secs):
            secs = [s for s in secs if s["flag"] != "r"]            # dialect / dated homographs: not beside the usual word
        out, total, seen = [], 0, set()
        for s in secs[:MAX_SECTIONS]:
            room = MAX_FIRST if not out else MAX_OTHER
            take = [g for g in s["senses"] if g not in seen][:room]
            if not take:
                continue
            text = f"{s['pos']}: " + "; ".join(take)
            if out and total + len(text) + 3 > MAX_GLOSS_CHARS:
                break
            seen.update(take)
            out.append(text)
            total += len(text) + 3
        gloss[key] = " | ".join(out)[:MAX_GLOSS_CHARS + 40]
        flags = {s["flag"] for s in secs}
        if flags <= {"p"}:
            lflags[key] = "p"
        elif flags <= {"a", "p"}:
            lflags[key] = "a"

    # ---- rare lemmas: no string only they have (headword or form) is in the frequency list, and the headword is
    # not a frequent word that is also a form of something else ("casa" is also casar's: unknown, not rare)
    if freq:
        claims: dict[str, int] = {}
        for form, lems in forms.items():
            claims[form] = len({x for x in lems if x in gloss}) + (1 if form in gloss else 0)
        score: dict[str, int] = {}
        for lem in gloss:
            if freq.get(lem, 0) > 0:
                score[lem] = freq[lem]     # frequent as written: unambiguous, or too ambiguous to call rare
        for form, lems in forms.items():
            ls = [x for x in lems if x in gloss]
            if len(ls) == 1 and claims[form] == 1 and freq.get(form, 0) > score.get(ls[0], 0):
                score[ls[0]] = freq[form]
        for lem in gloss:
            if lem in score:
                zipf[lem] = str(min(9, int(math.log10(score[lem]))))

    rows = []
    for lem, g in gloss.items():
        r = ""
        if lang == "ko":
            r = re.sub(r"[^a-z' -]", "", (rom.get(lem) or romanise_ko(lem)).lower()).strip()
        rows.append("\t".join(["L", lem, g, r, lflags.get(lem, ""), zipf.get(lem, "")]).rstrip("\t"))
    nf = 0
    for form, lems in forms.items():
        lems = [x for x in lems if x in gloss]
        lems = sorted(lems, key=lambda x: bool(freq) and x not in zipf)[:3]          # rare lemmas last
        if lang == "es" and lems and form not in gloss:
            # Spanish keeps fewer forms (memory): not those of rare verbs, which the reader's ending rules still
            # take back to the verb, nor plurals and feminines those rules make (casas -> casa, buena -> bueno)
            if all(x in para and x not in zipf for x in lems):
                continue
            lem = lems[0]
            if len(lems) == 1 and (form in (lem + "s", lem + "es") or (lem.endswith("z") and form == lem[:-1] + "ces")
                                   or (lem.endswith("o") and form in (lem[:-1] + "a", lem[:-1] + "as", lem[:-1] + "os"))):
                continue
        if lems:
            rows.append(f"F\t{form}\t{'|'.join(lems)}")
            nf += 1
    nc = 0
    for lem, tab in para.items():
        if lem not in gloss or (lang == "es" and lem not in zipf):
            continue
        cells = [f"{f}={'/'.join(merge_codes(c))}" for f, c in tab.items() if f in forms and lem in forms[f]]
        if cells:
            rows.append(f"C\t{lem}\t{','.join(cells)}")
            nc += 1
    rows += [f"P\t{p}" for p in phrases if p in gloss]
    rows.sort()
    out = ROOT / "sect_academy" / "dict" / lang / f"{lang}_en.tsv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=9) as f:
        f.write(("\n".join(rows) + "\n").encode("utf-8"))
    stats = {"lemmas": len(gloss), "forms": nf, "conjugations": nc, "rare": len(gloss) - len(zipf) if freq else 0,
             "bytes": out.stat().st_size}
    print(f"[{lang}] wrote {out.relative_to(ROOT)}: {stats}", file=sys.stderr)
    return stats


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("langs", nargs="*", choices=sorted(NAMES), help="languages to build (default: all)")
    ap.add_argument("--cache", help="directory for the slim extract and frequency list (default: a temporary one)")
    ap.add_argument("--keep", action="store_true", help="keep the cache")
    a = ap.parse_args(argv)
    cache = Path(a.cache) if a.cache else Path(tempfile.mkdtemp(prefix="dict-kaikki-"))
    cache.mkdir(parents=True, exist_ok=True)
    try:
        for lang in a.langs or ["es", "fr", "ko"]:
            sp = cache / f"{lang}.slim.jsonl.gz"
            if not sp.exists():
                tmp = sp.with_suffix(".part")
                extract(lang, tmp)
                tmp.rename(sp)
            fp = None
            if lang in ("es", "fr"):
                fp = cache / f"{lang}_50k.txt"
                if not fp.exists():
                    fetch_freq(lang, fp)
            build(lang, sp, load_freq(fp))
    finally:
        if not a.keep:
            shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    main()
