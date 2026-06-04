"""Maintenance windows / alert silencing.

When you knowingly restart a bot or take a device down for upkeep, you don't
want to be paged for the self-inflicted ``error`` state. A *silence* mutes
alerting (and incident auto-dispatch / remediation) for a target until it
expires, is lifted, or the target recovers.

Targets are matched against a project's ``device:project`` key:

  - ``"*"``                — silence everything
  - ``"device:*"``         — silence every project on one device
  - ``"device:project"``   — silence one project

State is intentionally in-memory (a monitoring aid, not a system of record),
mirroring :mod:`history`; it resets when the control center restarts.
"""
from __future__ import annotations

import datetime
import os
import threading
import time
from pathlib import Path

import yaml

_lock = threading.Lock()
# target -> {"target", "until" (epoch secs or None=indefinite), "reason", "who",
#            "created_at", "clear_on_recovery"}
_silences: dict[str, dict] = {}

# ---- Heavenly Calendar: scheduled / recurring maintenance windows -----------
CALENDAR_FILE = Path(os.getenv("MAYBOT_CALENDAR_FILE", "calendar.yaml"))
_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def load_windows() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    data = yaml.safe_load(CALENDAR_FILE.read_text(encoding="utf-8")) or {}
    w = data.get("windows", [])
    return w if isinstance(w, list) else []


def _recurring_active(w: dict, now: float) -> tuple[bool, int]:
    """(active, seconds_until_end) for a recurring daily/weekly window."""
    try:
        sh, sm = (int(x) for x in str(w.get("start", "0:00")).split(":", 1))
    except Exception:
        return False, 0
    dur = max(1, int(w.get("duration_minutes", 60)))
    lt = time.localtime(now)
    now_min = lt.tm_hour * 60 + lt.tm_min
    start_min, end_min = sh * 60 + sm, sh * 60 + sm + dur
    days = w.get("days") or ["*"]
    day_ok = "*" in days or any(_DAYS.get(str(d).lower()[:3]) == lt.tm_wday for d in days)
    if end_min <= 1440:
        active = day_ok and start_min <= now_min < end_min
        remaining = (end_min - now_min) * 60
    else:  # window crosses midnight
        active = (day_ok and now_min >= start_min) or now_min < (end_min - 1440)
        remaining = ((end_min - now_min) if now_min >= start_min else (end_min - 1440 - now_min)) * 60
    return active, max(0, remaining)


def _oneoff_active(w: dict, now: float) -> tuple[bool, int]:
    try:
        start = datetime.datetime.fromisoformat(str(w.get("start")))
    except Exception:
        return False, 0
    dur = max(1, int(w.get("duration_minutes", 60)))
    end = start + datetime.timedelta(minutes=dur)
    now_dt = datetime.datetime.fromtimestamp(now)
    active = start <= now_dt < end
    return active, max(0, int((end - now_dt).total_seconds())) if active else 0


def scheduled_active(now: float | None = None) -> list[dict]:
    now = _now() if now is None else now
    out = []
    for w in load_windows():
        target = w.get("target")
        if not target:
            continue
        recurring = bool(w.get("days") or w.get("recurring") or ":" in str(w.get("start", "")) and "T" not in str(w.get("start", "")))
        active, remaining = (_recurring_active(w, now) if recurring else _oneoff_active(w, now))
        if active:
            out.append({"target": target, "reason": (w.get("reason") or "").strip()[:200],
                        "ends_in": remaining, "scheduled": True})
    return out


def _now() -> float:
    return time.time()


def _key(device: str, name: str) -> str:
    return f"{device}:{name}"


def _matches(target: str, key: str) -> bool:
    if target == "*":
        return True
    if target == key:
        return True
    if target.endswith(":*"):
        return key.startswith(target[:-1])  # "device:*" -> prefix "device:"
    return False


def _prune(now: float) -> None:
    for t, s in list(_silences.items()):
        if s["until"] is not None and s["until"] <= now:
            del _silences[t]


def silence(target: str, minutes: float = 60.0, reason: str = "",
            who: str = "operator", clear_on_recovery: bool = True) -> dict:
    """Mute alerting for ``target``. ``minutes <= 0`` silences indefinitely
    (until lifted or, if enabled, the target recovers to ok)."""
    now = _now()
    until = None if minutes <= 0 else now + minutes * 60.0
    rec = {"target": target, "until": until, "reason": reason.strip()[:200],
           "who": who, "created_at": now, "clear_on_recovery": bool(clear_on_recovery)}
    with _lock:
        _silences[target] = rec
    _save()
    return _public(rec, now)


def unsilence(target: str) -> bool:
    with _lock:
        removed = _silences.pop(target, None) is not None
    if removed:
        _save()
    return removed


def is_silenced(device: str, name: str) -> bool:
    key = _key(device, name)
    now = _now()
    with _lock:
        _prune(now)
        if any(_matches(t, key) for t in _silences):
            return True
    # An active scheduled maintenance window also silences.
    return any(_matches(w["target"], key) for w in scheduled_active(now))


def note_recovery(device: str, name: str) -> None:
    """A project returned to ok — drop any recovery-clearing silence matching it."""
    key = _key(device, name)
    changed = False
    with _lock:
        for t, s in list(_silences.items()):
            if s.get("clear_on_recovery") and _matches(t, key):
                del _silences[t]
                changed = True
    if changed:
        _save()


def _public(rec: dict, now: float) -> dict:
    out = dict(rec)
    out["expires_in"] = None if rec["until"] is None else max(0, round(rec["until"] - now))
    return out


def active() -> list[dict]:
    now = _now()
    with _lock:
        _prune(now)
        return [_public(s, now) for s in sorted(_silences.values(), key=lambda s: s["created_at"])]


def snapshot() -> dict:
    return {"silences": active(), "scheduled": scheduled_active(), "now": int(_now())}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("maintenance", _silences)


def load_persisted() -> None:
    from . import store
    data = store.load_state("maintenance")
    if data:
        with _lock:
            _silences.update(data)


def clear() -> None:
    with _lock:
        _silences.clear()
    _save()
