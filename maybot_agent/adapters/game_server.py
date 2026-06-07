"""Game-server adapter — real, domain-aware health.

Beyond base process/log health, this queries the game's own status surface so
the dashboard shows players online, capacity, current map and tick rate (TPS),
and pages when the server is full, lagging, or unreachable.

Config (``projects.yaml``) knobs, all optional:
  * ``query_url``      — HTTP(S) endpoint returning JSON status. Recognised keys
                         (with common aliases): players/online,
                         max_players/slots/capacity, map, tps/tick_rate, version.
                         Unknown shapes are passed through untouched.
  * ``host`` + ``port``— if set (and no query_url), a raw TCP connect checks
                         whether the server port is accepting connections.
  * ``min_tps``        — warn when tick rate drops below this (default 15.0).
  * ``metrics``        — static fallback metrics merged in when nothing is live.

Degrades gracefully: any network/parse failure becomes an alert, never a raise.
"""
from __future__ import annotations

import socket
import time

from .base import base_project


def _coalesce(d: dict, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _fetch_status(url: str) -> tuple[bool, dict, float | str, str | None]:
    try:
        import requests
        st = time.perf_counter()
        r = requests.get(url, timeout=5)
        ms = round((time.perf_counter() - st) * 1000, 2)
        payload = r.json() if "application/json" in r.headers.get("content-type", "") else {}
        ok = 200 <= r.status_code < 300
        return ok, (payload if isinstance(payload, dict) else {}), ms, (None if ok else f"http {r.status_code}")
    except Exception as exc:
        return False, {}, "unknown", str(exc)


def _tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=5):
            return True
    except Exception:
        return False


def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    static = project.get("metrics", {}) or {}

    try:
        min_tps = float(project.get("min_tps", 15.0))
    except (TypeError, ValueError):
        min_tps = 15.0

    game = {
        "online": "unknown",
        "players": "unknown",
        "max_players": "unknown",
        "map": "unknown",
        "tps": "unknown",
        "version": "unknown",
        "response_time_ms": "unknown",
    }

    query_url = project.get("query_url")
    queried = False
    if query_url:
        ok, payload, ms, err = _fetch_status(query_url)
        queried = True
        game["response_time_ms"] = ms
        if ok:
            game["online"] = True
            players = _coalesce(payload, "players", "online", "player_count", "numplayers")
            mx = _coalesce(payload, "max_players", "maxplayers", "slots", "capacity")
            game["players"] = players if players is not None else "unknown"
            game["max_players"] = mx if mx is not None else "unknown"
            game["map"] = _coalesce(payload, "map", "level", "world") or "unknown"
            tps = _coalesce(payload, "tps", "tick_rate", "ticks")
            game["tps"] = tps if tps is not None else "unknown"
            game["version"] = _coalesce(payload, "version", "ver") or "unknown"
        else:
            game["online"] = False
            data["alerts"].append(f"ERROR: game status query failed: {err}")
    elif project.get("host") and project.get("port"):
        queried = True
        up = _tcp_open(project["host"], project["port"])
        game["online"] = up
        if not up:
            data["alerts"].append(f"ERROR: game port {project['host']}:{project['port']} not accepting connections")

    # Static fallback for anything we couldn't measure live.
    for k in ("players", "max_players", "map", "tps", "version"):
        if game[k] == "unknown" and k in static and static[k] is not None:
            game[k] = static[k]

    # Capacity / lag heuristics (only when we actually have numbers).
    try:
        if isinstance(game["players"], (int, float)) and isinstance(game["max_players"], (int, float)) \
                and game["max_players"] > 0 and game["players"] >= game["max_players"]:
            data["alerts"].append("WARNING: server is full (players at capacity)")
    except Exception:
        pass
    try:
        if isinstance(game["tps"], (int, float)) and game["tps"] < min_tps:
            data["alerts"].append(f"WARNING: low tick rate ({game['tps']} TPS < {min_tps})")
    except Exception:
        pass
    if queried and game["online"] is False and project.get("expect_running") \
            and not any("not accepting" in a or "query failed" in a for a in data["alerts"]):
        data["alerts"].append("ERROR: game server expected online but unreachable")

    metrics.update(game)
    data["metrics"] = metrics
    if any("ERROR" in a for a in data["alerts"]):
        data["health"] = "error"
    elif data["alerts"]:
        data["health"] = "warning"
    return data
