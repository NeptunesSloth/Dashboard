"""CORE PROBLEM 5 — skill dependency graph (no skipping prerequisites), and
CORE PROBLEM 6 — per-domain mastery with per-domain adaptive difficulty."""
import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    learning._skills_cache = None
    yield


# ---- CORE 6: per-domain mastery ----
def test_domain_classification():
    assert learning.classify_domain("Web App Security OWASP sql injection") == "Web Security"
    assert learning.classify_domain("Active Directory Kerberoasting DCSync") == "Active Directory"
    assert learning.classify_domain("Cloud IAM metadata SSRF") == "Cloud Security"
    assert learning.classify_domain("Incident triage in the SOC SIEM") == "Incident Response"
    assert learning.classify_domain("nothing relevant here") == ""


def test_domain_mastery_tracked_independently():
    learning._award_domain("Web Security", 50)
    learning._award_domain("Active Directory", 4)
    dm = learning.domain_mastery()
    web = next(d for d in dm["domains"] if d["domain"] == "Web Security")
    ad = next(d for d in dm["domains"] if d["domain"] == "Active Directory")
    assert web["points"] == 50 and ad["points"] == 4
    assert web["band"] != ad["band"]              # difficulty differs per domain
    assert dm["strongest"] == "Web Security"
    assert len(dm["domains"]) == len(learning.DOMAINS)


def test_difficulty_adapts_per_domain():
    learning._award_domain("Web Security", 300)   # expert
    assert learning._domain_band("Web Security") == "expert"
    assert learning._domain_band("Active Directory") == "absolute beginner"
    # the per-domain band flows into the generation prompt
    assert "expert" in learning._profile_brief("Web Security")
    assert "absolute beginner" in learning._profile_brief("Active Directory")


def test_lesson_credits_its_domain(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    learning.get_lesson("offensive-security", "Web Exploitation (OWASP Top 10 in depth)",
                        chat=lambda m, msgs: (True, "lesson", None))
    dm = {d["domain"]: d["points"] for d in learning.domain_mastery()["domains"]}
    assert dm["Web Security"] >= 1


# ---- CORE 5: skill dependency graph ----
def test_skill_graph_locks_advanced_until_prereqs():
    sg = learning.skill_graph()
    assert sg["total"] > 15
    by_id = {s["id"]: s for s in sg["skills"]}
    # foundations with no prereqs are unlocked from the start
    assert by_id["networking-fundamentals"]["unlocked"] is True
    # advanced nodes are locked with prereqs listed
    assert by_id["advanced-web-exploitation"]["unlocked"] is False
    assert by_id["advanced-web-exploitation"]["missing_prereqs"]
    assert by_id["domain-dominance"]["unlocked"] is False


def test_prereqs_unlock_as_domains_are_mastered():
    learning._award_domain("Web Security", 100)   # past the node threshold
    by_id = {s["id"]: s for s in learning.skill_graph()["skills"]}
    assert by_id["web-vulnerabilities"]["mastered"] is True
    # but a cross-domain node still needs its OTHER prerequisite domain
    assert by_id["ad-attacks"]["unlocked"] is False   # needs Privilege Escalation too
    learning._award_domain("Privilege Escalation", 100)
    learning._award_domain("Active Directory", 100)
    by_id2 = {s["id"]: s for s in learning.skill_graph()["skills"]}
    assert by_id2["ad-attacks"]["unlocked"] is True


def test_prereqs_met_for_topic():
    assert learning.prereqs_met("Advanced Web Exploitation")["ok"] is False
    assert learning.prereqs_met("a topic not in the graph")["in_graph"] is False


def test_enforced_prereqs_block_lesson(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    monkeypatch.setattr(learning, "ENFORCE_PREREQS", True)
    res = learning.get_lesson("offensive-security", "Advanced Web Exploitation",
                              chat=lambda m, msgs: (True, "x", None))
    assert res.get("locked") is True and res["missing_prereqs"]


def test_progress_includes_mastery_and_rank():
    p = learning.get_progress()
    assert "domain_mastery" in p and "rank" in p
