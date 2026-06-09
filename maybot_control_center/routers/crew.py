"""Disciple crew + missions API routes (extracted from app.py): the agent roster
and dossiers, task delegation and dispatch (with live-bot context), and the
comms mission feed.

Mounted by app.py via include_router.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import agents, comms, github_repo, governance
from ..agent_client import call_agent
from ..config import all_devices
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


class TaskIn(BaseModel):
    task: str
    critical: bool = False        # critical work the Sect Leader handles directly
    project: str | None = None    # optional project this task acts on (personal guard)
    device: str | None = None
    repo: str | None = None       # optional GitHub repo (owner/name) for context
    issue: int | None = None      # optional issue/PR number


@router.get("/api/agents")
def list_agents(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"agents": agents.snapshot()}


@router.get("/api/agents/{name}")
def agent_detail(name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    detail = agents.get_agent(name)
    if detail is None:
        raise HTTPException(404, "agent not found")
    return detail


class DelegateIn(BaseModel):
    to: str
    task: str


@router.post("/api/agents/{name}/delegate")
def agent_delegate(name: str, body: DelegateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name) or not _SAFE_NAME.match(body.to or ""):
        raise HTTPException(400, "invalid agent name")
    task = (body.task or "").strip()
    if not task:
        raise HTTPException(400, "task must not be empty")
    if len(task) > 4000:
        raise HTTPException(400, "task too long (max 4000 chars)")
    try:
        return agents.delegate(name, body.to, task)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except KeyError:
        raise HTTPException(404, "agent not found")


def _bot_context(device: str | None, project: str | None, log_lines: int = 12) -> str:
    """A compact live snapshot of one bot (status, PnL metrics, recent log tail)
    so a dispatched disciple can see what's actually going on with it."""
    if not project:
        return ""
    devices = all_devices()
    found, dev = None, None
    for d in devices:
        if device and d.get("name") != device:
            continue
        pl = call_agent(d, "/api/projects").get("data", [])
        if isinstance(pl, list):
            match = next((p for p in pl if p.get("name") == project), None)
            if match:
                found, dev = match, d
                break
        if device:
            break
    if not found or not dev:
        return ""
    m = found.get("metrics", {}) or {}
    lines = [f"### Live status — bot '{project}' on host '{dev.get('name')}'",
             f"- type: {found.get('type')} · status: {found.get('status')} · health: {found.get('health')}"]
    if found.get("type") == "trading_bot":
        for key, label in (("profit_today", "PnL today"), ("profit_this_week", "PnL this week"),
                           ("realized_pnl", "realized PnL"), ("unrealized_pnl", "unrealized PnL"),
                           ("open_positions", "open positions"), ("open_exposure", "open exposure"),
                           ("trades_today", "trades today"), ("fill_rate", "fill rate"),
                           ("last_trade_time", "last trade")):
            v = m.get(key)
            if v not in (None, "", "unknown"):
                lines.append(f"- {label}: {v}")
    for a in (found.get("alerts") or [])[:4]:
        lines.append(f"- alert: {a}")
    lg = call_agent(dev, f"/api/projects/{project}/logs?level=ALL").get("data", {})
    tail = lg.get("lines") if isinstance(lg, dict) else None
    if isinstance(tail, list) and tail:
        lines.append("\nRecent log tail:\n```")
        lines.extend(str(x) for x in tail[-log_lines:])
        lines.append("```")
    return "\n".join(lines)


@router.post("/api/agents/{name}/task")
def assign_agent_task(name: str, body: TaskIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    task = (body.task or "").strip()
    if not task:
        raise HTTPException(400, "task must not be empty")
    if len(task) > 4000:
        raise HTTPException(400, "task too long (max 4000 chars)")
    # The Ancestor's personal bot projects are off-limits to disciples.
    if body.project and governance.is_personal_project(body.project, body.device):
        raise HTTPException(403, f"'{body.project}' is the Ancestor's personal project — disciples may not be assigned to it")
    # Optional GitHub reference is prepended as context for the disciple.
    if body.repo:
        if not _SAFE_NAME.match(body.repo.replace("/", "_")):
            raise HTTPException(400, "invalid repo name")
        ref = github_repo.task_reference(body.repo, body.issue)
        if ref:
            task = f"{ref}\n\n{task}"
    # When the task is tied to a bot, prepend that bot's live status + recent logs
    # so the disciple can act on what's actually happening with it.
    if body.project:
        try:
            botctx = _bot_context(body.device, body.project)
            if botctx:
                task = f"{botctx}\n\n---\n\n{task}"
        except Exception:
            pass  # never let an observability lookup block dispatch
    # The Sect Leader oversees: routine work is routed to a deputy Elder.
    executor, delegated_from = governance.route_task(name, body.critical)
    try:
        snap = agents.assign_task(executor, task)
    except KeyError:
        raise HTTPException(404, "agent not found")
    if delegated_from:
        snap = dict(snap)
        snap["oversight"] = {"leader": delegated_from, "delegated_to": executor,
                             "note": "the Sect Leader oversees; routine work was passed to a deputy"}
    return snap


class MissionIn(BaseModel):
    goal: str
    participants: list[str] = []
    rounds: int = 2


@router.get("/api/comms")
def comms_feed(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"feed": comms.get_feed(max(1, min(limit, 200))), "status": comms.status()}


@router.post("/api/comms/mission")
def comms_mission(body: MissionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    goal = (body.goal or "").strip()
    if not goal:
        raise HTTPException(400, "goal required")
    if len(goal) > 2000:
        raise HTTPException(400, "goal too long (max 2000 chars)")
    parts = [p for p in body.participants if _SAFE_NAME.match(p or "")]
    try:
        return comms.start_mission(goal, parts, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
