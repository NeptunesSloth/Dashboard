"""Trading cockpit routes (extracted from app.py): live market data, broker
account state, risk status + kill switch, per-bot trading controls, ML signals,
the advisor, PnL history, and the command snapshot.

All read endpoints need any valid role; mutating ones need operator.
Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import advisor, authz, botcontrol, broker, command, notify, pnl_history, quotes, risk, signals
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/command")
def command_snapshot(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return command.snapshot()


@router.get("/api/market/quotes")
def market_quotes(symbols: str = Query(default=""), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:50]
    return {"quotes": quotes.get_quotes(syms), "live": quotes.live()}


@router.get("/api/market/account")
def market_account(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": broker.enabled(), "account": broker.account(), "fills": broker.recent_fills()}


@router.get("/api/risk")
def risk_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"status": risk.status(), "evaluation": command.snapshot().get("risk", {})}


class KillIn(BaseModel):
    on: bool = True


@router.post("/api/risk/kill")
def risk_kill(body: KillIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    actor = authz.name_for(x_control_token) or "operator"
    res = risk.kill_switch(bool(body.on), actor)
    try:
        notify.send("Kill-switch " + ("ENGAGED" if body.on else "released"),
                    f"by {actor}", level=("warn" if body.on else "info"), kind="risk")
    except Exception:
        pass
    return res


class BotControlIn(BaseModel):
    bot: str
    action: str


@router.post("/api/bots/control")
def bots_control(body: BotControlIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    bot = (body.bot or "").strip()
    if not bot or len(bot) > 64 or not re.match(r'^[\w \-\.]+$', bot):
        raise HTTPException(400, "invalid bot name")
    actor = authz.name_for(x_control_token) or "operator"
    res = botcontrol.set_state(bot, (body.action or "").strip().lower(), actor)
    if res.get("error"):
        raise HTTPException(400, res["error"])
    return res


@router.post("/api/bots/flatten")
def bots_flatten(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    actor = authz.name_for(x_control_token) or "operator"
    try:
        notify.send("Flatten-all requested", f"by {actor}", level="warn", kind="risk")
    except Exception:
        pass
    return botcontrol.flatten_all(actor)


@router.get("/api/signals")
def signals_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    snap = command.snapshot()
    syms = [p.get("ticker") for p in snap.get("positions", []) if p.get("ticker")]
    syms = syms or [o.get("ticker") for o in snap.get("opportunities", []) if o.get("ticker")]
    return {"enabled": signals.enabled(), "model": signals.model_info(), "scores": signals.score_symbols(syms)}


@router.get("/api/advisor")
def advisor_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return advisor.summary(command.snapshot())


@router.get("/api/pnl")
def pnl_view(metric: str = Query(default="total"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"metric": metric, "series": pnl_history.series(metric), "summary": pnl_history.summary()}
