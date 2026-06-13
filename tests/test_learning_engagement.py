"""CORE 9 — reporting engine, CORE 10 — purple-team loop, CORE 11 — engagement
discipline (rules of engagement, time pressure, documentation notebook)."""
import json
import time

import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    monkeypatch.setattr(learning, "_grader_member", lambda: {"name": "G"})
    yield


HOSTS = [{"id": "web1", "hostname": "web1", "kind": "web",
          "services": [{"port": 80, "name": "http"}], "enum_hint": "x", "vuln": "log4shell",
          "exploit": "jndi rce", "technique": "T1190", "access_level": "www",
          "privesc": "sudo misconfiguration", "persistence": "cron", "loot": "f", "pivots_to": []}]
GOOD = {"scenario": "s", "entry_points": ["web1"],
        "objective": {"goal": "exfil flag", "target_host": "web1", "flag": "FLAG"}, "hosts": HOSTS}


def chat(member, messages):
    s = messages[0]["content"].lower()
    if "penetration-testing ranges" in s:
        return True, json.dumps(GOOD), None
    if "approve" in s:
        return True, json.dumps({"approve": True, "issues": []}), None
    if "penetration-test assessor" in s:
        return True, json.dumps({"score": 80, "feedback": "ok", "tradecraft": "x"}), None
    if "detection engineer" in s:
        return True, json.dumps({"alert": "EDR: jndi exploit on web1", "tool": "EDR",
                                 "artifacts": "auth.log\nweb.log\nedr.log", "indicators": ["jndi"]}), None
    if "grade a soc analyst" in s:
        return True, json.dumps({"score": 85, "passed": True, "feedback": "good", "missed": []}), None
    if "engagement report" in s:
        return True, json.dumps({"overall": 78, "technical_accuracy": 80, "clarity": 75,
                                 "business_communication": 70, "remediation_quality": 85,
                                 "feedback": "solid", "missing": []}), None
    return True, "ok", None


def _worked_range():
    g = learning.generate_range("offensive-security", chat=chat)
    learning.range_enumerate(g["range_id"], "web1")
    learning.range_exploit(g["range_id"], "web1", "jndi rce", chat=chat, evidence="payload ${jndi}")
    return g["range_id"]


# ---- CORE 11: engagement discipline ----
def test_range_has_roe_timer_and_notebook():
    g = learning.generate_range("offensive-security", chat=chat)
    v = learning.get_range(g["range_id"])
    assert len(v["roe"]) >= 3 and v["time_limit_min"] >= 1
    assert v["time_left_s"] > 0 and v["expired"] is False
    assert v["notebook_entries"] == 0


def test_notebook_entries_recorded():
    g = learning.generate_range("offensive-security", chat=chat)
    learning.range_note(g["range_id"], "nmap -sV web1", "command")
    learning.range_note(g["range_id"], "found log4j", "finding")
    assert learning.get_range(g["range_id"])["notebook_entries"] == 2
    assert "empty" in learning.range_note(g["range_id"], "  ")["error"]


def test_documentation_factor_affects_reward():
    # no notebook -> reduced reward
    rid = _worked_range()
    res = learning.range_capture(rid, "FLAG")
    assert res["doc_factor"] < 1.0 and res["awarded"] < 80
    assert res["discipline_notes"]


def test_full_documentation_full_reward():
    rid = _worked_range()
    for i in range(4):
        learning.range_note(rid, f"step {i}", "note")
    res = learning.range_capture(rid, "FLAG")
    assert res["doc_factor"] == 1.0 and res["awarded"] == 80


def test_over_time_penalises():
    rid = _worked_range()
    rng = learning._g()["ranges"][rid]
    rng["started_at"] = int(time.time()) - 999999      # long over the limit
    res = learning.range_capture(rid, "FLAG")
    assert res["over_time"] is True


# ---- CORE 10: purple-team loop ----
def test_purple_loop_builds_incident_from_attack():
    rid = _worked_range()
    pur = learning.generate_purple_incident(rid, chat=chat)
    assert pur["purple"] is True and pur["from_range"] == rid
    assert "investigate" in pur["goal"].lower()
    # ground truth derives from the actual attack
    inc = learning._g()["incidents"][pur["incident_id"]]
    assert "web1" in inc["ground_truth"]["compromised"]
    assert "T1190" in inc["ground_truth"]["techniques"]


def test_purple_requires_a_compromise():
    g = learning.generate_range("offensive-security", chat=chat)  # nothing compromised
    assert "compromise at least one host" in learning.generate_purple_incident(g["range_id"], chat=chat)["error"]


# ---- CORE 9: reporting engine ----
def test_report_graded_on_four_dimensions():
    res = learning.grade_report({
        "executive_summary": "Critical RCE found",
        "technical_findings": "Log4Shell on web1 (T1190)",
        "risk_rating": "Critical",
        "evidence": "JNDI payload + response",
        "reproduction_steps": "send the header",
        "remediation": "upgrade log4j to 2.17",
    }, chat=chat)
    assert res["overall"] == 78 and res["passed"] is True
    assert set(res["scores"]) == {"technical_accuracy", "clarity",
                                  "business_communication", "remediation_quality"}


def test_empty_report_rejected():
    assert "empty" in learning.grade_report({}, chat=chat)["error"]


def test_report_flags_missing_sections():
    res = learning.grade_report({"executive_summary": "x"}, chat=chat)
    assert "remediation" in res["missing"]
