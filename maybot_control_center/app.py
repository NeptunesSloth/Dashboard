import csv
import io
import queue
import re
import secrets
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel
from .config import load_devices, all_devices, CONTROL_CENTER_TOKEN
from . import aggregator
from .aggregator import aggregate
from .agent_client import call_agent, post_agent
from . import history
from . import agents
from . import comms
from . import memory
from . import tools as tooling
from . import store
from . import events
from . import autonomy
from . import usage
from . import authz
from . import cultivation
from . import pills
from . import treasury
from . import quests
from . import metrics as metrics_mod
from . import scheduler
from . import reputation
from . import prophecy
from . import formations
from . import governance
from . import nightwatch
from . import spirit_root
from . import dreamscape
from . import chaos
from . import github_repo
from . import daoheart
from . import bonds
from . import lineage
from . import council_vote
from . import artifacts
from . import titles
from . import chronicle
from . import runbooks
from . import lifecycle
from . import tournament
from . import maintenance
from . import slo
from . import errorbudget
from . import meridians
from . import talismans
from . import oaths
from . import escalation
from . import taskqueue
from . import routing
from . import orchestrator
from . import autopilot
from . import sectmemory
from . import audit
from . import diagnostics
from . import inbound
from . import backup
from . import registry
from . import push
from . import command

# Restore persisted state (no-op unless MAYBOT_DB is set).
store.init()
for _loader in (history.load_persisted, agents.load_persisted, comms.load_persisted,
                tooling.load_persisted, usage.load_persisted, cultivation.load_persisted,
                treasury.load_persisted, taskqueue.load_persisted, oaths.load_persisted,
                maintenance.load_persisted, autopilot.load_persisted, sectmemory.load_persisted,
                audit.load_persisted, inbound.load_persisted, registry.load_persisted,
                push.load_persisted):
    try:
        _loader()
    except Exception:
        pass
scheduler.start()  # background cron for scheduled missions (no-op without schedules.yaml)
talismans.start()  # background synthetic uptime probes (no-op without talismans.yaml)
autopilot.start()  # the Sect Leader's autonomous ops loop (no-op unless MAYBOT_AUTOPILOT=1)

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
# A silence target: "*", "device:*", or "device:project".
_SAFE_TARGET = re.compile(r'^(\*|[a-zA-Z0-9_\-\.]{1,128}:(\*|[a-zA-Z0-9_\-\.]{1,128}))$')
_VALID_LEVELS = {"ALL", "ERROR", "WARNING", "INFO"}
_VALID_ACTIONS = {"start", "stop", "run-tests"}
_ACTION_TIMEOUTS = {"start": 15, "stop": 15, "run-tests": 330}

app = FastAPI(title="maybot-control-center")


@app.middleware("http")
async def _rate_limit(request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/stream"):
        key = request.headers.get("x-control-token") or (request.client.host if request.client else "anon")
        if not authz.allow_request(key):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    response = await call_next(request)
    # Operator audit: record every mutating API call (who, what, outcome).
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and request.url.path.startswith("/api/") \
            and not request.url.path.startswith("/api/audit"):
        try:
            actor = authz.name_for(request.headers.get("x-control-token", ""))
            audit.record(actor, f"{request.method} {request.url.path}", status=response.status_code)
        except Exception:
            pass
    return response


def _role(token: str) -> str:
    r = authz.role_for(token)
    if r is None:
        raise HTTPException(status_code=401, detail="invalid control token")
    return r


def _check_token(x_control_token: str = Header(default="")):
    """Any valid role (viewer or operator)."""
    _role(x_control_token)


def _check_operator(x_control_token: str = Header(default="")):
    """Operator role required for mutating actions."""
    if _role(x_control_token) != "operator":
        raise HTTPException(status_code=403, detail="operator role required")


def _resolve_device(device_name: str):
    device = next((d for d in all_devices() if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    return device


@app.get("/api/meta")
def meta():
    """Non-secret UI hints: whether auth is configured (for the setup warning),
    and which optional subsystems are on."""
    auth_configured = bool(authz.load_users()) or bool(CONTROL_CENTER_TOKEN)
    return {"auth_configured": auth_configured, "autopilot_enabled": autopilot.ENABLED,
            "public_status": status_page.enabled()}


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(all_devices())


@app.get("/api/logs/{device_name}/{project_name}")
def proxy_logs(device_name: str, project_name: str, level: str = Query(default="ALL"), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    if level.upper() not in _VALID_LEVELS:
        raise HTTPException(400, f"invalid log level '{level}'")
    result = call_agent(_resolve_device(device_name), f"/api/projects/{project_name}/logs?level={level.upper()}")
    if not result.get("online"):
        raise HTTPException(503, "agent unreachable")
    return result.get("data", {})


@app.get("/api/history/{device_name}/{project_name}")
def project_history(device_name: str, project_name: str, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    return {"history": history.get(device_name, project_name)}


@app.post("/api/action/{device_name}/{project_name}/{action}")
def proxy_action(device_name: str, project_name: str, action: str, force: bool = Query(default=False),
                 x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
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


class TaskIn(BaseModel):
    task: str
    critical: bool = False        # critical work the Sect Leader handles directly
    project: str | None = None    # optional project this task acts on (personal guard)
    device: str | None = None
    repo: str | None = None       # optional GitHub repo (owner/name) for context
    issue: int | None = None      # optional issue/PR number


@app.get("/api/agents")
def list_agents(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"agents": agents.snapshot()}


@app.get("/api/agents/{name}")
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


@app.post("/api/agents/{name}/delegate")
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


@app.post("/api/agents/{name}/task")
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


@app.get("/api/comms")
def comms_feed(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"feed": comms.get_feed(max(1, min(limit, 200))), "status": comms.status()}


@app.post("/api/comms/mission")
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


@app.get("/api/memory")
def memory_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "subdir": memory.SUBDIR}


@app.get("/api/memory/search")
def memory_search(q: str = Query(default=""), limit: int = Query(default=5), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": memory.enabled(), "results": memory.search(q, max(1, min(limit, 20)))}


@app.get("/api/memory/note")
def memory_note(path: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if len(path) > 512:
        raise HTTPException(400, "path too long")
    content = memory.read_note(path)
    if content is None:
        raise HTTPException(404, "note not found")
    return {"path": path, "content": content}


class ToolRunIn(BaseModel):
    tool: str
    args: dict = {}


@app.get("/api/tools")
def tools_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": tooling.enabled(), "tools": tooling.tool_summaries(),
            "calls": tooling.list_calls(), "autonomy": autonomy.status()}


@app.get("/api/tools/audit")
def tools_audit(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if store.enabled():
        return {"persisted": True, "calls": store.load_tool_calls(500)}
    return {"persisted": False, "calls": tooling.list_calls(200)}


@app.post("/api/autonomy/pause")
def autonomy_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(True)


@app.post("/api/autonomy/resume")
def autonomy_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autonomy.set_paused(False)


@app.post("/api/tools/run")
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


@app.post("/api/tools/{call_id}/approve")
def tools_approve(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.approve(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@app.post("/api/tools/{call_id}/deny")
def tools_deny(call_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return tooling.deny(call_id)
    except KeyError:
        raise HTTPException(404, "call not found")


@app.get("/api/usage")
def usage_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.snapshot()


@app.get("/api/usage/series")
def usage_series(hours: int = Query(default=24), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return usage.series(max(1, min(hours, 336)))


@app.get("/api/budget")
def budget_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    from . import budget
    return budget.snapshot()


@app.get("/api/cultivation")
def cultivation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return cultivation.snapshot()


@app.get("/api/reputation")
def reputation_stats(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return reputation.snapshot()


@app.get("/api/prophecy")
def prophecy_omens(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"omens": prophecy.divine()}


@app.get("/api/formations")
def formations_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": formations.catalog()}


class FormationIn(BaseModel):
    formation: str
    goal: str


@app.post("/api/formations/run")
def formations_run(body: FormationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return comms.start_formation(body.formation, body.goal)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/governance")
def governance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return governance.snapshot()


class ChallengeIn(BaseModel):
    challenger: str


@app.post("/api/governance/challenge")
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


@app.post("/api/governance/leader")
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


@app.post("/api/governance/specialty")
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


@app.post("/api/governance/strike-down")
def governance_strike_down(body: StrikeDownIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # only the Ancestor may strike a disciple down
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    try:
        new = lifecycle.strike_down(body.agent, body.reason)
        return {"struck_down": body.agent, "replacement": new["name"]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/tournament")
def tournament_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return tournament.snapshot()


@app.post("/api/tournament/start")
def tournament_start(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)  # the Ancestor calls the Grand Tournament
    try:
        return tournament.hold()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/governance/inbox")
def governance_inbox(limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"messages": governance.inbox(max(1, min(limit, 200)))}


class AncestorMsgIn(BaseModel):
    sender: str
    text: str


@app.post("/api/governance/message")
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
@app.get("/api/nightwatch")
def nightwatch_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return nightwatch.status()


class RotationIn(BaseModel):
    names: list[str] = []


@app.post("/api/nightwatch/rotation")
def nightwatch_rotation(body: RotationIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    names = [n for n in body.names if _SAFE_NAME.match(n or "")]
    return nightwatch.set_rotation(names)


@app.post("/api/nightwatch/{record_id}/handled")
def nightwatch_handled(record_id: int, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"resolved": nightwatch.handled(record_id)}


# ---- Spirit-Root assessment (capability benchmarking) ----
@app.get("/api/spirit-root")
def spirit_root_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"profiles": spirit_root.snapshot(), "probes": spirit_root.PROBES,
            "baseline": spirit_root.BASELINE_PROBES}


class AssessIn(BaseModel):
    agent: str
    results: list[dict] = []


@app.post("/api/spirit-root/assess")
def spirit_root_assess(body: AssessIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid agent name")
    return spirit_root.assess(body.agent, body.results)


# ---- Dreamscape dry-run (formation plan preview) ----
class DreamIn(BaseModel):
    formation: str
    goal: str


@app.post("/api/dreamscape/preview")
def dreamscape_preview(body: DreamIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(body.formation or ""):
        raise HTTPException(400, "invalid formation name")
    try:
        return dreamscape.preview(body.formation, body.goal)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Tribulation Trials (chaos engineering) ----
@app.get("/api/chaos")
def chaos_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return chaos.status()


class SummonIn(BaseModel):
    target: str
    kind: str
    disciple: str | None = None
    inject: bool = False          # actively inject the fault via a guarded tool


@app.post("/api/chaos/summon")
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


@app.post("/api/chaos/{trial_id}/resolve")
def chaos_resolve(trial_id: int, body: ResolveIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return chaos.resolve(trial_id, body.recovered, body.recovery_seconds)
    except KeyError:
        raise HTTPException(404, "trial not found")


# ---- GitHub repos (tracked as projects) ----
@app.get("/api/github")
def github_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"enabled": github_repo.enabled(), "repos": github_repo.collect() if github_repo.enabled() else []}


# ---- Dao-Heart drift detection ----
@app.get("/api/daoheart")
def daoheart_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"drift": daoheart.snapshot()}


# ---- Karmic-bond pairs ----
@app.get("/api/bonds")
def bonds_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return bonds.snapshot()


class BondIn(BaseModel):
    a: str
    b: str


@app.post("/api/bonds/bind")
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


@app.post("/api/bonds/unbind")
def bonds_unbind(body: UnbondIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or ""):
        raise HTTPException(400, "invalid disciple name")
    return {"unbound": bonds.unbind(body.agent)}


# ---- Lineage (knowledge graph) ----
@app.get("/api/lineage")
def lineage_graph(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return lineage.graph()


# ---- Merit-weighted council vote ----
class VoteIn(BaseModel):
    question: str
    votes: dict[str, str]


@app.post("/api/council/vote")
def council_vote_run(body: VoteIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return council_vote.tally(body.question, body.votes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/council/history")
def council_history(limit: int = Query(default=25), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"history": council_vote.history(max(1, min(limit, 100)))}


# ---- Artifact vault ----
@app.get("/api/artifacts")
def artifacts_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return artifacts.snapshot()


class ForgeIn(BaseModel):
    creator: str
    name: str
    kind: str
    content: str
    description: str = ""


@app.post("/api/artifacts/forge")
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


@app.post("/api/artifacts/wield")
def artifacts_wield(body: WieldIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return artifacts.wield(body.agent, body.name)
    except KeyError:
        raise HTTPException(404, "artifact not found")


# ---- Titles & achievements ----
@app.get("/api/titles")
def titles_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": titles.catalog()}


# ---- Cultivation chronicle (per-disciple timeline) ----
@app.get("/api/chronicle")
def chronicle_recent(limit: int = Query(default=50), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"recent": chronicle.recent(max(1, min(limit, 200))), "summary": chronicle.snapshot()}


@app.get("/api/chronicle/{name}")
def chronicle_agent(name: str, limit: int = Query(default=100), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    return {"agent": name, "timeline": chronicle.timeline(name, max(1, min(limit, 200)))}


# ---- Auto-remediation runbooks ----
@app.get("/api/runbooks")
def runbooks_catalog(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"runbooks": runbooks.catalog()}


@app.get("/api/treasury")
def treasury_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return treasury.status()


class EndowIn(BaseModel):
    amount: int


@app.post("/api/treasury/endow")
def treasury_endow(body: EndowIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    amount = int(body.amount or 0)
    if amount <= 0 or amount > 1_000_000:
        raise HTTPException(400, "amount must be 1..1000000")
    treasury.deposit(amount)
    return treasury.status()


class SeclusionIn(BaseModel):
    enter: bool = True


@app.post("/api/agents/{name}/seclusion")
def agent_seclusion(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_seclusion(name) if body.enter else cultivation.exit_seclusion(name)


@app.post("/api/agents/{name}/roaming")
def agent_roaming(name: str, body: SeclusionIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid agent name")
    if agents._agent_def(name) is None:
        raise HTTPException(404, "agent not found")
    return cultivation.enter_roaming(name) if body.enter else cultivation.exit_roaming(name)


class LearnGoalIn(BaseModel):
    skill: str = ""   # empty clears the goal


@app.post("/api/agents/{name}/learn-goal")
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


@app.post("/api/agents/{name}/transmit")
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


@app.get("/api/quests")
def quests_board(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": quests.catalog()}


class QuestIn(BaseModel):
    quest: str


@app.post("/api/agents/{name}/quest")
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


@app.get("/api/pills")
def pills_list(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"catalog": pills.catalog(), "active": pills.active_all()}


@app.post("/api/pills/buy")
def pills_buy(body: PillBuyIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.agent or "") or not _SAFE_NAME.match(body.pill or ""):
        raise HTTPException(400, "invalid agent or pill")
    try:
        return pills.buy(body.agent, body.pill)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class DebateIn(BaseModel):
    topic: str
    a: str
    b: str
    judge: str
    rounds: int = 2


@app.post("/api/comms/debate")
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


@app.post("/api/comms/tournament")
def comms_tournament(body: TournamentIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    parts = [p for p in body.participants if _SAFE_NAME.match(p or "")]
    if not _SAFE_NAME.match(body.judge or ""):
        raise HTTPException(400, "invalid judge name")
    try:
        return comms.start_tournament(body.topic, parts, body.judge, body.rounds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/stream")
def stream(token: str = Query(default="")):
    # EventSource can't send custom headers, so the control token comes as a query param.
    if CONTROL_CENTER_TOKEN and not secrets.compare_digest(token, CONTROL_CENTER_TOKEN):
        raise HTTPException(status_code=401, detail="invalid control token")

    def gen():
        q = events.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    yield f"data: {q.get(timeout=15)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"  # heartbeat keeps the connection alive
        finally:
            events.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- SLO / uptime ----
@app.get("/api/slo")
def slo_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return slo.snapshot(hours if hours > 0 else None)


# ---- Maintenance windows / alert silencing ----
@app.get("/api/maintenance")
def maintenance_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return maintenance.snapshot()


class SilenceIn(BaseModel):
    target: str
    minutes: float = 60.0
    reason: str = ""


@app.post("/api/maintenance/silence")
def maintenance_silence(body: SilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target):
        raise HTTPException(400, "invalid target; use '*', 'device:*', or 'device:project'")
    if body.minutes > 60 * 24 * 30:
        raise HTTPException(400, "minutes too large (max 30 days)")
    return maintenance.silence(target, body.minutes, body.reason)


class UnsilenceIn(BaseModel):
    target: str


@app.post("/api/maintenance/unsilence")
def maintenance_unsilence(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"unsilenced": maintenance.unsilence((body.target or "").strip())}


# ---- Error budgets & deploy-freeze (Karmic Debt / Heavenly Decree) ----
@app.get("/api/errorbudget")
def errorbudget_status(hours: int = Query(default=0), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return errorbudget.snapshot(hours if hours > 0 else None)


# ---- Dependency-aware alerting (Meridian Map) ----
@app.get("/api/meridians")
def meridians_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return meridians.graph()


# ---- Synthetic uptime probes (Warding Talismans) ----
@app.get("/api/talismans")
def talismans_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return talismans.snapshot()


# ---- Incident acknowledgement & ownership (Sworn Oath) ----
@app.get("/api/oaths")
def oaths_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return oaths.snapshot()


class OathIn(BaseModel):
    target: str
    who: str = "operator"
    note: str = ""


@app.post("/api/oaths/claim")
def oaths_claim(body: OathIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    target = (body.target or "").strip()
    if not _SAFE_TARGET.match(target) or target == "*" or target.endswith(":*"):
        raise HTTPException(400, "claim a specific 'device:project'")
    who = (body.who or "operator").strip()
    if not _SAFE_NAME.match(who):
        raise HTTPException(400, "invalid claimant name")
    return oaths.claim(target, who, body.note)


@app.post("/api/oaths/release")
def oaths_release(body: UnsilenceIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"released": oaths.release((body.target or "").strip())}


# ---- Escalation policy (Chain of Command) ----
@app.get("/api/escalation")
def escalation_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return escalation.snapshot()


# ---- Setup & diagnostics / fleet health ----
@app.get("/api/diagnostics")
def diagnostics_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return diagnostics.snapshot()


# ---- Inbound alert ingestion (external systems push incidents in) ----
def _check_ingest(x_control_token: str, x_ingest_token: str):
    if inbound.INGEST_TOKEN and x_ingest_token and secrets.compare_digest(x_ingest_token, inbound.INGEST_TOKEN):
        return
    _check_operator(x_control_token)


class InboundIn(BaseModel):
    title: str
    source: str = "external"
    severity: str = "warning"
    message: str = ""
    project: str = ""
    device: str = ""


@app.post("/api/ingest/alert")
def ingest_alert(body: InboundIn, x_control_token: str = Header(default=""),
                 x_ingest_token: str = Header(default="")):
    _check_ingest(x_control_token, x_ingest_token)
    if not (body.title or "").strip():
        raise HTTPException(400, "title required")
    return inbound.ingest(body.source, body.severity, body.title, body.message, body.project, body.device)


@app.get("/api/inbound")
def inbound_feed(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return inbound.snapshot()


# ---- State backup / restore ----
@app.get("/api/backup")
def backup_export(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return backup.export()


@app.post("/api/restore")
def backup_restore(body: dict, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return backup.restore(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Agent auto-registration ----
class RegisterIn(BaseModel):
    name: str
    url: str
    api_token: str = ""
    timeout: float | None = None


@app.post("/api/agents/register")
def agents_register(body: RegisterIn, x_control_token: str = Header(default=""),
                    x_register_token: str = Header(default="")):
    if registry.REGISTER_TOKEN and x_register_token and secrets.compare_digest(x_register_token, registry.REGISTER_TOKEN):
        pass
    else:
        _check_operator(x_control_token)
    if not _SAFE_NAME.match(body.name or ""):
        raise HTTPException(400, "invalid agent name")
    if not (body.url or "").startswith(("http://", "https://")):
        raise HTTPException(400, "url must start with http:// or https://")
    return registry.register(body.name, body.url, body.api_token, body.timeout)


class DeregisterIn(BaseModel):
    name: str


@app.post("/api/agents/deregister")
def agents_deregister(body: DeregisterIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return {"deregistered": registry.deregister((body.name or "").strip())}


@app.get("/api/registry")
def registry_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return registry.snapshot()


# ---- Login (validate a token) ----
class LoginIn(BaseModel):
    token: str = ""


@app.post("/api/login")
def login(body: LoginIn):
    role = authz.role_for(body.token)
    if role is None:
        raise HTTPException(401, "invalid token")
    return {"ok": True, "role": role, "name": authz.name_for(body.token)}


# ---- Web Push (VAPID) ----
@app.get("/api/push/key")
def push_key(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return push.public_key()


@app.post("/api/push/subscribe")
def push_subscribe(body: dict, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    try:
        return push.subscribe(body.get("subscription") or body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---- Operator audit log ----
@app.get("/api/audit")
def audit_log(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return audit.snapshot()


# ---- Compounding sect memory (shared knowledge) ----
@app.get("/api/sectmemory")
def sectmemory_status(q: str = Query(default=""), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    if q.strip():
        return {"query": q, "results": sectmemory.search(q, 8)}
    return sectmemory.snapshot()


# ---- Autopilot (the Sect Leader's second brain) ----
@app.get("/api/autopilot")
def autopilot_status(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return autopilot.status()


@app.post("/api/autopilot/pause")
def autopilot_pause(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)   # kill switch
    return autopilot.set_paused(True)


@app.post("/api/autopilot/resume")
def autopilot_resume(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    return autopilot.set_paused(False)


# ---- Task board / work queue ----
@app.get("/api/tasks")
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


@app.post("/api/tasks")
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


@app.post("/api/tasks/{task_id}/reassign")
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


@app.post("/api/tasks/{task_id}/status")
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
@app.get("/api/assign/preview")
def assign_preview(goal: str = Query(...), x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return {"goal": goal, "ranked": routing.rank(goal)}


class GoalIn(BaseModel):
    goal: str
    priority: str = "normal"
    dispatch: bool = True


@app.post("/api/assign/goal")
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


@app.post("/api/orchestrate")
def orchestrate_goal(body: OrchestrateIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    try:
        return orchestrator.orchestrate(body.goal, body.max_subtasks, body.dispatch)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


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


@app.get("/api/export/usage")
def export_usage(hours: int = Query(default=168), fmt: str = Query(default="csv"),
                 x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    data = usage.series(max(1, min(hours, 24 * 14)))
    if fmt == "json":
        return data
    rows = ([b["hour"], b["calls"], b["errors"], b["tokens_in"], b["tokens_out"], b["cost"]]
            for b in data["buckets"])
    return _csv_response("usage.csv", ["hour_epoch", "calls", "errors", "tokens_in", "tokens_out", "cost_usd"], rows)


@app.get("/api/export/history")
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


# ---- Health / readiness probes (unauthenticated, no secrets) ----
@app.get("/healthz")
def healthz():
    """Liveness: the process is up and serving."""
    return {"status": "ok"}


@app.get("/readyz")
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


@app.get("/metrics")
def prometheus_metrics():
    # Aggregate stats only (no secrets); standard unauthenticated Prometheus scrape target.
    return PlainTextResponse(metrics_mod.render(), media_type="text/plain; version=0.0.4")


# ---- Public status page (Sect Proclamation) — opt-in, unauthenticated ----
from . import status_page


@app.get("/status")
def public_status_page():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return PlainTextResponse(status_page.render_html(), media_type="text/html")


@app.get("/api/status/public")
def public_status_json():
    if not status_page.enabled():
        raise HTTPException(404, "public status page is disabled (set MAYBOT_PUBLIC_STATUS=1)")
    return status_page.public_data()


@app.get("/api/command")
def command_snapshot(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return command.snapshot()


@app.get("/api/sect/disciples")
def sect_disciples():
    """List authored disciple sprite basenames in static/assets/sect/disciples/
    (e.g. 'atlas_idle', 'nova_walk_4f'). The Realm Map loads only what exists and
    falls back to procedural characters otherwise — so no 404 probing."""
    import os
    d = "maybot_control_center/static/assets/sect/disciples"
    out = [fn[:-4] for fn in sorted(os.listdir(d)) if fn.lower().endswith(".png")] if os.path.isdir(d) else []
    return {"sprites": out}




_CMD = "maybot_control_center/static/command"


@app.get("/")
def home():
    return FileResponse(f"{_CMD}/index.html")


@app.get("/command.js")
def command_js():
    return FileResponse(f"{_CMD}/command.js", media_type="text/javascript")


@app.get("/command.css")
def command_css():
    return FileResponse(f"{_CMD}/command.css", media_type="text/css")


@app.get("/vendor/three.module.js")
def three_js():
    return FileResponse(f"{_CMD}/vendor/three.module.js", media_type="text/javascript")


@app.get("/vendor/OrbitControls.js")
def orbit_controls_js():
    return FileResponse(f"{_CMD}/vendor/OrbitControls.js", media_type="text/javascript")


@app.get("/lib.js")
def command_lib_js():
    return FileResponse(f"{_CMD}/lib.js", media_type="text/javascript")


@app.get("/realm-map")
def realm_map():
    return FileResponse(f"{_CMD}/map.html")


@app.get("/map.js")
def map_js():
    return FileResponse(f"{_CMD}/map.js", media_type="text/javascript")


@app.get("/chamber")
def chamber():
    return FileResponse(f"{_CMD}/chamber.html")


@app.get("/chamber.js")
def chamber_js():
    return FileResponse(f"{_CMD}/chamber.js", media_type="text/javascript")


@app.get("/trade")
def trade():
    return FileResponse(f"{_CMD}/trade.html")


@app.get("/trade.js")
def trade_js():
    return FileResponse(f"{_CMD}/trade.js", media_type="text/javascript")


@app.get("/treasury")
def treasury_page():
    return FileResponse(f"{_CMD}/treasury.html")


@app.get("/treasury.js")
def treasury_js():
    return FileResponse(f"{_CMD}/treasury.js", media_type="text/javascript")


@app.get("/classic")
def classic_home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")


# ---- PWA (installable app + offline shell) ----
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse("maybot_control_center/static/manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse("maybot_control_center/static/sw.js", media_type="text/javascript")


@app.get("/icon.svg")
def icon():
    return FileResponse("maybot_control_center/static/icon.svg", media_type="image/svg+xml")


@app.get("/assets/{path:path}")
def assets(path: str):
    """Serve static assets (Sect Map art, sprites). Rejects path traversal."""
    import os
    base = os.path.realpath("maybot_control_center/static/assets")
    target = os.path.realpath(os.path.join(base, path))
    if os.path.commonpath([base, target]) != base or not os.path.isfile(target):
        raise HTTPException(404, "asset not found")
    return FileResponse(target)
