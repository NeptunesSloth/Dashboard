"""Task board / work queue for disciples.

Turns fire-and-forget ``assign_task`` into a tracked backlog: every task is an
item with a **status** (queued → assigned → in_progress → done/failed), a
**priority**, an **assignee**, a **source** (manual / goal / orchestrator) and an
optional **parent** (so an orchestrated goal's subtasks group under it).

When a task is dispatched it links to the disciple's live run; ``run_task``
reports completion back here (:func:`on_agent_finished`) so the board reflects
real progress. State is in-memory (a coordination aid), like the rest of the
runtime state.
"""
from __future__ import annotations

import threading
import time

from . import events

PRIORITIES = ["low", "normal", "high", "urgent"]
_PRIO_RANK = {p: i for i, p in enumerate(PRIORITIES)}
ACTIVE = {"queued", "assigned", "in_progress"}

_lock = threading.Lock()
_tasks: dict[int, dict] = {}
_seq = 0
_current_by_agent: dict[str, int] = {}   # agent -> task id it is currently running


def _now() -> int:
    return int(time.time() * 1000)


def create(title: str, *, description: str = "", priority: str = "normal",
           assignee: str | None = None, source: str = "manual",
           parent_id: int | None = None, project: str | None = None,
           device: str | None = None, repo: str | None = None,
           issue: int | None = None) -> dict:
    global _seq
    if priority not in _PRIO_RANK:
        priority = "normal"
    with _lock:
        _seq += 1
        task = {
            "id": _seq, "title": title.strip()[:200], "description": description.strip()[:4000],
            "priority": priority, "assignee": assignee, "status": "assigned" if assignee else "queued",
            "source": source, "parent_id": parent_id, "project": project, "device": device,
            "repo": repo, "issue": issue, "result": None,
            "created_at": _now(), "updated_at": _now(),
        }
        _tasks[task["id"]] = task
        snap = dict(task)
    events.publish("tasks", {"id": snap["id"]})
    _save()
    return snap


def get(task_id: int) -> dict | None:
    with _lock:
        t = _tasks.get(task_id)
        return dict(t) if t else None


def update(task_id: int, **fields) -> dict | None:
    with _lock:
        t = _tasks.get(task_id)
        if not t:
            return None
        for k, v in fields.items():
            if k in t:
                t[k] = v
        t["updated_at"] = _now()
        snap = dict(t)
    events.publish("tasks", {"id": task_id})
    _save()
    return snap


def reassign(task_id: int, assignee: str) -> dict | None:
    return update(task_id, assignee=assignee, status="assigned")


def set_status(task_id: int, status: str, result: str | None = None) -> dict | None:
    fields = {"status": status}
    if result is not None:
        fields["result"] = result.strip()[:1000]
    return update(task_id, **fields)


def cancel(task_id: int) -> dict | None:
    return set_status(task_id, "cancelled")


def active_count(assignee: str) -> int:
    """How many active (queued/assigned/in_progress) tasks a disciple holds — its load."""
    with _lock:
        return sum(1 for t in _tasks.values() if t["assignee"] == assignee and t["status"] in ACTIVE)


def link_dispatch(task_id: int, agent: str) -> None:
    """Mark a task as the disciple's currently-running work."""
    with _lock:
        _current_by_agent[agent] = task_id
        t = _tasks.get(task_id)
        if t:
            t["assignee"] = agent
            t["status"] = "in_progress"
            t["updated_at"] = _now()
    events.publish("tasks", {"id": task_id})
    _save()


def on_agent_finished(agent: str, ok: bool, reply: str = "") -> None:
    """Called from agents.run_task when a disciple finishes its current task."""
    with _lock:
        task_id = _current_by_agent.pop(agent, None)
        t = _tasks.get(task_id) if task_id is not None else None
        if not t or t["status"] not in ACTIVE:
            return
        t["status"] = "done" if ok else "failed"
        t["result"] = (reply or "")[:1000]
        t["updated_at"] = _now()
    events.publish("tasks", {"id": task_id})
    _save()


def list_tasks(status: str | None = None, assignee: str | None = None, limit: int = 200) -> list[dict]:
    with _lock:
        rows = [dict(t) for t in _tasks.values()
                if (status is None or t["status"] == status)
                and (assignee is None or t["assignee"] == assignee)]
    # active first (by priority then age), then finished (newest first)
    rows.sort(key=lambda t: (
        0 if t["status"] in ACTIVE else 1,
        -_PRIO_RANK.get(t["priority"], 1) if t["status"] in ACTIVE else 0,
        t["created_at"] if t["status"] in ACTIVE else -t["created_at"],
    ))
    return rows[:limit]


def board() -> dict:
    cols = {"queued": [], "assigned": [], "in_progress": [], "done": [], "failed": [], "cancelled": []}
    for t in list_tasks(limit=500):
        cols.setdefault(t["status"], []).append(t)
    counts = {k: len(v) for k, v in cols.items()}
    return {"columns": cols, "counts": counts, "priorities": PRIORITIES}


def _save() -> None:
    from . import store
    if not store.enabled():
        return
    with _lock:
        store.save_state("taskqueue", {"tasks": _tasks, "seq": _seq, "current": _current_by_agent})


def load_persisted() -> None:
    from . import store
    data = store.load_state("taskqueue")
    if not data:
        return
    global _seq
    with _lock:
        _tasks.update({int(k): v for k, v in (data.get("tasks") or {}).items()})
        _seq = max(_seq, int(data.get("seq") or 0))
        _current_by_agent.update(data.get("current") or {})


def clear() -> None:
    global _seq
    with _lock:
        _tasks.clear()
        _current_by_agent.clear()
        _seq = 0
    _save()
