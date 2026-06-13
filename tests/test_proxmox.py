"""Real Proxmox provider driver — unit-tested against a MOCKED Proxmox API
(no live node, no network). Proves: health is 'ok' only after a reachability
check, launch clones+isolates+starts and confirms running, failures roll back,
connect_url stays None (no browser access yet), reset re-clones, destroy cleans
up, and orphaned VMs are reaped.

A real STAGING-NODE integration test is gated behind MAYBOT_PROXMOX_INTEGRATION
and skipped by default (see the bottom of this file)."""
import os

import pytest

from maybot_control_center import orchestration as orch
from maybot_control_center import proxmox


class FakeProxmox:
    """In-memory stand-in for the Proxmox API. Records calls; simulates VM state."""

    def __init__(self, reachable=True, fail_on=None, templates=None):
        self.node = "pve1"
        self.reachable = reachable
        self.fail_on = fail_on          # "clone" | "start" | None
        self._next = 1000
        self.vms = {}                   # vmid -> {name, status, net0}
        self.calls = []

    def version(self):
        if not self.reachable:
            raise proxmox.ProxmoxError("connection refused")
        return {"version": "8.1.4"}

    def next_id(self):
        self._next += 1
        return self._next

    def clone(self, src, newid, name):
        self.calls.append(("clone", src, newid, name))
        if self.fail_on == "clone":
            raise proxmox.ProxmoxError("clone failed")
        self.vms[newid] = {"vmid": newid, "name": name, "status": "stopped", "net0": None}
        return f"UPID:clone:{newid}"

    def wait_task(self, upid, timeout):
        return True

    def set_net(self, vmid, net0):
        self.vms[vmid]["net0"] = net0

    def start(self, vmid):
        self.calls.append(("start", vmid))
        if self.fail_on == "start":
            raise proxmox.ProxmoxError("start failed")
        return f"UPID:start:{vmid}"

    def wait_running(self, vmid, timeout):
        self.vms[vmid]["status"] = "running"
        return True

    def vm_status(self, vmid):
        return self.vms.get(vmid, {}).get("status", "stopped")

    def stop(self, vmid):
        self.calls.append(("stop", vmid))
        if vmid in self.vms:
            self.vms[vmid]["status"] = "stopped"
        return f"UPID:stop:{vmid}"

    def destroy(self, vmid):
        self.calls.append(("destroy", vmid))
        self.vms.pop(vmid, None)
        return f"UPID:destroy:{vmid}"

    def list_vms(self):
        return list(self.vms.values())


TMAP = {"kali_template": 9000, "windows_workstation": 9200, "domain_controller": 9201,
        "apache_vuln": 9101, "linux_privesc": 9102}


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    orch._state["sessions"] = {}
    orch._state["events"] = []
    orch._state["validations"] = []
    monkeypatch.setattr(proxmox, "template_map", lambda: dict(TMAP))
    monkeypatch.setenv("MAYBOT_RANGE_PROVIDER", "proxmox")
    fake = FakeProxmox()
    proxmox.set_test_client(fake)
    yield fake
    proxmox.set_test_client(None)


def _prov():
    return orch.get_provider("proxmox")


# ---- health: ok only after a live reachability check ----
def test_health_ok_when_reachable():
    assert _prov().health()["status"] == "ok"


def test_health_error_when_unreachable(wired):
    wired.reachable = False
    h = _prov().health()
    assert h["status"] == "error" and "unreachable" in h["detail"].lower()


def test_health_not_configured_without_client():
    proxmox.set_test_client(None)        # and no env config
    assert _prov().health()["status"] == "not_configured"


# ---- launch: clone + isolate + start + confirm running ----
def test_launch_clones_isolates_starts_and_confirms_running(wired):
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    assert res["ok"] is True and res["status"] == "running"
    # three VMs (kali attacker + 2 AD targets), all confirmed running by the API
    assert len(wired.vms) == 3
    assert all(v["status"] == "running" for v in wired.vms.values())
    # each NIC is on the lab bridge with a unique VLAN tag + firewall (isolation)
    for v in wired.vms.values():
        assert f"bridge={proxmox.LAB_BRIDGE}" in v["net0"]
        assert "tag=" in v["net0"] and "firewall=1" in v["net0"]


def test_launch_returns_no_connect_url_without_browser_access():
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    assert res["session"]["connect_url"] is None     # Guacamole/noVNC not wired
    assert "browser access" in res["detail"].lower()


def test_session_running_only_when_api_confirms(wired):
    res = orch.launch_lab("web_exploit_001", provider="proxmox")
    sid = res["session"]["id"]
    st = orch.session_status(sid)
    assert st["live_status"] == "running"
    # if a VM drops, status is no longer 'running'
    vmid = next(iter(wired.vms))
    wired.vms[vmid]["status"] = "stopped"
    assert orch.session_status(sid)["live_status"] == "degraded"


# ---- failure rollback ----
def test_clone_failure_rolls_back_and_marks_failed(wired):
    wired.fail_on = "clone"
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    assert res["ok"] is False and res["status"] == "failed"
    assert res["session"] is None
    assert wired.vms == {}                            # nothing left running
    assert orch.list_sessions()["count"] == 0


def test_start_failure_rolls_back_created_vms(wired):
    wired.fail_on = "start"
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    assert res["ok"] is False and res["status"] == "failed"
    assert wired.vms == {}                            # cloned VMs were destroyed
    assert any(c[0] == "destroy" for c in wired.calls)   # rollback issued destroys


def test_unmapped_template_fails_cleanly(monkeypatch, wired):
    monkeypatch.setattr(proxmox, "template_map", lambda: {})   # nothing mapped
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    assert res["ok"] is False and res["status"] == "failed"
    assert "not mapped" in res["detail"]
    assert wired.vms == {}


# ---- isolation: unique VLAN per session ----
def test_each_session_gets_a_distinct_vlan(wired):
    a = orch.launch_lab("linux_privesc_001", provider="proxmox")
    b = orch.launch_lab("linux_privesc_001", provider="proxmox")
    va = orch._state["sessions"][a["session"]["id"]]["meta"]["vlan"]
    vb = orch._state["sessions"][b["session"]["id"]]["meta"]["vlan"]
    assert va != vb


# ---- lifecycle: stop / reset / destroy ----
def test_stop_stops_all_vms(wired):
    res = orch.launch_lab("ad_attack_001", provider="proxmox")
    orch.stop_lab(res["session"]["id"])
    assert all(v["status"] == "stopped" for v in wired.vms.values())


def test_reset_destroys_and_reclones(wired):
    res = orch.launch_lab("web_exploit_001", provider="proxmox")
    sid = res["session"]["id"]
    old = sorted(wired.vms.keys())
    r = orch.reset_lab(sid)
    assert r["status"] == "running"
    new = sorted(wired.vms.keys())
    assert new and new != old                          # fresh VMs
    assert all(v["status"] == "running" for v in wired.vms.values())


def test_destroy_removes_vms_and_session(wired):
    res = orch.launch_lab("web_exploit_001", provider="proxmox")
    sid = res["session"]["id"]
    orch.destroy_lab(sid)
    assert wired.vms == {}
    assert orch.session_status(sid)["error"] == "unknown_session"


# ---- hygiene: stuck-session reaper + orphan cleanup ----
def test_reap_stuck_session_destroys_it(wired):
    res = orch.launch_lab("web_exploit_001", provider="proxmox")
    sid = res["session"]["id"]
    orch._state["sessions"][sid]["created"] = 0        # ancient -> past TTL
    out = orch.reap_stuck_sessions()
    assert sid in out["reaped"] and wired.vms == {}


def test_cleanup_orphans_destroys_vms_without_a_session(wired):
    # an orphaned lab VM whose session no longer exists
    wired.vms[7777] = {"vmid": 7777, "name": "maybotlab-sess-99999-attacker-7777",
                       "status": "running", "net0": "x"}
    out = orch.cleanup_orphans("proxmox")
    assert 7777 in out["removed"] and 7777 not in wired.vms


# ---- lifecycle events recorded for each step ----
def test_lifecycle_events_recorded(wired):
    orch.launch_lab("ad_attack_001", provider="proxmox")
    actions = {e["action"] for e in orch.events(50)}
    assert {"clone", "network", "start", "ready"} <= actions


# ---- integration test against a REAL node (disabled by default) ----
@pytest.mark.skipif(os.getenv("MAYBOT_PROXMOX_INTEGRATION") != "1",
                    reason="integration test needs a real staging Proxmox node "
                           "(set MAYBOT_PROXMOX_INTEGRATION=1 + MAYBOT_PROXMOX_URL/_TOKEN/_NODE "
                           "and proxmox_templates.yaml)")
def test_integration_launch_and_destroy_real_node():
    proxmox.set_test_client(None)        # use the real env-configured client
    assert orch.provider_health("proxmox")["status"] == "ok"
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    assert res["ok"] is True and res["status"] == "running"
    try:
        st = orch.session_status(res["session"]["id"])
        assert st["live_status"] == "running"
    finally:
        orch.destroy_lab(res["session"]["id"])
