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
from pathlib import Path

import yaml

ENABLED = os.getenv("MAYBOT_AUTOPILOT", "0").strip().lower() in {"1", "true", "yes", "on"}
INTERVAL = max(15, int(os.getenv("MAYBOT_AUTOPILOT_INTERVAL", "60")))
MAXATTEMPTS = max(1, int(os.getenv("MAYBOT_AUTOPILOT_MAX_ATTEMPTS", "3")))
STATES = {s.strip().lower() for s in os.getenv("MAYBOT_AUTOPILOT_STATES", "error").split(",") if s.strip()}
CODER = os.getenv("MAYBOT_AUTOPILOT_CODER", "")  # optional designated coding disciple
# Allowlist of projects autopilot may touch ("device:project" or bare "project"); empty = all.
ALLOW = {s.strip() for s in os.getenv("MAYBOT_AUTOPILOT_PROJECTS", "").split(",") if s.strip()}
# Restart-loop circuit breaker: more than RESTART_LIMIT restarts within RESTART_WINDOW → stop & escalate.
RESTART_LIMIT = max(1, int(os.getenv("MAYBOT_AUTOPILOT_RESTART_LIMIT", "3")))
RESTART_WINDOW = max(60, int(os.getenv("MAYBOT_AUTOPILOT_RESTART_WINDOW", "1800")))
# Per-project overrides (mode: auto|propose|off, remediation, coder). See autopilot.yaml.example.
AUTOPILOT_FILE = Path(os.getenv("MAYBOT_AUTOPILOT_FILE", "autopilot.yaml"))
# Daily digest of what the second brain did (0 = off).
DIGEST_HOURS = float(os.getenv("MAYBOT_AUTOPILOT_DIGEST_HOURS", "24"))
LOG_CAP = 200

_counters = {"fixes": 0, "restarts": 0, "escalations": 0, "recoveries": 0, "proposals": 0}
_last_digest = 0.0


def load_config() -> dict:
    """Per-project autopilot overrides keyed by 'device:project' (or bare 'project')."""
    if not AUTOPILOT_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(AUTOPILOT_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    for entry in data.get("projects", []) or []:
        if isinstance(entry, dict) and entry.get("project"):
            out[entry["project"]] = entry
    return out


def _project_cfg(device: str, name: str) -> dict:
    cfg = load_config()
    return cfg.get(f"{device}:{name}") or cfg.get(name) or {}


def _allowed(device: str, name: str) -> bool:
    return not ALLOW or name in ALLOW or f"{device}:{name}" in ALLOW


def _save() -> None:
    from . import store
    if not store.enabled():
        return
    with _lock:
        store.save_state("autopilot", {"incidents": _incidents, "log": _log[-LOG_CAP:], "paused": _paused})


def load_persisted() -> None:
    from . import store
    data = store.load_state("autopilot")
    if not data:
        return
    global _paused
    with _lock:
        _incidents.update(data.get("incidents") or {})
        _log.extend((data.get("log") or [])[-LOG_CAP:])
        _paused = bool(data.get("paused"))


def _postmortem(name: str, device: str, inc: dict) -> None:
    """On recovery, write a short post-incident summary to the artifact vault."""
    actions = inc.get("actions") or []
    if not actions:
        return
    try:
        from . import artifacts
        lines = "\n".join(f"- {a.get('action')}: {a.get('result')}" for a in actions)
        content = (f"# Post-incident: {name} on {device}\n\n"
                   f"Resolved autonomously by the Sect Leader after {len(actions)} action(s).\n\n"
                   f"## Cause\n{inc.get('cause', 'unknown')}\n\n## Actions taken\n{lines}\n")
        artifacts.forge("Autopilot", f"Post-incident {name} #{int(time.time())}", "note",
                        content, description=f"Autopilot post-incident summary for {name}.")
    except Exception:
        pass

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
    _save()
    return status()


def status() -> dict:
    with _lock:
        return {"enabled": ENABLED, "paused": _paused, "leader": _leader(),
                "interval": INTERVAL, "max_attempts": MAXATTEMPTS, "counters": dict(_counters),
                "incidents": [{"key": k, **v} for k, v in _incidents.items()],
                "log": [dict(r) for r in _log[-50:][::-1]]}


def digest(now: float | None = None) -> str | None:
    """Post a rollup of recent autopilot activity (counters + recent events). Returns
    the digest text, or None if there was nothing to report."""
    now = now if now is not None else time.time()
    with _lock:
        c = dict(_counters)
        recent = [r for r in _log if now - r["ts"] / 1000.0 <= DIGEST_HOURS * 3600 and r["kind"] in ("recovered", "escalated")]
    if not any(c.values()):
        return None
    lines = "; ".join(f"{k}: {v}" for k, v in c.items() if v)
    notable = " | ".join(f"{r['title']}" for r in recent[-6:]) or "no recoveries/escalations"
    msg = f"Last {int(DIGEST_HOURS)}h — {lines}. Recent: {notable}."
    _report("digest", "Autopilot daily digest", msg, _leader())
    return msg


def maybe_digest(now: float | None = None) -> bool:
    global _last_digest
    if DIGEST_HOURS <= 0:
        return False
    now = now if now is not None else time.time()
    with _lock:
        due = (now - _last_digest) >= DIGEST_HOURS * 3600
        if due:
            _last_digest = now
    if due:
        digest(now)
    return due


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
    _save()


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


def _recent_logs(device: str, name: str) -> str:
    """Pull the failing project's recent error logs to ground the coder's diagnosis."""
    try:
        from .config import load_devices
        from . import agent_client
        dev = next((d for d in load_devices() if d.get("name") == device), None)
        if not dev:
            return ""
        res = agent_client.call_agent(dev, f"/api/projects/{name}/logs?level=ERROR")
        if not res.get("online"):
            return ""
        data = res.get("data") or {}
        lines = data.get("lines") or data.get("logs") or []
        text = "\n".join(lines) if isinstance(lines, list) else str(lines)
        return text[-2000:]
    except Exception:
        return ""


def _dispatch_coder(p: dict, plan: dict, coder: str | None = None) -> str:
    from . import agents, routing, taskqueue, governance
    name, device = p.get("name", "?"), p.get("device", "?")
    logs = _recent_logs(device, name)
    goal = (f"Project '{name}' on '{device}' is failing: {plan.get('cause', 'unknown')}.\n"
            f"Investigate the code, apply a fix, and run the tests to confirm it recovers."
            + (f"\n\nRecent ERROR logs:\n{logs}" if logs else ""))
    coder = coder or CODER or (routing.best_fit(f"{name} code backend fix") or {}).get("agent") or governance.leader()
    if not coder:
        return "no disciple available to patch"
    task = taskqueue.create(f"Fix {name}", description=goal, source="autopilot",
                            assignee=coder, priority="high", project=name, device=device)
    executor, _ = governance.route_task(coder, critical=True)
    try:
        agents.assign_task(executor, goal)
        taskqueue.link_dispatch(task["id"], executor)
        return f"dispatched {executor} to patch the code" + (" (with logs)" if logs else "")
    except Exception as exc:
        return f"failed to dispatch coder ({exc})"


def _perform_action(p: dict, plan: dict, coder: str | None = None) -> str:
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
        return _dispatch_coder(p, plan, coder)
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
                _postmortem(name, device, had)
                _counters["recoveries"] += 1
                _report("recovered", f"{name} recovered",
                        f"{name} on {device} is healthy again after autopilot intervention.", leader)
                acted.append((key, "recovered"))
            continue

        cfg = _project_cfg(device, name)
        mode = (cfg.get("mode") or "auto").lower()
        if mode == "off" or health not in STATES or maintenance.is_silenced(device, name) or not _allowed(device, name):
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
            _counters["escalations"] += 1
            _report("escalated", f"Autopilot stuck on {name}",
                    f"{name} still {health} after {MAXATTEMPTS} attempts — escalating to the Ancestor.", leader)
            acted.append((key, "escalated"))
            continue

        plan = _diagnose(leader, p)
        if cfg.get("remediation") in {"restart", "runbook", "code", "none"}:
            plan["action"] = cfg["remediation"]   # per-project override of the chosen remedy

        # Propose-only mode: recommend, don't act.
        if mode == "propose":
            with _lock:
                inc["state"] = "proposed"
                inc["cause"] = plan.get("cause", "")
            _counters["proposals"] += 1
            _report("proposal", f"Autopilot recommends for {name}",
                    f"Cause: {plan.get('cause', '?')}. Recommended fix: {plan.get('action')} "
                    f"(propose-only — awaiting the Ancestor).", leader)
            acted.append((key, "proposed"))
            continue

        # Restart-loop circuit breaker: don't keep bouncing a project that won't stay up.
        if plan.get("action") == "restart":
            with _lock:
                recent = [t for t in inc.get("restarts", []) if now - t < RESTART_WINDOW]
            if len(recent) >= RESTART_LIMIT:
                with _lock:
                    inc["state"] = "escalated"
                _counters["escalations"] += 1
                _report("escalated", f"Restart loop on {name}",
                        f"{name} restarted {len(recent)}× in {RESTART_WINDOW // 60}m — circuit opened, "
                        f"escalating to the Ancestor instead of restarting again.", leader)
                acted.append((key, "circuit_open"))
                continue
        result = _perform_action(p, plan, cfg.get("coder"))
        with _lock:
            inc["attempts"] += 1
            inc["state"] = "acting"
            inc["cause"] = plan.get("cause", "")
            inc["last_action"] = result
            inc.setdefault("actions", []).append({"action": plan.get("action"), "result": result, "ts": int(now * 1000)})
            if plan.get("action") == "restart":
                inc.setdefault("restarts", []).append(now)
            attempts = inc["attempts"]
        _counters["fixes"] += 1
        if plan.get("action") == "restart":
            _counters["restarts"] += 1
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
    out = handle(snap.get("projects", []))
    maybe_digest()
    return out


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
    global _paused, _last_digest
    with _lock:
        _incidents.clear()
        _log.clear()
        _paused = False
        _last_digest = 0.0
        for k in _counters:
            _counters[k] = 0
