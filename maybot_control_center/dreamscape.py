"""Dreamscape — formation dry-run (plan preview).

Preview a multi-agent *formation* pipeline (its DAG of stages) WITHOUT calling
any LLM. The operator gets each stage's assigned disciple, a short synthetic
placeholder of what that disciple would do, and a token/cost estimate — so the
plan can be sanity-checked and budgeted before it is run for real.

This module is stateless and pure: it only reads the formation catalog and the
agent roster, then computes a plan. No network, no LLM, no shared mutable state.
"""
from __future__ import annotations

import os

COST_PER_STAGE = int(os.getenv("MAYBOT_DREAM_STAGE_TOKENS", "1500"))


def estimate_tokens(stage_count: int) -> int:
    """Estimated total tokens for a plan with ``stage_count`` stages."""
    return stage_count * COST_PER_STAGE


def preview(formation_name: str, goal: str, roster: list[str] | None = None) -> dict:
    """Dry-run a formation: assign disciples + estimate cost without any LLM call.

    Mirrors the real runner's stage assignment (explicit ``stage["agent"]`` if it
    is in the roster, else round-robin) but produces only synthetic placeholders.
    """
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal must not be empty")

    from . import formations  # lazy sibling import

    form = formations.get(formation_name)
    if form is None:
        raise ValueError(f"unknown formation: {formation_name!r}")

    if roster is None:
        from . import agents  # lazy sibling import

        roster = [a.get("name") for a in agents.load_agents() if a.get("name")]
    if not roster:
        raise ValueError("roster must not be empty")

    rows = []
    for i, stage in enumerate(form.get("stages") or []):
        sname = stage.get("name") or ""
        role = stage.get("role") or ""
        want = stage.get("agent")
        assignee = want if want in roster else roster[i % len(roster)]
        rows.append(
            {
                "stage": sname,
                "role": role,
                "assignee": assignee,
                "preview": f"⟨dream⟩ {assignee} would {role or 'advance the goal'} for: {goal}",
                "est_tokens": COST_PER_STAGE,
            }
        )

    participants: list[str] = []
    for row in rows:
        if row["assignee"] not in participants:
            participants.append(row["assignee"])

    n = len(rows)
    return {
        "formation": formation_name,
        "title": form.get("title") or formation_name,
        "goal": goal,
        "stages": rows,
        "stage_count": n,
        "est_tokens_total": estimate_tokens(n),
        "participants": participants,
    }
