"""Formations — reusable multi-agent workflows (a "formation array").

A *formation* is a named DAG of stages run in order: e.g.
``scout → analyze → propose → review``. Each stage names a role; one disciple
fills it and sees the goal plus every prior stage's output, then contributes
its part. Under the cultivation costume this is just a reusable multi-agent
pipeline — today the council only runs ad-hoc debates/missions, so a saved,
repeatable scout→analyze→propose→review array is the real value.

The catalog is loaded from ``formations.yaml`` (override with
``MAYBOT_FORMATIONS_FILE``); a small built-in default is used if no file
exists, so the feature works out of the box.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

FORMATIONS_FILE = Path(os.getenv("MAYBOT_FORMATIONS_FILE", "formations.yaml"))
MAX_STAGES = max(1, int(os.getenv("MAYBOT_FORMATION_MAX_STAGES", "8")))

# Built-in fallback so the feature is usable without any config file.
_DEFAULT = [
    {
        "name": "recon-array",
        "title": "Recon Array",
        "description": "Scout a target, analyze the findings, propose action, then review it.",
        "stages": [
            {"name": "scout", "role": "Gather the relevant facts and surface the key signals about the goal."},
            {"name": "analyze", "role": "Interpret the scout's findings; name the risks, causes and opportunities."},
            {"name": "propose", "role": "Draft a concrete, actionable plan addressing the analysis."},
            {"name": "review", "role": "Critique the proposal for flaws and give a clear go / no-go verdict."},
        ],
    },
    {
        "name": "triage-array",
        "title": "Triage Array",
        "description": "Diagnose an incident, propose a remediation, and sanity-check it.",
        "stages": [
            {"name": "diagnose", "role": "Establish what is wrong and the most likely root cause."},
            {"name": "remediate", "role": "Propose the safest concrete fix and the steps to apply it."},
            {"name": "verify", "role": "Check the fix for side effects and state how to confirm success."},
        ],
    },
]


def _normalize(form: dict) -> dict | None:
    name = (form.get("name") or "").strip()
    raw_stages = form.get("stages") or []
    if not name or not isinstance(raw_stages, list):
        return None
    stages = []
    for s in raw_stages[:MAX_STAGES]:
        sname = (s.get("name") or "").strip()
        if not sname:
            continue
        stage = {"name": sname, "role": (s.get("role") or "").strip()}
        agent = (s.get("agent") or "").strip()
        if agent:
            stage["agent"] = agent
        stages.append(stage)
    if not stages:
        return None
    return {
        "name": name,
        "title": (form.get("title") or name).strip(),
        "description": (form.get("description") or "").strip(),
        "stages": stages,
    }


def load_formations() -> list[dict]:
    raw = _DEFAULT
    if FORMATIONS_FILE.exists():
        with FORMATIONS_FILE.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        items = data.get("formations")
        if isinstance(items, list) and items:
            raw = items
    out = []
    for form in raw:
        norm = _normalize(form) if isinstance(form, dict) else None
        if norm:
            out.append(norm)
    return out


def catalog() -> list[dict]:
    """The list of available formations (for the API / UI)."""
    return load_formations()


def get(name: str) -> dict | None:
    return next((f for f in load_formations() if f["name"] == name), None)
