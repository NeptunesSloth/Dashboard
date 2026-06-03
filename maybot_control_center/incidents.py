"""Event-driven missions: when a monitored project goes unhealthy, auto-dispatch
a diagnostic task to a designated incident agent (``MAYBOT_INCIDENT_AGENT``).

The agent can then request a guarded tool (e.g. read the project's logs) and post
its findings. Debounced: one dispatch per incident, not re-fired until the
project recovers to ``ok``. Disabled unless an incident agent is configured and
exists in agents.yaml.
"""
from __future__ import annotations

import os
import threading

from . import agents
from . import cultivation
from . import notifier

INCIDENT_AGENT = os.getenv("MAYBOT_INCIDENT_AGENT", "")
STATES = {s.strip().lower() for s in os.getenv("MAYBOT_INCIDENT_STATES", "error").split(",") if s.strip()}

_lock = threading.Lock()
_active: set[str] = set()


def enabled() -> bool:
    return bool(INCIDENT_AGENT) and agents._agent_def(INCIDENT_AGENT) is not None


def _dispatch(p: dict) -> None:
    alerts = "; ".join(p.get("alerts", [])) or "none"
    task = (f"HEAVENLY TRIBULATION — a fallen realm calls. Project '{p.get('name')}' on device "
            f"'{p.get('device')}' is {p.get('health')} (status {p.get('status')}, type {p.get('type')}). "
            f"Alerts: {alerts}. Diagnose the likely cause and recommend a concrete next step to "
            f"survive the tribulation. If a tool would help (e.g. reading the logs), request it.")
    notifier.notify_event("incident", f"Incident on {p.get('name')}",
                          f"device {p.get('device')} is {p.get('health')} — {alerts}. Dispatched {INCIDENT_AGENT}.")
    try:
        # The incident IS the disciple's tribulation trial: survive (succeed) or be struck down.
        cultivation.face_tribulation(INCIDENT_AGENT, p.get("name", "?"))
        agents.assign_task(INCIDENT_AGENT, task)
    except Exception:
        with _lock:
            _active.discard(f"{p.get('device', '?')}:{p.get('name', '?')}")


def maybe_dispatch(projects: list[dict]) -> None:
    if not enabled():
        return
    for p in projects or []:
        key = f"{p.get('device', '?')}:{p.get('name', '?')}"
        health = str(p.get("health", "unknown")).lower()
        if health in STATES:
            with _lock:
                if key in _active:
                    continue
                _active.add(key)
            _dispatch(p)
        elif health == "ok":
            with _lock:
                _active.discard(key)


def clear() -> None:
    with _lock:
        _active.clear()
