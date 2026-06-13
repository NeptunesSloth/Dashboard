"""CORE PROBLEM 1 — ground truth: the canonical knowledge base, the scenario
validation engine, and multi-agent consensus that gate every generated range so
hallucinated/broken attack chains never reach a learner."""
import json

from maybot_control_center import knowledge, validation, consensus, learning


# ---- canonical knowledge base ----
def test_kb_loads_and_resolves_real_ids():
    snap = knowledge.snapshot()
    assert snap["total"] > 50 and snap["counts"]["techniques"] > 20
    assert knowledge.resolve("T1190")["name"].startswith("Exploit Public-Facing")
    assert knowledge.resolve("CVE-2021-44228")  # Log4Shell
    assert knowledge.resolve("A03")             # OWASP Injection


def test_kb_rejects_fabricated_ids():
    assert knowledge.resolve("T9999") is None
    assert knowledge.resolve("CVE-2099-0001") is None


def test_kb_extracts_known_vs_unknown_references():
    refs = knowledge.extract_references("Chain T1558.003 then CVE-2020-1472, also T9999 and CVE-2099-9999")
    assert "T1558.003" in refs["known"] and "CVE-2020-1472" in refs["known"]
    assert "T9999" in refs["unknown"] and "CVE-2099-9999" in refs["unknown"]


def test_kb_internally_consistent():
    # every CVE's cited technique must itself resolve in the KB
    for c in knowledge.load()["sections"]["cves"]:
        assert knowledge.resolve(c["technique"]) is not None, c["id"]


# ---- validation engine ----
def _good_parsed():
    return {"track": "x", "scenario": "s", "entry_points": ["web1"],
            "objective": {"goal": "exfil", "target_host": "dc1", "flag": "FLAG{x}"},
            "hosts": {
                "web1": {"kind": "web", "exploit": "jndi rce", "technique": "T1190",
                         "cve": "CVE-2021-44228", "vuln": "log4shell",
                         "privesc": "sudo misconfiguration", "pivots_to": ["dc1"], "loot": "creds"},
                "dc1": {"kind": "dc", "exploit": "kerberoast then dcsync", "technique": "T1558.003",
                        "vuln": "weak svc acct", "privesc": "dcsync replication",
                        "pivots_to": [], "loot": "FLAG{x}"}}}


def test_validation_approves_grounded_consistent_range():
    r = validation.validate_range(_good_parsed())
    assert r["approved"] is True and r["grounded_hosts"] == 2 and r["confidence"] > 70


def test_validation_rejects_hallucinated_reference():
    p = _good_parsed()
    p["hosts"]["web1"]["technique"] = "T9999"        # fabricated
    r = validation.validate_range(p)
    assert r["approved"] is False
    assert any(i["code"] == "unknown_reference" for i in r["hard"])


def test_validation_rejects_broken_attack_graph():
    p = _good_parsed()
    p["hosts"]["web1"]["pivots_to"] = ["ghost"]      # dangling
    r = validation.validate_range(p)
    assert r["approved"] is False
    codes = {i["code"] for i in r["hard"]}
    assert "dangling_pivot" in codes and "unreachable_hosts" in codes


def test_validation_rejects_unreachable_objective():
    p = _good_parsed()
    p["objective"]["target_host"] = "island"
    p["hosts"]["island"] = {"kind": "server", "exploit": "x", "technique": "T1190", "pivots_to": []}
    r = validation.validate_range(p)
    assert r["approved"] is False
    assert any(i["code"] in ("objective_unreachable", "unreachable_hosts") for i in r["hard"])


def test_validation_warns_on_missing_exploit():
    p = _good_parsed()
    p["hosts"]["dc1"]["exploit"] = ""
    r = validation.validate_range(p)
    assert r["approved"] is False
    assert any(i["code"] == "no_exploit" for i in r["hard"])


# ---- multi-agent consensus ----
def _panel(approve_roles):
    def chat(member, messages):
        s = messages[0]["content"].lower()
        if "adversarial" in s:
            return True, json.dumps({"approve": "adversarial" in approve_roles, "issues": ["x"]}), None
        if "fact checker" in s:
            return True, json.dumps({"approve": "factcheck" in approve_roles, "issues": ["x"]}), None
        if "simulate the attack" in s:
            return True, json.dumps({"approve": "pathsim" in approve_roles, "issues": ["x"]}), None
        return True, "ok", None
    return chat


def test_consensus_approves_when_panel_agrees(monkeypatch):
    monkeypatch.setattr(consensus, "THRESHOLD", 3)
    rep = consensus.review_range(_good_parsed(), chat=_panel({"adversarial", "factcheck", "pathsim"}))
    assert rep["approved"] is True and rep["llm_reviewers"] == 3
    assert rep["deterministic_ok"] is True and rep["panel_ok"] is True


def test_consensus_blocks_when_a_reviewer_dissents(monkeypatch):
    monkeypatch.setattr(consensus, "THRESHOLD", 3)
    rep = consensus.review_range(_good_parsed(), chat=_panel({"factcheck", "pathsim"}))  # adversarial rejects
    assert rep["approved"] is False and rep["panel_ok"] is False


def test_consensus_deterministic_veto_overrides_panel():
    # even a unanimous LLM panel can't approve a hallucinated scenario
    p = _good_parsed()
    p["hosts"]["web1"]["technique"] = "T9999"
    rep = consensus.review_range(p, chat=_panel({"adversarial", "factcheck", "pathsim"}))
    assert rep["approved"] is False and rep["deterministic_ok"] is False


def test_consensus_deterministic_only_when_no_panel():
    rep = consensus.review_range(_good_parsed(), panel=False)
    assert rep["approved"] is True and rep["llm_reviewers"] == 0


# ---- end-to-end through generate_range ----
def test_generate_range_repairs_then_serves(monkeypatch):
    learning._state.clear(); learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    bad = {"scenario": "s", "entry_points": ["web1"],
           "objective": {"goal": "x", "target_host": "web1", "flag": "F"},
           "hosts": [{"id": "web1", "kind": "web", "exploit": "x", "technique": "T9999", "pivots_to": []}]}
    good = {"scenario": "s", "entry_points": ["web1"],
            "objective": {"goal": "x", "target_host": "web1", "flag": "F"},
            "hosts": [{"id": "web1", "kind": "web", "exploit": "log4shell rce", "technique": "T1190",
                       "cve": "CVE-2021-44228", "vuln": "log4j", "privesc": "sudo misconfiguration",
                       "pivots_to": [], "loot": "F"}]}
    calls = {"n": 0}

    def chat(member, messages):
        s = messages[0]["content"].lower()
        if "penetration-testing ranges" in s:
            calls["n"] += 1
            return True, json.dumps(bad if calls["n"] == 1 else good), None
        if "approve" in s:
            return True, json.dumps({"approve": True, "issues": []}), None
        return True, "ok", None

    g = learning.generate_range("offensive-security", chat=chat)
    assert g.get("error") is None and g["validation"]["approved"] is True
    assert calls["n"] == 2   # first (hallucinated) rejected, repaired on the second


def test_generate_range_refuses_persistently_bad(monkeypatch):
    learning._state.clear(); learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    bad = {"scenario": "s", "entry_points": ["web1"],
           "objective": {"goal": "x", "target_host": "web1", "flag": "F"},
           "hosts": [{"id": "web1", "kind": "web", "exploit": "x", "technique": "T9999", "pivots_to": []}]}

    def chat(member, messages):
        s = messages[0]["content"].lower()
        if "penetration-testing ranges" in s:
            return True, json.dumps(bad), None
        return True, json.dumps({"approve": True, "issues": []}), None

    g = learning.generate_range("offensive-security", chat=chat)
    assert "failed multi-agent review" in (g.get("error") or "")
