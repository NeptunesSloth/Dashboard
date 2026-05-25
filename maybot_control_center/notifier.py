from __future__ import annotations

import logging
import os
import threading

import requests

_log = logging.getLogger("maybot_control_center.notifier")

DISCORD_WEBHOOK = os.getenv("MAYBOT_DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK = os.getenv("MAYBOT_SLACK_WEBHOOK_URL", "")
ALERT_STATES = {
    s.strip().lower()
    for s in os.getenv("MAYBOT_ALERT_STATES", "error").split(",")
    if s.strip()
}

_prev: dict[str, str] = {}


def _post(url: str, payload: dict) -> None:
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as exc:
        _log.warning("webhook delivery failed: %s", exc)


def _fire(project_name: str, device: str, prev: str, curr: str, status: str) -> None:
    discord_msg = (
        f"🚨 **{project_name}** on `{device}` — health `{prev}` → `{curr}` (status: {status})"
    )
    slack_msg = (
        f"🚨 *{project_name}* on `{device}` — health `{prev}` → `{curr}` (status: {status})"
    )
    _log.warning("alert fired: %s", discord_msg)
    if DISCORD_WEBHOOK:
        threading.Thread(target=_post, args=(DISCORD_WEBHOOK, {"content": discord_msg}), daemon=True).start()
    if SLACK_WEBHOOK:
        threading.Thread(target=_post, args=(SLACK_WEBHOOK, {"text": slack_msg}), daemon=True).start()


def check_and_notify(projects: list[dict]) -> None:
    for p in projects:
        key = f"{p.get('device', '?')}:{p.get('name', '?')}"
        curr = p.get("health", "unknown")
        prev = _prev.get(key)
        _prev[key] = curr
        if prev is None or prev == curr:
            continue
        if curr.lower() in ALERT_STATES:
            _fire(
                project_name=p.get("name", "?"),
                device=p.get("device", "?"),
                prev=prev,
                curr=curr,
                status=p.get("status", "unknown"),
            )
