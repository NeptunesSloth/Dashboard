"""Auto-remediation runbooks — automated incident response.

A *runbook* pairs a match-spec with a guarded tool: when a project / incident
matches the rule (by type, health, name glob, or alert substring), the runbook
*requests* the named tool to remediate it. Requesting goes through the existing
guarded-tools layer (``tools.request_tool``), so the dashboard's approval /
autonomy guards still decide whether the action actually runs — runbooks never
bypass them, they just wire a condition to a remediation.

The catalog is loaded from ``runbooks.yaml`` (override with
``MAYBOT_RUNBOOKS_FILE``). No file → no runbooks, and the feature is simply off.
"""
from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path

import yaml

RUNBOOKS_FILE = Path(os.getenv("MAYBOT_RUNBOOKS_FILE", "runbooks.yaml"))

_cache: list[dict] | None = None


def _normalize(rb: dict) -> dict | None:
    name = (rb.get("name") or "").strip()
    tool = (rb.get("tool") or "").strip()
    if not name or not tool:
        return None
    match_spec = rb.get("match")
    if not isinstance(match_spec, dict):
        match_spec = {}
    args = rb.get("args")
    if not isinstance(args, dict):
        args = {}
    requester = (rb.get("requester") or "operator").strip() or "operator"
    return {
        "name": name,
        "match": match_spec,
        "tool": tool,
        "args": args,
        "requester": requester,
        "auto": bool(rb.get("auto", False)),
    }


def load_runbooks() -> list[dict]:
    """Read + normalize the runbook catalog (cached). Missing file → []."""
    global _cache
    if _cache is not None:
        return _cache
    out: list[dict] = []
    if RUNBOOKS_FILE.exists():
        with RUNBOOKS_FILE.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        items = data.get("runbooks")
        if isinstance(items, list):
            for rb in items:
                norm = _normalize(rb) if isinstance(rb, dict) else None
                if norm:
                    out.append(norm)
    _cache = out
    return _cache


def catalog() -> list[dict]:
    """The loaded runbooks (for the API / UI)."""
    return load_runbooks()


def _matches(spec: dict, project: dict) -> bool:
    if "type" in spec and project.get("type") != spec["type"]:
        return False
    if "health" in spec and project.get("health") != spec["health"]:
        return False
    if "name_pattern" in spec and not fnmatch(
        str(project.get("name", "")), str(spec["name_pattern"])
    ):
        return False
    if "alert_contains" in spec:
        needle = spec["alert_contains"]
        alerts = project.get("alerts") or []
        if not any(isinstance(a, str) and needle in a for a in alerts):
            return False
    return True


def match(project: dict) -> dict | None:
    """First runbook whose match-spec matches the given project, else None."""
    for rb in load_runbooks():
        if _matches(rb["match"], project):
            return rb
    return None


def _render_args(args: dict, project: dict) -> dict:
    """Substitute ``{name}``/``{device}``/``{type}`` in string arg values."""
    mapping = _SafeMap(
        {
            "name": project.get("name", ""),
            "device": project.get("device", ""),
            "type": project.get("type", ""),
        }
    )
    rendered: dict = {}
    for key, value in args.items():
        if isinstance(value, str):
            rendered[key] = value.format_map(mapping)
        else:
            rendered[key] = value
    return rendered


class _SafeMap(dict):
    """Leaves unknown ``{placeholder}`` tokens untouched during formatting."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def dispatch(project: dict) -> dict | None:
    """Find a matching runbook and request its remediation tool.

    Returns None if no runbook matches or guarded tools are disabled. On a
    successful request returns a wrapper dict; if ``request_tool`` rejects the
    call (unknown tool) the ValueError is wrapped into an ``error`` field.
    """
    from . import tools  # lazy import of sibling

    rb = match(project)
    if rb is None or not tools.enabled():
        return None
    rendered = _render_args(rb["args"], project)
    try:
        result = tools.request_tool(rb["requester"], rb["tool"], rendered)
    except ValueError as exc:
        return {"runbook": rb["name"], "error": str(exc)}
    return {
        "runbook": rb["name"],
        "tool": rb["tool"],
        "requested": result,
        "auto": rb["auto"],
    }


def clear() -> None:
    """Drop the cached catalog."""
    global _cache
    _cache = None
