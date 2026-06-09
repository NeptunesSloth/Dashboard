"""Agent-ops API routes (extracted from app.py): shared memory, the guarded-tool
registry + autonomy gates, and LLM usage / budget telemetry.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import autonomy, memory, store, usage
from .. import tools as tooling
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


class ToolRunIn(BaseModel):
    tool: str
    args: dict = {}


@router.get("/api/memory")
def memory_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "subdir": memory.SUBDIR}


@router.get("/api/memory/search")
def memory_search(q: str = Query(default=""), limit: int = Query(default=5), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "results": memory.search(q, max(1, min(limit, 20)))}


@router.get("/api/memory/note")
def memory_note(path: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if len(path) > 512:
        raise HTTPException(400, "path too long")
    content = memory.read_note(path)
    if content is None:
        raise HTTPException(404, "note not found")
    return {"path": path, "content": content}


@router.get("/api/tools")
def tools_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": tooling.enabled(), "tools": tooling.tool_summaries(),
            "calls": tooling.list_calls(), "autonomy": autonomy.status()}


@router.get("/api/tools/audit")
def tools_audit(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if store.enabled():
        return {"persisted": True, "calls": store.load_tool_calls(500)}
    return {"persisted": False, "calls": tooling.list_calls(200)}


@router.post("/api/autonomy/pause")
def autonomy_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(True)


@router.post("/api/autonomy/resume")
def autonomy_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(False)


@router.post("/api/tools/run")
def tools_run(body: ToolRunIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.tool or ""):
        raise HTTPException(400, "invalid tool name")
    try:
        call = tooling.request_tool("operator", body.tool, body.args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    # Operator both requests and approves — run it now if it's still pending.
    if call.get("status") == "pending":
        call = tooling.approve(call["id"])
    return call


@router.post("/api/tools/{call_id}/approve")
def tools_approve(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.approve(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@router.post("/api/tools/{call_id}/deny")
def tools_deny(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.deny(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@router.get("/api/usage")
def usage_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.snapshot()


@router.get("/api/usage/series")
def usage_series(hours: int = Query(default=24), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.series(max(1, min(hours, 336)))


@router.get("/api/budget")
def budget_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    from .. import budget
    return budget.snapshot()
