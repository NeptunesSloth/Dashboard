"""Browser smoke test: drive the real app with ALL outside network blocked.

Run the app first (``python -m sect_academy``), then ``python tests/smoke_browser.py``.
Fails on any uncaught JS error, any console error, or any request to a host
other than the app itself — which is how "works completely offline" is enforced.
"""
import io
import os
import sys
import zipfile
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE = os.getenv("SMOKE_BASE", "http://127.0.0.1:8200")
_EXE = os.getenv("PW_EXECUTABLE")
HOST = urlparse(BASE).hostname
STORY = "Hola, Juan. Dimelo cuando puedas. Las casas del pueblo son blancas y el mar esta cerca."
# An Aozora Bunko-style book: Shift_JIS, ruby 《reading》 with the ｜ base marker, a ［＃…］ note, the symbol key
# between dashed lines at the top and the colophon (底本) at the end — all of which the import must take out.
AOZORA = ("吾輩は猫である\n夏目漱石\n\n" + "-" * 55 + "\n【テキスト中に現れる記号について】\n《》：ルビ\n" + "-" * 55 + "\n\n"
          "［＃８字下げ］一［＃「一」は中見出し］\n\n｜吾輩《わがはい》は猫である。名前《なまえ》はまだ無い。"
          "昨日、友達と映画を見ました。私は寿司を食べました。日本語を勉強しています。\n\n\n\n"
          "底本：「夏目漱石全集」\n入力：青空文庫\n").encode("cp932")
HANZI = ("我喜欢学习中文。他们在图书馆看书。我们已经学了三年中文了，但是说得还不太好。"
         "從前有座山，山裡有座廟，廟裡有個老和尚在給小和尚講故事。").encode("gb18030")
KO_STORY = "어제 저는 친구와 학교에서 밥을 먹었어요. 날씨가 너무 더워요. 그래서 우리는 집에 갔어요. 오늘은 한국어를 공부했습니다."
FR_STORY = ("The Project Gutenberg eBook of Petit conte\n\n*** START OF THE PROJECT GUTENBERG EBOOK PETIT CONTE ***\n\n"
            "Le matin, nous allons au marché. « Où est l'homme ? » dit-il. Les chevaux étaient déjà là, "
            "et l'été arrivait doucement sur le village.\n\n*** END OF THE PROJECT GUTENBERG EBOOK PETIT CONTE ***\n"
            "Licence text that is not the book.")


def _pdf(text: str) -> bytes:
    """A one-page PDF with real text (no PDF library needed)."""
    stream = f"BT /F1 12 Tf 40 760 Td ({text}) Tj ET".encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def _epub(text: str) -> bytes:
    """A minimal EPUB 3 (deflated chapter, so the browser's own inflater is exercised). The chapter carries a
    script and an outside image: neither may run or load."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Un cuento</dc:title></metadata>'
                   '<manifest><item id="c1" href="text/ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'
                   '<spine><itemref idref="c1"/></spine></package>')
        z.writestr("OEBPS/text/ch1.xhtml", f'<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Uno</h1><p>{text}</p>'
                   '<script>window.__epubRan = 1</script><img src="https://example.com/x.png"/></body></html>',
                   compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


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
        pg.wait_for_selector("#f-go, #sect-root", state="attached", timeout=10000)
        if pg.query_selector("#f-go"):
            pg.fill("#f-name", "Smoke Sect")
            pg.click(".rite-step[data-step='1'] [data-next]")
            pg.click(".tongue >> nth=0")          # opens the first language; its A1 is chosen
            pg.click(".rite-step[data-step='2'] [data-next]")
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
            if path == "/trials" and pg.query_selector("[data-ldrill]"):       # a language drill: choose, start, answer one
                pg.click("[data-ldrill]")
                pg.wait_for_selector("#d-go", timeout=10000)
                pg.click("#d-go")
                pg.wait_for_selector("#d-in", timeout=10000)
                pg.fill("#d-in", "test")
                pg.click("#d-check")
                pg.wait_for_selector(".verdict", timeout=5000)

        # 5) Read: a dictionary lookup, then a PDF (through the vendored pdf.js and its worker) and an EPUB
        #    imported, opened and a word tapped — all of it with the outside world blocked.
        pg.goto(BASE + "/read?tab=dict", wait_until="load", timeout=25000)
        pg.fill("#dq", "dímelo")
        pg.wait_for_selector(".dict-row", timeout=10000)
        pg.click(".dict-row")
        pg.wait_for_selector(".lookup .lk-senses", timeout=10000)
        assert "decir" in pg.inner_text(".lookup"), "dímelo did not lead to decir"
        for name, data in (("cuento.pdf", _pdf(STORY)), ("cuento.epub", _epub(STORY))):
            pg.goto(BASE + "/read", wait_until="load", timeout=25000)
            pg.wait_for_selector("#rb-file", state="attached", timeout=10000)
            mime = "application/pdf" if name.endswith(".pdf") else "application/epub+zip"
            pg.set_input_files("#rb-file", files=[{"name": name, "mimeType": mime, "buffer": data}])
            pg.wait_for_selector("#rd .w", timeout=30000)
            pg.locator("#rd .w", has_text="casas").first.click()
            pg.wait_for_selector(".lookup .lk-senses", timeout=10000)
            assert "casa" in pg.inner_text(".lookup .lk-path"), f"{name}: casas did not lead to casa"
        assert not pg.evaluate("window.__epubRan"), "a script inside an EPUB ran"
        # old plain-text encodings, each with the markup its source wraps it in: a Korean book in EUC-KR, a French one
        # in windows-1252 inside a Gutenberg wrapper, a Japanese one in Shift_JIS with Aozora Bunko markup, a Chinese
        # one in GB18030. Decoded, cut into words, looked up.
        for name, lang, data, tap, want in (
                ("ko.txt", "ko", KO_STORY.encode("euc-kr"), "먹었어요", "먹다"),
                ("fr.txt", "fr", FR_STORY.encode("cp1252"), "allons", "aller"),
                ("neko.txt", "ja", AOZORA, "食べました", "polite past"),
                ("shu.txt", "zh", HANZI, "图书馆", "library")):
            pg.goto(BASE + "/read", wait_until="load", timeout=25000)
            pg.wait_for_selector("#rb-file", state="attached", timeout=10000)
            pg.select_option("#rb-lang", lang)
            pg.set_input_files("#rb-file", files=[{"name": name, "mimeType": "text/plain", "buffer": data}])
            pg.wait_for_selector("#rd .w", timeout=30000)
            page_text = pg.inner_text("#rd")
            assert "GUTENBERG" not in page_text, f"{name}: the Gutenberg licence was left in"
            assert "《" not in page_text and "［＃" not in page_text and "底本" not in page_text and "記号" not in page_text, page_text
            if lang in ("ja", "zh"):
                assert ("吾輩は猫である。" in page_text) if lang == "ja" else ("图书馆" in page_text), page_text
            pg.locator("#rd .w", has_text=tap).first.click()
            pg.wait_for_selector(".lookup .lk-senses", timeout=10000)
            where = ".lookup .lk-path" if lang in ("ko", "fr") else ".lookup"
            assert want in pg.inner_text(where), f"{name}: {tap} gave {pg.inner_text('.lookup')}"

        # 6) phone width, dark mode
        m = b.new_context(viewport={"width": 390, "height": 800}, color_scheme="dark")
        m.route("**/*", gate)
        mp = m.new_page()
        mp.on("pageerror", lambda e: errors.append(f"pageerror(mobile): {e}"))
        mp.goto(BASE + "/", wait_until="load", timeout=25000)
        mp.wait_for_selector("#sect-root .hq", timeout=10000)
        b.close()

    assert not outside, f"the app tried to reach outside hosts: {outside[:5]}"
    assert not errors, f"JS errors: {errors[:5]}"
    print("smoke OK (offline: no request left the app; sect, study, read (dictionary, PDF, EPUB, EUC-KR Korean, windows-1252 French, Shift_JIS Japanese, GB18030 Chinese), library, trials, progress, phone)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
