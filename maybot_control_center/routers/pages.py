"""UI pages, static assets & public surface (extracted from app.py): the themed
command pages and legacy console, PWA files, the Sect Map art index, non-secret
UI meta, health/readiness probes, Prometheus metrics, and the opt-in public
status page.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from .. import aggregator, authz, autopilot, obs, status_page
from .. import metrics as metrics_mod
from ..config import CONTROL_CENTER_TOKEN
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/meta")
def meta():
    """Non-secret UI hints: whether auth is configured (for the setup warning),
    and which optional subsystems are on."""
    auth_configured = bool(authz.load_users()) or bool(CONTROL_CENTER_TOKEN)
    return {"auth_configured": auth_configured, "autopilot_enabled": autopilot.ENABLED,
            "public_status": status_page.enabled()}


# ---- Health / readiness probes (unauthenticated, no secrets) ----
@router.get("/healthz")
def healthz():
    """Liveness: the process is up and serving."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(strict: bool = Query(default=False)):
    """Readiness: the dashboard can serve. Reports the last poll's device health;
    with ``?strict=1`` returns 503 when any configured device is offline."""
    summary = aggregator.last_summary()
    offline = summary.get("offline_devices", 0)
    online = summary.get("online_devices", 0)
    polled = bool(summary)
    degraded = polled and offline > 0
    body = {"status": "degraded" if degraded else "ok", "ready": True, "polled": polled,
            "online_devices": online, "offline_devices": offline}
    if strict and degraded:
        return JSONResponse(body, status_code=503)
    return body


@router.get("/metrics")
def prometheus_metrics():
    # Aggregate stats only (no secrets); standard unauthenticated Prometheus scrape target.
    return PlainTextResponse(metrics_mod.render(), media_type="text/plain; version=0.0.4")


@router.get("/metrics/obs")
def prometheus_metrics_lite(x_control_token: str = Header(default="")):
    # Cheap, never-fail liveness/throughput exposition (no agent polling). Public by
    # default (internal scrape target); gated only when MAYBOT_METRICS_PUBLIC is off,
    # in which case a valid control token (or MAYBOT_METRICS_TOKEN) is required.
    if not obs.metrics_public():
        tok = obs.metrics_token()
        if not (tok and x_control_token == tok):
            _check_token(x_control_token)
    return PlainTextResponse(obs.render_prometheus(), media_type=obs.CONTENT_TYPE)


# ---- Public status page (Sect Proclamation) — opt-in, unauthenticated ----
@router.get("/status")
def public_status_page():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return PlainTextResponse(status_page.render_html(), media_type="text/html")


@router.get("/api/status/public")
def public_status_json():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return status_page.public_data()


def _sect_pngs(sub: str) -> list:
    d = f"maybot_control_center/static/assets/sect/{sub}"
    return [fn[:-4] for fn in sorted(os.listdir(d)) if fn.lower().endswith(".png")] if os.path.isdir(d) else []


@router.get("/api/sect/disciples")
def sect_disciples():
    """List authored Realm Map art basenames: character sprites (disciples/,
    e.g. 'trader_walk_6f'), effect strips (fx/, e.g. 'fx_breakthrough_8f'), and
    inspect portraits (portraits/, e.g. 'leader'). The Realm Map loads only what
    exists and falls back to procedural drawing otherwise — so no 404 probing."""
    return {"sprites": _sect_pngs("disciples"), "fx": _sect_pngs("fx"), "portraits": _sect_pngs("portraits")}


_CMD = "maybot_control_center/static/command"


@router.get("/")
def home():
    return FileResponse(f"{_CMD}/index.html")


@router.get("/command.js")
def command_js():
    return FileResponse(f"{_CMD}/command.js", media_type="text/javascript")


@router.get("/command.css")
def command_css():
    return FileResponse(f"{_CMD}/command.css", media_type="text/css")


@router.get("/vendor/three.module.js")
def three_js():
    return FileResponse(f"{_CMD}/vendor/three.module.js", media_type="text/javascript")


@router.get("/vendor/OrbitControls.js")
def orbit_controls_js():
    return FileResponse(f"{_CMD}/vendor/OrbitControls.js", media_type="text/javascript")


@router.get("/lib.js")
def command_lib_js():
    return FileResponse(f"{_CMD}/lib.js", media_type="text/javascript")


@router.get("/login")
def login_page():
    return FileResponse(f"{_CMD}/login.html")


@router.get("/login.js")
def login_js():
    return FileResponse(f"{_CMD}/login.js", media_type="text/javascript")


@router.get("/chamber")
def chamber():
    return FileResponse(f"{_CMD}/chamber.html")


@router.get("/chamber.js")
def chamber_js():
    return FileResponse(f"{_CMD}/chamber.js", media_type="text/javascript")


@router.get("/trade")
def trade():
    return FileResponse(f"{_CMD}/trade.html")


@router.get("/trade.js")
def trade_js():
    return FileResponse(f"{_CMD}/trade.js", media_type="text/javascript")


@router.get("/treasury")
def treasury_page():
    return FileResponse(f"{_CMD}/treasury.html")


@router.get("/treasury.js")
def treasury_js():
    return FileResponse(f"{_CMD}/treasury.js", media_type="text/javascript")


@router.get("/learn")
def learn_page():
    return FileResponse(f"{_CMD}/learn.html")


@router.get("/learn.js")
def learn_js():
    return FileResponse(f"{_CMD}/learn.js", media_type="text/javascript")


@router.get("/console")
def console_home():
    return FileResponse("maybot_control_center/static/index.html")


@router.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@router.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")


# ---- PWA (installable app + offline shell) ----
@router.get("/manifest.webmanifest")
def manifest():
    return FileResponse("maybot_control_center/static/manifest.webmanifest", media_type="application/manifest+json")


@router.get("/sw.js")
def service_worker():
    return FileResponse("maybot_control_center/static/sw.js", media_type="text/javascript")


@router.get("/pwa.js")
def pwa_js():
    return FileResponse("maybot_control_center/static/pwa.js", media_type="text/javascript")


@router.get("/icon.svg")
def icon():
    return FileResponse("maybot_control_center/static/icon.svg", media_type="image/svg+xml")


@router.get("/assets/{path:path}")
def assets(path: str):
    """Serve static assets (Sect Map art, sprites). Rejects path traversal."""
    base = os.path.realpath("maybot_control_center/static/assets")
    target = os.path.realpath(os.path.join(base, path))
    if os.path.commonpath([base, target]) != base or not os.path.isfile(target):
        raise HTTPException(404, "asset not found")
    return FileResponse(target)
