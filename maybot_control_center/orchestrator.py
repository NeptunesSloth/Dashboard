"""NL orchestrator — decompose a high-level goal into routed subtasks.

Describe a goal in plain language; a *planner* disciple (``MAYBOT_ORCHESTRATOR_AGENT``,
or the Sect Leader, else a heuristic) breaks it into concrete subtasks. Each
subtask is auto-routed to the best-fit disciple (:mod:`routing`), enqueued on the
board (:mod:`taskqueue`) under a parent goal, and dispatched.

The LLM step is optional and isolated in :func:`_plan_llm` (monkeypatchable);
when no model is configured or planning fails, a deterministic heuristic split
keeps the feature working.
"""
from __future__ import annotations

import json
import os
import re

MAX_SUBTASKS = max(1, int(os.getenv("MAYBOT_ORCHESTRATOR_MAX", "6")))

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def _planner() -> str | None:
    name = os.getenv("MAYBOT_ORCHESTRATOR_AGENT", "").strip()
    if name:
        return name
    try:
        from . import governance
        return governance.leader()
    except Exception:
        return None


def _plan_llm(goal: str, max_subtasks: int) -> list[dict] | None:
    """Ask the planner disciple for a JSON array of subtasks. None on any failure."""
    planner = _planner()
    if not planner:
        return None
    from . import agents
    agent = agents._agent_def(planner)
    if not agent:
        return None
    sys = ("You are a project planner. Break the user's goal into a short ordered list of "
           f"concrete, independently-assignable subtasks (max {max_subtasks}). Reply with ONLY a "
           'JSON array of objects: [{"title": "...", "description": "..."}]. No prose.')
    try:
        ok, text, _ = agents._chat(agent, [{"role": "system", "content": sys},
                                           {"role": "user", "content": goal}])
    except Exception:
        return None
    if not ok or not text:
        return None
    m = _JSON_ARRAY.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and item.get("title"):
            out.append({"title": str(item["title"])[:200], "description": str(item.get("description", ""))[:2000]})
    return out[:max_subtasks] or None


def _heuristic(goal: str, max_subtasks: int) -> list[dict]:
    """Deterministic fallback: split on connectives / lines / sentences."""
    goal = (goal or "").strip()
    parts = re.split(r"\s*(?:;|\n|\band then\b|\bthen\b|\band\b|,)\s*", goal)
    parts = [p.strip() for p in parts if len(p.strip()) > 3]
    if len(parts) <= 1:
        return [{"title": goal[:200], "description": ""}]
    return [{"title": p[:200], "description": ""} for p in parts[:max_subtasks]]


def decompose(goal: str, max_subtasks: int | None = None) -> list[dict]:
    n = MAX_SUBTASKS if max_subtasks is None else max(1, min(int(max_subtasks), 20))
    return _plan_llm(goal, n) or _heuristic(goal, n)


def orchestrate(goal: str, max_subtasks: int | None = None, dispatch: bool = True) -> dict:
    """Decompose a goal, route + enqueue each subtask, and (optionally) dispatch."""
    from . import taskqueue, routing, agents, governance
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal required")
    parent = taskqueue.create(goal, source="orchestrator")
    subs = decompose(goal, max_subtasks)
    results = []
    for sub in subs:
        text = sub["title"] + ((" — " + sub["description"]) if sub["description"] else "")
        fit = routing.best_fit(text)
        assignee = fit["agent"] if fit else None
        task = taskqueue.create(sub["title"], description=sub["description"], source="orchestrator",
                                parent_id=parent["id"], assignee=assignee)
        if dispatch and assignee:
            # The Sect Leader oversees: routine work flows to a deputy Elder.
            executor, _ = governance.route_task(assignee, critical=False)
            try:
                agents.assign_task(executor, text)
                taskqueue.link_dispatch(task["id"], executor)
                task = taskqueue.get(task["id"])
            except KeyError:
                pass
        results.append({"task": task, "routed_to": assignee,
                        "reason": fit["reason"] if fit else "no eligible disciple"})
    return {"parent": parent, "subtasks": results}
