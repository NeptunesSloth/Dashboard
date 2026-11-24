"""Browser smoke test: drive the real app with ALL outside network blocked.

Run the app first (``python -m sect_academy``), then ``python tests/smoke_browser.py``.
Fails on any uncaught JS error, any console error, or any request to a host
other than the app itself — which is how "works completely offline" is enforced.
"""
import os
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE = os.getenv("SMOKE_BASE", "http://127.0.0.1:8200")
_EXE = os.getenv("PW_EXECUTABLE")
HOST = urlparse(BASE).hostname


def main() -> int:
    errors: list[str] = []
    outside: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=_EXE) if _EXE else p.chromium.launch(args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1280, "height": 900})

        def gate(route):
            host = urlparse(route.request.url).hostname
            if host != HOST:
                outside.append(route.request.url)
                return route.abort()
            return route.continue_()

        ctx.route("**/*", gate)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
        pg.on("dialog", lambda d: d.accept())

        # 1) found a sect, take a placement test, land on the sect
        pg.goto(BASE + "/", wait_until="load", timeout=25000)
        pg.wait_for_selector("#f-go, #sect-root", timeout=10000)
        if pg.query_selector("#f-go"):
            pg.fill("#f-name", "Smoke Sect")
            pg.click("#f-go")
            pg.wait_for_selector("[data-place]", timeout=10000)
            pg.click("[data-place]")
            pg.wait_for_selector("#pl-idk", timeout=10000)
            for _ in range(20):
                if pg.query_selector("#pl-done"):
                    break
                pg.click("#pl-idk")
                pg.wait_for_timeout(200)
            pg.click("#pl-done")
            pg.wait_for_selector("#pl-skip", timeout=10000)
            pg.click("#pl-skip")
        pg.wait_for_selector("#sect-root .hq .room", timeout=10000)

        # 2) the colony: time passes, tabs render, orders work
        hour = pg.inner_text(".status h1 small")
        pg.click("[data-speed='3']")
        pg.wait_for_timeout(4500)
        assert pg.inner_text(".status h1 small") != hour, "the sect's clock did not advance"
        for tab in ("work", "build", "research", "chronicle", "disciples"):
            pg.click(f"[data-tab='{tab}']")
            pg.wait_for_timeout(150)
        pg.click("[data-tab='work']")
        pg.click(".prio")
        pg.click("[data-tab='disciples']")
        pg.click(".pawn")
        pg.wait_for_selector("#sheet .body", timeout=5000)
        pg.keyboard.press("Escape")
        pg.click(".room[data-room='library']")
        pg.wait_for_selector("#sheet .body", timeout=5000)
        pg.keyboard.press("Escape")
        pg.click("[data-speed='0']")

        # 3) a study session answers and gives feedback
        pg.goto(BASE + "/study", wait_until="load", timeout=25000)
        pg.wait_for_selector(".session, .summary", timeout=10000)
        answered = 0
        for _ in range(80):
            if answered >= 4 or pg.query_selector(".gains"):
                break
            nxt = pg.query_selector("#s-next")
            if nxt:
                nxt.click()
            elif pg.query_selector(".opt[data-i]:not(:disabled)"):
                pg.click(".opt[data-i]:not(:disabled)")
                pg.wait_for_selector(".verdict", timeout=5000)
                answered += 1
            elif pg.query_selector("#s-in:not(:disabled)"):
                pg.fill("#s-in", "test")
                pg.click("#s-check")
                pg.wait_for_selector(".verdict", timeout=5000)
                answered += 1
            pg.wait_for_timeout(60)
        assert answered >= 1, "the study session produced no answerable exercise"

        # 4) every other page renders
        for path, sel in (("/library", ".course"), ("/trials", "h1"), ("/progress", ".stats")):
            pg.goto(BASE + path, wait_until="load", timeout=25000)
            pg.wait_for_selector(sel, timeout=10000)
            pg.wait_for_timeout(300)

        # 5) phone width, dark mode
        m = b.new_context(viewport={"width": 390, "height": 800}, color_scheme="dark")
        m.route("**/*", gate)
        mp = m.new_page()
        mp.on("pageerror", lambda e: errors.append(f"pageerror(mobile): {e}"))
        mp.goto(BASE + "/", wait_until="load", timeout=25000)
        mp.wait_for_selector("#sect-root .hq", timeout=10000)
        b.close()

    assert not outside, f"the app tried to reach outside hosts: {outside[:5]}"
    assert not errors, f"JS errors: {errors[:5]}"
    print("smoke OK (offline: no request left the app; sect, study, library, trials, progress, phone)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
