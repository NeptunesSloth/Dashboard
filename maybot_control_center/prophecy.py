"""Prophecy / divination — read the omens in your metrics.

Reads the recorded metrics history (the same series that feeds the sparklines)
and forecasts each project's near-term health with a light trend + anomaly
model, framed as a "heavenly omen". Under the costume it's simple early-warning:
a sharp drop, a worsening trend, or recent error/warning states surface before
they become an outage.
"""
from __future__ import annotations

import statistics

from . import history


def _forecast(points: list[dict]) -> tuple[str, str]:
    healths = [p.get("health") for p in points]
    pnls = [p["pnl"] for p in points if isinstance(p.get("pnl"), (int, float))]

    recent = healths[-5:]
    if any(h == "error" for h in recent):
        return "ominous", "a baleful star — recent error in the realm"
    omen, note = "favorable", "the path is steady"
    if recent.count("warning") >= 2:
        omen, note = "caution", "warnings gather like storm clouds"

    if len(pnls) >= 6:
        mid = len(pnls) // 2
        slope = statistics.mean(pnls[mid:]) - statistics.mean(pnls[:mid])
        sd = statistics.pstdev(pnls) or 1.0
        z = (pnls[-1] - statistics.mean(pnls)) / sd
        if z <= -2:
            return "ominous", "a sudden ill omen — a sharp plunge"
        if slope < -1 and omen == "favorable":
            omen, note = "caution", "fortunes wane — a downward trend"
        elif z >= 2 and omen == "favorable":
            note = "an auspicious surge"
    return omen, note


def divine(min_points: int = 3) -> list[dict]:
    out = []
    for key, pts in history.all_series().items():
        if len(pts) < min_points:
            continue
        device, _, project = key.partition(":")
        omen, note = _forecast(pts)
        out.append({"key": key, "device": device, "project": project,
                    "omen": omen, "note": note, "points": len(pts)})
    # surface the most concerning omens first
    rank = {"ominous": 0, "caution": 1, "favorable": 2}
    out.sort(key=lambda o: rank.get(o["omen"], 3))
    return out
