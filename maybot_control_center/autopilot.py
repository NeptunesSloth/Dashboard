"""The Sect Leader's "second brain" — an autonomous operations autopilot.

When enabled (``MAYBOT_AUTOPILOT=1``), the Sect Leader watches the fleet and,
for any project that goes unhealthy, runs a closed loop **without the operator**:

    detect → diagnose → act → verify → continue → report

- **detect:** an unhealthy project is picked up; the Leader swears an oath to it
  (suppressing duplicate pages) and announces it.
- **diagnose:** the Leader (LLM, with a safe heuristic fallback) decides the
  likely cause and one remediation: ``restart`` | ``runbook`` | ``code`` | ``none``.
- **act (full auto):** restart/stop, run a remediation runbook, or dispatch a
  coding disciple to patch the project and run its tests.
- **verify:** the next poll checks health; recovery clears the incident.
- **escalate:** if still broken after ``MAXATTEMPTS`` attempts, it stops acting
  and escalates to the Ancestor.

Every step is reported to the Ancestor's Hall and the alert webhooks. A runtime
kill switch (:func:`set_paused`) and the ``MAYBOT_AUTOPILOT`` gate keep it
controllable; it runs headless on a background loop so it works while you're away.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

ENABLED = os.getenv("MAYBOT_AUTOPILOT", "0").strip().lower() in {"1", "true", "yes", "on"}
INTERVAL = max(15, int(os.getenv("MAYBOT_AUTOPILOT_INTERVAL", "60")))
MAXATTEMPTS = max(1, int(os.getenv("MAYBOT_AUTOPILOT_MAX_ATTEMPTS", "3")))
STATES = {s.strip().lower() for s in os.getenv("MAYBOT_AUTOPILOT_STATES", "error").split(",") if s.strip()}
CODER = os.getenv("MAYBOT_AUTOPILOT_CODER", "")  # optional designated coding disciple
LOG_CAP = 200

_lock = threading.Lock()
_paused = False
_incidents: dict[str, dict] = {}     # key -> {state, attempts, since, last_action}
_log: list[dict] = []
_started = False


def _leader() -> str | None:
    from . import governance
    return governance.leader()


def set_paused(value: bool) -> dict:
    global _paused
    with _lock:
        _paused = bool(value)
    return status()


def status() -> dict:
    with _lock:
        return {"enabled": ENABLED, "paused": _paused, "leader": _leader(),
                "interval": INTERVAL, "max_attempts": MAXATTEMPTS,
                "incidents": [{"key": k, **v} for k, v in _incidents.items()],
                "log": [dict(r) for r in _log[-50:][::-1]]}


def _report(kind: str, title: str, message: str, sender: str | None) -> None:
    rec = {"kind": kind, "title": title, "message": message,
           "ts": int(time.time() * 1000), "by": sender or "Sect Leader"}
    with _lock:
        _log.append(rec)
        if len(_log) > LOG_CAP:
            del _log[:-LOG_CAP]
    try:
        from . import governance
        governance.system_notice(f"🧠 [Autopilot] {title} — {message}", sender=sender or "Sect Leader")
    except Exception:
        pass
    try:
        from . import notifier
        notifier.notify_event("autopilot", title, message)
    except Exception:
        pass


# ---- diagnosis -------------------------------------------------------------
def _heuristic_plan(p: dict, leader: str | None) -> dict:
    status_l = str(p.get("status", "")).lower()
    if status_l in {"stopped", "crashed", "exited"} or p.get("status") != "running":
        action = "restart"
    elif p.get("type") in {"code_project", "ai_project"}:
        action = "code"
    else:
        action = "runbook"
    return {"cause": "; ".join(p.get("alerts", [])) or f"{p.get('health')} ({p.get('status')})",
            "action": action, "summary": "heuristic plan", "by": leader}


def _diagnose(leader: str | None, p: dict) -> dict:
    """Ask the Leader for {cause, action, summary}; fall back to a heuristic."""
    from . import agents
    agent = agents._agent_def(leader) if leader else None
    if agent:
        info = (f"Project '{p.get('name')}' on device '{p.get('device')}': health={p.get('health')}, "
                f"status={p.get('status')}, type={p.get('type')}, alerts={p.get('alerts')}.")
        sys = ("You are the Sect Leader acting as an autonomous operator (a second brain) for the "
               "Ancestor's projects. A project is unhealthy. Diagnose the most likely cause and choose "
               "ONE remediation. Reply with ONLY JSON: "
               '{"cause":"...","action":"restart|runbook|code|none","summary":"..."}')
        try:
            ok, text, _ = agents._chat(agent, [{"role": "system", "content": sys},
                                               {"role": "user", "content": info}])
            if ok and text:
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    d = json.loads(m.group(0))
                    if d.get("action") in {"restart", "runbook", "code", "none"}:
                        return {"cause": str(d.get("cause", ""))[:300], "action": d["action"],
                                "summary": str(d.get("summary", ""))[:500], "by": leader}
        except Exception:
            pass
    return _heuristic_plan(p, leader)


# ---- actions ---------------------------------------------------------------
def _restart(device: str, name: str) -> str:
    from .config import load_devices
    from . import agent_client
    dev = next((d for d in load_devices() if d.get("name") == device), None)
    if not dev:
        return "device not found"
    agent_client.post_agent(dev, f"/api/projects/{name}/stop", timeout=15)
    res = agent_client.post_agent(dev, f"/api/projects/{name}/start", timeout=15)
    return "restarted the bot" if res.get("online") else f"restart failed ({res.get('error')})"


def _dispatch_coder(p: dict, plan: dict) -> str:
    from . import agents, routing, taskqueue, governance
    goal = (f"Project '{p.get('name')}' on '{p.get('device')}' is failing: {plan.get('cause', 'unknown')}. "
            f"Investigate the code, apply a fix, and run the tests to confirm it recovers.")
    coder = CODER or (routing.best_fit(goal + " code backend fix") or {}).get("agent") or governance.leader()
    if not coder:
        return "no disciple available to patch"
    task = taskqueue.create(f"Fix {p.get('name')}", description=goal, source="autopilot",
                            assignee=coder, priority="high")
    executor, _ = governance.route_task(coder, critical=True)
    try:
        agents.assign_task(executor, goal)
        taskqueue.link_dispatch(task["id"], executor)
        return f"dispatched {executor} to patch the code"
    except Exception as exc:
        return f"failed to dispatch coder ({exc})"


def _perform_action(p: dict, plan: dict) -> str:
    action = plan.get("action")
    name, device = p.get("name", "?"), p.get("device", "?")
    if action == "restart":
        return _restart(device, name)
    if action == "runbook":
        try:
            from . import runbooks
            r = runbooks.dispatch(p)
        except Exception:
            r = None
        return f"ran runbook '{r.get('runbook')}'" if r else _restart(device, name)
    if action == "code":
        return _dispatch_coder(p, plan)
    return "no action taken"


# ---- the loop --------------------------------------------------------------
def handle(projects: list[dict], now: float | None = None) -> list[tuple]:
    """One pass of the detect→diagnose→act→verify loop. Returns (key, outcome) tuples."""
    if not ENABLED or _paused:
        return []
    leader = _leader()
    if not leader:
        return []
    now = now if now is not None else time.time()
    from . import maintenance, oaths
    acted: list[tuple] = []
    for p in projects or []:
        name, device = p.get("name", "?"), p.get("device", "?")
        key = f"{device}:{name}"
        health = str(p.get("health", "")).lower()

        if health == "ok":
            with _lock:
                had = _incidents.pop(key, None)
            if had:
                oaths.release(key)
                _report("recovered", f"{name} recovered",
                        f"{name} on {device} is healthy again after autopilot intervention.", leader)
                acted.append((key, "recovered"))
            continue

        if health not in STATES or maintenance.is_silenced(device, name):
            continue

        with _lock:
            inc = _incidents.get(key)
            fresh = inc is None
            if fresh:
                inc = _incidents[key] = {"state": "detected", "attempts": 0, "since": now, "last_action": None}
            if inc["state"] == "escalated":
                continue
            escalate = inc["attempts"] >= MAXATTEMPTS
            if escalate:
                inc["state"] = "escalated"

        if fresh:
            oaths.claim(key, leader, "autopilot handling")
            _report("detected", f"Autopilot: {name} {health}",
                    f"Sect Leader {leader} detected {name} on {device} is {health}; investigating.", leader)

        if escalate:
            _report("escalated", f"Autopilot stuck on {name}",
                    f"{name} still {health} after {MAXATTEMPTS} attempts — escalating to the Ancestor.", leader)
            acted.append((key, "escalated"))
            continue

        plan = _diagnose(leader, p)
        result = _perform_action(p, plan)
        with _lock:
            inc["attempts"] += 1
            inc["state"] = "acting"
            inc["last_action"] = result
            attempts = inc["attempts"]
        _report("fix", f"Autopilot fixing {name}",
                f"Cause: {plan.get('cause', '?')}. Action: {plan.get('action')} → {result}. "
                f"(attempt {attempts}/{MAXATTEMPTS})", leader)
        acted.append((key, plan.get("action")))
    return acted


def tick() -> list[tuple]:
    if not ENABLED or _paused:
        return []
    from . import aggregator
    from .config import load_devices
    try:
        snap = aggregator.aggregate(load_devices())
    except Exception:
        return []
    return handle(snap.get("projects", []))


def _loop() -> None:
    while True:
        time.sleep(INTERVAL)
        try:
            tick()
        except Exception:
            pass


def start() -> bool:
    global _started
    if _started or not ENABLED:
        return False
    _started = True
    threading.Thread(target=_loop, daemon=True).start()
    return True


def clear() -> None:
    global _paused
    with _lock:
        _incidents.clear()
        _log.clear()
        _paused = False
