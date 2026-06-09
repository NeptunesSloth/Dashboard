# Architecture

MayBot Control Center is a two-part system:

1. **The control center** (`maybot_control_center/`) — a central FastAPI dashboard
   you run once. It pulls status from your hosts, aggregates it into one fleet
   view, and adds an ops/automation/RPG layer on top.
2. **The on-host agent** (`maybot_agent/`) — a small FastAPI service you install on
   each machine that runs bots/projects. It reports project status and executes
   start/stop/test actions locally.

The control center never touches your hosts directly; it talks to each host's
agent over HTTP (or a reverse WebSocket tunnel). This keeps the dashboard a pure
*reader/orchestrator* and the agent the only thing with local access.

See [ROADMAP.md](ROADMAP.md) for the impact-ordered backlog and planned waves
(this doc reflects the code as it stands).

---

## The control center (`maybot_control_center/`)

### FastAPI app + router split

`app.py` is the application root: it builds the `FastAPI` app, installs an HTTP
middleware (rate limiting, baseline security headers, opt-in CSP/HSTS via
`MAYBOT_CSP`/`MAYBOT_HSTS`, self-observability counters, and an operator audit
trail of mutating calls), and defines a large set of API routes. Historically a
monolith, route groups have been extracted into `routers/*` and mounted via
`app.include_router(...)`:

- `routers/hosts.py` — host (agent) management + system settings.
- `routers/crew.py` — disciple crew + missions.
- `routers/agentops.py` — agent memory / tools / autonomy / usage / budget.
- `routers/sect.py` — the sect/cultivation RPG layer.
- `routers/economy.py` — disciple economy & lifecycle.
- `routers/reliability.py` — reliability / SLO.
- `routers/learning.py` — the Learning Center.

### `deps.py` — shared request gates

`deps.py` holds the auth/role/ACL helpers (`role`, `check_token`,
`check_operator`, `check_project_access`), device resolution (`resolve_device`),
the safe-name regexes, and `mask_token`. Routers import these directly (not from
`app.py`) to avoid circular imports; `app.py` re-exports them under their legacy
`_`-prefixed names for backward compatibility.

### `config.py` — file-backed fleet config

`config.py` loads/saves `devices.yaml` (the agent hosts to poll) with atomic
writes under a shared write lock, exposes `CONTROL_CENTER_TOKEN`, and
`all_devices()` merges file-configured hosts with any self-registered ones
(`registry.py`).

### `agents.py` — the LLM layer

`agents.py` is the agent runtime: persona "members" defined in `agents.yaml`,
each pointing at an LLM backend (Ollama, any OpenAI-compatible server, or
Claude/Anthropic). Assigning a task runs a chat completion in a background
thread, appends to the member's transcript, and surfaces the reply on the
dashboard. It also drives tool loops, delegation, inner-demon self-critique, and
usage accounting. Surrounding modules build on it: `comms.py` (debates /
tournaments), `routing.py` / `orchestrator.py` (route or decompose a goal to the
best-fit member), `governance.py`, `copilot.py` (the natural-language Ops
Copilot), and the cultivation/sect RPG modules.

### `aggregator.py` — the polling/aggregation core

`aggregate(devices)` is the heart of the read path. It fans out across hosts with
a `ThreadPoolExecutor`, calling each agent's `/api/ping` (reachability) then
`/api/projects` (authenticated). It builds per-device rows and a flat project
list, computes a fleet `summary` (online/offline hosts, outdated agents, bots
running, trading PnL today/this-week, open exposure, failing tests, local-AI host
counts, …), then runs the cross-cutting ops passes: notifications, history
recording, SLO/error-budget annotation, meridian (dependency) tagging, incident
ownership/acks, incident dispatch, heuristic diagnosis, and escalation. The
result `{summary, devices, projects}` is what the dashboard renders.

### `store.py` — optional persistence

`store.py` is opt-in SQLite persistence, enabled only when `MAYBOT_DB` is set.
When unset every function is a no-op and modules keep their in-memory behavior;
when set, modules write through and reload prior state on startup (metrics
history, transcripts, the comms feed, usage, cultivation/treasury, the guarded-
tools audit log, and a generic per-module JSON `state` table). On boot `app.py`
calls `store.init()` then a list of `*.load_persisted()` loaders.

### Feature modules

The rest of `maybot_control_center/*.py` are focused feature modules wired into
routes and into the `aggregate()` passes — e.g. `history.py`, `slo.py`,
`errorbudget.py`, `meridians.py`, `oaths.py`, `acks.py`, `escalation.py`,
`incidents.py`, `diagnosis.py`, `runbooks.py`, `taskqueue.py`, `autopilot.py`,
`notify.py`/`notifier.py`, `authz.py`, `registry.py`, `tunnel.py`, `push.py`,
`backup.py`/`dr.py`, plus the sect/cultivation RPG set
(`cultivation.py`, `treasury.py`, `sectsim.py`, and friends).

---

## The on-host agent (`maybot_agent/`)

`app.py` defines a small FastAPI service. Liveness/identity routes (`/healthz`,
`/api/ping`, `/api/device`) are intentionally unauthenticated (no secrets); all
sensitive routes (`/api/projects`, logs, start/stop/run-tests, config edits,
self-update) require the host API token via `Depends(verify_token)` from
`auth.py`. On startup its lifespan handler runs `selfregister.start()` (auto-
enroll with the control center if configured) and `tunnel_client.start()` (dial
out so no inbound port is needed).

### Adapters (`adapters/`)

Each project has a `type`; `ADAPTERS` maps it to a module that turns raw config
into a normalized status dict. `adapters/base.py` provides `base_project()` — git
status, process detection, log scanning, alerts, and an `actions_available` map.
Type-specific adapters extend it: `trading_bot`, `code_project`, `game_server`,
`website`, `school`, `ai_project`, `local_ai_host`, and a `generic` fallback.
Adapting is per-project and failure-isolated: a broken bot is surfaced as a
degraded entry rather than dropping it (and the rest of the host) from the view.

### Services (`services/`)

Low-level host primitives the adapters/routes call: `process_status.py`,
`git_status.py`, `log_reader.py`, `command_runner.py` (foreground/background/stop
process control), `discover.py` (heuristic project candidates), and `cache.py`.

---

## Data / serving flow

```
browser dashboard
      │  GET /api/overview   (x-control-token)
      ▼
control center  ──► aggregator.aggregate(all_devices())
      │                 │  fan-out (thread pool), per host:
      │                 ├─► agent /api/ping       (reachability, version)
      │                 └─► agent /api/projects   (authenticated status)
      │                 │  on each host the agent adapts every project via adapters/*
      │                 ▼
      └──────────  {summary, devices, projects}  ──► rendered fleet view
```

Operator actions (`POST /api/action/{device}/{project}/{start|stop|run-tests}`)
are proxied to the target agent's matching route. The dashboard also streams live
updates over Server-Sent Events (`/api/stream`) and accepts agent reverse tunnels
over a WebSocket (`/ws/agent`).

---

## Config files

Plain YAML at the repo root (each has a committed `*.example`):

- `devices.yaml` — the agent hosts the control center pulls from (name, url,
  api_token). Managed from the Hosts screen; `MAYBOT_DEVICES_FILE` overrides path.
- `agents.yaml` — the LLM-backed sect members (provider, model, base_url, persona).
- `projects.yaml` (on each host) — that host's bots/projects, consumed by the
  agent (`MAYBOT_PROJECTS_FILE`).
- `users.yaml` — dashboard accounts, roles, hashed passwords, and per-project ACLs
  (via `authz.py`).
- Feature configs: `learning.yaml`, `schedules.yaml`, `talismans.yaml`,
  `runbooks.yaml`, `meridians.yaml`, `formations.yaml`, `autopilot.yaml`,
  `tools.yaml`, and others — each loaded by its module and a no-op when absent.

---

## Env-driven optional subsystems

Most advanced behavior is **off by default** and switches on via environment
variables, so a plain deployment stays simple:

- **Persistence** — `MAYBOT_DB` enables the SQLite write-through in `store.py`.
- **Budgets / usage** — LLM cost and budget tracking (`usage.py`, `budget.py`),
  surfaced through `routers/agentops.py`.
- **Observability** — `obs.setup_logging()` (opt-in structured JSON logs via
  `MAYBOT_JSON_LOGS`), per-request/poll self-checks (`selfcheck.py`), and
  `metrics.py`.
- **Notifications** — Slack / Discord / Telegram / generic webhook / SMTP
  channels (`notify.py`), used for alerts, reports, and 2FA codes.
- **Autopilot** — the autonomous ops loop (`autopilot.py`), gated by
  `MAYBOT_AUTOPILOT`, with an operator kill-switch.
- **Reliability automation** — scheduled missions (`scheduler.py`), synthetic
  uptime probes (`talismans.py`), error budgets / Heavenly Decree freezes
  (`errorbudget.py`), escalation policies (`escalation.py`), self-healing runbooks
  (`runbooks.py`), retention/backups (`retention.py`), and an external dead-man's
  heartbeat (`deadman.py`).
- **Security headers** — opt-in `Content-Security-Policy` (`MAYBOT_CSP`) and HSTS
  (`MAYBOT_HSTS`); baseline headers are always applied.
