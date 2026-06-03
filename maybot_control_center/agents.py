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
from . import store
from . import events
from . import autonomy
from . import usage
from . import cultivation
from . import tools as tooling

AGENTS_FILE = Path(os.getenv("MAYBOT_AGENTS_FILE", "agents.yaml"))
DEFAULT_TIMEOUT = int(os.getenv("MAYBOT_AGENT_TIMEOUT", "60"))
MAX_TURNS = max(2, int(os.getenv("MAYBOT_AGENT_MAX_TURNS", "20")))  # transcript messages kept for context
# Tool loop: how many times a tool result may be fed back to an agent before a
# fresh (operator) task is required. Bounds runaway propose→run→continue loops.
MAX_FOLLOWUPS = max(0, int(os.getenv("MAYBOT_AGENT_MAX_FOLLOWUPS", "4")))
# Inner demon: a self-critique/revision pass after each reply (opt-in).
INNER_DEMON_GLOBAL = os.getenv("MAYBOT_INNER_DEMON", "0").lower() in ("1", "true", "yes", "on")

_lock = threading.Lock()
_state: dict[str, dict] = {}
_followups: dict[str, int] = {}
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

    name = agent.get("name", "?")
    model = agent.get("model") or "claude-opus-4-8"
    max_tokens = int(agent.get("max_tokens", 1024))
    system_text = next((m["content"] for m in messages if m["role"] == "system"), _persona(agent))
    convo = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
    t0 = time.time()
    try:
        resp = _anthropic_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            # Stable persona first, cached so repeat turns reuse the prefix.
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            messages=convo,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        u = getattr(resp, "usage", None)
        tin = getattr(u, "input_tokens", 0) or 0
        tout = getattr(u, "output_tokens", 0) or 0
        usage.record(name, model, True, int((time.time() - t0) * 1000), tin, tout)
        return True, text, None
    except anthropic.AuthenticationError:
        usage.record(name, model, False, int((time.time() - t0) * 1000))
        return False, "", "Claude API authentication failed — set ANTHROPIC_API_KEY"
    except Exception as exc:
        usage.record(name, model, False, int((time.time() - t0) * 1000))
        return False, "", str(exc)


def _chat(agent: dict, messages: list[dict]) -> tuple[bool, str, str | None]:
    """Run one chat completion against the agent's configured backend."""
    provider = (agent.get("provider") or "openai_compatible").lower()
    if provider in ("claude", "anthropic"):
        return _chat_claude(agent, messages)
    name = agent.get("name", "?")
    base_url = (agent.get("base_url") or "").rstrip("/")
    model = agent.get("model") or agent.get("default_model") or ""
    temperature = float(agent.get("temperature", 0.7))
    max_tokens = int(agent.get("max_tokens", 512))
    if not base_url:
        return False, "", "base_url not configured"
    t0 = time.time()
    tin = tout = 0
    try:
        if provider == "ollama":
            r = requests.post(f"{base_url}/api/chat", json={
                "model": model, "messages": messages, "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            text = (data.get("message") or {}).get("content") or ""
            tin = data.get("prompt_eval_count") or 0
            tout = data.get("eval_count") or 0
        else:
            # OpenAI-compatible: openai_compatible / lmstudio / llama_cpp / vllm / custom
            r = requests.post(f"{base_url}/v1/chat/completions", json={
                "model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens,
            }, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            u = data.get("usage") or {}
            tin = u.get("prompt_tokens") or 0
            tout = u.get("completion_tokens") or 0
        usage.record(name, model, True, int((time.time() - t0) * 1000), tin, tout)
        return True, text, None
    except Exception as exc:
        usage.record(name, model, False, int((time.time() - t0) * 1000))
        return False, "", str(exc)


def _inner_demon_on(agent: dict) -> bool:
    return bool(agent.get("inner_demon")) or INNER_DEMON_GLOBAL


def _inner_demon(agent: dict, task: str, answer: str) -> tuple[str, str | None]:
    """The disciple's inner demon critiques the answer; if flawed, the disciple revises it.

    Returns (final_answer, critique-or-None). Two extra model calls at most.
    """
    name = agent.get("name", "the disciple")
    demon_sys = (f"You are the Inner Demon of {name} — a harsh, exacting critic. Judge the disciple's "
                 f"answer against the task. List concrete errors, flaws, or omissions as terse bullet "
                 f"points. If the answer is fully correct and complete, reply with exactly: NO FLAWS")
    ok, critique, _ = _chat(agent, [
        {"role": "system", "content": demon_sys},
        {"role": "user", "content": f"Task:\n{task}\n\nAnswer:\n{answer}"},
    ])
    if not ok or not critique or critique.strip().upper().startswith("NO FLAWS"):
        return answer, None
    ok2, revised, _ = _chat(agent, [
        {"role": "system", "content": _persona(agent)},
        {"role": "user", "content": (f"Task:\n{task}\n\nYour previous answer:\n{answer}\n\nYour inner demon's "
                                      f"critique:\n{critique}\n\nProduce an improved, corrected final answer that "
                                      f"addresses every valid point. Output only the final answer.")},
    ])
    return (revised if ok2 and revised else answer), critique.strip()


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
    user_msg = {"role": "user", "content": task, "ts": now}
    with _lock:
        st = _ensure_state(agent)
        st.update(status="working", current_task=task, error=None, updated_at=now)
        st["transcript"].append(user_msg)
        recent = [m for m in st["transcript"] if m["role"] in ("user", "assistant")][-MAX_TURNS:]
    if store.enabled():
        store.add_transcript(name, user_msg)
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

    # Inner demon: critique and (if flawed) revise the answer before recording it.
    demon_critique = None
    if ok and _inner_demon_on(agent):
        text, demon_critique = _inner_demon(agent, task, text)

    done = int(time.time() * 1000)
    asst_msg = {"role": "assistant", "content": text if ok else f"(error: {err})", "ts": done}
    demon_msg = {"role": "system", "content": f"⚔ inner demon: {demon_critique}", "ts": done} if demon_critique else None
    with _lock:
        st = _ensure_state(agent)
        st["current_task"] = None
        st["updated_at"] = done
        if ok:
            st.update(status="idle", last_reply=text, error=None)
            st["tasks_done"] += 1
        else:
            st.update(status="error", error=err)
        if demon_msg:
            st["transcript"].append(demon_msg)
        st["transcript"].append(asst_msg)
        if len(st["transcript"]) > MAX_TURNS * 2:
            del st["transcript"][:-MAX_TURNS * 2]
        snap = dict(st)
    if store.enabled():
        if demon_msg:
            store.add_transcript(name, demon_msg)
        store.add_transcript(name, asst_msg)
    cultivation.on_task(name, ok)  # spirit stones for diligent work
    events.publish("agents", {"agent": name})

    # If the agent requested a tool, queue it for approval (never auto-run here).
    if ok and tools_on:
        req = tooling.parse_request(text)
        if req:
            try:
                tooling.request_tool(name, req["tool"], req.get("args"))
            except ValueError:
                pass  # invalid request is surfaced only as the agent's own text
    return snap


def _tool_followup(call: dict) -> None:
    """Tool-loop hook: feed a finished tool's result back to the requesting agent."""
    name = call.get("requester")
    if not name or not _agent_def(name):
        return  # operator-run or unknown requester → no continuation
    # Mastering a technique (new tool) advances cultivation; reward before the budget gate.
    cultivation.on_tool(name, call.get("tool"), call.get("status") == "done")
    with _lock:
        n = _followups.get(name, 0)
        if n >= MAX_FOLLOWUPS:
            return
        _followups[name] = n + 1
    out = (call.get("output") or "")[:2000]
    task = (f"The tool '{call.get('tool')}' you requested returned (status {call.get('status')}):\n"
            f"{out}\n\nContinue toward the original task. Request another tool if you need one; "
            f"otherwise give your final answer.")
    _pool.submit(run_task, name, task)


tooling.on_complete = _tool_followup


def assign_task(name: str, task: str) -> dict:
    """Queue a task for an agent and return immediately (runs in the background)."""
    agent = _agent_def(name)
    if not agent:
        raise KeyError(name)
    with _lock:
        _followups[name] = 0  # operator task resets the tool-loop budget
        autonomy.reset(name)  # ...and the per-task autonomy budget
        st = _ensure_state(agent)
        st.update(status="queued", current_task=task, updated_at=int(time.time() * 1000))
        snap = dict(st)
    events.publish("agents", {"agent": name})
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
                "cultivation": cultivation.state(name),
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


def load_persisted() -> None:
    if not store.enabled():
        return
    transcripts = store.load_transcripts()
    with _lock:
        for name, msgs in transcripts.items():
            agent = _agent_def(name)
            st = _ensure_state(agent or {"name": name})
            st["transcript"] = msgs[-MAX_TURNS * 2:]
            st["tasks_done"] = sum(1 for m in msgs if m["role"] == "assistant")
            last = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant"), "")
            st["last_reply"] = last


def clear() -> None:
    with _lock:
        _state.clear()
        _followups.clear()
