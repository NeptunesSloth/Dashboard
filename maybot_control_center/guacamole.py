"""Apache Guacamole REST API client + browser-access helpers for the cyber range.

When a Proxmox lab session reaches ``running``, the provider registers per-session
Guacamole CONNECTIONS (one per browser-accessible VM) and the dashboard hands out
a short-lived signed URL to open them. We never fabricate a console link: a URL is
produced only after Guacamole CONFIRMS the connection exists, and connections are
deleted when the session stops/destroys.

Mockable via ``set_test_client`` so the integration is unit-tested without a live
Guacamole server. ``requests`` is lazy; this module does not import
``orchestration`` (no import cycle).
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import yaml

VERIFY_TLS = os.getenv("MAYBOT_GUACAMOLE_VERIFY_TLS", "1").lower() not in ("0", "false", "no")
HTTP_TIMEOUT = int(os.getenv("MAYBOT_GUACAMOLE_TIMEOUT", "30"))
# Restrict clipboard + file transfer by default (security).
DISABLE_CLIPBOARD = os.getenv("MAYBOT_GUAC_DISABLE_CLIPBOARD", "1").lower() not in ("0", "false", "no")
DISABLE_FILE_TRANSFER = os.getenv("MAYBOT_GUAC_DISABLE_FILE_TRANSFER", "1").lower() not in ("0", "false", "no")
ATTACKER_PROTOCOL = os.getenv("MAYBOT_GUAC_ATTACKER_PROTOCOL", "vnc").strip().lower()
ACCESS_FILE = Path(os.getenv("MAYBOT_GUAC_ACCESS_FILE",
                             os.getenv("MAYBOT_PROXMOX_TEMPLATES_FILE", "proxmox_templates.yaml")))

_DEFAULT_PORTS = {"ssh": 22, "rdp": 3389, "vnc": 5900}

# Test seam — set to a fake client to drive the integration without a live server.
_TEST_CLIENT = None


class GuacamoleError(Exception):
    pass


def set_test_client(client) -> None:
    global _TEST_CLIENT
    _TEST_CLIENT = client


class GuacamoleClient:
    """Minimal Guacamole REST client (token auth → per-call ``?token=``)."""

    def __init__(self, base: str, user: str, password: str, datasource: str | None = None,
                 verify_tls: bool = VERIFY_TLS, timeout: int = HTTP_TIMEOUT):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self._datasource = datasource
        self.verify = verify_tls
        self.timeout = timeout
        self._token = None

    @property
    def datasource(self) -> str:
        return self._datasource or os.getenv("MAYBOT_GUACAMOLE_DATASOURCE", "postgresql")

    def _post(self, path, **kw):
        import requests
        return requests.post(self.base + path, verify=self.verify, timeout=self.timeout, **kw)

    def token(self) -> str:
        r = self._post("/api/tokens", data={"username": self.user, "password": self.password})
        r.raise_for_status()
        d = r.json()
        self._token = d["authToken"]
        self._datasource = d.get("dataSource", self._datasource)
        return self._token

    def _t(self) -> str:
        return self._token or self.token()

    def health(self) -> bool:
        self.token()        # an auth round-trip = real reachability
        return True

    def create_connection(self, name: str, protocol: str, params: dict) -> str:
        import requests
        body = {"name": name, "protocol": protocol, "parentIdentifier": "ROOT",
                "parameters": {k: str(v) for k, v in params.items()}, "attributes": {}}
        r = requests.post(f"{self.base}/api/session/data/{self.datasource}/connections",
                          params={"token": self._t()}, json=body, verify=self.verify, timeout=self.timeout)
        r.raise_for_status()
        return str((r.json() or {}).get("identifier"))

    def delete_connection(self, conn_id: str) -> None:
        import requests
        r = requests.delete(f"{self.base}/api/session/data/{self.datasource}/connections/{conn_id}",
                            params={"token": self._t()}, verify=self.verify, timeout=self.timeout)
        r.raise_for_status()

    def list_connections(self) -> dict:
        import requests
        r = requests.get(f"{self.base}/api/session/data/{self.datasource}/connections",
                         params={"token": self._t()}, verify=self.verify, timeout=self.timeout)
        r.raise_for_status()
        return r.json() or {}

    def client_url(self, conn_id: str) -> str:
        # Guacamole client identifier = base64("<id>\0c\0<dataSource>")
        raw = f"{conn_id}\x00c\x00{self.datasource}".encode()
        return f"{self.base}/#/client/{base64.b64encode(raw).decode()}"


def from_env() -> GuacamoleClient | None:
    url = os.getenv("MAYBOT_GUACAMOLE_URL", "").strip()
    user = os.getenv("MAYBOT_GUACAMOLE_USER", "").strip()
    pw = os.getenv("MAYBOT_GUACAMOLE_PASSWORD", "").strip()
    if not (url and user and pw):
        return None
    return GuacamoleClient(url, user, pw, datasource=os.getenv("MAYBOT_GUACAMOLE_DATASOURCE", "").strip() or None)


def client() -> GuacamoleClient | None:
    return _TEST_CLIENT if _TEST_CLIENT is not None else from_env()


def access_map() -> dict:
    """Optional per-template access config: {template: {protocol, port, username,
    password}}. Lets the operator define how to reach each guest; absent entries
    fall back to protocol-by-role and Guacamole prompts for any missing creds."""
    if not ACCESS_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(ACCESS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return {str(k): v for k, v in (data.get("access") or {}).items() if isinstance(v, dict)}


def accessible(vm: dict, lab: dict) -> bool:
    """Which VMs get a browser console: the attacker always; targets ONLY when the
    lab opts them in via ``browser_targets`` (SSH/RDP only when the lab allows)."""
    if vm.get("role") == "attacker":
        return True
    allow = {str(x) for x in (lab.get("browser_targets") or [])}
    return vm.get("template") in allow or vm.get("role") in allow


def protocol_for(vm: dict, access_entry: dict | None) -> str:
    if access_entry and access_entry.get("protocol"):
        return str(access_entry["protocol"]).lower()
    t = str(vm.get("template", "")).lower()
    if "windows" in t or "domain_controller" in t:
        return "rdp"
    if vm.get("role") == "attacker":
        return ATTACKER_PROTOCOL
    return "ssh"


def connection_params(protocol: str, ip: str, access_entry: dict | None) -> dict:
    a = access_entry or {}
    params = {"hostname": ip, "port": a.get("port", _DEFAULT_PORTS.get(protocol, 22))}
    if a.get("username"):
        params["username"] = a["username"]
    if a.get("password"):
        params["password"] = a["password"]
    if protocol == "rdp":
        params.update({"security": "any", "ignore-cert": "true"})
        if DISABLE_CLIPBOARD:
            params.update({"disable-copy": "true", "disable-paste": "true"})
        if DISABLE_FILE_TRANSFER:
            params.update({"disable-download": "true", "disable-upload": "true"})
    elif protocol == "vnc":
        if DISABLE_CLIPBOARD:
            params["disable-copy"] = "true"
    return params


def connection_for(vm: dict, ip: str, access: dict) -> tuple[str, dict]:
    entry = access.get(str(vm.get("template", "")))
    proto = protocol_for(vm, entry)
    return proto, connection_params(proto, ip, entry)
