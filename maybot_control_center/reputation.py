"""Reputation / trust tiers — merit & karma derived from what a disciple has done.

A merit score (0-100) is computed live from the persisted audit log and
cultivation state: cultivation realm & breakthroughs, LLM success rate, and
guarded-tool reliability (completed vs failed/denied calls), minus a penalty for
a current failure streak. The score maps to a trust tier:

  - Trusted   (>= 75): earns bonus autonomy budget
  - Standard  (45-74): normal
  - Probation (< 45):  auto-runs are blocked — every tool call needs approval

So autonomy is **earned**: reliable disciples are trusted to act; ones that keep
failing or get denied are demoted back to human-gated.
"""
from __future__ import annotations

import os

TRUSTED_AT = int(os.getenv("MAYBOT_TRUST_TRUSTED", "75"))
PROBATION_BELOW = int(os.getenv("MAYBOT_TRUST_PROBATION", "45"))
TRUSTED_BONUS = int(os.getenv("MAYBOT_TRUST_AUTONOMY_BONUS", "3"))


def _tool_stats(agent: str) -> dict:
    from . import tools as tooling  # lazy: tools imports autonomy which imports us
    done = failed = denied = 0
    for c in tooling.list_calls(200):
        if c.get("requester") != agent:
            continue
        s = c.get("status")
        if s == "done":
            done += 1
        elif s == "denied":
            denied += 1
        elif s in ("failed", "error"):
            failed += 1
    return {"done": done, "failed": failed, "denied": denied}


def score(agent: str) -> dict:
    from . import cultivation, usage
    c = cultivation.state(agent)
    u = next((r for r in usage.snapshot()["agents"] if r["agent"] == agent), None)
    success_pct = u["success_pct"] if u else 100
    tools = _tool_stats(agent)

    merit = 40
    merit += c["realm"] * 4
    merit += c["breakthroughs"] * 2
    merit += (success_pct - 50) * 0.4          # reward reliability, punish failures
    merit += tools["done"] * 2 - tools["failed"] * 3 - tools["denied"] * 6
    merit -= c.get("fail_streak", 0) * 5
    merit = int(max(0, min(100, round(merit))))

    tier = "Trusted" if merit >= TRUSTED_AT else ("Probation" if merit < PROBATION_BELOW else "Standard")
    return {"agent": agent, "merit": merit, "tier": tier,
            "signals": {"realm": c["realm"], "success_pct": success_pct, **tools, "fail_streak": c.get("fail_streak", 0)}}


def tier(agent: str) -> str:
    return score(agent)["tier"]


def is_probation(agent: str) -> bool:
    return tier(agent) == "Probation"


def autonomy_bonus(agent: str) -> int:
    return TRUSTED_BONUS if tier(agent) == "Trusted" else 0


def snapshot() -> dict:
    from . import agents
    return {a.get("name"): score(a["name"]) for a in agents.load_agents() if a.get("name")}
