"""Cyber-range control-plane seam — proves the honesty contract:
unconfigured providers fail safely, no fake VM is ever marked running, and the
API returns honest lifecycle/provider states. NO real VM is launched anywhere."""
import pytest
from starlette.testclient import TestClient

from maybot_control_center import orchestration as orch
from maybot_control_center.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    from maybot_control_center import proxmox
    orch._state["sessions"] = {}
    orch._state["events"] = []
    orch._state["validations"] = []
    proxmox.set_test_client(None)
    monkeypatch.delenv("MAYBOT_RANGE_PROVIDER", raising=False)
    for k in ("MAYBOT_PROXMOX_URL", "MAYBOT_PROXMOX_TOKEN", "MAYBOT_PROXMOX_NODE"):
        monkeypatch.delenv(k, raising=False)
    yield


# ---- providers fail safe ----
def test_default_provider_is_not_configured():
    h = orch.provider_health()
    assert h["status"] == "not_configured" and h["configured"] is False
    listing = orch.list_providers()
    assert listing["selected"] == "none"
    assert {p["name"] for p in listing["providers"]} >= {"none", "proxmox"}


def test_proxmox_without_config_is_not_configured():
    assert orch.provider_health("proxmox")["status"] == "not_configured"
    # (real-driver health/launch behaviour is covered with a mocked API in
    #  tests/test_proxmox.py — no real node is contacted)


# ---- launch is honestly rejected; no fake running VM ----
def test_launch_with_no_infra_is_rejected_and_creates_no_session():
    res = orch.launch_lab("ad_attack_001")
    assert res["ok"] is False and res["status"] == "unavailable"
    assert res["session"] is None
    assert orch.list_sessions()["count"] == 0           # nothing marked running


def test_no_session_ever_has_running_status():
    orch.launch_lab("ad_attack_001")
    orch.launch_lab("web_exploit_001")
    statuses = [s["status"] for s in orch.list_sessions()["sessions"]]
    assert "running" not in statuses and statuses == []  # zero fake VMs


def test_unknown_lab_rejected():
    assert orch.launch_lab("does_not_exist")["error"] == "unknown_lab"


# ---- catalog is config-driven and honest about liveness ----
def test_catalog_lists_labs_and_reports_not_live():
    labs = orch.list_labs()
    ids = {l["lab_id"] for l in labs["labs"]}
    assert {"ad_attack_001", "web_exploit_001"} <= ids
    assert labs["live"] is False                         # not live without a provider
    assert labs["infrastructure"]["status"] == "not_configured"


# ---- API returns honest lifecycle states ----
def test_api_providers_and_health():
    assert client.get("/api/range-infra/providers").json()["selected"] == "none"
    assert client.get("/api/range-infra/health").json()["status"] == "not_configured"


def test_api_launch_is_honest():
    r = client.post("/api/range-infra/launch", json={"lab_id": "ad_attack_001"}).json()
    assert r["ok"] is False and r["status"] == "unavailable" and r["session"] is None
    assert "not connected" in r["detail"].lower() or "infrastructure" in r["detail"].lower()
    # and no session leaked into the listing
    assert client.get("/api/range-infra/sessions").json()["count"] == 0


def test_api_labs_endpoint_marks_not_live():
    body = client.get("/api/range-infra/labs").json()
    assert body["live"] is False and body["labs"]


def test_api_unknown_session_status():
    assert client.get("/api/range-infra/session/nope").json()["error"] == "unknown_session"


# ---- validation engine records deterministic results (not AI) ----
def test_record_validation_result():
    rec = orch.record_validation("sess-x", "root_shell_obtained", True, {"uid": 0})
    assert rec["passed"] is True and rec["condition"] == "root_shell_obtained"
    assert orch._state["validations"][-1]["evidence"]["uid"] == 0
