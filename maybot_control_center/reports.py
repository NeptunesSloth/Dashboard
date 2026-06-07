"""Periodic summary reports — the sect's "Daily Proclamation".

Synthesises a human-readable digest of fleet health from the data the control
center already keeps: SLO/uptime per project, the last overview summary
(devices, trading PnL), recent incidents/escalations, and notification volume.
Surfaced at ``GET /api/reports/daily`` and, when ``MAYBOT_REPORT_INTERVAL_HOURS``
is set (>0), delivered automatically to the configured notification channels by
a background thread.

Read-only and dependency-light: it reads in-memory snapshots, never polls.
"""
from __future__ import annotations

import os
import threading
import time

INTERVAL_HOURS = float(os.getenv("MAYBOT_REPORT_INTERVAL_HOURS", "0") or 0)
WINDOW_HOURS = max(1, int(os.getenv("MAYBOT_REPORT_WINDOW_HOURS", "24")))

_lock = threading.Lock()
_last_run: float = 0.0
_started = False


def build(window_hours: int | None = None) -> dict:
    """Assemble the report payload for the given look-back window."""
    hours = WINDOW_HOURS if window_hours is None else max(1, int(window_hours))
    from . import slo, aggregator, notify

    slo_snap = slo.snapshot(hours)
    overall = slo_snap.get("overall", {})
    rows = slo_snap.get("projects", [])

    worst = sorted(
        (r for r in rows if r.get("uptime_pct") is not None),
        key=lambda r: r["uptime_pct"],
    )[:5]
    unhealthy = [r for r in rows if str(r.get("current", "")).lower() in {"error", "warning"}]

    summary = aggregator.last_summary()
    recent = notify.recent(100)

    return {
        "generated_at": int(time.time() * 1000),
        "window_hours": hours,
        "fleet": {
            "devices_total": summary.get("total_devices"),
            "devices_online": summary.get("online_devices"),
            "projects_total": summary.get("total_projects"),
            "projects_unhealthy": summary.get("projects_with_warnings_errors"),
            "bots_running": summary.get("bots_running"),
            "trading_profit_today": summary.get("total_trading_profit_today"),
        },
        "reliability": {
            "avg_uptime_pct": overall.get("avg_uptime_pct"),
            "total_incidents": overall.get("total_incidents"),
            "projects_measured": overall.get("projects"),
            "worst_uptime": [
                {"device": r["device"], "project": r["project"],
                 "uptime_pct": r["uptime_pct"], "incidents": r["incidents"]}
                for r in worst
            ],
            "currently_unhealthy": [
                {"device": r["device"], "project": r["project"], "state": r["current"]}
                for r in unhealthy
            ],
        },
        "notifications_sent": len(recent),
    }


def render_text(report: dict | None = None) -> str:
    """Render a report dict as a compact plaintext digest."""
    r = report or build()
    f = r["fleet"]
    rel = r["reliability"]
    lines = [
        f"MayBot Daily Proclamation — last {r['window_hours']}h",
        "",
        f"Fleet: {f.get('devices_online')}/{f.get('devices_total')} devices online, "
        f"{f.get('projects_total')} projects ({f.get('projects_unhealthy')} unhealthy), "
        f"{f.get('bots_running')} bots running.",
        f"Trading PnL today: {f.get('trading_profit_today')}",
        "",
        f"Reliability: avg uptime {rel.get('avg_uptime_pct')}% across "
        f"{rel.get('projects_measured')} projects, {rel.get('total_incidents')} incidents.",
    ]
    if rel["worst_uptime"]:
        lines.append("Lowest uptime:")
        for w in rel["worst_uptime"]:
            lines.append(f"  - {w['device']}:{w['project']} {w['uptime_pct']}% ({w['incidents']} incidents)")
    if rel["currently_unhealthy"]:
        lines.append("Currently unhealthy:")
        for u in rel["currently_unhealthy"]:
            lines.append(f"  - {u['device']}:{u['project']} [{u['state']}]")
    lines.append("")
    lines.append(f"Notifications sent (recent buffer): {r['notifications_sent']}")
    return "\n".join(lines)


def deliver() -> dict:
    """Build the report and push it to the configured notification channels."""
    from . import notify
    report = build()
    res = notify.send("MayBot Daily Proclamation", render_text(report),
                      level="info", kind="report")
    with _lock:
        global _last_run
        _last_run = time.time()
    return {"delivered": res.get("delivered", []), "report": report}


def _due(now: float) -> bool:
    if INTERVAL_HOURS <= 0:
        return False
    with _lock:
        return (now - _last_run) >= INTERVAL_HOURS * 3600


def tick(now: float | None = None) -> bool:
    """Deliver the report if the interval has elapsed. Returns True if it ran."""
    now = now if now is not None else time.time()
    if not _due(now):
        return False
    deliver()
    return True


def _loop() -> None:
    while True:
        time.sleep(300)
        try:
            tick()
        except Exception:
            pass


def start() -> bool:
    """Start the background report scheduler (no-op unless interval is set)."""
    global _started, _last_run
    if _started or INTERVAL_HOURS <= 0:
        return False
    _started = True
    with _lock:
        _last_run = time.time()  # first report fires one interval after startup
    threading.Thread(target=_loop, daemon=True).start()
    return True


def clear() -> None:
    global _last_run, _started
    with _lock:
        _last_run = 0.0
    _started = False
