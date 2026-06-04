"""Compounding sect memory — the shared knowledge the whole sect accumulates.

Every task result, post-incident summary, Elder manual, and roamed skill is
written here; before a disciple acts, the most relevant past knowledge is
retrieved and folded into its prompt. So the sect literally gets smarter the
longer it runs — knowledge compounds and is shared across disciples.

Retrieval is a lightweight, dependency-free TF-overlap ranker (no external vector
DB needed); it can be swapped for real embeddings later without touching callers.
State persists via the store when MAYBOT_DB is set.
"""
from __future__ import annotations

import math
import os
import re
import threading
import time

CAP = max(50, int(os.getenv("MAYBOT_SECT_MEMORY_CAP", "2000")))
ENABLED = os.getenv("MAYBOT_SECT_MEMORY", "1").strip().lower() not in {"0", "false", "no", ""}

_lock = threading.Lock()
_entries: list[dict] = []
_seq = 0
_STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "was", "are", "its", "into"}


def _tok(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]{3,}", (s or "").lower()) if t not in _STOP]


def add(text: str, source: str = "", agent: str = "", kind: str = "note") -> dict | None:
    if not ENABLED or not (text or "").strip():
        return None
    global _seq
    with _lock:
        _seq += 1
        rec = {"id": _seq, "text": text.strip()[:1200], "source": source,
               "agent": agent, "kind": kind, "ts": int(time.time() * 1000)}
        _entries.append(rec)
        if len(_entries) > CAP:
            del _entries[:len(_entries) - CAP]
    _save()
    return rec


def search(query: str, k: int = 4) -> list[dict]:
    q = set(_tok(query))
    if not q:
        return []
    scored = []
    with _lock:
        for e in _entries:
            et = _tok(e["text"])
            if not et:
                continue
            overlap = sum(1 for t in et if t in q)
            if overlap:
                scored.append((overlap / math.sqrt(len(et)), e))
    scored.sort(key=lambda x: -x[0])
    return [dict(e) for _, e in scored[:k]]


def context_for(query: str, k: int = 3) -> str:
    """A prompt block of the most relevant accumulated knowledge (or '')."""
    hits = search(query, k)
    if not hits:
        return ""
    lines = "\n".join(f"- ({h['kind']}{'/' + h['agent'] if h['agent'] else ''}) {h['text'][:240]}" for h in hits)
    return f"Relevant sect knowledge (learned from past work):\n{lines}"


def snapshot() -> dict:
    with _lock:
        return {"enabled": ENABLED, "count": len(_entries),
                "recent": [dict(e) for e in _entries[-20:][::-1]]}


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("sectmemory", {"entries": _entries[-CAP:], "seq": _seq})


def load_persisted() -> None:
    from . import store
    data = store.load_state("sectmemory")
    if not data:
        return
    global _seq
    with _lock:
        _entries.extend(data.get("entries") or [])
        _seq = max(_seq, int(data.get("seq") or 0))


def clear() -> None:
    global _seq
    with _lock:
        _entries.clear()
        _seq = 0
