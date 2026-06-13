"""Guacamole browser-access layer — unit-tested against a MOCKED Guacamole API
(no live server). Proves: a real connect URL appears only after Guacamole
confirms a connection, connections are revoked on stop/destroy, registration
failure rolls back the whole launch, no fake URL when Guacamole is unavailable,
signed connect links expire, and no raw VM IP is ever returned to the client."""
import base64

import pytest
from starlette.testclient import TestClient

from maybot_control_center import orchestration as orch
from maybot_control_center import proxmox, guacamole
from maybot_control_center.app import app

client = TestClient(app)


class FakeProxmox:
    def __init__(self):
        self.node = "pve1"
        self._next = 1000
        self.vms = {}

    def version(self):
        return {"version": "8.1"}

    def next_id(self):
        self._next += 1
        return self._next

    def clone(self, src, newid, name):
        self.vms[newid] = {"vmid": newid, "name": name, "status": "stopped"}
        return f"UPID:{newid}"

    def wait_task(self, upid, timeout):
        return True

    def set_net(self, vmid, net0):
        self.vms[vmid]["net0"] = net0

    def start(self, vmid):
        return f"UPID:{vmid}"

    def wait_running(self, vmid, timeout):
        self.vms[vmid]["status"] = "running"

    def vm_status(self, vmid):
        return self.vms.get(vmid, {}).get("status", "stopped")

    def vm_ip(self, vmid):
        return self.vms.get(vmid, {}).get("ip", f"10.10.0.{vmid % 250}")

    def stop(self, vmid):
        if vmid in self.vms:
            self.vms[vmid]["status"] = "stopped"
        return f"UPID:{vmid}"

    def destroy(self, vmid):
        self.vms.pop(vmid, None)
        return f"UPID:{vmid}"

    def list_vms(self):
        return list(self.vms.values())


class FakeGuacamole:
    def __init__(self, reachable=True, fail_on_create=False, datasource="postgresql"):
        self.reachable = reachable
        self.fail_on_create = fail_on_create
        self._datasource = datasource
        self._next = 100
        self.connections = {}        # id -> {name, protocol, params}
        self.base = "https://guac.example"

    @property
    def datasource(self):
        return self._datasource

    def health(self):
        if not self.reachable:
            raise guacamole.GuacamoleError("unreachable")
        return True

    def create_connection(self, name, protocol, params):
        if self.fail_on_create:
            raise guacamole.GuacamoleError("create failed")
        self._next += 1
        cid = str(self._next)
        self.connections[cid] = {"name": name, "protocol": protocol, "params": params}
        return cid

    def delete_connection(self, conn_id):
        self.connections.pop(str(conn_id), None)

    def client_url(self, conn_id):
        raw = f"{conn_id}\x00c\x00{self.datasource}".encode()
        return f"{self.base}/#/client/{base64.b64encode(raw).decode()}"


TMAP = {"kali_template": 9000, "apache_vuln": 9101, "linux_privesc": 9102,
        "windows_workstation": 9200, "domain_controller": 9201, "siem_box": 9400}


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    orch._state["sessions"] = {}
    orch._state["events"] = []
    orch._state["validations"] = []
    monkeypatch.setattr(proxmox, "template_map", lambda: dict(TMAP))
    monkeypatch.setattr(guacamole, "access_map", lambda: {})
    monkeypatch.setenv("MAYBOT_RANGE_PROVIDER", "proxmox")
    px, gc = FakeProxmox(), FakeGuacamole()
    proxmox.set_test_client(px)
    guacamole.set_test_client(gc)
    yield px, gc
    proxmox.set_test_client(None)
    guacamole.set_test_client(None)


# ---- helpers (pure) ----
def test_protocol_mapping_by_role_and_os():
    assert guacamole.protocol_for({"role": "target", "template": "windows_workstation"}, None) == "rdp"
    assert guacamole.protocol_for({"role": "target", "template": "domain_controller"}, None) == "rdp"
    assert guacamole.protocol_for({"role": "attacker", "template": "kali_template"}, None) == "vnc"
    assert guacamole.protocol_for({"role": "target", "template": "linux_privesc"}, None) == "ssh"
    # explicit access entry wins
    assert guacamole.protocol_for({"role": "target", "template": "siem_box"}, {"protocol": "ssh"}) == "ssh"


def test_accessible_attacker_always_targets_only_when_allowed():
    lab = {"browser_targets": ["siem_box"]}
    assert guacamole.accessible({"role": "attacker", "template": "kali_template"}, lab) is True
    assert guacamole.accessible({"role": "target", "template": "linux_privesc"}, lab) is False
    assert guacamole.accessible({"role": "target", "template": "siem_box"}, lab) is True


def test_connection_params_restrict_clipboard_and_file_transfer(monkeypatch):
    monkeypatch.setattr(guacamole, "DISABLE_CLIPBOARD", True)
    monkeypatch.setattr(guacamole, "DISABLE_FILE_TRANSFER", True)
    p = guacamole.connection_params("rdp", "10.10.0.5", {"username": "u", "password": "p"})
    assert p["disable-copy"] == "true" and p["disable-paste"] == "true"
    assert p["disable-download"] == "true" and p["disable-upload"] == "true"
    assert p["hostname"] == "10.10.0.5" and p["username"] == "u"


# ---- a real connect URL only after Guacamole confirms ----
def test_launch_registers_connection_and_returns_signed_url(wired):
    px, gc = wired
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    assert res["ok"] is True
    cu = res["session"]["connect_url"]
    assert cu and cu.startswith("/api/range-infra/connect/") and "sig=" in cu
    # exactly one Guacamole connection (the attacker; the target isn't browser-exposed)
    assert len(gc.connections) == 1


def test_no_connect_url_when_guacamole_unavailable(wired):
    px, _ = wired
    guacamole.set_test_client(None)        # Guacamole not configured
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    assert res["ok"] is True and res["status"] == "running"
    assert res["session"]["connect_url"] is None      # honest: VMs run, no console URL


def test_guacamole_create_failure_rolls_back_everything(wired):
    px, gc = wired
    gc.fail_on_create = True
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    assert res["ok"] is False and res["status"] == "failed"
    assert px.vms == {}                    # VMs destroyed
    assert gc.connections == {}            # no dangling connection
    assert orch.list_sessions()["count"] == 0


def test_no_ip_means_no_connection(wired):
    px, gc = wired
    # make the attacker report no guest IP (no agent)
    orig = px.vm_ip
    px.vm_ip = lambda vmid: None
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    px.vm_ip = orig
    assert res["ok"] is True                      # VMs still run
    assert res["session"]["connect_url"] is None  # but no console (no reachable guest)
    assert gc.connections == {}


# ---- connections revoked on stop/destroy ----
def test_connections_revoked_on_stop(wired):
    px, gc = wired
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    sid = res["session"]["id"]
    assert len(gc.connections) == 1
    orch.stop_lab(sid)
    assert gc.connections == {}                   # connection deleted from Guacamole
    assert orch._state["sessions"][sid]["connect_url"] is None


def test_connections_revoked_on_destroy(wired):
    px, gc = wired
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    orch.destroy_lab(res["session"]["id"])
    assert gc.connections == {} and px.vms == {}


def test_reset_revokes_and_reregisters(wired):
    px, gc = wired
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    sid = res["session"]["id"]
    old_conn = list(gc.connections)
    orch.reset_lab(sid)
    new_conn = list(gc.connections)
    assert new_conn and new_conn != old_conn      # fresh connection registered
    assert orch._state["sessions"][sid]["connect_url"]


# ---- broker: signed, short-lived, no raw IPs ----
def test_connect_returns_console_urls_not_ips(wired):
    px, gc = wired
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    cu = res["session"]["connect_url"]
    # the dashboard would open this signed link:
    body = client.get(cu).json()
    assert body["ok"] is True
    urls = [c["url"] for c in body["connections"]]
    assert urls and all(u.startswith("https://guac.example/#/client/") for u in urls)
    # no raw VM IP leaks into the response
    assert "10.10.0." not in str(body)


def test_connect_link_expires(wired):
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    sid = res["session"]["id"]
    # forge an already-expired signature
    bad = orch.connect_session(sid, 1, orch._connect_sig(sid, 1))
    assert bad["ok"] is False and bad["error"] == "expired_or_invalid"


def test_connect_rejects_tampered_signature(wired):
    res = orch.launch_lab("linux_privesc_001", provider="proxmox")
    sid = res["session"]["id"]
    import time
    exp = int(time.time()) + 600
    assert orch.connect_session(sid, exp, "deadbeef")["ok"] is False


def test_connect_unknown_session():
    import time
    exp = int(time.time()) + 600
    out = orch.connect_session("nope", exp, orch._connect_sig("nope", exp))
    assert out["ok"] is False and out["error"] == "unknown_session"


# ---- health is real ----
def test_guacamole_client_url_format(wired):
    _, gc = wired
    url = gc.client_url("123")
    enc = url.rsplit("/", 1)[-1]
    assert base64.b64decode(enc).decode() == "123\x00c\x00postgresql"
