"""Pluggable outbound notification channels with a no-op fallback.

Posts alerts to whichever channels are configured by environment variables —
Slack (``MAYBOT_SLACK_WEBHOOK``), Discord (``MAYBOT_DISCORD_WEBHOOK``), and a
generic JSON webhook (``MAYBOT_WEBHOOK_URL``). Every send is recorded to an
in-memory ring buffer regardless of whether any channel is configured, so the
dashboard can surface a recent-events log even in a fully offline demo.

Delivery uses ``requests`` when available, else the stdlib ``urllib``; every
network call is wrapped so nothing thrown here escapes. Identical (title, body)
notifications sent within a short window are de-duplicated.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

# Ring buffer of recent events (newest last), capped.
_RING_CAP = 100
_DEDUPE_WINDOW = 60.0  # seconds — suppress identical (title, body) repeats

_lock = threading.Lock()
_events: list[dict] = []
_last_seen: dict[tuple[str, str], float] = {}  # (title, body) -> last send ts


def _slack_url() -> str:
    return os.getenv("MAYBOT_SLACK_WEBHOOK", "").strip()


def _discord_url() -> str:
    return os.getenv("MAYBOT_DISCORD_WEBHOOK", "").strip()


def _webhook_url() -> str:
    return os.getenv("MAYBOT_WEBHOOK_URL", "").strip()


def channels() -> list[str]:
    """Which channels are currently configured (by env)."""
    out: list[str] = []
    if _slack_url():
        out.append("slack")
    if _discord_url():
        out.append("discord")
    if _webhook_url():
        out.append("webhook")
    return out


def _post(url: str, payload: dict) -> bool:
    """POST JSON to ``url``. Returns True on apparent success; never raises."""
    body = json.dumps(payload).encode("utf-8")
    try:
        try:
            import requests  # optional dependency
        except Exception:
            requests = None  # type: ignore

        if requests is not None:
            resp = requests.post(url, json=payload, timeout=5)
            return bool(getattr(resp, "ok", True))

        # Stdlib fallback — no requests installed.
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 (trusted webhook URLs)
            return 200 <= getattr(r, "status", 200) < 300
    except Exception:
        return False


def _deliver(title: str, body: str, level: str, kind: str) -> list[str]:
    """Fan the message out to every configured channel; return those delivered."""
    text = f"{title}\n{body}".strip() if body else title
    delivered: list[str] = []

    slack = _slack_url()
    if slack and _post(slack, {"text": text}):
        delivered.append("slack")

    discord = _discord_url()
    if discord and _post(discord, {"content": text}):
        delivered.append("discord")

    webhook = _webhook_url()
    if webhook and _post(webhook, {"title": title, "body": body, "level": level, "kind": kind}):
        delivered.append("webhook")

    return delivered


def send(title: str, body: str = "", level: str = "info", kind: str = "alert") -> dict:
    """Send a notification to all configured channels and record it.

    De-duplicates identical ``(title, body)`` pairs sent within ~60s. The event
    is always recorded to the in-memory ring, even when no channel is configured
    or every delivery fails.

    Returns ``{"delivered": [channels], "recorded": True}``.
    """
    now = time.time()
    key = (title, body)

    with _lock:
        last = _last_seen.get(key)
        duplicate = last is not None and (now - last) < _DEDUPE_WINDOW
        _last_seen[key] = now

    if duplicate:
        # Suppress: don't re-deliver and don't re-record the noisy repeat.
        return {"delivered": [], "recorded": False}

    delivered = _deliver(title, body, level, kind)

    event = {
        "ts": now,
        "title": title,
        "body": body,
        "level": level,
        "kind": kind,
        "delivered": delivered,
    }
    with _lock:
        _events.append(event)
        if len(_events) > _RING_CAP:
            del _events[:-_RING_CAP]

    return {"delivered": delivered, "recorded": True}


def recent(limit: int = 30) -> list[dict]:
    """Return the most recent events (newest last), at most ``limit``."""
    with _lock:
        return [dict(e) for e in _events[-max(0, limit):]]


def clear() -> None:
    """Reset the in-memory state (useful for tests)."""
    with _lock:
        _events.clear()
        _last_seen.clear()
