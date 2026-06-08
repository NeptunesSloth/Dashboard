"""Best-effort auto-discovery of bots/services running on this host.

Returns *candidate* project dicts (same shape as ``projects.yaml`` entries) for
the operator to review and accept in the dashboard — it never writes config on
its own. Heuristic by design: it scans processes (and Docker containers, if
present) and guesses a sensible ``type`` + match field.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import psutil

# Substring hints (lowercased) -> suggested project type.
_TYPE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("tradebot", "trade", "freqtrade", "hummingbot", "binance", "ccxt"), "trading_bot"),
    (("ollama", "vllm", "llama.cpp", "text-generation", "lmstudio"), "local_ai_host"),
    (("uvicorn", "gunicorn", "flask", "django", "fastapi", "next", "express"), "website"),
    (("minecraft", "valheim", "factorio", "gameserver", "pufferpanel"), "game_server"),
]

# Never propose our own services or obvious system noise.
_IGNORE = (
    "maybot_agent", "maybot_control_center", "uvicorn maybot_agent",
    "/usr/lib/systemd", "sshd", "-bash", "/bin/bash", "/bin/sh",
)

_APP_PROCS = {"python", "python3", "node", "java", "ollama", "uvicorn", "gunicorn", "deno", "bun"}


def _guess_type(text: str) -> str:
    low = text.lower()
    for keys, t in _TYPE_HINTS:
        if any(k in low for k in keys):
            return t
    return "generic"


def _match_token(cmd: str, fallback: str) -> str:
    """A stable, non-path word from the cmdline to use as ``cmdline_contains``."""
    for w in cmd.split():
        if len(w) > 3 and "/" not in w and not w.startswith("-"):
            return w
    return fallback


def _proc_candidates() -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            info = proc.info
            cmd = " ".join(info.get("cmdline") or []).strip()
            if not cmd or any(ig in cmd for ig in _IGNORE):
                continue
            name = (info.get("name") or "").lower()
            guessed = _guess_type(cmd)
            # Keep app-like processes, or anything with a strong type keyword.
            if name not in _APP_PROCS and "python" not in name and guessed == "generic":
                continue
            cwd = info.get("cwd") or ""
            key = (name, cwd, cmd[:80])
            if key in seen:
                continue
            seen.add(key)
            token = _match_token(cmd, name or "bot")
            out.append({
                "name": (os.path.basename(cwd) if cwd else "") or token or name,
                "type": guessed,
                "path": cwd or None,
                "cmdline_contains": token,
                "expect_running": True,
                "_source": "process",
                "_detail": cmd[:200],
            })
        except Exception:
            continue
    return out[:50]


def _docker_candidates() -> list[dict]:
    if not shutil.which("docker"):
        return []
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return []
    out: list[dict] = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        cname = parts[0].strip() if parts else ""
        if not cname:
            continue
        image = parts[1].strip() if len(parts) > 1 else ""
        out.append({
            "name": cname,
            "type": _guess_type(f"{cname} {image}"),
            "cmdline_contains": cname,
            "expect_running": True,
            "_source": "docker",
            "_detail": image,
        })
    return out


def discover_candidates() -> list[dict]:
    """All discovery candidates from every available source."""
    return _proc_candidates() + _docker_candidates()
