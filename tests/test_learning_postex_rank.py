"""Post-exploitation (privilege escalation + persistence), range hints, the
job-field rank ladder, and adaptive difficulty."""
import json

import pytest

from maybot_control_center import learning, cultivation


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "Tutor"})
    yield


def chat(member, messages):
    s = messages[0]["content"].lower()
    if "penetration-testing ranges" in s:
        return True, json.dumps({
            "scenario": "x", "objective": {"goal": "exfil", "target_host": "dc1", "flag": "FLAG{x}"},
            "entry_points": ["web1"],
            "hosts": [
                {"id": "web1", "hostname": "web1", "kind": "web",
                 "services": [{"port": 80, "name": "http"}], "enum_hint": "cms", "vuln": "rce",
                 "exploit": "shell", "access_level": "www-data", "privesc": "sudo misconfig",
                 "persistence": "cron job", "loot": "creds", "pivots_to": ["dc1"]},
                {"id": "dc1", "hostname": "dc1", "kind": "dc",
                 "services": [{"port": 445, "name": "smb"}], "enum_hint": "kerberoast",
                 "vuln": "weak svc acct", "exploit": "kerberoast", "access_level": "user",
                 "privesc": "dcsync", "persistence": "golden ticket", "loot": "FLAG{x}",
                 "pivots_to": []},
            ]}), None
    if "post-exploitation step" in s:
        return True, json.dumps({"score": 80, "feedback": "good", "tradecraft": "watch logs"}), None
    if "penetration-test assessor" in s:
        return True, json.dumps({"score": 85, "feedback": "ok", "tradecraft": "evidence"}), None
    if "lab mentor" in s:
        return True, "Check sudo -l for a misconfig.", None
    return True, "ok", None


def _pwn_web(rng_chat=chat):
    r = learning.generate_range("offensive-security", chat=rng_chat)
    learning.range_enumerate(r["range_id"], "web1")
    learning.range_exploit(r["range_id"], "web1", "rce via upload", chat=rng_chat)
    return r["range_id"]


# ---- privilege escalation ----
def test_privesc_requires_compromise_first():
    r = learning.generate_range("offensive-security", chat=chat)
    res = learning.range_escalate(r["range_id"], "web1", "sudo abuse", chat=chat)
    assert "compromise the host" in res["error"]


def test_privilege_escalation_flow():
    rid = _pwn_web()
    res = learning.range_escalate(rid, "web1", "abuse the sudo misconfiguration", chat=chat)
    assert res["escalated"] is True and res["tradecraft"]
    web = next(h for h in learning.get_range(rid)["hosts"] if h["id"] == "web1")
    assert web["access_level"] == "admin/root" and web["escalated"] is True
    assert learning._g()["game"]["privescs"] == 1
    assert any(b["id"] == "rooted" for b in res["badges"])
    # idempotent
    assert learning.range_escalate(rid, "web1", "again", chat=chat).get("already") is True


# ---- persistence ----
def test_persistence_flow():
    rid = _pwn_web()
    res = learning.range_persist(rid, "web1", "drop a cron job that calls back", chat=chat)
    assert res["persisted"] is True
    assert learning._g()["game"]["persists"] == 1
    assert any(b["id"] == "entrenched" for b in res["badges"])
    web = next(h for h in learning.get_range(rid)["hosts"] if h["id"] == "web1")
    assert web["persisted"] is True


# ---- range hints (spend stones, never the answer) ----
def test_range_hint_costs_stones():
    rid = _pwn_web()
    cultivation.reward(learning.LEARNER, learning.RANGE_HINT_COST * 2)
    res = learning.range_hint(rid, "dc1", "privesc", chat=chat)
    assert res["cost"] == learning.RANGE_HINT_COST and "sudo" in res["hint"].lower()


def test_range_hint_requires_stones(monkeypatch):
    rid = _pwn_web()
    monkeypatch.setattr(learning, "RANGE_HINT_COST", 10**9)
    assert "not enough spirit stones" in learning.range_hint(rid, "dc1", "privesc", chat=chat)["error"]


# ---- AD-aware generation carries privesc + persistence ----
def test_range_hosts_carry_privesc_and_persistence_hidden():
    r = learning.generate_range("offensive-security", chat=chat)
    # hidden from the learner view
    for h in r["hosts"]:
        assert "privesc" not in h and "persistence" not in h
    # stored server-side
    rng = learning._g()["ranges"][r["range_id"]]
    assert rng["hosts"]["dc1"]["privesc"] == "dcsync"
    assert rng["hosts"]["dc1"]["persistence"] == "golden ticket"


# ---- rank ladder ----
def test_rank_ladder_starts_at_intern_and_climbs():
    rank = learning.skill_rank()
    assert rank["rank"] == "Intern / Trainee" and rank["points"] == 0
    assert rank["next_rank"] == "Junior Security Analyst"
    assert [r["role"] for r in rank["ladder"]][-1].startswith("Head of Security")
    # bump mastery and re-check the climb
    learning._g()["game"]["ranges_cleared"] = 20      # lots of points
    higher = learning.skill_rank()
    assert higher["rank_index"] > 0 and higher["points"] >= 300


def test_progress_includes_rank():
    assert "rank" in learning.get_progress()


# ---- adaptive difficulty ----
def test_adaptive_difficulty_scales_with_mastery():
    assert learning._difficulty_band() == "absolute beginner"
    learning._g()["game"]["ranges_cleared"] = 5      # ~75 pts
    assert learning._difficulty_band() in ("intermediate", "advanced")
    learning._g()["game"]["ranges_cleared"] = 30     # expert territory
    assert learning._difficulty_band() == "expert"


def test_difficulty_injected_into_generation_prompts():
    learning._g()["game"]["ranges_cleared"] = 30      # expert
    seen = {}

    def spy(member, messages):
        seen.setdefault("user", messages[1]["content"])
        return True, "lesson", None

    learning.get_lesson("offensive-security", "Lateral Movement & Pivoting", chat=spy)
    assert "Calibrate difficulty" in seen["user"] and "expert" in seen["user"]
