# Japanese stroke order (kana and kanji)

`kanjivg.json` is the stroke data the handwriting exercise (`glyph_write`) uses for
Japanese: every hiragana and katakana (U+3041–3096, U+30A1–30FA, and ー), plus every
kanji that appears anywhere in the Japanese course files — 447 characters, 2,942
strokes, 163 KB. For each character it holds the strokes in order, each as the
centre line of the stroke (a flat list of points `[x0, y0, x1, y1, …]` in a 1000 ×
1000 box, origin top left), sampled from KanjiVG's SVG stroke path and simplified
(Ramer–Douglas–Peucker, 0.2 % of the box).

**Source:** KanjiVG, release r20260714 (`kanjivg-20260714-main.zip`),
https://github.com/KanjiVG/kanjivg/releases — https://kanjivg.tagaini.net.
Fetched 27 November 2026.

**Licence:** Creative Commons Attribution-ShareAlike 3.0 Unported
(CC BY-SA 3.0), https://creativecommons.org/licenses/by-sa/3.0/. Copyright (C)
2009–2026 Ulrich Apel and the KanjiVG contributors. `kanjivg.json` is an
adaptation of KanjiVG and is distributed under CC BY-SA 3.0, not under the rest
of this repository's terms: you may share and adapt it with attribution, and
what you build from it must carry the same or a compatible licence. The app
shows the credit line (`hand.CREDIT["ja"]`) under the writing pad.

**How it was built:** `python scripts/build_strokes.py` downloads the release zip
to a temporary folder, reads `kanji/<code>.svg` for each character (stroke paths
`kvg:<code>-s<n>`, in that order), writes this file and deletes the download.
The JSON's own `notice` field records what was changed and when.

**Known gaps:** stroke order follows KanjiVG, i.e. the Japanese school standard;
the small kana (ゃ ゅ ょ っ) sit in the lower part of the box, as written.
