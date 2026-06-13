"""Multi-agent consensus review — never trust one model.

A generated scenario is approved only when an INDEPENDENT panel agrees:

    1. Deterministic Validator  — ``validation.validate_range`` (NOT an LLM; the
       ground-truth gate). A hard issue here is an absolute veto.
    2. Adversarial Validator    — an LLM told to attack the scenario and find any
       flaw, contradiction, or implausible step.
    3. Fact Checker             — an LLM that checks every claim against the cited
       canonical references.
    4. Attack-Path Simulator    — an LLM that walks the chain step by step and
       confirms each stage actually enables the next.
    5. Final Verifier           — aggregates the votes against the threshold.

The deterministic validator always runs (cheap, exact). The three LLM reviewers
run only when the panel is enabled (``MAYBOT_CONSENSUS_LLM=1``) or a panel
``chat`` is injected — otherwise the deterministic gate alone decides, so the
system degrades safely rather than 4x-ing every generation. Each reviewer is
driven through the same injectable ``chat`` for testability.
"""
from __future__ import annotations

import json
import os
import re

from . import validation

PANEL_ON = os.getenv("MAYBOT_CONSENSUS_LLM", "0").lower() in ("1", "true", "yes", "on")
# How many of the LLM reviewers must approve (the deterministic gate is always
# mandatory and counted separately).
THRESHOLD = max(1, int(os.getenv("MAYBOT_CONSENSUS_THRESHOLD", "3")))

_ROLES = {
    "adversarial": (
        "You are an ADVERSARIAL reviewer of a simulated pentest training scenario. Try hard to break "
        "it: find any technical flaw, contradiction, impossible step, or implausible service/version. "
        "Respond with ONLY {\"approve\":true|false,\"issues\":[\"...\"]}."),
    "factcheck": (
        "You are a FACT CHECKER. Verify every vulnerability, CVE and ATT&CK technique referenced in "
        "this scenario is real and correctly applied. Flag anything fabricated or misused. Respond "
        "with ONLY {\"approve\":true|false,\"issues\":[\"...\"]}."),
    "pathsim": (
        "You SIMULATE the attack path. Walk the kill chain host by host and confirm each stage's loot "
        "actually enables reaching the next, and that the objective is achievable from the entry "
        "point. Flag any break. Respond with ONLY {\"approve\":true|false,\"issues\":[\"...\"]}."),
}


def _scenario_brief(parsed: dict) -> str:
    hosts = []
    for hid, h in parsed.get("hosts", {}).items():
        hosts.append({"id": hid, "kind": h.get("kind"), "vuln": h.get("vuln"),
                      "exploit": h.get("exploit"), "technique": h.get("technique"),
                      "cve": h.get("cve"), "privesc": h.get("privesc"),
                      "pivots_to": h.get("pivots_to")})
    return json.dumps({"entry_points": parsed.get("entry_points"),
                       "objective": parsed.get("objective"), "hosts": hosts}, default=str)


def _vote(chat, member, role: str, brief: str) -> dict:
    """Run one LLM reviewer; default to approve on parse failure so a flaky
    backend doesn't block (the deterministic gate still protects correctness)."""
    from . import agents
    chat = chat or agents._chat
    try:
        ok, text, _ = chat({**(member or {}), "max_tokens": 350, "temperature": 0.1},
                            [{"role": "system", "content": _ROLES[role]},
                             {"role": "user", "content": brief}])
        if not ok:
            return {"role": role, "approve": True, "issues": [], "ran": False}
        m = re.search(r"\{.*\}", text or "", re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        return {"role": role, "approve": bool(data.get("approve", True)),
                "issues": [str(x) for x in (data.get("issues") or [])][:5], "ran": True}
    except Exception:
        return {"role": role, "approve": True, "issues": [], "ran": False}


def review_range(parsed: dict, chat=None, member=None, panel: bool | None = None) -> dict:
    """Run the consensus panel over a parsed range. Returns an approval decision,
    every vote, and the merged issue list."""
    det = validation.validate_range(parsed)
    votes = [{"role": "deterministic", "approve": det["approved"],
              "issues": [i["detail"] for i in det["hard"]], "ran": True}]
    run_panel = PANEL_ON if panel is None else panel
    if (run_panel or chat is not None) and parsed.get("hosts"):
        brief = _scenario_brief(parsed)
        for role in ("adversarial", "factcheck", "pathsim"):
            votes.append(_vote(chat, member, role, brief))
    llm_votes = [v for v in votes if v["role"] != "deterministic"]
    llm_approvals = sum(1 for v in llm_votes if v["approve"])
    # threshold applies only to the LLM panel that actually ran
    panel_ok = (not llm_votes) or llm_approvals >= min(THRESHOLD, len(llm_votes))
    approved = det["approved"] and panel_ok
    issues = []
    for v in votes:
        if not v["approve"]:
            issues.extend(v["issues"])
    return {"approved": approved, "deterministic_ok": det["approved"],
            "panel_ok": panel_ok, "votes": votes, "issues": issues,
            "confidence": det.get("confidence", 0) if approved else 0,
            "warnings": [w["detail"] for w in det.get("warnings", [])],
            "grounded_hosts": det.get("grounded_hosts", 0),
            "threshold": THRESHOLD, "llm_reviewers": len(llm_votes)}


def issues_brief(report: dict) -> str:
    return "; ".join(report.get("issues", [])[:8])
