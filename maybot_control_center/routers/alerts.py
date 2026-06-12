"""Alerting & incident routes (extracted from app.py): dependency-aware alerting
(Meridian Map), synthetic uptime probes (Warding Talismans), incident ownership
(Sworn Oath), escalation policy, alert ack/snooze, inbound alert ingestion,
summary reports, and notification channels.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import acks, escalation, inbound, meridians, notify, oaths, reports, talismans
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import SAFE_TARGET as _SAFE_TARGET
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


# ---- Dependency-aware alerting (Meridian Map) ----
@router.get("/api/meridians")
def meridians_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return meridians.graph()


# ---- Synthetic uptime probes (Warding Talismans) ----
@router.get("/api/talismans")
def talismans_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return talismans.snapshot()


# ---- Incident acknowledgement & ownership (Sworn Oath) ----
@router.get("/api/oaths")
def oaths_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return oaths.snapshot()


class OathIn(BaseModel):
    target: str
    who: str = "operator"
    note: str = ""


@router.post("/api/oaths/claim")
def oaths_claim(body: OathIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target) or target == "*" or target.endswith(":*"):
        raise HTTPException(400, "claim a specific 'device:project'")
    who = (body.who or "operator").strip()
    if not _SAFE_NAME.match(who):
        raise HTTPException(400, "invalid claimant name")
    return oaths.claim(target, who, body.note)


class UnsilenceIn(BaseModel):
    target: str


@router.post("/api/oaths/release")
def oaths_release(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"released": oaths.release((body.target or "").strip())}


# ---- Escalation policy (Chain of Command) ----
@router.get("/api/escalation")
def escalation_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return escalation.snapshot()


# ---- Alert acknowledgement & snooze ----
@router.get("/api/alerts")
def alerts_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return acks.snapshot()


class AckIn(BaseModel):
    target: str
    who: str = "operator"
    minutes: float | None = None
    reason: str = ""


@router.post("/api/alerts/ack")
def alerts_ack(body: AckIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target) or target == "*" or target.endswith(":*"):
        raise HTTPException(400, "acknowledge a specific 'device:project'")
    who = (body.who or "operator").strip()
    if not _SAFE_NAME.match(who):
        raise HTTPException(400, "invalid actor name")
    if body.minutes is not None and (body.minutes < 0 or body.minutes > 60 * 24 * 30):
        raise HTTPException(400, "minutes out of range (0..43200)")
    return acks.ack(target, who, body.minutes, body.reason)


@router.post("/api/alerts/resolve")
def alerts_resolve(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"resolved": acks.resolve((body.target or "").strip())}


# ---- Summary reports (Daily Proclamation) ----
@router.get("/api/reports/daily")
def reports_daily(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    window = hours if hours > 0 else None
    report = reports.build(window)
    return {"report": report, "text": reports.render_text(report)}


@router.post("/api/reports/send")
def reports_send(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return reports.deliver()


# ---- Inbound alert ingestion (external systems push incidents in) ----
def _check_ingest(x_control_token: str, x_ingest_token: str):
    if inbound.INGEST_TOKEN and x_ingest_token and secrets.compare_digest(x_ingest_token, inbound.INGEST_TOKEN):
        return
    _check_operator(x_control_token)


class InboundIn(BaseModel):
    title: str
    source: str = "external"
    severity: str = "warning"
    message: str = ""
    project: str = ""
    device: str = ""


@router.post("/api/ingest/alert")
def ingest_alert(body: InboundIn, x_control_token: str = Header(default=""),
                 x_ingest_token: str = Header(default="")):
    _check_ingest(x_control_token, x_ingest_token)
    if not (body.title or "").strip():
        raise HTTPException(400, "title required")
    return inbound.ingest(body.source, body.severity, body.title, body.message, body.project, body.device)


@router.get("/api/inbound")
def inbound_feed(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return inbound.snapshot()


# ---- Notification channels ----
@router.get("/api/notifications")
def notifications_view(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"channels": notify.channels(), "recent": notify.recent(), **notify.snooze_status()}


class SnoozeIn(BaseModel):
    minutes: float = 60.0


@router.post("/api/notifications/snooze")
def notifications_snooze(body: SnoozeIn, x_control_token: str = Header(default="")):
    """Mute notification delivery for a while (events are still recorded)."""
    _check_operator(x_control_token)
    if body.minutes <= 0:
        return notify.unsnooze()
    return notify.snooze(body.minutes)
