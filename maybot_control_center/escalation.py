"""Escalation policies — the "Chain of Command".

A fired ``error`` alert that nobody has sworn an oath to (claimed) and that has
not been silenced is *escalated* up the chain after
``MAYBOT_ESCALATE_AFTER_SECONDS`` (default 900): an ``escalation`` event is
routed to the webhooks and the Ancestor's Hall. Escalation fires once per
incident; claiming, silencing, or recovery cancels it.

Generalises the Night-Watch's "error → escalate to the Ancestor" into a timed,
ack-aware policy that works for every project, not just the on-watch one.
"""
from __future__ import annotations

import os
import time

ESCALATE_AFTER = float(os.getenv("MAYBOT_ESCALATE_AFTER_SECONDS", "900"))
ENABLED = os.getenv("MAYBOT_ESCALATION", "1").strip().lower() not in {"0", "false", "no", ""}

# key -> {"since": ts, "escalated": bool, "device", "name"}
_pending: dict[str, dict] = {}


def arm(device: str, name: str, now: float | None = None) -> None:
    """Begin the escalation clock for a just-fired alert (idempotent)."""
    key = f"{device}:{name}"
    if key not in _pending:
        _pending[key] = {"since": now if now is not None else time.time(),
                         "escalated": False, "device": device, "name": name}


def disarm(device: str, name: str) -> None:
    _pending.pop(f"{device}:{name}", None)


def sweep(now: float | None = None) -> list[str]:
    """Escalate any armed alert past the threshold that is still unowned and
    unsilenced. Returns the keys escalated this sweep."""
    if not ENABLED:
        return []
    now = now if now is not None else time.time()
    from . import oaths, maintenance, notifier, governance, acks
    escalated: list[str] = []
    for key, rec in list(_pending.items()):
        if rec["escalated"] or (now - rec["since"]) < ESCALATE_AFTER:
            continue
        device, name = rec["device"], rec["name"]
        if oaths.is_claimed(device, name) or maintenance.is_silenced(device, name) \
                or acks.is_acked(device, name):
            continue  # owned, muted, or acknowledged — no escalation
        rec["escalated"] = True
        mins = int((now - rec["since"]) / 60)
        try:
            notifier.notify_event("escalation", f"Escalation: {name}",
                                  f"{name} on {device} has been in error {mins}m, unacknowledged.")
        except Exception:
            pass
        try:
            governance.system_notice(
                f"Unacknowledged incident escalated: {name} on {device} ({mins}m).",
                sender="Chain of Command")
        except Exception:
            pass
        escalated.append(key)
    return escalated


def snapshot() -> dict:
    return {"enabled": ENABLED, "escalate_after_seconds": ESCALATE_AFTER,
            "pending": [dict(v) for v in _pending.values()]}


def clear() -> None:
    _pending.clear()
