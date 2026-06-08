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
_persisted: list[dict] = []          # in-app rules (editable + persisted), override file rules by name


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


def _all() -> list[dict]:
    """File rules + in-app rules, with in-app rules overriding by name."""
    by_name = {rb["name"]: rb for rb in load_runbooks()}
    for rb in _persisted:
        by_name[rb["name"]] = rb
    return list(by_name.values())


def catalog() -> list[dict]:
    """The effective runbooks (file + in-app) for the API / UI."""
    return _all()


def list_rules() -> list[dict]:
    """The in-app, editable rules only (what the UI manages)."""
    return [dict(r) for r in _persisted]


def save_rule(rb: dict) -> dict:
    """Create or replace (by name) an in-app runbook; persisted."""
    norm = _normalize(rb) if isinstance(rb, dict) else None
    if not norm:
        raise ValueError("a runbook needs a non-empty 'name' and 'tool'")
    global _persisted
    _persisted = [r for r in _persisted if r["name"] != norm["name"]] + [norm]
    _persist()
    return norm


def delete_rule(name: str) -> bool:
    global _persisted
    before = len(_persisted)
    _persisted = [r for r in _persisted if r["name"] != (name or "").strip()]
    if len(_persisted) != before:
        _persist()
        return True
    return False


def _persist() -> None:
    from . import store
    if store.enabled():
        store.save_state("runbooks", {"rules": _persisted})


def load_persisted() -> None:
    global _persisted
    from . import store
    data = store.load_state("runbooks")
    if data and isinstance(data.get("rules"), list):
        _persisted = [r for r in (_normalize(x) for x in data["rules"] if isinstance(x, dict)) if r]


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
    for rb in _all():
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
    """Drop the cached catalog + in-app rules (test isolation)."""
    global _cache, _persisted
    _cache = None
    _persisted = []
