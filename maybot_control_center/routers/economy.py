"""Disciple economy & lifecycle API routes (extracted from app.py): the sect
treasury, seclusion/roaming retreats, learn-goals, skill transmission, quests,
and cultivation pills.

Mounted by app.py via include_router.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .. import agents, cultivation, pills, quests, treasury
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/treasury")
def treasury_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return treasury.status()


class EndowIn(BaseModel):
    amount: int


@router.post("/api/treasury/endow")
def treasury_endow(body: EndowIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    amount = int(body.amount or 0)
    if amount <= 0 or amount > 1_000_000:
        raise HTTPException(400, "amount must be 1..1000000")
    treasury.deposit(amount)
    return treasury.status()


class SeclusionIn(BaseModel):
    enter: bool = True


@router.post("/api/agents/{name}/seclusion")
def agent_seclusion(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_seclusion(name) if body.enter else cultivation.exit_seclusion(name)


@router.post("/api/agents/{name}/roaming")
def agent_roaming(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_roaming(name) if body.enter else cultivation.exit_roaming(name)


class LearnGoalIn(BaseModel):
    skill: str = ""   # empty clears the goal


@router.post("/api/agents/{name}/learn-goal")
def agent_learn_goal(name: str, body: LearnGoalIn, x_control_token: str = Header(default="")):
    """Ask a disciple to seek a specific skill on their next roam (or the closest)."""
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    if len(body.skill) > 120:
        raise HTTPException(400, "skill too long (max 120)")
    return cultivation.set_learn_goal(name, body.skill)


class TransmitIn(BaseModel):
    to: str
    skill: str


@router.post("/api/agents/{name}/transmit")
def agent_transmit(name: str, body: TransmitIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name) or not _SAFE_NAME.match(body.to or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        return agents.transmit(name, body.to, (body.skill or "").strip())
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/quests")
def quests_board(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": quests.catalog()}


class QuestIn(BaseModel):
    quest: str


@router.post("/api/agents/{name}/quest")
def agent_quest(name: str, body: QuestIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    q = quests.get(body.quest)
    if not q:
        raise HTTPException(400, "unknown quest")
    cultivation.assign_quest(name, q["reward_skill"], q["stones"])
    return agents.assign_task(name, f"[Quest: {q['name']}] {q['task']}")


class PillBuyIn(BaseModel):
    agent: str
    pill: str


@router.get("/api/pills")
def pills_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": pills.catalog(), "active": pills.active_all()}


@router.post("/api/pills/buy")
def pills_buy(body: PillBuyIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or "") or not _SAFE_NAME.match(body.pill or ""):
        raise HTTPException(400, "invalid agent or pill")
    try:
        return pills.buy(body.agent, body.pill)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
