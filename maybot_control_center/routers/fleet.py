"""Fleet status & per-project routes (extracted from app.py): the /api/overview
poll, per-bot log/diagnose/history/explain proxies, guarded start/stop/run-tests
actions, and the Ops Copilot.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import json as _json
import os

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import agents, aggregator, errorbudget, history
from ..agent_client import call_agent, post_agent
from ..aggregator import aggregate
from ..config import all_devices
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_project_access as _check_project_access
from ..deps import check_token as _check_token
from ..deps import resolve_device as _resolve_device

router = APIRouter()

_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}
# Opt-in async fleet poll for /api/overview (direct-HTTP fleets only).
_ASYNC_POLL = os.getenv("MAYBOT_ASYNC_POLL", "0").lower() in ("1", "true", "yes", "on")


@router.get("/api/overview")
async def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    devices = all_devices()
    # Opt-in async fleet poll (MAYBOT_ASYNC_POLL): gather every agent's ping +
    # projects concurrently with httpx instead of a thread pool. The async client
    # does DIRECT HTTP only, so fall back to the sync path when any device is on
    # the reverse tunnel. The sync path runs in a worker thread so a slow/offline
    # host never blocks the event loop.
    if _ASYNC_POLL and not _any_tunneled(devices):
        return await aggregator.aggregate_async(devices)
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(aggregate, devices)


def _any_tunneled(devices) -> bool:
    try:
        from .. import tunnel
        return any(tunnel.connected(d.get("name")) for d in (devices or []))
    except Exception:
        return False


@router.get("/api/logs/{device_name}/{project_name}")
def proxy_logs(device_name: str, project_name: str, level: str = Query(default="ALL"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    if level.upper() not in _VALID_LEVELS:
        raise HTTPException(400, f"invalid log level '{level}'")
    result = call_agent(_resolve_device(device_name), f"/api/projects/{project_name}/logs?level={level.upper()}")
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


@router.get("/api/diagnose/{device_name}/{project_name}")
def diagnose_project(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    """Heuristic root-cause analysis of a bot's recent error logs + status."""
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    from .. import diagnosis
    return diagnosis.diagnose(device_name, project_name)


@router.get("/api/history/{device_name}/{project_name}")
def project_history(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    return {"history": history.get(device_name, project_name)}


@router.post("/api/projects/{device_name}/{project_name}/explain")
def explain_project(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    """Plain-English status + recommendation for a bot: heuristic diagnosis,
    elaborated by a member if an LLM backend is configured."""
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    from .. import diagnosis
    d = diagnosis.diagnose(device_name, project_name)
    # try to elaborate with the first member that has a usable backend
    explanation = None
    for a in agents.file_agents():
        if (a.get("base_url") or a.get("provider") in ("claude", "anthropic")):
            facts = (f"Bot '{project_name}' on '{device_name}'. Health: {d.get('health')}. "
                     f"Findings: {[f['signal'] for f in d.get('findings', [])] or 'none'}. "
                     f"Summary: {d.get('summary')}")
            ok, text, _ = agents._chat({**a, "max_tokens": 220, "temperature": 0.3}, [
                {"role": "system", "content": "You are a terse trading-ops engineer. In 2-3 sentences, explain what's going on with this bot and the single most useful next action."},
                {"role": "user", "content": facts}])
            if ok and text:
                explanation = text.strip()
            break
    return {**d, "explanation": explanation}


@router.post("/api/action/{device_name}/{project_name}/{action}")
def proxy_action(device_name: str, project_name: str, action: str, force: bool = Query(default=False),
                 x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    _check_project_access(x_control_token, device_name, project_name)
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, f"unknown action '{action}'; must be one of {sorted(_VALID_ACTIONS)}")
    # Heavenly Decree: a project that burned its error budget is frozen against
    # state-changing actions until reliability recovers (override with ?force=1).
    if action in {"start", "stop"} and not force and errorbudget.is_frozen(device_name, project_name):
        raise HTTPException(423, f"'{project_name}' is under a Heavenly Decree (error budget exhausted); "
                                 f"reliability work only, or retry with force=true")
    agent_path = "run-tests" if action == "run-tests" else action
    timeout = _ACTION_TIMEOUTS[action]
    result = post_agent(_resolve_device(device_name), f"/api/projects/{project_name}/{agent_path}", timeout=timeout)
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


class CopilotIn(BaseModel):
    question: str


@router.post("/api/copilot")
def copilot_ask(body: CopilotIn, x_control_token: str = Header(default="")):
    """Ops Copilot: answer a natural-language question about the fleet, grounded
    in a fresh poll, and surface conservative one-click remediations."""
    _check_token(x_control_token)
    from .. import copilot
    overview = aggregate(all_devices())
    return copilot.ask(body.question, overview)


@router.post("/api/copilot/stream")
def copilot_ask_stream(body: CopilotIn, x_control_token: str = Header(default="")):
    """Streaming Ops Copilot: server-sent events so the answer renders token by
    token. Each line is ``data: {json}`` with a type of meta/token/done/error."""
    _check_token(x_control_token)
    from .. import copilot
    overview = aggregate(all_devices())

    def gen():
        try:
            for event in copilot.ask_stream(body.question, overview):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
