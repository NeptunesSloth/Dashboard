"""Pluggable outbound notification channels with a no-op fallback.

Posts alerts to whichever channels are configured by environment variables —
Slack (``MAYBOT_SLACK_WEBHOOK``), Discord (``MAYBOT_DISCORD_WEBHOOK``), a generic
JSON webhook (``MAYBOT_WEBHOOK_URL``), email over SMTP, and Telegram. Every send
is recorded to an in-memory ring buffer regardless of whether any channel is
configured, so the dashboard can surface a recent-events log even in a fully
offline demo.

Email (all required to enable): ``MAYBOT_SMTP_HOST``, ``MAYBOT_SMTP_FROM``,
``MAYBOT_SMTP_TO`` (comma-separated). Optional: ``MAYBOT_SMTP_PORT`` (587),
``MAYBOT_SMTP_USER`` / ``MAYBOT_SMTP_PASSWORD``, ``MAYBOT_SMTP_TLS`` (STARTTLS,
default on), ``MAYBOT_SMTP_SSL`` (implicit TLS, default off).

Telegram (both required): ``MAYBOT_TELEGRAM_TOKEN`` + ``MAYBOT_TELEGRAM_CHAT_ID``.

PagerDuty (Events API v2): ``MAYBOT_PAGERDUTY_ROUTING_KEY`` — triggers an event
with severity mapped from the alert level. Opsgenie: ``MAYBOT_OPSGENIE_API_KEY``
(+ optional ``MAYBOT_OPSGENIE_REGION`` = ``eu``|``us``, default ``us``) — creates
an alert with priority mapped from the level.

Delivery uses ``requests`` when available, else the stdlib ``urllib``; every
network call is wrapped so nothing thrown here escapes. Identical (title, body)
notifications sent within a short window are de-duplicated.
"""
from __future__ import annotations

import json
import os
import smtplib
import threading
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage

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


def _smtp_recipients() -> list[str]:
    return [a.strip() for a in os.getenv("MAYBOT_SMTP_TO", "").split(",") if a.strip()]


def _email_configured() -> bool:
    return bool(os.getenv("MAYBOT_SMTP_HOST", "").strip()
                and os.getenv("MAYBOT_SMTP_FROM", "").strip()
                and _smtp_recipients())


def _telegram_cfg() -> tuple[str, str]:
    return (os.getenv("MAYBOT_TELEGRAM_TOKEN", "").strip(),
            os.getenv("MAYBOT_TELEGRAM_CHAT_ID", "").strip())


def _pagerduty_key() -> str:
    return os.getenv("MAYBOT_PAGERDUTY_ROUTING_KEY", "").strip()


def _opsgenie_key() -> str:
    return os.getenv("MAYBOT_OPSGENIE_API_KEY", "").strip()


def _opsgenie_region() -> str:
    region = os.getenv("MAYBOT_OPSGENIE_REGION", "us").strip().lower()
    return "eu" if region == "eu" else "us"


def channels() -> list[str]:
    """Which channels are currently configured (by env)."""
    out: list[str] = []
    if _slack_url():
        out.append("slack")
    if _discord_url():
        out.append("discord")
    if _webhook_url():
        out.append("webhook")
    if _email_configured():
        out.append("email")
    tok, chat = _telegram_cfg()
    if tok and chat:
        out.append("telegram")
    if _pagerduty_key():
        out.append("pagerduty")
    if _opsgenie_key():
        out.append("opsgenie")
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


def _send_email(title: str, body: str) -> bool:
    """Send one alert email over SMTP. Returns True on apparent success."""
    host = os.getenv("MAYBOT_SMTP_HOST", "").strip()
    sender = os.getenv("MAYBOT_SMTP_FROM", "").strip()
    recipients = _smtp_recipients()
    if not (host and sender and recipients):
        return False
    try:
        port = int(os.getenv("MAYBOT_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    use_ssl = os.getenv("MAYBOT_SMTP_SSL", "").strip().lower() in {"1", "true", "yes"}
    use_tls = os.getenv("MAYBOT_SMTP_TLS", "1").strip().lower() not in {"0", "false", "no", ""}
    user = os.getenv("MAYBOT_SMTP_USER", "").strip()
    password = os.getenv("MAYBOT_SMTP_PASSWORD", "")

    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body or title)
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            smtp = smtplib.SMTP(host, port, timeout=10)
        with smtp:
            if use_tls and not use_ssl:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        return False


def _send_telegram(text: str) -> bool:
    """Send one Telegram message via the Bot API. Returns True on success."""
    token, chat_id = _telegram_cfg()
    if not (token and chat_id):
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _post(url, {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})


def _post_headers(url: str, payload: dict, headers: dict) -> bool:
    """POST JSON to ``url`` with extra ``headers``. Like ``_post`` but lets a
    channel attach auth headers (e.g. Opsgenie's ``Authorization: GenieKey``).
    Returns True on apparent success; never raises."""
    body = json.dumps(payload).encode("utf-8")
    base = {"Content-Type": "application/json"}
    base.update(headers)
    try:
        try:
            import requests  # optional dependency
        except Exception:
            requests = None  # type: ignore

        if requests is not None:
            resp = requests.post(url, json=payload, headers=base, timeout=5)
            return bool(getattr(resp, "ok", True))

        req = urllib.request.Request(url, data=body, headers=base, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 (trusted alerting URLs)
            return 200 <= getattr(r, "status", 200) < 300
    except Exception:
        return False


# PagerDuty Events API v2 severity is one of critical/error/warning/info.
_PAGERDUTY_SEVERITY = {"error": "error", "critical": "critical", "warning": "warning", "info": "info"}
# Opsgenie alert priority is P1 (highest) .. P5 (lowest).
_OPSGENIE_PRIORITY = {"error": "P1", "critical": "P1", "warning": "P3", "info": "P5"}


def _send_pagerduty(title: str, body: str, level: str) -> bool:
    """Trigger a PagerDuty Events API v2 event. Returns True on success."""
    key = _pagerduty_key()
    if not key:
        return False
    summary = f"{title}\n{body}".strip() if body else title
    severity = _PAGERDUTY_SEVERITY.get((level or "info").strip().lower(), "info")
    payload = {
        "routing_key": key,
        "event_action": "trigger",
        "payload": {
            "summary": summary[:1024],
            "severity": severity,
            "source": "maybot",
        },
    }
    return _post("https://events.pagerduty.com/v2/enqueue", payload)


def _send_opsgenie(title: str, body: str, level: str) -> bool:
    """Create an Opsgenie alert. Returns True on success."""
    key = _opsgenie_key()
    if not key:
        return False
    host = "api.opsgenie.com" if _opsgenie_region() == "us" else "api.eu.opsgenie.com"
    url = f"https://{host}/v2/alerts"
    priority = _OPSGENIE_PRIORITY.get((level or "info").strip().lower(), "P5")
    payload = {"message": title, "description": body, "priority": priority}
    return _post_headers(url, payload, {"Authorization": f"GenieKey {key}"})


# Per-channel severity routing: a channel only receives events at or above its
# configured minimum level. MAYBOT_NOTIFY_MIN_LEVEL sets a global floor;
# MAYBOT_NOTIFY_MIN_LEVEL_<CHANNEL> (e.g. _PAGERDUTY=error) overrides per channel.
_LEVEL_RANK = {"info": 0, "warn": 1, "warning": 1, "error": 2, "critical": 3}


def _routed(channel: str, level: str) -> bool:
    raw = (os.getenv(f"MAYBOT_NOTIFY_MIN_LEVEL_{channel.upper()}", "")
           or os.getenv("MAYBOT_NOTIFY_MIN_LEVEL", "")).strip().lower()
    floor = _LEVEL_RANK.get(raw, 0)
    return _LEVEL_RANK.get((level or "info").strip().lower(), 0) >= floor


def _deliver(title: str, body: str, level: str, kind: str) -> list[str]:
    """Fan the message out to every configured channel; return those delivered."""
    text = f"{title}\n{body}".strip() if body else title
    delivered: list[str] = []

    slack = _slack_url()
    if slack and _routed("slack", level) and _post(slack, {"text": text}):
        delivered.append("slack")

    discord = _discord_url()
    if discord and _routed("discord", level) and _post(discord, {"content": text}):
        delivered.append("discord")

    webhook = _webhook_url()
    if webhook and _routed("webhook", level) and _post(webhook, {"title": title, "body": body, "level": level, "kind": kind}):
        delivered.append("webhook")

    if _email_configured() and _routed("email", level) and _send_email(title, body):
        delivered.append("email")

    tok, chat = _telegram_cfg()
    if tok and chat and _routed("telegram", level) and _send_telegram(text):
        delivered.append("telegram")

    if _pagerduty_key() and _routed("pagerduty", level) and _send_pagerduty(title, body, level):
        delivered.append("pagerduty")

    if _opsgenie_key() and _routed("opsgenie", level) and _send_opsgenie(title, body, level):
        delivered.append("opsgenie")

    return delivered


# Operator snooze: mute delivery for a while (events are still recorded to the
# ring so nothing is lost — they just don't page anyone).
_snooze_until = 0.0


def snooze(minutes: float) -> dict:
    global _snooze_until
    minutes = max(0.0, min(float(minutes or 0), 60 * 24 * 7))  # cap at a week
    with _lock:
        _snooze_until = time.time() + minutes * 60
    return snooze_status()


def unsnooze() -> dict:
    global _snooze_until
    with _lock:
        _snooze_until = 0.0
    return snooze_status()


def snoozed() -> bool:
    with _lock:
        return time.time() < _snooze_until


def snooze_status() -> dict:
    with _lock:
        remaining = max(0.0, _snooze_until - time.time())
    return {"snoozed": remaining > 0, "remaining_s": int(remaining)}


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

    delivered = [] if snoozed() else _deliver(title, body, level, kind)

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
