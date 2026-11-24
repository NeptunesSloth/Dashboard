# CLAUDE.md

Orientation for AI assistants (and humans) working in this repo. Keep it short;
update it when the shape of the project changes.

## What this is

**Sect Academy** — an offline-first daily learning app (French A1, Spanish A1,
Security+ SY0-801, Network+ N10-009, ISC2 CC) where study sessions raise a
cultivation sect. It is the front door (`/`) and lives in
`maybot_control_center/academy/` (see "Sect Academy" below).

It grew out of, and still contains, MayBot Control Center — a self-hosted dashboard that watches a fleet of machines
("hosts") and the projects/bots running on them (trading bots, AI projects, game
servers, websites…), wrapped in a cultivation-sect theme. It also includes an AI
**Learning Center**, an **Ops Copilot**, persona "Sect Member" agents, and a
gamified XP/realm system.

Two deployables, both FastAPI:

- **`maybot_control_center/`** — the dashboard server (the thing you open in a
  browser). Aggregates state from agents, serves the UI, runs the LLM features.
- **`maybot_agent/`** — a lightweight agent that runs *on each host*, exposes
  read-only project status via `adapters/`, and reports back to the control
  center.

## Run it

```bash
pip install -r requirements.txt

# Dashboard with seeded demo data (no real agents needed) — easiest way to look around:
MAYBOT_DEMO=1 python -m uvicorn maybot_control_center.app:app --reload --port 8200
#   → http://127.0.0.1:8200   (Academy: / /study /library /trials /progress,
#     Command Hall: /command, Trade: /trade, Chamber: /chamber,
#     Treasury: /treasury, AI tutor: /learn, legacy console: /console)

# An agent on a host:
MAYBOT_API_TOKEN=... python -m uvicorn maybot_agent.app:app --port 8100
```

Docker: `docker-compose.yml` (default/SQLite) and `docker-compose.full.yml`
(Postgres + Redis + secret encryption, "everything on"). See `.env.example`.

## Test / lint (what CI gates on — `.github/workflows/ci.yml`)

```bash
coverage run -m pytest -q          # 133+ test files; the test gate
ruff check . --select E9,F         # lint gate (syntax + undefined names)
python -m playwright install --with-deps chromium && python tests/smoke_browser.py   # smoke gate
```

- `pytest tests/test_<area>.py` to run one area.
- Frontend is **vanilla JS, no build step**. After editing `static/**/*.js`,
  `node --check <file>` catches syntax errors; the Playwright smoke
  (`tests/smoke_browser.py`) loads every page and fails on any uncaught JS error.
- `typecheck` (mypy) and `audit` (pip-audit) also run in CI.

## Architecture (the 30-second version)

- **`app.py`** — the control-center FastAPI app: middleware, startup wiring, the
  agent tunnel + SSE stream. All HTTP routes live in domain routers under
  `routers/*.py`, with shared helpers in `deps.py`
  (`check_token`/`check_operator`/`resolve_device`/`SAFE_NAME`…).
- **`aggregator.py`** — polls every agent and builds `/api/overview`. Sync by
  default; opt-in async path via `MAYBOT_ASYNC_POLL=1` (`aggregate_async`).
- **LLM layer** — `agents.py` (`_chat`/`stream_chat`, retries, fallback models,
  budget, context trimming + opt-in secret redaction), `copilot.py` (Ops Copilot),
  `learning.py` (Learning Center tutor/quiz/labs + learner-profile adaptation;
  topic test-out, an objective-driven end-to-end pentest range with a capture
  step + tradecraft grading, blue-team incident-scoping labs, current-threat
  injection for security tracks, and an immersive tutor + cloze/translation
  drills for language tracks). Every LLM fn takes an injectable `chat=` param
  defaulting to `agents._chat`, for testability. Real-command labs are a
  default-off contract (`attach_real_env`/`MAYBOT_REAL_LABS`) — see
  `docs/REAL_LABS.md`; execution always routes through the guarded tools
  allow-list, never free-text shell.
- **Gamification** — `cultivation.py` (XP/realm ladder, spirit stones),
  `governance.py`, `traits.py`, `chronicle.py` (the event feed), `lifecycle.py`.
- **Persistence** — `store.py` (optional SQLite/Postgres via `MAYBOT_DB`; a no-op
  when unset, so features hold working data in memory and degrade gracefully).
  `history.py` / `pnl_history.py` keep bounded in-memory time series for the
  charts. Real migrations under `alembic/`.
- **Frontend** — `static/app.js` is the legacy single-page console (`/console`,
  includes the **Sect Map**). The newer themed pages live in
  `static/command/{command,trade,chamber,treasury,learn,login}.{html,js}` and
  share `static/command/lib.js` (`$`, `api`, `post`, `esc`, `money`, `mountRail`,
  `initAccount`, `starfield`, `countUp`) and `command.css`.

Deeper detail: `ARCHITECTURE.md`. Remaining ideas: `ROADMAP.md`.

## Sect Academy (the learning app)

Design + rationale: `docs/superpowers/specs/2026-11-24-sect-academy-design.md`;
research: `docs/research/`. No LLM, network or DB needed.

- **`academy/packs/*.yaml`** — the curated courses. Schema and authoring rules in
  `docs/ACADEMY_CONTENT.md`; validate with `python -m maybot_control_center.academy.packs`.
  An invalid pack is skipped at load, never a crash. Item ids are unique across
  all packs and are the keys of saved progress — **never rename an item id**.
- **`academy/fsrs.py`** — FSRS-6 with the published default weights. Don't tune
  the constants by hand.
- **`academy/engine.py`** — sessions (due reviews first, rationed new items),
  server-side grading, exercise formats that harden with card maturity, trials.
- **`academy/game.py`** — the sect game. Invariant: qi/stones are paid only for
  scheduled, graded work; nothing is ever destroyed by a missed day.
- **`academy/state.py`** — always-on JSON persistence (`MAYBOT_ACADEMY_FILE`,
  `:memory:` in tests — the root `conftest.py` sets that default).
- **`routers/academy.py`** + **`static/academy/`** — API and the app shell
  (`academy.js`), independent of `static/command/lib.js`. All artwork is vector
  and generated in `art.js` (the sect scene, portraits, icons) from numbers and
  known ids only — never pass user text into it. Colours live as CSS variables
  in `academy.css` (light + dark); the scene reads the `--a-*` set.
- Tests: `tests/test_academy.py` (engine/game on fixture packs),
  `tests/test_academy_api.py` (HTTP + every shipped item builds valid exercises).

## Conventions

- **Opt-in, default-off.** New capabilities are gated behind `MAYBOT_*` env vars
  and optional deps are lazy-imported, so a bare install always boots.
- **Escape all LLM/user text** in the frontend with `esc()` before putting it in
  `innerHTML`.
- **Auth:** read endpoints use a control token; mutating/operator ones require the
  operator role (`check_token` vs `check_operator`).
- **The model never runs a shell command from free text.** Labs are simulated;
  any real-env hook must route through the guarded-tools allow-list.

## Trading-bot PnL contract (read this before touching trading data)

The control center pulls trade/PnL data **agent-side**, in
`maybot_agent/adapters/trading_bot.py`. A bot points the adapter at its data via
the project config keys `database`, `log_file`, and/or `trade_csv_glob`.

**Time-bucketed profit** (`profit_today` / `profit_this_week` / `profit_this_month`
— the "Profit · Today" headline) is derived from per-trade rows with a **PnL
column and a timestamp**. The adapter reads, in precedence order:

1. `pnl_snapshots` (DayBot) → `total_pnl`,
2. `paper_trades` → `pnl_usd` + `closed_at`/`opened_at`,
3. a generic **`trades`** table — `_read_trade_rows()` recognises common PnL column
   names (`pnl`, `pnl_usd`, `realized_pnl`, `profit`, `net_pnl`, …) and timestamps
   (`closed_at`, `exit_time`, `timestamp`, …),
4. a `paper_trades_*.csv` fallback/merge.

`SUM(trades.pnl)` alone only feeds `realized_pnl` — **not** the time buckets. So
"catching trades but no PnL" means the bot's trades have no recognised PnL+time
columns where the adapter looks. The frontend shows an honest "no PnL reported
yet" state (not $0) when nothing reports. Tests: `tests/test_trading_bot_daybot.py`.

## Gotchas

- The dashboard is single-operator; the Learning Center's learner key is fixed
  (`"scholar"`), and the academy has exactly one learner/sect.
- `/` is the academy; the fleet Command Hall is `/command` (it used to be `/`).
- Agent adapters run on the *host*, not the control center — adapter changes need
  the agent redeployed/restarted on each bot host to take effect.
- `store.enabled()` is false without `MAYBOT_DB`; don't assume persistence in tests
  — use `store._reset_for_tests(":memory:")`.
