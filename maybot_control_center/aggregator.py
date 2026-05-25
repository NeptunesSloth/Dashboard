from .agent_client import call_agent


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def aggregate(devices: list[dict]) -> dict:
    device_rows, projects = [], []
    for d in devices:
        ping = call_agent(d, "/api/ping")
        online = bool(ping.get("online"))
        device_rows.append({"name": d.get("name", "unknown"), "online": online, "url": d.get("url", "unknown")})
        if online:
            p = call_agent(d, "/api/projects").get("data", [])
            for pr in p:
                pr["device"] = d.get("name", "unknown")
                projects.append(pr)

    summary = {
        "total_devices": len(device_rows),
        "online_devices": sum(1 for x in device_rows if x["online"]),
        "offline_devices": sum(1 for x in device_rows if not x["online"]),
        "total_projects": len(projects),
        "projects_with_warnings_errors": sum(1 for p in projects if p.get("health") in {"warning", "error"}),
        "bots_running": sum(1 for p in projects if p.get("type") == "trading_bot" and p.get("status") == "running"),
        "total_trading_profit_today": round(sum(_num(p.get("metrics", {}).get("profit_today")) for p in projects if p.get("type") == "trading_bot"), 4),
        "total_trading_profit_this_week": round(sum(_num(p.get("metrics", {}).get("profit_this_week")) for p in projects if p.get("type") == "trading_bot"), 4),
        "total_open_exposure": round(sum(_num(p.get("metrics", {}).get("open_exposure")) for p in projects if p.get("type") == "trading_bot"), 4),
        "tests_failing": sum(1 for p in projects if str(p.get("metrics", {}).get("last_test_result", "")).lower() in {"failed", "error"}),
    }
    return {"summary": summary, "devices": device_rows, "projects": projects}
