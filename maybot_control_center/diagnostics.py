"""Setup & diagnostics — what's configured, and is the fleet reachable.

Powers the Ops tab: a config checklist (auth, persistence, autopilot, webhooks,
integrations) and a live per-agent connectivity probe (online, latency, auth).
"""
from __future__ import annotations

import os
import time

from .config import load_devices, all_devices, CONTROL_CENTER_TOKEN


def config_checks() -> dict:
    from . import authz, autopilot, status_page, github_repo, talismans, meridians, maintenance, sectmemory
    def _envset(*keys):
        return any(os.getenv(k, "").strip() for k in keys)
    return {
        "auth_configured": bool(authz.load_users()) or bool(CONTROL_CENTER_TOKEN),
        "persistence_db": bool(os.getenv("MAYBOT_DB", "").strip()),
        "autopilot": bool(autopilot.ENABLED),
        "real_prs": os.getenv("MAYBOT_PR_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"},
        "public_status": status_page.enabled(),
        "github_repos": github_repo.enabled(),
        "synthetic_probes": bool(talismans.load_talismans()),
        "meridians": bool(meridians.load_map()),
        "maintenance_calendar": bool(maintenance.load_windows()),
        "sect_memory": bool(sectmemory.ENABLED),
        "webhooks": {
            "discord": _envset("MAYBOT_DISCORD_WEBHOOK_URL"),
            "slack": _envset("MAYBOT_SLACK_WEBHOOK_URL"),
            "generic": _envset("MAYBOT_ALERT_WEBHOOK_URL"),
        },
    }


def agent_health() -> list[dict]:
    from . import agent_client
    rows = []
    for d in all_devices():
        t0 = time.time()
        ping = agent_client.call_agent(d, "/api/ping")
        latency = round((time.time() - t0) * 1000)
        version = None
        if ping.get("online"):
            dev = agent_client.call_agent(d, "/api/device")
            version = (dev.get("data") or {}).get("version")
        rows.append({
            "name": d.get("name", "?"), "url": d.get("url", ""),
            "online": bool(ping.get("online")), "auth_error": bool(ping.get("auth_error")),
            "latency_ms": latency, "status_code": ping.get("status_code"),
            "error": ping.get("error"), "version": version,
            "timeout": d.get("timeout"),
        })
    return rows


def snapshot() -> dict:
    return {"config": config_checks(), "agents": agent_health(), "now": int(time.time() * 1000)}
