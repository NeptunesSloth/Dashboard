#!/usr/bin/env python3
"""Slice a disciple contact-sheet into per-archetype, per-state sprite strips.

The Realm Map renderer (static/command/map.js) loads authored character art
from ``static/assets/sect/disciples/`` named ``<role>_<state>_<F>f.png`` where
``<F>`` is the number of evenly-spaced frames packed left-to-right in the strip.
The engine divides the strip width by ``<F>`` to play the animation, so this
tool only needs to cut the sheet at the *state-group* boundaries (5 per row),
not at every individual frame.

Input sheet layout (one archetype per row, states across the columns):

    role   ->  idle(4)  walk(6)  work(4)  meditate(2)  celebrate(4)

The script crops each (row, state) cell, removes the near-white background by
flood-filling inward from the borders (so enclosed light areas like the Elder's
white robe survive), trims to the character bbox vertically (feet on the bottom
edge) while keeping the full state x-span (so frame spacing stays even), and
writes a transparent PNG strip.

Geometry defaults match the bundled 1536x1024 reference sheet; override with the
CLI flags if you regenerate the art at a different size.
"""
from __future__ import annotations

import argparse
import os
from collections import deque

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    raise SystemExit("Pillow is required: pip install pillow")

# Archetype rows, top->bottom. Filename keys must match map.js role keys.
ROLES = ["leader", "elder", "researcher", "analyst", "engineer", "architect", "trader", "disciple"]

# State columns, left->right: (name, frame_count).
STATES = [("idle", 4), ("walk", 6), ("work", 4), ("meditate", 2), ("celebrate", 4)]

# Vertical ink-band per row (y0, y1) on the reference sheet.
ROW_BANDS = [(60, 190), (202, 330), (344, 468), (480, 594), (605, 716), (727, 838), (844, 938), (937, 1022)]

# Horizontal span per state-group (x0, x1) on the reference sheet.
STATE_BANDS = {
    "idle": (132, 420), "walk": (420, 836), "work": (836, 1108),
    "meditate": (1108, 1249), "celebrate": (1249, 1532),
}

PAD = 4  # px of breathing room kept around the vertical bbox


def is_bg(px) -> bool:
    r, g, b = px[0], px[1], px[2]
    return min(r, g, b) >= 230 and (max(r, g, b) - min(r, g, b)) <= 16


def cut_transparent(cell: Image.Image) -> Image.Image:
    """Return an RGBA copy with the border-connected near-white made transparent."""
    cell = cell.convert("RGBA")
    w, h = cell.size
    px = cell.load()
    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            q.append((x, y))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        if not is_bg(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        if x > 0:
            q.append((x - 1, y))
        if x < w - 1:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y < h - 1:
            q.append((x, y + 1))
    return cell


def vbbox(cell: Image.Image) -> tuple[int, int]:
    """Top/bottom of opaque content (alpha>0)."""
    w, h = cell.size
    px = cell.load()
    top, bot = None, None
    for y in range(h):
        if any(px[x, y][3] > 12 for x in range(w)):
            if top is None:
                top = y
            bot = y
    if top is None:
        return 0, h
    return max(0, top - PAD), min(h, bot + 1 + PAD)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.join(here, os.pardir, "maybot_control_center",
                               "static", "assets", "sect", "disciples")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet", help="path to the contact-sheet PNG")
    ap.add_argument("--out", default=os.path.normpath(default_out), help="output directory")
    args = ap.parse_args()

    sheet = Image.open(args.sheet).convert("RGB")
    os.makedirs(args.out, exist_ok=True)
    written = 0
    for r, role in enumerate(ROLES):
        ry0, ry1 = ROW_BANDS[r]
        for state, frames in STATES:
            sx0, sx1 = STATE_BANDS[state]
            cell = cut_transparent(sheet.crop((sx0, ry0, sx1, ry1)))
            top, bot = vbbox(cell)
            strip = cell.crop((0, top, cell.width, bot))
            name = f"{role}_{state}_{frames}f.png"
            strip.save(os.path.join(args.out, name))
            written += 1
    print(f"wrote {written} strips to {args.out}")


if __name__ == "__main__":
    main()
