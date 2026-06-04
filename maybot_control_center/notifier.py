from __future__ import annotations

import logging
import os
import threading
import time

import requests

_log = logging.getLogger("maybot_control_center.notifier")

DISCORD_WEBHOOK = os.getenv("MAYBOT_DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK = os.getenv("MAYBOT_SLACK_WEBHOOK_URL", "")
GENERIC_WEBHOOK = os.getenv("MAYBOT_ALERT_WEBHOOK_URL", "")  # generic JSON {event,title,message}
ALERT_STATES = {
    s.strip().lower()
    for s in os.getenv("MAYBOT_ALERT_STATES", "error").split(",")
    if s.strip()
}
# Which non-health events route to the webhooks (incidents, tribulations, agent failures).
ALERT_EVENTS = {
    s.strip().lower()
    for s in os.getenv("MAYBOT_ALERT_EVENTS", "incident,tribulation,budget,escalation,autopilot,inbound").split(",")
    if s.strip()
}

# ---- noise control --------------------------------------------------------
# Don't re-page for the same project+state within the cooldown.
COOLDOWN_SECONDS = float(os.getenv("MAYBOT_ALERT_COOLDOWN_SECONDS", "300"))
# A project that changes health FLAP_THRESHOLD+ times within FLAP_WINDOW is
# "flapping": page once, then stay quiet until it settles.
FLAP_WINDOW_SECONDS = float(os.getenv("MAYBOT_ALERT_FLAP_WINDOW_SECONDS", "600"))
FLAP_THRESHOLD = int(os.getenv("MAYBOT_ALERT_FLAP_THRESHOLD", "5"))
# Send a follow-up when a project that alerted returns to ok.
SEND_RECOVERY = os.getenv("MAYBOT_ALERT_RECOVERY", "1").strip().lower() not in {"0", "false", "no", ""}
# Extra delivery attempts on webhook failure (0 = single attempt, no retry).
WEBHOOK_RETRIES = max(0, int(os.getenv("MAYBOT_WEBHOOK_RETRIES", "2")))

_lock = threading.Lock()
_prev: dict[str, str] = {}
_transitions: dict[str, list[float]] = {}   # recent transition timestamps (flap detection)
_flapping: dict[str, bool] = {}
_in_alert: dict[str, bool] = {}             # currently in an un-recovered alert state
_last_alert: dict[str, tuple[str, float]] = {}  # key -> (state, ts) for cooldown dedup


def _now() -> float:
    return time.time()


def notify_event(event: str, title: str, message: str) -> None:
    """Route a noteworthy event to the configured webhooks (if subscribed)."""
    if event.lower() not in ALERT_EVENTS:
        return
    text = f"🔔 {title} — {message}"
    _log.warning("alert(%s): %s", event, text)
    _broadcast(text, text, {"event": event, "title": title, "message": message})


def _broadcast(discord_text: str, slack_text: str, generic: dict) -> None:
    if DISCORD_WEBHOOK:
        threading.Thread(target=_post, args=(DISCORD_WEBHOOK, {"content": discord_text}), daemon=True).start()
    if SLACK_WEBHOOK:
        threading.Thread(target=_post, args=(SLACK_WEBHOOK, {"text": slack_text}), daemon=True).start()
    if GENERIC_WEBHOOK:
        threading.Thread(target=_post, args=(GENERIC_WEBHOOK, generic), daemon=True).start()


def _post(url: str, payload: dict) -> None:
    for attempt in range(WEBHOOK_RETRIES + 1):
        try:
            requests.post(url, json=payload, timeout=5)
            return
        except Exception as exc:
            if attempt >= WEBHOOK_RETRIES:
                _log.warning("webhook delivery failed after %d attempts: %s", attempt + 1, exc)
                return
            time.sleep(min(2.0 ** attempt, 8.0))  # 1s, 2s, 4s, 8s …


def _fire(project_name: str, device: str, prev: str, curr: str, status: str) -> None:
    discord_msg = f"🚨 **{project_name}** on `{device}` — health `{prev}` → `{curr}` (status: {status})"
    slack_msg = f"🚨 *{project_name}* on `{device}` — health `{prev}` → `{curr}` (status: {status})"
    _log.warning("alert fired: %s", discord_msg)
    _broadcast(discord_msg, slack_msg,
               {"event": "health", "title": f"{project_name} {curr}",
                "message": f"{project_name} on {device}: {prev} -> {curr} (status {status})"})


def _fire_recovery(project_name: str, device: str) -> None:
    msg = f"✅ **{project_name}** on `{device}` recovered (health `ok`)"
    _log.warning("recovery: %s", msg)
    _broadcast(msg, msg.replace("**", "*"),
               {"event": "recovery", "title": f"{project_name} recovered",
                "message": f"{project_name} on {device} returned to ok"})


def _fire_flap(project_name: str, device: str, n: int) -> None:
    msg = f"🌊 **{project_name}** on `{device}` is flapping ({n} changes) — further alerts suppressed until it settles"
    _log.warning("flap: %s", msg)
    _broadcast(msg, msg.replace("**", "*"),
               {"event": "flap", "title": f"{project_name} flapping",
                "message": f"{project_name} on {device}: {n} health changes in {int(FLAP_WINDOW_SECONDS)}s"})


def _recent_transitions(key: str, now: float) -> int:
    buf = _transitions.setdefault(key, [])
    buf.append(now)
    cutoff = now - FLAP_WINDOW_SECONDS
    while buf and buf[0] < cutoff:
        buf.pop(0)
    return len(buf)


def check_and_notify(projects: list[dict]) -> None:
    from . import maintenance, meridians, oaths, escalation
    now = _now()
    health_by_key = {f"{p.get('device', '?')}:{p.get('name', '?')}": str(p.get("health", "unknown"))
                     for p in projects}
    for p in projects:
        name = p.get("name", "?")
        device = p.get("device", "?")
        key = f"{device}:{name}"
        curr = str(p.get("health", "unknown"))
        with _lock:
            prev = _prev.get(key)
            _prev[key] = curr
            if prev is None or prev == curr:
                continue
            # A genuine transition.
            n_changes = _recent_transitions(key, now)
            silenced = maintenance.is_silenced(device, name)
            recovered = curr.lower() == "ok"

            # Track alert/recovery bookkeeping regardless of whether we page.
            was_alerting = _in_alert.get(key, False)
            if recovered:
                _in_alert[key] = False
                maintenance.note_recovery(device, name)
                oaths.note_recovery(device, name)        # claimed incident resolved
                escalation.disarm(device, name)
            elif curr.lower() in ALERT_STATES:
                _in_alert[key] = True

            if n_changes >= FLAP_THRESHOLD:
                # Flapping: announce once, then suppress every alert/recovery until it settles.
                if silenced or _flapping.get(key):
                    continue
                _flapping[key] = True
                fire = ("flap", n_changes)
            else:
                _flapping[key] = False  # settled (transitions aged out of the window)
                if silenced:
                    continue
                if recovered:
                    if not was_alerting or not SEND_RECOVERY:
                        continue
                    fire = ("recovery",)
                elif curr.lower() in ALERT_STATES:
                    # Dependency-aware: an unhealthy upstream means this is likely a
                    # downstream symptom — let the root cause page, suppress this one.
                    if meridians.SUPPRESS and meridians.blocked_upstreams(key, health_by_key):
                        escalation.arm(device, name, now)
                        continue
                    # Ownership: if a disciple has sworn an oath to this incident, the
                    # owner is on it — suppress repeat pages (escalation stays disarmed).
                    if oaths.is_claimed(device, name):
                        continue
                    last = _last_alert.get(key)
                    if last and last[0] == curr and (now - last[1]) < COOLDOWN_SECONDS:
                        continue                       # deduped within cooldown
                    _last_alert[key] = (curr, now)
                    escalation.arm(device, name, now)  # start the unacked-escalation clock
                    fire = ("alert", prev, p.get("status", "unknown"))
                else:
                    continue  # transition into a non-alert, non-ok state (e.g. warning)

        # Fire outside the lock (webhook posts spawn threads).
        kind = fire[0]
        if kind == "recovery":
            _fire_recovery(name, device)
        elif kind == "flap":
            _fire_flap(name, device, fire[1])
        elif kind == "alert":
            _fire(project_name=name, device=device, prev=fire[1], curr=curr, status=fire[2])


def clear() -> None:
    with _lock:
        _prev.clear()
        _transitions.clear()
        _flapping.clear()
        _in_alert.clear()
        _last_alert.clear()
