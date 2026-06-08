import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.getenv("SMOKE_BASE", "http://127.0.0.1:8200")
_EXE = os.getenv("PW_EXECUTABLE")   # local override; CI uses the installed Chromium


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=_EXE) if _EXE else p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page()
        # Console: the unified left rail must build and tabs must switch.
        pg.goto(BASE + "/console", wait_until="load", timeout=25000)
        pg.wait_for_timeout(1500)
        rail = pg.eval_on_selector_all("#side-rail .sr-item", "els => els.length")
        assert rail >= 5, f"side rail not built ({rail})"
        pg.click(".sr-item[data-k='ops']")
        pg.wait_for_timeout(500)
        vis = pg.evaluate("Array.from(document.querySelectorAll('.container>section'))"
                          ".filter(s=>!s.classList.contains('tab-hidden')).map(s=>s.dataset.tab)")
        assert "ops" in vis, f"tab switch failed: {vis}"
        # Login page renders.
        pg.goto(BASE + "/login", wait_until="load", timeout=25000)
        pg.wait_for_timeout(800)
        assert pg.query_selector("#login-body"), "login page missing"
        # Command hall renders its rail.
        pg.goto(BASE + "/", wait_until="load", timeout=25000)
        pg.wait_for_timeout(1000)
        assert pg.eval_on_selector_all("#rail .nav-item", "els => els.length") >= 5, "command rail missing"
        b.close()
    print("smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
