"""Self-registration: the agent announces itself to the control center on startup
so a new host just *appears* on the dashboard — no 'Add host' click, no editing
devices.yaml.

Enabled when ``MAYBOT_CONTROL_CENTER_URL`` is set. The agent POSTs its name, its
reachable URL, and its api_token to ``{control}/api/agents/register`` (authorized
by ``MAYBOT_REGISTER_TOKEN``), then re-announces periodically so it survives a
control-center restart.

Env:
  MAYBOT_CONTROL_CENTER_URL  the dashboard, e.g. http://10.0.0.5:8200   (required)
  MAYBOT_REGISTER_TOKEN      shared enrolment secret (matches the dashboard)
  MAYBOT_AGENT_NAME          label for this host (default: the hostname)
  MAYBOT_AGENT_URL           this agent's reachable URL (default: http://<lan-ip>:PORT)
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request

from .config import API_TOKEN, PORT

CONTROL_URL = os.getenv("MAYBOT_CONTROL_CENTER_URL", "").rstrip("/")
REGISTER_TOKEN = os.getenv("MAYBOT_REGISTER_TOKEN", "")
RE_ANNOUNCE_SECONDS = float(os.getenv("MAYBOT_REGISTER_INTERVAL", "300"))


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))           # no packet sent; just picks the egress iface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def _agent_url() -> str:
    return os.getenv("MAYBOT_AGENT_URL", "").rstrip("/") or f"http://{_lan_ip()}:{PORT}"


def _agent_name() -> str:
    return os.getenv("MAYBOT_AGENT_NAME", "") or socket.gethostname() or "agent"


def _announce_once() -> bool:
    import json
    body = json.dumps({"name": _agent_name(), "url": _agent_url(), "api_token": API_TOKEN}).encode()
    req = urllib.request.Request(f"{CONTROL_URL}/api/agents/register", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "x-register-token": REGISTER_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:   # noqa: S310 (operator-supplied URL)
            return 200 <= r.status < 300
    except Exception:
        return False


def _loop() -> None:
    while True:
        _announce_once()
        time.sleep(max(30.0, RE_ANNOUNCE_SECONDS))


def start() -> None:
    """Begin announcing this agent (no-op unless MAYBOT_CONTROL_CENTER_URL is set)."""
    if not CONTROL_URL:
        return
    threading.Thread(target=_loop, daemon=True).start()
