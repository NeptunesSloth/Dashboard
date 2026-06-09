"""Reliability / SLO API routes (extracted from app.py): uptime SLOs,
maintenance windows / alert silencing, and error budgets (deploy-freeze).

Mounted by app.py via include_router.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import errorbudget, maintenance, slo
from ..deps import SAFE_TARGET as _SAFE_TARGET
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


# ---- SLO / uptime ----
@router.get("/api/slo")
def slo_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return slo.snapshot(hours if hours > 0 else None)


# ---- Maintenance windows / alert silencing ----
@router.get("/api/maintenance")
def maintenance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return maintenance.snapshot()


class SilenceIn(BaseModel):
    target: str
    minutes: float = 60.0
    reason: str = ""


@router.post("/api/maintenance/silence")
def maintenance_silence(body: SilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target):
        raise HTTPException(400, "invalid target; use '*', 'device:*', or 'device:project'")
    if body.minutes > 60 * 24 * 30:
        raise HTTPException(400, "minutes too large (max 30 days)")
    return maintenance.silence(target, body.minutes, body.reason)


class UnsilenceIn(BaseModel):
    target: str


@router.post("/api/maintenance/unsilence")
def maintenance_unsilence(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"unsilenced": maintenance.unsilence((body.target or "").strip())}


# ---- Error budgets & deploy-freeze (Karmic Debt / Heavenly Decree) ----
@router.get("/api/errorbudget")
def errorbudget_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return errorbudget.snapshot(hours if hours > 0 else None)
