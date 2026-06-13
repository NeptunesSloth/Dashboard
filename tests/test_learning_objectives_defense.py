"""Mission-objective ranges, blue-team incident investigation, tradecraft-focused
grading, and the default-off real-command-execution contract."""
import json

import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    yield


def range_chat(member, messages):
    s = messages[0]["content"].lower()
    if "penetration-testing ranges" in s:
        return True, json.dumps({
            "scenario": "Assess ACME; rules of engagement: internal only.",
            "objective": {"goal": "exfiltrate /srv/finance/payroll_2026.xlsx from the DC",
                          "target_host": "dc1", "flag": "PAYROLL{c0rp-cr0wn-j3wels}"},
            "entry_points": ["web1"],
            "hosts": [
                {"id": "web1", "hostname": "web-01", "ip": "10.0.0.5", "kind": "web",
                 "services": [{"port": 80, "name": "http", "version": "nginx"}],
                 "enum_hint": "outdated CMS", "vuln": "unauth upload -> RCE",
                 "exploit": "upload a webshell", "loot": "ad creds svc:pass", "pivots_to": ["dc1"]},
                {"id": "dc1", "hostname": "dc-01", "ip": "10.0.0.9", "kind": "dc",
                 "services": [{"port": 445, "name": "smb", "version": "x"}],
                 "enum_hint": "credential reuse", "vuln": "pass-the-hash",
                 "exploit": "PtH with looted creds", "loot": "PAYROLL{c0rp-cr0wn-j3wels}",
                 "pivots_to": []},
            ]}), None
    if "senior penetration-test assessor" in s:
        return True, json.dumps({"score": 85, "feedback": "Sound enumeration and root cause.",
                                 "tradecraft": "Cite the evidence that led you to the vuln."}), None
    return True, "ok", None


def incident_chat(member, messages):
    s = messages[0]["content"].lower()
    if "blue-team incident-investigation" in s:
        return True, json.dumps({
            "alert": "EDR flagged encoded PowerShell on WS-3", "tool": "EDR",
            "artifacts": "auth.log...\nweb.log...\nedr.log...\nfw.log...",
            "ground_truth": {"entry_vector": "phishing macro on WS-3",
                             "compromised": ["WS-3", "FILE-01"], "not_compromised": ["WS-9"],
                             "lateral_path": "WS-3 -> FILE-01 over SMB",
                             "exfiltration": "1.2GB to 203.0.113.7 over HTTPS",
                             "timeline": "t0 phish, t1 lateral, t2 exfil"},
            "indicators": ["203.0.113.7", "encoded powershell"]}), None
    if "grade a soc analyst" in s:
        return True, json.dumps({"score": 82, "passed": True,
                                 "feedback": "Correct scope and exfil call.", "missed": []}), None
    return True, "ok", None


# ---------------------------------------------------------------------------
# objective-driven ranges
# ---------------------------------------------------------------------------
def test_range_has_objective_with_hidden_flag():
    r = learning.generate_range("offensive-security", chat=range_chat)
    obj = r["objective"]
    assert obj["goal"].startswith("exfiltrate") and obj["target_host"] == "dc1"
    assert obj["captured"] is False
    assert "flag" not in obj                    # the flag is never sent to the client


def test_range_exploit_grades_on_tradecraft():
    r = learning.generate_range("offensive-security", chat=range_chat)
    learning.range_enumerate(r["range_id"], "web1")
    res = learning.range_exploit(r["range_id"], "web1", "exploit the CMS upload for RCE", chat=range_chat)
    assert res["compromised"] is True
    assert res["tradecraft"]                     # the grader returns a habit to improve


def test_capture_requires_compromising_the_target_first():
    r = learning.generate_range("offensive-security", chat=range_chat)
    # target (dc1) not compromised yet
    res = learning.range_capture(r["range_id"], "PAYROLL{c0rp-cr0wn-j3wels}")
    assert "compromise the objective's target host" in res["error"]


def test_full_objective_capture_flow():
    r = learning.generate_range("offensive-security", chat=range_chat)
    rid = r["range_id"]
    learning.range_enumerate(rid, "web1")
    learning.range_exploit(rid, "web1", "webshell via CMS upload", chat=range_chat)
    learning.range_enumerate(rid, "dc1")
    learning.range_exploit(rid, "dc1", "pass-the-hash with the looted service creds", chat=range_chat)
    # wrong submission is rejected
    bad = learning.range_capture(rid, "not the file")
    assert bad["captured"] is False
    # correct flag captures the objective
    good = learning.range_capture(rid, "the file held PAYROLL{c0rp-cr0wn-j3wels}")
    assert good["captured"] is True
    assert learning._g()["game"]["objectives_captured"] == 1
    assert any(b["id"] == "exfiltrator" for b in good["badges"])
    # idempotent
    again = learning.range_capture(rid, "PAYROLL{c0rp-cr0wn-j3wels}")
    assert again.get("already") is True


# ---------------------------------------------------------------------------
# blue-team incident investigation
# ---------------------------------------------------------------------------
def test_incident_hides_ground_truth_and_states_goal():
    inc = learning.generate_incident("blue-team", chat=incident_chat)
    assert "Scope the compromise" in inc["goal"]
    assert inc["alert"] and inc["artifacts"]
    assert "ground_truth" not in inc            # hidden until graded


def test_incident_grading_scopes_compromise():
    inc = learning.generate_incident("blue-team", chat=incident_chat)
    res = learning.grade_incident(
        inc["incident_id"],
        "WS-3 entry via phishing; pivoted to FILE-01; 1.2GB exfil to 203.0.113.7.",
        chat=incident_chat)
    assert res["solved"] is True
    gt = res["ground_truth"]
    assert "FILE-01" in gt["compromised"] and "203.0.113.7" in gt["exfiltration"]
    assert learning._g()["game"]["incidents_solved"] == 1
    assert any(b["id"] == "incident_handler" for b in res["badges"])


def test_incident_unknown():
    assert "unknown" in learning.grade_incident("nope", "x", chat=incident_chat)["error"]


# ---------------------------------------------------------------------------
# real-command execution contract (default off)
# ---------------------------------------------------------------------------
def test_real_env_off_by_default(monkeypatch):
    monkeypatch.setattr(learning, "REAL_LABS", False)
    st = learning.real_env_status()
    assert st["enabled"] is False and st["configured_targets"] == []
    assert st["ready"] is False
    assert learning.attach_real_env({}, "web1") is None


def test_pentest_toolkit_catalog_and_phases():
    tools = learning.recommended_pentest_tools()
    names = {t["name"] for t in tools}
    # the real-world staples are present
    assert {"Nmap", "Metasploit", "sqlmap", "Hydra"} <= names
    phases = {t["phase"] for t in tools}
    assert {"enumeration", "exploitation", "lateral-movement", "post-exploitation"} <= phases
    # every tool maps to a tools.yaml entry name and at least one host kind
    for t in tools:
        assert t["tool"] and t["kinds"]


def test_pentest_toolkit_filters_by_host_kind():
    web = {t["name"] for t in learning.recommended_pentest_tools("web")}
    dc = {t["name"] for t in learning.recommended_pentest_tools("dc")}
    assert "sqlmap" in web and "WPScan" in web        # web-appropriate
    assert "Metasploit" in dc and "WPScan" not in dc  # AD-appropriate, not web
    assert learning.recommended_pentest_tools() != learning.recommended_pentest_tools("web")


def test_real_env_exposes_toolkit(monkeypatch):
    monkeypatch.setattr(learning, "REAL_LABS", False)
    st = learning.real_env_status()
    assert st["toolkit"] and any(t["name"] == "Metasploit" for t in st["toolkit"])
    assert st["gui_tools"] and any("Burp" in g for g in st["gui_tools"])


def test_real_env_requirements_checklist(monkeypatch):
    monkeypatch.setattr(learning, "REAL_LABS", False)
    st = learning.real_env_status()
    labels = " | ".join(r["label"].lower() for r in st["requirements"])
    assert "toggle" in labels and "real_targets.yaml" in labels
    assert "tools.yaml" in labels and "sandbox" in labels and "no egress" in labels
    assert st["docs"] == "docs/REAL_LABS.md"
    assert st["requirements"][0]["met"] is False        # toggle reflects the gate


def test_settings_toggle_flips_real_labs(monkeypatch):
    from maybot_control_center import settings
    monkeypatch.setattr(learning, "REAL_LABS", False)
    try:
        settings.set_value("MAYBOT_REAL_LABS", "1")      # the one-click button
        assert learning.REAL_LABS is True
        assert learning.real_env_status()["requirements"][0]["met"] is True
        settings.set_value("MAYBOT_REAL_LABS", "0")
        assert learning.REAL_LABS is False
    finally:
        settings._overrides.pop("MAYBOT_REAL_LABS", None)
        import os
        os.environ.pop("MAYBOT_REAL_LABS", None)


def test_real_env_binding_when_enabled(monkeypatch, tmp_path):
    f = tmp_path / "real_targets.yaml"
    f.write_text(
        "targets:\n"
        "  - host_id: web1\n"
        "    agent: lab-attacker\n"
        "    target: 10.10.0.10\n"
        "    network: 10.10.0.0/24\n"
        "    allowed_tools: [nmap_scan, nikto_scan]\n")
    monkeypatch.setattr(learning, "REAL_LABS", True)
    monkeypatch.setattr(learning, "REAL_TARGETS_FILE", f)
    st = learning.real_env_status()
    assert st["enabled"] is True and "web1" in st["configured_targets"]
    binding = learning.attach_real_env({}, "web1")
    assert binding["agent"] == "lab-attacker" and binding["target"] == "10.10.0.10"
    assert binding["allowed_tools"] == ["nmap_scan", "nikto_scan"]
    assert binding["requires_approval"] is True
    # an unbound host still returns None even when the feature is on
    assert learning.attach_real_env({}, "unbound") is None
