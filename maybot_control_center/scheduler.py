"""Scheduled missions: run a task / mission / quest / debate on an interval.

Defined in ``schedules.yaml`` (see schedules.yaml.example) and ticked by a
background thread. Each entry fires once per ``every_minutes`` (the first
interval after startup, not at boot). No file → the scheduler stays idle.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import yaml

SCHEDULES_FILE = Path(os.getenv("MAYBOT_SCHEDULES_FILE", "schedules.yaml"))

_lock = threading.Lock()
_last: dict[str, float] = {}
_started = False


def load_schedules() -> list[dict]:
    if not SCHEDULES_FILE.exists():
        return []
    data = yaml.safe_load(SCHEDULES_FILE.read_text(encoding="utf-8")) or {}
    s = data.get("schedules", [])
    return s if isinstance(s, list) else []


def _run_action(s: dict) -> None:
    from . import agents, comms, cultivation, quests
    action = (s.get("action") or "task").lower()
    try:
        if action == "task":
            agents.assign_task(s["agent"], s["task"])
        elif action == "mission":
            comms.start_mission(s.get("goal", ""), s.get("participants", []), s.get("rounds", 2))
        elif action == "debate":
            comms.start_debate(s.get("topic", ""), s["a"], s["b"], s["judge"], s.get("rounds", 2))
        elif action == "quest":
            q = quests.get(s.get("quest", ""))
            if q:
                cultivation.assign_quest(s["agent"], q["reward_skill"], q["stones"])
                agents.assign_task(s["agent"], f"[Quest: {q['name']}] {q['task']}")
    except Exception:
        pass


def tick(now: float | None = None) -> list[str]:
    """Fire any due schedules; returns the names fired. Safe to call repeatedly."""
    now = now if now is not None else time.time()
    fired = []
    for s in load_schedules():
        name = s.get("name")
        if not name:
            continue
        every = max(1, int(s.get("every_minutes", 60))) * 60
        with _lock:
            if name not in _last:
                _last[name] = now  # register without firing at boot
                continue
            if now - _last[name] < every:
                continue
            _last[name] = now
        _run_action(s)
        fired.append(name)
    return fired


def _loop() -> None:
    while True:
        time.sleep(60)
        try:
            from . import safemode
            if not safemode.engaged():     # panic button halts scheduled missions too
                tick()
        except Exception:
            pass


def start() -> bool:
    global _started
    if _started or not load_schedules():
        return False
    _started = True
    threading.Thread(target=_loop, daemon=True).start()
    return True


def clear() -> None:
    with _lock:
        _last.clear()
