# Chinese stroke order (hanzi)

`makemeahanzi.json` is the stroke data the handwriting exercise (`glyph_write`)
uses for Mandarin: every CJK character that appears anywhere in the Mandarin
course files — 425 characters, 3,260 strokes, 888 KB. For each character, in
stroke order: `m`, the stroke's median (centre line) as a flat point list, and
`o`, the stroke's filled outline as an SVG path (absolute M/L/Q/C/Z). All
coordinates are in a 1000 × 1000 box, origin top left, y down.

**Source:** Make Me a Hanzi by Shaunak Kishore, `graphics.txt`,
https://github.com/skishore/makemeahanzi (master, fetched 27 November 2026).
Its `COPYING` (copied here unchanged as `COPYING`) says `graphics.txt` is
derived from the fonts Arphic PL KaitiM GB and Arphic PL UKai and may be
redistributed and modified under the Arphic Public License.

**Licence:** Arphic Public License (Copyright (C) 1999 Arphic Technology Co.,
Ltd.), the full text in `ARPHICPL.TXT` in this folder, unaltered as the licence
requires. It is not the licence of the rest of this repository. What it asks
of us, and how this folder meets it:

- Copies must keep `ARPHICPL.TXT` unaltered: it is here, byte for byte as in
  Make Me a Hanzi's `APL/english/ARPHICPL.TXT`.
- A modified file must carry a prominent notice saying how and when it was
  changed: `makemeahanzi.json` is a modification (a subset, coordinates moved
  to a 1000 box with y down, rounded, stored as JSON), and its `notice` field,
  the first thing after the source and licence fields, says so with the date.
- Modifications must be freely available as a whole, under the same licence:
  the file ships with the app, in source form, under the Arphic Public License,
  and `scripts/build_strokes.py` rebuilds it from the public original.
- No warranty (sections 7 and 8 of the licence).

The licence allows redistribution and modification, so the Mandarin course
uses this data; KanjiVG is not needed as a fallback. The rest of the app is a
separate work that only reads this file (licence section 2: mere aggregation),
so the licence does not extend to it. The app shows the credit line
(`hand.CREDIT["zh"]`) under the writing pad.

**How it was built:** `python scripts/build_strokes.py` downloads
`graphics.txt` (30 MB) to a temporary folder, keeps the course's characters,
writes this file and deletes the download.

**Known gaps:** the strokes are those of a Kaiti (brush) font: the shapes, and a
few stroke orders, follow the mainland simplified-character standard as Make Me
a Hanzi gives it.
