# Contributing

Thanks for hacking on the MayBot Control Center. The short version: keep the
bare install bootable, gate new powers behind env vars, and ship focused,
tested PRs ("waves") rather than one giant change.

## Setup & run

```bash
pip install -r requirements.txt
MAYBOT_DEMO=1 python -m uvicorn maybot_control_center.app:app --reload --port 8200
```

`MAYBOT_DEMO=1` seeds fake hosts/bots so every page has something to show.

## Before you push (what CI gates on)

```bash
coverage run -m pytest -q          # the test gate — keep it green
ruff check . --select E9,F         # lint gate (syntax + undefined names)
python -m playwright install --with-deps chromium && python tests/smoke_browser.py
```

- `pytest tests/test_<area>.py` runs one area while iterating.
- The frontend is vanilla JS with no build step: after editing
  `static/**/*.js`, `node --check <file>` catches syntax errors; the Playwright
  smoke loads every page and fails on any uncaught JS error.
- `mypy` and `pip-audit` also run in CI (report-only).

## Conventions

- **Opt-in, default-off.** New capabilities hide behind `MAYBOT_*` env vars and
  optional deps are lazy-imported, so a bare install always boots.
- **Routes live in `routers/<domain>.py`**, not `app.py`. Shared auth/ACL
  helpers come from `deps.py` (`check_token`, `check_operator`,
  `resolve_device`, `SAFE_NAME`…). Read endpoints take any valid role;
  mutating endpoints require the operator role.
- **Escape all LLM/user text** in the frontend with `esc()` before it goes
  anywhere near `innerHTML`.
- **The model never runs a shell command from free text.** Labs are simulated;
  any real-env hook must route through the guarded-tools allow-list.
- **LLM functions take an injectable `chat=`** (defaulting to `agents._chat`)
  so tests can fake the model — follow that pattern for anything new.
- Don't assume persistence in tests: `store.enabled()` is false without
  `MAYBOT_DB`; use `store._reset_for_tests(":memory:")` and reset with
  `store._reset_for_tests("")` when done.

## Where things go

See `ARCHITECTURE.md` for the map and `ROADMAP.md` for the backlog. Agent-side
changes (`maybot_agent/`, especially `adapters/`) run on the *bot hosts* — they
need the agent redeployed there to take effect, so call that out in your PR.
