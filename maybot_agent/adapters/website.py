from __future__ import annotations

import time
import requests
from .base import base_project


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    health_url = project.get("health_url")
    if health_url:
        try:
            st = time.perf_counter()
            r = requests.get(health_url, timeout=5)
            ms = round((time.perf_counter() - st) * 1000, 2)
            metrics.update({"online": r.status_code < 500, "status_code": r.status_code, "response_time_ms": ms})
            if r.status_code >= 400:
                data["alerts"].append("WARNING: health check returned 4xx/5xx")
        except Exception as exc:
            metrics.update({"online": False, "status_code": "unknown", "response_time_ms": "unknown"})
            data["alerts"].append(f"ERROR: health check failed: {exc}")
    else:
        metrics.update({"online": "unknown", "status_code": "unknown", "response_time_ms": "unknown"})

    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
