"""Optional persistence (opt-in via the MAYBOT_DB env var).

When MAYBOT_DB is unset every function is a no-op and the modules keep their
in-memory behavior. When it points at a file (or ``:memory:``) the modules
write through to it and reload prior state on startup, so metrics history,
agent transcripts, the comms feed, and — most importantly — the guarded-tools
**audit log** survive a restart.

Backends
--------
``MAYBOT_DB`` selects the backend by its value:

* **SQLite (default):** any plain file path, or ``:memory:``. Uses the stdlib
  ``sqlite3`` module. This is the original, unchanged behavior.
* **Postgres (opt-in):** a URL starting with ``postgres://`` or
  ``postgresql://`` (e.g. ``postgresql://user:pass@host:5432/maybot``). Uses
  **psycopg v3**, which is an *optional* dependency and is NOT listed in
  ``requirements.txt`` (to avoid breaking CI installs). To enable Postgres::

      pip install "psycopg[binary]"
      export MAYBOT_DB="postgresql://user:pass@host:5432/maybot"

  If a Postgres URL is set but psycopg is not importable, the layer logs a
  warning and degrades to *disabled* (every function no-ops) rather than
  crashing the app.

The SQLite codepath below is preserved byte-for-byte; Postgres is a parallel
branch. The handful of statements that differ between dialects are funnelled
through ``_sql()`` (placeholder + upsert + autoincrement translation), which is
ONLY applied on the Postgres branch — SQLite SQL is executed exactly as written.

Migrations / TODO
-----------------
The schema is raw SQL (``CREATE TABLE IF NOT EXISTS``), not ORM models, so it is
idempotent on both backends and ``init()`` can be re-run safely. Formal,
versioned migrations (e.g. Alembic) are intentionally a *follow-up*: retrofitting
Alembic onto raw-SQL DDL is a sizable separate effort and out of scope here.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading

log = logging.getLogger(__name__)

DB_PATH = os.getenv("MAYBOT_DB", "")

_lock = threading.Lock()
# SQLite connection, or a psycopg v3 connection on the Postgres branch. Typed
# loosely because psycopg is an optional, lazily-imported dependency.
_conn = None
# Set True once we've tried and failed to import psycopg for a Postgres URL, so
# we degrade to "disabled" without retrying (and re-logging) on every call.
_pg_unavailable = False

# ---- backend selection ----
_PG_PREFIXES = ("postgres://", "postgresql://")


def _is_postgres(path: str | None = None) -> bool:
    """True when MAYBOT_DB (or ``path``) names a Postgres URL, not a file path."""
    p = DB_PATH if path is None else path
    return bool(p) and p.startswith(_PG_PREFIXES)


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
    # Generic JSON blob per module — used by in-memory coordination aids
    # (task board, oaths, maintenance silences, autopilot) to survive restarts.
    "CREATE TABLE IF NOT EXISTS state (module TEXT PRIMARY KEY, data TEXT)",
]

# Primary-key column for each table that the code upserts into via
# ``INSERT OR REPLACE``. Used to build the Postgres ``ON CONFLICT (<pk>)`` clause.
_UPSERT_PK = {
    "tool_calls": "id",
    "cultivation": "agent",
    "treasury": "id",
    "state": "module",
}


def _sql(query: str) -> str:
    """Translate a SQLite statement to its Postgres equivalent.

    This is applied ONLY on the Postgres branch; SQLite statements are executed
    verbatim. Three transforms:

    * ``?`` placeholders  -> ``%s`` (psycopg paramstyle).
    * ``INSERT OR REPLACE INTO t (cols) VALUES (vals)`` ->
      ``INSERT INTO t (cols) VALUES (vals) ON CONFLICT (<pk>) DO UPDATE SET
      col = EXCLUDED.col, ...`` (every non-PK column).
    * ``id INTEGER PRIMARY KEY`` autoincrement -> ``id SERIAL PRIMARY KEY`` in
      ``CREATE TABLE`` DDL.
    """
    q = query

    # CREATE TABLE: SQLite makes "INTEGER PRIMARY KEY" an autoincrement rowid
    # alias; Postgres needs SERIAL for the same effect.
    if q.lstrip().upper().startswith("CREATE TABLE"):
        # ``id INTEGER PRIMARY KEY CHECK (id = 1)`` (treasury) must stay a plain
        # INTEGER PK — it is a fixed singleton row, not an autoincrement — so
        # only convert the bare ``id INTEGER PRIMARY KEY`` form.
        q = re.sub(r"\bid INTEGER PRIMARY KEY\b(?! CHECK)", "id SERIAL PRIMARY KEY", q)
        # SQLite gives every table an implicit ``rowid``; ``comms`` relies on it
        # for ordering. Postgres has none, so give comms an explicit serial
        # surrogate key that ``rowid`` references are rewritten to (below).
        if re.search(r"CREATE TABLE IF NOT EXISTS comms\b", q, re.IGNORECASE):
            q = q.replace("comms (", "comms (rowid BIGSERIAL PRIMARY KEY, ", 1)

    # INSERT OR REPLACE -> INSERT ... ON CONFLICT DO UPDATE.
    m = re.match(
        r"\s*INSERT OR REPLACE INTO\s+(\w+)\s*\(([^)]*)\)\s*VALUES\s*\((.*)\)\s*$",
        q, re.IGNORECASE | re.DOTALL)
    if m:
        table, cols_raw, vals = m.group(1), m.group(2), m.group(3)
        cols = [c.strip() for c in cols_raw.split(",")]
        pk = _UPSERT_PK.get(table)
        if pk:
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != pk)
            q = (f"INSERT INTO {table} ({cols_raw}) VALUES ({vals}) "
                 f"ON CONFLICT ({pk}) DO UPDATE SET {updates}")

    # Placeholder style: SQLite '?' -> psycopg '%s'. Done last so the rewritten
    # upsert's placeholders are converted too.
    q = q.replace("?", "%s")
    return q


def enabled() -> bool:
    if not DB_PATH:
        return False
    if _is_postgres():
        # Enabled only if psycopg actually loads (checked once, lazily). Hold the
        # lock since this may open/cache the connection.
        with _lock:
            return _connect() is not None
    return True


def _connect():
    global _conn, _pg_unavailable
    if not DB_PATH:
        return None
    if _conn is None:
        if _is_postgres():
            return _connect_postgres()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        if DB_PATH != ":memory:":
            _conn.execute("PRAGMA journal_mode=WAL")
        for s in _SCHEMA:
            _conn.execute(s)
        _conn.commit()
    return _conn


def _connect_postgres():
    """Lazily import psycopg and open a Postgres connection.

    psycopg v3 is an optional dependency (``pip install "psycopg[binary]"``).
    If it is not installed we log once and degrade to disabled.
    """
    global _conn, _pg_unavailable
    if _pg_unavailable:
        return None
    try:
        import psycopg  # type: ignore
    except ImportError:
        _pg_unavailable = True
        log.warning(
            "MAYBOT_DB points at Postgres (%s) but psycopg is not installed; "
            'persistence disabled. Run: pip install "psycopg[binary]"',
            DB_PATH)
        return None
    _conn = psycopg.connect(DB_PATH, autocommit=False)
    for s in _SCHEMA:
        _conn.execute(_sql(s))
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
            c.execute(_sql(sql) if _is_postgres() else sql, params)
            c.commit()


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    if not DB_PATH:
        return []
    with _lock:
        c = _connect()
        if c is None:
            return []
        cur = c.execute(_sql(sql) if _is_postgres() else sql, params)
        return list(cur.fetchall())


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


# ---- generic per-module JSON state ----
def save_state(module: str, obj) -> None:
    if not DB_PATH:
        return
    _exec("INSERT OR REPLACE INTO state (module, data) VALUES (?, ?)", (module, json.dumps(obj)))


def load_state(module: str):
    rows = _query("SELECT data FROM state WHERE module = ?", (module,))
    if not rows:
        return None
    try:
        return json.loads(rows[0][0])
    except Exception:
        return None


def export_state() -> dict:
    """Every module's persisted JSON blob (for backup). Empty without a DB."""
    out: dict = {}
    for module, data in _query("SELECT module, data FROM state"):
        try:
            out[module] = json.loads(data)
        except Exception:
            pass
    return out


def import_state(state: dict) -> int:
    """Write module blobs back (for restore). Returns how many were written."""
    n = 0
    for module, obj in (state or {}).items():
        save_state(str(module), obj)
        n += 1
    return n


# ---- retention / pruning ----
# Tables with a millisecond/epoch ``ts`` column that can be aged out. The audit
# (tool_calls), cultivation, treasury and generic state tables are deliberately
# excluded — those are systems of record, not time series.
_PRUNABLE = {
    "history": "ts",
    "transcript": "ts",
    "comms": "ts",
    "usage": "ts",
}


def prune_older_than(cutoff_ms: int) -> dict[str, int]:
    """Delete time-series rows older than ``cutoff_ms`` (epoch milliseconds).

    Returns a per-table count of rows removed. A no-op without a DB.
    """
    removed: dict[str, int] = {}
    if not DB_PATH:
        return removed
    with _lock:
        c = _connect()
        if c is None:
            return removed
        pg = _is_postgres()
        for table, col in _PRUNABLE.items():
            sql = f"DELETE FROM {table} WHERE {col} < ?"
            cur = c.execute(_sql(sql) if pg else sql, (cutoff_ms,))
            removed[table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        c.commit()
    return removed


def vacuum() -> None:
    """Reclaim space after a large prune (best-effort; no-op without a DB)."""
    if not DB_PATH:
        return
    with _lock:
        c = _connect()
        if c is not None:
            try:
                if _is_postgres():
                    # Postgres VACUUM cannot run inside a transaction block.
                    c.commit()
                    old = getattr(c, "autocommit", None)
                    try:
                        c.autocommit = True
                        c.execute("VACUUM")
                    finally:
                        if old is not None:
                            c.autocommit = old
                else:
                    c.execute("VACUUM")
                    c.commit()
            except Exception:
                pass


def _reset_for_tests(path: str) -> None:
    """Test helper: point at a fresh DB and drop the cached connection."""
    global DB_PATH, _conn, _pg_unavailable
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _pg_unavailable = False
        DB_PATH = path
