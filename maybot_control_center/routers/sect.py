"""Sect / cultivation RPG API routes (extracted from app.py): cultivation,
reputation, prophecy, formations, governance, tournament, night-watch,
spirit-root, dreamscape, chaos trials, GitHub repos, dao-heart, karmic bonds,
lineage, council votes, artifacts, titles and the chronicle.

Mounted by app.py via include_router.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .. import (artifacts, bonds, chaos, chronicle, comms, council_vote,
                cultivation, daoheart, dreamscape, formations, github_repo,
                governance, lineage, lifecycle, nightwatch, prophecy, reputation,
                spirit_root, titles, tournament)
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token

router = APIRouter()


@router.get("/api/cultivation")
def cultivation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return cultivation.snapshot()


@router.get("/api/reputation")
def reputation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return reputation.snapshot()


@router.get("/api/prophecy")
def prophecy_omens(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"omens": prophecy.divine()}


@router.get("/api/formations")
def formations_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": formations.catalog()}


class FormationIn(BaseModel):
    formation: str
    goal: str


@router.post("/api/formations/run")
def formations_run(body: FormationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return comms.start_formation(body.formation, body.goal)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/governance")
def governance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return governance.snapshot()


class ChallengeIn(BaseModel):
    challenger: str


@router.post("/api/governance/challenge")
def governance_challenge(body: ChallengeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.challenger or ""):
        raise HTTPException(400, "invalid challenger name")
    try:
        return governance.challenge(body.challenger)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class LeaderIn(BaseModel):
    leader: str | None = None     # None releases the role back to merit
    pinned: bool = True


@router.post("/api/governance/leader")
def governance_set_leader(body: LeaderIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # Ancestor authority
    if body.leader is not None and not _SAFE_NAME.match(body.leader):
        raise HTTPException(400, "invalid leader name")
    try:
        return governance.set_leader(body.leader, body.pinned)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class SpecialtyIn(BaseModel):
    agent: str
    specialty: str


@router.post("/api/governance/specialty")
def governance_specialty(body: SpecialtyIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        return governance.choose_specialty(body.agent, body.specialty)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class StrikeDownIn(BaseModel):
    agent: str
    reason: str = ""


@router.post("/api/governance/strike-down")
def governance_strike_down(body: StrikeDownIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # only the Ancestor may strike a disciple down
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        new = lifecycle.strike_down(body.agent, body.reason)
        return {"struck_down": body.agent, "replacement": new["name"]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/tournament")
def tournament_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return tournament.snapshot()


@router.post("/api/tournament/start")
def tournament_start(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # the Ancestor calls the Grand Tournament
    try:
        return tournament.hold()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/governance/inbox")
def governance_inbox(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"messages": governance.inbox(max(1, min(limit, 200)))}


class AncestorMsgIn(BaseModel):
    sender: str
    text: str


@router.post("/api/governance/message")
def governance_message(body: AncestorMsgIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.sender or ""):
        raise HTTPException(400, "invalid sender name")
    try:
        return governance.message_ancestor(body.sender, body.text)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Night-Watch (on-call rotation + auto-triage) ----
@router.get("/api/nightwatch")
def nightwatch_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return nightwatch.status()


class RotationIn(BaseModel):
    names: list[str] = []


@router.post("/api/nightwatch/rotation")
def nightwatch_rotation(body: RotationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    names = [n for n in body.names if _SAFE_NAME.match(n or "")]
    return nightwatch.set_rotation(names)


@router.post("/api/nightwatch/{record_id}/handled")
def nightwatch_handled(record_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"resolved": nightwatch.handled(record_id)}


# ---- Spirit-Root assessment (capability benchmarking) ----
@router.get("/api/spirit-root")
def spirit_root_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"profiles": spirit_root.snapshot(), "probes": spirit_root.PROBES,
            "baseline": spirit_root.BASELINE_PROBES}


class AssessIn(BaseModel):
    agent: str
    results: list[dict] = []


@router.post("/api/spirit-root/assess")
def spirit_root_assess(body: AssessIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    return spirit_root.assess(body.agent, body.results)


# ---- Dreamscape dry-run (formation plan preview) ----
class DreamIn(BaseModel):
    formation: str
    goal: str


@router.post("/api/dreamscape/preview")
def dreamscape_preview(body: DreamIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return dreamscape.preview(body.formation, body.goal)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Tribulation Trials (chaos engineering) ----
@router.get("/api/chaos")
def chaos_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return chaos.status()


class SummonIn(BaseModel):
    target: str
    kind: str
    disciple: str | None = None
    inject: bool = False          # actively inject the fault via a guarded tool


@router.post("/api/chaos/summon")
def chaos_summon(body: SummonIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if body.disciple and not _SAFE_NAME.match(body.disciple):
        raise HTTPException(400, "invalid disciple name")
    try:
        return chaos.summon(body.target, body.kind, body.disciple, inject=body.inject)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class ResolveIn(BaseModel):
    recovered: bool
    recovery_seconds: float | None = None


@router.post("/api/chaos/{trial_id}/resolve")
def chaos_resolve(trial_id: int, body: ResolveIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return chaos.resolve(trial_id, body.recovered, body.recovery_seconds)
    except KeyError:
        raise HTTPException(404, "trial not found")


# ---- GitHub repos (tracked as projects) ----
@router.get("/api/github")
def github_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": github_repo.enabled(), "repos": github_repo.collect() if github_repo.enabled() else []}


# ---- Dao-Heart drift detection ----
@router.get("/api/daoheart")
def daoheart_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"drift": daoheart.snapshot()}


# ---- Karmic-bond pairs ----
@router.get("/api/bonds")
def bonds_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return bonds.snapshot()


class BondIn(BaseModel):
    a: str
    b: str


@router.post("/api/bonds/bind")
def bonds_bind(body: BondIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.a or "") or not _SAFE_NAME.match(body.b or ""):
        raise HTTPException(400, "invalid disciple name")
    try:
        return bonds.bind(body.a, body.b)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class UnbondIn(BaseModel):
    agent: str


@router.post("/api/bonds/unbind")
def bonds_unbind(body: UnbondIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid disciple name")
    return {"unbound": bonds.unbind(body.agent)}


# ---- Lineage (knowledge graph) ----
@router.get("/api/lineage")
def lineage_graph(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return lineage.graph()


# ---- Merit-weighted council vote ----
class VoteIn(BaseModel):
    question: str
    votes: dict[str, str]


@router.post("/api/council/vote")
def council_vote_run(body: VoteIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return council_vote.tally(body.question, body.votes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/council/history")
def council_history(limit: int = Query(default=25), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"history": council_vote.history(max(1, min(limit, 100)))}


# ---- Artifact vault ----
@router.get("/api/artifacts")
def artifacts_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return artifacts.snapshot()


class ForgeIn(BaseModel):
    creator: str
    name: str
    kind: str
    content: str
    description: str = ""


@router.post("/api/artifacts/forge")
def artifacts_forge(body: ForgeIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.name or ""):
        raise HTTPException(400, "invalid artifact name")
    try:
        return artifacts.forge(body.creator, body.name, body.kind, body.content, body.description)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class WieldIn(BaseModel):
    agent: str
    name: str


@router.post("/api/artifacts/wield")
def artifacts_wield(body: WieldIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return artifacts.wield(body.agent, body.name)
    except KeyError:
        raise HTTPException(404, "artifact not found")


# ---- Titles & achievements ----
@router.get("/api/titles")
def titles_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": titles.catalog()}


# ---- Cultivation chronicle (per-disciple timeline) ----
@router.get("/api/chronicle")
def chronicle_recent(limit: int = Query(default=50), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"recent": chronicle.recent(max(1, min(limit, 200))), "summary": chronicle.snapshot()}


@router.get("/api/chronicle/{name}")
def chronicle_agent(name: str, limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    return {"agent": name, "timeline": chronicle.timeline(name, max(1, min(limit, 200)))}
