"""Learning Center API routes (extracted from app.py).

Mounted by ``app.py`` via ``app.include_router(learning.router)``. Handlers gate
on the shared ``deps`` helpers and delegate to the ``learning`` feature module.
"""
from __future__ import annotations

import json as _json

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import authz
from ..aggregator import aggregate
from ..config import all_devices
from ..deps import (
    SAFE_NAME,
    check_operator,
    check_project_access,
    check_token,
    resolve_device,
)

router = APIRouter()


class TrackIn(BaseModel):
    title: str
    topics: list[str] = []
    labs: list[str] = []


class TrackPatch(BaseModel):
    title: str | None = None
    topics: list[str] | None = None
    labs: list[str] | None = None


class AskIn(BaseModel):
    track: str
    question: str
    history: list[dict] = []


class QuizIn(BaseModel):
    track: str
    topic: str
    n: int = 5


class QuizGradeIn(BaseModel):
    quiz_id: str
    answers: list[int] = []


class LabIn(BaseModel):
    track: str
    kind: str


class LabGradeIn(BaseModel):
    lab_id: str
    finding: str = ""
    evidence: str = ""


class ProfileIn(BaseModel):
    style_summary: str | None = None
    preferences: list[str] | None = None
    strengths: list[str] | None = None
    gaps: list[str] | None = None
    goals: list[str] | None = None
    notes: str | None = None


class ReviewGradeIn(BaseModel):
    card_id: str
    quality: int


class ExamIn(BaseModel):
    track: str
    n: int = 20


class ExamGradeIn(BaseModel):
    exam_id: str
    answers: list[int] = []
    elapsed: int = 0


class RealLabIn(BaseModel):
    track: str = "cybersecurity"
    device: str
    project: str


class PlanIn(BaseModel):
    track: str
    exam_date: str


class PlanItemIn(BaseModel):
    track: str
    index: int
    done: bool = True


@router.get("/api/learning/tracks")
def learning_tracks(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.list_tracks()


@router.post("/api/learning/tracks")
def learning_track_create(body: TrackIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.create_track(body.title, body.topics, body.labs)


@router.put("/api/learning/tracks/{track_id}")
def learning_track_update(track_id: str, body: TrackPatch, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.update_track(track_id, title=body.title, topics=body.topics, labs=body.labs)


@router.delete("/api/learning/tracks/{track_id}")
def learning_track_delete(track_id: str, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.delete_track(track_id)


@router.get("/api/learning/lesson")
def learning_lesson(track: str, topic: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_lesson(track, topic)


@router.post("/api/learning/ask")
def learning_ask(body: AskIn, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.ask_tutor(body.track, body.question, body.history)


@router.post("/api/learning/ask/stream")
def learning_ask_stream(body: AskIn, x_control_token: str = Header(default="")):
    """Streaming tutor reply (server-sent events): meta -> token* -> done/error."""
    check_token(x_control_token)
    from .. import learning

    def gen():
        try:
            for event in learning.ask_tutor_stream(body.track, body.question, body.history):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/learning/quiz")
def learning_quiz(body: QuizIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_quiz(body.track, body.topic, body.n)


@router.post("/api/learning/quiz/grade")
def learning_quiz_grade(body: QuizGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_quiz(body.quiz_id, body.answers)


@router.post("/api/learning/lab")
def learning_lab(body: LabIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_lab(body.track, body.kind)


@router.post("/api/learning/lab/grade")
def learning_lab_grade(body: LabGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_lab(body.lab_id, body.finding, evidence=body.evidence)


class LabHintIn(BaseModel):
    lab_id: str


@router.post("/api/learning/lab/hint")
def learning_lab_hint(body: LabHintIn, x_control_token: str = Header(default="")):
    """Spend spirit stones for one mentor nudge on an open lab."""
    check_operator(x_control_token)
    from .. import learning
    return learning.lab_hint(body.lab_id)


class PlacementIn(BaseModel):
    track: str
    topic: str
    n: int = 6


class PlacementGradeIn(BaseModel):
    quiz_id: str
    answers: list[int] = []


@router.post("/api/learning/placement")
def learning_placement(body: PlacementIn, x_control_token: str = Header(default="")):
    """Generate a test-out challenge to skip a topic you already know."""
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_placement(body.track, body.topic, body.n)


@router.post("/api/learning/placement/grade")
def learning_placement_grade(body: PlacementGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_placement(body.quiz_id, body.answers)


# ---- language drills (cloze / translation) ----
class DrillIn(BaseModel):
    track: str
    topic: str
    kind: str = "cloze"
    n: int = 6


class DrillGradeIn(BaseModel):
    drill_id: str
    answers: list[str] = []


@router.post("/api/learning/drill")
def learning_drill(body: DrillIn, x_control_token: str = Header(default="")):
    """Generate a cloze or translation drill for a language track."""
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_drill(body.track, body.topic, body.kind, body.n)


@router.post("/api/learning/drill/grade")
def learning_drill_grade(body: DrillGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_drill(body.drill_id, body.answers)


# ---- end-to-end pentest range ----
class RangeIn(BaseModel):
    track: str = "cybersecurity"


class RangeHostIn(BaseModel):
    range_id: str
    host_id: str


class RangeExploitIn(BaseModel):
    range_id: str
    host_id: str
    finding: str = ""
    evidence: str = ""


@router.post("/api/learning/range")
def learning_range(body: RangeIn, x_control_token: str = Header(default="")):
    """Generate a simulated multi-stage pentest range (virtual network)."""
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_range(body.track)


@router.get("/api/learning/range/{range_id}")
def learning_range_state(range_id: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_range(range_id)


@router.post("/api/learning/range/enumerate")
def learning_range_enumerate(body: RangeHostIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.range_enumerate(body.range_id, body.host_id)


@router.post("/api/learning/range/exploit")
def learning_range_exploit(body: RangeExploitIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.range_exploit(body.range_id, body.host_id, body.finding, evidence=body.evidence)


class RangeCaptureIn(BaseModel):
    range_id: str
    submission: str = ""


@router.post("/api/learning/range/capture")
def learning_range_capture(body: RangeCaptureIn, x_control_token: str = Header(default="")):
    """Complete the engagement objective — extract the target file/secret."""
    check_operator(x_control_token)
    from .. import learning
    return learning.range_capture(body.range_id, body.submission)


class RangePostExIn(BaseModel):
    range_id: str
    host_id: str
    plan: str = ""


@router.post("/api/learning/range/escalate")
def learning_range_escalate(body: RangePostExIn, x_control_token: str = Header(default="")):
    """Privilege escalation: foothold -> admin/root on a compromised host."""
    check_operator(x_control_token)
    from .. import learning
    return learning.range_escalate(body.range_id, body.host_id, body.plan)


@router.post("/api/learning/range/persist")
def learning_range_persist(body: RangePostExIn, x_control_token: str = Header(default="")):
    """Establish persistence on a compromised host."""
    check_operator(x_control_token)
    from .. import learning
    return learning.range_persist(body.range_id, body.host_id, body.plan)


class RangeHintIn(BaseModel):
    range_id: str
    host_id: str
    stage: str = ""


@router.post("/api/learning/range/hint")
def learning_range_hint(body: RangeHintIn, x_control_token: str = Header(default="")):
    """Stuck? Spend spirit stones for a nudge on a host (never the answer)."""
    check_operator(x_control_token)
    from .. import learning
    return learning.range_hint(body.range_id, body.host_id, body.stage)


@router.get("/api/learning/rank")
def learning_rank(x_control_token: str = Header(default="")):
    """The learner's standing versus real job-field roles (junior … head)."""
    check_token(x_control_token)
    from .. import learning
    return learning.skill_rank()


@router.get("/api/learning/mastery")
def learning_mastery(x_control_token: str = Header(default="")):
    """Per-domain mastery (web vs AD vs cloud …) — each tracked independently."""
    check_token(x_control_token)
    from .. import learning
    return learning.domain_mastery()


@router.get("/api/learning/skills")
def learning_skills(x_control_token: str = Header(default="")):
    """The skill dependency graph — what's mastered, unlocked, and locked."""
    check_token(x_control_token)
    from .. import learning
    return learning.skill_graph()


# ---- graduation (real execution required, not simulation) ----
@router.get("/api/learning/graduation")
def learning_graduation(x_control_token: str = Header(default="")):
    """Whether the learner has graduated — proven career-ready by real execution."""
    check_token(x_control_token)
    from .. import learning
    return learning.graduation_status()


class ExecutionProofIn(BaseModel):
    domain: str = ""
    summary: str
    lab: str = ""
    tool: str = ""
    verified: bool = False


@router.post("/api/learning/execution-proof")
def learning_execution_proof(body: ExecutionProofIn, x_control_token: str = Header(default="")):
    """Record proof the learner executed against a real sandbox target. Operator-
    gated; only verified proofs count toward graduation."""
    check_operator(x_control_token)
    from .. import learning
    return learning.record_execution_proof(body.domain, body.summary, verified=body.verified,
                                           lab=body.lab, tool=body.tool)


# ---- canonical knowledge base (ground truth) ----
@router.get("/api/learning/knowledge")
def learning_knowledge(q: str = Query(default=""), x_control_token: str = Header(default="")):
    """Search the verified knowledge base (ATT&CK / CVE / OWASP / NIST) that
    anchors generated content, or get its summary when no query is given."""
    check_token(x_control_token)
    from .. import knowledge
    if q.strip():
        return {"query": q, "results": knowledge.search(q, 25)}
    return knowledge.snapshot()


# ---- bring-your-own material (RAG) ----
class MaterialIn(BaseModel):
    track: str
    text: str
    name: str = ""


@router.post("/api/learning/material")
def learning_material_set(body: MaterialIn, x_control_token: str = Header(default="")):
    """Attach your own notes/document text to a track; lessons + quizzes + exams
    are then grounded in it."""
    check_operator(x_control_token)
    from .. import learning
    return learning.set_material(body.track, body.text, body.name)


@router.get("/api/learning/material")
def learning_material_get(track: str = Query(...), x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_material(track)


@router.delete("/api/learning/material")
def learning_material_clear(track: str = Query(...), x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.clear_material(track)


@router.get("/api/learning/real-env")
def learning_real_env(x_control_token: str = Header(default="")):
    """Whether real-command (sandboxed) labs are wired — default off."""
    check_token(x_control_token)
    from .. import learning
    return learning.real_env_status()


@router.get("/api/learning/pentest-tools")
def learning_pentest_tools(kind: str = Query(default=""), x_control_token: str = Header(default="")):
    """The real-world pentest toolkit (optionally for a host kind) so the range
    teaches which tool fits which stage."""
    check_token(x_control_token)
    from .. import learning
    return {"tools": learning.recommended_pentest_tools(kind or None),
            "gui_tools": list(learning.PENTEST_GUI_TOOLS)}


# ---- blue-team incident investigation ----
class IncidentIn(BaseModel):
    track: str = "blue-team"


class IncidentGradeIn(BaseModel):
    incident_id: str
    findings: str = ""


@router.post("/api/learning/incident")
def learning_incident(body: IncidentIn, x_control_token: str = Header(default="")):
    """Generate a defensive incident-investigation exercise (scope the compromise)."""
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_incident(body.track)


@router.post("/api/learning/incident/grade")
def learning_incident_grade(body: IncidentGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_incident(body.incident_id, body.findings)


@router.get("/api/learning/progress")
def learning_progress(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_progress()


@router.get("/api/learning/profile")
def learning_profile(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_profile()


@router.put("/api/learning/profile")
def learning_profile_set(body: ProfileIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.set_profile({k: v for k, v in body.dict().items() if v is not None})


@router.get("/api/learning/quests")
def learning_quests(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.daily_quests()


@router.post("/api/learning/chest/open")
def learning_chest_open(x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.open_chest()


@router.get("/api/learning/lessons")
def learning_lessons(track: str = Query(default=""), x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.list_lessons(track or None)


@router.get("/api/learning/lessons/{lesson_id}")
def learning_lesson_get(lesson_id: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_saved_lesson(lesson_id)


@router.get("/api/learning/chat")
def learning_chat(track: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_chat(track)


@router.get("/api/learning/reviews")
def learning_reviews(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.due_reviews()


@router.post("/api/learning/reviews/grade")
def learning_review_grade(body: ReviewGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_review(body.card_id, body.quality)


@router.post("/api/learning/exam")
def learning_exam(body: ExamIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.generate_exam(body.track, body.n)


@router.post("/api/learning/exam/grade")
def learning_exam_grade(body: ExamGradeIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.grade_exam(body.exam_id, body.answers, body.elapsed)


@router.get("/api/learning/lab/sources")
def learning_lab_sources(x_control_token: str = Header(default="")):
    """Host/project pairs whose real logs can be pulled into a log-analysis lab."""
    check_token(x_control_token)
    ov = aggregate(all_devices())
    out = []
    for p in ov.get("projects", []) or []:
        if authz.can_access_project(x_control_token, p.get("device"), p.get("name")):
            out.append({"device": p.get("device"), "project": p.get("name"), "type": p.get("type")})
    return {"sources": out}


@router.get("/api/learning/lab/targets")
def learning_lab_targets(x_control_token: str = Header(default="")):
    """Built-in catalog of Docker-based pentest/IDS lab TARGETS (labs/). Read-only
    catalog data — the operator runs the targets; the dashboard executes nothing."""
    check_token(x_control_token)
    from .. import learning
    return {"targets": learning.list_lab_targets()}


@router.post("/api/learning/lab/real")
def learning_lab_real(body: RealLabIn, x_control_token: str = Header(default="")):
    """Read-only: pull a host's real logs (same path/ACL as /api/logs) and turn
    them into an intrusion-detection lab. No command execution."""
    check_operator(x_control_token)
    if not SAFE_NAME.match(body.device) or not SAFE_NAME.match(body.project):
        raise HTTPException(400, "invalid device or project name")
    check_project_access(x_control_token, body.device, body.project)
    from .. import learning
    logs, err = learning.fetch_real_logs(resolve_device(body.device), body.project)
    if err:
        raise HTTPException(503, err)
    return learning.generate_real_lab(body.track, body.device, body.project, logs)


@router.get("/api/learning/analytics")
def learning_analytics(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_analytics()


@router.post("/api/learning/plan")
def learning_plan_create(body: PlanIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.create_plan(body.track, body.exam_date)


@router.get("/api/learning/plan")
def learning_plan_get(track: str, x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.get_plan(track)


@router.post("/api/learning/plan/item")
def learning_plan_item(body: PlanItemIn, x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.complete_plan_item(body.track, body.index, body.done)


@router.get("/api/learning/reminders")
def learning_reminders(x_control_token: str = Header(default="")):
    check_token(x_control_token)
    from .. import learning
    return learning.reminder_status()


@router.post("/api/learning/remind")
def learning_remind(x_control_token: str = Header(default="")):
    check_operator(x_control_token)
    from .. import learning
    return learning.send_reminder(force=True)
