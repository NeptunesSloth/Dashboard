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

import json
import os
import re
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
from . import pills
from . import tools as tooling

AGENTS_FILE = Path(os.getenv("MAYBOT_AGENTS_FILE", "agents.yaml"))
DEFAULT_TIMEOUT = int(os.getenv("MAYBOT_AGENT_TIMEOUT", "60"))
MAX_TURNS = max(2, int(os.getenv("MAYBOT_AGENT_MAX_TURNS", "20")))  # transcript messages kept for context
# Tool loop: how many times a tool result may be fed back to an agent before a
# fresh (operator) task is required. Bounds runaway propose→run→continue loops.
MAX_FOLLOWUPS = max(0, int(os.getenv("MAYBOT_AGENT_MAX_FOLLOWUPS", "4")))
# Inner demon: a self-critique/revision pass after each reply (opt-in).
INNER_DEMON_GLOBAL = os.getenv("MAYBOT_INNER_DEMON", "0").lower() in ("1", "true", "yes", "on")
# Delegation: a disciple may hand a task to a LOWER-ranked disciple (by cultivation
# realm). Operator-driven delegation is always available; agent-initiated (autonomous)
# delegation is opt-in and bounded per task.
DELEGATION_GLOBAL = os.getenv("MAYBOT_DELEGATION", "0").lower() in ("1", "true", "yes", "on")
MAX_DELEGATIONS = max(0, int(os.getenv("MAYBOT_AGENT_MAX_DELEGATIONS", "3")))
_delegations: dict[str, int] = {}
_DELEGATE_BLOCK = re.compile(r"```delegate\s+(\{.*?\})\s*```", re.DOTALL)

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


def _demon_cycles(realm: int) -> int:
    """The inner demon is harshest when the disciple is weakest (low realm), easing as it ascends."""
    return max(0, 3 - (realm + 1) // 2)  # Mortal:3, Qi/Foundation:2, Core/Nascent:1, Soul+:0


def _demon_tone(realm: int) -> str:
    if realm <= 1:
        return "merciless and exacting — nitpick every imprecision, unstated assumption, and possible error"
    if realm <= 3:
        return "exacting — flag concrete errors, flaws, and omissions"
    return "discerning — flag only genuine errors or omissions; ignore matters of style"


def _inner_demon(agent: dict, task: str, answer: str, realm: int) -> tuple[str, str | None]:
    """One critique→revise cycle. Returns (answer, critique-or-None when clean)."""
    name = agent.get("name", "the disciple")
    demon_sys = (f"You are the Inner Demon of {name} — {_demon_tone(realm)}. Judge the disciple's answer "
                 f"against the task. List concrete errors, flaws, or omissions as terse bullet points. "
                 f"If the answer is fully correct and complete, reply with exactly: NO FLAWS")
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
    try:
        from . import governance
        system = f"{system}\n\n{governance.persona_context(name)}"
    except Exception:
        pass  # governance is an optional layer
    if memory.enabled() and agent.get("memory", True):
        ctx = memory.context_for(task)
        if ctx:
            system = f"{system}\n\n{ctx}"
    tools_on = tooling.enabled() and agent.get("tools", True)
    if tools_on:
        system = f"{system}\n\n{tooling.prompt_hint()}"
    if DELEGATION_GLOBAL:
        hint = _delegate_hint(name)
        if hint:
            system = f"{system}\n\n{hint}"
    messages = [{"role": "system", "content": system}] + \
               [{"role": m["role"], "content": m["content"]} for m in recent]

    # Apply any active pill buffs (stronger model / deeper response) to this call.
    boost = pills.effects(name)
    agent_eff = dict(agent)
    if boost.get("model"):
        agent_eff["model"] = boost["model"]
    if boost.get("max_tokens"):
        agent_eff["max_tokens"] = int(agent.get("max_tokens", 1024)) + int(boost["max_tokens"])

    ok, text, err = _chat(agent_eff, messages)  # network call outside the lock

    # Inner demon: harsher at low realms (and with a Heart-Demon pill); revise until clean.
    demon_critique = None
    if ok:
        realm = cultivation.realm_of(name)
        cycles = (_demon_cycles(realm) if _inner_demon_on(agent) else 0) + int(boost.get("inner_demon", 0))
        for _ in range(cycles):
            text, crit = _inner_demon(agent_eff, task, text, realm)
            if crit is None:
                break
            demon_critique = crit

    # Karmic-bond peer review: a bonded partner critiques the work before it ships.
    peer_review = None
    if ok:
        try:
            from . import bonds
            reviewer = bonds.reviewer_for(name)
            if reviewer and reviewer != name:
                peer_review = _peer_review(reviewer, name, task, text)
        except Exception:
            peer_review = None

    done = int(time.time() * 1000)
    asst_msg = {"role": "assistant", "content": text if ok else f"(error: {err})", "ts": done}
    demon_msg = {"role": "system", "content": f"⚔ inner demon: {demon_critique}", "ts": done} if demon_critique else None
    peer_msg = {"role": "system", "content": f"🤝 peer review by {reviewer}: {peer_review}", "ts": done} if peer_review else None
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
        if peer_msg:
            st["transcript"].append(peer_msg)
        if len(st["transcript"]) > MAX_TURNS * 2:
            del st["transcript"][:-MAX_TURNS * 2]
        snap = dict(st)
    if store.enabled():
        if demon_msg:
            store.add_transcript(name, demon_msg)
        store.add_transcript(name, asst_msg)
        if peer_msg:
            store.add_transcript(name, peer_msg)
    cultivation.on_task(name, ok)  # spirit stones for diligent work
    try:  # Dao-Heart drift: record this output's quality signals
        from . import daoheart
        daoheart.record(name, {"ok": ok, "chars": len(text or ""), "latency_ms": max(0, done - now)})
    except Exception:
        pass
    events.publish("agents", {"agent": name})

    # If the agent requested a tool, queue it for approval (never auto-run here).
    if ok and tools_on:
        req = tooling.parse_request(text)
        if req:
            try:
                tooling.request_tool(name, req["tool"], req.get("args"))
            except ValueError:
                pass  # invalid request is surfaced only as the agent's own text

    # Agent-initiated delegation (opt-in): hand a subtask down the hierarchy, bounded.
    if ok and DELEGATION_GLOBAL:
        dreq = _parse_delegate(text)
        if dreq:
            with _lock:
                n = _delegations.get(name, 0)
            if n < MAX_DELEGATIONS and can_delegate(name, dreq["to"]):
                with _lock:
                    _delegations[name] = n + 1
                try:
                    delegate(name, dreq["to"], dreq["task"])
                except Exception:
                    pass
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


def can_delegate(delegator: str, delegate: str) -> bool:
    """A disciple may delegate only DOWNWARD — to one of strictly lower cultivation realm."""
    if delegator == delegate or not (_agent_def(delegator) and _agent_def(delegate)):
        return False
    return cultivation.realm_of(delegator) > cultivation.realm_of(delegate)


def subordinates(name: str) -> list[str]:
    """Names this disciple outranks (and may delegate to)."""
    my = cultivation.realm_of(name)
    return [a.get("name") for a in load_agents()
            if a.get("name") and a.get("name") != name and cultivation.realm_of(a["name"]) < my]


def delegate(delegator: str, delegate: str, task: str) -> dict:
    """Hand a task down the sect hierarchy. Raises PermissionError if rank is insufficient."""
    if not can_delegate(delegator, delegate):
        raise PermissionError(f"{delegator} may not delegate to {delegate} (must outrank them)")
    from . import comms  # lazy import to avoid an import cycle
    comms._post("system", f"📜 {delegator} delegates a task to {delegate}.", "system")
    cultivation.on_council(delegator)  # leading the sect is meritorious
    return assign_task(delegate, f"[Delegated by {delegator}] {task}")


def transmit(teacher: str, student: str, skill: str) -> dict:
    """A higher-ranked disciple passes one of its techniques down to a subordinate."""
    if not can_delegate(teacher, student):  # must strictly outrank
        raise PermissionError(f"{teacher} may not teach {student} (must outrank them)")
    if skill not in cultivation.state(teacher)["skills"]:
        raise ValueError(f"{teacher} does not know the {skill} technique")
    if skill in cultivation.state(student)["skills"]:
        raise ValueError(f"{student} already knows {skill}")
    cultivation.learn(student, skill, bonus=cultivation.AWARD_NEW_SKILL // 2)
    cultivation.on_council(teacher)  # mentoring is meritorious
    from . import comms, lineage
    lineage.record_transmission(teacher, student, skill)  # knowledge-transfer graph
    comms._post("system", f"📜 {teacher} transmits the {skill} technique to {student}.", "system")
    return cultivation.state(student)


def _peer_review(reviewer_name: str, author: str, task: str, text: str) -> str | None:
    """A karmic-bonded partner critiques the author's work before it ships."""
    rev = _agent_def(reviewer_name)
    if not rev:
        return None
    sys = (f"{_persona(rev)}\n\nYou are {reviewer_name}, karmic-bonded to {author} as their reviewer. "
           f"Check their work for correctness and quality before it ships. Reply 'APPROVE' if sound, "
           f"otherwise 'REVISE:' and the single most important issue. Be terse.")
    user = f"Task: {task}\n\n{author}'s output:\n{text}\n\nYour review:"
    ok, out, _ = _chat(rev, [{"role": "system", "content": sys}, {"role": "user", "content": user}])
    return (out or "").strip()[:1000] if ok else None


def _parse_delegate(text: str) -> dict | None:
    m = _DELEGATE_BLOCK.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except Exception:
        return None
    if isinstance(obj, dict) and obj.get("to") and obj.get("task"):
        return {"to": str(obj["to"]), "task": str(obj["task"])}
    return None


def _delegate_hint(name: str) -> str:
    subs = subordinates(name)
    if not subs:
        return ""
    return ("You may delegate ONE subtask to a lower-ranked disciple by ending your reply with:\n"
            '```delegate\n{"to": "<name>", "task": "<subtask>"}\n```\n'
            f"Disciples you may delegate to: {', '.join(subs)}")


def assign_task(name: str, task: str) -> dict:
    """Queue a task for an agent and return immediately (runs in the background)."""
    agent = _agent_def(name)
    if not agent:
        raise KeyError(name)
    with _lock:
        _followups[name] = 0  # operator task resets the tool-loop budget
        _delegations[name] = 0  # ...and the delegation budget
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
            cultivation.grant_stipend(name)  # daily spirit-stone stipend (no-op unless due)
            cultivation.tick_seclusion(name)  # mature any closed-door seclusion into a breakthrough
            cultivation.tick_roaming(name)    # return any roaming disciple with a discovery
            st = _state.get(name)
            cultivation.auto_retreat_tick(name, st["status"] if st else "idle")  # idle disciples retreat on their own
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
                "sprite": a.get("sprite"),   # optional fixed map sprite (e.g. "demon")
                "skin": a.get("skin"),       # optional character skin set (e.g. "elder")
            })
    from . import reputation, governance, titles, bonds
    governance.throne_cultivation()  # the Sect Leader passively gains qi while presiding
    leader = governance.leader()
    if leader:  # an idle Leader walks the sect, mentoring a junior disciple
        ld_row = next((r for r in out if r["name"] == leader), None)
        ld_cult = ld_row.get("cultivation", {}) if ld_row else {}
        governance.leader_guidance(
            ld_row["status"] if ld_row else "idle",
            in_retreat=bool(ld_cult.get("in_seclusion") or ld_cult.get("in_roaming")),
        )
    for row in out:
        name = row["name"]
        row["reputation"] = reputation.score(name)
        row["governance"] = {
            "is_leader": name == leader,
            "is_elder": governance.is_elder(name),
            "is_master": governance.is_master(name),
            "specialty": governance.specialty(name),
            "mastery": governance.mastery(name),
            "standing": governance.standing(name)["score"],
        }
        row["titles"] = titles.evaluate(name)
        row["bond"] = bonds.partner(name)
    return out


def tasks_done(name: str) -> int:
    """How many tasks this agent has completed (0 if it has no runtime state yet)."""
    with _lock:
        st = _state.get(name)
        return int(st["tasks_done"]) if st else 0


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
        _delegations.clear()
