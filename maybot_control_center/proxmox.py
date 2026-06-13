"""Proxmox VE REST API client + config for the cyber-range Proxmox provider.

A thin, mockable HTTP client over the Proxmox API (token auth). The provider
(``orchestration.ProxmoxProvider``) uses it to clone templates into per-session
VMs on an isolated VLAN, start/stop/reset/destroy them, and verify REAL VM state
via the API — it never fabricates state.

Honesty rules enforced by the caller:
- ``health`` reports ``ok`` only after a live ``/version`` reachability check.
- a session is ``running`` only when the API confirms every VM is running.
- ``connect_url`` stays ``None`` until browser access (Guacamole/noVNC) is wired —
  ``guacamole_connect_url`` returns ``None`` because that registration isn't built.

Nothing here imports ``orchestration`` (no import cycle); ``requests`` is lazy.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import yaml

# --- config (all operator-supplied via env / files) ---
LAB_BRIDGE = os.getenv("MAYBOT_PROXMOX_LAB_BRIDGE", "vmbrLAB")          # VLAN-aware, NO uplink
NIC_MODEL = os.getenv("MAYBOT_PROXMOX_NIC_MODEL", "virtio")
VLAN_MIN = int(os.getenv("MAYBOT_PROXMOX_VLAN_MIN", "100"))
VLAN_MAX = int(os.getenv("MAYBOT_PROXMOX_VLAN_MAX", "4000"))
FULL_CLONE = os.getenv("MAYBOT_PROXMOX_FULL_CLONE", "1").lower() not in ("0", "false", "no")
CLONE_TIMEOUT = int(os.getenv("MAYBOT_PROXMOX_CLONE_TIMEOUT", "600"))
START_TIMEOUT = int(os.getenv("MAYBOT_PROXMOX_START_TIMEOUT", "120"))
READY_TIMEOUT = int(os.getenv("MAYBOT_PROXMOX_READY_TIMEOUT", "300"))
TASK_POLL = float(os.getenv("MAYBOT_PROXMOX_TASK_POLL", "2"))
HTTP_TIMEOUT = int(os.getenv("MAYBOT_PROXMOX_HTTP_TIMEOUT", "30"))
TEMPLATES_FILE = Path(os.getenv("MAYBOT_PROXMOX_TEMPLATES_FILE", "proxmox_templates.yaml"))
VM_NAME_PREFIX = "maybotlab"   # used for orphan detection

# Test seam: set to a fake client to drive the provider without a real node.
_TEST_CLIENT = None


class ProxmoxError(Exception):
    pass


def set_test_client(client) -> None:
    global _TEST_CLIENT
    _TEST_CLIENT = client


class ProxmoxClient:
    """Minimal Proxmox VE API client (token auth). Returns the API ``data`` field."""

    def __init__(self, url: str, token: str, node: str, verify_tls: bool = True,
                 timeout: int = HTTP_TIMEOUT):
        base = url.rstrip("/")
        if not base.endswith("/api2/json"):
            base = base + "/api2/json"
        self.base = base
        self.token = token
        self.node = node
        self.verify = verify_tls
        self.timeout = timeout

    def _req(self, method: str, path: str, data: dict | None = None, params: dict | None = None):
        import requests  # lazy — keeps the optional dep out of import time
        r = requests.request(method, self.base + path,
                             headers={"Authorization": f"PVEAPIToken={self.token}"},
                             data=data, params=params, verify=self.verify, timeout=self.timeout)
        r.raise_for_status()
        try:
            return (r.json() or {}).get("data")
        except ValueError:
            return None

    # --- low level ---
    def get(self, path, params=None):
        return self._req("GET", path, params=params)

    def post(self, path, data=None):
        return self._req("POST", path, data=data or {})

    def delete(self, path, params=None):
        return self._req("DELETE", path, params=params)

    # --- high level ---
    def version(self) -> dict:
        return self.get("/version") or {}

    def next_id(self) -> int:
        return int(self.get("/cluster/nextid"))

    def list_vms(self) -> list[dict]:
        return self.get(f"/nodes/{self.node}/qemu") or []

    def list_templates(self) -> list[dict]:
        return [v for v in self.list_vms() if str(v.get("template")) in ("1", "True", "true")]

    def clone(self, src_vmid: int, new_vmid: int, name: str) -> str:
        return self.post(f"/nodes/{self.node}/qemu/{src_vmid}/clone",
                         {"newid": new_vmid, "name": name, "full": 1 if FULL_CLONE else 0,
                          "target": self.node})

    def set_net(self, vmid: int, net0: str):
        return self.post(f"/nodes/{self.node}/qemu/{vmid}/config", {"net0": net0})

    def start(self, vmid: int) -> str:
        return self.post(f"/nodes/{self.node}/qemu/{vmid}/status/start")

    def stop(self, vmid: int) -> str:
        return self.post(f"/nodes/{self.node}/qemu/{vmid}/status/stop")

    def destroy(self, vmid: int) -> str:
        return self.delete(f"/nodes/{self.node}/qemu/{vmid}", params={"purge": 1, "destroy-unreferenced-disks": 1})

    def vm_status(self, vmid: int) -> str:
        return (self.get(f"/nodes/{self.node}/qemu/{vmid}/status/current") or {}).get("status", "unknown")

    def task_status(self, upid: str) -> dict:
        return self.get(f"/nodes/{self.node}/tasks/{upid}/status") or {}

    def wait_task(self, upid: str, timeout: int) -> bool:
        if not upid:
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.task_status(upid)
            if st.get("status") == "stopped":
                ex = st.get("exitstatus")
                if ex not in (None, "OK"):
                    raise ProxmoxError(f"task {upid} failed: {ex}")
                return True
            time.sleep(TASK_POLL)
        raise ProxmoxError(f"task {upid} timed out after {timeout}s")

    def wait_running(self, vmid: int, timeout: int) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.vm_status(vmid) == "running":
                return True
            time.sleep(TASK_POLL)
        raise ProxmoxError(f"vm {vmid} did not reach 'running' within {timeout}s")


def from_env() -> ProxmoxClient | None:
    url = os.getenv("MAYBOT_PROXMOX_URL", "").strip()
    token = os.getenv("MAYBOT_PROXMOX_TOKEN", "").strip()
    node = os.getenv("MAYBOT_PROXMOX_NODE", "").strip()
    if not (url and token and node):
        return None
    verify = os.getenv("MAYBOT_PROXMOX_VERIFY_TLS", "1").lower() not in ("0", "false", "no")
    return ProxmoxClient(url, token, node, verify_tls=verify)


def client() -> ProxmoxClient | None:
    """The active client — a test client if injected, else one from env config."""
    return _TEST_CLIENT if _TEST_CLIENT is not None else from_env()


def template_map() -> dict[str, int]:
    """Logical template name (from lab_catalog.yaml) -> Proxmox source VMID."""
    if not TEMPLATES_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(TEMPLATES_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    for k, v in (data.get("templates") or {}).items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def net_config(vlan: int) -> str:
    """Per-session isolated NIC: lab bridge + unique VLAN tag + firewall on."""
    return f"{NIC_MODEL},bridge={LAB_BRIDGE},tag={vlan},firewall=1"


def vm_name(session_id: str, role: str, vmid: int) -> str:
    return f"{VM_NAME_PREFIX}-{session_id}-{role}-{vmid}"


def session_of(vm_name_str: str) -> str | None:
    """Recover the session id from a lab VM name (for orphan detection)."""
    if not str(vm_name_str).startswith(VM_NAME_PREFIX + "-"):
        return None
    parts = str(vm_name_str).split("-")
    # maybotlab - sess - <ts> - role - vmid  => session id is "sess-<ts>"
    return f"{parts[1]}-{parts[2]}" if len(parts) >= 5 else None


def guacamole_connect_url(session_id: str, vms: list[dict]) -> str | None:
    """Browser access requires a Guacamole/noVNC connection registration, which is
    NOT implemented in this build. Returns ``None`` so we never hand out a fake
    console link — a running VM is reachable only once this is wired."""
    return None
