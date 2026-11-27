"""Build the handwriting stroke data (``sect_academy/strokes/ja/`` and ``strokes/zh/``).

    python scripts/build_strokes.py                     # download both sources, build both files
    python scripts/build_strokes.py --kanjivg kanjivg-20260714-main.zip --mmah graphics.txt

Sources (see each folder's README for the licence statement):

* Japanese kana and kanji: KanjiVG (CC BY-SA 3.0, Ulrich Apel), the release zip
  https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714-main.zip
* Chinese hanzi: Make Me a Hanzi graphics.txt (Arphic Public License),
  https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt
* Korean needs no file: ``sect_academy/hangul.py`` composes each syllable from its jamo.

Only the characters the courses use are kept: every hiragana and katakana, and every
CJK ideograph that appears anywhere in the Japanese or Mandarin course files (so a new
glyph item made from a word already in the course is covered without a rebuild).

Built format (UTF-8 JSON): ``{"source", "licence", "notice", "chars": {char: entry}}``,
entry ``{"m": [stroke, ...], "o": [outline, ...]}``. Every coordinate is in a 1000 x 1000
box, origin top left, y down. ``m`` holds each stroke's centre line, in stroke order, as a
flat list ``[x0, y0, x1, y1, ...]`` of integers (KanjiVG: its stroke path sampled and
simplified; Make Me a Hanzi: its "medians"). ``o`` (Make Me a Hanzi only) holds each
stroke's filled outline as an SVG path of absolute M/L/Q/C/Z commands.

The raw downloads go to a temporary folder and are deleted afterwards.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sect_academy" / "strokes"
KVG_URL = "https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714-main.zip"
MMAH_URL = "https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt"

KANA = [chr(c) for c in range(0x3041, 0x3097)] + [chr(c) for c in range(0x30A1, 0x30FB)] + ["ー"]


def course_chars(prefix: str) -> set[str]:
    text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "sect_academy" / "packs").glob(f"{prefix}*.yaml"))
    return {c for c in text if 0x4E00 <= ord(c) <= 0x9FFF or 0x3400 <= ord(c) <= 0x4DBF}


# ---------------------------------------------------------------------------
# SVG path -> points (KanjiVG uses M, C, S, L, H, V, Z in both cases)
# ---------------------------------------------------------------------------
_TOK = re.compile(r"[MmCcSsLlHhVvZzQqTt]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def path_points(d: str, steps: int = 10) -> list[tuple[float, float]]:
    toks = _TOK.findall(d)
    pts: list[tuple[float, float]] = []
    i, cmd = 0, ""
    x = y = 0.0
    last_ctrl = None
    start = (0.0, 0.0)

    def nums(n):
        nonlocal i
        out = [float(t) for t in toks[i:i + n]]
        i += n
        return out

    def cubic(p0, p1, p2, p3):
        for k in range(1, steps + 1):
            t = k / steps
            a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
            pts.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                x, y = start
                pts.append(start)
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            dx, dy = nums(2)
            x, y = (x + dx, y + dy) if rel else (dx, dy)
            start = (x, y)
            pts.append((x, y))
            cmd = "l" if rel else "L"            # further pairs are line-tos
            last_ctrl = None
        elif c == "L":
            dx, dy = nums(2)
            x, y = (x + dx, y + dy) if rel else (dx, dy)
            pts.append((x, y))
            last_ctrl = None
        elif c == "H":
            (dx,) = nums(1)
            x = x + dx if rel else dx
            pts.append((x, y))
        elif c == "V":
            (dy,) = nums(1)
            y = y + dy if rel else dy
            pts.append((x, y))
        elif c == "C":
            a = nums(6)
            if rel:
                a = [a[0] + x, a[1] + y, a[2] + x, a[3] + y, a[4] + x, a[5] + y]
            cubic((x, y), (a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
            last_ctrl = (a[2], a[3])
            x, y = a[4], a[5]
        elif c == "S":
            a = nums(4)
            if rel:
                a = [a[0] + x, a[1] + y, a[2] + x, a[3] + y]
            c1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
            cubic((x, y), c1, (a[0], a[1]), (a[2], a[3]))
            last_ctrl = (a[0], a[1])
            x, y = a[2], a[3]
        else:
            raise ValueError(f"path command {cmd!r} not handled")
    return pts


def _rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1e-9
    best, idx = -1.0, 0
    for k in range(1, len(pts) - 1):
        px, py = pts[k]
        dist = abs((x1 - x0) * (y0 - py) - (x0 - px) * (y1 - y0)) / L if L > 1e-6 else math.hypot(px - x0, py - y0)
        if dist > best:
            best, idx = dist, k
    if best <= eps:
        return [pts[0], pts[-1]]
    return _rdp(pts[:idx + 1], eps)[:-1] + _rdp(pts[idx:], eps)


def flat(pts) -> list[int]:
    out: list[int] = []
    for x, y in pts:
        out += [int(round(x)), int(round(y))]
    return out


# ---------------------------------------------------------------------------
# KanjiVG
# ---------------------------------------------------------------------------
_KVG_STROKE = re.compile(r'<path id="kvg:[0-9a-f]+-s(\d+)"[^>]*?\sd="([^"]+)"')


def build_kanjivg(zpath: Path, chars: set[str]) -> dict:
    out = {}
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
        for ch in sorted(chars):
            name = f"kanji/{ord(ch):05x}.svg"
            if name not in names:
                continue
            svg = z.read(name).decode("utf-8")
            strokes = sorted(((int(n), d) for n, d in _KVG_STROKE.findall(svg)), key=lambda t: t[0])
            m = []
            for _, d in strokes:
                pts = [(x * 1000 / 109, y * 1000 / 109) for x, y in path_points(d)]
                m.append(flat(_rdp(pts, 2.0)))
            if m:
                out[ch] = {"m": m}
    return out


# ---------------------------------------------------------------------------
# Make Me a Hanzi (1024 box, y up, baseline at 900)
# ---------------------------------------------------------------------------
_K = 1000 / 1024


def _tx(x: float, y: float) -> tuple[int, int]:
    return int(round(x * _K)), int(round((900 - y) * _K))


def _outline(d: str) -> str:
    toks = re.findall(r"[MLQCZ]|-?\d+(?:\.\d+)?", d)
    out, nums = [], []
    for t in toks:
        if t.isalpha():
            out.append(t)
            continue
        nums.append(float(t))
        if len(nums) == 2:
            x, y = _tx(*nums)
            out.append(f"{x} {y}")
            nums = []
    return " ".join(out)


def build_mmah(gpath: Path, chars: set[str]) -> dict:
    out = {}
    with gpath.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            ch = rec["character"]
            if ch not in chars:
                continue
            out[ch] = {"m": [flat(_tx(x, y) for x, y in med) for med in rec["medians"]],
                       "o": [_outline(d) for d in rec["strokes"]]}
    return out


def _fetch(url: str, dest: Path) -> Path:
    print(f"downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kanjivg", type=Path)
    ap.add_argument("--mmah", type=Path)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="strokes-"))
    try:
        kvg = args.kanjivg or _fetch(KVG_URL, tmp / "kanjivg.zip")
        mmah = args.mmah or _fetch(MMAH_URL, tmp / "graphics.txt")
        today = date.today().isoformat()
        ja_chars = set(KANA) | course_chars("japanese")
        ja = build_kanjivg(kvg, ja_chars)
        zh_chars = course_chars("mandarin")
        zh = build_mmah(mmah, zh_chars)
        files = {
            "ja": ("kanjivg.json", {
                "source": "KanjiVG r20260714, https://kanjivg.tagaini.net (Ulrich Apel and contributors)",
                "licence": "CC BY-SA 3.0, https://creativecommons.org/licenses/by-sa/3.0/",
                "notice": f"Adapted from KanjiVG on {today} by scripts/build_strokes.py: only the kana and the kanji used "
                          "in the courses, each stroke path sampled to points in a 1000 box. Distributed under CC BY-SA 3.0.",
                "chars": ja}),
            "zh": ("makemeahanzi.json", {
                "source": "Make Me a Hanzi graphics.txt, https://github.com/skishore/makemeahanzi, derived from "
                          "Arphic PL KaitiM GB and Arphic PL UKai",
                "licence": "Arphic Public License (ARPHICPL.TXT, in this folder, unaltered)",
                "notice": f"MODIFIED FILE. Changed on {today} by scripts/build_strokes.py from Make Me a Hanzi's graphics.txt: "
                          "kept only the characters used in the Mandarin course, moved the coordinates from the 1024 box with "
                          "y up to a 1000 box with y down, rounded to integers, and stored as JSON. You may copy, modify and "
                          "redistribute it under the Arphic Public License; there is no warranty.",
                "chars": zh}),
        }
        for lang, (name, data) in files.items():
            d = OUT / lang
            d.mkdir(parents=True, exist_ok=True)
            p = d / name
            p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{p.relative_to(ROOT)}: {len(data['chars'])} characters, {p.stat().st_size:,} bytes", file=sys.stderr)
        missing = {"ja": sorted(ja_chars - set(ja)), "zh": sorted(zh_chars - set(zh))}
        print(f"not in the source: {missing}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
