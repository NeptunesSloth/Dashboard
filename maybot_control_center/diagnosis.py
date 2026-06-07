"""Heuristic incident diagnosis — the "why" behind an unhealthy bot.

No LLM required: scans a project's recent ERROR logs for well-known failure
signatures and pairs them with the project's metrics to produce a concise
root-cause summary and a concrete suggestion. The autopilot's LLM diagnosis is
richer when configured; this always works, instantly, for free.
"""
from __future__ import annotations

import re

# (signature regex, signal label, human cause, suggested fix)
_SIGNATURES = [
    (r"connection refused|econnrefused|failed to connect|connection reset|could not connect",
     "dependency unreachable", "A service it depends on (broker/API/DB) is refusing connections.",
     "Check that the upstream service is running and reachable from the bot host."),
    (r"timed out|timeout|etimedout|read timed out",
     "timeouts", "Requests are timing out — the upstream is slow or the network is degraded.",
     "Check upstream latency/health and raise the client timeout if it's just slow."),
    (r"out of memory|oom|memoryerror|killed process|cannot allocate",
     "out of memory", "The process ran out of memory and was likely killed.",
     "Lower memory use or raise the host/container memory limit; check for leaks."),
    (r"\b(401|403)\b|unauthorized|forbidden|invalid api key|authentication failed|permission denied",
     "auth failure", "Credentials are missing, expired, or rejected.",
     "Rotate/refresh the API key or token and confirm it's set in the bot's environment."),
    (r"\b429\b|rate limit|too many requests|quota exceeded",
     "rate limited", "The bot is being throttled by an upstream API.",
     "Back off / add retry-with-jitter, or request a higher rate limit."),
    (r"insufficient (funds|buying power|balance|margin)|not enough buying power",
     "capital exhausted", "Orders are failing for lack of buying power / margin.",
     "Free up capital, reduce position size, or pause new entries until funded."),
    (r"no space left|disk full|enospc",
     "disk full", "The disk is full, so writes/logs are failing.",
     "Clear space or grow the volume; check log/data retention."),
    (r"database is locked|deadlock|could not obtain lock",
     "db contention", "Database lock contention is blocking work.",
     "Serialize writers or add retry/backoff around the DB."),
    (r"traceback \(most recent call last\)|unhandled exception|panic:",
     "code exception", "The bot is throwing an unhandled exception.",
     "Open the logs to the traceback and fix the failing code path."),
]
_EXC = re.compile(r"^([A-Za-z_][A-Za-z0-9_\.]*(?:Error|Exception|Warning)):", re.MULTILINE)


def analyze_logs(lines: list[str]) -> list[dict]:
    """Return matched failure signatures (most frequent first)."""
    text = "\n".join(str(x) for x in (lines or []))
    low = text.lower()
    out = []
    for rx, signal, cause, fix in _SIGNATURES:
        n = len(re.findall(rx, low))
        if n:
            out.append({"signal": signal, "count": n, "cause": cause, "suggestion": fix})
    out.sort(key=lambda d: -d["count"])
    # surface the most recent exception type if any
    excs = _EXC.findall(text)
    if excs:
        out.append({"signal": f"exception: {excs[-1]}", "count": len(excs),
                    "cause": f"Most recent exception type: {excs[-1]}.",
                    "suggestion": "Trace where this exception is raised and guard it."})
    return out


def diagnose(device: str, project: str) -> dict:
    """Pull a project's ERROR logs + status and produce a root-cause summary."""
    from .agent_client import call_agent
    from .config import all_devices
    dev = next((d for d in all_devices() if d.get("name") == device), None)
    if not dev:
        return {"ok": False, "error": f"unknown host '{device}'"}
    proj = None
    pl = call_agent(dev, "/api/projects").get("data", [])
    if isinstance(pl, list):
        proj = next((p for p in pl if p.get("name") == project), None)
    lg = call_agent(dev, f"/api/projects/{project}/logs?level=ERROR").get("data", {})
    lines = lg.get("lines") if isinstance(lg, dict) else None
    findings = analyze_logs(lines or [])
    health = (proj or {}).get("health", "unknown")
    metrics = (proj or {}).get("metrics", {}) or {}
    alerts = (proj or {}).get("alerts", []) or []
    if findings:
        top = findings[0]
        summary = f"Likely root cause: {top['cause']}"
        suggestion = top["suggestion"]
    elif health in ("error", "warning"):
        summary = f"'{project}' is {health}, but no known error signature was found in recent logs."
        suggestion = "Open the full logs and check the process/exit status on the host."
    else:
        summary = f"'{project}' looks healthy — nothing alarming in recent logs."
        suggestion = ""
    return {"ok": True, "device": device, "project": project, "health": health,
            "summary": summary, "suggestion": suggestion, "findings": findings,
            "alerts": [str(a) for a in alerts][:5],
            "lines_scanned": len(lines or [])}
