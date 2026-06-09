"""Alembic migration environment for the MayBot Control Center.

The database URL is resolved from the same ``MAYBOT_DB`` environment variable
that ``maybot_control_center/store.py`` uses, so migrations target whatever DB
the app would use:

* **empty / unset** -> a local sqlite file (``maybot_migrations.db`` in the cwd),
  so migrations can be authored/inspected offline without configuring anything.
* **a plain file path** (e.g. ``/var/lib/maybot.db`` or ``:memory:``) ->
  ``sqlite:///<abs path>`` (SQLAlchemy sqlite URL).
* **a ``postgres://`` / ``postgresql://`` URL** -> passed through, normalized to
  the psycopg v3 dialect (``postgresql+psycopg://``) so it matches the driver
  ``store.py`` uses for Postgres.

This mirrors store.py's backend selection; see docs/MIGRATIONS.md.
"""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object (reads alembic.ini).
config = context.config

# Postgres URL prefixes, matching store._PG_PREFIXES.
_PG_PREFIXES = ("postgres://", "postgresql://")

# Default sqlite file used for offline migration authoring when MAYBOT_DB is
# unset. A relative path resolved against the current working directory.
_DEFAULT_SQLITE = "maybot_migrations.db"


def _resolve_url() -> str:
    """Build a SQLAlchemy URL from MAYBOT_DB (mirrors store.py backend choice)."""
    raw = os.getenv("MAYBOT_DB", "").strip()

    # An already-dialect-pinned SQLAlchemy Postgres URL: pass straight through.
    if raw.startswith("postgresql+"):
        return raw

    # Postgres URL: pass through, but pin the psycopg v3 dialect so SQLAlchemy
    # uses the same driver family as store.py (which connects via psycopg v3).
    if raw.startswith(_PG_PREFIXES):
        if raw.startswith("postgres://"):
            raw = "postgresql://" + raw[len("postgres://"):]
        # postgresql://...  ->  postgresql+psycopg://...  (unless already pinned)
        if raw.startswith("postgresql://"):
            raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
        return raw

    # Otherwise it's a sqlite file path (or unset -> default authoring file).
    path = raw or _DEFAULT_SQLITE
    if path == ":memory:":
        return "sqlite://"
    return "sqlite:///" + os.path.abspath(path)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    context.configure(
        url=_resolve_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect and apply)."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
