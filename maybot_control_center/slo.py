"""SLO / uptime tracking per project.

:mod:`history` records a health point each poll; this turns that raw series
into the numbers an operator actually cares about — rolling **uptime %**,
**incident count**, **MTTR** (mean time to recovery), and the current state —
over a configurable window.

Uptime is *time-weighted*: each point's health is counted for the interval
until the next point (the final point persists to "now"). ``unknown`` samples
are excluded from the uptime denominator (no signal), so a project that was
never reachable reports ``uptime=None`` rather than 0%.
"""
from __future__ import annotations

import os
import time

from . import history

WINDOW_HOURS = max(1, int(os.getenv("MAYBOT_SLO_WINDOW_HOURS", "168")))  # default 7d

_HEALTHY = {"ok"}
_DOWN = {"warning", "error"}


def _split_key(key: str) -> tuple[str, str]:
    device, _, name = key.partition(":")
    return device, name


def _project(points: list[dict], window_ms: int, now_ms: int) -> dict | None:
    pts = [p for p in points if isinstance(p.get("ts"), (int, float)) and p["ts"] >= now_ms - window_ms]
    if not pts:
        return None
    pts.sort(key=lambda p: p["ts"])

    up_ms = down_ms = 0.0
    incidents = 0
    recovery_durations: list[float] = []
    down_started: float | None = None
    prev_healthy = None

    for i, p in enumerate(pts):
        end = pts[i + 1]["ts"] if i + 1 < len(pts) else now_ms
        dur = max(0.0, end - p["ts"])
        h = str(p.get("health", "unknown")).lower()
        if h in _HEALTHY:
            up_ms += dur
        elif h in _DOWN:
            down_ms += dur

        healthy = h in _HEALTHY
        if prev_healthy is True and h in _DOWN:      # ok -> unhealthy = a new incident
            incidents += 1
            down_started = p["ts"]
        elif prev_healthy is False and healthy and down_started is not None:
            recovery_durations.append(p["ts"] - down_started)  # unhealthy span resolved
            down_started = None
        if h in _HEALTHY or h in _DOWN:
            prev_healthy = healthy

    measured = up_ms + down_ms
    uptime = round(100.0 * up_ms / measured, 3) if measured > 0 else None
    mttr = round(sum(recovery_durations) / len(recovery_durations) / 1000.0, 1) if recovery_durations else None
    last = pts[-1]
    return {
        "uptime_pct": uptime,
        "incidents": incidents,
        "mttr_seconds": mttr,
        "current": str(last.get("health", "unknown")).lower(),
        "samples": len(pts),
        "measured_seconds": round(measured / 1000.0, 1),
    }


def snapshot(window_hours: int | None = None) -> dict:
    hours = WINDOW_HOURS if window_hours is None else max(1, min(int(window_hours), 24 * 90))
    window_ms = hours * 3600 * 1000
    now_ms = int(time.time() * 1000)

    rows: list[dict] = []
    for key, points in history.all_series().items():
        stats = _project(points, window_ms, now_ms)
        if stats is None:
            continue
        device, name = _split_key(key)
        rows.append({"device": device, "project": name, **stats})

    rows.sort(key=lambda r: (r["uptime_pct"] if r["uptime_pct"] is not None else 101.0, r["project"]))
    measurable = [r["uptime_pct"] for r in rows if r["uptime_pct"] is not None]
    overall = {
        "window_hours": hours,
        "projects": len(rows),
        "total_incidents": sum(r["incidents"] for r in rows),
        "avg_uptime_pct": round(sum(measurable) / len(measurable), 3) if measurable else None,
    }
    return {"overall": overall, "projects": rows}
