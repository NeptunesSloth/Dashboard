"""Sect-wide cost governance — the "qi reserves".

Turns the trust tiers into real cost control. A sect-wide USD budget
(``MAYBOT_BUDGET_USD``) is drawn down by LLM spend (from :mod:`usage`). As the
reserves run low, autonomous tool-runs are cut off **low-merit first**:

  - reserves healthy (>= ``MAYBOT_BUDGET_LOW_PCT`` remaining): no budget throttle
  - low (< low%):            Probation disciples are cut off
  - critical (< low%/2):     Standard disciples are cut off too — only Trusted act
  - exhausted (<= $0):       all autonomous runs blocked (operator unaffected)

An optional per-agent cap (``MAYBOT_BUDGET_AGENT_USD``) caps any single disciple.
Budget off (``MAYBOT_BUDGET_USD`` <= 0, the default) → never throttles; the gauge
just shows spend. Operator-initiated work is never throttled.
"""
from __future__ import annotations

import os
import threading

BUDGET_USD = float(os.getenv("MAYBOT_BUDGET_USD", "0"))            # sect-wide cap (0 = off)
AGENT_CAP = float(os.getenv("MAYBOT_BUDGET_AGENT_USD", "0"))       # per-agent cap (0 = none)
LOW_PCT = float(os.getenv("MAYBOT_BUDGET_LOW_PCT", "20"))          # % remaining that counts as "low"


def _usage():
    from . import usage
    return usage.snapshot()


def reserves() -> dict:
    """Sect-wide budget state."""
    spent = round(_usage()["totals"]["cost"], 4)
    if BUDGET_USD <= 0:
        return {"enabled": False, "budget": 0.0, "spent": spent, "remaining": 0.0,
                "pct_remaining": 100.0, "low": False, "critical": False, "exhausted": False}
    remaining = max(0.0, round(BUDGET_USD - spent, 4))
    pct = round(100.0 * remaining / BUDGET_USD, 1)
    return {"enabled": True, "budget": round(BUDGET_USD, 4), "spent": spent, "remaining": remaining,
            "pct_remaining": pct, "low": pct < LOW_PCT, "critical": pct < LOW_PCT / 2,
            "exhausted": remaining <= 0}


def agent_spend(agent: str) -> float:
    row = next((r for r in _usage()["agents"] if r["agent"] == agent), None)
    return round(row["cost"], 4) if row else 0.0


def allowed(agent: str) -> bool:
    """May this disciple run autonomous tools under the current reserves?"""
    if agent == "operator":
        return True
    if AGENT_CAP > 0 and agent_spend(agent) >= AGENT_CAP:
        return False
    r = reserves()
    if not r["enabled"]:
        return True
    if r["exhausted"]:
        return False
    if not r["low"]:
        return True
    # reserves are low — keep only the more trusted disciples acting
    from . import reputation
    tier = reputation.tier(agent)
    if tier == "Trusted":
        return True
    if tier == "Standard":
        return not r["critical"]   # Standard cut once critical
    return False                   # Probation cut as soon as low


def status(agent: str) -> str:
    """A short throttle label for one agent (for the UI)."""
    if AGENT_CAP > 0 and agent_spend(agent) >= AGENT_CAP:
        return "capped"
    return "ok" if allowed(agent) else "throttled"


# ---- budget-breach alerting (fires once per worsening transition) -----------
_RANK = {"healthy": 0, "low": 1, "critical": 2, "exhausted": 3}
_alert_lock = threading.Lock()
_alert_level = "healthy"


def _level(r: dict) -> str:
    if not r.get("enabled"):
        return "healthy"
    if r["exhausted"]:
        return "exhausted"
    if r["critical"]:
        return "critical"
    if r["low"]:
        return "low"
    return "healthy"


def check_alert() -> str | None:
    """Fire a webhook alert when reserves cross into a worse budget level. Called
    from snapshot(). Returns the new level when an alert fired, else None."""
    global _alert_level
    r = reserves()
    lvl = _level(r)
    with _alert_lock:
        prev = _alert_level
        if _RANK[lvl] <= _RANK[prev]:   # unchanged or recovering — no alert
            _alert_level = lvl
            return None
        _alert_level = lvl
    try:
        from . import notifier
        notifier.notify_event(
            "budget", f"Sect reserves {lvl}",
            f"{r['pct_remaining']}% of the ${r['budget']} budget remains (${r['remaining']} left).")
    except Exception:
        pass
    return lvl


def reset_alert() -> None:
    global _alert_level
    with _alert_lock:
        _alert_level = "healthy"


def snapshot() -> dict:
    r = reserves()
    check_alert()
    rows = []
    for a in _usage()["agents"]:
        rows.append({"agent": a["agent"], "cost": round(a["cost"], 4),
                     "tokens": a["tokens_in"] + a["tokens_out"], "status": status(a["agent"])})
    return {"reserves": r, "agent_cap": round(AGENT_CAP, 4), "low_pct": LOW_PCT, "agents": rows}
