"""How well the Mandarin and Japanese dictionaries read the courses' own sentences.

    python tests/lexicon_quality.py            # both languages, with sample misses
    python tests/lexicon_quality.py zh 40      # one language, 40 samples

Text: every Chinese / Japanese sentence in sect_academy/packs/*.yaml (l2, ex, alt
and dialogue lines). Two measures:

* **hit rate**: the share of word tokens (punctuation and numbers left out) that
  get a real dictionary answer (not only a weak "variant of"/surname entry);
* **segmentation agreement**: word-boundary precision/recall against the
  course's own word division — Japanese beginner text is written with spaces
  between words (わたし は がくせい です), Chinese text against the word grouping of
  its pinyin (Wǒ yǒu yí ge Zhōngguó péngyou: 我|有|一|个|中国|朋友).

``tests/test_lexicon_zh_ja.py`` runs a fixed subset of this quickly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sect_academy.lexicon import cjk, ja, zh  # noqa: E402

PACKS = {"zh": ["mandarin_a1.yaml"], "ja": ["japanese_a1.yaml"]}


def _texts(node, out):
    if isinstance(node, dict):
        if node.get("type") == "glyph":
            return
        for k in ("l2", "ex", "text"):
            v = node.get(k)
            if isinstance(v, str):
                out.append((v, node.get("rom") if k == "l2" else node.get("ex_rom") if k == "ex" else None))
        for a in node.get("alt") or []:
            if isinstance(a, str):
                out.append((a, None))
        for v in node.values():
            if isinstance(v, (list, dict)):
                _texts(v, out)
    elif isinstance(node, list):
        for v in node:
            _texts(v, out)


def sentences(lang: str) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    for name in PACKS[lang]:
        _texts(yaml.safe_load((ROOT / "sect_academy" / "packs" / name).read_text(encoding="utf-8")), out)
    keep, seen = [], set()
    for t, rom in out:
        if any(cjk.is_han(ch) or cjk.is_hira(ch) or cjk.is_kata(ch) for ch in t) and t not in seen:
            seen.add(t)
            keep.append((t, rom))
    return keep


def _syllables(word: str) -> int:
    return sum(len(re.findall(r"[aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+", part, re.I)) for part in word.split("'"))


def gold_zh(text: str, rom: str | None) -> list[int] | None:
    """Word boundaries (cut offsets in the Han-only string) from the pinyin's word grouping, or None."""
    if not rom:
        return None
    han = "".join(ch for ch in text if cjk.is_han(ch))
    words = [w for w in re.split(r"[\s,.!?;:—\-–\"“”()]+", rom) if w]
    sizes = [_syllables(w) for w in words]
    if sum(sizes) != len(han) or any(s == 0 for s in sizes):
        return None
    cuts, at = [], 0
    for s in sizes:
        at += s
        cuts.append(at)
    return cuts


def gold_ja(text: str) -> list[int] | None:
    """Word boundaries from a spaced sentence (わたし は がくせい です), in the unspaced string; None if unspaced."""
    if " " not in text.strip():
        return None
    cuts, at = [], 0
    for w in text.split():
        w = "".join(ch for ch in w if cjk.kind(ch))
        if w:
            at += len(w)
            cuts.append(at)
    return cuts


def _cuts(tokens, keep) -> list[int]:
    out, at = [], 0
    for t in tokens:
        n = sum(1 for ch in t["t"] if keep(ch))
        if n:
            at += n
            out.append(at)
    return out


def measure(lang: str):
    mod = zh if lang == "zh" else ja
    sents = sentences(lang)
    tok = hit = 0
    misses: list[str] = []
    bp = br = bm = 0
    bad_splits: list[str] = []
    for text, rom in sents:
        src = text.replace(" ", "") if lang == "ja" else text
        toks = mod.segment(src)
        for t in toks:
            if not t["k"] or not any(cjk.kind(ch) in ("h", "H", "K", "L") for ch in t["t"]):
                continue
            tok += 1
            if lang == "zh":
                r = zh.lookup(t["k"])
                good = r["found"] and not r["weak"]
            else:
                nxt = src[src.find(t["t"]) + len(t["t"]):][:6] if t["t"] in src else ""
                good = ja.lookup(t["k"], around=("", nxt))["found"]
            if good:
                hit += 1
            elif len(misses) < 400:
                misses.append(f"{t['t']}  in  {src}")
        if lang == "zh":
            gold, keep = gold_zh(text, rom), cjk.is_han
        else:
            gold, keep = gold_ja(text), (lambda ch: bool(cjk.kind(ch)))
        if gold:
            mine = _cuts(toks, keep)
            g, m = set(gold[:-1]), set(mine[:-1])
            bm += len(g & m)
            bp += len(m)
            br += len(g)
            if g != m and len(bad_splits) < 400:
                bad_splits.append(f"{' | '.join(t['t'] for t in toks if t['k'])}    (course: {text if lang == 'ja' else rom})")
    return {"sentences": len(sents), "tokens": tok, "hit": hit / max(1, tok), "misses": misses,
            "precision": bm / max(1, bp), "recall": bm / max(1, br), "bad_splits": bad_splits, "gold_boundaries": br}


def main() -> None:
    langs = [a for a in sys.argv[1:] if a in ("zh", "ja")] or ["zh", "ja"]
    n = next((int(a) for a in sys.argv[1:] if a.isdigit()), 20)
    for lang in langs:
        r = measure(lang)
        print(f"== {lang}: {r['sentences']} sentences, {r['tokens']} word tokens, hit rate {r['hit']:.1%}; "
              f"boundaries vs the course: precision {r['precision']:.1%}, recall {r['recall']:.1%} ({r['gold_boundaries']} boundaries)")
        print(f"-- misses ({len(r['misses'])}):")
        for m in r["misses"][:n]:
            print("  ", m)
        print(f"-- splits that differ from the course ({len(r['bad_splits'])}):")
        for m in r["bad_splits"][:n]:
            print("  ", m)


if __name__ == "__main__":
    main()
