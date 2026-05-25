from .agent_client import call_agent


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
        "projects_with_errors": sum(1 for p in projects if p.get("health") == "error"),
        "bots_running": sum(1 for p in projects if p.get("type") == "trading_bot" and p.get("status") == "running"),
    }
    return {"summary": summary, "devices": device_rows, "projects": projects}
