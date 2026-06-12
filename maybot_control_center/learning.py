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
# Catalog of Docker-based pentest/IDS lab targets the OPERATOR runs (labs/). This
# is read-only seed DATA — list_lab_targets() returns it and NOTHING here executes
# a command. See labs/README.md for the read-only boundary.
LAB_TARGETS_FILE = Path(os.getenv("MAYBOT_LAB_TARGETS_FILE", "lab_targets.yaml"))
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
# Language tracks get a tutor built around proven second-language acquisition:
# comprehensible input (mostly the target language, scaffolded), retrieval
# practice, learner PRODUCTION with gentle corrective recasts, spaced repetition,
# and high-frequency vocab first.
LANG_METHODS = (
    "Use evidence-based language teaching: (1) COMPREHENSIBLE INPUT — speak mostly in {lang} at a "
    "level just above the learner's, with brief English glosses in (parentheses) for anything new; "
    "(2) HIGH-FREQUENCY first — prioritise the most common words/structures; "
    "(3) RETRIEVAL — make the learner recall and PRODUCE {lang}, don't just present it; "
    "(4) CORRECTIVE RECASTS — when they err, restate it correctly and naturally, briefly noting why; "
    "(5) keep it communicative and contextual, not grammar-rules in isolation. "
    "Always end a lesson by prompting the learner to produce 1-2 sentences of their own in {lang}."
)
SYSTEM_LANG_TUTOR = (
    "You are a warm, patient {lang} tutor and conversation partner. " + LANG_METHODS
)
SYSTEM_DRILL = (
    "You write short {lang} practice drills for active recall and production. Respond with ONLY a "
    "JSON object: {\"items\":[{\"prompt\":\"what the learner sees\",\"answer\":\"the exact expected "
    "response\",\"accept\":[\"other acceptable answers\"],\"hint\":\"a short hint\",\"explain\":\"one-line why\"}]}. "
    "For a `cloze` drill, `prompt` is a natural {lang} sentence with one blank as ___ and `answer` is "
    "the missing word/phrase. For a `translate` drill, `prompt` is a short English sentence and "
    "`answer` is its natural {lang} translation; put any equally-valid translations in `accept`. "
    "Use high-frequency vocabulary. No prose outside JSON."
)
SYSTEM_RANGE = (
    "You design SIMULATED, end-to-end penetration-testing ranges for authorized training. "
    "Respond with ONLY a JSON object describing a small virtual network the learner attacks "
    "stage by stage toward a CONCRETE OBJECTIVE:\n"
    '{"scenario":"1-2 sentence engagement brief (who hired you, rules of engagement)",'
    '"objective":{"goal":"a specific real-world mission, e.g. exfiltrate the file '
    '/srv/finance/payroll_2026.xlsx from the domain controller","target_host":"the host id holding '
    'it","flag":"the exact secret/file-contents the learner must produce to prove capture"},'
    '"entry_points":["host id the learner can reach first"],'
    '"hosts":[{"id":"h1","hostname":"...","ip":"10.0.0.x","kind":"router|workstation|server|web|db|'
    'dc|fileshare|iot|cloud","services":[{"port":22,"name":"ssh","version":"..."}],'
    '"enum_hint":"what enumeration reveals here","vuln":"the specific weakness","exploit":"how it is '
    'exploited in THIS simulation","loot":"credentials/keys/data gained, used to pivot","pivots_to":'
    '["host ids this loot unlocks"]}]}.\n'
    "Build a realistic kill chain: a reachable foothold, then lateral movement across DIFFERENT device "
    "kinds (e.g. web server -> database -> workstation -> domain controller), where each host's loot "
    "unlocks the next, and the OBJECTIVE lives on the deepest host (target_host should have no further "
    "pivots). 4-7 hosts. Mix services/versions realistically. Keep vuln/exploit/loot/flag HIDDEN from "
    "the brief — the learner must discover them. " + _GUARD
)
# Grade an exploit attempt on REAL TRADECRAFT, not buzzword-matching: reward
# sound enumeration, correct vuln identification, a viable exploitation path, and
# awareness of post-exploitation + detection. Penalise "just run <tool>" with no
# understanding. The point is teaching method, not making script kiddies.
SYSTEM_RANGE_GRADER = (
    "You are a senior penetration-test assessor grading a learner's plan to compromise one host in a "
    "simulated range. Grade on TRADECRAFT, not keywords. Reward: (1) correct identification of the "
    "actual weakness; (2) a viable, specific exploitation path (not just naming a tool); (3) sound "
    "method — enumeration evidence, why this works, safe validation; (4) awareness of what's gained and "
    "the next pivot. Penalise blind tool-spraying, hand-waving, or wrong root cause even if a tool is "
    "named. Respond with ONLY: {\"score\":0-100,\"feedback\":\"2-3 sentences: tradecraft done well and "
    "the single biggest gap\",\"tradecraft\":\"one concrete habit to improve\"}."
)
# Defensive (blue-team) incident investigation: an alert + multi-source logs hide
# a ground truth the learner must SCOPE — entry vector, every compromised device,
# the lateral path, and exactly what (if anything) was exfiltrated.
SYSTEM_INCIDENT = (
    "You design SIMULATED blue-team incident-investigation exercises for authorized training. "
    "Respond with ONLY a JSON object:\n"
    '{"alert":"the initial alert/notification as a SOC tool (EDR/SIEM/IDS) would phrase it",'
    '"tool":"the tool the alert came from","artifacts":"15-40 lines of realistic, multi-source '
    'synthetic logs (auth, web, EDR, firewall, DNS) the analyst pivots through — embed the real '
    'evidence among noise","ground_truth":{"entry_vector":"how they got in","compromised":["device '
    'names actually compromised"],"not_compromised":["devices that look suspicious but were NOT"],'
    '"lateral_path":"device-to-device movement","exfiltration":"exactly what data left and to where, '
    'or \'none\'","timeline":"brief ordered sequence"},"indicators":["IOC 1","IOC 2"]}.\n'
    "Make scoping genuinely require reading the evidence: include red herrings. " + _GUARD
)
SYSTEM_INCIDENT_GRADER = (
    "You grade a SOC analyst's incident investigation against the hidden ground truth. Grade on "
    "investigative TRADECRAFT and accuracy of the SCOPE, not vibes. Score these dimensions and weight "
    "them: (1) correct ENTRY vector; (2) correct list of COMPROMISED devices (false positives AND "
    "misses both cost points); (3) correct determination of EXFILTRATION — what left and where, or "
    "correctly concluding nothing did; (4) EVIDENCE — did they cite specific log lines/IOCs rather than "
    "guess. Respond with ONLY: {\"score\":0-100,\"passed\":true/false (>=70),\"feedback\":\"what they "
    "scoped correctly and what they got wrong\",\"missed\":[\"key things not found\"]}."
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
    ("proven", "Proven", "Test out of a topic you already knew.", lambda g: g.get("tested_out", 0) >= 1, 30),
    ("foothold", "Foothold", "Compromise your first host in a range.", lambda g: g.get("hosts_pwned", 0) >= 1, 30),
    ("domain_admin", "Domain Admin", "Clear an end-to-end pentest range.", lambda g: g.get("ranges_cleared", 0) >= 1, 120),
    ("exfiltrator", "Exfiltrator", "Capture a range's objective (the crown jewels).", lambda g: g.get("objectives_captured", 0) >= 1, 90),
    ("incident_handler", "Incident Handler", "Correctly scope an incident investigation.", lambda g: g.get("incidents_solved", 0) >= 1, 70),
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
        "ranges": {},          # range_id -> end-to-end pentest range (virtual network); see generate_range()
        "drills": {},          # drill_id -> language cloze/translation drill; see generate_drill()
        "incidents": {},       # incident_id -> blue-team investigation exercise; see generate_incident()
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
        "tested_out": 0, "hosts_pwned": 0, "ranges_cleared": 0,
        "objectives_captured": 0, "incidents_total": 0, "incidents_solved": 0,
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


# Keep security content current. The model's training has a cutoff, so the
# operator can inject the live threat picture — recent TTPs, CVEs, tooling — via
# a `threats.yaml` file and/or MAYBOT_THREAT_CONTEXT. Injected into security
# lesson/lab/exam/range prompts so generated content reflects how the field
# looks NOW, not just at training time. Non-security tracks (e.g. French) skip it.
THREATS_FILE = Path(os.getenv("MAYBOT_THREATS_FILE", "threats.yaml"))
_BASELINE_THREATS = (
    "Emphasize how attacks and defenses look in real organizations TODAY: identity-first "
    "attacks (Active Directory, Entra/Azure AD, OAuth token theft, MFA fatigue), cloud "
    "misconfiguration and metadata-service abuse, supply-chain and CI/CD compromise, "
    "ransomware tradecraft and living-off-the-land, edge/VPN device exploitation, and "
    "EDR/SIEM-aware tradecraft. Map techniques to MITRE ATT&CK where natural."
)


def _language_of(track: dict) -> str:
    """The target language for a language track, or '' for non-language tracks.

    Explicit ``language:`` field wins; otherwise infer from a one-word title with
    no labs (e.g. the built-in 'French') so existing language tracks just work."""
    lang = str(track.get("language") or "").strip()
    if lang:
        return lang
    title = str(track.get("title") or "").strip()
    known = {"french", "spanish", "german", "italian", "portuguese", "japanese",
             "mandarin", "chinese", "korean", "russian", "arabic", "english"}
    if not track.get("labs") and title.lower() in known:
        return title
    return ""


def _is_language_track(track: dict) -> bool:
    return bool(_language_of(track))


def _is_security_track(track: dict) -> bool:
    hay = (str(track.get("id", "")) + " " + str(track.get("title", "")) + " "
           + " ".join(track.get("topics", []))).lower()
    return bool(track.get("labs")) or any(
        w in hay for w in ("security", "cyber", "pentest", "red team", "blue team",
                           "soc", "incident", "owasp", "threat", "attack"))


def _threat_context(track: dict) -> str:
    """Current-threat-landscape guidance for security tracks (empty otherwise)."""
    if not _is_security_track(track):
        return ""
    extra = []
    try:
        if THREATS_FILE.exists():
            data = yaml.safe_load(THREATS_FILE.read_text(encoding="utf-8")) or {}
            items = data.get("threats") or data.get("items") or []
            extra = [str(x) for x in items][:30]
    except Exception:
        extra = []
    env = (os.getenv("MAYBOT_THREAT_CONTEXT") or "").strip()
    if env:
        extra.append(env)
    body = _BASELINE_THREATS
    if extra:
        body += "\nCurrent focus items (operator-supplied):\n- " + "\n- ".join(extra)
    return "\n\nCURRENT THREAT LANDSCAPE — weave this in so the material stays current:\n" + body


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
                "mastered_topics": p.get("mastered_topics", []),
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
    p = prog.setdefault(track_id, {"lessons_done": 0, "quizzes_done": 0, "labs_done": 0,
                                   "score_sum": 0, "score_n": 0, "completed_topics": []})
    p.setdefault("mastered_topics", [])  # topics proven via a passing check / test-out
    return p


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
    lang = _language_of(track)
    system = SYSTEM_LANG_TUTOR.format(lang=lang) if lang else SYSTEM_TUTOR
    user = (f"Track: {track['title']}\nTopic: {topic}\n\nLearner profile:\n{_profile_brief()}\n\n"
            "Teach this topic now: a focused lesson with a clear explanation, one or two worked "
            "examples, and a short 'check yourself' question at the end."
            + _threat_context(track))
    ok, text, err = _call(member, system, user, chat, max_tokens=1100, temperature=0.5)
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


def _tutor_system(track: dict) -> str:
    """Immersive language tutor for language tracks, expert tutor otherwise."""
    lang = _language_of(track)
    return SYSTEM_LANG_TUTOR.format(lang=lang) if lang else SYSTEM_TUTOR


def _tutor_user_prompt(track: dict, question: str, history) -> str:
    convo = ""
    for turn in (history or [])[-6:]:
        role = "You" if turn.get("role") == "user" else "Tutor"
        convo += f"{role}: {turn.get('content', '')}\n"
    return (f"Track: {track.get('title')}\n\nLearner profile:\n{_profile_brief()}\n\n"
            + (f"Recent conversation:\n{convo}\n" if convo else "")
            + f"Learner asks: {question}")


def _persist_chat(track_id: str, question: str, answer: str) -> None:
    with _lock:
        log = _g().setdefault("chats", {}).setdefault(track_id, [])
        log.append({"role": "user", "content": question})
        log.append({"role": "assistant", "content": answer})
        del log[:-40]   # keep last 40 turns
        _save()


def ask_tutor(track_id: str, question: str, history=None, chat=None) -> dict:
    question = (question or "").strip()
    if not question:
        return {"error": "empty question"}
    track = _track(track_id) or {"title": "general study"}
    member = _backend_member()
    if not member:
        return {"answer": "", "member": None, "error": "no_backend"}
    user = _tutor_user_prompt(track, question, history)
    ok, text, err = _call(member, _tutor_system(track), user, chat, max_tokens=700, temperature=0.5)
    if not ok:
        return {"answer": "", "member": member.get("name"), "error": err or "no response"}
    answer = (text or "").strip()
    if _track(track_id):
        _persist_chat(track_id, question, answer)
    _touch_streak()
    return {"answer": answer, "member": member.get("name"), "error": None}


def ask_tutor_stream(track_id: str, question: str, history=None, chat_stream=None):
    """Streaming tutor reply: yields ``meta`` -> ``token``* -> ``done``/``error``
    event dicts, using the shared streaming engine. Persists the full reply to the
    track's chat history on completion. ``chat_stream`` is injectable for tests."""
    question = (question or "").strip()
    if not question:
        yield {"type": "error", "error": "empty question"}
        return
    track = _track(track_id) or {"title": "general study"}
    member = _backend_member()
    if not member:
        yield {"type": "meta", "member": None}
        yield {"type": "error", "error": "no_backend"}
        return
    yield {"type": "meta", "member": member.get("name")}
    messages = [{"role": "system", "content": _tutor_system(track)},
                {"role": "user", "content": _tutor_user_prompt(track, question, history)}]
    chat_stream = chat_stream or agents.stream_chat
    answer = ""
    try:
        for chunk in chat_stream({**member, "max_tokens": 700, "temperature": 0.5}, messages):
            if chunk:
                answer += chunk
                yield {"type": "token", "text": chunk}
    except Exception as exc:
        yield {"type": "error", "error": str(exc)}
        return
    answer = answer.strip()
    if not answer:
        yield {"type": "error", "error": "the tutor did not respond"}
        return
    if _track(track_id):
        _persist_chat(track_id, question, answer)
    _touch_streak()
    yield {"type": "done"}


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
# test-out / placement — prove you already know a topic and skip it
# ---------------------------------------------------------------------------
PLACEMENT_PASS = int(os.getenv("MAYBOT_PLACEMENT_PASS", "80"))


def generate_placement(track_id: str, topic: str, n: int = 6, chat=None) -> dict:
    """A harder challenge quiz that lets a learner test OUT of a topic they
    already know. Stored like a quiz but flagged so grading marks mastery."""
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    if not topic:
        return {"error": "a topic is required"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    n = max(4, min(10, int(n or 6)))
    user = (f"Track: {track['title']}\nTopic: {topic}\nLearner profile:\n{_profile_brief()}\n\n"
            f"Write {n} CHALLENGING multiple-choice questions to verify real mastery of this topic "
            "(application and edge cases, not just definitions). A learner who passes may skip it."
            + _threat_context(track))
    ok, text, err = _call(member, SYSTEM_QUIZ, user, chat, max_tokens=1500, temperature=0.5)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    questions = (data or {}).get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions:
        return {"error": "could not parse placement from the model"}
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
        return {"error": "could not parse placement from the model"}
    quiz_id = f"pl-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("quizzes", {})[quiz_id] = {
            "track": track_id, "topic": topic, "questions": clean,
            "placement": True, "created": int(time.time())}
        _save()
    public = [{"q": q["q"], "choices": q["choices"]} for q in clean]
    return {"quiz_id": quiz_id, "topic": topic, "questions": public,
            "pass_mark": PLACEMENT_PASS, "error": None}


def grade_placement(quiz_id: str, answers: list[int], chat=None) -> dict:
    """Grade a test-out attempt. On a pass, the topic is marked mastered (and
    studied) so the learner can skip it; a near-miss just gives feedback."""
    with _lock:
        quiz = (_g().get("quizzes") or {}).get(quiz_id)
    if not quiz:
        return {"error": "unknown or expired placement"}
    questions = quiz["questions"]
    answers = list(answers or [])
    correct = sum(1 for i, q in enumerate(questions)
                  if i < len(answers) and answers[i] == q["answer"])
    total = len(questions)
    score = round(100 * correct / total) if total else 0
    passed = score >= PLACEMENT_PASS
    topic = quiz.get("topic", "")
    stones = 25 if passed else 0
    with _lock:
        p = _progress_for(quiz["track"])
        if passed:
            if topic and topic not in p["mastered_topics"]:
                p["mastered_topics"].append(topic)
            if topic and topic not in p["completed_topics"]:
                p["completed_topics"].append(topic)
            g = _g()["game"]
            g["tested_out"] = g.get("tested_out", 0) + 1
        _save()
    if passed:
        _award_progress(stones, skill=f"{_track(quiz['track'])['title']}: {topic}")
        _touch_streak()
    earned = _check_badges() if passed else []
    _update_profile(
        f"{'Tested OUT of' if passed else 'Attempted to test out of'} '{topic}' "
        f"({score}%). {'Already proficient.' if passed else 'Not yet — should study it.'}", chat)
    return {"score": score, "correct": correct, "total": total, "passed": passed,
            "mastered": passed, "topic": topic, "pass_mark": PLACEMENT_PASS,
            "awarded": stones, "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# language drills — cloze (fill-in) + translation, for active recall + output
# ---------------------------------------------------------------------------
import unicodedata


def _norm_answer(s: str) -> str:
    """Fold case, accents, and surrounding punctuation/space so a learner isn't
    failed for a missing accent or trailing period."""
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"^[\s\W]+|[\s\W]+$", "", s)


def generate_drill(track_id: str, topic: str, kind: str = "cloze", n: int = 6, chat=None) -> dict:
    """A {lang} cloze or translation drill (language tracks only)."""
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    lang = _language_of(track)
    if not lang:
        return {"error": "drills are for language tracks"}
    if kind not in ("cloze", "translate"):
        return {"error": "kind must be 'cloze' or 'translate'"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    n = max(3, min(12, int(n or 6)))
    user = (f"Language: {lang}\nTopic: {topic}\nLearner profile:\n{_profile_brief()}\n\n"
            f"Write {n} `{kind}` drill items at the learner's level.")
    # .replace (not .format) — SYSTEM_DRILL embeds literal JSON braces.
    ok, text, err = _call(member, SYSTEM_DRILL.replace("{lang}", lang), user, chat, max_tokens=1200, temperature=0.5)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    items = (data or {}).get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        return {"error": "could not parse drill from the model"}
    clean = []
    for it in items[:n]:
        if not isinstance(it, dict) or not it.get("prompt") or not it.get("answer"):
            continue
        clean.append({"prompt": str(it["prompt"]), "answer": str(it["answer"]),
                      "accept": [str(a) for a in (it.get("accept") or [])],
                      "hint": str(it.get("hint", "")), "explain": str(it.get("explain", ""))})
    if not clean:
        return {"error": "could not parse drill from the model"}
    drill_id = f"dr-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("drills", {})[drill_id] = {
            "track": track_id, "topic": topic, "kind": kind, "lang": lang,
            "items": clean, "created": int(time.time())}
        _save()
    public = [{"prompt": it["prompt"], "hint": it["hint"]} for it in clean]
    return {"drill_id": drill_id, "kind": kind, "lang": lang, "topic": topic,
            "items": public, "error": None}


def grade_drill(drill_id: str, answers: list[str]) -> dict:
    """Grade a language drill (accent/case-tolerant). Missed items seed the
    spaced-repetition deck so they come back."""
    with _lock:
        drill = (_g().get("drills") or {}).get(drill_id)
    if not drill:
        return {"error": "unknown or expired drill"}
    items = drill["items"]
    answers = list(answers or [])
    per = []
    correct = 0
    missed_cards = []
    for i, it in enumerate(items):
        given = answers[i] if i < len(answers) else ""
        accepted = {_norm_answer(it["answer"]), *(_norm_answer(a) for a in it.get("accept", []))}
        is_ok = _norm_answer(given) in accepted and _norm_answer(given) != ""
        correct += 1 if is_ok else 0
        per.append({"correct": is_ok, "your_answer": given, "answer": it["answer"],
                    "explain": it.get("explain", "")})
        if not is_ok:
            # turn the miss into a recall card (prompt -> answer)
            missed_cards.append({"q": it["prompt"], "choices": [it["answer"]], "answer": 0,
                                 "explanation": it.get("explain", "")})
    total = len(items)
    score = round(100 * correct / total) if total else 0
    stones = correct * 2 + (8 if score == 100 else 0)
    with _lock:
        g = _g()["game"]
        g["quizzes_total"] = g.get("quizzes_total", 0) + 1
        if score == 100:
            g["flawless"] = g.get("flawless", 0) + 1
        p = _progress_for(drill["track"])
        p["quizzes_done"] += 1
        p["score_sum"] += score
        p["score_n"] += 1
        _save()
    _award_progress(stones)
    _touch_streak()
    _progress_quest("quiz", passed=(score >= 80))
    _log_activity("quizzes", score)
    if missed_cards:
        _seed_reviews(drill["track"], drill.get("topic", ""), missed_cards)
    earned = _check_badges()
    return {"score": score, "correct": correct, "total": total, "per_item": per,
            "awarded": stones, "badges": earned, "error": None}


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
    user = f"Track: {track['title']}\nLearner profile:\n{_profile_brief()}\n\n{ask}" + _threat_context(track)
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


HINT_COST = 10

SYSTEM_HINT = (
    "You are a patient lab mentor. Given a lab's hidden answer and indicators, give the learner ONE "
    "nudge toward the next step: point at where to look or what to question, but NEVER name the "
    "vulnerability, attack, or flag outright. 2-3 sentences, plain text, no JSON."
)


def lab_hint(lab_id: str, chat=None) -> dict:
    """A paid nudge: spend spirit stones for one mentor hint on an open lab."""
    with _lock:
        lab = (_g().get("labs") or {}).get(lab_id)
    if not lab:
        return {"error": "unknown or expired lab"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    if not cultivation.spend(LEARNER, HINT_COST):
        return {"error": f"not enough spirit stones — a hint costs {HINT_COST}"}
    user = (f"Lab brief: {lab['brief']}\n\nHidden answer (do NOT reveal it):\n{lab['answer']}\n\n"
            f"Key indicators: {', '.join(lab['indicators'])}\n\n"
            f"Hints already given: {lab.get('hints', 0)}")
    ok, text, err = _call(member, SYSTEM_HINT, user, chat, max_tokens=220, temperature=0.5)
    if not ok:
        cultivation.reward(LEARNER, HINT_COST)  # refund — the learner paid for nothing
        return {"error": err or "no response"}
    with _lock:
        lab["hints"] = lab.get("hints", 0) + 1
        _save()
    return {"hint": text.strip(), "cost": HINT_COST, "hints_used": lab["hints"], "error": None}


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
# end-to-end pentest range — a SIMULATED virtual network you attack host by host:
# enumerate a reachable host, exploit it (server-side graded free-text finding),
# loot credentials that unlock pivots, and move laterally across device kinds to
# the crown jewels. ZERO command execution — same safety boundary as the labs.
# ---------------------------------------------------------------------------
RANGE_EXPLOIT_PASS = int(os.getenv("MAYBOT_RANGE_PASS", "65"))


def _range_reachable(rng: dict) -> set[str]:
    """Host ids the learner can currently touch: entry points + anything a
    compromised host pivots to."""
    reach = set(rng.get("entry_points") or [])
    for h in rng["hosts"].values():
        if h.get("compromised"):
            reach.update(h.get("pivots_to") or [])
    return reach


def _range_view(rng: dict) -> dict:
    """The learner-facing state — hidden vuln/exploit/loot stay server-side until
    earned (loot is revealed only for hosts already compromised)."""
    reach = _range_reachable(rng)
    hosts = []
    for hid, h in rng["hosts"].items():
        owned = bool(h.get("compromised"))
        enumerated = bool(h.get("enumerated"))
        hosts.append({
            "id": hid, "hostname": h.get("hostname"), "ip": h.get("ip"), "kind": h.get("kind"),
            "reachable": hid in reach, "enumerated": enumerated, "compromised": owned,
            # services appear once enumerated; loot only once compromised.
            "services": h.get("services", []) if enumerated else None,
            "enum_hint": h.get("enum_hint") if enumerated else None,
            "loot": h.get("loot") if owned else None,
        })
    total = len(rng["hosts"])
    owned = sum(1 for h in rng["hosts"].values() if h.get("compromised"))
    obj = rng.get("objective") or {}
    # The objective's goal/target are shown; the flag stays hidden until captured.
    objective = {"goal": obj.get("goal", ""), "target_host": obj.get("target_host", ""),
                 "captured": bool(obj.get("captured"))} if obj else None
    return {"range_id": rng["id"], "scenario": rng.get("scenario", ""), "track": rng.get("track"),
            "objective": objective, "hosts": hosts, "owned": owned, "total": total,
            "cleared": owned >= total and total > 0, "error": None}


def generate_range(track_id: str, chat=None) -> dict:
    """Generate a simulated multi-stage pentest range (virtual network)."""
    track = _track(track_id)
    if not track:
        return {"error": "unknown track"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    user = (f"Track: {track['title']}\nLearner profile:\n{_profile_brief()}\n\n"
            "Design a simulated end-to-end pentest range as specified."
            + _threat_context(track))
    ok, text, err = _call(member, SYSTEM_RANGE, user, chat, max_tokens=2600, temperature=0.7)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    raw_hosts = (data or {}).get("hosts") if isinstance(data, dict) else None
    if not isinstance(raw_hosts, list) or not raw_hosts:
        return {"error": "could not parse range from the model"}
    hosts: dict[str, dict] = {}
    for h in raw_hosts:
        if not isinstance(h, dict) or not h.get("id"):
            continue
        hid = str(h["id"])
        hosts[hid] = {
            "hostname": str(h.get("hostname", hid)), "ip": str(h.get("ip", "")),
            "kind": str(h.get("kind", "server")),
            "services": [{"port": s.get("port"), "name": str(s.get("name", "")),
                          "version": str(s.get("version", ""))}
                         for s in (h.get("services") or []) if isinstance(s, dict)],
            "enum_hint": str(h.get("enum_hint", "")), "vuln": str(h.get("vuln", "")),
            "exploit": str(h.get("exploit", "")), "loot": str(h.get("loot", "")),
            "pivots_to": [str(x) for x in (h.get("pivots_to") or [])],
            "enumerated": False, "compromised": False}
    if not hosts:
        return {"error": "could not parse range hosts from the model"}
    entry = [str(x) for x in (data.get("entry_points") or []) if str(x) in hosts]
    if not entry:
        entry = [next(iter(hosts))]  # fall back to the first host as the foothold
    raw_obj = data.get("objective") if isinstance(data.get("objective"), dict) else {}
    target = str(raw_obj.get("target_host", "")) if raw_obj else ""
    if target not in hosts:
        # default the objective to the deepest host (one with no onward pivots)
        target = next((hid for hid, h in hosts.items() if not h.get("pivots_to")),
                      list(hosts)[-1])
    objective = {"goal": str(raw_obj.get("goal", "") or "Reach and loot the crown-jewel host."),
                 "target_host": target,
                 "flag": str(raw_obj.get("flag", "") or (hosts[target].get("loot") or "OBJECTIVE")),
                 "captured": False}
    range_id = f"rng-{int(time.time()*1000)}-{random.randint(100,999)}"
    rng = {"id": range_id, "track": track_id, "scenario": str(data.get("scenario", "")),
           "objective": objective, "entry_points": entry, "hosts": hosts,
           "created": int(time.time())}
    with _lock:
        ranges = _g().setdefault("ranges", {})
        ranges[range_id] = rng
        # keep the most recent 10 ranges
        if len(ranges) > 10:
            for k in sorted(ranges, key=lambda x: ranges[x]["created"])[:len(ranges) - 10]:
                ranges.pop(k, None)
        _save()
    _log_activity("labs")
    return _range_view(rng)


def get_range(range_id: str) -> dict:
    with _lock:
        rng = (_g().get("ranges") or {}).get(range_id)
    if not rng:
        return {"error": "unknown or expired range"}
    return _range_view(rng)


def range_enumerate(range_id: str, host_id: str) -> dict:
    """Scan a reachable host: reveal its services + enumeration hint."""
    with _lock:
        rng = (_g().get("ranges") or {}).get(range_id)
        if not rng:
            return {"error": "unknown or expired range"}
        host = rng["hosts"].get(host_id)
        if not host:
            return {"error": "no such host in this range"}
        if host_id not in _range_reachable(rng):
            return {"error": "host not reachable yet — compromise a host that pivots to it first"}
        host["enumerated"] = True
        _save()
    return {"host_id": host_id, "hostname": host.get("hostname"), "kind": host.get("kind"),
            "services": host.get("services", []), "enum_hint": host.get("enum_hint", ""),
            "error": None}


def range_exploit(range_id: str, host_id: str, finding: str, chat=None) -> dict:
    """Submit how you'd exploit an enumerated host. Graded server-side against
    the hidden vuln/exploit; on success you loot it and unlock its pivots."""
    with _lock:
        rng = (_g().get("ranges") or {}).get(range_id)
        if not rng:
            return {"error": "unknown or expired range"}
        host = rng["hosts"].get(host_id)
        if not host:
            return {"error": "no such host in this range"}
        if host_id not in _range_reachable(rng):
            return {"error": "host not reachable yet"}
        if not host.get("enumerated"):
            return {"error": "enumerate the host before exploiting it"}
        if host.get("compromised"):
            return {"error": "host already compromised", "already": True}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    user = (f"Host: {host.get('hostname')} ({host.get('kind')})\n"
            f"Services: {host.get('services')}\n\nHidden vulnerability: {host['vuln']}\n"
            f"Expected exploitation: {host['exploit']}\n\n"
            f"Learner's plan:\n{(finding or '').strip() or '(blank)'}")
    ok, text, err = _call(member, SYSTEM_RANGE_GRADER, user, chat, max_tokens=450, temperature=0.2)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text) or {}
    try:
        score = max(0, min(100, int(data.get("score", 0))))
    except Exception:
        score = 0
    feedback = str(data.get("feedback", "")).strip()
    owned = score >= RANGE_EXPLOIT_PASS
    result: dict = {"host_id": host_id, "score": score, "feedback": feedback,
                    "tradecraft": str(data.get("tradecraft", "")).strip(),
                    "compromised": owned, "error": None}
    if not owned:
        return result
    with _lock:
        host["compromised"] = True
        g = _g()["game"]
        g["hosts_pwned"] = g.get("hosts_pwned", 0) + 1
        view = _range_view(rng)
        cleared = view["cleared"]
        if cleared:
            g["ranges_cleared"] = g.get("ranges_cleared", 0) + 1
            p = _progress_for(rng["track"])
            p["labs_done"] += 1
        _save()
    stones = 20 + (60 if cleared else 0)
    _award_progress(stones, skill="Network Penetration Testing", bonus=15 if cleared else 0)
    _touch_streak()
    _progress_quest("lab", passed=True)
    earned = _check_badges()
    result.update({"loot": host.get("loot", ""), "unlocked": host.get("pivots_to", []),
                   "awarded": stones, "cleared": cleared, "badges": earned, "range": view})
    _update_profile(
        f"Compromised {host.get('hostname')} ({host.get('kind')}) in a pentest range."
        + (" Cleared the whole range." if cleared else ""), chat)
    return result


def range_capture(range_id: str, submission: str) -> dict:
    """Complete the engagement OBJECTIVE: extract the specific file/secret from the
    target host. The target must be compromised first; the submission is matched
    against the hidden flag (accent/format tolerant). This is the real-world goal
    — getting domain admin isn't the point, getting the data out is."""
    with _lock:
        rng = (_g().get("ranges") or {}).get(range_id)
        if not rng:
            return {"error": "unknown or expired range"}
        obj = rng.get("objective") or {}
        if not obj:
            return {"error": "this range has no objective"}
        if obj.get("captured"):
            return {"captured": True, "already": True, "goal": obj.get("goal", ""), "error": None}
        target_id = obj.get("target_host")
        target = rng["hosts"].get(target_id) or {}
        if not target.get("compromised"):
            return {"error": "compromise the objective's target host before extracting from it",
                    "target_host": target_id}
        flag = obj.get("flag", "")
        got = _norm_answer(submission)
        ok = bool(got) and (got == _norm_answer(flag) or _norm_answer(flag) in got
                            or (len(got) >= 6 and got in _norm_answer(flag)))
        if not ok:
            return {"captured": False, "goal": obj.get("goal", ""),
                    "hint": "that's not the objective data — re-check what's on the target host",
                    "error": None}
        obj["captured"] = True
        g = _g()["game"]
        g["objectives_captured"] = g.get("objectives_captured", 0) + 1
        _save()
    _award_progress(80, skill="Objective-Based Operations", bonus=20)
    _touch_streak()
    earned = _check_badges()
    _update_profile(f"Captured the engagement objective ({obj.get('goal','')}) in a pentest range.")
    return {"captured": True, "goal": obj.get("goal", ""), "flag": flag,
            "awarded": 80, "badges": earned, "error": None}


# ---------------------------------------------------------------------------
# blue-team incident investigation — scope a real compromise from alert + logs
# ---------------------------------------------------------------------------
INCIDENT_PASS = int(os.getenv("MAYBOT_INCIDENT_PASS", "70"))


def generate_incident(track_id: str = "blue-team", chat=None) -> dict:
    """Generate a defensive investigation: an alert + multi-source logs hiding a
    ground truth the analyst must scope (entry, spread, exfiltration)."""
    track = _track(track_id) or {"id": track_id, "title": "Blue Team"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    user = (f"Track: {track.get('title')}\nLearner profile:\n{_profile_brief()}\n\n"
            "Design a blue-team incident-investigation exercise as specified."
            + _threat_context({"labs": ["ids"], "title": "incident"}))
    ok, text, err = _call(member, SYSTEM_INCIDENT, user, chat, max_tokens=2200, temperature=0.7)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text)
    gt = (data or {}).get("ground_truth") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not data.get("artifacts") or not isinstance(gt, dict):
        return {"error": "could not parse incident from the model"}
    incident_id = f"inc-{int(time.time()*1000)}-{random.randint(100,999)}"
    with _lock:
        _g().setdefault("incidents", {})[incident_id] = {
            "track": track_id, "alert": str(data.get("alert", "")), "tool": str(data.get("tool", "")),
            "artifacts": str(data["artifacts"]), "ground_truth": gt,
            "indicators": [str(x) for x in (data.get("indicators") or [])],
            "created": int(time.time())}
        _save()
    # The alert + raw logs are shown; the ground truth stays server-side.
    return {"incident_id": incident_id, "alert": str(data.get("alert", "")),
            "tool": str(data.get("tool", "")), "artifacts": str(data["artifacts"]),
            "goal": ("Scope the compromise: the entry vector, EVERY compromised device, the lateral "
                     "path, and exactly what (if anything) was exfiltrated. Cite the evidence."),
            "error": None}


def grade_incident(incident_id: str, findings: str, chat=None) -> dict:
    """Grade a SOC analyst's investigation on scope accuracy + tradecraft."""
    with _lock:
        inc = (_g().get("incidents") or {}).get(incident_id)
    if not inc:
        return {"error": "unknown or expired incident"}
    member = _backend_member()
    if not member:
        return {"error": "no_backend"}
    gt = inc["ground_truth"]
    user = (f"Alert ({inc.get('tool')}): {inc.get('alert')}\n\nGround truth:\n{json.dumps(gt)}\n\n"
            f"Analyst's investigation:\n{(findings or '').strip() or '(blank)'}")
    ok, text, err = _call(member, SYSTEM_INCIDENT_GRADER, user, chat, max_tokens=500, temperature=0.2)
    if not ok:
        return {"error": err or "no response"}
    data = _extract_json(text) or {}
    try:
        score = max(0, min(100, int(data.get("score", 0))))
    except Exception:
        score = 0
    solved = bool(data.get("passed")) if "passed" in data else (score >= INCIDENT_PASS)
    stones = 12 + score // 5 if solved else score // 10
    with _lock:
        g = _g()["game"]
        g["incidents_total"] = g.get("incidents_total", 0) + 1
        if solved:
            g["incidents_solved"] = g.get("incidents_solved", 0) + 1
        p = _progress_for(inc["track"])
        p["labs_done"] += 1
        _save()
    _award_progress(stones, skill="Incident Response & Scoping" if solved else None, bonus=10 if solved else 0)
    _touch_streak()
    _progress_quest("lab", passed=solved)
    _log_activity("labs", score)
    earned = _check_badges()
    _update_profile(f"Investigated an incident and scored {score}/100. "
                    + ("Scoped it accurately." if solved else "Missed parts of the scope."), chat)
    return {"score": score, "solved": solved, "passed": solved,
            "feedback": str(data.get("feedback", "")).strip(),
            "missed": [str(x) for x in (data.get("missed") or [])],
            "ground_truth": gt, "awarded": stones, "badges": earned, "error": None}


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
            "Tag each question with its domain (use one of the topic names as the `domain`)."
            + _threat_context(track))
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
# lab target catalog (phase 3) — DATA ONLY, executes nothing
# ---------------------------------------------------------------------------
def list_lab_targets() -> list[dict]:
    """Return the built-in catalog of Docker-based pentest/IDS lab TARGETS
    (from ``lab_targets.yaml``, mirroring how ``seed_tracks`` loads tracks).

    SAFE: this is just catalog data + a getter. It does NOT run Docker, does NOT
    execute any command, and does NOT touch a host. The operator runs the targets
    themselves (``labs/docker-compose.yml``); their real logs are then pulled
    READ-ONLY via ``fetch_real_logs`` into ``generate_real_lab``. Each item:
    ``{id, name, kind, app, service, ports, look_for, notes}``."""
    if not LAB_TARGETS_FILE.exists():
        return []
    try:
        data = yaml.safe_load(LAB_TARGETS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    targets = data.get("targets", [])
    if not isinstance(targets, list):
        return []
    out: list[dict] = []
    for t in targets:
        if not isinstance(t, dict) or not t.get("id"):
            continue
        out.append({
            "id": str(t.get("id")),
            "name": str(t.get("name", t.get("id"))),
            "kind": t.get("kind") if t.get("kind") in ("ids", "pentest") else "pentest",
            "app": str(t.get("app", "")),
            "service": str(t.get("service", "")),
            "ports": [str(p) for p in (t.get("ports") or [])],
            "look_for": [str(x) for x in (t.get("look_for") or [])],
            "notes": str(t.get("notes", "")).strip(),
        })
    return out


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
# ---------------------------------------------------------------------------
# real-command execution (default-OFF) — the contract, not a live exploit driver.
# See docs/REAL_LABS.md for the microVM/sandbox topology this binds to.
# ---------------------------------------------------------------------------
REAL_LABS = os.getenv("MAYBOT_REAL_LABS", "0").lower() in ("1", "true", "yes", "on")
REAL_TARGETS_FILE = Path(os.getenv("MAYBOT_REAL_TARGETS_FILE", "real_targets.yaml"))


def _load_real_targets() -> dict:
    """Operator-defined map of range/lab host -> a real, isolated sandbox target +
    the guarded tools allowed against it. Read-only data; nothing here executes."""
    if not REAL_LABS or not REAL_TARGETS_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(REAL_TARGETS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    for t in (data.get("targets") or []):
        if isinstance(t, dict) and t.get("host_id"):
            out[str(t["host_id"])] = t
    return out


def real_env_status() -> dict:
    """Surface whether real-command labs are wired (default off). The UI shows
    this so simulated labs are clearly distinguished from a live sandbox."""
    targets = _load_real_targets()
    return {"enabled": REAL_LABS, "configured_targets": sorted(targets.keys()),
            "agent_required": True,
            "note": ("OFF — labs are simulated, graded server-side." if not REAL_LABS else
                     "ON — host actions route through the guarded tools allow-list on an "
                     "isolated-sandbox agent. See docs/REAL_LABS.md.")}


def attach_real_env(exercise: dict, host_id: str) -> dict | None:
    """Bind a simulated range/lab host to a REAL, isolated sandbox target so its
    enumerate/exploit actions run actual tools — the CONTRACT, default-OFF.

    Returns ``None`` unless ``MAYBOT_REAL_LABS=1`` AND ``real_targets.yaml`` maps
    ``host_id`` to a sandbox target. When bound, it returns a descriptor naming the
    sandbox agent and the *allow-listed* guarded tools permitted against it — it
    does NOT execute anything. Execution still goes through ``tools.run`` (fixed
    argv, no shell, validated args, human approval, audited) dispatched to a
    ``maybot_agent`` running INSIDE the isolated microVM/sandbox network, scoped to
    the lab subnet. The model never turns free text into a command; it can only
    request an allow-listed tool with validated parameters. See docs/REAL_LABS.md."""
    targets = _load_real_targets()
    t = targets.get(str(host_id))
    if not t:
        return None
    return {
        "host_id": str(host_id),
        "agent": str(t.get("agent", "")),          # the in-sandbox maybot_agent host name
        "target": str(t.get("target", "")),        # sandbox-internal IP/hostname only
        "network": str(t.get("network", "")),      # the isolated lab subnet (scope guard)
        "allowed_tools": [str(x) for x in (t.get("allowed_tools") or [])],
        "requires_approval": bool(t.get("requires_approval", True)),
        "ephemeral": bool(t.get("ephemeral", True)),
    }
