"""CORE 15 — certification mapping + exportable portfolio, and
CORE 12 (foundation) — instructor/employer verifiable record."""
import pytest

from maybot_control_center import learning, certifications


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "REAL_LABS", False)
    yield


def _strong():
    for d, p in [("Web Security", 90), ("Privilege Escalation", 85),
                 ("Active Directory", 75), ("Network Security", 85)]:
        learning._award_domain(d, p)


# ---- CORE 15: certifications ----
def test_certs_cover_the_industry_set():
    names = {c["name"] for c in learning.certifications()["certifications"]}
    assert {"CompTIA Security+", "EC-Council CEH", "OffSec OSCP",
            "ISC2 CISSP", "SANS/GIAC (GPEN/GCIH)"} <= names


def test_readiness_rises_with_mastery():
    low = {c["id"]: c["readiness_pct"] for c in learning.certifications()["certifications"]}
    _strong()
    high = {c["id"]: c["readiness_pct"] for c in learning.certifications()["certifications"]}
    assert high["ceh"] > low["ceh"]


def test_hands_on_cert_blocked_until_graduation(monkeypatch):
    _strong()
    oscp = next(c for c in learning.certifications()["certifications"] if c["id"] == "oscp")
    assert oscp["ready"] is False
    assert any("real execution" in b for b in oscp["blockers"])
    # graduate, then OSCP unblocks
    monkeypatch.setattr(learning, "REAL_LABS", True)
    learning._g()["game"]["ranges_cleared"] = 10
    learning.record_execution_proof("Web Security", "real exploit", verified=True)
    oscp2 = next(c for c in learning.certifications()["certifications"] if c["id"] == "oscp")
    assert not oscp2["blockers"] and oscp2["ready"] is True


def test_non_hands_on_cert_needs_no_execution():
    _strong()
    learning._award_domain("Incident Response", 80)
    learning._award_domain("Cryptography", 80)
    learning._award_domain("Cloud Security", 80)
    cissp = next(c for c in learning.certifications()["certifications"] if c["id"] == "cissp")
    assert cissp["blockers"] == []


# ---- CORE 15: exportable portfolio ----
def test_portfolio_is_verifiable_and_complete():
    _strong()
    learning._g()["game"]["ranges_cleared"] = 3
    pf = learning.portfolio()
    assert pf["learner"] == learning.LEARNER
    assert len(pf["verification"]) == 64        # sha256 hex
    assert pf["evidence"]["ranges_cleared"] == 3
    assert pf["domain_mastery"] and pf["certifications"]


def test_portfolio_hash_changes_with_record():
    h1 = learning.portfolio()["verification"]
    learning._award_domain("Web Security", 50)
    h2 = learning.portfolio()["verification"]
    assert h1 != h2


# ---- CORE 12: instructor/employer view ----
def test_instructor_summary_exposes_verifiable_record():
    ins = learning.instructor_summary()
    assert ins["verification"] == ins["portfolio"]["verification"]
    assert "audit_tail" in ins
    assert "enterprise" in ins["note"].lower()      # honest about multi-tenant scope


# ---- pure cert math ----
def test_cert_readiness_pure_function():
    r = certifications.readiness(
        {"id": "x", "name": "X", "provider": "p", "hands_on": False, "bar": 50,
         "domains": ["Web Security", "Network Security"]},
        {"Web Security": 50, "Network Security": 50}, graduated=False)
    assert r["readiness_pct"] == 100 and r["ready"] is True
