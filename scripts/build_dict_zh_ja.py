"""Build the reader's Mandarin and Japanese dictionaries (``sect_academy/dict/zh/`` and ``dict/ja/``).

    python scripts/build_dict_zh_ja.py                 # download both sources, build both files
    python scripts/build_dict_zh_ja.py --only zh       # or just one
    python scripts/build_dict_zh_ja.py --cedict F.gz --jmdict G.gz   # from files already downloaded

Sources (both CC BY-SA 4.0; see each folder's README for the licence statement):

* CC-CEDICT, https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
* JMdict (English-only file), EDRDG, http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz
* word frequencies for Chinese (CEDICT has none): jieba's dict.txt (MIT licence, (c) 2013 Sun Junyi),
  https://raw.githubusercontent.com/fxsjy/jieba/v0.42.1/jieba/dict.txt — only its counts are kept

The raw downloads go to a temporary directory, are read as a stream and deleted
afterwards; only the compact built files are kept (and committed). Nothing here
runs when the app runs: the app reads the built files and never goes online.

Built formats (gzip of UTF-8 text, tab-separated, one entry per line, ``#`` lines are comments):

zh  ``cedict_zh_en.tsv.gz``  simplified, traditional ("" if the same), numbered pinyin,
    gloss (senses joined "; "), flags ("w" weak: only a variant/surname/"see" pointer;
    "p" proper noun), frequency (jieba's count for the simplified headword, 0 if it has none)
ja  ``jmdict_ja_en.tsv.gz``  kanji forms, kana readings (both comma-separated, "!" after a
    common form, a reading limited to some kanji forms as "reading@k1/k2"), part-of-speech
    and usage tags (space-separated JMdict codes, plus "uk": usually written in kana),
    rank (1 most frequent .. 99 no frequency data), gloss (senses "; ", glosses ", ")
"""
from __future__ import annotations

import argparse
import gzip
import re
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sect_academy" / "dict"
CEDICT_URL = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"
# Word frequencies only (one number per CEDICT headword): jieba's dictionary, MIT licence, (c) 2013 Sun Junyi.
JIEBA_URL = "https://raw.githubusercontent.com/fxsjy/jieba/v0.42.1/jieba/dict.txt"


def fetch(url: str, dest: Path) -> Path:
    print(f"downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:   # noqa: S310 — fixed https/http URLs
        shutil.copyfileobj(r, f, 1 << 20)
    return dest


# ---------------------------------------------------------------------------
# CC-CEDICT
# ---------------------------------------------------------------------------
_CE_LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")
_WEAK_GLOSS = re.compile(r"^(?:\([^)]*\) )?(?:(?:old|archaic|unofficial|erhua|Japanese|Korean|ancient|obscure|also written)\s+)*"
                         r"variant of |^(?:see|see also|surname|used in)\b", re.I)


def build_zh(src: Path, out: Path, jieba: Path | None = None) -> dict:
    rows = []
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            m = _CE_LINE.match(line)
            if not m:
                continue
            trad, simp, pin, body = m.groups()
            glosses = [g.strip() for g in body.split("/") if g.strip()]
            glosses = [g for g in glosses if not g.startswith("CL:")]
            strong = [g for g in glosses if not _WEAK_GLOSS.match(g)]
            weak = not strong
            keep = (strong or glosses)[:3]
            if not keep:
                continue
            gloss = "; ".join(g if len(g) <= 90 else g[:87].rstrip() + "…" for g in keep).replace("\t", " ")
            proper = pin[:1].isupper() and not weak
            rows.append([simp, "" if trad == simp else trad, pin.replace("u:", "v"), gloss, ("w" if weak else "") + ("p" if proper else "")])
    freq: dict[str, int] = {}
    if jieba is not None:
        with open(jieba, encoding="utf-8") as f:
            for line in f:
                p = line.split()
                if len(p) >= 2 and p[1].isdigit():
                    freq[p[0]] = int(p[1])
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(f"# CC-CEDICT (MDBG), CC BY-SA 4.0, fetched {date.today().isoformat()}; frequencies from jieba (MIT); "
                "built by scripts/build_dict_zh_ja.py\n")
        for r in rows:
            f.write("\t".join([*r, str(freq.get(r[0], 0))]) + "\n")
    return {"entries": len(rows), "bytes": out.stat().st_size}


# ---------------------------------------------------------------------------
# JMdict
# ---------------------------------------------------------------------------
_ENT = re.compile(r"&([A-Za-z][\w.-]*);")
_XML_ENT = {"amp", "lt", "gt", "quot", "apos"}
POS_KEEP = {"v1", "v1-s", "vk", "vs", "vs-i", "vs-s", "vs-c", "vz", "adj-i", "adj-ix", "adj-na", "adj-no", "adj-pn", "adj-t",
            "adj-f", "n", "n-suf", "n-pref", "n-adv", "n-t", "pn", "prt", "exp", "adv", "adv-to", "conj", "int", "aux", "aux-v",
            "aux-adj", "cop", "suf", "pref", "ctr", "num", "v5aru", "v5r-i", "v5k-s", "v5u-s", "unc"}
_COMMON = {"news1", "ichi1", "spec1", "spec2", "gai1"}


def _rank(pris: set[str]) -> int:
    nf = [int(p[2:]) for p in pris if p.startswith("nf") and p[2:].isdigit()]
    if nf:
        return min(nf) if pris & _COMMON else min(nf) + 24          # nf01..nf48 (500-word bands)
    if pris & {"ichi1", "spec1"}:
        return 12                                                     # basic words the newspaper bands miss (行く)
    if pris & _COMMON:
        return 30
    if pris:
        return 60                                                     # news2, ichi2, gai2 only
    return 99


def _jm_lines(src: Path):
    """The XML with the DTD left out and every &entity; turned into its code (so <pos>&v1;</pos> reads "v1")."""
    with gzip.open(src, "rt", encoding="utf-8") as f:
        in_dtd = False
        for line in f:
            if line.startswith("<!DOCTYPE"):
                in_dtd = True
            if in_dtd:
                if line.startswith("]>"):
                    in_dtd = False
                continue
            yield _ENT.sub(lambda m: m.group(0) if m.group(1) in _XML_ENT else m.group(1), line)


def build_ja(src: Path, out: Path) -> dict:
    parser = ET.XMLPullParser(events=("end",))
    kept = dropped = 0
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(f"# JMdict (EDRDG), CC BY-SA 4.0, fetched {date.today().isoformat()}; built by scripts/build_dict_zh_ja.py\n")
        for line in _jm_lines(src):
            parser.feed(line)
            for _, el in parser.read_events():
                if el.tag != "entry":
                    continue
                row = _jm_entry(el)
                el.clear()
                if row is None:
                    dropped += 1
                    continue
                f.write("\t".join(row) + "\n")
                kept += 1
    return {"entries": kept, "dropped": dropped, "bytes": out.stat().st_size}


def _jm_entry(el) -> list[str] | None:
    kanji, kana, pris_all = [], [], set()
    for k in el.findall("k_ele"):
        keb = k.findtext("keb") or ""
        if not keb:
            continue
        pr = {x.text for x in k.findall("ke_pri")}
        pris_all |= pr
        common = bool(pr & _COMMON) or any(p.startswith("nf") for p in pr)
        kanji.append(keb + ("!" if common else ""))
    for r in el.findall("r_ele"):
        reb = r.findtext("reb") or ""
        if not reb:
            continue
        pr = {x.text for x in r.findall("re_pri")}
        pris_all |= pr
        common = bool(pr & _COMMON) or any(p.startswith("nf") for p in pr)
        restr = [x.text for x in r.findall("re_restr") if x.text]
        if r.find("re_nokanji") is not None:
            restr = ["-"]
        kana.append(reb + ("!" if common else "") + ("@" + "/".join(restr) if restr else ""))
    if not kana:
        return None
    pos: list[str] = []
    misc: set[str] = set()
    senses, last_pos = [], []
    for s in el.findall("sense"):
        sp = [x.text for x in s.findall("pos") if x.text]
        last_pos = sp or last_pos
        for p in last_pos:
            if (p in POS_KEEP or p.startswith("v5")) and p not in pos:
                pos.append(p)
        sm = {x.text for x in s.findall("misc") if x.text}
        gl = [g.text.strip() for g in s.findall("gloss") if g.text and g.text.strip()]
        if not gl:
            continue
        if len(senses) < 3:
            senses.append((gl, sm))
    if not senses:
        return None
    rank = _rank(pris_all)
    first_misc = senses[0][1]
    if rank == 99 and all(sm & {"arch", "obs", "rare", "obsc"} for _, sm in senses):
        return None                                                    # rare and archaic with no frequency data
    if "uk" in first_misc:
        misc.add("uk")
    gloss = "; ".join(", ".join(g if len(g) <= 70 else g[:67].rstrip() + "…" for g in gl[:3]) for gl, _ in senses)
    tags = " ".join(pos + sorted(misc))
    return [",".join(kanji), ",".join(kana), tags, str(rank), gloss.replace("\t", " ")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["zh", "ja"])
    ap.add_argument("--cedict", type=Path, help="a CC-CEDICT .txt.gz already downloaded")
    ap.add_argument("--jmdict", type=Path, help="a JMdict_e.gz already downloaded")
    ap.add_argument("--jieba", type=Path, help="jieba's dict.txt already downloaded")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="dict_zh_ja_"))
    try:
        if a.only in (None, "zh"):
            src = a.cedict or fetch(CEDICT_URL, tmp / "cedict.txt.gz")
            jb = a.jieba or fetch(JIEBA_URL, tmp / "jieba_dict.txt")
            (OUT / "zh").mkdir(parents=True, exist_ok=True)
            print("zh", build_zh(src, OUT / "zh" / "cedict_zh_en.tsv.gz", jb))
            for f in (src, jb):
                if f.parent == tmp:
                    f.unlink()
        if a.only in (None, "ja"):
            src = a.jmdict or fetch(JMDICT_URL, tmp / "JMdict_e.gz")
            (OUT / "ja").mkdir(parents=True, exist_ok=True)
            print("ja", build_ja(src, OUT / "ja" / "jmdict_ja_en.tsv.gz"))
            if src.parent == tmp:
                src.unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
