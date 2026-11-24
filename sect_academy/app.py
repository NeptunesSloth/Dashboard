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

from . import colony, engine, packs, state

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Sect Academy", docs_url=None, redoc_url=None, openapi_url=None)


def guard(x_academy_token: str = Header(default="")) -> None:
    want = os.getenv("SECT_ACADEMY_TOKEN", "")
    if want and not secrets.compare_digest((x_academy_token or "").encode("utf-8", "replace"), want.encode()):
        raise HTTPException(401, "token required")


API = [Depends(guard)]


@app.middleware("http")
async def no_surprises(request: Request, call_next):
    """Same-origin only, and never let a browser cache API answers."""
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


class SessionIn(BaseModel):
    course: str = ""
    size: int = 0
    practice: bool = False


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
    if body.practice:
        return engine.build_practice(body.course or None)
    return engine.build_session(body.course or None, body.size or None)


@app.post("/api/answer", dependencies=API)
def answer(body: AnswerIn):
    res = engine.answer(body.item, body.mode, _clip(body.answer), retry=body.retry, claim=body.claim, session=body.session)
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
    return {**res, "l2": ln["l2"], "l1": ln["l1"]}


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
        elif action == "deliver":
            res = colony.deliver(st, now)
        elif action == "expedition":
            res = colony.expedition(st, body.place, now)
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
