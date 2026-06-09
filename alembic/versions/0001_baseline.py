"""baseline schema (mirrors maybot_control_center/store.py)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-09

This baseline creates the CURRENT persistence schema using the exact
``CREATE TABLE IF NOT EXISTS ...`` DDL from ``store.py``'s ``_SCHEMA`` list.

Because every statement uses ``IF NOT EXISTS``, running ``alembic upgrade head``
against a database that ``store.init()`` already populated is a no-op for the
table data — it only stamps the Alembic version. New deployments can be created
either way; Alembic is the explicit, versioned forward path for schema changes
going forward, while ``store.init()`` keeps auto-creating tables idempotently.

The DDL here is kept byte-for-byte identical to ``store._SCHEMA`` (SQLite form).
This is portable to Postgres for the trivial cases; store.py's ``_sql()`` applies
a couple of dialect transforms (SERIAL autoincrement, an explicit ``comms``
surrogate key) on its own Postgres branch that are not reproduced here because
the baseline's purpose is to match the schema store.py created on each backend.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


# Mirror of maybot_control_center.store._SCHEMA (SQLite DDL, verbatim).
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
    "CREATE TABLE IF NOT EXISTS state (module TEXT PRIMARY KEY, data TEXT)",
]

# Tables created above, in reverse order for a clean downgrade.
_TABLES = ["history", "transcript", "comms", "tool_calls", "usage",
           "cultivation", "treasury", "state"]


def upgrade() -> None:
    for stmt in _SCHEMA:
        op.execute(stmt)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
