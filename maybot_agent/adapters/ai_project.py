"""AI-project adapter — domain-aware health for ML training/inference work.

Surfaces the ML lifecycle (phase, model, GPU/VRAM use, epoch/step, loss, eval
score) and scans logs for AI-specific failure modes that the generic ERROR scan
would otherwise lump together — CUDA OOM, NaN/inf loss, and stalled training.

Config (``projects.yaml``) knobs, all optional:
  * ``query_url``    — HTTP(S) endpoint returning JSON. Recognised keys (with
                       aliases): phase/status, model, gpu_util, vram_used_mb,
                       epoch, step, loss, eval_score/score.
  * ``metrics``      — static fallback metrics merged in when nothing is live.

The log scan is heuristic and additive: it raises AI-specific WARN/ERROR alerts
on top of whatever the base adapter already found, then recomputes health.
"""
from __future__ import annotations

from pathlib import Path

from .base import base_project
from ..services.log_reader import read_logs


def _coalesce(d: dict, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _fetch(url: str) -> tuple[bool, dict, str | None]:
    try:
        import requests
        r = requests.get(url, timeout=5)
        payload = r.json() if "application/json" in r.headers.get("content-type", "") else {}
        ok = 200 <= r.status_code < 300
        return ok, (payload if isinstance(payload, dict) else {}), (None if ok else f"http {r.status_code}")
    except Exception as exc:
        return False, {}, str(exc)


# (needle, severity, human label) — scanned case-insensitively in recent logs.
_LOG_SIGNS = [
    ("cuda out of memory", "ERROR", "CUDA out of memory"),
    ("out of memory", "ERROR", "out of memory (OOM)"),
    ("torch.cuda.outofmemoryerror", "ERROR", "CUDA OOM"),
    ("nan loss", "ERROR", "NaN loss"),
    ("loss is nan", "ERROR", "NaN loss"),
    ("loss=inf", "WARNING", "infinite loss"),
    ("gradient overflow", "WARNING", "gradient overflow"),
    ("nan or inf", "WARNING", "NaN/Inf detected"),
]


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    static = project.get("metrics", {}) or {}

    ai = {
        "phase": "unknown",
        "model": "unknown",
        "gpu_util": "unknown",
        "vram_used_mb": "unknown",
        "epoch": "unknown",
        "step": "unknown",
        "loss": "unknown",
        "eval_score": "unknown",
    }

    query_url = project.get("query_url")
    if query_url:
        ok, payload, err = _fetch(query_url)
        if ok:
            ai["phase"] = _coalesce(payload, "phase", "status", "stage") or "unknown"
            ai["model"] = _coalesce(payload, "model", "model_name", "checkpoint") or "unknown"
            ai["gpu_util"] = _coalesce(payload, "gpu_util", "gpu", "gpu_percent")
            ai["vram_used_mb"] = _coalesce(payload, "vram_used_mb", "vram", "gpu_mem_mb")
            ai["epoch"] = _coalesce(payload, "epoch", "epochs")
            ai["step"] = _coalesce(payload, "step", "global_step", "iteration")
            ai["loss"] = _coalesce(payload, "loss", "train_loss")
            ai["eval_score"] = _coalesce(payload, "eval_score", "score", "accuracy", "val_acc")
        else:
            data["alerts"].append(f"WARNING: AI status query failed: {err}")

    # Static fallback for anything not measured live.
    for k in ai:
        if ai[k] in (None, "unknown") and k in static and static[k] is not None:
            ai[k] = static[k]
    for k, v in list(ai.items()):
        if v is None:
            ai[k] = "unknown"

    # AI-specific log scan (in addition to the base ERROR/CRITICAL scan).
    log_file = project.get("log_file")
    seen: set[str] = set()
    if log_file and Path(log_file).exists():
        log = read_logs(log_file, level="ALL", tail=200)
        joined = "\n".join(log.get("lines", [])).lower()
        for needle, sev, label in _LOG_SIGNS:
            if needle in joined and label not in seen:
                seen.add(label)
                data["alerts"].append(f"{sev}: {label} in recent logs")

    metrics.update(ai)
    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
