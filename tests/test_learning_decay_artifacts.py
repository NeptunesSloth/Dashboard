"""CORE PROBLEM 7 — skill decay (retention), and
CORE PROBLEM 8 — real-world artifact labs (no synthetic-only)."""
import json
import time

import pytest

from maybot_control_center import learning, lab_artifacts


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    learning._skills_cache = None
    yield


# ---- CORE 7: skill decay ----
def test_mastery_decays_without_practice():
    learning._award_domain("Web Security", 90)
    # pretend it was last practised 120 days ago
    learning._g()["game"]["domain_practiced"]["Web Security"] = int(time.time()) - 120 * 86400
    web = next(d for d in learning.domain_mastery()["domains"] if d["domain"] == "Web Security")
    assert web["points"] == 90
    assert 55 <= web["retained"] <= 80      # decayed below raw (≈67 in the example)
    assert web["decayed"] is True and web["needs_reassessment"] is True


def test_recent_practice_no_decay():
    learning._award_domain("Cloud Security", 40)   # practised just now
    cloud = next(d for d in learning.domain_mastery()["domains"] if d["domain"] == "Cloud Security")
    assert cloud["retained"] == 40 and cloud["decayed"] is False


def test_decay_relocks_skills_until_reassessed():
    learning._award_domain("Web Security", 100)
    g = learning._g()["game"]
    by_id = {s["id"]: s for s in learning.skill_graph()["skills"]}
    assert by_id["web-vulnerabilities"]["mastered"] is True
    # let it decay far past the node threshold
    g["domain_practiced"]["Web Security"] = int(time.time()) - 3000 * 86400
    by_id2 = {s["id"]: s for s in learning.skill_graph()["skills"]}
    assert by_id2["web-vulnerabilities"]["mastered"] is False   # re-locked
    # reassessing (any practice) restores it
    learning._award_domain("Web Security", 1)
    by_id3 = {s["id"]: s for s in learning.skill_graph()["skills"]}
    assert by_id3["web-vulnerabilities"]["mastered"] is True


def test_reassess_list_surfaced():
    learning._award_domain("Active Directory", 50)
    learning._g()["game"]["domain_practiced"]["Active Directory"] = int(time.time()) - 400 * 86400
    dm = learning.domain_mastery()
    assert "Active Directory" in dm["reassess"]


# ---- CORE 8: real-world artifacts ----
def test_artifact_catalog_covers_real_types():
    cat = lab_artifacts.catalog()
    types = {t["type"] for t in cat["types"]}
    assert {"pcap", "memory", "apache_log", "windows_event", "sysmon",
            "malware_script", "iam_policy", "s3_config", "terraform", "docker"} <= types


def test_artifact_type_has_tool_and_domain():
    pcap = lab_artifacts.artifact_type("pcap")
    assert "Wireshark" in pcap["tool"] and pcap["domain"] == "Network Security"
    mem = lab_artifacts.artifact_type("memory")
    assert "Volatility" in mem["tool"]


def test_generate_artifact_lab(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})

    def chat(member, messages):
        if "real-artifact analysis lab" in messages[0]["content"].lower():
            return True, json.dumps({"brief": "find it", "artifact": "real apache log lines",
                                     "answer": "web shell upload", "indicators": ["up.php"]}), None
        return True, "ok", None

    lab = learning.generate_artifact_lab("blue-team", "apache_log", chat=chat)
    assert lab["error"] is None and lab["artifact_type"] == "apache_log"
    assert "SIEM" in lab["tool"] and lab["domain"] == "Incident Response"
    # it is graded via the normal lab grader
    g = learning.grade_lab(lab["lab_id"], "web shell uploaded via up.php", chat=lambda m, msgs:
                           (True, json.dumps({"score": 80, "feedback": "ok"}), None))
    assert g["solved"] is True


def test_unknown_artifact_type():
    assert "unknown artifact type" in learning.generate_artifact_lab("blue-team", "nope")["error"]


def test_registered_artifact_is_used(monkeypatch, tmp_path):
    f = tmp_path / "arts.yaml"
    f.write_text("artifacts:\n  - type: pcap\n    name: Cap\n    source: ./x.pcap\n    note: open in wireshark\n")
    monkeypatch.setattr(lab_artifacts, "ARTIFACTS_FILE", f)
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    seen = {}

    def chat(member, messages):
        if "real-artifact" in messages[0]["content"].lower():
            seen["user"] = messages[1]["content"]
            return True, json.dumps({"brief": "b", "artifact": "a", "answer": "x", "indicators": []}), None
        return True, "ok", None

    lab = learning.generate_artifact_lab("blue-team", "pcap", chat=chat)
    assert lab["real_artifact"] is True and "./x.pcap" in seen["user"]
    assert "REAL artifact" in lab["artifact"]
