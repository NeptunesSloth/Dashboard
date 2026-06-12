"""Admin & ops routes (extracted from app.py): full config export/import,
dead-man's-switch heartbeat, safe mode (panic button), system settings,
self-healing runbooks, state backup/restore, data retention, self-observability,
fleet diagnostics, the operator audit log, and CSV/JSON data export.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .. import audit, authz, backup, deadman, diagnostics, events, history, retention, runbooks, safemode, selfcheck, usage
from .. import settings as app_settings
from .. import tools as tooling
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/admin/export")
def admin_export(x_control_token: str = Header(default="")):
    """Download a full config backup (hosts, accounts, enroll token, state)."""
    _check_operator(x_control_token)
    from .. import dr
    return JSONResponse(dr.export_all(),
                        headers={"Content-Disposition": "attachment; filename=maybot-backup.json"})


@router.post("/api/admin/import")
def admin_import(body: dict, x_control_token: str = Header(default="")):
    """Restore from a backup bundle — rebuilds hosts/accounts/state in place."""
    _check_operator(x_control_token)
    from .. import dr
    try:
        return dr.restore_all(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class DeadmanIn(BaseModel):
    url: str = ""
    interval: float | None = None


@router.get("/api/deadman")
def deadman_get(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return deadman.status()


@router.post("/api/deadman")
def deadman_set(body: DeadmanIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return deadman.configure(body.url, body.interval)


@router.post("/api/deadman/test")
def deadman_test(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"ok": deadman.ping_once(), **deadman.status()}


class SafemodeIn(BaseModel):
    engaged: bool


@router.get("/api/safemode")
def safemode_get(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return safemode.status()


@router.post("/api/safemode")
def safemode_set(body: SafemodeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    safemode.set_engaged(body.engaged)
    events.publish("safemode", {"engaged": body.engaged})
    return safemode.status()


def _verify_account_password(token: str, password: str) -> None:
    """Gate the secrets panel: re-check the operator's account password.

    In open mode (no account password set) there is nothing to verify against,
    so access follows the dashboard's own (open) posture.
    """
    u = authz.current_user(token)
    pw_hash = (u or {}).get("pw") or ""
    if pw_hash and not authz.verify_password(password or "", pw_hash):
        raise HTTPException(403, "incorrect password")


@router.get("/api/settings")
def settings_get(x_control_token: str = Header(default="")):
    """System settings with secrets MASKED (status only). Reveal needs /unlock."""
    _check_operator(x_control_token)
    return app_settings.view(reveal=False)


class SettingsUnlockIn(BaseModel):
    password: str = ""


@router.post("/api/settings/unlock")
def settings_unlock(body: SettingsUnlockIn, x_control_token: str = Header(default="")):
    """Password-protected reveal: returns settings incl. secret values."""
    _check_operator(x_control_token)
    _verify_account_password(x_control_token, body.password)
    return {"ok": True, **app_settings.view(reveal=True)}


class SettingsIn(BaseModel):
    values: dict = {}
    password: str = ""


@router.post("/api/settings")
def settings_set(body: SettingsIn, x_control_token: str = Header(default="")):
    """Update system settings (password-gated); persisted + applied at runtime."""
    _check_operator(x_control_token)
    _verify_account_password(x_control_token, body.password)
    app_settings.set_many(body.values or {})
    return {"ok": True, **app_settings.view(reveal=True)}


# ---- Auto-remediation runbooks ----
@router.get("/api/runbooks")
def runbooks_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"runbooks": runbooks.catalog(), "editable": runbooks.list_rules(),
            "tools": [t.get("name") for t in tooling.tool_summaries()]}


class RunbookIn(BaseModel):
    name: str
    tool: str
    match: dict = {}
    args: dict = {}
    requester: str = "operator"
    auto: bool = False


@router.post("/api/runbooks")
def runbooks_save(body: RunbookIn, x_control_token: str = Header(default="")):
    """Create/replace a self-healing rule from the UI (persisted)."""
    _check_operator(x_control_token)
    try:
        saved = runbooks.save_rule(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "runbook": saved}


@router.delete("/api/runbooks/{name}")
def runbooks_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"ok": runbooks.delete_rule(name)}


# ---- Data retention & scheduled backups (Archivist) ----
@router.get("/api/retention")
def retention_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return retention.snapshot()


@router.post("/api/retention/prune")
def retention_prune(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return retention.prune_now()


@router.post("/api/backup/snapshot")
def backup_snapshot(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return retention.snapshot_now()


@router.get("/api/backup/list")
def backup_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"backups": retention.list_backups()}


# ---- State backup / restore ----
@router.get("/api/backup")
def backup_export(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return backup.export()


@router.post("/api/restore")
def backup_restore(body: dict, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return backup.restore(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Control-center self-observability ----
@router.get("/api/selfcheck")
def selfcheck_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return selfcheck.snapshot()


# ---- Setup & diagnostics / fleet health ----
@router.get("/api/diagnostics")
def diagnostics_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return diagnostics.snapshot()


# ---- Operator audit log ----
@router.get("/api/audit")
def audit_log(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return audit.snapshot()


@router.get("/api/audit/verify")
def audit_verify(x_control_token: str = Header(default="")):
    """Walk the audit log's hash chain and report any tampering."""
    _check_token(x_control_token)
    return audit.verify()


@router.get("/api/audit/export")
def audit_export(x_control_token: str = Header(default="")):
    """The retained audit log as JSON Lines, for SIEM / log-pipeline ingestion."""
    _check_operator(x_control_token)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(audit.export_jsonl(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": 'attachment; filename="audit.jsonl"'})


# ---- Data export (CSV / JSON) ----
def _csv_response(filename: str, header: list[str], rows) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/export/usage")
def export_usage(hours: int = Query(default=168), fmt: str = Query(default="csv"),
                 x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    data = usage.series(max(1, min(hours, 24 * 14)))
    if fmt == "json":
        return data
    rows = ([b["hour"], b["calls"], b["errors"], b["tokens_in"], b["tokens_out"], b["cost"]]
            for b in data["buckets"])
    return _csv_response("usage.csv", ["hour_epoch", "calls", "errors", "tokens_in", "tokens_out", "cost_usd"], rows)


@router.get("/api/export/history")
def export_history(fmt: str = Query(default="csv"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    series = history.all_series()
    if fmt == "json":
        return {"series": series}

    def _rows():
        for key, points in series.items():
            device, _, name = key.partition(":")
            for pt in points:
                yield [device, name, pt.get("ts"), pt.get("health"), pt.get("pnl")]
    return _csv_response("history.csv", ["device", "project", "ts_ms", "health", "pnl"], _rows())
