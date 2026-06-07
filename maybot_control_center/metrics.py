"""Prometheus metrics exposition (text format, no dependencies).

Exposes the sect + monitoring state at /metrics so it can be scraped into
Grafana. Reads only in-memory snapshots (the last cached overview summary, plus
cultivation / treasury / usage / tool state), so a scrape is cheap and never
triggers a fresh device poll.
"""
from __future__ import annotations

from . import aggregator
from . import agents
from . import cultivation
from . import treasury
from . import usage
from . import tools as tooling
from . import slo
from . import maintenance
from . import errorbudget
from . import oaths
from . import escalation
from . import autopilot


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render() -> str:
    lines: list[str] = []

    def metric(name: str, value, help_text: str, mtype: str = "gauge", labels: str = ""):
        if not any(line == f"# TYPE {name} {mtype}" for line in lines):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {mtype}")
        lines.append(f"{name}{('{' + labels + '}') if labels else ''} {value}")

    # ---- monitoring (last cached overview) ----
    s = aggregator.last_summary()
    for key, name, help_text in [
        ("total_devices", "maybot_devices_total", "Configured devices"),
        ("online_devices", "maybot_devices_online", "Online devices"),
        ("offline_devices", "maybot_devices_offline", "Offline devices"),
        ("total_projects", "maybot_projects_total", "Monitored projects"),
        ("projects_with_warnings_errors", "maybot_projects_unhealthy", "Projects in warning/error"),
        ("bots_running", "maybot_bots_running", "Trading bots running"),
        ("tests_failing", "maybot_tests_failing", "Projects with failing tests"),
        ("local_ai_hosts_online", "maybot_local_ai_online", "Local AI hosts online"),
    ]:
        if key in s:
            metric(name, s[key], help_text)

    # ---- treasury ----
    t = treasury.status()
    metric("maybot_treasury_balance", t["balance"], "Sect treasury balance (spirit stones)")
    metric("maybot_treasury_income_total", t["total_income"], "Spirit stones channelled into the treasury", "counter")
    metric("maybot_treasury_spent_total", t["total_spent"], "Spirit stones disbursed from the treasury", "counter")

    # ---- usage / cost ----
    u = usage.snapshot()["totals"]
    metric("maybot_llm_calls_total", u["calls"], "LLM calls", "counter")
    metric("maybot_llm_tokens_total", u["tokens_in"] + u["tokens_out"], "LLM tokens (in+out)", "counter")
    metric("maybot_llm_cost_usd_total", u["cost"], "Estimated LLM cost (USD)", "counter")

    # ---- guarded tools (audit) ----
    by_status: dict[str, int] = {}
    for c in tooling.list_calls(200):
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    for status, n in sorted(by_status.items()):
        metric("maybot_tool_calls_total", n, "Guarded tool calls by status", "counter", f'status="{_esc(status)}"')

    # ---- cultivation (per agent) ----
    agent_count = 0
    for name, c in cultivation.snapshot().items():
        agent_count += 1
        lbl = f'agent="{_esc(name)}"'
        metric("maybot_agent_realm", c["realm"], "Cultivation realm index (0=Mortal)", "gauge", lbl)
        metric("maybot_agent_spirit_stones", c["stones"], "Spirit stones held by a disciple", "gauge", lbl)
        metric("maybot_agent_breakthroughs", c["breakthroughs"], "Breakthroughs achieved", "counter", lbl)
        metric("maybot_agent_techniques", len(c["skills"]), "Techniques mastered", "gauge", lbl)
    metric("maybot_agents_total", len(agents.load_agents()) or agent_count, "Configured disciples")

    # ---- SLO / uptime (per project) ----
    sl = slo.snapshot()
    for r in sl["projects"]:
        lbl = f'device="{_esc(r["device"])}",project="{_esc(r["project"])}"'
        if r["uptime_pct"] is not None:
            metric("maybot_project_uptime_ratio", round(r["uptime_pct"] / 100.0, 5),
                   "Rolling uptime ratio over the SLO window", "gauge", lbl)
        metric("maybot_project_incidents", r["incidents"],
               "Incidents (ok->unhealthy transitions) in the SLO window", "gauge", lbl)
        if r["mttr_seconds"] is not None:
            metric("maybot_project_mttr_seconds", r["mttr_seconds"],
                   "Mean time to recovery in the SLO window", "gauge", lbl)

    # ---- maintenance silences ----
    metric("maybot_alerts_silenced", len(maintenance.active()), "Active alert silences")

    # ---- error budgets / freeze, ownership, escalation ----
    eb = errorbudget.snapshot()
    metric("maybot_projects_frozen", len(eb["frozen"]),
           "Projects frozen by an exhausted error budget (Heavenly Decree)")
    for r in eb["projects"]:
        if r["budget_remaining_pct"] is not None:
            lbl = f'device="{_esc(r["device"])}",project="{_esc(r["project"])}"'
            metric("maybot_error_budget_remaining_pct", r["budget_remaining_pct"],
                   "Error budget remaining (percent of allowed downtime)", "gauge", lbl)
    metric("maybot_incidents_claimed", len(oaths.snapshot()["oaths"]),
           "Incidents under an active sworn oath (acknowledged)")
    metric("maybot_escalations_pending",
           sum(1 for p in escalation.snapshot()["pending"] if not p["escalated"]),
           "Armed escalations awaiting acknowledgement")

    # ---- autopilot (the second brain) ----
    ap = autopilot.status()
    c = ap.get("counters", {})
    for k in ("fixes", "restarts", "escalations", "recoveries", "proposals"):
        metric(f"maybot_autopilot_{k}_total", c.get(k, 0), f"Autopilot {k} (cumulative)", "counter")
    metric("maybot_autopilot_enabled", 1 if ap.get("enabled") else 0, "Autopilot enabled")
    metric("maybot_autopilot_paused", 1 if ap.get("paused") else 0, "Autopilot kill switch engaged")
    metric("maybot_autopilot_open_incidents",
           sum(1 for i in ap.get("incidents", []) if i.get("state") not in ("recovered",)),
           "Open incidents the autopilot is handling")

    # ---- acknowledgements ----
    from . import acks
    metric("maybot_alerts_acknowledged", len(acks.snapshot()["acks"]),
           "Alerts under an active operator acknowledgement / snooze")

    # ---- control-center self-observability ----
    from . import selfcheck
    sc = selfcheck.snapshot()
    if sc.get("last_poll_age_seconds") is not None:
        metric("maybot_poll_age_seconds", sc["last_poll_age_seconds"],
               "Seconds since the last successful device poll")
    if sc.get("last_poll_duration_ms") is not None:
        metric("maybot_poll_duration_ms", sc["last_poll_duration_ms"],
               "Duration of the last device poll (ms)")
    metric("maybot_poll_stale", 1 if sc.get("poll_stale") else 0,
           "Whether the last poll is older than the staleness threshold")
    metric("maybot_poll_total", sc.get("poll_count", 0), "Device polls completed", "counter")
    metric("maybot_api_requests_total", sc.get("api_requests", 0), "API requests served", "counter")
    metric("maybot_api_errors_total", sc.get("api_errors", 0), "API 5xx responses", "counter")
    metric("maybot_uptime_seconds", sc.get("uptime_seconds", 0), "Control center process uptime")

    return "\n".join(lines) + "\n"
