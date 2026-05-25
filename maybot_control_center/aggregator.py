from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from .agent_client import call_agent
from .notifier import check_and_notify


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _fetch_device(d: dict) -> tuple[dict, list[dict]]:
    ping = call_agent(d, "/api/ping")
    online = bool(ping.get("online"))
    device_row = {
        "name": d.get("name", "unknown"),
        "online": online,
        "auth_error": bool(ping.get("auth_error")),
        "status_code": ping.get("status_code", "unknown"),
        "error": ping.get("error"),
        "url": d.get("url", "unknown"),
    }
    projects: list[dict] = []
    if online:
        p = call_agent(d, "/api/projects").get("data", [])
        if isinstance(p, list):
            for pr in p:
                pr["device"] = d.get("name", "unknown")
                projects.append(pr)
    return device_row, projects


def aggregate(devices: list[dict]) -> dict:
    device_rows: list[dict] = []
    projects: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(len(devices), 16) or 1) as pool:
        for device_row, device_projects in pool.map(_fetch_device, devices):
            device_rows.append(device_row)
            projects.extend(device_projects)

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
        "local_ai_hosts_total": sum(1 for p in projects if p.get("type") == "local_ai_host"),
        "local_ai_hosts_online": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("metrics", {}).get("status") == "online"),
        "local_ai_hosts_offline": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("metrics", {}).get("status") == "offline"),
        "local_ai_hosts_with_errors": sum(1 for p in projects if p.get("type") == "local_ai_host" and p.get("health") in {"warning", "error"}),
    }
    check_and_notify(projects)
    return {"summary": summary, "devices": device_rows, "projects": projects}
