"""Unit tests for the opt-in Postgres routing / SQL-translation logic in store.

These exercise the parts that can be verified WITHOUT a live Postgres server:
backend selection (`_is_postgres`), the `_sql` dialect translation, and graceful
degradation when psycopg is not installed. A real Postgres round-trip is NOT
covered here (no server in CI/sandbox).
"""
import builtins

from maybot_control_center import store


# ---- backend selection ----
def test_is_postgres_true_for_urls():
    assert store._is_postgres("postgresql://user:pass@host:5432/maybot") is True
    assert store._is_postgres("postgres://user@host/db") is True


def test_is_postgres_false_for_files_and_empty():
    assert store._is_postgres("/var/lib/maybot/maybot.db") is False
    assert store._is_postgres("t.db") is False
    assert store._is_postgres(":memory:") is False
    assert store._is_postgres("") is False


def test_is_postgres_uses_global_db_path(monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", "postgresql://h/d")
    assert store._is_postgres() is True
    monkeypatch.setattr(store, "DB_PATH", "/tmp/x.db")
    assert store._is_postgres() is False


# ---- placeholder translation ----
def test_sql_converts_qmark_to_pyformat():
    assert store._sql("SELECT a FROM t WHERE x = ?") == "SELECT a FROM t WHERE x = %s"
    assert store._sql("INSERT INTO t (a, b) VALUES (?,?)") == "INSERT INTO t (a, b) VALUES (%s,%s)"


# ---- INSERT OR REPLACE -> ON CONFLICT ... DO UPDATE ----
def test_sql_translates_insert_or_replace_state():
    out = store._sql("INSERT OR REPLACE INTO state (module, data) VALUES (?, ?)")
    assert out == (
        "INSERT INTO state (module, data) VALUES (%s, %s) "
        "ON CONFLICT (module) DO UPDATE SET data = EXCLUDED.data"
    )
    assert "INSERT OR REPLACE" not in out


def test_sql_translates_insert_or_replace_tool_calls():
    out = store._sql(
        "INSERT OR REPLACE INTO tool_calls (id, requester, tool, args, status, output, code, "
        "created_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?)")
    assert out.startswith("INSERT INTO tool_calls (")
    assert "ON CONFLICT (id) DO UPDATE SET" in out
    # PK column must not appear in the SET list; every non-PK column must.
    assert "id = EXCLUDED.id" not in out
    for col in ("requester", "tool", "args", "status", "output", "code", "created_at", "finished_at"):
        assert f"{col} = EXCLUDED.{col}" in out
    # placeholders converted, none left as '?'
    assert "?" not in out
    assert out.count("%s") == 9


def test_sql_translates_treasury_singleton_upsert():
    out = store._sql(
        "INSERT OR REPLACE INTO treasury (id, balance, last_accrual, income, spent) VALUES (1,?,?,?,?)")
    assert "ON CONFLICT (id) DO UPDATE SET" in out
    assert "VALUES (1,%s,%s,%s,%s)" in out
    assert "balance = EXCLUDED.balance" in out


# ---- CREATE TABLE autoincrement / surrogate-key handling ----
def test_sql_create_table_serial_for_autoincrement():
    out = store._sql("CREATE TABLE IF NOT EXISTS tool_calls (id INTEGER PRIMARY KEY, requester TEXT)")
    assert "id SERIAL PRIMARY KEY" in out


def test_sql_create_table_keeps_treasury_singleton_integer_pk():
    out = store._sql(
        "CREATE TABLE IF NOT EXISTS treasury (id INTEGER PRIMARY KEY CHECK (id = 1), balance INTEGER)")
    # The fixed singleton row must stay a plain INTEGER PK, NOT SERIAL.
    assert "id INTEGER PRIMARY KEY CHECK (id = 1)" in out
    assert "SERIAL" not in out


def test_sql_create_table_comms_gets_rowid_surrogate():
    out = store._sql("CREATE TABLE IF NOT EXISTS comms (mission INTEGER, sender TEXT, ts INTEGER)")
    # Postgres has no implicit rowid; comms needs an explicit serial surrogate
    # so the existing "ORDER BY rowid" queries keep working.
    assert "rowid BIGSERIAL PRIMARY KEY" in out


def test_full_schema_translates_without_error():
    for stmt in store._SCHEMA:
        out = store._sql(stmt)
        assert out  # non-empty
        assert "?" not in out


# ---- graceful degradation when psycopg is absent ----
def _force_no_psycopg(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psycopg" or name.startswith("psycopg."):
            raise ImportError("No module named 'psycopg' (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_postgres_without_psycopg_degrades_gracefully(monkeypatch):
    store._reset_for_tests("postgresql://user:pass@localhost:5432/maybot")
    _force_no_psycopg(monkeypatch)
    try:
        # None of these should raise even though psycopg cannot be imported.
        store.init()
        assert store.enabled() is False
        store.add_comms({"from": "x", "kind": "agent", "content": "y", "ts": 1})
        store.upsert_tool_call({"id": 1, "requester": "n", "tool": "t", "args": {},
                                "status": "pending", "output": None, "code": None,
                                "created_at": 1, "finished_at": None})
        assert store.load_comms() == []
        assert store.load_tool_calls() == []
        assert store.prune_older_than(0) == {}
        store.vacuum()  # no-op, must not raise
    finally:
        store._reset_for_tests("")


def test_postgres_unavailable_flag_logged_once(monkeypatch):
    store._reset_for_tests("postgresql://h/d")
    _force_no_psycopg(monkeypatch)
    try:
        assert store._connect() is None
        assert store._pg_unavailable is True
        # second call short-circuits on the flag, still None
        assert store._connect() is None
    finally:
        store._reset_for_tests("")


# ---- SQLite path must NOT be touched by translation ----
def test_sqlite_path_unaffected(tmp_path):
    store._reset_for_tests(str(tmp_path / "t.db"))
    store.init()
    try:
        assert store.enabled() is True
        assert store._is_postgres() is False
        store.add_comms({"from": "a", "kind": "agent", "content": "hi", "ts": 5})
        feed = store.load_comms()
        assert feed and feed[-1]["content"] == "hi"
    finally:
        store._reset_for_tests("")
