"""How often the reader's dictionary finds the words of real text: every sentence of a language in the courses
(``l2``, ``ex``, dialogue lines, filled-in clozes), tokenised the way the reader tokenises a page.

    python scripts/lexicon_hit_rate.py fr ko     # share of word tokens with a non-weak hit, and the commonest misses
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sect_academy import lexicon, packs  # noqa: E402


def sentences(lang: str) -> list[str]:
    name = lexicon.LANGS[lang].split()[0]          # "French", "Korean", "Mandarin", ...
    out: list[str] = []
    for p in packs.load_all().values():
        if p.get("kind") != "language" or p.get("personal") or not str(p.get("language", "")).startswith(name):
            continue
        for u in p["units"]:
            for it in u["items"]:
                if it.get("type") == "glyph":
                    continue
                for k in ("l2", "ex"):
                    if isinstance(it.get(k), str):
                        out.append(it[k])
                if it.get("type") == "cloze" and isinstance(it.get("text"), str) and isinstance(it.get("answer"), str):
                    out.append(it["text"].replace("___", it["answer"]))
                for line in it.get("lines") or []:
                    if isinstance(line, dict) and isinstance(line.get("l2"), str):
                        out.append(line["l2"])
    return out


def hit_rate(lang: str, texts: list[str]) -> tuple[float, int, collections.Counter]:
    """(share of word tokens found with a non-weak sense, word tokens, misses by count)."""
    mod = lexicon.get(lang)
    cache: dict[str, bool] = {}
    n = ok = 0
    misses: collections.Counter = collections.Counter()
    for t in texts:
        for tok in mod.segment(t):
            k = tok["k"]
            if not k:
                continue
            if k not in cache:
                r = mod.lookup(k, {})
                cache[k] = bool(r["found"] and not r.get("weak"))
            n += 1
            if cache[k]:
                ok += 1
            else:
                misses[k] += 1
    return (ok / n if n else 1.0), n, misses


def main(argv: list[str]) -> None:
    for lang in argv or ["fr", "ko"]:
        texts = sentences(lang)
        rate, n, misses = hit_rate(lang, texts)
        print(f"{lang}: {len(texts)} sentences, {n} word tokens, hit rate {rate:.1%}, {len(misses)} distinct misses")
        print("   ", ", ".join(f"{w} ({c})" for w, c in misses.most_common(40)))


if __name__ == "__main__":
    main(sys.argv[1:])
