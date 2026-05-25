from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import requests
from .base import base_project


SUPPORTED = {"ollama", "llama_cpp", "lmstudio", "openai_compatible", "custom"}


def _safe_json_get(url: str, timeout: int = 5) -> tuple[bool, object, int | str, float | str, str | None]:
    try:
        st = datetime.now(timezone.utc)
        r = requests.get(url, timeout=timeout)
        ms = round((datetime.now(timezone.utc) - st).total_seconds() * 1000, 2)
        data = r.json() if "application/json" in r.headers.get("content-type", "") else {}
        ok = 200 <= r.status_code < 300
        err = None if ok else f"http status {r.status_code}"
        return ok, data, r.status_code, ms, err
    except Exception as exc:
        return False, {}, "unknown", "unknown", str(exc)


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    provider = project.get("provider", "unknown")
    base_url = (project.get("base_url") or "").rstrip("/")
    default_model = project.get("default_model", "unknown")

    ai_metrics = {
        "provider": provider,
        "base_url": base_url or "unknown",
        "status": "unknown",
        "default_model": default_model,
        "available_models": [],
        "loaded_model": "unknown",
        "response_time_ms": "unknown",
        "last_health_check_time": datetime.now(timezone.utc).isoformat(),
        "api_version": "unknown",
        "gpu_vram_usage": "unknown",
        "last_error": "unknown",
        "log_file_status": "unknown",
    }

    log_file = project.get("log_file")
    if log_file:
        ai_metrics["log_file_status"] = "present" if Path(log_file).exists() else "missing"

    if provider not in SUPPORTED:
        ai_metrics["status"] = "unknown"
        ai_metrics["last_error"] = f"unsupported provider: {provider}"
        metrics.update(ai_metrics)
        data["metrics"] = metrics
        data["health"] = "unknown"
        return data

    if not base_url and provider != "custom":
        ai_metrics["status"] = "unknown"
        ai_metrics["last_error"] = "base_url missing"
        metrics.update(ai_metrics)
        data["metrics"] = metrics
        data["health"] = "unknown"
        return data

    health_url = project.get("health_url")
    ok, payload, status_code, rt_ms, err = False, {}, "unknown", "unknown", None
    if provider == "ollama":
        endpoint = health_url or f"{base_url}/api/tags"
        ok, payload, status_code, rt_ms, err = _safe_json_get(endpoint)
        if ok:
            ai_metrics["available_models"] = [m.get("name") for m in payload.get("models", []) if isinstance(m, dict) and m.get("name")]
            v_ok, v_payload, _, _, _ = _safe_json_get(f"{base_url}/api/version")
            if v_ok and isinstance(v_payload, dict):
                ai_metrics["api_version"] = v_payload.get("version", "unknown")
    elif provider in {"openai_compatible", "lmstudio"}:
        ok, payload, status_code, rt_ms, err = _safe_json_get(f"{base_url}/v1/models")
        if ok:
            ai_metrics["available_models"] = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")]
    elif provider == "llama_cpp":
        if health_url:
            ok, payload, status_code, rt_ms, err = _safe_json_get(health_url)
        else:
            ok, payload, status_code, rt_ms, err = _safe_json_get(f"{base_url}/health")
            if not ok:
                ok, payload, status_code, rt_ms, err = _safe_json_get(f"{base_url}/v1/models")
                if ok:
                    ai_metrics["available_models"] = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")]
    elif provider == "custom":
        if health_url:
            ok, payload, status_code, rt_ms, err = _safe_json_get(health_url)
        else:
            ai_metrics["status"] = "unknown"
            ai_metrics["last_error"] = "custom provider requires health_url"
            metrics.update(ai_metrics)
            data["metrics"] = metrics
            data["health"] = "unknown"
            return data

    if project.get("test_prompt_enabled") is True and base_url and provider in {"openai_compatible", "lmstudio"}:
        # tiny opt-in prompt test only
        try:
            model = default_model if default_model != "unknown" else (ai_metrics["available_models"][0] if ai_metrics["available_models"] else "")
            requests.post(f"{base_url}/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": project.get("test_prompt", "ping")}], "max_tokens": 1}, timeout=5)
        except Exception:
            pass

    ai_metrics["status"] = "online" if ok else "offline"
    ai_metrics["response_time_ms"] = rt_ms
    if ai_metrics["available_models"]:
        ai_metrics["loaded_model"] = ai_metrics["available_models"][0]
    if err:
        ai_metrics["last_error"] = err

    proc = metrics.get("process", {})
    ai_metrics["process_status"] = "running" if proc.get("running") is True else ("stopped" if proc.get("running") is False else "unknown")
    ai_metrics["pid"] = proc.get("pid", "unknown")
    ai_metrics["cpu_usage"] = proc.get("cpu", "unknown")
    ai_metrics["ram_usage_mb"] = proc.get("ram_mb", "unknown")

    metrics.update(ai_metrics)
    data["metrics"] = metrics
    if ai_metrics["status"] == "offline" or (project.get("expect_running") and proc.get("running") is False):
        data["health"] = "error"
    elif ai_metrics["status"] == "unknown":
        data["health"] = "unknown"
    return data
