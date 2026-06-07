"""Phase 4: guarded tools — let agents *act*, behind an allow-list + approvals.

Security model (deny-by-default):
- Agents can only invoke tools explicitly defined in ``tools.yaml``. Nothing
  else is runnable. No tools file → the feature is off.
- Tools run as a **fixed argv with no shell** (``subprocess.run([...])``). The
  command and working directory come from the tool definition, never from the
  agent.
- An agent may only fill **named ``{placeholder}`` args** declared by the tool,
  and each value is validated against a conservative pattern before use — so an
  agent can parameterize a tool but cannot inject a new command or shell
  metacharacters.
- Every invocation is **pending until a human approves it** in the dashboard,
  unless the tool sets ``auto_approve: true`` (intended for safe, read-only
  tools). Denials are recorded; nothing runs on a denied call.

State is in-memory and resets on restart.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import yaml

from . import store
from . import events
from . import autonomy

TOOLS_FILE = Path(os.getenv("MAYBOT_TOOLS_FILE", "tools.yaml"))
MAX_CALLS = 100
OUTPUT_CAP = 8000

# Conservative allowed value for an agent-supplied arg: no spaces, no shell
# metacharacters, bounded length. Operators can keep tools narrow; this is a
# second line of defence on top of the no-shell argv execution.
_ARG_RE = re.compile(r"^[A-Za-z0-9_./:@=+-]{1,200}$")
_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_TOOL_BLOCK = re.compile(r"```tool\s+(\{.*?\})\s*```", re.DOTALL)

_lock = threading.Lock()
_calls: list[dict] = []
_seq = 0

# Optional hook fired when a call finishes (set by agents.py for the tool loop).
on_complete = None


def _notify_complete(call: dict) -> None:
    cb = on_complete
    if cb and call.get("status") in ("done", "failed", "error"):
        try:
            cb(call)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Built-in, read-only OBSERVABILITY tools — always available to disciples so they
# can see a bot's PnL/status and tail its logs. These do NOT shell out; they read
# the same data the dashboard already exposes, and auto-approve (read-only).
# ---------------------------------------------------------------------------
def _builtin_bot_status(args: dict) -> str:
    from . import config
    from .agent_client import call_agent
    project = (args.get("project") or "").strip()
    device = (args.get("device") or "").strip()
    if not project:
        return "usage: bot_status needs a 'project' (bot) name, optionally a 'device' (host)."
    for d in config.all_devices():
        if device and d.get("name") != device:
            continue
        pl = call_agent(d, "/api/projects").get("data", [])
        if isinstance(pl, list):
            p = next((x for x in pl if x.get("name") == project), None)
            if p:
                m = p.get("metrics", {}) or {}
                out = [f"{project} @ {d.get('name')} — status={p.get('status')} "
                       f"health={p.get('health')} type={p.get('type')}"]
                for k in ("profit_today", "profit_this_week", "realized_pnl", "unrealized_pnl",
                          "open_positions", "open_exposure", "trades_today", "fill_rate",
                          "last_trade_time"):
                    v = m.get(k)
                    if v not in (None, "", "unknown"):
                        out.append(f"{k}: {v}")
                for a in (p.get("alerts") or [])[:5]:
                    out.append(f"alert: {a}")
                return "\n".join(out)
        if device:
            break
    return f"no bot named '{project}'" + (f" on host '{device}'" if device else " on any host")


def _builtin_bot_logs(args: dict) -> str:
    from . import config
    from .agent_client import call_agent
    project = (args.get("project") or "").strip()
    device = (args.get("device") or "").strip()
    level = (args.get("level") or "ALL").strip().upper()
    if level not in {"ALL", "ERROR", "WARNING", "INFO"}:
        level = "ALL"
    if not project:
        return "usage: bot_logs needs a 'project' (bot) name, optionally 'device' and 'level'."
    for d in config.all_devices():
        if device and d.get("name") != device:
            continue
        pl = call_agent(d, "/api/projects").get("data", [])
        names = [x.get("name") for x in pl] if isinstance(pl, list) else []
        if project in names:
            lg = call_agent(d, f"/api/projects/{project}/logs?level={level}").get("data", {})
            lines = lg.get("lines") if isinstance(lg, dict) else None
            if isinstance(lines, list) and lines:
                return "\n".join(str(x) for x in lines[-40:])
            return f"(no {level} log lines for '{project}')"
        if device:
            break
    return f"no bot named '{project}'" + (f" on host '{device}'" if device else " on any host")


_BUILTINS: dict = {
    "bot_status": {
        "description": "Read a bot/project's live status and PnL metrics (profit today/week, positions, fill rate, alerts).",
        "args": ["project", "device"], "auto_approve": True, "handler": _builtin_bot_status,
    },
    "bot_logs": {
        "description": "Tail a bot/project's recent logs to see what it's doing (level is ALL|ERROR|WARNING|INFO).",
        "args": ["project", "device", "level"], "auto_approve": True, "handler": _builtin_bot_logs,
    },
}


def load_tools() -> list[dict]:
    if not TOOLS_FILE.exists():
        return []
    data = yaml.safe_load(TOOLS_FILE.read_text(encoding="utf-8")) or {}
    tools = data.get("tools", [])
    return tools if isinstance(tools, list) else []


def _all_tool_defs() -> list[dict]:
    """Built-in observability tools first, then operator-defined yaml tools."""
    builtins = [{"name": n, "description": s["description"], "args": list(s["args"]),
                 "auto_approve": bool(s["auto_approve"])} for n, s in _BUILTINS.items()]
    return builtins + load_tools()


def enabled() -> bool:
    # Built-ins are always available, so the tool channel is always on.
    return bool(_BUILTINS) or bool(load_tools())


def _tool_def(name: str) -> dict | None:
    return next((t for t in load_tools() if t.get("name") == name), None)


def tool_summaries() -> list[dict]:
    return [{
        "name": t.get("name"),
        "description": t.get("description", ""),
        "args": list(t.get("args", [])),
        "auto_approve": bool(t.get("auto_approve")),
        "builtin": t.get("name") in _BUILTINS,
    } for t in _all_tool_defs()]


def prompt_hint() -> str:
    lines = [
        "You may request ONE tool by ending your reply with a fenced block exactly like:",
        "```tool",
        '{"tool": "<name>", "args": {"<arg>": "<value>"}}',
        "```",
        "Read-only tools run immediately; others need a human to approve. Available tools:",
    ]
    for t in _all_tool_defs():
        args = ", ".join(t.get("args", [])) or "none"
        lines.append(f"- {t.get('name')}: {t.get('description', '')} (args: {args})")
    return "\n".join(lines)


def _validate_args(tool: dict, args: dict | None) -> dict:
    args = args or {}
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    declared = set(tool.get("args", []))
    needed = set()
    for part in tool.get("argv", []):
        needed |= set(_PLACEHOLDER.findall(str(part)))
    clean = {}
    for k, v in args.items():
        if k not in declared:
            raise ValueError(f"unknown arg '{k}'")
        sv = str(v)
        if not _ARG_RE.match(sv):
            raise ValueError(f"invalid value for arg '{k}'")
        clean[k] = sv
    for n in needed:
        if n not in clean:
            raise ValueError(f"missing required arg '{n}'")
    return clean


def _build_argv(tool: dict, args: dict) -> list[str]:
    return [_PLACEHOLDER.sub(lambda m: args.get(m.group(1), ""), str(part))
            for part in tool.get("argv", [])]


def _find(call_id: int) -> dict | None:
    return next((c for c in _calls if c["id"] == call_id), None)


def _run_builtin(requester: str, name: str, spec: dict, args: dict | None) -> dict:
    """Execute a built-in observability tool in-process (read-only, auto-approved)."""
    global _seq
    declared = set(spec.get("args", []))
    clean = {k: str(v) for k, v in (args or {}).items() if k in declared}
    with _lock:
        _seq += 1
        call = {
            "id": _seq, "requester": requester, "tool": name, "args": clean,
            "status": "running", "created_at": int(time.time() * 1000),
            "output": None, "code": None, "builtin": True,
        }
        _calls.append(call)
        if len(_calls) > MAX_CALLS:
            del _calls[:-MAX_CALLS]
        call_id = call["id"]
    try:
        output, status, code = (str(spec["handler"](clean) or "")[:OUTPUT_CAP], "done", 0)
    except Exception as exc:  # noqa: BLE001
        output, status, code = (f"error: {exc}", "error", None)
    with _lock:
        call = _find(call_id)
        if call:
            call.update(status=status, output=output, code=code, finished_at=int(time.time() * 1000))
            snap = dict(call)
        else:
            snap = None
    if snap is not None:
        if store.enabled():
            store.upsert_tool_call(snap)
        events.publish("tools", {"id": snap["id"], "status": snap["status"]})
        _notify_complete(snap)
    return snap


def request_tool(requester: str, tool_name: str, args: dict | None = None) -> dict:
    """Request a tool run. Creates a pending call (or runs it if auto_approve)."""
    global _seq
    builtin = _BUILTINS.get(tool_name)
    if builtin:
        return _run_builtin(requester, tool_name, builtin, args)
    tool = _tool_def(tool_name)
    if not tool:
        raise ValueError(f"unknown tool '{tool_name}'")
    clean = _validate_args(tool, args)
    with _lock:
        _seq += 1
        call = {
            "id": _seq, "requester": requester, "tool": tool_name, "args": clean,
            "status": "pending", "created_at": int(time.time() * 1000),
            "output": None, "code": None,
        }
        _calls.append(call)
        if len(_calls) > MAX_CALLS:
            del _calls[:-MAX_CALLS]
        call_id = call["id"]
        snap = dict(call)
    # Decide autonomy OUTSIDE the lock: reputation re-reads the tool audit log
    # (list_calls), which re-acquires _lock — doing this inside would deadlock.
    auto = autonomy.allow(requester, tool)
    if store.enabled():
        store.upsert_tool_call(snap)
    events.publish("tools", {"id": snap["id"], "status": snap["status"]})
    return _execute(call_id) if auto else snap


def _execute(call_id: int) -> dict | None:
    with _lock:
        call = _find(call_id)
        if not call or call["status"] not in ("pending", "approved"):
            return dict(call) if call else None
        tool = _tool_def(call["tool"])
        if not tool:
            call.update(status="error", output="tool no longer defined")
            return dict(call)
        call["status"] = "running"
        argv = _build_argv(tool, call["args"])
        cwd = tool.get("cwd")
        timeout = int(tool.get("timeout_seconds", 60))

    try:
        if cwd and not Path(cwd).is_dir():
            raise FileNotFoundError(f"cwd not found: {cwd}")
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        output = ((r.stdout or "") + ("\n" + r.stderr if r.stderr else "")).strip()[:OUTPUT_CAP]
        status, code = ("done" if r.returncode == 0 else "failed"), r.returncode
    except FileNotFoundError as exc:
        output, status, code = str(exc), "error", None
    except subprocess.TimeoutExpired:
        output, status, code = f"timed out after {timeout}s", "error", None
    except Exception as exc:  # noqa: BLE001
        output, status, code = str(exc), "error", None

    with _lock:
        call = _find(call_id)
        if call:
            call.update(status=status, output=output, code=code, finished_at=int(time.time() * 1000))
            snap = dict(call)
        else:
            snap = None
    if snap is not None:
        if store.enabled():
            store.upsert_tool_call(snap)
        events.publish("tools", {"id": snap["id"], "status": snap["status"]})
        _notify_complete(snap)
    return snap


def approve(call_id: int) -> dict:
    with _lock:
        call = _find(call_id)
        if not call:
            raise KeyError(call_id)
        if call["status"] != "pending":
            return dict(call)
        call["status"] = "approved"
    return _execute(call_id)


def deny(call_id: int) -> dict:
    with _lock:
        call = _find(call_id)
        if not call:
            raise KeyError(call_id)
        if call["status"] == "pending":
            call["status"] = "denied"
        snap = dict(call)
    if store.enabled():
        store.upsert_tool_call(snap)
    events.publish("tools", {"id": snap["id"], "status": snap["status"]})
    return snap


def list_calls(limit: int = 50) -> list[dict]:
    with _lock:
        return [dict(c) for c in _calls[-limit:]]


def parse_request(text: str) -> dict | None:
    """Extract a ```tool {...}``` request from an agent's reply, if present."""
    m = _TOOL_BLOCK.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except Exception:
        return None
    if isinstance(obj, dict) and obj.get("tool"):
        return {"tool": str(obj["tool"]), "args": obj.get("args") or {}}
    return None


def load_persisted() -> None:
    global _seq
    if not store.enabled():
        return
    rows = store.load_tool_calls(MAX_CALLS)
    with _lock:
        _calls.clear()
        _calls.extend(rows)
        _seq = max((c.get("id") or 0 for c in _calls), default=0)


def clear() -> None:
    with _lock:
        _calls.clear()
