"""CORE 13 — quality feedback loop + auto-quarantine, and
CORE 14 — content caching with offline fallback."""
import json

import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state():
    learning._state.clear()
    learning._state.update(learning._blank())
    yield


HOSTS = [{"id": "web1", "hostname": "web1", "kind": "web",
          "services": [{"port": 80, "name": "http"}], "enum_hint": "x", "vuln": "log4shell",
          "exploit": "jndi rce", "technique": "T1190", "access_level": "www",
          "privesc": "sudo", "persistence": "cron", "loot": "f", "pivots_to": []}]
GOOD = {"scenario": "s", "entry_points": ["web1"],
        "objective": {"goal": "exfil", "target_host": "web1", "flag": "FLAG"}, "hosts": HOSTS}


def chat(member, messages):
    s = messages[0]["content"].lower()
    if "penetration-testing ranges" in s:
        return True, json.dumps(GOOD), None
    if "approve" in s:
        return True, json.dumps({"approve": True, "issues": []}), None
    return True, "ok", None


# ---- CORE 14: caching + fallback ----
def test_validated_range_is_cached(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    g = learning.generate_range("offensive-security", chat=chat)
    assert g.get("cached") is False and g["content_id"]
    assert learning.cache_status()["cached"].get("range") == 1


def test_offline_falls_back_to_cache(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    learning.generate_range("offensive-security", chat=chat)   # seed the cache
    monkeypatch.setattr(learning, "_backend_member", lambda: None)   # backend down
    g = learning.generate_range("offensive-security", chat=chat)
    assert g.get("cached") is True and len(g["hosts"]) == 1
    assert g.get("error") is None


def test_no_cache_no_backend_errors(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: None)
    assert learning.generate_range("offensive-security", chat=chat)["error"] == "no_backend"


def test_cached_instance_starts_clean(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    g = learning.generate_range("offensive-security", chat=chat)
    learning.range_enumerate(g["range_id"], "web1")  # mutate the live instance
    monkeypatch.setattr(learning, "_backend_member", lambda: None)
    g2 = learning.generate_range("offensive-security", chat=chat)   # from cache
    assert all(h["enumerated"] is False for h in g2["hosts"])       # fresh state


# ---- CORE 13: quality + quarantine ----
def test_quality_events_recorded():
    learning.record_quality("c1", "attempt")
    learning.record_quality("c1", "hint")
    learning.record_quality("c1", "solve")
    item = next(i for i in learning.quality_snapshot()["items"] if i["id"] == "c1")
    assert item["attempts"] == 1 and item["hints"] == 1 and item["solves"] == 1


def test_bug_report_quarantines():
    res = learning.record_quality("c2", "bug")
    assert res["quarantined"] is True
    assert "c2" in learning.quality_snapshot()["quarantined"]


def test_repeated_disputes_quarantine():
    assert learning.record_quality("c3", "dispute")["quarantined"] is False
    assert learning.record_quality("c3", "dispute")["quarantined"] is True


def test_high_failure_rate_quarantines():
    for _ in range(4):
        learning.record_quality("c4", "attempt")
    for _ in range(3):
        learning.record_quality("c4", "fail")
    assert learning._is_quarantined("c4") is True


def test_quarantined_template_not_reused_offline(monkeypatch):
    monkeypatch.setattr(learning, "_backend_member", lambda: {"name": "T"})
    g = learning.generate_range("offensive-security", chat=chat)
    learning.record_quality(g["content_id"], "bug")        # quarantine the template
    monkeypatch.setattr(learning, "_backend_member", lambda: None)
    g2 = learning.generate_range("offensive-security", chat=chat)
    assert g2.get("error") == "no_backend"                 # the bad cache is skipped
