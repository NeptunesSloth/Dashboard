"""Handwriting: stroke data for the script courses, and the stroke matcher that grades it.

Data (all in a 1000 x 1000 box, origin top left, y down; see each folder's README):

* Japanese kana and kanji: ``strokes/ja/kanjivg.json`` (KanjiVG, CC BY-SA 3.0)
* Chinese hanzi: ``strokes/zh/makemeahanzi.json`` (Make Me a Hanzi, Arphic Public License)
* Korean: composed from jamo by ``hangul.py`` (ours)

The learner draws on a square canvas; the page checks each stroke as it lands (the same
matcher, ported to ``static/handwriting.js``) to give hints, and at the end sends every
stroke it drew, in order, failed ones included. This module replays them and decides:
nothing the page says about its own strokes is believed.

A drawn stroke matches the expected one when, in the unit box: its start and end are
each within ``END_TOL`` of the expected start and end; after both are resampled to
``SAMPLES`` points by arc length, the mean distance between paired points is within
``MEAN_TOL`` (this is the shape check, and it also catches a reversed loop); its length
is between ``LEN_LO`` and ``LEN_HI`` times the expected length; and, for a stroke with a
clear direction, it points the same way. A stroke that fits a later stroke clearly better
than the one due is a stroke-order mistake.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from . import hangul

DIR = Path(__file__).parent / "strokes"
FILES = {"ja": DIR / "ja" / "kanjivg.json", "zh": DIR / "zh" / "makemeahanzi.json"}
CREDIT = {
    "ja": "Stroke order: KanjiVG, by Ulrich Apel and contributors, CC BY-SA 3.0 (kanjivg.tagaini.net)",
    "zh": "Stroke order: Make Me a Hanzi (Shaunak Kishore), from Arphic fonts, Arphic Public License",
    "ko": "Stroke order: Sect Academy's own jamo strokes",
}

SAMPLES = 16
END_TOL = 0.17          # start / end point, as a share of the box
MEAN_TOL = 0.12         # mean distance of paired resampled points
LEN_LO, LEN_HI = 0.35, 2.4
MIN_LEN = 0.06          # a dot or a tick is judged as if it were this long
DIR_COS = 0.5           # direction agreement for a stroke longer than DIR_LONG
DIR_LONG, DIR_SHORT = 0.15, 0.05
BETTER, MARGIN = 0.6, 0.04   # a later stroke "fits better": mean distance below this share, and this much lower
ORDER_FLOOR = 0.05      # ... unless the stroke sits this close to the one that is due

MAX_CHARS = 6
MAX_ATTEMPTS = 120      # strokes per character, failed ones included
MAX_POINTS = 256        # points kept from one drawn stroke
COORD_LO, COORD_HI = -0.5, 1.5
WRITE_MIN_S = 4.0       # FSRS stability (days) before a glyph is asked written


def slips_allowed(n_strokes: int) -> int:
    """Mistakes a character may have and still count as written: 1, plus 1 per 4 strokes."""
    return 1 + n_strokes // 4


@lru_cache(maxsize=None)
def _table(lang: str) -> dict:
    p = FILES.get(lang)
    if not p or not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("chars", {})


def lang_of(ch: str) -> str:
    c = ord(ch)
    if 0xAC00 <= c <= 0xD7A3 or 0x3131 <= c <= 0x318E:
        return "ko"
    if 0x3040 <= c <= 0x30FF:
        return "ja"
    return ""


def _pairs(flat: list) -> list[tuple[float, float]]:
    return [(flat[i] / 1000.0, flat[i + 1] / 1000.0) for i in range(0, len(flat) - 1, 2)]


@lru_cache(maxsize=4096)
def char_strokes(ch: str, lang: str) -> tuple | None:
    """The expected strokes of one character (unit box), or None if there is no data for it."""
    if lang == "ko" or lang_of(ch) == "ko":
        s = hangul.syllable(ch)
        return tuple(tuple(st) for st in s) if s else None
    want = lang if lang in FILES else ("ja" if lang_of(ch) == "ja" else "zh")
    e = _table(want).get(ch)
    if not e and lang_of(ch) == "ja":
        e = _table("ja").get(ch)
    if not e:
        return None
    return tuple(tuple(_pairs(m)) for m in e["m"])


def _lang(lang: str) -> str:
    return str(lang or "").split("-")[0]


def can_write(text: str, lang: str) -> bool:
    text = str(text or "")
    return 0 < len(text) <= MAX_CHARS and all(char_strokes(c, _lang(lang)) for c in text)


def public(text: str, lang: str) -> list[dict]:
    """What the page needs to draw and check: each character's strokes (and outlines, for hanzi)."""
    lg = _lang(lang)
    out = []
    for ch in str(text):
        strokes = char_strokes(ch, lg)
        if not strokes:
            return []
        e = {"m": [[int(round(v * 1000)) for p in s for v in p] for s in strokes], "slips": slips_allowed(len(strokes))}
        src = "ko" if lang_of(ch) == "ko" else ("ja" if lg == "ja" or lang_of(ch) == "ja" else "zh")
        if src == "zh" and _table("zh").get(ch, {}).get("o"):
            e["o"] = list(_table("zh")[ch]["o"])
        out.append(e)
    return out


def credit(lang: str) -> str:
    return CREDIT.get(_lang(lang), "")


# ---------------------------------------------------------------------------
# the matcher
# ---------------------------------------------------------------------------
def _length(pts) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def resample(pts, n: int = SAMPLES) -> list[tuple[float, float]]:
    """n points evenly spaced along the polyline (by arc length)."""
    pts = list(pts)
    if not pts:
        return []
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    total = cum[-1]
    if total <= 1e-9:
        return [pts[0]] * n
    out, j = [], 0
    for k in range(n):
        t = total * k / (n - 1)
        while j < len(pts) - 2 and cum[j + 1] < t:
            j += 1
        seg = cum[j + 1] - cum[j]
        u = 0.0 if seg <= 1e-12 else min(1.0, max(0.0, (t - cum[j]) / seg))
        a, b = pts[j], pts[j + 1]
        out.append((a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])))
    return out


def compare(drawn, expected) -> dict:
    """How a drawn stroke sits against an expected one: {ok, mean, why}."""
    d, e = resample(drawn), resample(expected)
    if not d or not e:
        return {"ok": False, "mean": 9.0, "why": "empty"}
    mean = sum(math.dist(p, q) for p, q in zip(d, e)) / len(e)
    le, ld = max(_length(expected), MIN_LEN), _length(drawn)
    why = ""
    if math.dist(d[0], e[0]) > END_TOL:
        why = "start"
    elif math.dist(d[-1], e[-1]) > END_TOL:
        why = "end"
    elif mean > MEAN_TOL:
        why = "shape"
    elif not (LEN_LO <= ld / le <= LEN_HI):
        why = "length"
    else:
        ce = (e[-1][0] - e[0][0], e[-1][1] - e[0][1])
        cd = (d[-1][0] - d[0][0], d[-1][1] - d[0][1])
        ne, nd = math.hypot(*ce), math.hypot(*cd)
        if ne > DIR_SHORT and nd > 1e-6:
            cos = (ce[0] * cd[0] + ce[1] * cd[1]) / (ne * nd)
            if cos < (DIR_COS if ne > DIR_LONG else 0.0):
                why = "direction"
        elif ne > DIR_SHORT:
            why = "direction"
    return {"ok": not why, "mean": mean, "why": why}


def match_stroke(drawn, strokes, at: int) -> dict:
    """Judge one drawn stroke when stroke ``at`` is due: {ok, why}; why "order" when it is a later stroke."""
    here = compare(drawn, strokes[at])
    later = [compare(drawn, strokes[j]) for j in range(at + 1, len(strokes))]
    best_later = min((c["mean"] for c in later if c["ok"]), default=None)
    if here["ok"]:
        if (best_later is not None and here["mean"] > ORDER_FLOOR and best_later < BETTER * here["mean"]
                and here["mean"] - best_later > MARGIN):
            return {"ok": False, "why": "order"}
        return {"ok": True, "why": ""}
    if best_later is not None:
        return {"ok": False, "why": "order"}
    return {"ok": False, "why": here["why"]}


def clean_stroke(raw) -> list[tuple[float, float]] | None:
    """A drawn stroke as sent ([x0, y0, x1, y1, ...] in the unit box) -> points, or None if unusable."""
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    if len(raw) > 2 * MAX_POINTS:
        step = math.ceil(len(raw) / (2 * MAX_POINTS))
        raw = [v for k in range(0, len(raw) - 1, 2 * step) for v in raw[k:k + 2]] + raw[-2:]
    pts = []
    for i in range(0, len(raw) - 1, 2):
        x, y = raw[i], raw[i + 1]
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        pts.append((min(max(float(x), COORD_LO), COORD_HI), min(max(float(y), COORD_LO), COORD_HI)))
    return pts or None


def grade_char(strokes, attempts) -> dict:
    """Replay the strokes drawn for one character: {done, mistakes, strokes, slips}."""
    at, mistakes, why = 0, 0, []
    for raw in (attempts if isinstance(attempts, list) else [])[:MAX_ATTEMPTS]:
        if at >= len(strokes):
            break                                   # strokes after the last one are ignored (the page stops there)
        pts = clean_stroke(raw)
        res = match_stroke(pts, strokes, at) if pts else {"ok": False, "why": "empty"}
        if res["ok"]:
            at += 1
        else:
            mistakes += 1
            why.append(res["why"])
    return {"done": at == len(strokes), "mistakes": mistakes, "strokes": len(strokes),
            "slips": slips_allowed(len(strokes)), "matched": at, "why": why[:20]}


def check(it: dict, given, lang: str) -> dict:
    """Grade a written glyph: {correct, flag, expected, chars}."""
    text = str(it.get("l2", ""))
    expected = text
    if not isinstance(given, dict):
        return {"correct": False, "flag": None, "expected": expected, "chars": []}
    chars = given.get("chars")
    chars = chars[:MAX_CHARS] if isinstance(chars, list) else []
    lg = _lang(lang)
    results = []
    for k, ch in enumerate(text[:MAX_CHARS]):
        strokes = char_strokes(ch, lg)
        if not strokes:
            return {"correct": False, "flag": None, "expected": expected, "chars": [], "error": "no stroke data"}
        results.append(grade_char(strokes, chars[k] if k < len(chars) else []))
    ok = bool(results) and all(r["done"] and r["mistakes"] <= r["slips"] for r in results)
    assisted = given.get("assisted") is True
    flag = "slips" if ok and (assisted or any(r["mistakes"] for r in results)) else None
    return {"correct": ok, "flag": flag, "expected": expected, "chars": results}


def check_self(answer) -> dict:
    """"I wrote it on paper": the learner's own verdict, never better than Hard."""
    ok = answer == "right"
    return {"correct": ok, "flag": "self" if ok else None}
