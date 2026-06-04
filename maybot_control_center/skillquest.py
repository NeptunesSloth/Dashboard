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


_CLEAN = re.compile(r"[^a-z0-9 +/&-]")


def _normalize(title: str) -> str:
    """Reduce a result title to a concise skill name (leading phrase, lowercased)."""
    head = re.split(r"\s*[|–—:]\s+|\s+-\s+", title.strip())[0]
    head = _CLEAN.sub("", head.lower()).strip()
    words = head.split()
    return " ".join(words[:5])


def discover(agent: str | None = None, known: set | None = None) -> dict | None:
    """Search the web for a new, real AI skill the disciple doesn't already know.

    Returns {"skill", "url", "source": web|offline, "query"} or None if nothing new.
    """
    known_l = {str(k).lower() for k in (known or set())}
    query = random.choice(SEEDS)
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
        source = "offline"
        pool = [s for s in FALLBACK if s.lower() not in known_l]
        if not pool:
            return None
        skill = random.choice(pool)

    meta = {"skill": skill, "url": url, "source": source, "query": query}
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
