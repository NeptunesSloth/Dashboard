"""CORE PROBLEM 2 — sealed tutor/examiner separation, and
CORE PROBLEM 3 — proof-of-work assessment (evidence required, not claims)."""
import json

import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    yield


# ---- CORE 2: sealed separation ----
def test_tutor_prompt_refuses_to_solve_assessments():
    # the tutor system prompt instructs refusal of "solve this lab/flag" requests
    assert "REFUSE" in learning.SYSTEM_TUTOR
    assert "answer key" in learning.SYSTEM_TUTOR.lower()


def test_grader_member_separate_from_tutor(monkeypatch):
    import maybot_control_center.agents as agents
    tutor = {"name": "Tutor", "base_url": "http://t"}
    grader = {"name": "Sealed-Grader", "provider": "claude"}
    monkeypatch.setattr(learning, "_backend_member", lambda: tutor)
    # no dedicated grader configured -> falls back to the tutor backend
    monkeypatch.setattr(learning, "GRADER_MEMBER", "")
    assert learning._grader_member()["name"] == "Tutor"
    # a named grader member is used instead (a distinct model/process)
    monkeypatch.setattr(learning, "GRADER_MEMBER", "Sealed-Grader")
    monkeypatch.setattr(agents, "_agent_def", lambda n: grader if n == "Sealed-Grader" else None)
    assert learning._grader_member()["name"] == "Sealed-Grader"


def test_tutor_never_receives_answer_keys(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    # ask_tutor builds its prompt from track/topic/history only — never the lab
    # answer/range exploit fields. Assert no solution leaks into the tutor prompt.
    learning._g().setdefault("labs", {})["lab-x"] = {
        "track": "cybersecurity", "kind": "pentest", "brief": "b",
        "answer": "SUPER_SECRET_FLAG_42", "indicators": ["x"], "artifact": "a"}
    seen = {}

    def spy(member, messages):
        seen["text"] = json.dumps(messages)
        return True, "Here's the concept…", None

    learning.ask_tutor("cybersecurity", "How does SQL injection work generally?", chat=spy)
    assert "SUPER_SECRET_FLAG_42" not in seen["text"]


# ---- CORE 3: proof-of-work ----
def test_graders_demand_proof_of_work():
    for sysprompt in (learning.SYSTEM_GRADER, learning.SYSTEM_RANGE_GRADER,
                      learning.SYSTEM_POSTEX_GRADER):
        assert "PROOF-OF-WORK" in sysprompt
        assert "below passing" in sysprompt


def _range_with_host(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    HOSTS = [{"id": "web1", "hostname": "w", "kind": "web",
              "services": [{"port": 80, "name": "http"}], "enum_hint": "x", "vuln": "sqli",
              "exploit": "union sqli", "technique": "T1190", "access_level": "www",
              "privesc": "sudo misconfiguration", "persistence": "cron", "loot": "f", "pivots_to": []}]
    good = {"scenario": "s", "entry_points": ["web1"],
            "objective": {"goal": "x", "target_host": "web1", "flag": "f"}, "hosts": HOSTS}

    def gen_chat(member, messages):
        s = messages[0]["content"].lower()
        if "penetration-testing ranges" in s:
            return True, json.dumps(good), None
        return True, json.dumps({"approve": True, "issues": []}), None

    g = learning.generate_range("offensive-security", chat=gen_chat)
    learning.range_enumerate(g["range_id"], "web1")
    return g["range_id"]


def test_exploit_evidence_reaches_the_grader(monkeypatch):
    rid = _range_with_host(monkeypatch)
    seen = {}

    def grader(member, messages):
        if "penetration-test assessor" in messages[0]["content"].lower():
            seen["user"] = messages[1]["content"]
            return True, json.dumps({"score": 85, "feedback": "ok", "tradecraft": "x"}), None
        return True, "ok", None

    monkeypatch.setattr(learning, "_grader_member", lambda: {"name": "G"})
    learning.range_exploit(rid, "web1", "union-based SQLi on the id param", chat=grader,
                           evidence="payload: ' UNION SELECT user,pass-- ; response: dumped users")
    assert "payload:" in seen["user"] and "Evidence/artifacts" in seen["user"]


def test_bare_claim_is_flagged_as_no_evidence(monkeypatch):
    rid = _range_with_host(monkeypatch)
    seen = {}

    def grader(member, messages):
        if "penetration-test assessor" in messages[0]["content"].lower():
            seen["user"] = messages[1]["content"]
            return True, json.dumps({"score": 30, "feedback": "no evidence", "tradecraft": "x"}), None
        return True, "ok", None

    monkeypatch.setattr(learning, "_grader_member", lambda: {"name": "G"})
    learning.range_exploit(rid, "web1", "I exploited SQL injection", chat=grader)  # no evidence
    assert "No evidence/artifacts submitted" in seen["user"]
