"""Optional SQLite persistence (opt-in via the MAYBOT_DB env var).

When MAYBOT_DB is unset every function is a no-op and the modules keep their
in-memory behavior. When it points at a file (or ``:memory:``) the modules
write through to it and reload prior state on startup, so metrics history,
agent transcripts, the comms feed, and — most importantly — the guarded-tools
**audit log** survive a restart.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

DB_PATH = os.getenv("MAYBOT_DB", "")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS history (device TEXT, project TEXT, ts INTEGER, pnl REAL, health TEXT)",
    "CREATE TABLE IF NOT EXISTS transcript (agent TEXT, role TEXT, content TEXT, ts INTEGER)",
    "CREATE TABLE IF NOT EXISTS comms (mission INTEGER, sender TEXT, kind TEXT, content TEXT, ts INTEGER)",
    ("CREATE TABLE IF NOT EXISTS tool_calls (id INTEGER PRIMARY KEY, requester TEXT, tool TEXT, "
     "args TEXT, status TEXT, output TEXT, code INTEGER, created_at INTEGER, finished_at INTEGER)"),
    ("CREATE TABLE IF NOT EXISTS usage (agent TEXT, model TEXT, ok INTEGER, latency_ms INTEGER, "
     "tin INTEGER, tout INTEGER, cost REAL, ts INTEGER)"),
    ("CREATE TABLE IF NOT EXISTS cultivation (agent TEXT PRIMARY KEY, stones INTEGER, realm INTEGER, "
     "skills TEXT, breakthroughs INTEGER, updated_at INTEGER)"),
    ("CREATE TABLE IF NOT EXISTS treasury (id INTEGER PRIMARY KEY CHECK (id = 1), balance INTEGER, "
     "last_accrual REAL, income INTEGER, spent INTEGER)"),
]


def enabled() -> bool:
    return bool(DB_PATH)


def _connect() -> sqlite3.Connection | None:
    global _conn
    if not DB_PATH:
        return None
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        if DB_PATH != ":memory:":
            _conn.execute("PRAGMA journal_mode=WAL")
        for s in _SCHEMA:
            _conn.execute(s)
        _conn.commit()
    return _conn


def init() -> None:
    with _lock:
        _connect()


def _exec(sql: str, params: tuple = ()) -> None:
    if not DB_PATH:
        return
    with _lock:
        c = _connect()
        if c is not None:
            c.execute(sql, params)
            c.commit()


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    if not DB_PATH:
        return []
    with _lock:
        c = _connect()
        if c is None:
            return []
        return list(c.execute(sql, params).fetchall())


# ---- history ----
def add_history(device: str, project: str, point: dict) -> None:
    _exec("INSERT INTO history (device, project, ts, pnl, health) VALUES (?,?,?,?,?)",
          (device, project, point.get("ts"), point.get("pnl"), point.get("health")))


def load_history() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for device, project, ts, pnl, health in _query(
            "SELECT device, project, ts, pnl, health FROM history ORDER BY ts ASC"):
        out.setdefault(f"{device}:{project}", []).append({"ts": ts, "pnl": pnl, "health": health})
    return out


# ---- transcripts ----
def add_transcript(agent: str, msg: dict) -> None:
    _exec("INSERT INTO transcript (agent, role, content, ts) VALUES (?,?,?,?)",
          (agent, msg.get("role"), msg.get("content"), msg.get("ts")))


def load_transcripts() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for agent, role, content, ts in _query(
            "SELECT agent, role, content, ts FROM transcript ORDER BY ts ASC"):
        out.setdefault(agent, []).append({"role": role, "content": content, "ts": ts})
    return out


# ---- comms ----
def add_comms(msg: dict) -> None:
    _exec("INSERT INTO comms (mission, sender, kind, content, ts) VALUES (?,?,?,?,?)",
          (msg.get("mission"), msg.get("from"), msg.get("kind"), msg.get("content"), msg.get("ts")))


def load_comms(limit: int = 200) -> list[dict]:
    rows = _query("SELECT rowid, mission, sender, kind, content, ts FROM comms ORDER BY rowid DESC LIMIT ?", (limit,))
    rows.reverse()
    return [{"id": rid, "mission": m, "from": s, "kind": k, "content": c, "ts": t}
            for (rid, m, s, k, c, t) in rows]


# ---- tool calls (audit log) ----
def upsert_tool_call(call: dict) -> None:
    _exec(
        "INSERT OR REPLACE INTO tool_calls (id, requester, tool, args, status, output, code, created_at, finished_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (call.get("id"), call.get("requester"), call.get("tool"), json.dumps(call.get("args") or {}),
         call.get("status"), call.get("output"), call.get("code"), call.get("created_at"), call.get("finished_at")),
    )


def load_tool_calls(limit: int = 100) -> list[dict]:
    rows = _query(
        "SELECT id, requester, tool, args, status, output, code, created_at, finished_at"
        " FROM tool_calls ORDER BY id DESC LIMIT ?", (limit,))
    rows.reverse()
    out = []
    for (cid, requester, tool, args, status, output, code, created, finished) in rows:
        try:
            parsed = json.loads(args) if args else {}
        except Exception:
            parsed = {}
        out.append({"id": cid, "requester": requester, "tool": tool, "args": parsed,
                    "status": status, "output": output, "code": code,
                    "created_at": created, "finished_at": finished})
    return out


# ---- usage ----
def add_usage(agent: str, model: str, ok: bool, latency_ms: int, tin: int, tout: int, cost: float, ts: int) -> None:
    _exec("INSERT INTO usage (agent, model, ok, latency_ms, tin, tout, cost, ts) VALUES (?,?,?,?,?,?,?,?)",
          (agent, model, int(bool(ok)), latency_ms, tin, tout, cost, ts))


def load_usage(limit: int = 20000) -> list[tuple]:
    return _query("SELECT agent, model, ok, latency_ms, tin, tout, cost, ts FROM usage ORDER BY ts ASC LIMIT ?", (limit,))


# ---- cultivation ----
def upsert_cultivation(s: dict) -> None:
    _exec("INSERT OR REPLACE INTO cultivation (agent, stones, realm, skills, breakthroughs, updated_at) VALUES (?,?,?,?,?,?)",
          (s.get("agent"), s.get("stones", 0), s.get("realm", 0), json.dumps(s.get("skills") or []),
           s.get("breakthroughs", 0), s.get("updated_at", 0)))


def load_cultivation() -> list[tuple]:
    return _query("SELECT agent, stones, realm, skills, breakthroughs, updated_at FROM cultivation")


# ---- sect treasury ----
def set_treasury(balance: int, last_accrual: float, income: int, spent: int) -> None:
    _exec("INSERT OR REPLACE INTO treasury (id, balance, last_accrual, income, spent) VALUES (1,?,?,?,?)",
          (balance, last_accrual, income, spent))


def get_treasury() -> tuple | None:
    rows = _query("SELECT balance, last_accrual, income, spent FROM treasury WHERE id = 1")
    return rows[0] if rows else None


def _reset_for_tests(path: str) -> None:
    """Test helper: point at a fresh DB and drop the cached connection."""
    global DB_PATH, _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        DB_PATH = path
