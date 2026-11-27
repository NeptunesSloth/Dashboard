"""Sect Academy — the whole server.

One FastAPI app: the study API, the sect (colony sim) API and the static app
shell. Nothing here talks to the network, and no page loads anything from
another origin, so it runs fully offline:

    python -m sect_academy            # http://127.0.0.1:8200

Access control is deliberately simple. By default the app is open and binds to
localhost. Set ``SECT_ACADEMY_TOKEN`` to require that token (header
``x-academy-token``) on every API call — do that before exposing it on a LAN.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import colony, dao, drills, engine, hand, packs, reader, state

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Sect Academy", docs_url=None, redoc_url=None, openapi_url=None)


def guard(x_academy_token: str = Header(default="")) -> None:
    want = os.getenv("SECT_ACADEMY_TOKEN", "")
    if want and not secrets.compare_digest((x_academy_token or "").encode("utf-8", "replace"), want.encode()):
        raise HTTPException(401, "token required")


def _allowed_hosts() -> set[str]:
    """Hostnames this server answers to: this machine's own names, plus SECT_ACADEMY_HOSTS
    (comma-separated) for a LAN name or address you choose to serve on."""
    extra = {h.strip().lower() for h in os.getenv("SECT_ACADEMY_HOSTS", "").split(",") if h.strip()}
    bind = os.getenv("SECT_ACADEMY_HOST", "127.0.0.1").lower()
    return {"localhost", "127.0.0.1", "::1", "testserver", bind} | extra


API = [Depends(guard)]


@app.middleware("http")
async def no_surprises(request: Request, call_next):
    """Same-origin only, and never let a browser cache API answers."""
    # A page on another site can point its own hostname at 127.0.0.1 (DNS rebinding) and then read
    # the API as "same origin". It cannot fake the Host header, so only known names are answered.
    host_only = request.headers.get("host", "").rsplit(":", 1)[0].strip("[]").lower()
    if host_only not in _allowed_hosts():
        return JSONResponse({"detail": "unknown host"}, status_code=421)
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        # Another web page must never be able to change (or wipe) your progress.
        origin = request.headers.get("origin", "")
        site = request.headers.get("sec-fetch-site", "")
        host = request.headers.get("host", "")
        foreign = bool(origin) and origin.split("://", 1)[-1] != host
        if foreign or site in ("cross-site", "same-site"):
            return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                               "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                                               "form-action 'self'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------------------
# the app shell (one page; the client routes on the path)
# ---------------------------------------------------------------------------
def _file(name: str, media: str | None = None) -> FileResponse:
    return FileResponse(STATIC / name, media_type=media, headers={"Cache-Control": "no-cache"})


@app.get("/")
@app.get("/study")
@app.get("/read")
@app.get("/library")
@app.get("/trials")
@app.get("/progress")
def page():
    return _file("index.html")


@app.get("/academy.js")
def js():
    return _file("academy.js", "text/javascript")


@app.get("/sect.js")
def sect_js():
    return _file("sect.js", "text/javascript")


@app.get("/reader.js")
def reader_js():
    return _file("reader.js", "text/javascript")


@app.get("/pictures.js")
def pictures_js():
    return _file("pictures.js", "text/javascript")


# pdf.js (Apache-2.0, static/vendor/pdfjs/LICENSE) pulls the text out of an imported PDF in the browser.
VENDOR = {"pdf.min.js", "pdf.worker.min.js"}


@app.get("/vendor/pdfjs/{name}")
def vendor(name: str):
    if name not in VENDOR:                    # a fixed list, like the art
        raise HTTPException(404, "no such file")
    return FileResponse(STATIC / "vendor" / "pdfjs" / name, media_type="text/javascript",
                        headers={"Cache-Control": "public, max-age=604800"})


@app.get("/handwriting.js")
def handwriting_js():
    return _file("handwriting.js", "text/javascript")


@app.get("/art.js")
def art_js():
    return _file("art.js", "text/javascript")


@app.get("/academy.css")
def css():
    return _file("academy.css", "text/css")


@app.get("/sw.js")
def sw():
    return _file("sw.js", "text/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return _file("manifest.webmanifest", "application/manifest+json")


@app.get("/icon.svg")
def icon():
    return _file("icon.svg", "image/svg+xml")


ART = {f.name for f in (STATIC / "art").glob("*.webp")}


@app.get("/art/{name}")
def art(name: str):
    if name not in ART:                       # a fixed list: nothing outside static/art can be reached
        raise HTTPException(404, "no such picture")
    return FileResponse(STATIC / "art" / name, media_type="image/webp", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/healthz")
def healthz():
    return {"status": "ok", "courses": len(packs.load_all())}


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class SetupIn(BaseModel):
    name: str = ""
    master: str = ""
    courses: list[str] = []
    storyteller: str = "balanced"


class EnrollIn(BaseModel):
    course: str
    on: bool = True


class SettingsIn(BaseModel):
    new_per_day: int | None = None
    session_size: int | None = None
    retention: float | None = None
    tz_offset_min: int | None = None
    audio: bool | None = None
    handwriting: bool | None = None


class SessionIn(BaseModel):
    course: str = ""
    size: int = 0
    practice: bool = False
    kind: str = ""


class DrillIn(BaseModel):
    kind: str = ""
    drill: str = ""
    n: int = 0
    answer: str = ""
    opts: dict = {}


class AnswerIn(BaseModel):
    session: str
    item: str
    mode: str
    answer: str | list[str] = ""
    retry: bool = False
    claim: bool = False


class LineIn(BaseModel):
    item: str
    index: int
    answer: str = ""


class FinishIn(BaseModel):
    session: str
    secs: int = 0


class LearnMoreIn(BaseModel):
    course: str
    n: int = 5


class TrialStartIn(BaseModel):
    course: str
    full: bool = False


class TrialSubmitIn(BaseModel):
    trial: str
    answers: list[str | list[str] | None] = []


class IdIn(BaseModel):
    trial: str = ""
    course: str = ""
    placement: str = ""
    unit: int = -1
    answers: list[str | list[str] | None] = []


class SectIn(BaseModel):
    hours: int = 0
    pawn: str = ""
    job: str = ""
    level: int = 0
    room: str = ""
    index: int = 0
    tech: str = ""
    option: str = ""
    storyteller: str = ""
    sect: str = ""
    manual: str = ""
    place: str = ""
    artifact: str = ""
    other: str = ""
    precept: str = ""
    path: str = ""
    recipe: str = ""
    colour: str = ""
    pawns: list[str] = []
    stance: str = ""
    node: str = ""
    name: str = ""
    count: int = 0
    motto: str = ""
    on: bool = False


def _clip(a):
    if isinstance(a, list):
        return [str(x)[:400] for x in a[:12]]
    return a[:400] if isinstance(a, str) else a


# ---------------------------------------------------------------------------
# study
# ---------------------------------------------------------------------------
@app.get("/api/overview", dependencies=API)
def overview(tz: int | None = Query(default=None)):
    if tz is not None and -840 <= tz <= 840 and state.get()["settings"].get("tz_offset_min") != tz:
        engine.set_settings({"tz_offset_min": tz})
    return engine.overview()


@app.post("/api/setup", dependencies=API)
def setup(body: SetupIn):
    for c in body.courses:
        engine.enroll(c, True)
    with state.LOCK:
        st = state.get()
        colony.setup(st, body.name, body.master, time.time())
        if body.storyteller in colony.STORYTELLERS:
            colony.set_storyteller(st, body.storyteller, time.time())
        state.save()
    return engine.overview()


@app.post("/api/enroll", dependencies=API)
def enroll(body: EnrollIn):
    res = engine.enroll(body.course, body.on)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


@app.put("/api/settings", dependencies=API)
def settings(body: SettingsIn):
    return engine.set_settings({k: v for k, v in body.model_dump().items() if v is not None})


@app.get("/api/unit", dependencies=API)
def unit(course: str, unit: str):
    res = engine.unit_detail(course, unit)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


@app.post("/api/session", dependencies=API)
def session(body: SessionIn):
    if body.kind:
        return engine.build_special(body.kind, body.course or None)
    if body.practice:
        return engine.build_practice(body.course or None)
    return engine.build_session(body.course or None, body.size or None)


@app.post("/api/answer", dependencies=API)
def answer(body: AnswerIn):
    res = engine.answer(body.item, body.mode, _clip(body.answer), retry=body.retry, claim=body.claim, session=body.session)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


class PicturePinIn(BaseModel):
    item: str
    answer: str = ""


class PictureAnswerIn(BaseModel):
    session: str
    pins: list[PicturePinIn] = []
    retry: bool = False


@app.post("/api/answer/picture", dependencies=API)
def answer_picture(body: PictureAnswerIn):
    """A whole drag-the-words picture at once; each pin is graded and scheduled on its own."""
    res = engine.answer_picture([{"item": p.item[:80], "answer": p.answer[:200]} for p in body.pins[:17]],
                                session=body.session, retry=body.retry)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


class WriteIn(BaseModel):
    session: str
    item: str
    chars: list = []           # per character: the strokes drawn, in order, each [x0, y0, x1, y1, ...] in the unit box
    assisted: bool = False     # the outline or the demo was shown
    retry: bool = False


@app.post("/api/answer/write", dependencies=API)
def answer_write(body: WriteIn):
    """A glyph written by hand: every stroke drawn is replayed and matched here (hand.py), never on the page."""
    res = engine.answer(body.item[:80], "glyph_write", {"chars": body.chars[:hand.MAX_CHARS], "assisted": body.assisted},
                        retry=body.retry, session=body.session)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@app.post("/api/line", dependencies=API)
def line(body: LineIn):
    """Check one of your lines in a dialogue as you go (nothing is scheduled)."""
    it = packs.item_index().get(body.item)
    if not it or it["type"] != "dialogue":
        raise HTTPException(404, "unknown dialogue")
    res = engine.check_line(it, body.index, body.answer[:400])
    if res.get("error"):
        raise HTTPException(400, res["error"])
    ln = it["lines"][body.index]
    return {**res, "l2": ln["l2"], "l1": ln["l1"], "rom": ln.get("rom", "")}


@app.post("/api/session/finish", dependencies=API)
def finish(body: FinishIn):
    return engine.finish_session(secs=body.secs, session=body.session)


@app.post("/api/learn-more", dependencies=API)
def learn_more(body: LearnMoreIn):
    return engine.learn_more(body.course, body.n)


@app.post("/api/placement/start", dependencies=API)
def placement_start(body: IdIn):
    return engine.placement_start(body.course)


@app.post("/api/placement/answer", dependencies=API)
def placement_answer(body: IdIn):
    return engine.placement_answer(body.placement, [_clip(a) for a in body.answers[:12]], unit=body.unit)


@app.get("/api/trial", dependencies=API)
def trial_info(course: str):
    return engine.trial_info(course)


@app.post("/api/trial/start", dependencies=API)
def trial_start(body: TrialStartIn):
    return engine.start_trial(body.course, full=body.full)


@app.post("/api/trial/submit", dependencies=API)
def trial_submit(body: TrialSubmitIn):
    return engine.submit_trial(body.trial, [_clip(a) for a in body.answers[:200]])


@app.post("/api/trial/abandon", dependencies=API)
def trial_abandon(body: IdIn):
    return engine.abandon_trial(body.trial)


@app.get("/api/mistakes", dependencies=API)
def mistakes(course: str = ""):
    return engine.mistakes(course or None)


@app.post("/api/drill", dependencies=API)
def drill_start(body: DrillIn):
    return drills.start(body.kind, opts=body.opts)


@app.get("/api/drill/options", dependencies=API)
def drill_options(lang: str = ""):
    return drills.options(lang)


@app.post("/api/drill/answer", dependencies=API)
def drill_answer(body: DrillIn):
    res = drills.answer(body.drill, body.n, body.answer[:120])
    if res.get("finished"):
        with state.LOCK:
            d = state.get().setdefault("drills", {}).setdefault(res["kind"], {"best": 0, "runs": 0})
            if not res.get("counted"):
                d["runs"] += 1
                d["best"] = max(d["best"], round(100 * res["score"] / res["total"]))
            state.save()
    return res


@app.get("/api/stats", dependencies=API)
def stats(days: int = Query(default=60, ge=7, le=365)):
    return engine.stats(days)


@app.get("/api/export", dependencies=API)
def export():
    return state.export()


@app.post("/api/import", dependencies=API)
async def import_(request: Request):
    if int(request.headers.get("content-length") or 0) > state.MAX_IMPORT_BYTES:
        raise HTTPException(413, "backup file is too large")
    raw = await request.body()
    if len(raw) > state.MAX_IMPORT_BYTES:
        raise HTTPException(413, "backup file is too large")
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(400, "not a Sect Academy backup")     # a plain form post from another page lands here
    try:
        body = json.loads(raw)
    except Exception:
        raise HTTPException(400, "not a Sect Academy backup") from None
    # The blob is coerced to safe shapes and test-driven before it replaces anything.
    if not state.import_(body, probe=engine.overview):
        raise HTTPException(400, "not a Sect Academy backup")
    return {"ok": True}


# ---------------------------------------------------------------------------
# the reader: dictionary, your words, books
# ---------------------------------------------------------------------------
class EntryIn(BaseModel):
    lang: str = "es"
    word: str = ""
    meaning: str = ""
    form: str = ""
    ctx: str = ""


class SegmentIn(BaseModel):
    lang: str = "es"
    text: str = ""


class PosIn(BaseModel):
    pos: int = 0


LangQ = Query(default="es", max_length=8)


@app.get("/api/dict/langs", dependencies=API)
def dict_langs():
    return reader.languages()


@app.get("/api/dict", dependencies=API)
def dict_lookup(w: str = Query(default="", max_length=200), lang: str = LangQ,
                pre: str = Query(default="", max_length=40), post: str = Query(default="", max_length=40)):
    """``pre``/``post``: a few characters of the text around a tapped word (Chinese, Japanese: a longer word it sits in)."""
    return reader.lookup(lang, w, around=(pre, post))


@app.get("/api/dict/search", dependencies=API)
def dict_search(q: str = Query(default="", max_length=200), dir: str = "from", lang: str = LangQ):
    return reader.search(lang, q, "en" if dir == "en" else "from")


@app.post("/api/dict/segment", dependencies=API)
def dict_segment(body: SegmentIn):
    """A page cut into tokens with their lookup keys (Spanish: split on spaces; CJK will need the dictionary)."""
    if len(body.text) > reader.MAX_SEGMENT:
        raise HTTPException(413, "Send one page at a time.")
    return reader.segment(body.lang[:8], body.text)


@app.post("/api/dict/entry", dependencies=API)
def dict_add(body: EntryIn):
    res = reader.add_entry(body.lang[:8], body.word[:200], body.meaning[:1000])
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@app.delete("/api/dict/entry", dependencies=API)
def dict_delete(w: str = Query(default="", max_length=200), lang: str = LangQ):
    return reader.delete_entry(lang, w)


@app.get("/api/words", dependencies=API)
def words(lang: str = LangQ):
    return reader.list_words(lang)


@app.post("/api/words", dependencies=API)
def word_save(body: EntryIn):
    res = reader.save_word(body.lang[:8], body.word[:200], body.meaning[:1000], body.form[:200], body.ctx[:1000])
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@app.delete("/api/words", dependencies=API)
def word_delete(w: str = Query(default="", max_length=200), lang: str = LangQ):
    return reader.delete_word(lang, w)


@app.get("/api/books", dependencies=API)
def books():
    return reader.list_books()


@app.post("/api/books", dependencies=API)
async def book_add(request: Request):
    # Books are large: refuse an oversized body before reading it, and only ever take JSON
    # (a plain form post from another page cannot be JSON, and is refused here as well as by the middleware).
    if int(request.headers.get("content-length") or 0) > reader.BOOK_POST_MAX_BYTES:
        raise HTTPException(413, "That book is too large.")
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(400, "Books are sent as JSON.")
    raw = await request.body()
    if len(raw) > reader.BOOK_POST_MAX_BYTES:
        raise HTTPException(413, "That book is too large.")
    try:
        body = json.loads(raw)
    except Exception:
        raise HTTPException(400, "Books are sent as JSON.") from None
    if not isinstance(body, dict) or not isinstance(body.get("text"), str):
        raise HTTPException(400, "A book needs its text.")
    res = reader.add_book(body.get("title"), body["text"], body.get("lang") if isinstance(body.get("lang"), str) else "es")
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@app.get("/api/books/{bid}", dependencies=API)
def book_get(bid: str):
    res = reader.get_book(bid)
    if not res:
        raise HTTPException(404, "unknown book")
    return res


@app.put("/api/books/{bid}/pos", dependencies=API)
def book_pos(bid: str, body: PosIn):
    res = reader.set_position(bid, body.pos)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


class TitleIn(BaseModel):
    title: str = ""


@app.put("/api/books/{bid}/title", dependencies=API)
def book_title(bid: str, body: TitleIn):
    res = reader.rename_book(bid, body.title[:1000])
    if not res["ok"]:
        raise HTTPException(404 if res["error"] == "unknown book" else 400, res["error"])
    return res


@app.delete("/api/books/{bid}", dependencies=API)
def book_delete(bid: str):
    res = reader.delete_book(bid)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


# ---------------------------------------------------------------------------
# the sect
# ---------------------------------------------------------------------------
_tick = {"t": 0.0, "credit": float(colony.MAX_TICK), "saved": 0.0}


@app.post("/api/sect/{action}", dependencies=API)
def sect(action: str, body: SectIn):
    now = time.time()
    with state.LOCK:
        st = state.get()
        if action == "tick":
            # The page asks for hours as real time passes; never run faster than 3 sim hours a second,
            # however many tabs are asking. Zero hours is a heartbeat: "I am here, and paused".
            _tick["credit"] = min(float(colony.MAX_TICK), _tick["credit"] + max(0.0, now - _tick["t"]) * 3.0)
            _tick["t"] = now
            grant = max(0, min(int(body.hours), int(_tick["credit"])))
            _tick["credit"] -= grant
            res = colony.advance(st, grant, now)
        elif action == "priority":
            res = colony.set_priority(st, body.pawn, body.job, body.level, now)
        elif action == "build":
            res = colony.queue_build(st, body.room, now)
        elif action == "cancel-build":
            res = colony.cancel_build(st, body.index, now)
        elif action == "research":
            res = colony.set_research(st, body.tech, now)
        elif action == "resolve":
            res = colony.resolve(st, body.option, now)
        elif action == "pill":
            res = colony.use_pill(st, body.pawn, now)
        elif action == "banish":
            res = colony.banish(st, body.pawn, now)
        elif action == "attempt":
            res = colony.attempt(st, body.pawn, now)
        elif action == "gift":
            res = colony.gift(st, body.sect, now)
        elif action == "burn":
            res = colony.burn_manual(st, body.manual, now)
        elif action == "apprentice":
            res = dao.apprentice(st, body.pawn, body.other, now)
        elif action == "companion":
            res = dao.companion(st, body.pawn, body.other, now)
        elif action == "face-demon":
            res = dao.face_demon(st, body.pawn, now)
        elif action == "precept":
            res = dao.set_precept(st, body.precept, body.on, now)
        elif action == "path":
            res = dao.set_path(st, body.pawn, body.path, now)
        elif action == "retreat":
            res = dao.retreat(st, body.pawn, now)
        elif action == "recipe":
            res = dao.set_recipe(st, body.recipe, now)
        elif action == "marrow":
            res = dao.take_marrow(st, body.pawn, now)
        elif action == "ally":
            res = dao.ally(st, body.sect, now)
        elif action == "branch":
            res = dao.found_branch(st, body.pawn, now)
        elif action == "style":
            res = dao.set_style(st, body.colour, body.motto[:80], now)
        elif action == "forge":
            res = colony.forge(st, now)
        elif action == "equip":
            res = colony.equip(st, body.pawn, body.artifact, now)
        elif action == "direct":
            res = colony.set_direct(st, body.pawn, body.on, now)
        elif action == "deliver":
            res = colony.deliver(st, now)
        elif action == "expedition":
            res = colony.expedition(st, body.place, now, [str(x)[:16] for x in body.pawns[:3]], body.stance)
        elif action == "meridian":
            res = dao.road.open_node(st, body.pawn, body.node, now)
        elif action == "standing":
            res = dao.road.set_standing(st, body.count, body.on, now)
        elif action == "preset-save":
            res = dao.road.preset_save(st, body.name, now)
        elif action == "preset-apply":
            res = dao.road.preset_apply(st, body.name, now)
        elif action == "scene-seen":
            res = colony.scene_seen(st, body.index, now)
        elif action == "guide-skip":
            res = colony.skip_guide(st, now)
        elif action == "storyteller":
            res = colony.set_storyteller(st, body.storyteller, now)
        elif action == "seclusion":
            res = colony.set_seclusion(st, body.on, now)
        else:
            raise HTTPException(404, "unknown action")
        view = colony.view(st, now)
        # Ticks arrive every second or so; writing the whole file each time would wear the disk for nothing.
        if action != "tick" or now - _tick["saved"] >= 5.0:
            _tick["saved"] = now
            state.save()
    return JSONResponse({**res, "sect": view})


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=os.getenv("SECT_ACADEMY_HOST", "127.0.0.1"), port=int(os.getenv("SECT_ACADEMY_PORT", "8200")),
                log_level="warning")
