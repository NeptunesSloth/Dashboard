"""Dependency-aware alerting — the "Meridian Map".

Qi flows between connected projects along *meridians*: a service depends on the
ones upstream of it. Declare those links in ``meridians.yaml`` and when an
**upstream** is unhealthy, a downstream's own ``error`` is recognised as a
*blocked meridian* — likely a downstream symptom, not a separate fault. The
root cause gets paged; the downstream page is suppressed (`MAYBOT_MERIDIAN_SUPPRESS`).

``meridians.yaml`` (see meridians.yaml.example)::

    meridians:
      - project: prod-1:Dashboard
        depends_on: [prod-1:api-gateway, prod-1:TradeBot]

No file → no dependencies declared, and everything alerts independently as before.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

MERIDIANS_FILE = Path(os.getenv("MAYBOT_MERIDIANS_FILE", "meridians.yaml"))
SUPPRESS = os.getenv("MAYBOT_MERIDIAN_SUPPRESS", "1").strip().lower() not in {"0", "false", "no", ""}

_UNHEALTHY = {"warning", "error"}


def load_map() -> dict[str, list[str]]:
    """downstream key -> list of upstream keys it depends on."""
    if not MERIDIANS_FILE.exists():
        return {}
    data = yaml.safe_load(MERIDIANS_FILE.read_text(encoding="utf-8")) or {}
    out: dict[str, list[str]] = {}
    for entry in data.get("meridians", []) or []:
        if not isinstance(entry, dict):
            continue
        proj = entry.get("project")
        ups = entry.get("depends_on") or []
        if proj and isinstance(ups, list):
            out.setdefault(proj, [])
            for u in ups:
                if u and u not in out[proj]:
                    out[proj].append(u)
    return out


def blocked_upstreams(key: str, health_by_key: dict[str, str]) -> list[str]:
    """Upstreams of ``key`` that are themselves currently unhealthy."""
    ups = load_map().get(key, [])
    return [u for u in ups if str(health_by_key.get(u, "")).lower() in _UNHEALTHY]


def annotate(project: dict, health_by_key: dict[str, str]) -> dict:
    """If this project is unhealthy *and* has an unhealthy upstream, tag it."""
    key = f"{project.get('device', '?')}:{project.get('name', '?')}"
    if str(project.get("health", "")).lower() in _UNHEALTHY:
        blocked = blocked_upstreams(key, health_by_key)
        if blocked:
            project["blocked_by"] = blocked
    return project


def graph() -> dict:
    return {"meridians": load_map(), "suppress": SUPPRESS}
