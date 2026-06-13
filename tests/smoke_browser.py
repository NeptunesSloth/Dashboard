import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.getenv("SMOKE_BASE", "http://127.0.0.1:8200")
_EXE = os.getenv("PW_EXECUTABLE")   # local override; CI uses the installed Chromium

# Every page + a selector that only renders once the page's JS module has run its
# initial render. If a render function throws (the "CI-green but broken when
# actually loaded" bug class), the page-error sweep below catches it.
PAGES = [
    ("/", "#rail .nav-item"),
    ("/trade", "#rail .nav-item"),
    ("/chamber", "#rail .nav-item"),
    ("/treasury", "#rail .nav-item"),
    ("/learn", "#tracks"),
    ("/console", "#side-rail .sr-item"),
    ("/login", "#login-body"),
]

# Console noise that is not a real bug (optional assets / dev warnings).
_IGNORE = ("favicon", "manifest", "sw.js", "ServiceWorker", "Failed to load resource",
           "the server responded with a status of 404", "Download the React")


def _visit(b, path, must_have):
    """Load a page and fail on any uncaught JS exception; assert it rendered."""
    pg = b.new_page()
    errors, console_errs = [], []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: console_errs.append(m.text)
          if m.type == "error" and not any(s in m.text for s in _IGNORE) else None)
    pg.goto(BASE + path, wait_until="load", timeout=25000)
    pg.wait_for_timeout(1500)
    assert not errors, f"{path}: uncaught JS error(s): {errors}"
    assert pg.query_selector(must_have), f"{path}: did not render ({must_have} missing)"
    if console_errs:
        print(f"  note: {path} console errors (non-fatal): {console_errs[:3]}")
    pg.close()


def _decree_flow(b):
    """Exercise the Heavenly Decree: Ask (copilot) + Command (mission/task) must
    both produce output and raise no uncaught error. (#91 was invisible to a
    page-load-only smoke — it only failed on submit.)"""
    pg = b.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/", wait_until="load", timeout=25000)
    pg.wait_for_selector("#decree-input", timeout=10000)
    out_len = "() => (document.querySelector('#decree-out')||{}).textContent?.trim().length || 0"
    # Ask mode (default).
    pg.fill("#decree-input", "what needs attention?")
    pg.click("#decree-send")
    pg.wait_for_timeout(1800)
    assert pg.evaluate(out_len) > 0, "Heavenly Decree Ask produced no output"
    # Command mode.
    pg.click("#decree-cmd")
    pg.wait_for_timeout(200)
    pg.fill("#decree-input", "scan the fleet")
    pg.click("#decree-send")
    pg.wait_for_timeout(1500)
    assert pg.evaluate(out_len) > 0, "Heavenly Decree Command produced no output"
    assert not errs, f"Heavenly Decree raised: {errs}"
    pg.close()


def _learning_flow(b):
    """Switch through the Learning mode bar and open a lesson — each render path
    must run without an uncaught error (backend-free panels render; backend ones
    degrade gracefully)."""
    pg = b.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/learn", wait_until="load", timeout=25000)
    pg.wait_for_selector("#modes button", timeout=10000)
    for mode in ("plan", "stats", "review", "library", "real",
                 "range", "incident", "material", "skills"):
        btn = pg.query_selector(f"#modes button[data-mode='{mode}']")
        if btn:
            btn.click()
            pg.wait_for_timeout(700)
            assert not errs, f"Learning '{mode}' mode raised: {errs}"
    topic = pg.query_selector("#topics .topic-btn")
    if topic:
        topic.click()
        pg.wait_for_timeout(1200)
    # the per-topic test-out (placement) button
    testout = pg.query_selector("#topics .topic-testout")
    if testout:
        testout.click()
        pg.wait_for_timeout(900)
    assert not errs, f"Learning interactions raised: {errs}"
    pg.close()


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=_EXE) if _EXE else p.chromium.launch(args=["--no-sandbox"])

        # 1) Every page loads and renders with NO uncaught JS errors.
        for path, sel in PAGES:
            _visit(b, path, sel)

        # 1b) Interactive flows (clicks, not just loads).
        _decree_flow(b)
        _learning_flow(b)

        # 2) Deeper interactions on the Command Hall.
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/console", wait_until="load", timeout=25000)
        pg.wait_for_timeout(1500)
        rail = pg.eval_on_selector_all("#side-rail .sr-item", "els => els.length")
        assert rail >= 5, f"side rail not built ({rail})"
        pg.click(".sr-item[data-k='ops']")
        pg.wait_for_timeout(500)
        vis = pg.evaluate("Array.from(document.querySelectorAll('.container>section'))"
                          ".filter(s=>!s.classList.contains('tab-hidden')).map(s=>s.dataset.tab)")
        assert "ops" in vis, f"tab switch failed: {vis}"
        assert pg.query_selector("#settings-gear"), "settings gear missing"
        pg.click("#settings-gear")
        pg.wait_for_timeout(400)
        assert pg.query_selector("#settings-modal"), "settings modal did not open"
        assert not errors, f"/console interactions raised: {errors}"
        b.close()
    print(f"smoke OK ({len(PAGES)} pages + Decree/Learning interactions, no uncaught JS errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
