# Database Migrations (Alembic)

The MayBot Control Center persistence layer (`maybot_control_center/store.py`)
stores its schema as raw `CREATE TABLE IF NOT EXISTS ...` statements, and
`store.init()` auto-creates every table idempotently at startup. **That behavior
is unchanged** — the app runs identically with or without Alembic.

Alembic provides the *explicit, versioned forward-migration path* for schema
changes going forward. It is an **ops/dev tool**: it is intentionally **not**
listed in `requirements.txt` (so it never affects app installs or CI), and you
install it on demand.

## Install

```bash
pip install alembic
```

For Postgres targets you also need the same driver `store.py` uses:

```bash
pip install "psycopg[binary]"
```

## Database selection (`MAYBOT_DB`)

`alembic/env.py` resolves the database URL from the **same** `MAYBOT_DB`
environment variable as `store.py`:

| `MAYBOT_DB` value                              | URL Alembic uses                          |
| ---------------------------------------------- | ----------------------------------------- |
| *(unset / empty)*                              | `sqlite:///<cwd>/maybot_migrations.db` (offline authoring) |
| `:memory:`                                     | `sqlite://` (in-memory)                   |
| a plain file path, e.g. `/var/lib/maybot.db`   | `sqlite:///<abs path>`                    |
| `postgres://user:pass@host/db`                 | `postgresql+psycopg://user:pass@host/db`  |
| `postgresql://user:pass@host/db`               | `postgresql+psycopg://user:pass@host/db`  |

The `postgres://` / `postgresql://` forms are normalized to the **psycopg v3**
dialect (`postgresql+psycopg://`), matching the driver `store.py` connects with.

## Workflow

Apply all migrations (create / update the schema):

```bash
MAYBOT_DB=/path/to/maybot.db alembic upgrade head
```

Roll the schema back to empty:

```bash
MAYBOT_DB=/path/to/maybot.db alembic downgrade base
```

Inspect status:

```bash
MAYBOT_DB=/path/to/maybot.db alembic current
MAYBOT_DB=/path/to/maybot.db alembic history
```

Because the baseline migration (`0001_baseline`) uses `CREATE TABLE IF NOT
EXISTS`, running `alembic upgrade head` against a database that `store.init()`
already populated is safe — it creates nothing new and just records the Alembic
version stamp.

## Adding a schema change

1. Create a new revision:

   ```bash
   alembic revision -m "add some_table"
   ```

2. Edit the generated file in `alembic/versions/` — write `upgrade()` /
   `downgrade()` with `op.execute("...")` (raw SQL, to stay consistent with the
   raw-SQL style of `store.py`).
3. **Also** update `store._SCHEMA` (and any related code) so `store.init()`'s
   idempotent auto-create stays in sync with the migrated schema.
4. Apply with `alembic upgrade head`.

Keep migration DDL backend-portable where trivial (the `IF NOT EXISTS` form
already is). Where SQLite and Postgres genuinely differ, mirror the dialect
handling that `store._sql()` performs.
