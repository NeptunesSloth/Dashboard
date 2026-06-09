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


# ---- saved lessons + chat history ----
def test_lessons_are_saved_and_retrievable(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    res = learning.get_lesson("french", "Greetings & Introductions", chat=fake_chat)
    lid = res["lesson_id"]
    listed = learning.list_lessons("french")["lessons"]
    assert any(x["id"] == lid for x in listed)
    full = learning.get_saved_lesson(lid)
    assert full["body"] == res["body"] and full["topic"] == "Greetings & Introductions"


def test_chat_history_persists(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    learning.ask_tutor("french", "Comment dit-on bonjour?", chat=fake_chat)
    hist = learning.get_chat("french")["history"]
    assert hist and hist[0]["role"] == "user" and hist[1]["role"] == "assistant"


# ---- spaced repetition ----
def test_missed_quiz_questions_become_due_reviews(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    q = learning.generate_quiz("cybersecurity", "TCP", n=2, chat=fake_chat)
    learning.grade_quiz(q["quiz_id"], [1, 1], chat=fake_chat)   # both wrong
    d = learning.due_reviews()
    assert d["due_count"] == 2 and len(d["due"]) == 2
    assert all("answer" not in c for c in d["due"])             # answer key hidden


def test_review_sm2_schedules_forward():
    learning._g()["reviews"] = [learning._new_card("cybersecurity", "TCP",
        {"q": "Port?", "choices": ["80", "443"], "answer": 1, "explanation": "https"})]
    cid = learning._g()["reviews"][0]["id"]
    r = learning.grade_review(cid, 5)
    assert r["error"] is None and r["correct_answer"] == 1
    assert r["interval_days"] >= 1 and r["next_due"] > learning._today()
    assert learning._g()["game"]["reviews_done"] == 1


# ---- practice exams ----
def test_exam_generate_and_grade_with_domains(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})

    def exam_chat(member, messages):
        if "EXAM" in messages[-1]["content"] or "domain" in messages[0]["content"]:
            return True, json.dumps({"questions": [
                {"q": "Q1", "choices": ["a", "b"], "answer": 0, "explanation": "", "domain": "Crypto"},
                {"q": "Q2", "choices": ["a", "b"], "answer": 1, "explanation": "", "domain": "Networking"},
            ]}), None
        return fake_chat(member, messages)

    ex = learning.generate_exam("cybersecurity", n=2, chat=exam_chat)
    assert ex["error"] is None and ex["duration_sec"] > 0 and ex["pass_mark"] == 75
    assert all("domain" in q and "answer" not in q for q in ex["questions"])
    g = learning.grade_exam(ex["exam_id"], [0, 1], chat=exam_chat)
    assert g["score"] == 100 and g["passed"] is True
    assert g["per_domain"]["Crypto"]["correct"] == 1
    assert learning._g()["game"]["exams_passed"] == 1


# ---- real-log labs (read-only) ----
def test_real_log_lab_from_fetched_logs(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    logs = "10.0.0.5 GET /\n10.0.0.9 POST /login failed x40 brute force"
    lab = learning.generate_real_lab("cybersecurity", "web-01", "nginx", logs, chat=fake_chat)
    assert lab["error"] is None and lab["kind"] == "real-ids"
    assert lab["artifact"] == logs and lab["source"] == "web-01/nginx"
    # gradeable like any lab; answer was hidden server-side
    g = learning.grade_lab(lab["lab_id"], "brute force on /login from 10.0.0.9", chat=fake_chat)
    assert g["score"] == 85 and g["solved"] is True


def test_fetch_real_logs_is_read_only(monkeypatch):
    calls = {}

    def fake_call(device, endpoint):
        calls["endpoint"] = endpoint
        return {"online": True, "data": {"lines": ["line one", {"line": "line two"}]}}

    monkeypatch.setattr("maybot_control_center.agent_client.call_agent", fake_call)
    text, err = learning.fetch_real_logs({"name": "web-01"}, "nginx")
    assert err is None and "line one" in text and "line two" in text
    assert calls["endpoint"].startswith("/api/projects/nginx/logs")   # GET logs only


# ---- analytics ----
def test_analytics_tracks_activity(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    learning.get_lesson("french", "Greetings & Introductions", chat=fake_chat)
    a = learning.get_analytics(days=30)
    assert a["totals"]["lessons"] == 1
    assert a["active_days"] == 1
    assert a["heatmap"][-1]["count"] == 1                      # today has activity
    assert len(a["heatmap"]) == 30


# ---- study plan ----
def test_study_plan_schedule_and_completion():
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=14)).isoformat()
    res = learning.create_plan("cybersecurity", future)
    assert res["ok"] and res["plan"]["items"]
    assert res["plan"]["exam_date"] == future
    # has lessons for the track's topics + at least one exam item
    kinds = {it["kind"] for it in res["plan"]["items"]}
    assert "lesson" in kinds and "exam" in kinds
    # completing the first due item advances progress
    g = learning.complete_plan_item("cybersecurity", 0, True)
    assert g["ok"] and g["plan"]["done"] >= 1
    assert learning.get_plan("cybersecurity")["plan"]["items"][0]["done"] is True


def test_plan_rejects_past_date():
    from datetime import date, timedelta
    past = (date.today() - timedelta(days=1)).isoformat()
    assert "error" in learning.create_plan("cybersecurity", past)


# ---- reminders ----
def test_reminder_dedupes_per_day(monkeypatch):
    sent = []
    monkeypatch.setattr("maybot_control_center.notify.send",
                        lambda *a, **k: sent.append(a) or {"delivered": ["log"]})
    # streak at risk: had a streak yesterday, nothing today
    from datetime import date, timedelta
    g = learning._g()["game"]
    g["streak"] = 5
    g["last_active_day"] = (date.today() - timedelta(days=1)).isoformat()
    r1 = learning.send_reminder()
    assert r1["sent"] is True and len(sent) == 1
    r2 = learning.send_reminder()                              # same day -> deduped
    assert r2["sent"] is False and len(sent) == 1


# ---- streaming tutor ----
def test_ask_tutor_stream_emits_tokens_and_persists(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})

    def fake_stream(member, messages):
        for piece in ["Bon", "jour", "!"]:
            yield piece

    events = list(learning.ask_tutor_stream("french", "How do I say hello?", chat_stream=fake_stream))
    assert events[0]["type"] == "meta" and events[0]["member"] == "Sage"
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Bonjour!"
    assert events[-1]["type"] == "done"
    # full reply persisted to the track's chat history
    hist = learning.get_chat("french")["history"]
    assert hist[-1]["role"] == "assistant" and hist[-1]["content"] == "Bonjour!"


def test_ask_tutor_stream_no_backend(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: None)
    events = list(learning.ask_tutor_stream("french", "hi"))
    assert any(e.get("error") == "no_backend" for e in events)


def test_ask_tutor_stream_empty_output_errors(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Sage", "provider": "claude"})
    events = list(learning.ask_tutor_stream("french", "hi", chat_stream=lambda m, msgs: iter(())))
    assert any(e["type"] == "error" for e in events)


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
