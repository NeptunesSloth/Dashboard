"""Roaming skill-quests — disciples wander the *real* web for an actual AI skill.

When a roaming disciple's journey matures, instead of inventing a flavour art it
**searches the web** for a real AI / agent technique and learns it. The search
is a best-effort, keyless HTTP call (DuckDuckGo's Instant-Answer API by default,
or a configured endpoint); the chosen skill and its **source URL** are recorded.
When the web is unreachable it falls back to a curated list of genuine AI skills,
so roaming always yields something real.
"""
from __future__ import annotations

import os
import random
import re
import threading

import requests

# Seed queries — disciples go looking for different kinds of AI skill each time.
SEEDS = [
    "AI agent technique", "LLM prompting technique", "machine learning method",
    "retrieval augmented generation", "AI reasoning method", "agent tool use technique",
    "neural network technique", "model fine-tuning method", "vector database technique",
]
# Real AI skills, used when the web can't be reached (so roaming never comes back empty).
FALLBACK = [
    "retrieval-augmented generation", "function calling", "chain-of-thought prompting",
    "vector search", "semantic chunking", "reranking", "tool use", "prompt caching",
    "speculative decoding", "mixture of experts", "lora fine-tuning", "rlhf",
    "few-shot prompting", "self-consistency decoding", "react prompting",
    "context compression", "embedding search", "output guardrails", "structured output",
    "model distillation", "quantization", "agentic planning", "self-reflection",
]

TIMEOUT = float(os.getenv("MAYBOT_SKILLQUEST_TIMEOUT", "6"))
SEARCH_URL = os.getenv("MAYBOT_SEARCH_URL", "https://api.duckduckgo.com/")

_lock = threading.Lock()
_last: dict[str, dict] = {}     # agent -> last discovery meta


def _ddg(query: str) -> list[dict]:
    """DuckDuckGo Instant-Answer API (no key). Returns [{title, url}]."""
    r = requests.get(SEARCH_URL, params={"q": query, "format": "json", "no_html": 1, "t": "maybot"},
                     timeout=TIMEOUT, headers={"User-Agent": "maybot-skillquest"})
    data = r.json()
    out: list[dict] = []
    if data.get("Heading") and data.get("AbstractURL"):
        out.append({"title": data["Heading"], "url": data["AbstractURL"]})
    for t in data.get("RelatedTopics", []):
        if isinstance(t, dict) and t.get("Text") and t.get("FirstURL"):
            out.append({"title": t["Text"], "url": t["FirstURL"]})
    return out


# Injectable so the search can be swapped/tested without network.
def _search(query: str) -> list[dict]:
    return _ddg(query)


def _fetch_doc(url: str) -> str:
    """Fetch a short how-to summary from the skill's source page (best effort)."""
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "maybot-skillquest"})
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:700]
    except Exception:
        return ""


_CLEAN = re.compile(r"[^a-z0-9 +/&-]")


def _normalize(title: str) -> str:
    """Reduce a result title to a concise skill name (leading phrase, lowercased)."""
    head = re.split(r"\s*[|–—:]\s+|\s+-\s+", title.strip())[0]
    head = _CLEAN.sub("", head.lower()).strip()
    words = head.split()
    return " ".join(words[:5])


def _closest(want: str, pool: list[str]) -> str | None:
    """The pool entry sharing the most words with ``want`` (None if no overlap)."""
    wanted = set(re.findall(r"[a-z0-9]+", want.lower()))
    best, best_score = None, 0
    for s in pool:
        overlap = len(wanted & set(re.findall(r"[a-z0-9]+", s.lower())))
        if overlap > best_score:
            best, best_score = s, overlap
    return best


def discover(agent: str | None = None, known: set | None = None,
             want: str | None = None) -> dict | None:
    """Search the web for a real AI skill the disciple doesn't already know.

    If ``want`` is set (an Ancestor-requested skill), search for *that* and learn
    it or the closest match. Returns {"skill","url","source","query","requested"}
    or None if nothing new.
    """
    known_l = {str(k).lower() for k in (known or set())}
    want = (want or "").strip()
    query = want or random.choice(SEEDS)
    try:
        results = _search(query) or []
    except Exception:
        results = []

    skill, url, source = "", "", "web"
    for r in results:
        cand = _normalize(r.get("title", ""))
        if len(cand) > 3 and cand not in known_l:
            skill, url = cand, r.get("url", "")
            break

    if not skill:
        if want:
            # Offline but a skill was requested: learn the closest curated match,
            # or the requested skill itself if nothing's close.
            source = "requested"
            cand = _closest(want, [s for s in FALLBACK if s.lower() not in known_l])
            skill = cand or (want.lower() if want.lower() not in known_l else "")
        else:
            source = "offline"
            pool = [s for s in FALLBACK if s.lower() not in known_l]
            skill = random.choice(pool) if pool else ""
        if not skill:
            return None

    doc = _fetch_doc(url) if (source == "web" and url) else ""
    meta = {"skill": skill, "url": url, "source": source, "query": query,
            "requested": bool(want), "doc": doc}
    if agent:
        with _lock:
            _last[agent] = meta
    return meta


def last(agent: str) -> dict | None:
    with _lock:
        return dict(_last[agent]) if agent in _last else None


def clear() -> None:
    with _lock:
        _last.clear()
