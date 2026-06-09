"""Learning Center — AI tutor, quizzes, simulated labs, learner profile, and the
cultivation-tied gamification (streaks, badges, daily quests, mystery chests)."""
import json

import pytest

from maybot_control_center import learning, cultivation, store


@pytest.fixture(autouse=True)
def fresh_state():
    """Each test starts from a blank, in-memory learning state."""
    learning._state.clear()
    learning._state.update(learning._blank())
    yield


def fake_chat(member, messages):
    """One fake LLM that answers each Learning prompt type by inspecting its system message."""
    system = messages[0]["content"]
    if "quiz author" in system:
        return True, json.dumps({"questions": [
            {"q": "What does TCP provide?", "choices": ["Reliable", "Lossy", "None", "Encryption"],
             "answer": 0, "explanation": "TCP is reliable, ordered."},
            {"q": "Port for HTTPS?", "choices": ["80", "22", "443", "21"], "answer": 2, "explanation": "443."},
        ]}), None
    if "training labs" in system:
        return True, json.dumps({"brief": "Find the intrusion.",
                                 "artifact": "10.0.0.1 GET /\n10.0.0.9 POST /admin ' OR 1=1--",
                                 "answer": "SQL injection against /admin from 10.0.0.9.",
                                 "indicators": ["OR 1=1", "/admin"]}), None
    if "grade a learner's free-text" in system:
        return True, json.dumps({"score": 85, "feedback": "Good — you spotted the SQLi."}), None
    if "model of how a particular learner" in system:
        return True, json.dumps({"style_summary": "Likes concrete examples.",
                                 "preferences": ["worked examples"], "strengths": ["networking"],
                                 "gaps": ["crypto"], "goals": ["pass Security+"], "notes": ""}), None
    # tutor / lesson
    return True, "Here is a lesson with a worked example.", None


# ---- tracks ----
def test_seed_tracks_present():
    ids = {t["id"] for t in learning.seed_tracks()}
    assert {"cybersecurity", "french", "cert-prep"} <= ids


def test_create_and_list_custom_track():
    learning.create_track("Spanish", ["Greetings", "Verbs"])
    tracks = {t["id"]: t for t in learning.list_tracks()["tracks"]}
    assert "spanish" in tracks
    assert tracks["spanish"]["builtin"] is False
    assert "cybersecurity" in tracks and tracks["cybersecurity"]["builtin"] is True


# ---- tutor grounding ----
def test_lesson_grounded_in_profile_and_awards(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    learning.set_profile({"goals": ["pass Security+"], "style_summary": "concrete examples"})
    seen = {}

    def spy(member, messages):
        seen.setdefault("system", messages[0]["content"])
        seen.setdefault("user", messages[-1]["content"])
        return fake_chat(member, messages)

    res = learning.get_lesson("cybersecurity", "Cryptography Basics", chat=spy)
    assert res["error"] is None and res["body"]
    assert "pass Security+" in seen["user"]            # conditioned on the learner profile
    assert res["awarded"] == 8
    # progress + totals advanced
    assert learning._g()["game"]["lessons_total"] == 1


def test_no_backend_is_graceful(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: None)
    assert learning.get_lesson("french", "Greetings & Introductions")["error"] == "no_backend"
    assert learning.ask_tutor("french", "bonjour?")["error"] == "no_backend"
    assert learning.generate_quiz("french", "Greetings")["error"] == "no_backend"


# ---- quizzes ----
def test_quiz_generate_and_grade(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    q = learning.generate_quiz("cybersecurity", "Networking & TCP/IP", n=2, chat=fake_chat)
    assert q["error"] is None and len(q["questions"]) == 2
    # the answer key must NOT leak to the client
    assert all("answer" not in question for question in q["questions"])
    # answer first right, second wrong
    g = learning.grade_quiz(q["quiz_id"], [0, 0], chat=fake_chat)
    assert g["correct"] == 1 and g["total"] == 2 and g["score"] == 50
    assert g["awarded"] > 0
    assert g["per_question"][1]["correct"] is False


def test_perfect_quiz_sets_flawless(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    q = learning.generate_quiz("cybersecurity", "TCP", n=2, chat=fake_chat)
    g = learning.grade_quiz(q["quiz_id"], [0, 2], chat=fake_chat)
    assert g["score"] == 100
    assert learning._g()["game"]["flawless"] == 1
    assert learning._g()["game"]["best_combo"] >= 2


# ---- labs ----
def test_lab_generate_hides_answer_and_grades(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    lab = learning.generate_lab("cybersecurity", "ids", chat=fake_chat)
    assert lab["error"] is None and lab["artifact"]
    assert "answer" not in lab and "indicators" not in lab   # hidden server-side
    g = learning.grade_lab(lab["lab_id"], "SQL injection on /admin", chat=fake_chat)
    assert g["score"] == 85 and g["solved"] is True
    assert g["expected"]                                       # revealed only after grading
    assert learning._g()["game"]["ids_solved"] == 1


# ---- learner profile updates ----
def test_profile_updates_after_interaction(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    learning.get_lesson("cybersecurity", "Cryptography Basics", chat=fake_chat)
    prof = learning.get_profile()
    assert prof["style_summary"] == "Likes concrete examples."
    assert "crypto" in prof["gaps"]


# ---- gamification ----
def test_badge_awarded_once(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    learning._g()["game"]["lessons_total"] = 1
    first = learning._check_badges()
    assert any(b["id"] == "first_steps" for b in first)
    assert learning._check_badges() == []                     # not awarded twice


def test_streak_increments_and_resets():
    from datetime import date, timedelta
    g = learning._g()["game"]
    g["last_active_day"] = (date.today() - timedelta(days=1)).isoformat()
    g["streak"] = 3
    learning._touch_streak()
    assert learning._g()["game"]["streak"] == 4
    # a gap with no freeze resets to 1
    g = learning._g()["game"]
    g["last_active_day"] = (date.today() - timedelta(days=5)).isoformat()
    g["freezes"] = 0
    g["streak"] = 4
    learning._touch_streak()
    assert learning._g()["game"]["streak"] == 1


def test_daily_quest_completion_grants_reward():
    learning.daily_quests()
    learning._g()["game"]["quests"] = [{"kind": "lesson", "desc": "Finish a lesson",
                                        "need": 1, "reward": 8, "have": 0, "done": False}]
    learning._progress_quest("lesson")
    q = learning._g()["game"]["quests"][0]
    assert q["done"] is True
    assert learning._g()["game"]["pending_chests"] >= 1       # completing a quest drops a chest


def test_chest_requires_earning():
    assert "error" in learning.open_chest()                   # none earned yet
    learning._g()["game"]["pending_chests"] = 1
    res = learning.open_chest()
    assert res.get("error") is None and res["stones"] > 0


# ---- cultivation XP integration ----
def test_award_raises_learner_stones():
    before = cultivation.state(learning.LEARNER)["stones"]
    learning._award_progress(20)
    after = cultivation.state(learning.LEARNER)["stones"]
    assert after == before + 20


# ---- store round-trip ----
def test_state_persists_round_trip():
    store._reset_for_tests(":memory:")
    store.init()
    try:
        learning.create_track("Persisted", ["A"])
        learning._g()["game"]["streak"] = 9
        learning._save()
        learning._state.clear()
        learning.load_persisted()
        assert "persisted" in learning._g().get("custom_tracks", {})
        assert learning._g()["game"]["streak"] == 9
    finally:
        store._reset_for_tests("")
