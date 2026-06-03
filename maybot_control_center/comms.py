"""Phase 2: inter-agent comms — a shared "ship comms" channel.

A *mission* gives a roster of agents a shared goal and runs a bounded,
round-robin conversation: each round, every participant contributes one message
based on the channel so far. Messages land in a shared feed the dashboard
renders as SHIP COMMS.

Guardrails (this is where multi-agent loops get expensive/runaway):
- One mission at a time (a second start is rejected).
- Rounds and participant count are hard-capped.
- Total LLM calls per mission = rounds x participants, so cost is bounded.
- Each turn is a single `agents._chat` call (which carries its own timeout).
Reuses the Phase 1 agent definitions and backends (local hosts + Claude).
State is in-memory and resets on restart.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import agents
from . import memory
from . import store
from . import events
from . import cultivation

MAX_ROUNDS = max(1, int(os.getenv("MAYBOT_COMMS_MAX_ROUNDS", "3")))
MAX_PARTICIPANTS = max(2, int(os.getenv("MAYBOT_COMMS_MAX_PARTICIPANTS", "6")))
FEED_CAP = max(20, int(os.getenv("MAYBOT_COMMS_FEED_CAP", "200")))
MSG_CHARS = 4000
CONTEXT_LINES = 40  # how much of the channel each agent sees

_lock = threading.Lock()
_feed: list[dict] = []
_mission: dict | None = None
_seq = 0
_pool = ThreadPoolExecutor(max_workers=1)  # serialize missions


def _post(sender: str, content: str, kind: str = "agent", mission_id=None) -> None:
    global _seq
    with _lock:
        _seq += 1
        msg = {"id": _seq, "from": sender, "content": content, "kind": kind,
               "ts": int(time.time() * 1000), "mission": mission_id}
        _feed.append(msg)
        if len(_feed) > FEED_CAP:
            del _feed[:-FEED_CAP]
    if store.enabled():
        store.add_comms(msg)
    events.publish("comms", {"from": sender, "kind": kind})


def get_feed(limit: int = 100) -> list[dict]:
    with _lock:
        return list(_feed[-limit:])


def status() -> dict:
    with _lock:
        return {"active": _mission is not None, "mission": dict(_mission) if _mission else None}


def _channel_text() -> str:
    with _lock:
        lines = [f"{m['from']}: {m['content']}" for m in _feed if m["kind"] in ("agent", "system")]
    return "\n".join(lines[-CONTEXT_LINES:])


def _mission_system(agent: dict, name: str, roster: str, vault_ctx: str = "") -> str:
    base = (f"{agents._persona(agent)}\n\nYou are {name}, collaborating in a shared team "
            f"channel with: {roster}. Work together toward the goal. Be concise and useful; "
            f"address teammates by name when relevant and build on what they said.")
    return f"{base}\n\n{vault_ctx}" if vault_ctx else base


def _write_mission_memory(goal: str, mission_id) -> None:
    """Persist a mission summary back to the Obsidian vault."""
    if not memory.enabled():
        return
    with _lock:
        msgs = [m for m in _feed if m.get("mission") == mission_id and m["kind"] == "agent"]
    if not msgs:
        return
    body = [f"## Mission: {goal}", f"_recorded {time.strftime('%Y-%m-%d %H:%M')}_", ""]
    body += [f"- **{m['from']}**: {m['content']}" for m in msgs]
    memory.write_note(f"mission-{goal[:48]}", "\n".join(body))


def run_mission(goal: str, names: list[str], rounds: int, mission_id) -> None:
    """Run the round-robin conversation (the background worker entrypoint)."""
    global _mission
    roster = ", ".join(names)
    vault_ctx = memory.context_for(goal) if memory.enabled() else ""
    try:
        for rnd in range(rounds):
            for name in names:
                agent = agents._agent_def(name)
                if not agent:
                    _post("system", f"(skipped unknown agent {name})", "system", mission_id)
                    continue
                with _lock:
                    if _mission is not None:
                        _mission["round"] = rnd + 1
                        _mission["current"] = name
                channel = _channel_text()
                user = (f"Mission goal: {goal}\n\nChannel so far:\n{channel or '(empty)'}\n\n"
                        f"You are {name}. Add ONE concise contribution (2-4 sentences). "
                        f"Don't repeat what's already been said.")
                ok, text, err = agents._chat(agent, [
                    {"role": "system", "content": _mission_system(agent, name, roster, vault_ctx)},
                    {"role": "user", "content": user},
                ])
                content = (text or "").strip()[:MSG_CHARS] if ok else f"(error: {err})"
                _post(name, content or "(no response)", "agent", mission_id)
                cultivation.on_council(name) if ok else cultivation.on_task(name, False)
        _write_mission_memory(goal, mission_id)
        saved = " · saved to vault" if memory.enabled() else ""
        _post("system", f"Mission complete.{saved}", "system", mission_id)
    finally:
        with _lock:
            _mission = None


def start_mission(goal: str, participants: list[str], rounds: int = 2) -> dict:
    """Validate + launch a mission in the background. Returns the mission snapshot."""
    global _mission
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal required")
    seen: set[str] = set()
    names = [p for p in (participants or [])
             if agents._agent_def(p) and not (p in seen or seen.add(p))]
    if len(names) < 2:
        raise ValueError("need at least 2 valid participants")
    names = names[:MAX_PARTICIPANTS]
    rounds = max(1, min(int(rounds or 1), MAX_ROUNDS))

    with _lock:
        if _mission is not None:
            raise RuntimeError("a mission is already running")
        mission_id = int(time.time() * 1000)
        _mission = {
            "id": mission_id, "goal": goal, "participants": names, "rounds": rounds,
            "round": 0, "current": None, "started_at": mission_id,
        }
        snap = dict(_mission)
    _post("system", f"Mission started: {goal} — crew: {', '.join(names)} ({rounds} rounds)", "system", mission_id)
    _pool.submit(run_mission, goal, names, rounds, mission_id)
    return snap


def load_persisted() -> None:
    global _seq
    if not store.enabled():
        return
    rows = store.load_comms(FEED_CAP)
    with _lock:
        _feed.clear()
        _feed.extend(rows)
        _seq = max((m.get("id") or 0 for m in _feed), default=0)


def clear() -> None:
    global _mission
    with _lock:
        _feed.clear()
        _mission = None
