"""Stroke order for Hangul: the jamo drawn by hand here, syllable blocks composed from them.

Each jamo is a list of strokes in its own unit box (x right, y down), each stroke a
polyline in the order and direction it is written: horizontals left to right,
verticals top to bottom, ㅇ anticlockwise from the top. A syllable block puts its
initial, vowel and final jamo into the regions of the standard layouts:

* a vertical vowel (ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅣ) stands to the right of the initial,
* a horizontal vowel (ㅗ ㅛ ㅜ ㅠ ㅡ) lies under it,
* a compound vowel (ㅘ ㅙ ㅚ ㅝ ㅞ ㅟ ㅢ) wraps it: its horizontal part under, its vertical part right,
* a final consonant (batchim) takes the bottom band; doubled and cluster jamo split their region in two.

The strokes are written as: initial, vowel, final (each in its own stroke order).
This data is ours (no outside source), authored for this app.
"""
from __future__ import annotations

import math

Box = tuple[float, float, float, float]
Stroke = list[tuple[float, float]]


def _ring(cx: float, cy: float, r: float, n: int = 32) -> Stroke:
    # from the top, anticlockwise on screen (left first), back to the top
    return [(cx + r * math.cos(-math.pi / 2 - 2 * math.pi * k / n), cy + r * math.sin(-math.pi / 2 - 2 * math.pi * k / n))
            for k in range(n + 1)]


# --- consonants, in a unit box ----------------------------------------------
_G = [[(0.1, 0.15), (0.85, 0.15), (0.85, 0.9)]]
_N = [[(0.15, 0.1), (0.15, 0.85), (0.9, 0.85)]]
_D = [[(0.15, 0.15), (0.85, 0.15)], [(0.15, 0.15), (0.15, 0.85), (0.9, 0.85)]]
_R = [[(0.12, 0.12), (0.85, 0.12), (0.85, 0.48)], [(0.15, 0.48), (0.85, 0.48)], [(0.15, 0.48), (0.15, 0.88), (0.9, 0.88)]]
_M = [[(0.15, 0.15), (0.15, 0.85)], [(0.15, 0.15), (0.85, 0.15), (0.85, 0.85)], [(0.15, 0.85), (0.85, 0.85)]]
_B = [[(0.15, 0.1), (0.15, 0.88)], [(0.85, 0.1), (0.85, 0.88)], [(0.15, 0.48), (0.85, 0.48)], [(0.15, 0.88), (0.85, 0.88)]]
_S = [[(0.5, 0.12), (0.35, 0.55), (0.1, 0.88)], [(0.48, 0.45), (0.7, 0.7), (0.9, 0.88)]]
_NG = [_ring(0.5, 0.5, 0.36)]
_J = [[(0.12, 0.15), (0.85, 0.15), (0.5, 0.55), (0.1, 0.88)], [(0.5, 0.52), (0.72, 0.72), (0.9, 0.88)]]
_CH = [[(0.5, 0.0), (0.5, 0.14)], [(0.12, 0.25), (0.85, 0.25), (0.5, 0.6), (0.1, 0.9)], [(0.5, 0.58), (0.72, 0.76), (0.9, 0.9)]]
_K = [[(0.1, 0.15), (0.85, 0.15), (0.85, 0.9)], [(0.15, 0.5), (0.85, 0.5)]]
_T = [[(0.15, 0.12), (0.85, 0.12)], [(0.15, 0.48), (0.85, 0.48)], [(0.15, 0.12), (0.15, 0.88), (0.9, 0.88)]]
_P = [[(0.1, 0.15), (0.9, 0.15)], [(0.32, 0.15), (0.35, 0.85)], [(0.68, 0.15), (0.65, 0.85)], [(0.08, 0.85), (0.92, 0.85)]]
_H = [[(0.5, 0.0), (0.5, 0.14)], [(0.15, 0.25), (0.85, 0.25)], _ring(0.5, 0.63, 0.26)]

SINGLE = {"ㄱ": _G, "ㄴ": _N, "ㄷ": _D, "ㄹ": _R, "ㅁ": _M, "ㅂ": _B, "ㅅ": _S, "ㅇ": _NG, "ㅈ": _J, "ㅊ": _CH,
          "ㅋ": _K, "ㅌ": _T, "ㅍ": _P, "ㅎ": _H}
# doubled consonants and final clusters: (left jamo, right jamo), side by side
PAIRS = {"ㄲ": "ㄱㄱ", "ㄸ": "ㄷㄷ", "ㅃ": "ㅂㅂ", "ㅆ": "ㅅㅅ", "ㅉ": "ㅈㅈ", "ㄳ": "ㄱㅅ", "ㄵ": "ㄴㅈ", "ㄶ": "ㄴㅎ",
         "ㄺ": "ㄹㄱ", "ㄻ": "ㄹㅁ", "ㄼ": "ㄹㅂ", "ㄽ": "ㄹㅅ", "ㄾ": "ㄹㅌ", "ㄿ": "ㄹㅍ", "ㅀ": "ㄹㅎ", "ㅄ": "ㅂㅅ"}

# --- vowels, each in the unit box of its own region ---------------------------
_VL = {   # vertical vowels: a tall region to the right
    "ㅏ": [[(0.35, 0.0), (0.35, 1.0)], [(0.35, 0.5), (0.8, 0.5)]],
    "ㅑ": [[(0.35, 0.0), (0.35, 1.0)], [(0.35, 0.36), (0.8, 0.36)], [(0.35, 0.64), (0.8, 0.64)]],
    "ㅓ": [[(0.1, 0.5), (0.6, 0.5)], [(0.6, 0.0), (0.6, 1.0)]],
    "ㅕ": [[(0.1, 0.36), (0.6, 0.36)], [(0.1, 0.64), (0.6, 0.64)], [(0.6, 0.0), (0.6, 1.0)]],
    "ㅣ": [[(0.5, 0.0), (0.5, 1.0)]],
    "ㅐ": [[(0.25, 0.0), (0.25, 1.0)], [(0.25, 0.5), (0.55, 0.5)], [(0.78, 0.0), (0.78, 1.0)]],
    "ㅒ": [[(0.25, 0.0), (0.25, 1.0)], [(0.25, 0.36), (0.55, 0.36)], [(0.25, 0.64), (0.55, 0.64)], [(0.78, 0.0), (0.78, 1.0)]],
    "ㅔ": [[(0.05, 0.5), (0.4, 0.5)], [(0.4, 0.0), (0.4, 1.0)], [(0.8, 0.0), (0.8, 1.0)]],
    "ㅖ": [[(0.05, 0.36), (0.4, 0.36)], [(0.05, 0.64), (0.4, 0.64)], [(0.4, 0.0), (0.4, 1.0)], [(0.8, 0.0), (0.8, 1.0)]],
}
_VH = {   # horizontal vowels: a wide region underneath
    "ㅗ": [[(0.5, 0.1), (0.5, 0.55)], [(0.0, 0.6), (1.0, 0.6)]],
    "ㅛ": [[(0.35, 0.1), (0.35, 0.55)], [(0.65, 0.1), (0.65, 0.55)], [(0.0, 0.6), (1.0, 0.6)]],
    "ㅜ": [[(0.0, 0.35), (1.0, 0.35)], [(0.5, 0.4), (0.5, 0.95)]],
    "ㅠ": [[(0.0, 0.35), (1.0, 0.35)], [(0.35, 0.4), (0.35, 0.95)], [(0.65, 0.4), (0.65, 0.95)]],
    "ㅡ": [[(0.0, 0.5), (1.0, 0.5)]],
}
_VM = {"ㅘ": "ㅗㅏ", "ㅙ": "ㅗㅐ", "ㅚ": "ㅗㅣ", "ㅝ": "ㅜㅓ", "ㅞ": "ㅜㅔ", "ㅟ": "ㅜㅣ", "ㅢ": "ㅡㅣ"}

LEADS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
TAILS = ["", *"ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"]

# regions (x0, y0, x1, y1) in the 1-unit syllable box: I initial, V vertical part, H horizontal part, F final
_LAYOUT = {
    ("v", False): {"I": (0.08, 0.12, 0.56, 0.88), "V": (0.56, 0.06, 0.94, 0.94)},
    ("v", True): {"I": (0.08, 0.06, 0.56, 0.52), "V": (0.56, 0.03, 0.94, 0.6), "F": (0.12, 0.64, 0.88, 0.96)},
    ("h", False): {"I": (0.22, 0.06, 0.78, 0.48), "H": (0.06, 0.42, 0.94, 0.94)},
    ("h", True): {"I": (0.24, 0.03, 0.76, 0.32), "H": (0.06, 0.24, 0.94, 0.6), "F": (0.12, 0.64, 0.88, 0.96)},
    ("m", False): {"I": (0.08, 0.06, 0.52, 0.44), "H": (0.04, 0.38, 0.66, 0.92), "V": (0.62, 0.04, 0.95, 0.96)},
    ("m", True): {"I": (0.08, 0.04, 0.5, 0.3), "H": (0.04, 0.24, 0.64, 0.58), "V": (0.62, 0.02, 0.95, 0.6),
                  "F": (0.12, 0.64, 0.88, 0.96)},
}
# a jamo written on its own (ㄱ, ㅏ, ㅘ as glyph items)
_ALONE = {"c": (0.1, 0.1, 0.9, 0.9), "V": (0.22, 0.08, 0.78, 0.92), "H": (0.08, 0.15, 0.92, 0.85),
          "mH": (0.06, 0.3, 0.66, 0.85), "mV": (0.6, 0.06, 0.95, 0.94)}


def _place(strokes: list[Stroke], box: Box) -> list[Stroke]:
    x0, y0, x1, y1 = box
    return [[(x0 + x * (x1 - x0), y0 + y * (y1 - y0)) for x, y in s] for s in strokes]


def _consonant(j: str, box: Box) -> list[Stroke]:
    if j in SINGLE:
        return _place(SINGLE[j], box)
    a, b = PAIRS[j]
    x0, y0, x1, y1 = box
    mid = (x0 + x1) / 2
    return _consonant(a, (x0, y0, mid, y1)) + _consonant(b, (mid, y0, x1, y1))


def _vowel_kind(v: str) -> str:
    return "v" if v in _VL else "h" if v in _VH else "m"


def _vowel(v: str, regions: dict[str, Box]) -> list[Stroke]:
    if v in _VL:
        return _place(_VL[v], regions["V"])
    if v in _VH:
        return _place(_VH[v], regions["H"])
    h, vv = _VM[v]
    return _place(_VH[h], regions["H"]) + _place(_VL[vv], regions["V"])


def syllable(ch: str) -> list[Stroke] | None:
    """The strokes of one Hangul syllable or jamo, in order, in a unit box; None if it is not Hangul."""
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        n = code - 0xAC00
        lead, vowel, tail = LEADS[n // 588], VOWELS[(n % 588) // 28], TAILS[n % 28]
        regions = _LAYOUT[(_vowel_kind(vowel), bool(tail))]
        out = _consonant(lead, regions["I"]) + _vowel(vowel, regions)
        if tail:
            out += _consonant(tail, regions["F"])
        return out
    if ch in SINGLE or ch in PAIRS:
        return _consonant(ch, _ALONE["c"])
    if ch in _VL:
        return _place(_VL[ch], _ALONE["V"])
    if ch in _VH:
        return _place(_VH[ch], _ALONE["H"])
    if ch in _VM:
        return _vowel(ch, {"H": _ALONE["mH"], "V": _ALONE["mV"]})
    return None
