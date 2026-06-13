"""Real-world artifact library — CORE 8: security work is not synthetic text.

A catalog of the artifact TYPES real analysts work with (PCAPs, memory images,
Apache/nginx/Windows-Event/Sysmon logs, malware samples, IAM/S3/Terraform configs,
vulnerable containers), the tool each is analysed with, and the domain it trains.
Operators register actual artifact files via ``lab_artifacts.yaml`` (or
``MAYBOT_ARTIFACTS_FILE``); the Learning Center grounds labs in a registered
artifact when one exists for the requested type, instead of a synthetic-only lab.

Read-only metadata. Malware samples are operator-supplied and must be handled in
the isolated sandbox (see docs/REAL_LABS.md) — nothing here executes anything.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ARTIFACTS_FILE = Path(os.getenv("MAYBOT_ARTIFACTS_FILE", "lab_artifacts.yaml"))

# The artifact TYPES a real curriculum must cover, with the analysis tool + domain.
ARTIFACT_TYPES = [
    {"type": "pcap", "name": "Packet capture (PCAP)", "tool": "Wireshark / tshark / Zeek",
     "domain": "Network Security", "prompt": "raw packet capture of network traffic"},
    {"type": "memory", "name": "Memory image", "tool": "Volatility Framework",
     "domain": "Digital Forensics", "prompt": "a memory dump to analyse for injected code / processes"},
    {"type": "apache_log", "name": "Apache access log", "tool": "grep / awk / SIEM",
     "domain": "Incident Response", "prompt": "Apache access logs"},
    {"type": "nginx_log", "name": "nginx access log", "tool": "grep / awk / SIEM",
     "domain": "Incident Response", "prompt": "nginx access/error logs"},
    {"type": "windows_event", "name": "Windows Event Log", "tool": "Event Viewer / EvtxECmd",
     "domain": "Digital Forensics", "prompt": "Windows Security event logs (4624/4625/4688…)"},
    {"type": "sysmon", "name": "Sysmon log", "tool": "Sysmon / EDR",
     "domain": "Incident Response", "prompt": "Sysmon process/network telemetry"},
    {"type": "malware_script", "name": "Obfuscated script sample", "tool": "deobfuscation / sandbox",
     "domain": "Malware Analysis", "prompt": "an obfuscated (safe, defanged) malicious script to analyse"},
    {"type": "malware_sample", "name": "Malware sample (sandboxed)", "tool": "static/dynamic analysis",
     "domain": "Malware Analysis", "prompt": "a malware sample to triage (operator-supplied, sandbox only)"},
    {"type": "iam_policy", "name": "Cloud IAM policy", "tool": "policy review / Prowler",
     "domain": "Cloud Security", "prompt": "a cloud IAM policy document to audit for over-permission"},
    {"type": "s3_config", "name": "Object storage / S3 config", "tool": "config review / ScoutSuite",
     "domain": "Cloud Security", "prompt": "an S3 bucket / object-storage configuration to audit"},
    {"type": "terraform", "name": "Terraform / IaC", "tool": "tfsec / Checkov",
     "domain": "Cloud Security", "prompt": "Terraform / IaC to review for misconfiguration"},
    {"type": "docker", "name": "Vulnerable container", "tool": "Trivy / Dockerfile review",
     "domain": "Cloud Security", "prompt": "a Dockerfile / container config to review for weaknesses"},
]
_BY_TYPE = {a["type"]: a for a in ARTIFACT_TYPES}


def artifact_type(t: str) -> dict | None:
    return _BY_TYPE.get((t or "").strip().lower())


def types_for_domain(domain: str) -> list[dict]:
    return [a for a in ARTIFACT_TYPES if a["domain"] == domain]


def load_registered() -> list[dict]:
    """Operator-registered REAL artifact files (path/url + type), if any."""
    if not ARTIFACTS_FILE.exists():
        return []
    try:
        data = yaml.safe_load(ARTIFACTS_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out = []
    for a in (data.get("artifacts") or []):
        if isinstance(a, dict) and a.get("type") and a.get("source"):
            out.append({"type": str(a["type"]).lower(), "name": str(a.get("name", a["type"])),
                        "source": str(a["source"]), "note": str(a.get("note", "")),
                        "answer": str(a.get("answer", ""))})
    return out


def registered_for(t: str) -> dict | None:
    t = (t or "").strip().lower()
    return next((a for a in load_registered() if a["type"] == t), None)


def catalog() -> dict:
    reg = load_registered()
    have = {a["type"] for a in reg}
    return {"types": [{**a, "registered": a["type"] in have} for a in ARTIFACT_TYPES],
            "registered": reg, "registered_count": len(reg)}
