"""Shared helpers for the unspaced scripts (Chinese, Japanese): character classes, word keys, the segmenter.

The segmenter is a small lattice search: every dictionary word that starts at a
position is an edge, each edge has a cost (about 1 per word, a little more for
a rare or doubtful word, more again for a character the dictionary does not
know), and the cheapest path through the text wins. Fewer, more common words
beat many small ones — the usual "maximum matching" result, with ties broken by
how common the words are instead of by reading direction.
"""
from __future__ import annotations

import re
import unicodedata

from . import MAX_WORD


def is_han(ch: str) -> bool:
    o = ord(ch)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2FFFF or 0xF900 <= o <= 0xFAFF or ch in "〇々〆ヶ"


def is_hira(ch: str) -> bool:
    return 0x3041 <= ord(ch) <= 0x309F


def is_kata(ch: str) -> bool:
    o = ord(ch)
    return 0x30A0 <= o <= 0x30FF and ch != "・" or 0x31F0 <= o <= 0x31FF


def kind(ch: str) -> str:
    """'h' Han, 'H' hiragana, 'K' katakana, 'L' Latin letter, 'D' digit, '' anything else (space, punctuation)."""
    if is_han(ch):
        return "h"
    if is_hira(ch):
        return "H"
    if is_kata(ch):
        return "K"
    if ch.isdigit():
        return "D"
    if ch.isalpha():
        return "L"
    return ""


def norm_word(w) -> str:
    """A tapped or typed word as a key: NFKC (full-width letters, half-width kana), no punctuation or spaces
    around or inside it, Latin lower-cased; "" if it is not a word."""
    if not isinstance(w, str):
        return ""
    w = unicodedata.normalize("NFKC", w[:200]).strip()
    w = re.sub(r"^[^\w〆々ー]+|[^\w〆々ー]+$", "", w)
    w = re.sub(r"\s+", "", w).lower()
    if not w or len(w) > MAX_WORD or not any(ch.isalpha() for ch in w) or re.search(r"[^\w々〆ー・'-]", w):
        return ""
    return w


def runs(text: str):
    """(start, end, word_run) pieces: runs of script/letters/digits, and the gaps between them."""
    i, n = 0, len(text)
    while i < n:
        j = i
        word = bool(kind(text[i]))
        while j < n and bool(kind(text[j])) == word:
            j += 1
        yield i, j, word
        i = j


def lattice(s: str, edges, unknown) -> list[tuple[int, int]]:
    """Cheapest cut of ``s``. ``edges(s, i)`` -> [(end, cost)] for dictionary words starting at i;
    ``unknown(s, i)`` -> (end, cost) for the fallback piece at i. Returns [(start, end)]."""
    n = len(s)
    INF = float("inf")
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for i in range(n):
        if best[i] == INF:
            continue
        for end, cost in [*edges(s, i), unknown(s, i)]:
            c = best[i] + cost
            if c < best[end] - 1e-9:
                best[end], back[end] = c, i
    out, j = [], n
    while j > 0:
        out.append((back[j], j))
        j = back[j]
    return out[::-1]


def fallback_piece(s: str, i: int) -> int:
    """Where an unknown piece starting at i ends: a whole run of digits, Latin letters or katakana; else one character."""
    k = kind(s[i])
    if k in ("D", "L", "K"):
        j = i + 1
        while j < len(s) and (kind(s[j]) == k or (k == "D" and s[j] in ".,") or (k == "K" and s[j] == "ー")):
            j += 1
        return j
    return i + 1


def segment(text: str, edges, unknown, key=norm_word) -> list[dict]:
    """Tokens ({t, k}) for the text: word runs cut with ``lattice``, everything else kept as it is (k None)."""
    out = []
    for a, b, word in runs(text):
        piece = text[a:b]
        if not word:
            out.append({"t": piece, "k": None})
            continue
        for i, j in lattice(piece, edges, unknown):
            t = piece[i:j]
            k = None if all(kind(ch) == "D" for ch in t) else (key(t) or None)
            out.append({"t": t, "k": k})
    return out


def around(word: str, pre: str, post: str, has) -> str:
    """The longest dictionary word in ``pre + word + post`` that contains the whole tapped word and is longer."""
    pre, post = (pre or "")[-6:], (post or "")[:6]
    s = pre + word + post
    a0, b0 = len(pre), len(pre) + len(word)
    best = ""
    for i in range(0, a0 + 1):
        for j in range(len(s), b0 - 1, -1):
            if j - i <= len(word) or j - i <= len(best) or j - i > MAX_WORD:
                continue
            if has(s[i:j]):
                best = s[i:j]
                break
    return best


class IdMap(dict):
    """key -> entry ids, stored compactly: a bare int for the (usual) single id, a tuple for several.
    ``get``/``[]`` always give a tuple, so callers never see the difference (about 35 MB saved on JMdict)."""

    def add(self, key, i: int) -> None:
        """Append id ``i`` to ``key`` while loading (no list is made for a key with one id)."""
        v = dict.get(self, key)
        if v is None:
            dict.__setitem__(self, key, i)
        elif type(v) is int:
            dict.__setitem__(self, key, [v, i])
        else:
            v.append(i)

    def freeze(self, sort_key=None) -> IdMap:
        """After loading: every list of several ids becomes a tuple (sorted by ``sort_key``, stable, if given)."""
        for k, v in dict.items(self):
            if type(v) is list:
                if sort_key is not None:
                    v.sort(key=sort_key)
                dict.__setitem__(self, k, tuple(v))
        return self

    def get(self, key, default=None):
        v = dict.get(self, key)
        if v is None:
            return default
        return (v,) if type(v) is int else v

    def __getitem__(self, key):
        v = dict.__getitem__(self, key)
        return (v,) if type(v) is int else v
