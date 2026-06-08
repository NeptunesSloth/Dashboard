"""First-run / health guidance — a prioritized "Quick Start" checklist that
tells the operator exactly what to do next, in order, so a brand-new dashboard
gets to "working" with no docs.

Returns only booleans/counts and step metadata: no secrets. The UI composes any
install command itself (with the enroll token it already has access to).
"""
from __future__ import annotations

import os

from . import config, aggregator, authz

try:
    from maybot_agent import __version__ as LATEST_AGENT_VERSION
except Exception:  # pragma: no cover
    LATEST_AGENT_VERSION = "1.0"


def _auth_configured() -> bool:
    try:
        if authz.load_users():
            return True
    except Exception:
        pass
    return bool(os.getenv("MAYBOT_CONTROL_CENTER_TOKEN"))


def checklist(devices: list[dict] | None = None) -> dict:
    """Action-oriented onboarding steps (get hosts + bots online and updated).

    Merged into ``/api/setup`` alongside the first-run wizard flags. No secrets —
    the UI composes any install command from the enroll token it already holds.
    ``devices`` may be passed in to reuse a caller's already-loaded device list.
    """
    devices = (config.load_devices() if devices is None else devices) or []
    s = aggregator.last_summary() or {}
    online = int(s.get("online_devices", 0) or 0)
    bots = int(s.get("total_projects", 0) or 0)
    outdated = int(s.get("agents_outdated", 0) or 0)
    has_host = len(devices) > 0
    auth_ok = _auth_configured()

    steps = [
        {
            "id": "auth", "title": "Secure the dashboard", "done": auth_ok,
            "detail": ("Operator authentication is on." if auth_ok else
                       "Anyone who can reach this dashboard has full control. "
                       "Set MAYBOT_CONTROL_CENTER_TOKEN or create an operator account."),
            "action": None if auth_ok else {"kind": "settings", "label": "How"},
        },
        {
            "id": "first_host", "title": "Add your first host", "done": has_host,
            "detail": ("At least one host is enrolled." if has_host else
                       "Run one command on a machine that runs your bots — it installs the "
                       "agent and self-enrolls, then appears here."),
            "action": None if has_host else {"kind": "install", "label": "Show command"},
        },
        {
            "id": "host_online", "title": "Bring a host online",
            "done": has_host and online > 0,
            "detail": ("A host is online." if online > 0 else
                       "A host is enrolled but unreachable — check the agent is running and its "
                       "port is open to this dashboard."),
            "action": {"kind": "hosts", "label": "Open Hosts"} if has_host and online == 0 else None,
        },
        {
            "id": "bots", "title": "Add bots to a host", "done": bots > 0,
            "detail": ("Bots are being tracked." if bots > 0 else
                       "Open a host and click Manage bots → Discover to pull in what it's running."),
            "action": {"kind": "manage_bots", "label": "Manage bots"} if online > 0 and bots == 0 else None,
        },
    ]
    if outdated:
        steps.append({
            "id": "agents", "title": "Update outdated agents", "done": False,
            "detail": f"{outdated} agent(s) are behind v{LATEST_AGENT_VERSION}. "
                      "Update them in place — no SSH needed.",
            "action": {"kind": "update_agents", "label": "Update all"},
        })

    ready = auth_ok and has_host and online > 0 and bots > 0 and outdated == 0
    return {
        "ready": ready,
        "summary": {
            "hosts": len(devices), "online": online, "bots": bots,
            "agents_outdated": outdated, "latest_agent": LATEST_AGENT_VERSION,
        },
        "steps": steps,
    }
