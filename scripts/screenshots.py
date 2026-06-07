#!/usr/bin/env python3
"""Capture dashboard screenshots into docs/img/ with headless Chromium.

Usage:
    pip install playwright && playwright install chromium
    # start the dashboard (e.g. `docker compose up -d` or uvicorn) so it serves
    # on the base URL, then:
    python scripts/screenshots.py

Environment:
    SCREENSHOT_BASE_URL   dashboard URL (default http://127.0.0.1:8200)
    SCREENSHOT_TOKEN      control token, if the dashboard requires one
    PLAYWRIGHT_CHROMIUM   path to a chromium/chrome binary (else Playwright's own)

Best run against an instance that has a few projects configured so the views
aren't empty. Existing files are overwritten.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("SCREENSHOT_BASE_URL", "http://127.0.0.1:8200").rstrip("/")
TOKEN = os.getenv("SCREENSHOT_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "docs" / "img"

# (path, output filename, settle milliseconds) — heavier WebGL views settle longer.
PAGES = [
    ("/console", "dashboard-classic.png", 3500),
    ("/", "dashboard-cockpit.png", 6000),
    ("/trade", "trade-cockpit.png", 5000),
    ("/treasury", "treasury.png", 4000),
]


def _chromium_path() -> str | None:
    p = os.getenv("PLAYWRIGHT_CHROMIUM")
    if p and os.path.exists(p):
        return p
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    exe = _chromium_path()
    launch_args = ["--no-sandbox", "--use-gl=swiftshader", "--ignore-gpu-blocklist",
                   "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=exe, args=launch_args)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=2)
        # Seed the control token so the SPA skips the login overlay.
        if TOKEN:
            ctx.add_init_script(f"try{{localStorage.setItem('control_token',{TOKEN!r});"
                                f"localStorage.setItem('mb_token',{TOKEN!r});}}catch(e){{}}")
        page = ctx.new_page()
        ok = 0
        for path, fname, settle in PAGES:
            url = f"{BASE}{path}"
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception as exc:
                print(f"  ! {url}: {exc}")
            page.wait_for_timeout(settle)
            dest = OUT / fname
            try:
                page.screenshot(path=str(dest))
                size = dest.stat().st_size
                print(f"  ✓ {path} -> docs/img/{fname} ({size} bytes)")
                ok += 1
            except Exception as exc:
                print(f"  ! screenshot {path}: {exc}")
        browser.close()
    print(f"Captured {ok}/{len(PAGES)} screenshots into {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
