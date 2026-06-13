"""Canonical security knowledge base — the verified ground truth that anchors
all AI-generated security content.

A generated lab/range may only reference techniques, CVEs, weaknesses or controls
that RESOLVE here. The base ships as version-controlled data (``knowledge/
canonical.yaml``: MITRE ATT&CK techniques, MITRE CVEs, OWASP Top 10, NIST 800-53,
verified AD/privesc/cloud attack chains) and an operator can layer their own set
via ``MAYBOT_KNOWLEDGE_FILE`` (same shape, merged on top).

Pure read-only data + lookups; the validation engine (``validation.py``) uses it
to approve or reject generated scenarios before they reach a learner.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import yaml

_BUNDLED = Path(__file__).resolve().parent.parent / "knowledge" / "canonical.yaml"
_OVERLAY = os.getenv("MAYBOT_KNOWLEDGE_FILE", "")

# Reference shapes we recognise in generated content.
_RE_TECHNIQUE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
_RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_RE_OWASP = re.compile(r"\bA0[1-9]|A10\b")

_lock = threading.RLock()
_kb: dict | None = None


def _load_file(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _index(raw: dict) -> dict:
    """Build id -> entry maps for fast resolution, keyed by section/kind."""
    kb: dict = {"meta": raw.get("meta", {}), "by_id": {}, "sections": {}}
    sections = ("techniques", "cves", "owasp", "nist", "ad_chains", "privesc", "cloud")
    for sec in sections:
        items = raw.get(sec) or []
        clean = [it for it in items if isinstance(it, dict) and it.get("id")]
        kb["sections"][sec] = clean
        for it in clean:
            kb["by_id"][str(it["id"]).upper()] = {**it, "_kind": sec}
    return kb


def _merge(base: dict, overlay: dict) -> dict:
    """Overlay operator entries on top of the bundled set (overlay id wins)."""
    out = {k: list(v) for k, v in base.items() if k not in ("meta",)}
    out_meta = dict(base.get("meta", {}))
    for sec in ("techniques", "cves", "owasp", "nist", "ad_chains", "privesc", "cloud"):
        b = {str(it["id"]): it for it in (base.get(sec) or []) if isinstance(it, dict) and it.get("id")}
        for it in (overlay.get(sec) or []):
            if isinstance(it, dict) and it.get("id"):
                b[str(it["id"])] = it
        out[sec] = list(b.values())
    out_meta.update(overlay.get("meta", {}))
    out["meta"] = out_meta
    return out


def load() -> dict:
    """Load (and cache) the indexed knowledge base."""
    global _kb
    with _lock:
        if _kb is not None:
            return _kb
        raw = _load_file(_BUNDLED)
        if _OVERLAY and Path(_OVERLAY).exists():
            raw = _merge(raw, _load_file(Path(_OVERLAY)))
        _kb = _index(raw)
        return _kb


def reload() -> dict:
    """Drop the cache and reload (e.g. after editing the overlay)."""
    global _kb
    with _lock:
        _kb = None
    return load()


def resolve(ref: str) -> dict | None:
    """Return the canonical entry for an id (T####, CVE-…, A##, control id), or
    None if it does not exist in the knowledge base."""
    if not ref:
        return None
    return load()["by_id"].get(str(ref).strip().upper())


def exists(ref: str) -> bool:
    return resolve(ref) is not None


def extract_references(text: str) -> dict:
    """Pull every technique/CVE/OWASP id mentioned in free text, split into those
    that resolve and those that don't (the hallucinated ones)."""
    if not text:
        return {"known": [], "unknown": []}
    found = set()
    for rx in (_RE_TECHNIQUE, _RE_CVE, _RE_OWASP):
        found |= {m.group(0).upper() for m in rx.finditer(text)}
    known = sorted(r for r in found if exists(r))
    unknown = sorted(r for r in found if not exists(r))
    return {"known": known, "unknown": unknown}


def techniques_for(tactic: str | None = None, platform: str | None = None) -> list[dict]:
    out = []
    for t in load()["sections"].get("techniques", []):
        if tactic and tactic not in (t.get("tactics") or []):
            continue
        if platform and platform not in (t.get("platforms") or []):
            continue
        out.append(t)
    return out


def search(query: str, limit: int = 20) -> list[dict]:
    q = (query or "").strip().lower()
    kb = load()
    if not q:
        items = [v for v in kb["by_id"].values()]
        return items[:limit]
    out = []
    for v in kb["by_id"].values():
        hay = (str(v.get("id", "")) + " " + str(v.get("name", ""))).lower()
        if q in hay:
            out.append(v)
    return out[:limit]


def grounding_brief(track_kind: str = "offensive", limit: int = 16) -> str:
    """A compact menu of canonical references for the generator to CITE — so it
    anchors output to real techniques/CVEs instead of inventing them."""
    kb = load()
    techs = kb["sections"].get("techniques", [])
    cves = kb["sections"].get("cves", [])
    chains = kb["sections"].get("ad_chains", [])
    lines = ["Cite ONLY these canonical references (MITRE ATT&CK technique ids, real CVEs). "
             "Do NOT invent technique ids or CVEs."]
    lines.append("Techniques: " + "; ".join(f"{t['id']} {t['name']}" for t in techs[:limit]))
    lines.append("CVEs: " + "; ".join(f"{c['id']} {c['name']}" for c in cves[:10]))
    if chains:
        lines.append("Verified AD chains: " + "; ".join(c["name"] for c in chains))
    return "\n".join(lines)


def snapshot() -> dict:
    kb = load()
    return {"meta": kb.get("meta", {}),
            "counts": {sec: len(items) for sec, items in kb["sections"].items()},
            "total": len(kb["by_id"])}
