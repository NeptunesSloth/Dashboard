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
import time

BUDGET_USD = float(os.getenv("MAYBOT_BUDGET_USD", "0"))            # sect-wide cap (0 = off)
AGENT_CAP = float(os.getenv("MAYBOT_BUDGET_AGENT_USD", "0"))       # per-agent cap (0 = none)
LOW_PCT = float(os.getenv("MAYBOT_BUDGET_LOW_PCT", "20"))          # % remaining that counts as "low"

# ---- hard spend caps (daily / monthly) -------------------------------------
# Additive, OFF BY DEFAULT: with neither set (0), allow_call() always permits and
# no alerts fire — existing behaviour is unchanged. When configured, a fresh LLM
# call is *blocked* once the rolling spend for the period reaches the cap, and an
# alert fires once per threshold per day as spend crosses 80% then 100%.
DAILY_USD = float(os.getenv("MAYBOT_BUDGET_DAILY_USD", "0"))       # rolling 24h cap (0 = off)
MONTHLY_USD = float(os.getenv("MAYBOT_BUDGET_MONTHLY_USD", "0"))   # rolling ~30d cap (0 = off)
WARN_PCT = 80.0                                                    # alert threshold (% of cap)


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


# ---- hard spend caps: rolling-window spend, allow_call(), threshold alerts ---
_DAY = 24 * 3600
_caps_lock = threading.Lock()
# (cap-kind, threshold-pct) -> day-epoch the alert last fired on. De-dupes alerts
# to once per threshold per UTC day, like the repo's other daily notifiers.
_cap_alerted: dict[tuple[str, int], int] = {}


def _series(hours: int) -> dict:
    from . import usage
    return usage.series(hours)


def _window_spend(hours: int) -> float:
    """USD spent over roughly the last ``hours`` hours, from the usage cost series.
    Reuses usage's per-model pricing — no pricing is reinvented here."""
    try:
        return round(float(_series(hours)["totals"]["cost"]), 6)
    except Exception:
        return 0.0


def daily_spend() -> float:
    return _window_spend(24)


def monthly_spend() -> float:
    # usage keeps up to two weeks of hourly buckets; sum all we have for the month.
    return _window_spend(24 * 30)


def _cap_state(kind: str, cap: float, spent: float) -> dict:
    """State for one configured cap (daily/monthly)."""
    if cap <= 0:
        return {"kind": kind, "enabled": False, "cap": 0.0, "spent": round(spent, 4),
                "remaining": 0.0, "pct_used": 0.0, "paused": False}
    remaining = max(0.0, round(cap - spent, 4))
    pct = round(100.0 * spent / cap, 1)
    return {"kind": kind, "enabled": True, "cap": round(cap, 4), "spent": round(spent, 4),
            "remaining": remaining, "pct_used": pct, "paused": spent >= cap}


def caps() -> dict:
    """Current daily/monthly hard-cap state (off by default)."""
    return {"daily": _cap_state("daily", DAILY_USD, daily_spend()),
            "monthly": _cap_state("monthly", MONTHLY_USD, monthly_spend())}


def _cap_alert(kind: str, st: dict) -> None:
    """Fire an alert once per crossed threshold (80%, 100%) per UTC day. Best-effort."""
    if not st["enabled"]:
        return
    today = int(time.time()) // _DAY
    for thresh in (100, int(WARN_PCT)):
        if st["pct_used"] < thresh:
            continue
        key = (kind, thresh)
        with _caps_lock:
            if _cap_alerted.get(key) == today:
                continue
            _cap_alerted[key] = today
        level = "critical" if thresh >= 100 else "warn"
        verb = "reached — calls paused" if thresh >= 100 else "warning"
        try:
            from . import notify
            notify.send(
                f"{kind.capitalize()} LLM budget {verb}",
                f"${st['spent']} of ${st['cap']} {kind} cap used ({st['pct_used']}%).",
                level=level, kind="budget")
        except Exception:
            pass
        break  # only the highest crossed threshold this pass


def reset_caps() -> None:
    """Test/ops helper: clear the once-per-day cap-alert de-dupe state."""
    with _caps_lock:
        _cap_alerted.clear()


def allow_call(agent_name: str | None = None) -> tuple[bool, str | None]:
    """Whether a new LLM call is permitted under the configured hard spend caps.

    Returns ``(True, None)`` when permitted (always, if no cap is configured), or
    ``(False, reason)`` when a daily/monthly cap has been reached. Crossing a
    threshold also fires an alert (once per threshold per day, best-effort).
    """
    c = caps()
    denied: str | None = None
    for kind in ("daily", "monthly"):
        st = c[kind]
        if not st["enabled"]:
            continue
        _cap_alert(kind, st)
        if st["paused"] and denied is None:
            denied = (f"{kind} LLM budget reached (${st['spent']}/${st['cap']}) — calls paused")
    if denied is not None:
        return False, denied
    return True, None


def snapshot() -> dict:
    r = reserves()
    check_alert()
    rows = []
    for a in _usage()["agents"]:
        rows.append({"agent": a["agent"], "cost": round(a["cost"], 4),
                     "tokens": a["tokens_in"] + a["tokens_out"], "status": status(a["agent"])})
    return {"reserves": r, "agent_cap": round(AGENT_CAP, 4), "low_pct": LOW_PCT,
            "caps": caps(), "agents": rows}
