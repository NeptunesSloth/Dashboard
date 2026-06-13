"""CORE PROBLEM 4 — graduation requires real execution, not simulation. The
ephemeral sandbox provisioning is operator-run (deploy/lab-range/); this gates
the credential on a VERIFIED real-execution proof."""
import pytest

from maybot_control_center import learning


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    learning._state.clear()
    learning._state.update(learning._blank())
    monkeypatch.setattr(learning, "REAL_LABS", False)
    yield


def _reach_grad_rank():
    learning._g()["game"]["ranges_cleared"] = 10   # plenty of mastery points


def test_fresh_learner_is_not_graduated():
    gs = learning.graduation_status()
    assert gs["graduated"] is False
    assert all(r["met"] is False for r in gs["requirements"])


def test_simulation_alone_does_not_graduate(monkeypatch):
    _reach_grad_rank()
    # an UNVERIFIED proof (i.e. simulation) must not count
    learning.record_execution_proof("Web Security", "claimed exploit", verified=False)
    gs = learning.graduation_status()
    assert gs["graduated"] is False
    assert gs["verified_executions"] == 0


def test_verified_execution_required_and_graduates(monkeypatch):
    _reach_grad_rank()
    monkeypatch.setattr(learning, "REAL_LABS", True)
    # still not graduated until a verified proof exists
    assert learning.graduation_status()["graduated"] is False
    learning.record_execution_proof("Web Security", "exploited Juice Shop SQLi in sandbox",
                                    verified=True, lab="juice", tool="sqlmap")
    gs = learning.graduation_status()
    assert gs["graduated"] is True
    assert gs["verified_executions"] == 1 and "Web Security" in gs["domains_proven"]


def test_verified_proof_credits_domain():
    before = {d["domain"]: d["points"] for d in learning.domain_mastery()["domains"]}
    learning.record_execution_proof("Active Directory", "DCSync in sandbox", verified=True)
    after = {d["domain"]: d["points"] for d in learning.domain_mastery()["domains"]}
    assert after["Active Directory"] > before["Active Directory"]


def test_execution_proofs_recorded():
    learning.record_execution_proof("Web Security", "x", verified=True)
    learning.record_execution_proof("Cloud Security", "y", verified=False)
    proofs = learning.execution_proofs()
    assert len(proofs) == 2 and proofs[0]["verified"] is True
