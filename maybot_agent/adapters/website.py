"""Website adapter — HTTP health plus TLS-expiry and content checks.

On top of the basic up/down + status-code + latency probe, this can:
  * assert response time stays under ``max_response_ms`` (warn if slow);
  * assert the body contains an expected marker (``expect_text``) so a page that
    returns 200 but renders an error is still caught;
  * check the TLS certificate's days-to-expiry for ``https`` health URLs and
    warn/error as the cert approaches expiry (``cert_warn_days`` /
    ``cert_error_days``; set ``check_cert: false`` to skip).

All checks are optional and degrade gracefully — any failure becomes an alert,
never a raise.
"""
from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from .base import base_project


def _cert_days_left(host: str, port: int = 443) -> tuple[float | None, str | None]:
    """Days until the server's TLS cert expires (None, err on failure)."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
        not_after = cert.get("notAfter")
        if not not_after:
            return None, "certificate has no notAfter"
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return round((expires - datetime.now(timezone.utc)).total_seconds() / 86400.0, 1), None
    except Exception as exc:
        return None, str(exc)


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

            # Response-time budget.
            max_ms = project.get("max_response_ms")
            try:
                if max_ms is not None and ms > float(max_ms):
                    data["alerts"].append(f"WARNING: slow response {ms}ms (budget {max_ms}ms)")
            except (TypeError, ValueError):
                pass

            # Content assertion: 200 OK but missing expected marker == real failure.
            expect_text = project.get("expect_text")
            if expect_text:
                present = expect_text in (r.text or "")
                metrics["content_ok"] = present
                if not present:
                    data["alerts"].append(f"ERROR: expected content '{expect_text}' not found in response")
        except Exception as exc:
            metrics.update({"online": False, "status_code": "unknown", "response_time_ms": "unknown"})
            data["alerts"].append(f"ERROR: health check failed: {exc}")
    else:
        metrics.update({"online": "unknown", "status_code": "unknown", "response_time_ms": "unknown"})

    # TLS certificate expiry (https only, opt-out with check_cert: false).
    parsed = urlparse(health_url or "")
    if parsed.scheme == "https" and project.get("check_cert", True):
        try:
            warn_days = float(project.get("cert_warn_days", 21))
        except (TypeError, ValueError):
            warn_days = 21.0
        try:
            err_days = float(project.get("cert_error_days", 7))
        except (TypeError, ValueError):
            err_days = 7.0
        days, cert_err = _cert_days_left(parsed.hostname, parsed.port or 443)
        metrics["cert_days_left"] = days if days is not None else "unknown"
        if cert_err is not None:
            data["alerts"].append(f"WARNING: TLS certificate check failed: {cert_err}")
        elif days is not None:
            if days <= err_days:
                data["alerts"].append(f"ERROR: TLS certificate expires in {days} days")
            elif days <= warn_days:
                data["alerts"].append(f"WARNING: TLS certificate expires in {days} days")

    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
