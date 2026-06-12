"""Sect Member roster routes (extracted from app.py): add/edit/remove members
(agents.yaml) from the UI, RPG dossiers, backend connectivity tests, one-click
starter seeding, and member-vs-member debates/tournaments.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .. import agents, comms
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()

_PROVIDERS = {"ollama", "openai_compatible", "claude", "openai"}


class MemberIn(BaseModel):
    name: str
    role: str = "Disciple"
    provider: str = "ollama"
    model: str = ""
    base_url: str = ""
    persona: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    original_name: str | None = None


@router.get("/api/members/profiles")
def members_profiles(x_control_token: str = Header(default="")):
    """Persistent, evolving RPG dossiers for the current roster (the sect sim)."""
    _check_token(x_control_token)
    from .. import sectsim
    return {"profiles": sectsim.profiles(agents.snapshot())}


class MemberTestIn(BaseModel):
    provider: str = "ollama"
    model: str = ""
    base_url: str = ""


@router.post("/api/members/test")
def members_test(body: MemberTestIn, x_control_token: str = Header(default="")):
    """Send a tiny prompt to a member's AI backend to confirm it actually answers."""
    _check_operator(x_control_token)
    if not (body.model or "").strip():
        raise HTTPException(400, "a model is required")
    probe = {"name": "(test)", "provider": (body.provider or "ollama"), "model": body.model.strip(),
             "base_url": (body.base_url or "").strip(), "max_tokens": 16, "temperature": 0}
    import time as _t
    t0 = _t.time()
    ok, text, err = agents._chat(probe, [{"role": "user", "content": "Reply with the single word: pong"}])
    return {"ok": bool(ok), "reply": (text or "").strip()[:200], "error": err, "latency_ms": int((_t.time() - t0) * 1000)}


@router.post("/api/members/seed")
def members_seed(x_control_token: str = Header(default="")):
    """One-click starter sect: a few Hermes-backed members (only when empty)."""
    _check_operator(x_control_token)
    if agents.file_agents():
        raise HTTPException(409, "the sect already has members")
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    starter = [
        ("Nova", "Research Analyst", "Meticulous, data-driven, concise. Answers in tight bullet points."),
        ("Forge", "Builder", "Pragmatic engineer; proposes the smallest implementation that works."),
        ("Sage", "Reviewer", "Careful reviewer; checks claims and gives a clear go / no-go."),
        ("Atlas", "Strategist", "Weighs trade-offs explicitly and gives one clear recommendation."),
    ]
    roster = [{"name": n, "role": r, "provider": "ollama", "base_url": base,
               "model": "nous-hermes", "persona": p, "max_tokens": 512} for n, r, p in starter]
    agents.save_agents(roster)
    return {"ok": True, "count": len(roster)}


@router.get("/api/members")
def members_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    out = [{
        "name": a.get("name"), "role": a.get("role", ""), "provider": a.get("provider", ""),
        "model": a.get("model", ""), "base_url": a.get("base_url", ""),
        "persona": a.get("persona") or a.get("system") or "",
        "temperature": a.get("temperature"), "max_tokens": a.get("max_tokens"),
    } for a in agents.file_agents()]
    return {"members": out}


@router.post("/api/members")
def members_save(body: MemberIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "member name may contain letters, numbers, dashes and underscores only")
    provider = body.provider if body.provider in _PROVIDERS else "ollama"
    if not (body.model or "").strip():
        raise HTTPException(400, "a model is required")
    if provider in ("ollama", "openai_compatible", "openai") and not (body.base_url or "").strip() and provider != "openai":
        raise HTTPException(400, "this provider needs a base_url (e.g. http://127.0.0.1:11434)")
    entry: dict = {"name": name, "role": (body.role or "Disciple").strip(), "provider": provider,
                   "model": body.model.strip()}
    if body.base_url.strip():
        entry["base_url"] = body.base_url.strip()
    if body.persona.strip():
        entry["persona"] = body.persona.strip()
    if body.temperature is not None:
        entry["temperature"] = float(body.temperature)
    if body.max_tokens is not None:
        entry["max_tokens"] = int(body.max_tokens)
    roster = agents.file_agents()
    if body.original_name:
        idx = next((i for i, a in enumerate(roster) if a.get("name") == body.original_name.strip()), None)
        if idx is None:
            raise HTTPException(404, "member not found")
        if any(a.get("name") == name for i, a in enumerate(roster) if i != idx):
            raise HTTPException(409, f"a member named '{name}' already exists")
        roster[idx] = entry
    else:
        if any(a.get("name") == name for a in roster):
            raise HTTPException(409, f"a member named '{name}' already exists")
        roster.append(entry)
    agents.save_agents(roster)
    return {"ok": True, "name": name}


@router.delete("/api/members/{name}")
def members_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid member name")
    roster = agents.file_agents()
    remaining = [a for a in roster if a.get("name") != name]
    if len(remaining) == len(roster):
        raise HTTPException(404, "member not found")
    agents.save_agents(remaining)
    return {"ok": True}


class DebateIn(BaseModel):
    topic: str
    a: str
    b: str
    judge: str
    rounds: int = 2


@router.post("/api/comms/debate")
def comms_debate(body: DebateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    for n in (body.a, body.b, body.judge):
        if not _SAFE_NAME.match(n or ""):
            raise HTTPException(400, "invalid participant name")
    try:
        return comms.start_debate(body.topic, body.a, body.b, body.judge, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


class TournamentIn(BaseModel):
    topic: str
    participants: list[str] = []
    judge: str
    rounds: int = 1


@router.post("/api/comms/tournament")
def comms_tournament(body: TournamentIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    parts = [p for p in body.participants if _SAFE_NAME.match(p or "")]
    if not _SAFE_NAME.match(body.judge or ""):
        raise HTTPException(400, "invalid judge name")
    try:
        return comms.start_tournament(body.topic, parts, body.judge, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
