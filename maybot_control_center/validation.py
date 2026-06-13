"""Scenario validation engine — the gate every AI-generated security scenario
passes before a learner ever sees it.

Pipeline (per the platform's ground-truth requirement):

    generated scenario
        -> parse            (normalise into a checkable structure)
        -> references       (every cited technique/CVE resolves in the KB)
        -> consistency      (the attack graph actually works end to end)
        -> security rules   (no impossible / contradictory tradecraft)
        -> APPROVE / REJECT

A HARD issue rejects the scenario (it would teach something false or broken). A
WARNING is recorded but allowed (e.g. weak grounding) so generation degrades
gracefully rather than failing shut. ``learning.generate_range`` runs this,
asks the model to repair on rejection, and refuses to serve a scenario that
still fails — so a hallucinated attack chain never reaches the learner.
"""
from __future__ import annotations

from . import knowledge


def _issue(level: str, code: str, detail: str) -> dict:
    return {"level": level, "code": code, "detail": detail}


# --- stage 1: parse -------------------------------------------------------
def parse_range(rng: dict) -> dict:
    """Normalise a range into {hosts, entry_points, objective} we can check."""
    hosts = rng.get("hosts") or {}
    return {
        "hosts": hosts,
        "entry_points": list(rng.get("entry_points") or []),
        "objective": rng.get("objective") or {},
    }


def _host_text(h: dict) -> str:
    return " ".join(str(h.get(k, "")) for k in
                    ("vuln", "exploit", "privesc", "persistence", "enum_hint", "technique", "cve"))


# --- stage 2: references resolve -----------------------------------------
def _check_references(parsed: dict) -> list[dict]:
    issues: list[dict] = []
    grounded_hosts = 0
    for hid, h in parsed["hosts"].items():
        refs = knowledge.extract_references(_host_text(h))
        if refs["unknown"]:
            issues.append(_issue("hard", "unknown_reference",
                                 f"host '{hid}' cites unknown reference(s) {refs['unknown']} "
                                 "— likely hallucinated; not in the knowledge base"))
        if refs["known"]:
            grounded_hosts += 1
    if grounded_hosts == 0 and parsed["hosts"]:
        issues.append(_issue("warn", "ungrounded",
                             "no host cites a canonical technique/CVE — weak grounding"))
    return issues


# --- stage 3: consistency (the graph actually works) ---------------------
def _check_consistency(parsed: dict) -> list[dict]:
    issues: list[dict] = []
    hosts = parsed["hosts"]
    ids = set(hosts)
    if not hosts:
        return [_issue("hard", "empty", "scenario has no hosts")]

    entries = [e for e in parsed["entry_points"] if e in ids]
    if not entries:
        issues.append(_issue("hard", "no_entry", "no valid entry point — the learner can't start"))

    # every pivot target must exist
    for hid, h in hosts.items():
        for tgt in (h.get("pivots_to") or []):
            if tgt not in ids:
                issues.append(_issue("hard", "dangling_pivot",
                                     f"host '{hid}' pivots to unknown host '{tgt}'"))
        if not str(h.get("exploit", "")).strip():
            issues.append(_issue("hard", "no_exploit", f"host '{hid}' has no exploitation path"))

    # the whole graph must be reachable from the entry points
    reachable = set(entries)
    frontier = list(entries)
    while frontier:
        cur = frontier.pop()
        for tgt in (hosts.get(cur, {}).get("pivots_to") or []):
            if tgt in ids and tgt not in reachable:
                reachable.add(tgt)
                frontier.append(tgt)
    unreachable = ids - reachable
    if unreachable:
        issues.append(_issue("hard", "unreachable_hosts",
                             f"hosts {sorted(unreachable)} can never be reached from the entry point"))

    # the objective must sit on a reachable host that is a sink (the crown jewel)
    obj = parsed["objective"]
    tgt = obj.get("target_host")
    if tgt:
        if tgt not in ids:
            issues.append(_issue("hard", "objective_missing_host",
                                 f"objective targets unknown host '{tgt}'"))
        else:
            if tgt not in reachable:
                issues.append(_issue("hard", "objective_unreachable",
                                     f"objective host '{tgt}' is unreachable — the range can't be completed"))
            if hosts[tgt].get("pivots_to"):
                issues.append(_issue("warn", "objective_not_sink",
                                     f"objective host '{tgt}' still pivots onward — expected the deepest host"))
            if not str(obj.get("flag", "")).strip():
                issues.append(_issue("warn", "no_flag", "objective has no concrete flag/file to capture"))
    return issues


# --- stage 4: security rule engine ---------------------------------------
def _security_rules(parsed: dict) -> list[dict]:
    issues: list[dict] = []
    hosts = parsed["hosts"]
    # A domain controller in scope should involve real AD tradecraft, not generic.
    dc = [hid for hid, h in hosts.items() if str(h.get("kind", "")).lower() == "dc"]
    if dc:
        ad_terms = ("kerber", "ntlm", "dcsync", "golden", "ticket", "ldap", "smb", "domain",
                    "t1558", "t1003", "t1207", "t1021", "t1187")
        blob = " ".join(_host_text(hosts[d]).lower() for d in dc)
        if not any(t in blob for t in ad_terms):
            issues.append(_issue("warn", "weak_ad_tradecraft",
                                 "a domain controller is in scope but the path uses no recognisable "
                                 "AD technique (Kerberoasting/NTLM/DCSync/etc.)"))
    # privesc claimed on a host should name a mechanism, not hand-wave.
    for hid, h in hosts.items():
        pe = str(h.get("privesc", "")).strip().lower()
        if pe and len(pe) < 8:
            issues.append(_issue("warn", "vague_privesc",
                                 f"host '{hid}' privesc is too vague to be a real technique"))
    return issues


# --- orchestrator ---------------------------------------------------------
def validate_range(rng: dict) -> dict:
    """Run the full pipeline. ``approved`` is False if any HARD issue is found."""
    parsed = parse_range(rng)
    issues = (_check_references(parsed) + _check_consistency(parsed) + _security_rules(parsed))
    hard = [i for i in issues if i["level"] == "hard"]
    warnings = [i for i in issues if i["level"] == "warn"]
    grounded = sum(1 for h in parsed["hosts"].values()
                   if knowledge.extract_references(_host_text(h))["known"])
    n = max(1, len(parsed["hosts"]))
    # confidence: penalise hard issues heavily, warnings lightly, reward grounding.
    score = max(0, min(100, 100 - 100 * len(hard) - 8 * len(warnings) + round(20 * grounded / n) - 20))
    return {"approved": not hard, "hard": hard, "warnings": warnings,
            "issues": issues, "grounded_hosts": grounded, "host_count": len(parsed["hosts"]),
            "confidence": (score if not hard else 0)}


def issues_brief(report: dict) -> str:
    """A terse list of problems to feed back to the generator for a repair pass."""
    return "; ".join(f"[{i['code']}] {i['detail']}" for i in report.get("issues", []))


# --- a lighter check for single-artifact labs ----------------------------
def validate_lab(lab: dict) -> dict:
    """Labs are a single artifact + answer; check the cited references resolve."""
    text = " ".join(str(lab.get(k, "")) for k in ("answer", "brief", "artifact"))
    refs = knowledge.extract_references(text)
    hard = []
    if refs["unknown"]:
        hard.append(_issue("hard", "unknown_reference",
                           f"lab cites unknown reference(s) {refs['unknown']}"))
    return {"approved": not hard, "hard": hard, "warnings": [],
            "issues": hard, "known_refs": refs["known"]}
