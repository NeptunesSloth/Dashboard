#!/usr/bin/env python3
"""Generate Sect Map art assets via OpenAI's image API (gpt-image-1).

Why: the Sect Map's hand-drawn SVG can't match reference-quality xianxia art.
This produces real painted assets — a sky backdrop, individual floating-peak
sprites (transparent), a cloud-sea overlay, a hall backdrop, and one cultivator
figure per activity (transparent) — which the map renders and animates.

Usage:
    OPENAI_API_KEY=...  python scripts/generate_map_assets.py [--force]

Writes PNGs to maybot_control_center/static/assets/map/. Idempotent: skips files
that already exist unless --force. No third-party deps (stdlib urllib).
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "maybot_control_center", "static", "assets", "map")
API = "https://api.openai.com/v1/images/generations"

STYLE = ("Chinese xianxia / wuxia fantasy concept art, soft painterly anime film style, "
         "warm golden-hour sunrise lighting, lush and atmospheric, highly detailed, clean edges.")

# (filename, prompt, size, transparent_background)
ASSETS = [
    ("bg_sky.png",
     f"{STYLE} A serene dawn sky over a sea of clouds with distant hazy blue mountain ranges and a soft glowing sun low on the left, "
     "wispy pink and gold clouds, no foreground objects, panoramic matte painting background.",
     "1536x1024", False),
    ("cloudsea.png",
     f"{STYLE} A band of soft rolling white clouds, a sea of mist, isolated on a fully transparent background, "
     "horizontal strip, fluffy volumetric cloud tops catching warm light.",
     "1536x1024", True),
    ("peak_a.png",
     f"{STYLE} A single tall lush floating karst mountain spire covered in green forest and cliffs, narrow at top, "
     "small waterfalls, isolated on a fully transparent background, full body of the peak, no sky, no clouds.",
     "1024x1536", True),
    ("peak_b.png",
     f"{STYLE} A single rugged floating green mountain pinnacle with pine trees clinging to grey rock ledges, "
     "isolated on a fully transparent background, no sky, no clouds.",
     "1024x1536", True),
    ("peak_c.png",
     f"{STYLE} A single slender emerald jade mountain spire with terraced greenery and a thin waterfall, "
     "isolated on a fully transparent background, no sky, no clouds.",
     "1024x1536", True),
    ("peak_leader.png",
     f"{STYLE} A grand sacred floating mountain summit crowned with an ornate Chinese pavilion with curved tiled roofs, "
     "stone switchback stairs, a glowing ancient sacred tree, waterfalls, lush forest, isolated on a fully transparent background, no sky.",
     "1024x1536", True),
    ("hall_bg.png",
     f"{STYLE} Interior-courtyard view of a serene Chinese cultivation hall pavilion with dark curved tiled roofs and red "
     "wooden pillars, perched on a misty green cliff above clouds, hanging lanterns, soft god rays, empty stone floor in front.",
     "1536x1024", False),
    ("char_cultivate.png",
     f"{STYLE} A young cultivator in flowing jade-blue robes sitting cross-legged in meditation, palms up, a glowing orb of "
     "spiritual qi energy floating above the hands, serene, full body, isolated on a fully transparent background.",
     "1024x1536", True),
    ("char_sweep.png",
     f"{STYLE} A young disciple in simple grey robes standing and sweeping the floor with a straw broom, full body, "
     "mid-sweep, isolated on a fully transparent background.",
     "1024x1536", True),
    ("char_struggle.png",
     f"{STYLE} A cultivator in dark robes kneeling and straining, wrestling a swirling dark shadowy inner demon wisp around them, "
     "tense, full body, isolated on a fully transparent background.",
     "1024x1536", True),
    ("char_seclude.png",
     f"{STYLE} A cultivator meditating inside a translucent glowing protective barrier dome of blue spiritual light, "
     "seated, calm, full body, isolated on a fully transparent background.",
     "1024x1536", True),
    ("char_roam.png",
     f"{STYLE} A traveling cultivator in a straw hat and travel robes walking with a staff, seen from behind, full body, "
     "isolated on a fully transparent background.",
     "1024x1536", True),
]


def generate(name: str, prompt: str, size: str, transparent: bool, key: str) -> None:
    payload = {"model": "gpt-image-1", "prompt": prompt, "size": size, "n": 1}
    if transparent:
        payload["background"] = "transparent"
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)
    b64 = data["data"][0]["b64_json"]
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(base64.b64decode(b64))


def main() -> int:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY not set — add it to the environment and retry.", file=sys.stderr)
        return 2
    os.makedirs(OUT, exist_ok=True)
    force = "--force" in sys.argv
    for name, prompt, size, transparent in ASSETS:
        path = os.path.join(OUT, name)
        if os.path.exists(path) and not force:
            print(f"skip {name} (exists)")
            continue
        for attempt in range(3):
            try:
                print(f"generating {name} ({size}{', transparent' if transparent else ''}) …")
                generate(name, prompt, size, transparent, key)
                print(f"  ✓ {name}")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {name} attempt {attempt + 1} failed: {exc}", file=sys.stderr)
                time.sleep(2 ** attempt)
        else:
            print(f"  ✗ gave up on {name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
