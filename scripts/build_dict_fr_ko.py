"""Build the French and Korean dictionaries for the reader from English Wiktionary (kaikki.org / wiktextract).

    python scripts/build_dict_fr_ko.py             # both languages
    python scripts/build_dict_fr_ko.py ko          # one
    python scripts/build_dict_fr_ko.py fr --cache /some/dir --keep   # keep the slim extract to rebuild offline

Stage 1 streams the kaikki.org JSONL (hundreds of MB) line by line straight from the network and keeps only
what the reader needs (headword, part of speech, forms, romanisation, the first glosses) in a small gzip
"slim" file in a temporary cache directory; the raw download is never written to disk. Stage 2 builds
``sect_academy/dict/<lang>/<lang>_en.tsv.gz`` from the slim file. The cache is deleted afterwards unless
``--keep`` is given (with ``--cache`` an existing slim file is reused, so stage 2 can be re-run offline).

Output (gzip of UTF-8 text, tab-separated, one entry per line, sorted):

    L <tab> lemma <tab> English gloss [<tab> romanisation (Korean)]   senses separated by "; "
    F <tab> form  <tab> lemma[|lemma2...]                                 inflected form -> its lemma(s)
    P <tab> headword                                                      a set phrase / interjection (Korean)

Source and licence: English Wiktionary, by the Wiktionary contributors, CC BY-SA 4.0 (and GFDL), via
kaikki.org's wiktextract extracts. The built files carry that licence (see dict/<lang>/README.md).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://kaikki.org/dictionary/{name}/kaikki.org-dictionary-{name}.jsonl"
NAMES = {"fr": "French", "ko": "Korean"}

MAX_SENSES = 3
MAX_SENSE_CHARS = 90
MAX_GLOSS_CHARS = 240
MAX_HEAD_WORDS = 4            # multiword headwords longer than this are dropped
SKIP_POS = {"character", "symbol", "romanization", "prefix", "suffix", "infix", "interfix", "circumfix",
            "affix", "proverb", "punct", "syllable", "root"}
DROP_TAGS = {"obsolete", "archaic", "dated", "rare", "historical", "nonstandard", "misspelling", "Middle-Korean"}
NAME_GLOSS = re.compile(r"\b(?:given name|surname|family name|patronymic)\b", re.I)
FUNCTION_POS = {"article", "det", "contraction", "pron", "prep", "conj"}   # their "form of" gloss is their meaning
PHRASE_POS = {"intj", "phrase"}
SOFT_TAGS = {"dated", "rare"}
FORM_SKIP_TAGS = {"table-tags", "inflection-template", "romanization", "hangeul", "hanja", "class",
                  "auxiliary", "multiword-construction", "canonical"}


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
    with urllib.request.urlopen(req, timeout=120) as resp, gzip.open(out, "wt", encoding="utf-8") as fo:
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
    return g.replace(";", ",")          # "; " separates senses in the table


_FORM_GLOSS = re.compile(r"^(?:.*\b(?:form|participle|plural|singular|person|tense|indicative|subjunctive|imperative|"
                         r"conditional|feminine|masculine|infinitive|spelling|alternative|abbreviation|contraction)\b.*\bof\b)",
                         re.I)


def good_head(w: str) -> bool:
    return 0 < len(w) <= 40 and len(w.split()) <= MAX_HEAD_WORDS and not w.startswith("-") and not w.endswith("-")


def romanise_ko(s: str) -> str:
    sys.path.insert(0, str(ROOT))
    from sect_academy.lexicon.ko import romanise
    return romanise(s)


def build(lang: str, slim_path: Path) -> dict:
    gloss: dict[str, list[str]] = {}       # lemma -> senses (in order, deduplicated)
    rom: dict[str, str] = {}
    forms: dict[str, list[str]] = {}       # form -> lemmas
    phrases: set[str] = set()
    upper: dict[str, list[str]] = {}       # senses of capitalised headwords (French), used only as a fallback

    def add_form(form: str, lemma: str) -> None:
        if not form or form == lemma or not good_head(form) or len(form.split()) > 2:
            return
        lst = forms.setdefault(form, [])
        if lemma not in lst:
            lst.append(lemma)

    for d in records(slim_path):
        w, pos = d["w"], d["p"]
        if not good_head(w):
            continue
        if lang == "ko" and not re.search(r"[가-힣]", w):
            continue                       # hanja-only headwords: the reader looks up Hangul
        key = w.lower() if lang == "fr" else w
        for s in d["s"]:
            tags = set(s["t"])
            for lem in s["fo"]:
                if lem and lem != w and good_head(lem) and (tags & {"form-of", "alt-of"} or _FORM_GLOSS.search(s["g"] or "")):
                    add_form(key, lem.lower() if lang == "fr" else lem)
        if pos in SKIP_POS:
            continue
        keep, dated = [], []
        for s in d["s"]:
            tags = set(s["t"])
            if not s["g"] or "no-gloss" in tags or tags & (DROP_TAGS - SOFT_TAGS):
                continue
            if tags & SOFT_TAGS:           # "dated" or "rare": kept only when the word has nothing else
                if not s["fo"] and not (pos == "name" and NAME_GLOSS.search(s["g"])):
                    dated.append((trim_gloss(s["g"]), "auxiliary" in tags))
                continue
            if s["fo"] and (tags & {"form-of", "alt-of"}) and pos not in FUNCTION_POS:
                continue                   # an inflected form: its meaning is its lemma's
            if pos == "name" and NAME_GLOSS.search(s["g"]):
                continue                   # people's names: places (Londres, 서울) stay
            keep.append((trim_gloss(s["g"]), "auxiliary" in tags))
        keep = keep or dated
        if lang == "fr" and w[:1].isupper() and w.lower() != w and not keep:
            continue
        main = [g for g, aux in keep if not aux]
        keep = main or [g for g, _ in keep]          # an auxiliary-verb sense only when it is the only one
        if keep:
            # "CE" or "Paris" never push out "ce" or "paris": capitalised headwords only fill a gap
            senses = (gloss if w == key else upper).setdefault(key, [])
            for g in keep:
                if g not in senses and len(senses) < MAX_SENSES + (1 if senses else 0):
                    senses.append(g)
            if pos in PHRASE_POS and lang == "ko":
                phrases.add(key)
        if lang == "ko" and key not in rom:
            rom[key] = d["r"] or ""
        if lang == "fr" and pos not in ("noun", "adj", "verb"):
            continue                       # a pronoun's "forms" are its relatives (je -> nous), not inflections
        for form, ftags, _froman in d["f"]:
            if set(ftags) & FORM_SKIP_TAGS or set(ftags) & DROP_TAGS:
                continue
            form = form.lower() if lang == "fr" else form
            if lang == "ko" and not re.fullmatch(r"[가-힣]+", form):
                continue
            if lang == "fr" and not re.fullmatch(r"[a-zàâäæçéèêëîïôœùûüÿ'’ -]+", form):
                continue
            add_form(form.replace("’", "'"), key)

    for k, v in upper.items():
        gloss.setdefault(k, v)
    rows = []
    for lem, senses in gloss.items():
        g = "; ".join(senses)[:MAX_GLOSS_CHARS]
        if lang == "ko":
            r = re.sub(r"[^a-z' -]", "", (rom.get(lem) or romanise_ko(lem)).lower()).strip()
            rows.append(f"L\t{lem}\t{g}\t{r}")
        else:
            rows.append(f"L\t{lem}\t{g}")
    nf = 0
    for form, lems in forms.items():
        lems = [x for x in lems if x in gloss][:3]
        if lems:
            rows.append(f"F\t{form}\t{'|'.join(lems)}")
            nf += 1
    rows += [f"P\t{p}" for p in phrases if p in gloss]
    rows.sort()
    out = ROOT / "sect_academy" / "dict" / lang / f"{lang}_en.tsv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=9) as f:
        f.write(("\n".join(rows) + "\n").encode("utf-8"))
    stats = {"lemmas": len(gloss), "forms": nf, "bytes": out.stat().st_size}
    print(f"[{lang}] wrote {out.relative_to(ROOT)}: {stats}", file=sys.stderr)
    return stats


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("langs", nargs="*", choices=["fr", "ko"], help="languages to build (default: both)")
    ap.add_argument("--cache", help="directory for the slim extract (default: a temporary one)")
    ap.add_argument("--keep", action="store_true", help="keep the slim extract")
    a = ap.parse_args(argv)
    cache = Path(a.cache) if a.cache else Path(tempfile.mkdtemp(prefix="dict-fr-ko-"))
    cache.mkdir(parents=True, exist_ok=True)
    try:
        for lang in a.langs or ["fr", "ko"]:
            sp = cache / f"{lang}.slim.jsonl.gz"
            if not sp.exists():
                tmp = sp.with_suffix(".part")
                extract(lang, tmp)
                tmp.rename(sp)
            build(lang, sp)
    finally:
        if not a.keep:
            shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    main()
