"""Sect Academy API + pages: the offline-first learning app and its sect game.

Reads need any valid role; anything that changes study progress or the sect
needs the operator role (open mode grants it, as everywhere else).
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..academy import engine, game, packs, state
from ..deps import check_operator, check_token, role

router = APIRouter()
_DIR = "maybot_control_center/static/academy"


# ---- pages (one app shell; the client routes on the path) ----
@router.get("/")
@router.get("/study")
@router.get("/library")
@router.get("/trials")
@router.get("/progress")
def academy_page():
    return FileResponse(f"{_DIR}/index.html", headers={"Cache-Control": "no-cache"})


@router.get("/academy.js")
def academy_js():
    return FileResponse(f"{_DIR}/academy.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/art.js")
def academy_art_js():
    return FileResponse(f"{_DIR}/art.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/academy.css")
def academy_css():
    return FileResponse(f"{_DIR}/academy.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


# ---- models ----
class SetupIn(BaseModel):
    name: str = ""
    master: str = ""
    courses: list[str] = []


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
    answer: str = ""
    retry: bool = False
    claim: bool = False


class FinishIn(BaseModel):
    session: str
    secs: int = 0


class LearnMoreIn(BaseModel):
    course: str
    n: int = 5


class TrialStartIn(BaseModel):
    course: str


class TrialSubmitIn(BaseModel):
    trial: str
    answers: list[str | None] = []


class TrialAbandonIn(BaseModel):
    trial: str


class GameIn(BaseModel):
    room: str = ""
    disciple: str = ""
    candidate: str = ""
    kind: str = ""
    on: bool = False


def _game(fn, *args):
    """Run a game action under the academy lock, then persist."""
    with state.LOCK:
        st = state.get()
        out = fn(st, *args, time.time())
        state.save()
    return out


# ---- study ----
@router.get("/api/academy/overview")
def academy_overview(tz: int | None = Query(default=None), x_control_token: str = Header(default="")):
    # The learner's own browser reports its UTC offset so "today" is their day.
    # That changes state, so only an operator's request may set it.
    if (role(x_control_token) == "operator" and tz is not None and -840 <= tz <= 840
            and state.get()["settings"].get("tz_offset_min") != tz):
        engine.set_settings({"tz_offset_min": tz})
    return engine.overview()


@router.post("/api/academy/setup")
def academy_setup(body: SetupIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    for c in body.courses:
        engine.enroll(c, True)
    _game(game.setup, body.name, body.master)
    return engine.overview()


@router.post("/api/academy/enroll")
def academy_enroll(body: EnrollIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    res = engine.enroll(body.course, body.on)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


@router.put("/api/academy/settings")
def academy_settings(body: SettingsIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.set_settings({k: v for k, v in body.model_dump().items() if v is not None})


@router.get("/api/academy/unit")
def academy_unit(course: str, unit: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    res = engine.unit_detail(course, unit)
    if not res["ok"]:
        raise HTTPException(404, res["error"])
    return res


@router.post("/api/academy/session")
def academy_session(body: SessionIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    if body.practice:
        return engine.build_practice(body.course or None)
    return engine.build_session(body.course or None, body.size or None)


@router.post("/api/academy/answer")
def academy_answer(body: AnswerIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    res = engine.answer(body.item, body.mode, body.answer[:400], retry=body.retry,
                        claim=body.claim, session=body.session)
    if not res["ok"]:
        raise HTTPException(400, res["error"])
    return res


@router.post("/api/academy/session/finish")
def academy_finish(body: FinishIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.finish_session(secs=body.secs, session=body.session)


@router.post("/api/academy/learn-more")
def academy_learn_more(body: LearnMoreIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.learn_more(body.course, body.n)


@router.get("/api/academy/trial")
def academy_trial_info(course: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    return engine.trial_info(course)


@router.post("/api/academy/trial/start")
def academy_trial_start(body: TrialStartIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.start_trial(body.course)


@router.post("/api/academy/trial/submit")
def academy_trial_submit(body: TrialSubmitIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.submit_trial(body.trial, body.answers)


@router.post("/api/academy/trial/abandon")
def academy_trial_abandon(body: TrialAbandonIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return engine.abandon_trial(body.trial)


@router.get("/api/academy/stats")
def academy_stats(days: int = Query(default=60, ge=7, le=365), x_control_token: str = Header(default="")):
    check_token(x_control_token)
    return engine.stats(days)


@router.get("/api/academy/export")
def academy_export(x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    return state.export()


@router.post("/api/academy/import")
async def academy_import(request: Request, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    raw = await request.body()
    if len(raw) > state.MAX_IMPORT_BYTES:
        raise HTTPException(413, "backup file is too large")
    try:
        body = json.loads(raw)
    except Exception:
        raise HTTPException(400, "not an academy export") from None
    # The blob is coerced to safe shapes and test-driven before it replaces anything.
    if not state.import_(body, probe=engine.overview):
        raise HTTPException(400, "not an academy export")
    return {"ok": True}


# ---- the sect ----
@router.post("/api/academy/game/{action}")
def academy_game(action: str, body: GameIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    if action == "collect":
        res = _game(game.collect)
    elif action == "upgrade":
        res = _game(game.upgrade, body.room)
    elif action == "recruit":
        res = _game(game.recruit_offer)
    elif action == "recruit-pick":
        res = _game(game.recruit_pick, body.candidate)
    elif action == "assign":
        res = _game(game.assign, body.disciple, body.room or None)
    elif action == "dismiss":
        res = _game(game.dismiss, body.disciple)
    elif action == "dispatch":
        res = _game(game.dispatch, body.disciple, body.kind)
    elif action == "pill":
        res = _game(game.brew_pill)
    elif action == "seclusion":
        res = _game(game.set_seclusion, body.on)
    else:
        raise HTTPException(404, "unknown action")
    return {**res, "game": engine.overview()["game"]}


@router.get("/api/academy/packs")
def academy_packs(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    return [{"id": p["id"], "title": p["title"], "kind": p["kind"], "units": len(p["units"]),
             "items": sum(len(u["items"]) for u in p["units"])} for p in packs.load_all().values()]
