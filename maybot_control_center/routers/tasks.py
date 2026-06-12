"""Task board & orchestration routes (extracted from app.py): the work queue,
goal-based auto-routing to the best-fit disciple, goal decomposition into routed
subtasks, the autopilot kill switch, and shared sect memory.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import agents, autopilot, governance, orchestrator, routing, sectmemory, taskqueue
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


# ---- Compounding sect memory (shared knowledge) ----
@router.get("/api/sectmemory")
def sectmemory_status(q: str = Query(default=""), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if q.strip():
        return {"query": q, "results": sectmemory.search(q, 8)}
    return sectmemory.snapshot()


# ---- Autopilot (the Sect Leader's second brain) ----
@router.get("/api/autopilot")
def autopilot_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return autopilot.status()


@router.post("/api/autopilot/pause")
def autopilot_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)   # kill switch
    return autopilot.set_paused(True)


@router.post("/api/autopilot/resume")
def autopilot_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autopilot.set_paused(False)


# ---- Task board / work queue ----
@router.get("/api/tasks")
def tasks_board(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return taskqueue.board()


class NewTaskIn(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    assignee: str | None = None
    dispatch: bool = True
    project: str | None = None
    device: str | None = None


@router.post("/api/tasks")
def tasks_create(body: NewTaskIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    if len(title) > 200:
        raise HTTPException(400, "title too long (max 200)")
    if body.assignee and not _SAFE_NAME.match(body.assignee):
        raise HTTPException(400, "invalid assignee name")
    task = taskqueue.create(title, description=body.description, priority=body.priority,
                            assignee=body.assignee, project=body.project, device=body.device)
    if body.dispatch and body.assignee:
        if agents._agent_def(body.assignee) is None:
            raise HTTPException(404, "assignee not found")
        text = title + ((" — " + body.description) if body.description else "")
        agents.assign_task(body.assignee, text)
        taskqueue.link_dispatch(task["id"], body.assignee)
        task = taskqueue.get(task["id"])
    return task


class ReassignIn(BaseModel):
    assignee: str
    dispatch: bool = True


@router.post("/api/tasks/{task_id}/reassign")
def tasks_reassign(task_id: int, body: ReassignIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.assignee or ""):
        raise HTTPException(400, "invalid assignee name")
    task = taskqueue.get(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if agents._agent_def(body.assignee) is None:
        raise HTTPException(404, "assignee not found")
    taskqueue.reassign(task_id, body.assignee)
    if body.dispatch:
        text = task["title"] + ((" — " + task["description"]) if task["description"] else "")
        agents.assign_task(body.assignee, text)
        taskqueue.link_dispatch(task_id, body.assignee)
    return taskqueue.get(task_id)


class StatusIn(BaseModel):
    status: str
    result: str | None = None


@router.post("/api/tasks/{task_id}/status")
def tasks_set_status(task_id: int, body: StatusIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    valid = {"queued", "assigned", "in_progress", "done", "failed", "cancelled"}
    if body.status not in valid:
        raise HTTPException(400, f"invalid status; must be one of {sorted(valid)}")
    task = taskqueue.set_status(task_id, body.status, body.result)
    if not task:
        raise HTTPException(404, "task not found")
    return task


# ---- Assign by goal (auto-route to the best-fit disciple) ----
@router.get("/api/assign/preview")
def assign_preview(goal: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"goal": goal, "ranked": routing.rank(goal)}


class GoalIn(BaseModel):
    goal: str
    priority: str = "normal"
    dispatch: bool = True


@router.post("/api/assign/goal")
def assign_goal(body: GoalIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    goal = (body.goal or "").strip()
    if not goal:
        raise HTTPException(400, "goal required")
    if len(goal) > 4000:
        raise HTTPException(400, "goal too long (max 4000)")
    fit = routing.best_fit(goal)
    if not fit:
        raise HTTPException(409, "no eligible disciple to take this goal")
    task = taskqueue.create(goal[:200], description=goal if len(goal) > 200 else "",
                            priority=body.priority, source="goal", assignee=fit["agent"])
    if body.dispatch:
        executor, _ = governance.route_task(fit["agent"], critical=False)
        agents.assign_task(executor, goal)
        taskqueue.link_dispatch(task["id"], executor)
        task = taskqueue.get(task["id"])
    return {"task": task, "routed_to": fit["agent"], "reason": fit["reason"], "ranked": fit["ranked"]}


# ---- Orchestrate (decompose a goal into routed subtasks) ----
class OrchestrateIn(BaseModel):
    goal: str
    max_subtasks: int | None = None
    dispatch: bool = True


@router.post("/api/orchestrate")
def orchestrate_goal(body: OrchestrateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return orchestrator.orchestrate(body.goal, body.max_subtasks, body.dispatch)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
