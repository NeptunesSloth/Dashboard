"""Check and adjust the pins of a picture lesson against its painting.

    python scripts/pin_preview.py body                  # -> pin_preview_body.png (pins + a 10% grid)
    python scripts/pin_preview.py body --lang es        # label the pins with a course's words
    python scripts/pin_preview.py body --html out.html  # a page where the pins can be dragged; it prints
                                                        # the pins: block to paste into packs/pictures/body.yaml
    python scripts/pin_preview.py --all                 # a PNG for every picture

The picture is sect_academy/static/art/pic_<id>.webp; while it is missing, a dark panel stands in,
so a layout can be checked before the painting exists. The PNG needs Pillow (pip install pillow);
the HTML page does not. Both are written locally and never served by the app.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sect_academy import packs  # noqa: E402

W, H = 1200, 900
LANGS = {"es": "spanish-pictures", "fr": "french-pictures", "zh": "mandarin-pictures",
         "ja": "japanese-pictures", "ko": "korean-pictures"}


def words(picture: str, lang: str | None) -> dict[str, str]:
    """pin id -> the label to draw: the course's word (with its romanisation), else the English."""
    pic = packs.pictures()[picture]
    out = {p["id"]: p["en"] for p in pic["pins"]}
    if not lang:
        return out
    pack = packs._read(packs.PACK_DIR / f"{LANGS[lang].split('-')[0]}_pictures.yaml") or {}
    for u in pack.get("units", []):
        for it in u.get("items", []):
            if it.get("type") == "picture" and it.get("picture") == picture:
                for qid, pin in it["pins"].items():
                    out[qid] = pin["l2"] + (f" ({pin['rom']})" if pin.get("rom") else "")
    return out


def art(picture: str) -> Path:
    return packs.ART_DIR / f"pic_{picture}.webp"


def png(picture: str, out: Path, lang: str | None) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        sys.exit("The PNG preview needs Pillow: pip install pillow (or use --html).")
    pic = packs.pictures()[picture]
    if art(picture).is_file():
        img = Image.open(art(picture)).convert("RGB").resize((W, H))
    else:
        img = Image.new("RGB", (W, H), (16, 22, 42))
    d = ImageDraw.Draw(img, "RGBA")

    def font(size: int):
        # a font with Chinese, kana and hangul first (Windows, macOS, Linux names), then plain Latin
        for name in ("msgothic.ttc", "malgun.ttf", "msyh.ttc", "Hiragino Sans GB.ttc", "AppleSDGothicNeo.ttc",
                     "NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                     "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()
    small, big = font(16), font(20)
    for i in range(1, 10):                        # the 10% grid, labelled, to read coordinates off
        x, y = W * i // 10, H * i // 10
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 50))
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 50))
        d.text((x + 3, 3), str(i * 10), fill=(255, 255, 255, 140), font=small)
        d.text((3, y + 3), str(i * 10), fill=(255, 255, 255, 140), font=small)
    labels = words(picture, lang)
    for n, p in enumerate(pic["pins"], 1):
        x, y = p["x"] * W / 100, p["y"] * H / 100
        d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=(255, 194, 51, 235), outline=(255, 246, 220), width=2)
        d.text((x, y), str(n), fill=(58, 42, 0), font=big, anchor="mm")
        text = f"{p['id']}: {labels[p['id']]}  ({p['x']:g}, {p['y']:g})"
        tw = d.textlength(text, font=small)
        d.rectangle([x - tw / 2 - 5, y + 18, x + tw / 2 + 5, y + 40], fill=(10, 14, 26, 210))
        d.text((x, y + 29), text, fill=(255, 246, 220), font=small, anchor="mm")
    if not art(picture).is_file():
        d.text((W - 8, H - 8), f"pic_{picture}.webp is not painted yet: pins on a blank panel", fill=(255, 255, 255, 120),
               font=small, anchor="rd")
    img.save(out)
    print(f"wrote {out}")


PAGE = """<!doctype html><meta charset="utf-8"><title>Pins: {title}</title>
<style>body{{background:#0f1627;color:#edf2fb;font:15px system-ui;margin:16px}}#f{{position:relative;width:min(1200px,100%);aspect-ratio:4/3;background:#10162a}}
#f img{{width:100%;height:100%;display:block}}.p{{position:absolute;transform:translate(-50%,-50%);width:28px;height:28px;border-radius:50%;background:#ffc233;color:#3a2a00;
border:2px solid #fff6dc;display:grid;place-items:center;font-weight:800;cursor:grab;user-select:none;touch-action:none}}
.p i{{position:absolute;top:30px;left:50%;transform:translateX(-50%);white-space:nowrap;font-style:normal;background:#000c;color:#fff6dc;padding:1px 6px;border-radius:6px;font-weight:600;font-size:12px}}
pre{{background:#18223a;padding:10px;border-radius:8px;user-select:all}}</style>
<h1>{title}</h1><p>Drag the pins onto the things they name, then copy the block below into
<code>sect_academy/packs/pictures/{id}.yaml</code> (replace its <code>pins:</code>). Pin ids never change.</p>
<div id="f">{img}</div><pre id="out"></pre>
<script>
const PINS = {pins};
const f = document.getElementById('f'), out = document.getElementById('out');
const r1 = (v) => Math.round(v * 2) / 2;
function show() {{ out.textContent = 'pins:\\n' + PINS.map((p) => `  - {{id: ${{p.id}}, x: ${{p.x}}, y: ${{p.y}}, en: ${{p.en}}}}`).join('\\n'); }}
PINS.forEach((p, i) => {{
  const el = document.createElement('div'); el.className = 'p'; el.textContent = i + 1;
  const lab = document.createElement('i'); lab.textContent = p.id + ': ' + p.label; el.appendChild(lab);
  const place = () => {{ el.style.left = p.x + '%'; el.style.top = p.y + '%'; }};
  place(); f.appendChild(el);
  el.onpointerdown = (e) => {{
    el.setPointerCapture(e.pointerId);
    el.onpointermove = (m) => {{ const b = f.getBoundingClientRect();
      p.x = r1(Math.min(100, Math.max(0, 100 * (m.clientX - b.left) / b.width)));
      p.y = r1(Math.min(100, Math.max(0, 100 * (m.clientY - b.top) / b.height))); place(); show(); }};
    el.onpointerup = () => {{ el.onpointermove = null; }};
  }};
}});
show();
</script>"""


def page(picture: str, out: Path, lang: str | None) -> None:
    pic = packs.pictures()[picture]
    labels = words(picture, lang)
    pins = [{"id": p["id"], "x": p["x"], "y": p["y"], "en": p["en"], "label": labels[p["id"]]} for p in pic["pins"]]
    if art(picture).is_file():
        img = f'<img src="data:image/webp;base64,{base64.b64encode(art(picture).read_bytes()).decode()}" alt="">'
    else:
        img = ""
    out.write_text(PAGE.format(title=html.escape(pic["title"]), id=html.escape(picture), img=img,
                               pins=json.dumps(pins).replace("</", "<\\/")), encoding="utf-8")
    print(f"wrote {out}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("picture", nargs="?", help="picture id (a file in sect_academy/packs/pictures/)")
    ap.add_argument("--all", action="store_true", help="a PNG for every picture")
    ap.add_argument("--lang", choices=sorted(LANGS), help="label the pins with this course's words")
    ap.add_argument("--out", help="PNG path (default pin_preview_<id>.png)")
    ap.add_argument("--html", help="write a draggable HTML page here instead of a PNG")
    a = ap.parse_args(argv)
    known = packs.pictures()
    ids = sorted(known) if a.all else [a.picture]
    if not ids or any(i not in known for i in ids):
        print("known pictures:", ", ".join(sorted(known)))
        return 2
    for pid in ids:
        if a.html and not a.all:
            page(pid, Path(a.html), a.lang)
        else:
            png(pid, Path(a.out if a.out and not a.all else f"pin_preview_{pid}.png"), a.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
