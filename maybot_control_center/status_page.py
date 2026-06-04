"""Public status page — the "Sect Proclamation".

An opt-in, unauthenticated, read-only summary of service health and uptime for
stakeholders who shouldn't have a dashboard token. Derived from the SLO/uptime
data; exposes only service names + state + uptime%, never device URLs, tokens,
costs, or agent internals.

Enable with ``MAYBOT_PUBLIC_STATUS=1`` (off by default — a public page can leak
service names). Served at ``GET /status`` (HTML) and ``GET /api/status/public``.
"""
from __future__ import annotations

import html
import os

from . import slo, aggregator

TITLE = os.getenv("MAYBOT_STATUS_TITLE", "Service Status")


def enabled() -> bool:
    return os.getenv("MAYBOT_PUBLIC_STATUS", "0").strip().lower() in {"1", "true", "yes", "on"}


def public_data() -> dict:
    rows = []
    for r in slo.snapshot()["projects"]:
        rows.append({"service": r["project"], "state": r["current"],
                     "uptime_pct": r["uptime_pct"]})
    rows.sort(key=lambda x: x["service"].lower())
    summary = aggregator.last_summary()
    unhealthy = sum(1 for r in rows if r["state"] not in {"ok", "unknown"})
    overall = "operational" if unhealthy == 0 else ("degraded" if unhealthy < max(1, len(rows)) else "major outage")
    return {"title": TITLE, "overall": overall, "services": rows,
            "online_devices": summary.get("online_devices", 0),
            "offline_devices": summary.get("offline_devices", 0)}


_DOT = {"ok": "#3fb950", "warning": "#d29922", "error": "#f85149", "unknown": "#8b949e"}


def render_html() -> str:
    d = public_data()
    overall_color = {"operational": "#3fb950", "degraded": "#d29922", "major outage": "#f85149"}[d["overall"]]
    rows = []
    for s in d["services"]:
        color = _DOT.get(s["state"], "#8b949e")
        up = "—" if s["uptime_pct"] is None else f"{s['uptime_pct']:.2f}%"
        rows.append(
            f"<tr><td><span class='dot' style='background:{color}'></span>{html.escape(s['service'])}</td>"
            f"<td class='state'>{html.escape(s['state'])}</td><td class='up'>{up}</td></tr>")
    body = "\n".join(rows) or "<tr><td colspan='3' class='muted'>No services reporting yet.</td></tr>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(d['title'])}</title>
<style>
 body {{ font-family: system-ui, sans-serif; background:#0d1117; color:#e6edf3; margin:0; padding:32px; }}
 .wrap {{ max-width:720px; margin:0 auto; }}
 h1 {{ font-size:22px; margin:0 0 4px; }}
 .overall {{ display:inline-block; padding:6px 12px; border-radius:16px; font-weight:600;
   color:#0d1117; background:{overall_color}; margin:12px 0 20px; }}
 table {{ width:100%; border-collapse:collapse; }}
 td {{ padding:12px 8px; border-bottom:1px solid #21262d; }}
 .state {{ text-transform:capitalize; color:#8b949e; }}
 .up {{ text-align:right; font-variant-numeric:tabular-nums; }}
 .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:10px; vertical-align:middle; }}
 .muted {{ color:#8b949e; text-align:center; }}
 .foot {{ color:#8b949e; font-size:12px; margin-top:18px; }}
</style></head><body><div class="wrap">
<h1>{html.escape(d['title'])}</h1>
<div class="overall">{html.escape(d['overall'].title())}</div>
<table><tbody>
{body}
</tbody></table>
<div class="foot">{d['online_devices']} sources online · {d['offline_devices']} offline</div>
</div></body></html>"""
