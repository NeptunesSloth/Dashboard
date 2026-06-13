"""Cyber-range infrastructure API — the dashboard's control panel for external
VM backends. Read endpoints need any role; lifecycle actions need operator.

This NEVER hosts or fakes a VM. With no provider configured every launch is
honestly rejected; the endpoints report real lifecycle/provider states. See
``orchestration.py`` and docs/CYBER_RANGE_ARCHITECTURE.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from .. import orchestration
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/range-infra/providers")
def providers(x_control_token: str = Header(default="")):
    """List VM backends and their honest health (none / proxmox / …)."""
    _check_token(x_control_token)
    return orchestration.list_providers()


@router.get("/api/range-infra/health")
def health(provider: str = Query(default=""), x_control_token: str = Header(default="")):
    """Health of the selected (or named) provider — not_configured by default."""
    _check_token(x_control_token)
    return orchestration.provider_health(provider or None)


@router.get("/api/range-infra/labs")
def labs(x_control_token: str = Header(default="")):
    """The lab catalog + whether infrastructure is actually live."""
    _check_token(x_control_token)
    return orchestration.list_labs()


@router.get("/api/range-infra/sessions")
def sessions(x_control_token: str = Header(default="")):
    """Active lab sessions (empty unless a real provider launched one)."""
    _check_token(x_control_token)
    return orchestration.list_sessions()


@router.get("/api/range-infra/session/{session_id}")
def session_status(session_id: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return orchestration.session_status(session_id)


class LaunchIn(BaseModel):
    lab_id: str
    provider: str | None = None


@router.post("/api/range-infra/launch")
def launch(body: LaunchIn, x_control_token: str = Header(default="")):
    """Launch a lab. Honestly rejected (no VM, no running session) until a real
    hypervisor provider is connected."""
    _check_operator(x_control_token)
    from .. import authz
    owner = authz.name_for(x_control_token) or "operator"
    return orchestration.launch_lab(body.lab_id, owner=owner, provider=body.provider)


class SessionIn(BaseModel):
    session_id: str


@router.post("/api/range-infra/stop")
def stop(body: SessionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return orchestration.stop_lab(body.session_id)


@router.post("/api/range-infra/reset")
def reset(body: SessionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return orchestration.reset_lab(body.session_id)


@router.post("/api/range-infra/destroy")
def destroy(body: SessionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return orchestration.destroy_lab(body.session_id)


@router.get("/api/range-infra/events")
def events(limit: int = Query(default=50), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"events": orchestration.events(limit)}
