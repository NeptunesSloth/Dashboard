"""CORE 15 — map the curriculum to industry certifications so progress means
something OUTSIDE the platform, and an employer can read it.

Pure functions: given the learner's per-domain RETAINED mastery and whether they
have graduated (real execution), compute readiness for each recognised cert.
``learning.py`` supplies the inputs and assembles the exportable portfolio.
"""
from __future__ import annotations

# Each cert maps to the domains it covers, whether it is HANDS-ON (requires
# proven real execution, i.e. graduation), and the rough mastery bar per domain.
CERTS = [
    {"id": "security_plus", "name": "CompTIA Security+", "provider": "CompTIA",
     "hands_on": False, "bar": 40,
     "domains": ["Network Security", "Incident Response", "Cryptography", "Cloud Security"]},
    {"id": "ceh", "name": "EC-Council CEH", "provider": "EC-Council",
     "hands_on": False, "bar": 60,
     "domains": ["Web Security", "Network Security", "Privilege Escalation", "Active Directory"]},
    {"id": "oscp", "name": "OffSec OSCP", "provider": "OffSec",
     "hands_on": True, "bar": 80,
     "domains": ["Web Security", "Privilege Escalation", "Active Directory", "Network Security"]},
    {"id": "cissp", "name": "ISC2 CISSP", "provider": "ISC2",
     "hands_on": False, "bar": 70,
     "domains": ["Incident Response", "Cryptography", "Cloud Security", "Network Security"]},
    {"id": "giac", "name": "SANS/GIAC (GPEN/GCIH)", "provider": "SANS Institute",
     "hands_on": True, "bar": 75,
     "domains": ["Incident Response", "Digital Forensics", "Malware Analysis", "Network Security"]},
]


def readiness(cert: dict, retained: dict, graduated: bool) -> dict:
    """Readiness for one cert from per-domain retained mastery (points, ~band
    scale). Hands-on certs additionally require graduation (proven execution)."""
    doms = cert["domains"]
    # normalise each domain's mastery to 0..100 against the cert's bar
    per = {d: min(100, round(100 * retained.get(d, 0) / max(1, cert["bar"]))) for d in doms}
    avg = round(sum(per.values()) / len(per)) if per else 0
    gaps = sorted((d for d in doms if per[d] < 70), key=lambda d: per[d])
    blockers = []
    if cert["hands_on"] and not graduated:
        blockers.append("requires proven real execution (graduate first)")
    ready = avg >= 70 and not gaps and not blockers
    return {"id": cert["id"], "name": cert["name"], "provider": cert["provider"],
            "hands_on": cert["hands_on"], "readiness_pct": avg, "ready": ready,
            "per_domain": per, "gaps": gaps, "blockers": blockers}


def all_readiness(retained: dict, graduated: bool) -> list[dict]:
    out = [readiness(c, retained, graduated) for c in CERTS]
    out.sort(key=lambda x: x["readiness_pct"], reverse=True)
    return out
