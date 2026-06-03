"""Phase 1 agent runtime: LLM-backed persona agents you can assign tasks to.

Agents are defined in ``agents.yaml`` (see ``agents.yaml.example``). Each agent
has a persona (system prompt) and points at a local AI host endpoint — Ollama or
any OpenAI-compatible server (LM Studio, llama.cpp, vLLM, …). Assigning a task
runs a single chat completion against that endpoint in a background thread; the
reply is appended to the agent's transcript and surfaced on the dashboard.

Phase 1 is deliberately read-only: agents *think and talk*, they do NOT execute
commands or tools, and they do not talk to each other yet (that is Phase 2).
State is in-memory and resets when the control center restarts.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml

from . import memory
from . import tools as tooling

AGENTS_FILE = Path(os.getenv("MAYBOT_AGENTS_FILE", "agents.yaml"))
DEFAULT_TIMEOUT = int(os.getenv("MAYBOT_AGENT_TIMEOUT", "60"))
MAX_TURNS = max(2, int(os.getenv("MAYBOT_AGENT_MAX_TURNS", "20")))  # transcript messages kept for context

_lock = threading.Lock()
_state: dict[str, dict] = {}
_pool = ThreadPoolExecutor(max_workers=4)
_anthropic = None


def load_agents() -> list[dict]:
    if not AGENTS_FILE.exists():
        return []
    with AGENTS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    agents = data.get("agents", [])
    return agents if isinstance(agents, list) else []


def _agent_def(name: str) -> dict | None:
    return next((a for a in load_agents() if a.get("name") == name), None)


def _persona(agent: dict) -> str:
    return agent.get("persona") or agent.get("system") or f"You are {agent.get('name', 'an assistant')}."


def _anthropic_client():
    """Lazily construct (and cache) the Anthropic SDK client."""
    global _anthropic
    if _anthropic is None:
        import anthropic  # resolves ANTHROPIC_API_KEY from the environment
        _anthropic = anthropic.Anthropic()
    return _anthropic


def _chat_claude(agent: dict, messages: list[dict]) -> tuple[bool, str, str | None]:
    """Run one turn against the Claude API via the official Anthropic SDK."""
    try:
        import anthropic
    except ImportError:
        return False, "", "anthropic SDK not installed (pip install anthropic)"

    model = agent.get("model") or "claude-opus-4-8"
    max_tokens = int(agent.get("max_tokens", 1024))
    system_text = next((m["content"] for m in messages if m["role"] == "system"), _persona(agent))
    convo = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
    try:
        resp = _anthropic_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            # Stable persona first, cached so repeat turns reuse the prefix.
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            messages=convo,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return True, text, None
    except anthropic.AuthenticationError:
        return False, "", "Claude API authentication failed — set ANTHROPIC_API_KEY"
    except Exception as exc:
        return False, "", str(exc)


def _chat(agent: dict, messages: list[dict]) -> tuple[bool, str, str | None]:
    """Run one chat completion against the agent's configured backend."""
    provider = (agent.get("provider") or "openai_compatible").lower()
    if provider in ("claude", "anthropic"):
        return _chat_claude(agent, messages)
    base_url = (agent.get("base_url") or "").rstrip("/")
    model = agent.get("model") or agent.get("default_model") or ""
    temperature = float(agent.get("temperature", 0.7))
    max_tokens = int(agent.get("max_tokens", 512))
    if not base_url:
        return False, "", "base_url not configured"
    try:
        if provider == "ollama":
            r = requests.post(f"{base_url}/api/chat", json={
                "model": model, "messages": messages, "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            return True, ((r.json().get("message") or {}).get("content") or ""), None
        # OpenAI-compatible: openai_compatible / lmstudio / llama_cpp / vllm / custom
        r = requests.post(f"{base_url}/v1/chat/completions", json={
            "model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return True, r.json()["choices"][0]["message"]["content"], None
    except Exception as exc:
        return False, "", str(exc)


def _ensure_state(agent: dict) -> dict:
    name = agent.get("name", "agent")
    st = _state.get(name)
    if st is None:
        st = _state[name] = {
            "name": name, "role": agent.get("role", ""), "status": "idle",
            "current_task": None, "last_reply": "", "transcript": [],
            "error": None, "tasks_done": 0, "updated_at": int(time.time() * 1000),
        }
    return st


def run_task(name: str, task: str) -> dict:
    """Synchronously run one task for an agent (the background worker entrypoint).

    Raises KeyError if the agent is not defined.
    """
    agent = _agent_def(name)
    if not agent:
        raise KeyError(name)

    now = int(time.time() * 1000)
    with _lock:
        st = _ensure_state(agent)
        st.update(status="working", current_task=task, error=None, updated_at=now)
        st["transcript"].append({"role": "user", "content": task, "ts": now})
        recent = [m for m in st["transcript"] if m["role"] in ("user", "assistant")][-MAX_TURNS:]
    # Pull relevant notes from the Obsidian vault (if configured and not opted out).
    system = _persona(agent)
    if memory.enabled() and agent.get("memory", True):
        ctx = memory.context_for(task)
        if ctx:
            system = f"{system}\n\n{ctx}"
    tools_on = tooling.enabled() and agent.get("tools", True)
    if tools_on:
        system = f"{system}\n\n{tooling.prompt_hint()}"
    messages = [{"role": "system", "content": system}] + \
               [{"role": m["role"], "content": m["content"]} for m in recent]

    ok, text, err = _chat(agent, messages)  # network call outside the lock

    done = int(time.time() * 1000)
    with _lock:
        st = _ensure_state(agent)
        st["current_task"] = None
        st["updated_at"] = done
        if ok:
            st.update(status="idle", last_reply=text, error=None)
            st["tasks_done"] += 1
            st["transcript"].append({"role": "assistant", "content": text, "ts": done})
        else:
            st.update(status="error", error=err)
            st["transcript"].append({"role": "assistant", "content": f"(error: {err})", "ts": done})
        if len(st["transcript"]) > MAX_TURNS * 2:
            del st["transcript"][:-MAX_TURNS * 2]
        snap = dict(st)

    # If the agent requested a tool, queue it for approval (never auto-run here).
    if ok and tools_on:
        req = tooling.parse_request(text)
        if req:
            try:
                tooling.request_tool(name, req["tool"], req.get("args"))
            except ValueError:
                pass  # invalid request is surfaced only as the agent's own text
    return snap


def assign_task(name: str, task: str) -> dict:
    """Queue a task for an agent and return immediately (runs in the background)."""
    agent = _agent_def(name)
    if not agent:
        raise KeyError(name)
    with _lock:
        st = _ensure_state(agent)
        st.update(status="queued", current_task=task, updated_at=int(time.time() * 1000))
        snap = dict(st)
    _pool.submit(run_task, name, task)
    return snap


def snapshot() -> list[dict]:
    """Compact list of all defined agents merged with their live runtime state."""
    out = []
    with _lock:
        for a in load_agents():
            name = a.get("name", "agent")
            st = _state.get(name)
            out.append({
                "name": name,
                "role": a.get("role", ""),
                "model": a.get("model") or a.get("default_model") or "unknown",
                "provider": a.get("provider", "openai_compatible"),
                "status": st["status"] if st else "idle",
                "current_task": st["current_task"] if st else None,
                "last_reply": st["last_reply"] if st else "",
                "tasks_done": st["tasks_done"] if st else 0,
                "transcript_len": len(st["transcript"]) if st else 0,
                "error": st["error"] if st else None,
            })
    return out


def get_agent(name: str) -> dict | None:
    """Full detail for one agent, including persona and transcript."""
    a = _agent_def(name)
    if not a:
        return None
    with _lock:
        st = _state.get(name)
        return {
            "name": name,
            "role": a.get("role", ""),
            "persona": _persona(a),
            "model": a.get("model") or a.get("default_model") or "unknown",
            "provider": a.get("provider", "openai_compatible"),
            "status": st["status"] if st else "idle",
            "current_task": st["current_task"] if st else None,
            "error": st["error"] if st else None,
            "tasks_done": st["tasks_done"] if st else 0,
            "transcript": list(st["transcript"]) if st else [],
        }


def clear() -> None:
    with _lock:
        _state.clear()
