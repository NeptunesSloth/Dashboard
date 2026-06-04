"""Error budgets & deploy-freeze — the "Karmic Debt / Heavenly Decree".

Every project is granted a *fated misfortune* — the downtime it may suffer and
still meet its SLO target. :mod:`slo` measures the uptime actually achieved over
the window; here we turn the gap into an **error budget**: how much of the
allowed misfortune remains.

When a project burns through its budget (uptime fell below its target), the sect
issues a **Heavenly Decree** and *freezes* risky changes to it — state-changing
actions (start/stop) are refused until reliability recovers (an operator can
still override with ``force``). Real value: SLO-driven change freeze.

Targets: ``MAYBOT_SLO_TARGET_PCT`` (default 99.0) is the fleet default; override
per project via ``MAYBOT_SLO_TARGETS="device:project=99.9,device:other=99.0"``.
"""
from __future__ import annotations

import os

from . import slo

DEFAULT_TARGET = float(os.getenv("MAYBOT_SLO_TARGET_PCT", "99.0"))


def targets() -> dict[str, float]:
    out: dict[str, float] = {}
    for item in os.getenv("MAYBOT_SLO_TARGETS", "").split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, _, val = item.partition("=")
        try:
            out[key.strip()] = float(val)
        except ValueError:
            continue
    return out


def target_for(device: str, name: str) -> float:
    return targets().get(f"{device}:{name}", DEFAULT_TARGET)


def _evaluate_row(row: dict) -> dict:
    target = targets().get(f"{row['device']}:{row['project']}", DEFAULT_TARGET)
    uptime = row.get("uptime_pct")
    out = {"device": row["device"], "project": row["project"], "target_pct": target,
           "uptime_pct": uptime, "budget_remaining_pct": None, "frozen": False}
    if uptime is None:
        return out
    allowed = max(0.0, 100.0 - target)        # allowed downtime %
    consumed = max(0.0, 100.0 - uptime)       # downtime % actually suffered
    if allowed <= 0:
        out["budget_remaining_pct"] = 0.0 if consumed > 0 else 100.0
    else:
        out["budget_remaining_pct"] = round(max(0.0, 100.0 * (1.0 - consumed / allowed)), 1)
    out["frozen"] = uptime < target
    return out


def snapshot(window_hours: int | None = None) -> dict:
    rows = [_evaluate_row(r) for r in slo.snapshot(window_hours)["projects"]]
    frozen = [r for r in rows if r["frozen"]]
    return {"default_target_pct": DEFAULT_TARGET, "projects": rows,
            "frozen": [f"{r['device']}:{r['project']}" for r in frozen]}


def _row_for(device: str, name: str) -> dict | None:
    key = f"{device}:{name}"
    for r in snapshot()["projects"]:
        if f"{r['device']}:{r['project']}" == key:
            return r
    return None


def is_frozen(device: str, name: str) -> bool:
    row = _row_for(device, name)
    return bool(row and row["frozen"])


def annotate(project: dict, by_key: dict[str, dict]) -> dict:
    """Attach error-budget state to a project dict (from a precomputed map)."""
    key = f"{project.get('device', '?')}:{project.get('name', '?')}"
    row = by_key.get(key)
    if row:
        project["error_budget"] = {"target_pct": row["target_pct"],
                                   "remaining_pct": row["budget_remaining_pct"]}
        project["frozen"] = row["frozen"]
    return project
