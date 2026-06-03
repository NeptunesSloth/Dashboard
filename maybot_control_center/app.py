import queue
import re
import secrets
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from .config import load_devices, CONTROL_CENTER_TOKEN
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

# Restore persisted state (no-op unless MAYBOT_DB is set).
store.init()
for _loader in (history.load_persisted, agents.load_persisted, comms.load_persisted,
                tooling.load_persisted, usage.load_persisted, cultivation.load_persisted,
                treasury.load_persisted):
    try:
        _loader()
    except Exception:
        pass
scheduler.start()  # background cron for scheduled missions (no-op without schedules.yaml)

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_\-\.]{1,128}$')
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
    return await call_next(request)


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
    device = next((d for d in load_devices() if d.get("name") == device_name), None)
    if not device:
        raise HTTPException(404, "device not found")
    return device


@app.get("/api/overview")
def overview(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return aggregate(load_devices())


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
def proxy_action(device_name: str, project_name: str, action: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(device_name) or not _SAFE_NAME.match(project_name):
        raise HTTPException(400, "invalid device or project name")
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, f"unknown action '{action}'; must be one of {sorted(_VALID_ACTIONS)}")
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


@app.post("/api/chaos/summon")
def chaos_summon(body: SummonIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if body.disciple and not _SAFE_NAME.match(body.disciple):
        raise HTTPException(400, "invalid disciple name")
    try:
        return chaos.summon(body.target, body.kind, body.disciple)
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


@app.get("/metrics")
def prometheus_metrics():
    # Aggregate stats only (no secrets); standard unauthenticated Prometheus scrape target.
    return PlainTextResponse(metrics_mod.render(), media_type="text/plain; version=0.0.4")


@app.get("/")
def home():
    return FileResponse("maybot_control_center/static/index.html")


@app.get("/app.js")
def js():
    return FileResponse("maybot_control_center/static/app.js")


@app.get("/style.css")
def css():
    return FileResponse("maybot_control_center/static/style.css")
