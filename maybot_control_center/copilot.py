"""Ops Copilot — answer natural-language questions about the whole fleet,
grounded in live state (hosts, bots, health, alerts), using a configured LLM
member.

Advisory by design: the model only *explains and recommends*. Any concrete
remediation is surfaced as a structured action the operator clicks, which routes
through the existing, access-controlled ``/api/action`` proxy — the copilot
never executes anything on its own.
"""
from __future__ import annotations

from . import agents

SYSTEM = (
    "You are MayBot's Ops Copilot — a terse, precise site-reliability engineer for a "
    "fleet of trading bots and services. Answer the operator's question using ONLY the "
    "fleet context provided. Be concrete and brief (a few sentences). When a bot needs "
    "attention, name the bot and its host and the single best next step. Never invent "
    "hosts, bots, or numbers that are not in the context."
)


def _backend_member() -> dict | None:
    """First configured member with a usable LLM backend (same rule as /explain)."""
    for a in agents.file_agents():
        if a.get("base_url") or a.get("provider") in ("claude", "anthropic"):
            return a
    return None


def build_context(overview: dict, max_bots: int = 40) -> str:
    s = overview.get("summary", {}) or {}
    devices = overview.get("devices", []) or []
    projects = overview.get("projects", []) or []
    lines = [
        f"Fleet: {s.get('online_devices', 0)}/{s.get('total_devices', 0)} hosts online, "
        f"{s.get('total_projects', 0)} bots, {s.get('projects_with_warnings_errors', 0)} with "
        f"warnings/errors, {s.get('bots_running', 0)} trading bots running.",
    ]
    offline = [str(d.get("name")) for d in devices if not d.get("online")]
    if offline:
        lines.append(f"Offline/unreachable hosts: {', '.join(offline)}.")
    for p in projects[:max_bots]:
        alerts = p.get("alerts") or []
        lines.append(
            f"- {p.get('name')} on {p.get('device')}: type={p.get('type')}, "
            f"status={p.get('status')}, health={p.get('health')}"
            + (f", alerts={alerts}" if alerts else "")
        )
    return "\n".join(lines)


def _suggested_actions(projects: list[dict]) -> list[dict]:
    """Conservative, deterministic remediations (independent of the LLM)."""
    acts: list[dict] = []
    for p in projects or []:
        alerts = " ".join(p.get("alerts") or [])
        if p.get("status") == "stopped" and ("expected but stopped" in alerts or p.get("health") == "error"):
            acts.append({
                "kind": "start", "device": p.get("device"), "project": p.get("name"),
                "label": f"Start {p.get('name')} on {p.get('device')}",
            })
    return acts[:8]


def ask(question: str, overview: dict, chat=None) -> dict:
    """Answer a fleet question. ``chat`` is injectable for tests; defaults to the
    real LLM call. Returns {answer, actions, member, error}."""
    question = (question or "").strip()
    projects = (overview or {}).get("projects", []) or []
    actions = _suggested_actions(projects)
    if not question:
        return {"answer": "", "actions": actions, "member": None, "error": "empty question"}

    member = _backend_member()
    if not member:
        return {
            "answer": "No AI member with an LLM backend is configured yet. Add one in "
                      "Sect Members (Claude, or a local Ollama/OpenAI-compatible base_url) "
                      "to enable the Ops Copilot.",
            "actions": actions, "member": None, "error": "no_backend",
        }

    chat = chat or agents._chat
    context = build_context(overview)
    ok, text, err = chat(
        {**member, "max_tokens": 500, "temperature": 0.2},
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Fleet context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    if not ok:
        return {"answer": "", "actions": actions, "member": member.get("name"),
                "error": err or "the AI member did not respond"}
    return {"answer": (text or "").strip(), "actions": actions, "member": member.get("name"), "error": None}


def ask_stream(question: str, overview: dict, chat_stream=None):
    """Streaming variant of ask(): a generator of event dicts —
    ``{"type":"meta",...}`` first (member + deterministic actions), then any
    number of ``{"type":"token","text":...}`` as the model produces output, and
    finally ``{"type":"done"}`` (or ``{"type":"error",...}``). ``chat_stream`` is
    injectable for tests; it defaults to the real streaming call."""
    question = (question or "").strip()
    projects = (overview or {}).get("projects", []) or []
    actions = _suggested_actions(projects)
    if not question:
        yield {"type": "meta", "member": None, "actions": actions}
        yield {"type": "error", "error": "empty question"}
        return

    member = _backend_member()
    if not member:
        yield {"type": "meta", "member": None, "actions": actions}
        yield {"type": "error", "error": "no_backend",
               "answer": "No AI member with an LLM backend is configured yet. Add one in "
                         "Sect Members to enable the Ops Copilot."}
        return

    yield {"type": "meta", "member": member.get("name"), "actions": actions}
    chat_stream = chat_stream or agents.stream_chat
    context = build_context(overview)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Fleet context:\n{context}\n\nQuestion: {question}"},
    ]
    got = False
    try:
        for chunk in chat_stream({**member, "max_tokens": 500, "temperature": 0.2}, messages):
            if chunk:
                got = True
                yield {"type": "token", "text": chunk}
    except Exception as exc:  # never let a backend error break the SSE stream
        yield {"type": "error", "error": str(exc)}
        return
    if not got:
        yield {"type": "error", "error": "the AI member did not respond"}
    yield {"type": "done"}
