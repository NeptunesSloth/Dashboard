#!/usr/bin/env python3
"""Voxel isometric sprite baker for the Realm Map (Sect Headquarters).

Buildings are authored as voxel models (à la MagicaVoxel), then rendered once to
transparent isometric PNG sprites with shaded faces, block outlines and a little
weathering noise. The Realm Map blits these sprites instead of drawing buildings
from live primitives. Iso matches the map: 6 voxels per tile, 2:1 projection.

Run:  python tools/build_sect_sprites.py
Out:  maybot_control_center/static/assets/sect/*.png  (+ manifest.json)
"""
import json, math, os, random
from PIL import Image, ImageDraw

N = 6                       # voxels per map tile
TW2, TH2 = 40, 20          # map half-tile width/height (must match map.js)
SS = 4                     # supersample factor for crisp downscale
HW, HH = TW2 / N * SS, TH2 / N * SS
VH = HW                    # voxel height in px (cubic-ish)
OUT = "maybot_control_center/static/assets/sect"


def mul(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))), max(0, min(255, int(c[2] * f))))


# ---------------- voxel authoring helpers ----------------
def box(m, x0, y0, z0, sx, sy, sz, c, jit=8):
    for x in range(x0, x0 + sx):
        for y in range(y0, y0 + sy):
            for z in range(z0, z0 + sz):
                j = random.randint(-jit, jit)
                m[(x, y, z)] = (max(0, min(255, c[0] + j)), max(0, min(255, c[1] + j)), max(0, min(255, c[2] + j)))


def roof(m, cx, cy, z0, hw, hd, layers, c):
    """Stepped pagoda roof: wide eaves tapering up, with upturned corner tips."""
    for i in range(layers):
        w, d = hw - i, hd - i
        if w < 0 or d < 0:
            break
        box(m, cx - w, cy - d, z0 + i, 2 * w + 1, 2 * d + 1, 1, c, jit=6)
    # upturned eave tips (raise the four corners of the bottom layer)
    for (dx, dy) in [(-hw, -hd), (hw, -hd), (-hw, hd), (hw, hd)]:
        box(m, cx + dx, cy + dy, z0 + 1, 1, 1, 1, mul(c, 1.15), jit=0)


def gem(m, cx, cy, z0, h, c):
    for z in range(h):
        r = max(0, (h - z) // 2)
        box(m, cx - r, cy - r, z0 + z, 2 * r + 1, 2 * r + 1, 1, c, jit=10)


# ---------------- building models ----------------
STONE = (122, 120, 140)
STONE_D = (92, 90, 110)
WOOD = (120, 86, 54)
ROOF = (110, 84, 196)
ROOFG = (196, 150, 60)
JADE = (66, 150, 96)
GOLD = (228, 188, 78)
CRYS = (96, 176, 248)
WATER = (70, 150, 210)


def m_grand_pagoda():
    m = {}
    box(m, 0, 0, 0, 20, 20, 2, STONE_D)             # plinth (foot 20 = ~3.3 tiles)
    box(m, 2, 2, 2, 16, 16, 1, STONE)               # terrace
    box(m, 4, 4, 3, 12, 12, 6, WOOD)                # body 1
    roof(m, 10, 10, 9, 10, 10, 3, ROOF)
    box(m, 6, 6, 12, 8, 8, 5, WOOD)                 # body 2
    roof(m, 10, 10, 17, 7, 7, 3, ROOF)
    box(m, 8, 8, 22, 4, 4, 4, STONE)                # body 3
    roof(m, 10, 10, 26, 4, 4, 2, ROOF)
    box(m, 9, 9, 28, 2, 2, 3, ROOFG)                # finial
    gem(m, 9, 9, 31, 3, GOLD)
    return m, 20, 20


def m_pagoda():
    m = {}
    box(m, 0, 0, 0, 16, 12, 2, STONE_D)
    box(m, 2, 2, 2, 12, 8, 6, WOOD)
    roof(m, 8, 6, 8, 9, 7, 3, ROOF)
    box(m, 5, 4, 11, 6, 4, 4, WOOD)
    roof(m, 8, 6, 15, 6, 5, 2, ROOF)
    box(m, 7, 5, 17, 2, 2, 3, ROOFG)
    return m, 16, 12


def m_pavilion():
    m = {}
    box(m, 0, 0, 0, 12, 10, 1, STONE)
    for (x, y) in [(1, 1), (10, 1), (1, 8), (10, 8)]:
        box(m, x, y, 1, 1, 1, 8, WOOD)              # posts
    roof(m, 6, 5, 9, 7, 6, 2, ROOF)
    box(m, 5, 4, 11, 2, 2, 2, ROOFG)
    return m, 12, 10


def m_lantern():
    m = {}
    box(m, 0, 0, 0, 3, 3, 7, STONE_D)               # post
    box(m, -1, -1, 7, 5, 5, 3, STONE)               # lamp housing
    box(m, 0, 0, 8, 3, 3, 1, (255, 210, 110))       # light
    box(m, -1, -1, 10, 5, 5, 1, STONE_D)            # cap
    return m, 3, 3


def m_tree():
    m = {}
    box(m, 2, 2, 0, 2, 2, 6, (96, 70, 46))          # trunk
    gem(m, 3, 3, 5, 8, JADE)                         # canopy
    box(m, 1, 3, 8, 1, 1, 1, mul(JADE, 1.3))
    box(m, 5, 2, 9, 1, 1, 1, mul(JADE, 1.3))
    return m, 7, 7


def m_stall():
    m = {}
    box(m, 0, 0, 0, 9, 5, 2, WOOD)                  # counter
    for (x, y) in [(0, 0), (8, 0), (0, 4), (8, 4)]:
        box(m, x, y, 2, 1, 1, 6, mul(WOOD, 0.8))    # posts
    for i in range(9):                              # striped awning
        c = (190, 80, 60) if i % 2 else (236, 232, 220)
        box(m, i, 0, 8, 1, 5, 1, c, jit=4)
    box(m, 0, 0, 8, 9, 1, 2, mul((190, 80, 60), 0.9))  # awning front lip
    return m, 9, 5


def m_gate():
    m = {}
    box(m, 0, 0, 0, 3, 3, 16, mul(ROOF, 0.7))       # left pillar
    box(m, 12, 0, 0, 3, 3, 16, mul(ROOF, 0.7))      # right pillar
    box(m, 0, 0, 16, 15, 3, 2, ROOF)               # lintel
    roof(m, 7, 1, 18, 9, 2, 2, ROOF)               # gate roof
    box(m, 6, 0, 20, 3, 3, 2, ROOFG)
    return m, 15, 3


def m_crystal():
    m = {}
    box(m, 0, 0, 0, 9, 9, 2, mul(CRYS, 0.4))        # base
    gem(m, 4, 4, 2, 16, CRYS)                        # main spire
    gem(m, 1, 5, 2, 8, mul(CRYS, 1.1))
    gem(m, 7, 3, 2, 9, mul(CRYS, 1.1))
    return m, 9, 9


def m_fountain():
    m = {}
    box(m, 0, 0, 0, 11, 11, 2, mul(GOLD, 0.6))      # outer basin
    box(m, 2, 2, 2, 7, 7, 1, WATER)                 # water
    box(m, 3, 3, 3, 5, 5, 3, mul(GOLD, 0.8))        # mid tier
    box(m, 4, 4, 6, 3, 3, 1, WATER)
    box(m, 5, 5, 7, 1, 1, 5, GOLD)                  # spout
    box(m, 4, 4, 12, 3, 3, 1, mul(WATER, 1.2))
    return m, 11, 11


def m_observatory():
    m = {}
    box(m, 0, 0, 0, 11, 11, 2, STONE_D)
    box(m, 2, 2, 2, 7, 7, 7, STONE)                 # tower
    for z in range(4):                              # dome
        r = 4 - z
        box(m, 5 - r, 5 - r, 9 + z, 2 * r + 1, 2 * r + 1, 1, mul(CRYS, 0.7))
    box(m, 5, 5, 13, 1, 1, 2, GOLD)                 # telescope tip
    return m, 11, 11


def m_forge():
    m = {}
    box(m, 0, 0, 0, 11, 9, 2, STONE_D)
    box(m, 1, 1, 2, 9, 7, 5, STONE)                 # hut
    roof(m, 5, 4, 7, 6, 5, 2, mul(ROOF, 0.8))
    box(m, 8, 5, 7, 2, 2, 8, STONE_D)               # chimney
    box(m, 8, 5, 15, 2, 2, 1, (255, 150, 60))       # ember
    box(m, 4, 3, 2, 3, 3, 1, (255, 140, 50))        # forge glow
    return m, 11, 9


def m_bell():
    m = {}
    box(m, 0, 0, 0, 9, 4, 1, STONE_D)
    box(m, 0, 1, 1, 1, 2, 12, WOOD)                 # frame posts
    box(m, 8, 1, 1, 1, 2, 12, WOOD)
    box(m, 0, 1, 13, 9, 2, 1, WOOD)                 # crossbeam
    for z in range(7):                              # bell
        r = 2 + z // 4
        box(m, 4 - r, 1, 5 + z, 2 * r + 1, 2, 1, mul(ROOFG, 0.9), jit=6)
    return m, 9, 4


PINE = (44, 120, 78)
CHERRY = (236, 156, 196)


def m_pine():
    m = {}
    box(m, 2, 2, 0, 2, 2, 5, (96, 70, 46))          # trunk
    box(m, 0, 0, 5, 6, 6, 1, mul(PINE, 0.85))
    box(m, 1, 1, 6, 4, 4, 2, PINE)
    box(m, 1, 1, 8, 4, 4, 1, mul(PINE, 1.08))
    box(m, 2, 2, 9, 2, 2, 2, mul(PINE, 1.15))
    box(m, 2, 2, 11, 2, 2, 1, mul(PINE, 1.2))
    box(m, 3, 3, 12, 1, 1, 2, mul(PINE, 1.25))
    return m, 6, 6


def m_cherry():
    m = {}
    box(m, 2, 2, 0, 2, 2, 5, (110, 80, 54))         # trunk
    gem(m, 3, 3, 5, 7, CHERRY)                        # blossom canopy
    box(m, 1, 4, 8, 1, 1, 1, mul(CHERRY, 1.1))
    box(m, 5, 2, 9, 1, 1, 1, mul(CHERRY, 1.1))
    return m, 7, 7


def m_crane():
    m = {}
    box(m, 2, 2, 0, 1, 1, 3, (40, 40, 44))          # legs
    box(m, 4, 3, 0, 1, 1, 3, (40, 40, 44))
    box(m, 1, 1, 3, 5, 3, 2, (240, 240, 244))       # body
    box(m, 0, 2, 3, 1, 1, 2, (28, 28, 30))          # tail
    box(m, 5, 2, 5, 1, 1, 3, (240, 240, 244))       # neck
    box(m, 6, 2, 8, 1, 1, 1, (240, 240, 244))       # head
    box(m, 6, 2, 9, 1, 1, 1, (208, 56, 56))         # red crown
    return m, 6, 5


def m_shrine():
    m = {}
    box(m, 0, 0, 0, 9, 9, 2, STONE_D)               # stone terrace
    box(m, 2, 2, 2, 5, 5, 1, mul(GOLD, 0.55))       # gilded platform
    box(m, 2, 3, 3, 1, 1, 6, (168, 40, 40))         # torii posts
    box(m, 6, 3, 3, 1, 1, 6, (168, 40, 40))
    box(m, 1, 3, 9, 7, 1, 1, (150, 30, 30))         # torii lintels
    box(m, 1, 3, 10, 7, 1, 1, (120, 24, 24))
    box(m, 4, 5, 3, 1, 1, 2, STONE)                 # altar
    gem(m, 4, 5, 5, 3, GOLD)                          # golden relic
    roof(m, 4, 4, 7, 4, 4, 2, ROOFG)                 # golden roof
    box(m, 4, 4, 9, 1, 1, 2, GOLD)
    return m, 9, 9


MODELS = {
    "grand_pagoda": m_grand_pagoda, "pagoda": m_pagoda, "pavilion": m_pavilion,
    "lantern": m_lantern, "tree": m_tree, "stall": m_stall, "gate": m_gate,
    "crystal": m_crystal, "fountain": m_fountain, "observatory": m_observatory,
    "forge": m_forge, "bell": m_bell, "pine": m_pine, "cherry": m_cherry,
    "crane": m_crane, "shrine": m_shrine,
}


# ---------------- isometric renderer ----------------
def project(x, y, z):
    return ((x - y) * HW, (x + y) * HH - z * VH)


def render(model, footx, footy):
    pts = []
    for (x, y, z) in model:
        for (dx, dy, dz) in [(0, 0, 1), (1, 1, 1), (1, 0, 1), (0, 1, 1)]:
            px, py = project(x + dx, y + dy, z + dz)
            pts.append((px, py))
    minx = min(p[0] for p in pts) - 2 * SS
    maxx = max(p[0] for p in pts) + 2 * SS
    miny = min(p[1] for p in pts) - 2 * SS
    maxy = max(p[1] for p in pts) + 2 * SS
    W, H = int(maxx - minx), int(maxy - miny)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(x, y, z):
        px, py = project(x, y, z)
        return (px - minx, py - miny)

    order = sorted(model.keys(), key=lambda p: (p[0] + p[1] + p[2], p[2], p[0] + p[1]))
    for (x, y, z) in order:
        c = model[(x, y, z)]
        # top (+z)
        if (x, y, z + 1) not in model:
            poly = [P(x, y, z + 1), P(x + 1, y, z + 1), P(x + 1, y + 1, z + 1), P(x, y + 1, z + 1)]
            d.polygon(poly, fill=c, outline=mul(c, 0.78))
        # right face (+x, down-right)
        if (x + 1, y, z) not in model:
            cc = mul(c, 0.52)
            poly = [P(x + 1, y, z), P(x + 1, y + 1, z), P(x + 1, y + 1, z + 1), P(x + 1, y, z + 1)]
            d.polygon(poly, fill=cc, outline=mul(cc, 0.8))
        # left face (+y, down-left)
        if (x, y + 1, z) not in model:
            cc = mul(c, 0.7)
            poly = [P(x, y + 1, z), P(x + 1, y + 1, z), P(x + 1, y + 1, z + 1), P(x, y + 1, z + 1)]
            d.polygon(poly, fill=cc, outline=mul(cc, 0.8))

    ax, ay = project(footx / 2, footy / 2, 0)
    anchor = ((ax - minx) / SS, (ay - miny) / SS)
    img = img.resize((max(1, W // SS), max(1, H // SS)), Image.LANCZOS)
    return img, anchor


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {"tile": [TW2, TH2], "voxPerTile": N, "sprites": {}}
    for name, fn in MODELS.items():
        random.seed(hash(name) & 0xffff)
        model, fx, fy = fn()
        img, (ax, ay) = render(model, fx, fy)
        img.save(os.path.join(OUT, name + ".png"))
        manifest["sprites"][name] = {"file": name + ".png", "w": img.width, "h": img.height,
                                     "anchorX": round(ax, 1), "anchorY": round(ay, 1),
                                     "footTiles": round(fx / N, 3)}
        print(f"{name:14s} {img.width:3d}x{img.height:3d}  anchor=({ax:.0f},{ay:.0f}) foot={fx/N:.2f}t")
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("wrote", len(MODELS), "sprites ->", OUT)


if __name__ == "__main__":
    main()
