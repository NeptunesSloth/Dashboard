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

    return "\n".join(lines) + "\n"
