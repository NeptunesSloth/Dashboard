"""Learning Center — an AI tutor that teaches you topics (Cybersecurity, French,
cert prep, plus your own tracks), generates lessons + quizzes + practice exams,
and runs hands-on labs (spot the intrusion in a synthetic log, CTF-style pentest
scenarios). Grounded in a per-learner profile the AI keeps updating so lessons
adapt to how *you* learn, and wired into the sect cultivation ladder so progress
earns spirit stones and advances your realm.

Structurally this mirrors ``copilot.py``: small functions, each taking an
injectable ``chat=None`` LLM param (defaulting to ``agents._chat``) for tests.

Security: the simulated labs need ZERO command execution — the model generates a
synthetic artifact and the hidden answer is graded server-side. Attaching a REAL
environment (running commands / reading logs on a host) is a deliberately-unbuilt,
deny-by-default phase-2 hook (``attach_real_env``) that must route through the
existing guarded-tools / ``/api/action`` allow-list. LLM text never becomes a shell
command here.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import yaml

from . import agents
from . import store
from . import cultivation

LEARNING_FILE = Path(os.getenv("MAYBOT_LEARNING_FILE", "learning.yaml"))
# The cultivation key for the human learner. Single-operator dashboard, so one
# fixed key (any non-"operator" string works with the cultivation API).
LEARNER = os.getenv("MAYBOT_LEARNER", "scholar")

_lock = threading.RLock()
# In-memory working state (write-through to the store; loaded at startup).
_state: dict = {}


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------
_GUARD = (
    "You teach security defensively and for authorized, simulated practice only. "
    "Labs are self-contained CTF/synthetic exercises — never give instructions aimed "
    "at real third-party systems you do not own."
)
SYSTEM_TUTOR = (
    "You are a patient, encouraging expert tutor. Teach the requested topic clearly and "
    "concretely, building on what the learner already knows. Adapt your explanation to the "
    "learner profile provided (their level, gaps, and preferred style). Keep it focused. "
    + _GUARD
)
SYSTEM_QUIZ = (
    "You are a quiz author. Produce multiple-choice questions that genuinely test "
    "understanding of the topic, calibrated to the learner profile. Respond with ONLY a "
    "JSON object of the exact shape: "
    '{"questions":[{"q":"...","choices":["A","B","C","D"],"answer":0,"explanation":"..."}]}. '
    "`answer` is the 0-based index of the correct choice. No prose outside the JSON."
)
SYSTEM_LAB = (
    "You design hands-on security training labs. Respond with ONLY a JSON object: "
    '{"brief":"what the learner must do","artifact":"the material to analyze (e.g. raw log '
    'lines for an IDS lab, or a scenario for a pentest lab)","answer":"the full expected '
    'finding","indicators":["key thing 1","key thing 2"]}. For an `ids` lab, embed a realistic '
    "intrusion inside otherwise-normal synthetic log lines. For a `pentest` lab, describe a "
    "self-contained CTF target and the finding/flag the learner should report. " + _GUARD
)
SYSTEM_GRADER = (
    "You grade a learner's free-text finding against the expected answer for a security lab. "
    "Be fair but rigorous. Respond with ONLY a JSON object: "
    '{"score":0-100,"feedback":"2-3 sentences: what they got right and what they missed"}.'
)
SYSTEM_PROFILER = (
    "You maintain a concise model of how a particular learner learns, to help a tutor adapt. "
    "Given the prior profile and a note about what just happened, return an UPDATED profile as "
    "ONLY a JSON object of the shape: "
    '{"style_summary":"one sentence","preferences":["..."],"strengths":["..."],"gaps":["..."],'
    '"goals":["..."],"notes":"short"}. Merge sensibly — keep durable goals, refine strengths/gaps '
    "from the new evidence, and keep each list short (<=6 items)."
)

# ---------------------------------------------------------------------------
# badges (id, name, description, predicate(game) -> bool, stones)
# ---------------------------------------------------------------------------
BADGES = [
    ("first_steps", "First Steps", "Finish your first lesson.", lambda g: g.get("lessons_total", 0) >= 1, 10),
    ("scholar", "Diligent Scholar", "Finish 10 lessons.", lambda g: g.get("lessons_total", 0) >= 10, 30),
    ("first_blood", "First Blood", "Solve your first lab.", lambda g: g.get("labs_total", 0) >= 1, 25),
    ("threat_hunter", "Threat Hunter", "Solve 5 intrusion-detection labs.", lambda g: g.get("ids_solved", 0) >= 5, 60),
    ("red_teamer", "Red Teamer", "Solve 3 pentest labs.", lambda g: g.get("pentest_solved", 0) >= 3, 60),
    ("flawless", "Flawless Victory", "Score 100% on a quiz.", lambda g: g.get("flawless", 0) >= 1, 25),
    ("on_fire", "On Fire", "Reach a 7-day streak.", lambda g: g.get("max_streak", 0) >= 7, 50),
    ("unstoppable", "Unstoppable", "Reach a 30-day streak.", lambda g: g.get("max_streak", 0) >= 30, 150),
    ("combo_master", "Combo Master", "Hit a 5-answer combo.", lambda g: g.get("best_combo", 0) >= 5, 30),
    ("exam_ready", "Exam Ready", "Pass a practice exam.", lambda g: g.get("exams_passed", 0) >= 1, 50),
    ("reviewer", "Spaced Learner", "Complete 25 spaced-repetition reviews.", lambda g: g.get("reviews_done", 0) >= 25, 40),
]


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------
def _blank() -> dict:
    return {
        "custom_tracks": {},   # id -> {id,title,topics,labs}
        "progress": {},        # track_id -> {lessons_done, quizzes_done, labs_done, score_sum, score_n, completed_topics}
        "profile": _blank_profile(),
        "game": _blank_game(),
        "quizzes": {},         # quiz_id -> {track, topic, questions:[{q,choices,answer,explanation}], created}
        "labs": {},            # lab_id -> {track, kind, brief, artifact, answer, indicators, created}
        "lessons": {},         # lesson_id -> {id, track, topic, body, created}
        "chats": {},           # track_id -> [{role, content}]
        "reviews": [],         # spaced-repetition cards (SM-2): see _new_card()
        "exams": {},           # exam_id -> {track, questions:[{...,domain}], created}
        "activity": {},        # YYYY-MM-DD -> {lessons, quizzes, labs, reviews, exams, score_sum, score_n}
        "plans": {},           # track_id -> {track, exam_date, created, items:[{date, kind, ref, done}]}
    }


def _blank_profile() -> dict:
    return {"style_summary": "", "preferences": [], "strengths": [], "gaps": [], "goals": [], "notes": ""}


def _blank_game() -> dict:
    return {
        "streak": 0, "max_streak": 0, "last_active_day": "", "freezes": 1,
        "badges": [], "pending_chests": 0,
        "lessons_total": 0, "quizzes_total": 0, "labs_total": 0,
        "ids_solved": 0, "pentest_solved": 0, "flawless": 0,
        "combo": 0, "best_combo": 0, "exams_passed": 0, "reviews_done": 0,
        "quest_day": "", "quests": [],
    }


def load_persisted() -> None:
    """Restore working state from the store (no-op unless MAYBOT_DB is set)."""
    data = store.load_state("learning")
    with _lock:
        base = _blank()
        if isinstance(data, dict):
            base.update({k: data[k] for k in base if k in data})
            # forward-compatible: ensure new game fields exist
            g = _blank_game(); g.update(base.get("game") or {}); base["game"] = g
            p = _blank_profile(); p.update(base.get("profile") or {}); base["profile"] = p
        _state.clear()
        _state.update(base)


def _save() -> None:
    with _lock:
        store.save_state("learning", dict(_state))


def _g() -> dict:
    if not _state:
        _state.update(_blank())
    return _state


# ---------------------------------------------------------------------------
# LLM plumbing (mirrors copilot.py)
# ---------------------------------------------------------------------------
def _backend_member() -> dict | None:
    """First configured member with a usable LLM backend (same rule as the copilot)."""
    for a in agents.file_agents():
        if a.get("base_url") or a.get("provider") in ("claude", "anthropic"):
            return a
    return None


def _extract_json(text: str):
    """Best-effort: parse a JSON object out of a model reply (tolerates code fences)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    raw = m.group(0) if m else text
    try:
        return json.loads(raw)
    except Exception:
        return None


def _profile_brief() -> str:
    p = _g().get("profile") or {}
    parts = []
    if p.get("style_summary"):
        parts.append(f"Style: {p['style_summary']}")
    for label, key in (("Prefers", "preferences"), ("Strengths", "strengths"),
                       ("Gaps", "gaps"), ("Goals", "goals")):
        vals = p.get(key) or []
        if vals:
            parts.append(f"{label}: {', '.join(str(v) for v in vals[:6])}")
    return "\n".join(parts) or "No learner profile yet — start at a beginner level and observe."


def _call(member: dict, system: str, user: str, chat, max_tokens=900, temperature=0.4):
    chat = chat or agents._chat
    return chat(
        {**member, "max_tokens": max_tokens, "temperature": temperature},
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )


# ---------------------------------------------------------------------------
# tracks
# ---------------------------------------------------------------------------
def seed_tracks() -> list[dict]:
    if not LEARNING_FILE.exists():
        return []
    try:
        data = yaml.safe_load(LEARNING_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    tracks = data.get("tracks", [])
    return tracks if isinstance(tracks, list) else []


def _all_tracks() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in seed_tracks():
        if t.get("id"):
            out[t["id"]] = {**t, "builtin": True}
    for tid, t in (_g().get("custom_tracks") or {}).items():
        out[tid] = {**t, "builtin": False}
    return out


def _track(track_id: str) -> dict | None:
    return _all_tracks().get(track_id)


def _track_level(prog: dict) -> dict:
    """Derive a per-track level + mastery bar from lessons/quizzes done and avg score."""
    lessons = prog.get("lessons_done", 0)
    avg = (prog.get("score_sum", 0) / prog.get("score_n", 1)) if prog.get("score_n") else 0
    points = lessons * 10 + prog.get("quizzes_done", 0) * 8 + prog.get("labs_done", 0) * 15
    level = 1 + points // 50
    pct = (points % 50) * 2  # 0..100 toward next level
    return {"level": level, "progress_pct": pct, "avg_score": round(avg)}


def list_tracks() -> dict:
    with _lock:
        prog = _g().get("progress") or {}
        tracks = []
        for tid, t in _all_tracks().items():
            p = prog.get(tid) or {}
            tracks.append({
                "id": tid, "title": t.get("title", tid), "topics": t.get("topics", []),
                "labs": t.get("labs", []), "builtin": t.get("builtin", False),
                "level": _track_level(p), "completed_topics": p.get("completed_topics", []),
            })
        return {"tracks": tracks}


def create_track(title: str, topics: list[str], labs: list[str] | None = None) -> dict:
    title = (title or "").strip()
    if not title:
        return {"error": "title required"}
    tid = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or f"track-{int(time.time())}"
    with _lock:
        custom = _g().setdefault("custom_tracks", {})
        if tid in custom or tid in {t.get("id") for t in seed_tracks()}:
            tid = f"{tid}-{int(time.time()) % 10000}"
        track = {"id": tid, "title": title,
                 "topics": [str(x).strip() for x in (topics or []) if str(x).strip()],
                 "labs": [x for x in (labs or []) if x in ("ids", "pentest")]}
        custom[tid] = track
        _save()
    return {"ok": True, "track": track}


def update_track(track_id: str, title=None, topics=None, labs=None) -> dict:
    with _lock:
        custom = _g().get("custom_tracks") or {}
        t = custom.get(track_id)
        if not t:
            return {"error": "track not found (built-in tracks are read-only)"}
        if title:
            t["title"] = title.strip()
        if topics is not None:
            t["topics"] = [str(x).strip() for x in topics if str(x).strip()]
        if labs is not None:
            t["labs"] = [x for x in labs if x in ("ids", "pentest")]
        _save()
        return {"ok": True, "track": t}


def delete_track(track_id: str) -> dict:
    with _lock:
        custom = _g().get("custom_tracks") or {}
        if track_id not in custom:
            return {"error": "track not found (built-in tracks cannot be deleted)"}
        custom.pop(track_id, None)
        (_g().get("progress") or {}).pop(track_id, None)
        _save()
        return {"ok": True}


def _progress_for(track_id: str) -> dict:
    prog = _g().setdefault("progress", {})
    return prog.setdefault(track_id, {"lessons_done": 0, "quizzes_done": 0, "labs_done": 0,
                                      "score_sum": 0, "score_n": 0, "completed_topics": []})


# ---------------------------------------------------------------------------
# learner profile
# ---------------------------------------------------------------------------
def get_profile() -> dict:
    with _lock:
        return dict(_g().get("profile") or _blank_profile())


def set_profile(patch: dict) -> dict:
    """User-driven edit (set goals / correct the AI's read)."""
    with _lock:
        prof = _g().setdefault("profile", _blank_profile())
        for k in ("style_summary", "notes"):
            if k in patch:
                prof[k] = str(patch[k])
        for k in ("preferences", "strengths", "gaps", "goals"):
            if k in patch and isinstance(patch[k], list):
                prof[k] = [str(x) for x in patch[k]][:6]
        _save()
        return dict(prof)


def _update_profile(event: str, chat=None) -> None:
    """Best-effort: fold what just happened into the learner profile via the LLM."""
    member = _backend_member()
    if not member:
        return
    prior = json.dumps(get_profile())
    ok, text, _ = _call(member, SYSTEM_PROFILER,
                        f"Prior profile:\n{prior}\n\nWhat just happened:\n{event}",
                        chat, max_tokens=400, temperature=0.2)
    if not ok:
        return
    new = _extract_json(text)
    if not isinstance(new, dict):
        return
    with _lock:
        prof = _g().setdefault("profile", _blank_profile())
        if isinstance(new.get("style_summary"), str):
            prof["style_summary"] = new["style_summary"]
        if isinstance(new.get("notes"), str):
            prof["notes"] = new["notes"]
        for k in ("preferences", "strengths", "gaps", "goals"):
            if isinstance(new.get(k), list):
                prof[k] = [str(x) for x in new[k]][:6]
        _save()


# ---------------------------------------------------------------------------
# tutor / lessons
# ---------------------------------------------------------------------------
def get_lesson(track_id: str, topic: str, chat=None) -> dict:
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    user = (f"Track: {track['title']}\nTopic: {topic}\n\nLearner profile:\n{_profile_brief()}\n\n"
            "Teach this topic now: a focused lesson with a clear explanation, one or two worked "
            "examples, and a short 'check yourself' question at the end.")
    ok, text, err = _call(member, SYSTEM_TUTOR, user, chat, max_tokens=1100, temperature=0.5)
    if not ok:
        return {"error": err or "the tutor did not respond"}
    body = (text or "").strip()
    lesson_id = f"ls-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        p = _progress_for(track_id)
        p["lessons_done"] += 1
        if topic and topic not in p["completed_topics"]:
            p["completed_topics"].append(topic)
        _g()["game"]["lessons_total"] = _g()["game"].get("lessons_total", 0) + 1
        lessons = _g().setdefault("lessons", {})
        lessons[lesson_id] = {"id": lesson_id, "track": track_id, "topic": topic,
                              "body": body, "created": int(time.time())}
        # keep the most recent 60 lessons
        if len(lessons) > 60:
            for k in sorted(lessons, key=lambda x: lessons[x]["created"])[:len(lessons) - 60]:
                lessons.pop(k, None)
        _save()
    _award_progress(8)
    _touch_streak()
    _progress_quest("lesson")
    _log_activity("lessons")
    earned = _check_badges()
    _update_profile(f"Completed a lesson on '{topic}' in {track['title']}.", chat)
    return {"lesson_id": lesson_id, "title": topic, "body": body, "member": member.get("name"),
            "awarded": 8, "badges": earned, "error": None}


def list_lessons(track_id: str | None = None) -> dict:
    with _lock:
        items = list((_g().get("lessons") or {}).values())
    if track_id:
        items = [x for x in items if x["track"] == track_id]
    items.sort(key=lambda x: x["created"], reverse=True)
    return {"lessons": [{"id": x["id"], "track": x["track"], "topic": x["topic"],
                         "created": x["created"], "snippet": x["body"][:140]} for x in items]}


def get_saved_lesson(lesson_id: str) -> dict:
    with _lock:
        x = (_g().get("lessons") or {}).get(lesson_id)
    return dict(x) if x else {"error": "lesson not found"}


def get_chat(track_id: str) -> dict:
    with _lock:
        return {"history": list((_g().get("chats") or {}).get(track_id, []))}


def ask_tutor(track_id: str, question: str, history=None, chat=None) -> dict:
    question = (question or "").strip()
    if not question:
        return {"error": "empty question"}
    track = _track(track_id) or {"title": "general study"}
    member = _backend_member()
    if not member:
        return {"answer": "", "member": None, "error": "no_backend"}
    convo = ""
    for turn in (history or [])[-6:]:
        role = "You" if turn.get("role") == "user" else "Tutor"
        convo += f"{role}: {turn.get('content', '')}\n"
    user = (f"Track: {track.get('title')}\n\nLearner profile:\n{_profile_brief()}\n\n"
            + (f"Recent conversation:\n{convo}\n" if convo else "")
            + f"Learner asks: {question}")
    ok, text, err = _call(member, SYSTEM_TUTOR, user, chat, max_tokens=700, temperature=0.5)
    if not ok:
        return {"answer": "", "member": member.get("name"), "error": err or "no response"}
    answer = (text or "").strip()
    tid = _track(track_id) and track_id
    if tid:
        with _lock:
            log = _g().setdefault("chats", {}).setdefault(tid, [])
            log.append({"role": "user", "content": question})
            log.append({"role": "assistant", "content": answer})
            del log[:-40]   # keep last 40 turns
            _save()
    _touch_streak()
    return {"answer": answer, "member": member.get("name"), "error": None}


# ---------------------------------------------------------------------------
# quizzes
# ---------------------------------------------------------------------------
def generate_quiz(track_id: str, topic: str, n: int = 5, chat=None) -> dict:
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    n = max(1, min(10, int(n or 5)))
    user = (f"Track: {track['title']}\nTopic: {topic}\nLearner profile:\n{_profile_brief()}\n\n"
            f"Write {n} multiple-choice questions on this topic.")
    ok, text, err = _call(member, SYSTEM_QUIZ, user, chat, max_tokens=1200, temperature=0.6)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    questions = (data or {}).get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions:
        return {"error": "could not parse quiz from the model"}
    clean = []
    for q in questions[:n]:
        if not isinstance(q, dict) or not q.get("q") or not isinstance(q.get("choices"), list):
            continue
        try:
            ans = int(q.get("answer", 0))
        except Exception:
            ans = 0
        clean.append({"q": str(q["q"]), "choices": [str(c) for c in q["choices"]],
                      "answer": max(0, min(ans, len(q["choices"]) - 1)),
                      "explanation": str(q.get("explanation", ""))})
    if not clean:
        return {"error": "could not parse quiz from the model"}
    quiz_id = f"qz-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("quizzes", {})[quiz_id] = {
            "track": track_id, "topic": topic, "questions": clean, "created": int(time.time())}
        _save()
    # The answer key is never sent to the client.
    public = [{"q": q["q"], "choices": q["choices"]} for q in clean]
    return {"quiz_id": quiz_id, "topic": topic, "questions": public, "error": None}


def grade_quiz(quiz_id: str, answers: list[int], chat=None) -> dict:
    with _lock:
        quiz = (_g().get("quizzes") or {}).get(quiz_id)
    if not quiz:
        return {"error": "unknown or expired quiz"}
    questions = quiz["questions"]
    answers = list(answers or [])
    per = []
    correct = 0
    for i, q in enumerate(questions):
        picked = answers[i] if i < len(answers) else -1
        is_ok = (picked == q["answer"])
        correct += 1 if is_ok else 0
        per.append({"correct": is_ok, "answer": q["answer"], "your_answer": picked,
                    "explanation": q["explanation"]})
    total = len(questions)
    score = round(100 * correct / total) if total else 0
    # Combo + stones: each correct answer builds a combo that multiplies the reward.
    stones = 0
    with _lock:
        g = _g()["game"]
        for r in per:
            if r["correct"]:
                g["combo"] = g.get("combo", 0) + 1
                g["best_combo"] = max(g.get("best_combo", 0), g["combo"])
                mult = 1 + min(g["combo"], 5) * 0.1
                stones += int(round(4 * mult))
            else:
                g["combo"] = 0
        g["quizzes_total"] = g.get("quizzes_total", 0) + 1
        if score == 100:
            g["flawless"] = g.get("flawless", 0) + 1
        p = _progress_for(quiz["track"])
        p["quizzes_done"] += 1
        p["score_sum"] += score
        p["score_n"] += 1
        _save()
    _award_progress(stones)
    _touch_streak()
    _progress_quest("quiz", passed=(score >= 80))
    _log_activity("quizzes", score)
    # Missed questions feed the spaced-repetition deck (due immediately).
    _seed_reviews(quiz["track"], quiz.get("topic", ""),
                  [questions[i] for i, r in enumerate(per) if not r["correct"]])
    earned = _check_badges()
    missed = [questions[i]["q"] for i, r in enumerate(per) if not r["correct"]]
    note = (f"Scored {score}% on a '{quiz.get('topic')}' quiz."
            + (f" Missed: {'; '.join(missed[:4])}." if missed else " Perfect score."))
    _update_profile(note, chat)
    return {"score": score, "correct": correct, "total": total, "per_question": per,
            "awarded": stones, "best_combo": _g()["game"].get("best_combo", 0),
            "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# labs (simulated)
# ---------------------------------------------------------------------------
def generate_lab(track_id: str, kind: str, chat=None) -> dict:
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    if kind not in ("ids", "pentest"):
        return {"error": "kind must be 'ids' or 'pentest'"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    if kind == "ids":
        ask = ("Design an INTRUSION-DETECTION lab. The artifact must be ~15-25 lines of realistic "
               "synthetic server/auth/web logs with a single intrusion hidden among normal traffic. "
               "The learner must identify the attack and the evidence.")
    else:
        ask = ("Design a PENTEST CTF lab: a self-contained, simulated target described in the brief. "
               "The artifact is the scenario (services, hints). The answer is the vulnerability + how "
               "to exploit it in this simulation and the flag/finding to report.")
    user = f"Track: {track['title']}\nLearner profile:\n{_profile_brief()}\n\n{ask}"
    ok, text, err = _call(member, SYSTEM_LAB, user, chat, max_tokens=1300, temperature=0.7)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    if not isinstance(data, dict) or not data.get("artifact") or not data.get("answer"):
        return {"error": "could not parse lab from the model"}
    lab_id = f"lab-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("labs", {})[lab_id] = {
            "track": track_id, "kind": kind, "brief": str(data.get("brief", "")),
            "artifact": str(data["artifact"]), "answer": str(data["answer"]),
            "indicators": [str(x) for x in (data.get("indicators") or [])],
            "created": int(time.time())}
        _save()
    # Hidden answer/indicators stay server-side.
    return {"lab_id": lab_id, "kind": kind, "brief": str(data.get("brief", "")),
            "artifact": str(data["artifact"]), "error": None}


def grade_lab(lab_id: str, finding: str, chat=None) -> dict:
    with _lock:
        lab = (_g().get("labs") or {}).get(lab_id)
    if not lab:
        return {"error": "unknown or expired lab"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    user = (f"Lab brief: {lab['brief']}\n\nExpected answer:\n{lab['answer']}\n\n"
            f"Key indicators: {', '.join(lab['indicators'])}\n\n"
            f"Learner's finding:\n{(finding or '').strip() or '(blank)'}")
    ok, text, err = _call(member, SYSTEM_GRADER, user, chat, max_tokens=400, temperature=0.2)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text) or {}
    try:
        score = max(0, min(100, int(data.get("score", 0))))
    except Exception:
        score = 0
    feedback = str(data.get("feedback", "")).strip()
    solved = score >= 70
    stones = 15 + score // 5 if solved else score // 10
    with _lock:
        g = _g()["game"]
        g["labs_total"] = g.get("labs_total", 0) + 1
        if solved:
            g[f"{lab['kind']}_solved"] = g.get(f"{lab['kind']}_solved", 0) + 1
        p = _progress_for(lab["track"])
        p["labs_done"] += 1
        _save()
    skill = None
    if solved:
        skill = ("Penetration Testing" if lab["kind"] == "pentest" else "Intrusion Detection")
    _award_progress(stones, skill=skill, bonus=10 if solved else 0)
    _touch_streak()
    _progress_quest("lab", passed=solved)
    _log_activity("labs", score)
    earned = _check_badges()
    _update_profile(f"Attempted a {lab['kind']} lab and scored {score}/100. {feedback}", chat)
    return {"score": score, "feedback": feedback, "solved": solved,
            "expected": lab["answer"], "awarded": stones, "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# spaced repetition (SM-2)
# ---------------------------------------------------------------------------
def _new_card(track: str, topic: str, q: dict) -> dict:
    return {"id": f"rv-{int(time.time()*1000)}-{random.randint(100,999)}",
            "track": track, "topic": topic, "q": q["q"], "choices": q["choices"],
            "answer": q["answer"], "explanation": q.get("explanation", ""),
            "ease": 2.5, "interval": 0, "reps": 0, "due": _today(), "created": int(time.time())}


def _seed_reviews(track: str, topic: str, questions: list[dict]) -> None:
    if not questions:
        return
    with _lock:
        deck = _g().setdefault("reviews", [])
        have = {c["q"] for c in deck}
        for q in questions:
            if q.get("q") and q["q"] not in have:
                deck.append(_new_card(track, topic, q))
        del deck[200:]   # cap the deck
        _save()


def due_reviews(limit: int = 20) -> dict:
    today = _today()
    with _lock:
        deck = _g().get("reviews", [])
        due = [c for c in deck if c.get("due", today) <= today]
        total = len(deck)
    due.sort(key=lambda c: c.get("due", today))
    public = [{"id": c["id"], "track": c["track"], "topic": c["topic"],
               "q": c["q"], "choices": c["choices"]} for c in due[:limit]]
    return {"due": public, "due_count": len(due), "deck_size": total}


def grade_review(card_id: str, quality: int) -> dict:
    """SM-2 update. quality 0-5 (0-2 = forgot, 3-5 = recalled)."""
    quality = max(0, min(5, int(quality)))
    with _lock:
        deck = _g().get("reviews", [])
        card = next((c for c in deck if c["id"] == card_id), None)
        if not card:
            return {"error": "unknown review card"}
        correct = card["answer"]
        if quality < 3:
            card["reps"] = 0
            card["interval"] = 1
        else:
            card["reps"] += 1
            if card["reps"] == 1:
                card["interval"] = 1
            elif card["reps"] == 2:
                card["interval"] = 6
            else:
                card["interval"] = int(round(card["interval"] * card["ease"]))
            card["ease"] = max(1.3, card["ease"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        card["due"] = (date.today() + timedelta(days=card["interval"])).isoformat()
        _g()["game"]["reviews_done"] = _g()["game"].get("reviews_done", 0) + 1
        _save()
    stones = 3 if quality >= 3 else 1
    _award_progress(stones)
    _touch_streak()
    _log_activity("reviews")
    earned = _check_badges()
    return {"correct_answer": correct, "explanation": card["explanation"], "next_due": card["due"],
            "interval_days": card["interval"], "awarded": stones, "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# practice exams (timed, multi-domain, pass/fail)
# ---------------------------------------------------------------------------
EXAM_PASS = int(os.getenv("MAYBOT_EXAM_PASS", "75"))


def generate_exam(track_id: str, n: int = 20, chat=None) -> dict:
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    n = max(5, min(40, int(n or 20)))
    topics = ", ".join(track.get("topics", []))
    user = (f"Track: {track['title']}\nDomains/topics: {topics}\nLearner profile:\n{_profile_brief()}\n\n"
            f"Write a {n}-question practice EXAM spanning ALL the domains above, weighted realistically. "
            "Tag each question with its domain (use one of the topic names as the `domain`).")
    sys = SYSTEM_QUIZ.replace(
        '{"q":"...","choices":["A","B","C","D"],"answer":0,"explanation":"..."}',
        '{"q":"...","choices":["A","B","C","D"],"answer":0,"explanation":"...","domain":"..."}')
    ok, text, err = _call(member, sys, user, chat, max_tokens=3500, temperature=0.5)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    qs = (data or {}).get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        return {"error": "could not parse exam from the model"}
    clean = []
    for q in qs[:n]:
        if not isinstance(q, dict) or not q.get("q") or not isinstance(q.get("choices"), list):
            continue
        try:
            ans = int(q.get("answer", 0))
        except Exception:
            ans = 0
        clean.append({"q": str(q["q"]), "choices": [str(c) for c in q["choices"]],
                      "answer": max(0, min(ans, len(q["choices"]) - 1)),
                      "explanation": str(q.get("explanation", "")),
                      "domain": str(q.get("domain", "General"))})
    if not clean:
        return {"error": "could not parse exam from the model"}
    exam_id = f"ex-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("exams", {})[exam_id] = {"track": track_id, "questions": clean,
                                                 "created": int(time.time())}
        _save()
    public = [{"q": q["q"], "choices": q["choices"], "domain": q["domain"]} for q in clean]
    return {"exam_id": exam_id, "title": track["title"], "questions": public,
            "duration_sec": len(clean) * 72, "pass_mark": EXAM_PASS, "error": None}


def grade_exam(exam_id: str, answers: list[int], elapsed: int = 0, chat=None) -> dict:
    with _lock:
        exam = (_g().get("exams") or {}).get(exam_id)
    if not exam:
        return {"error": "unknown or expired exam"}
    questions = exam["questions"]
    answers = list(answers or [])
    per, domains = [], {}
    correct = 0
    for i, q in enumerate(questions):
        picked = answers[i] if i < len(answers) else -1
        ok = (picked == q["answer"])
        correct += 1 if ok else 0
        d = domains.setdefault(q["domain"], {"correct": 0, "total": 0})
        d["total"] += 1
        d["correct"] += 1 if ok else 0
        per.append({"correct": ok, "answer": q["answer"], "your_answer": picked,
                    "explanation": q["explanation"], "domain": q["domain"]})
    total = len(questions)
    score = round(100 * correct / total) if total else 0
    passed = score >= EXAM_PASS
    stones = correct * 3 + (40 if passed else 0)
    with _lock:
        g = _g()["game"]
        if passed:
            g["exams_passed"] = g.get("exams_passed", 0) + 1
        p = _progress_for(exam["track"])
        p["score_sum"] += score
        p["score_n"] += 1
        _save()
    _award_progress(stones, skill=(f"{_track(exam['track'])['title']} Mastery" if passed else None),
                    bonus=20 if passed else 0)
    _touch_streak()
    if passed:
        _progress_quest("quiz", passed=True)
    _log_activity("exams", score)
    earned = _check_badges()
    weak = [d for d, v in domains.items() if v["total"] and v["correct"] / v["total"] < 0.6]
    _update_profile(f"Took a practice exam for {_track(exam['track'])['title']}: {score}%"
                    + (f", weak in {', '.join(weak)}." if weak else ", strong across domains."), chat)
    return {"score": score, "passed": passed, "pass_mark": EXAM_PASS, "correct": correct,
            "total": total, "per_domain": domains, "per_question": per, "weak_domains": weak,
            "awarded": stones, "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# real-environment log labs (read-only) — phase 2 of the labs
# ---------------------------------------------------------------------------
def fetch_real_logs(device: dict, project: str, level: str = "ALL") -> tuple[str, str | None]:
    """Read-only: pull recent logs from a host's agent. No command execution.
    ``device`` is a resolved devices.yaml entry; the caller (app.py) has already
    enforced operator role + per-project ACL, mirroring the /api/logs proxy."""
    from . import agent_client
    res = agent_client.call_agent(device, f"/api/projects/{project}/logs?level={level.upper()}")
    if not res.get("online"):
        return "", res.get("error") or "agent unreachable"
    data = res.get("data") or {}
    lines = data.get("lines") or data.get("log") or []
    if isinstance(lines, list):
        text = "\n".join(str(x.get("line") if isinstance(x, dict) else x) for x in lines)
    else:
        text = str(lines)
    return text[:6000], None


def generate_real_lab(track_id: str, device: str, project: str, logs_text: str, chat=None) -> dict:
    """Build an intrusion-detection lab from REAL logs pulled off a host. The
    learner analyzes the real artifact; the AI grades against its own expert
    read of those same logs."""
    track = _track(track_id) or {"title": "Security"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    logs_text = (logs_text or "").strip()
    if not logs_text:
        return {"error": "no logs returned from that host/project"}
    # Ask the model for an expert analysis of the REAL logs — that becomes the rubric.
    ok, text, err = _call(member, (
        "You are a senior SOC analyst. Analyze these REAL log lines and produce ONLY a JSON object: "
        '{"answer":"what is notable — any suspicious or malicious activity, or a clear all-clear",'
        '"indicators":["..."]}. Be precise; cite evidence from the logs.'),
        f"Logs from {device}/{project}:\n{logs_text}", chat, max_tokens=600, temperature=0.2)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text) or {}
    lab_id = f"lab-{int(time.time()*1000)}-{random.randint(100,999)}"
    brief = (f"Analyze the real logs pulled from {device}/{project}. Identify any intrusion or "
             "suspicious activity and your evidence — or justify an all-clear.")
    with _lock:
        _g().setdefault("labs", {})[lab_id] = {
            "track": track_id, "kind": "real-ids", "brief": brief, "artifact": logs_text,
            "answer": str(data.get("answer", "")), "indicators": [str(x) for x in (data.get("indicators") or [])],
            "source": f"{device}/{project}", "created": int(time.time())}
        _save()
    return {"lab_id": lab_id, "kind": "real-ids", "brief": brief, "artifact": logs_text,
            "source": f"{device}/{project}", "error": None}


# ---------------------------------------------------------------------------
# cultivation / XP
# ---------------------------------------------------------------------------
def _award_progress(stones: int, skill: str | None = None, bonus: int = 0) -> None:
    if stones:
        cultivation.reward(LEARNER, int(stones))
    if skill:
        cultivation.learn(LEARNER, skill, bonus=int(bonus))


# ---------------------------------------------------------------------------
# gamification: streaks, quests, badges, chests
# ---------------------------------------------------------------------------
def _today() -> str:
    return date.today().isoformat()


def _log_activity(kind: str, score: int | None = None) -> None:
    """Record a unit of study for today (drives analytics + reminders)."""
    with _lock:
        day = _g().setdefault("activity", {}).setdefault(
            _today(), {"lessons": 0, "quizzes": 0, "labs": 0, "reviews": 0, "exams": 0,
                       "score_sum": 0, "score_n": 0})
        if kind in day:
            day[kind] += 1
        if score is not None:
            day["score_sum"] += score
            day["score_n"] += 1
        # keep ~1 year
        if len(_g()["activity"]) > 400:
            for k in sorted(_g()["activity"])[:len(_g()["activity"]) - 400]:
                _g()["activity"].pop(k, None)
        _save()


def _touch_streak() -> dict:
    """Advance the daily streak; consume a freeze to survive a single missed day."""
    with _lock:
        g = _g()["game"]
        today = _today()
        last = g.get("last_active_day") or ""
        if last == today:
            return {"streak": g["streak"]}
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last == yesterday:
            g["streak"] = g.get("streak", 0) + 1
        elif last and last < yesterday and g.get("freezes", 0) > 0:
            g["freezes"] -= 1  # a freeze covers the gap; streak survives
            g["streak"] = g.get("streak", 0) + 1
        else:
            g["streak"] = 1
        g["last_active_day"] = today
        g["max_streak"] = max(g.get("max_streak", 0), g["streak"])
        # Streak milestones drop a mystery chest.
        if g["streak"] in (3, 7, 14, 30, 60, 100):
            g["pending_chests"] = g.get("pending_chests", 0) + 1
        _save()
        return {"streak": g["streak"]}


def daily_quests() -> dict:
    """Today's small goals; regenerated each day."""
    pool = [
        {"kind": "lesson", "desc": "Finish a lesson", "need": 1, "reward": 8},
        {"kind": "quiz", "desc": "Pass a quiz (80%+)", "need": 1, "reward": 12},
        {"kind": "lab", "desc": "Solve a hands-on lab", "need": 1, "reward": 18},
    ]
    with _lock:
        g = _g()["game"]
        if g.get("quest_day") != _today():
            picks = random.sample(pool, k=min(3, len(pool)))
            g["quest_day"] = _today()
            g["quests"] = [{**q, "have": 0, "done": False} for q in picks]
            _save()
        return {"day": g["quest_day"], "quests": list(g.get("quests", []))}


def _progress_quest(kind: str, passed: bool = True) -> None:
    if not passed:
        return
    daily_quests()  # ensure today's quests exist
    with _lock:
        g = _g()["game"]
        changed = False
        for q in g.get("quests", []):
            if q["kind"] == kind and not q["done"]:
                q["have"] += 1
                if q["have"] >= q["need"]:
                    q["done"] = True
                    cultivation.reward(LEARNER, int(q.get("reward", 0)))
                    g["pending_chests"] = g.get("pending_chests", 0) + 1
                changed = True
        if changed:
            _save()


def _check_badges() -> list[dict]:
    """Award any newly-earned badges; returns the newly-earned list."""
    earned = []
    with _lock:
        g = _g()["game"]
        have = set(g.get("badges", []))
        for bid, name, desc, test, stones in BADGES:
            if bid not in have and test(g):
                g.setdefault("badges", []).append(bid)
                cultivation.reward(LEARNER, stones)
                earned.append({"id": bid, "name": name, "desc": desc, "stones": stones})
        if earned:
            _save()
    return earned


def open_chest() -> dict:
    """Open one earned mystery chest. Server rolls the (variable) reward so it can't
    be gamed; returns an error if no chest has been earned."""
    with _lock:
        g = _g()["game"]
        if g.get("pending_chests", 0) <= 0:
            return {"error": "no chest available — earn one from a streak milestone or daily quest"}
        g["pending_chests"] -= 1
        roll = random.random()
        if roll < 0.6:
            stones = random.randint(10, 30); rarity = "common"
        elif roll < 0.9:
            stones = random.randint(30, 70); rarity = "rare"
        else:
            stones = random.randint(70, 150); rarity = "legendary"
        _save()
    cultivation.reward(LEARNER, stones)
    return {"stones": stones, "rarity": rarity, "remaining": g.get("pending_chests", 0), "error": None}


def _badge_catalog(have: list[str]) -> list[dict]:
    return [{"id": b[0], "name": b[1], "desc": b[2], "earned": b[0] in (have or [])} for b in BADGES]


# ---------------------------------------------------------------------------
# progress summary
# ---------------------------------------------------------------------------
def get_progress() -> dict:
    daily_quests()  # keep today's quests fresh
    with _lock:
        g = dict(_g()["game"])
        prog = _g().get("progress") or {}
        track_levels = {tid: _track_level(p) for tid, p in prog.items()}
    realm = cultivation.state(LEARNER)
    return {
        "learner": LEARNER,
        "realm": realm,
        "reviews_due": due_reviews()["due_count"],
        "streak": g.get("streak", 0),
        "max_streak": g.get("max_streak", 0),
        "freezes": g.get("freezes", 0),
        "combo": g.get("combo", 0),
        "best_combo": g.get("best_combo", 0),
        "pending_chests": g.get("pending_chests", 0),
        "badges": _badge_catalog(g.get("badges", [])),
        "earned_badges": len(g.get("badges", [])),
        "track_levels": track_levels,
        "totals": {k: g.get(k, 0) for k in ("lessons_total", "quizzes_total", "labs_total",
                                            "ids_solved", "pentest_solved")},
        "daily_quests": g.get("quests", []),
    }


# ---------------------------------------------------------------------------
# progress analytics
# ---------------------------------------------------------------------------
def get_analytics(days: int = 120) -> dict:
    """Heatmap, accuracy trend, totals and per-skill mastery for the dashboard."""
    with _lock:
        activity = dict(_g().get("activity") or {})
        prog = dict(_g().get("progress") or {})
        game = dict(_g()["game"])
    today = date.today()
    heatmap, trend = [], []
    studied_days = 0
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        a = activity.get(d, {})
        count = sum(a.get(k, 0) for k in ("lessons", "quizzes", "labs", "reviews", "exams"))
        if count:
            studied_days += 1
        heatmap.append({"date": d, "count": count})
        if a.get("score_n"):
            trend.append({"date": d, "accuracy": round(a["score_sum"] / a["score_n"])})
    totals = {k: sum(a.get(k, 0) for a in activity.values())
              for k in ("lessons", "quizzes", "labs", "reviews", "exams")}
    mastery = []
    for tid, p in prog.items():
        t = _track(tid)
        if t:
            mastery.append({"track": t.get("title", tid), "level": _track_level(p)["level"],
                            "avg_score": _track_level(p)["avg_score"],
                            "topics_done": len(p.get("completed_topics", [])),
                            "topics_total": len(t.get("topics", []))})
    realm = cultivation.state(LEARNER)
    return {"heatmap": heatmap, "accuracy_trend": trend, "totals": totals, "mastery": mastery,
            "active_days": studied_days, "streak": game.get("streak", 0),
            "max_streak": game.get("max_streak", 0), "skills": realm.get("skills", []),
            "realm": realm.get("realm_name"), "stones": realm.get("stones", 0)}


# ---------------------------------------------------------------------------
# study plan toward an exam date (deterministic schedule, no LLM needed)
# ---------------------------------------------------------------------------
def create_plan(track_id: str, exam_date: str) -> dict:
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    try:
        target = date.fromisoformat(exam_date)
    except Exception:
        return {"error": "exam_date must be YYYY-MM-DD"}
    today = date.today()
    days = (target - today).days
    if days < 1:
        return {"error": "exam_date must be in the future"}
    topics = track.get("topics", []) or ["Study"]
    # Build the task list: one lesson per topic, a review every ~3rd task, two mock
    # exams in the back third, and a final review the day before.
    tasks = []
    for idx, tp in enumerate(topics):
        tasks.append({"kind": "lesson", "ref": tp})
        if idx % 3 == 2:
            tasks.append({"kind": "review", "ref": "Spaced review"})
    tasks.append({"kind": "exam", "ref": f"Practice exam — {track['title']}"})
    if days >= 5:
        tasks.insert(max(1, len(tasks) - 1), {"kind": "review", "ref": "Spaced review"})
        tasks.append({"kind": "exam", "ref": "Final practice exam"})
    # Spread tasks across the available study days (leave exam day for rest).
    study_days = max(1, days - 1)
    items = []
    for i, task in enumerate(tasks):
        offset = round(i * (study_days - 1) / max(1, len(tasks) - 1)) if len(tasks) > 1 else 0
        items.append({"date": (today + timedelta(days=offset)).isoformat(),
                      "kind": task["kind"], "ref": task["ref"], "done": False})
    plan = {"track": track_id, "title": track["title"], "exam_date": exam_date,
            "created": _today(), "items": items}
    with _lock:
        _g().setdefault("plans", {})[track_id] = plan
        _save()
    return {"ok": True, "plan": _plan_status(plan)}


def _plan_status(plan: dict) -> dict:
    today = _today()
    items = plan.get("items", [])
    due = [it for it in items if it["date"] <= today]
    done_due = [it for it in due if it["done"]]
    done_all = [it for it in items if it["done"]]
    target = plan.get("exam_date", today)
    try:
        days_left = (date.fromisoformat(target) - date.today()).days
    except Exception:
        days_left = 0
    return {**plan, "days_left": max(0, days_left), "total": len(items),
            "done": len(done_all), "due": len(due), "done_due": len(done_due),
            "on_track": len(done_due) >= len(due)}


def get_plan(track_id: str) -> dict:
    with _lock:
        plan = (_g().get("plans") or {}).get(track_id)
    return {"plan": _plan_status(plan) if plan else None}


def complete_plan_item(track_id: str, index: int, done: bool = True) -> dict:
    with _lock:
        plan = (_g().get("plans") or {}).get(track_id)
        if not plan or index < 0 or index >= len(plan["items"]):
            return {"error": "plan item not found"}
        plan["items"][index]["done"] = bool(done)
        _save()
        status = _plan_status(plan)
    if done:
        _award_progress(5)
        _touch_streak()
    return {"ok": True, "plan": status}


# ---------------------------------------------------------------------------
# reminders / re-engagement nudges (uses the existing notify channels)
# ---------------------------------------------------------------------------
REMINDERS_ON = os.getenv("MAYBOT_LEARNING_REMINDERS", "0").lower() in ("1", "true", "yes", "on")
_reminder_started = False


def reminder_status() -> dict:
    from . import notify
    with _lock:
        g = _g()["game"]
        streak = g.get("streak", 0)
        active_today = g.get("last_active_day") == _today()
    return {"reviews_due": due_reviews()["due_count"], "streak": streak,
            "active_today": active_today, "streak_at_risk": streak > 0 and not active_today,
            "channels": notify.channels(), "enabled": REMINDERS_ON}


def send_reminder(force: bool = False) -> dict:
    """Nudge the learner if reviews are due or the streak is at risk (once/day)."""
    from . import notify
    st = reminder_status()
    with _lock:
        g = _g()["game"]
        if not force and g.get("last_reminder_day") == _today():
            return {"sent": False, "reason": "already sent today"}
        if not force and not (st["reviews_due"] or st["streak_at_risk"]):
            return {"sent": False, "reason": "nothing to nudge about"}
        g["last_reminder_day"] = _today()
        _save()
    bits = []
    if st["streak_at_risk"]:
        bits.append(f"🔥 Your {st['streak']}-day streak is at risk — study today to keep it.")
    if st["reviews_due"]:
        bits.append(f"🔁 {st['reviews_due']} spaced-repetition card(s) are due.")
    if not bits:
        bits.append("📚 Time for today's lesson.")
    res = notify.send("Learning Center reminder", " ".join(bits), level="info", kind="learning")
    return {"sent": True, "delivered": res.get("delivered", []), "message": " ".join(bits)}


def _reminder_loop() -> None:
    import time as _t
    while True:
        _t.sleep(1800)  # every 30 min; send_reminder de-dupes to once/day
        try:
            hour = int(_t.strftime("%H"))
            if 8 <= hour <= 22:  # daytime nudges only
                send_reminder()
        except Exception:
            pass


def start() -> bool:
    """Background reminder thread (no-op unless MAYBOT_LEARNING_REMINDERS is set)."""
    global _reminder_started
    if _reminder_started or not REMINDERS_ON:
        return False
    _reminder_started = True
    threading.Thread(target=_reminder_loop, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# PHASE 2 (optional) — real environment hook. Intentionally unbuilt.
# ---------------------------------------------------------------------------
def attach_real_env(exercise: dict, device_name: str, project_name: str) -> dict | None:
    """PHASE 3 (not built): COMMAND-EXECUTION labs. Running an allow-listed
    recon/exploit command on a real target (vs. the read-only log analysis in
    ``generate_real_lab``) would route via the operator-approved ``tools.yaml`` /
    ``/api/action`` allow-list — LLM text must never become a shell command.
    Returns ``None``. The read-only real-log lab is implemented above and is the
    only real-environment path that touches a host."""
    return None
