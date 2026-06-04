# MayBot Dashboard Integration Prompts

This file contains one **copy-paste-ready prompt per project type**. Hand the prompt for your
project's type to a coding agent working *inside your project's repo*. Each prompt is fully
self-contained: the coding agent needs **no prior MayBot knowledge**. Each prompt tells the
agent exactly which signals the matching MayBot adapter reads, what the dashboard expects your
project to emit, and gives a ready-to-use `projects.yaml` block to register the project.

## Background (applies to every type)

MayBot is an external dashboard/control-center. It does **not** import your code. For every
registered project it runs an "adapter" that passively collects signals from the outside:

- **Process status** — found via one of: a PID file (`pid_file`, read relative to `path`), a
  substring match on a running process command line (`cmdline_contains`), or a process name
  (`process_name`). It reports `running`, `pid`, `cpu`, `ram_mb`, and `cmdline` via `psutil`.
- **Git status** — runs `git` in `path`: current branch, dirty/clean working tree, and the last
  commit (`%h %s`).
- **Logs** — reads the tail of `log_file` (last ~100–400 lines, plain text). **Universal rule:**
  if any recent log line contains the substring `ERROR` or `CRITICAL`, the project is flagged
  unhealthy (a warning alert is raised). Emit clean, greppable log lines and reserve the words
  `ERROR`/`CRITICAL` for genuine problems.
- **Alerts → health.** The dashboard derives `health` from alerts: any alert beginning with
  `ERROR` ⇒ `health = "error"`; otherwise any alert ⇒ `health = "warning"`; no alerts ⇒ `"ok"`.

Base alerts raised for **every** type:

- `ERROR: configured path missing` — if `path` is set but does not exist.
- `WARNING: configured log file missing` — if `log_file` is set but does not exist.
- `ERROR: process expected but stopped` — if `expect_running: true` and the process is not found.
- `WARNING: recent logs contain ERROR/CRITICAL` — if the tailed log contains `ERROR`/`CRITICAL`.

Each project is registered as one entry under `projects:` in MayBot's `projects.yaml`. Common
fields every type supports: `name`, `type`, `path`, `log_file`, `expect_running`, one of
`pid_file` / `cmdline_contains` / `process_name`, an optional `metrics:` map of static overrides,
and a `commands:` map (`start`, `stop`, `run_tests`) that enables remote action buttons.

---

## trading_bot

> **Prompt — paste into a coding agent working in your trading bot's repo:**
>
> My trading bot will be monitored by an external read-only dashboard called **MayBot**. MayBot
> does not import my code; it watches my process, my git repo, my log file, and my SQLite
> database from the outside. Make my bot emit the exact signals it reads. Do **not** change my
> trading logic — only logging, the SQLite schema, and PID-file handling.
>
> **1. Process / PID / cmdline.** MayBot locates my process by either a PID file or a command-line
> substring.
> - Write my OS process PID to a PID file (e.g. `run/<bot>.pid`) on startup and remove it on
>   clean exit.
> - Ensure my launch command line contains a stable, unique substring (e.g. `tradebot`) so it can
>   be matched by `cmdline_contains`.
> - MayBot expects the process to be running; if it is configured with `expect_running: true` and
>   the process is gone, it raises `ERROR: process expected but stopped`.
>
> **2. Log file.** Append-only plain-text log at a stable path. MayBot tails the last ~400 lines
> and regex-scans them. **Universal health rule:** any line containing `ERROR` or `CRITICAL` marks
> the bot unhealthy — only use those words for real failures. Once per cycle, emit a metrics line
> containing these **exact `key=value` tokens** (case-insensitive; `:` or `=` separator both work;
> values may be negative; floats use `.`). MayBot reads the most recent occurrence of each:
>
> | log token | meaning |
> |---|---|
> | `total_pnl=<num>` | today's total P&L (→ `profit_today`) |
> | `unrealized_pnl=<num>` | open-position unrealized P&L |
> | `orders_filled=<int>` | orders filled (→ `fills_today`) |
> | `orders_attempted=<int>` | orders attempted (→ `trades_today`) |
> | `fill_rate=<num>` | fill rate |
> | `open_positions=<int>` | currently open positions |
> | `total_exposure_usd=<num>` | open exposure in USD |
> | `risk_blocked=<int>` | trades blocked by risk checks |
> | `rejected=<int>` | rejected trades |
>
> Example line:
> `2026-06-04 14:00:00 INFO cycle total_pnl=125.40 unrealized_pnl=-12.10 orders_filled=3 orders_attempted=5 fill_rate=0.6 open_positions=2 total_exposure_usd=4200.00 risk_blocked=1 rejected=0`
>
> **3. SQLite database (optional but richer).** If I have a SQLite DB, MayBot opens it read-only
> and reads any of these tables/columns that exist (all optional — create the ones that fit):
>
> - `cycle_summaries(open_positions, total_exposure_usd, unrealized_pnl, orders_filled, orders_attempted, market_status, tickers_scanned, mode, recorded_at)` — newest row by `recorded_at` is used for live cycle metrics.
> - `pnl_snapshots(recorded_at, total_pnl, unrealized_pnl, open_positions)` — newest row → `profit_today`, `unrealized_pnl`, `open_positions`.
> - `paper_trades(opened_at, closed_at, order_id, pnl_usd, status)` — all rows; MayBot sums `pnl_usd` and buckets by `closed_at`/`opened_at` into today/week/month P&L and counts.
> - `trades(pnl)` — `SUM(pnl)` → `realized_pnl`.
> - `positions(unrealized_pnl, exposure)` — `SUM(unrealized_pnl)` → `unrealized_pnl`, `SUM(exposure)` → `open_exposure`.
> - `rejected_signals` — `COUNT(*)` → `rejected_trades`.
>
> Use ISO-8601 timestamps for `opened_at`/`closed_at`/`recorded_at`. Keep the DB writable while
> read; MayBot opens it in read-only WAL-friendly mode but warns if it is locked.
>
> **4. CSV fallback (optional).** If I export trades as CSV instead of `paper_trades`, MayBot can
> read files matching a glob under `path`, expecting columns `opened_at, closed_at, order_id,
> pnl_usd`.
>
> **5. `projects.yaml` block** — add this entry to MayBot's `projects.yaml` under `projects:`
> (edit paths and the cmdline/pid substring to match my setup):
>
> ```yaml
>   - name: my-trading-bot
>     type: trading_bot
>     path: /path/to/trading-bot
>     expect_running: true
>     cmdline_contains: tradebot          # unique substring of my launch command
>     pid_file: run/bot.pid               # relative to path
>     log_file: /path/to/trading-bot/logs/bot.log
>     database: /path/to/trading-bot/data/trades.sqlite3
>     # trade_csv_glob: "exports/trades_*.csv"   # optional CSV fallback, relative to path
>     metrics:
>       mode: paper                       # static label shown on the dashboard
>     commands:
>       start:
>         argv: ["tradebot"]
>         cwd: /path/to/trading-bot
>         stdout: logs/bot.log
>         stderr: logs/bot.log
>         pid_file: run/bot.pid
>         background: true
>       stop:
>         pid_file: run/bot.pid
>         match_cmdline_contains: tradebot
>       run_tests:
>         argv: [".venv/bin/python", "-m", "pytest", "-q"]
>         cwd: /path/to/trading-bot
>         timeout_seconds: 300
> ```
>
> Implement the PID file, the per-cycle metrics log line with the exact tokens above, and (if
> practical) the `cycle_summaries`/`pnl_snapshots`/`paper_trades` tables. Confirm `ERROR`/`CRITICAL`
> only appear in the log on real failures.

---

## code_project

> **Prompt — paste into a coding agent working in your code project's repo:**
>
> My code repository will be monitored by an external read-only dashboard called **MayBot**. It
> does not import my code; it inspects my git repo, optionally watches a process and a log file,
> and reports code-health signals. Make my project expose what it reads. The signals it collects
> for a `code_project` are:
>
> - **Git** (run in `path`): current branch, working-tree clean/dirty, last commit (`%h %s`), and
>   a **count of modified files** via `git status --porcelain`. Keep the repo a valid git
>   checkout at `path`.
> - **TODO/FIXME count** — MayBot runs `rg -n "TODO|FIXME"` over `path` and counts matches. (No
>   action needed; just be aware these are surfaced.)
> - **`log_file` size** and **`database` size** — if I configure a `log_file` and/or `database`,
>   MayBot reports their byte sizes. Point them at real files if I want sizes shown.
> - **`last_test_result`** — MayBot displays whatever I set in the project's static `metrics`
>   (e.g. `pass`/`fail`); it does not run my tests to compute this (unless triggered via the
>   `run_tests` command).
> - **Process** (optional): if I set `pid_file`/`cmdline_contains`/`process_name` and
>   `expect_running: true`, MayBot reports running/stopped and CPU/RAM.
>
> **Universal health rule:** if a configured `log_file` is tailed and any recent line contains
> `ERROR` or `CRITICAL`, the project is flagged unhealthy. Also, a missing `path` raises an error
> and a missing configured `log_file` raises a warning.
>
> **`projects.yaml` block** — add this to MayBot's `projects.yaml` under `projects:`:
>
> ```yaml
>   - name: my-code-project
>     type: code_project
>     path: /path/to/repo
>     log_file: /path/to/repo/build.log     # optional; size is reported
>     database: /path/to/repo/dev.sqlite3   # optional; size is reported
>     metrics:
>       last_test_result: unknown           # set to pass/fail from CI if desired
>     commands:
>       run_tests:
>         argv: ["python", "-m", "pytest", "-q"]
>         cwd: /path/to/repo
>         timeout_seconds: 300
> ```
>
> Ensure `path` is a clean git checkout and (optionally) point `log_file`/`database` at real
> files. Keep `ERROR`/`CRITICAL` out of normal log output.

---

## website

> **Prompt — paste into a coding agent working in your web service's repo:**
>
> My website/web service will be monitored by an external read-only dashboard called **MayBot**.
> It does not import my code; it polls an HTTP health endpoint and (optionally) watches my process,
> git repo, and log file. Make my service expose a health endpoint. The signals it collects for a
> `website` are:
>
> - **HTTP health check** — MayBot issues `GET <health_url>` with a 5s timeout and records:
>   `online` (true if status code < 500), `status_code`, and `response_time_ms`.
>   - If the response status is **>= 400**, it raises `WARNING: health check returned 4xx/5xx`.
>   - If the request **fails/times out**, it raises `ERROR: health check failed: <reason>`
>     (→ health = error).
>   - Provide a lightweight, fast, unauthenticated endpoint (e.g. `GET /health`) that returns
>     `200` when healthy.
> - **Process / git / logs** — optional, same as other types: configure `cmdline_contains` (or
>   `pid_file`/`process_name`) and `expect_running` to track the server process; set `path` for
>   git status; set `log_file` to tail logs.
>
> **Universal health rule:** any recent log line containing `ERROR` or `CRITICAL` flags the
> project unhealthy.
>
> **`projects.yaml` block** — add this to MayBot's `projects.yaml` under `projects:`:
>
> ```yaml
>   - name: my-website
>     type: website
>     health_url: https://example.com/health   # GET, must return <400 when healthy
>     path: /path/to/web-repo                   # optional, for git status
>     log_file: /path/to/web-repo/logs/app.log  # optional
>     expect_running: true
>     cmdline_contains: gunicorn                 # unique substring of the server process
>     commands:
>       start:
>         argv: ["gunicorn", "app:app"]
>         cwd: /path/to/web-repo
>         background: true
>       stop:
>         match_cmdline_contains: gunicorn
> ```
>
> Implement a fast unauthenticated `GET /health` returning `200`/`<400` when healthy, and make sure
> `ERROR`/`CRITICAL` only appear in logs on real failures.

---

## game_server

> **Prompt — paste into a coding agent working in your game server's repo:**
>
> My game server will be monitored by an external read-only dashboard called **MayBot**. It does
> not import my code; it watches my process, my git repo (if `path` is set), and my log file. The
> `game_server` adapter is lightweight — it surfaces the base signals plus any static metrics I
> define. Make my server emit clean process and log signals:
>
> - **Process / PID / cmdline** — MayBot finds my server by `pid_file` (relative to `path`),
>   `cmdline_contains`, or `process_name`, and reports `running`, `pid`, `cpu`, and `ram_mb`. Set
>   `expect_running: true` so a crashed server raises `ERROR: process expected but stopped`.
> - **Log file** — tail-scanned. **Universal health rule:** any line containing `ERROR` or
>   `CRITICAL` flags the server unhealthy. Keep those words for genuine failures (crashes, failed
>   world load, etc.).
> - **Static metrics** — MayBot does not parse game-specific metrics; anything you want shown
>   (e.g. `game: minecraft`, `max_players: 20`) goes in the static `metrics:` map and is displayed
>   as-is.
> - **Git** — set `path` to a git checkout to show branch/dirty/last-commit.
>
> **`projects.yaml` block** — add this to MayBot's `projects.yaml` under `projects:`:
>
> ```yaml
>   - name: my-game-server
>     type: game_server
>     path: /path/to/server
>     expect_running: true
>     cmdline_contains: server.jar            # or process_name / pid_file
>     log_file: /path/to/server/logs/latest.log
>     metrics:
>       game: minecraft                        # static, shown as-is
>       max_players: 20
>     commands:
>       start:
>         argv: ["java", "-jar", "server.jar", "--nogui"]
>         cwd: /path/to/server
>         background: true
>       stop:
>         match_cmdline_contains: server.jar
> ```
>
> Make sure the process is matchable, the log path is correct, and `ERROR`/`CRITICAL` only appear
> on real failures.

---

## ai_project

> **Prompt — paste into a coding agent working in your AI project's repo:**
>
> My AI/ML project will be monitored by an external read-only dashboard called **MayBot**. It does
> not import my code; it watches my process, my git repo (if `path` is set), and my log file. The
> `ai_project` adapter is lightweight — it surfaces the base signals plus any static metrics I
> define. **Note:** this type is for general AI projects (training jobs, pipelines, agents). If
> what I actually run is a *local model-serving API* (Ollama, llama.cpp, LM Studio, an
> OpenAI-compatible server), use the **`local_ai_host`** type instead, which actively probes model
> endpoints. Make my project emit clean process and log signals:
>
> - **Process / PID / cmdline** — MayBot finds my process by `pid_file` (relative to `path`),
>   `cmdline_contains`, or `process_name`, and reports `running`, `pid`, `cpu`, and `ram_mb`. Set
>   `expect_running: true` if the job should always be running.
> - **Log file** — tail-scanned. **Universal health rule:** any line containing `ERROR` or
>   `CRITICAL` flags the project unhealthy. Reserve those words for real failures (e.g. CUDA OOM,
>   crashed training).
> - **Static metrics** — MayBot does not parse training/inference metrics; anything I want shown
>   (e.g. `model: my-model`, `epoch: 12`) goes in the static `metrics:` map and is displayed as-is.
> - **Git** — set `path` to a git checkout to show branch/dirty/last-commit.
>
> **`projects.yaml` block** — add this to MayBot's `projects.yaml` under `projects:`:
>
> ```yaml
>   - name: my-ai-project
>     type: ai_project
>     path: /path/to/ai-repo
>     expect_running: false                   # true if a long-running job should always run
>     cmdline_contains: train.py              # or process_name / pid_file
>     log_file: /path/to/ai-repo/logs/run.log
>     metrics:
>       model: my-model                        # static, shown as-is
>       stage: training
>     commands:
>       start:
>         argv: ["python", "train.py"]
>         cwd: /path/to/ai-repo
>         stdout: logs/run.log
>         stderr: logs/run.log
>         background: true
>       run_tests:
>         argv: ["python", "-m", "pytest", "-q"]
>         cwd: /path/to/ai-repo
>         timeout_seconds: 300
> ```
>
> Ensure the process is matchable, the log path is correct, and `ERROR`/`CRITICAL` only appear on
> real failures.

---

## local_ai_host

> **Prompt — paste into a coding agent working on your local model-serving host:**
>
> My locally-hosted model API will be monitored by an external read-only dashboard called
> **MayBot**. It does not import my code; it actively probes my model server's HTTP API and
> watches the host process. This type is for **LAN/VPN/local-only model APIs — do not expose them
> publicly.** Make my server expose the endpoints MayBot probes. Supported providers are exactly:
> `ollama`, `llama_cpp`, `lmstudio`, `openai_compatible`, `custom`.
>
> **What MayBot probes per provider** (all GET, 5s timeout; it records `status` online/offline,
> `response_time_ms`, `available_models`, `loaded_model`, and for Ollama `api_version`):
>
> - **`ollama`** — `GET <base_url>/api/tags` (or my `health_url`); reads `models[].name` →
>   `available_models`. Also `GET <base_url>/api/version` → `api_version`.
> - **`openai_compatible`** / **`lmstudio`** — `GET <base_url>/v1/models`; reads `data[].id` →
>   `available_models`.
> - **`llama_cpp`** — `GET <base_url>/health` (or my `health_url`); falls back to
>   `GET <base_url>/v1/models` and reads `data[].id`.
> - **`custom`** — requires `health_url`; MayBot just GETs it and treats `2xx` as online.
>
> Rules:
> - The first entry in `available_models` is reported as `loaded_model`. List the active/default
>   model first if order matters.
> - If the probe is not `2xx`/reachable, `status` becomes `offline` and **health = error**.
> - `provider` must be one of the supported set above, and `base_url` is required (except for
>   `custom`, which requires `health_url`) — otherwise status is `unknown`.
> - **Process** — MayBot also matches the host process by `cmdline_contains` (or
>   `pid_file`/`process_name`) and reports `pid`, `cpu_usage`, `ram_usage_mb`. With
>   `expect_running: true`, a stopped process forces **health = error**.
> - **`log_file`** — if set, MayBot reports whether it is `present`/`missing` and applies the
>   universal rule: any recent line containing `ERROR`/`CRITICAL` flags it unhealthy.
> - **Optional prompt test** — only for `openai_compatible`/`lmstudio` and only if
>   `test_prompt_enabled: true`; MayBot POSTs a 1-token `chat/completions` request. Leave it
>   `false` unless I want it.
>
> **`projects.yaml` block** — add the entry matching my provider to MayBot's `projects.yaml`:
>
> ```yaml
>   # Ollama
>   - name: my-ollama-host
>     type: local_ai_host
>     provider: ollama
>     base_url: http://127.0.0.1:11434
>     health_url: http://127.0.0.1:11434/api/tags
>     default_model: nous-hermes
>     expect_running: true
>     cmdline_contains: ollama
>     test_prompt_enabled: false
>
>   # OpenAI-compatible / LM Studio
>   - name: my-openai-compatible-host
>     type: local_ai_host
>     provider: openai_compatible        # or: lmstudio
>     base_url: http://127.0.0.1:1234
>     health_url: http://127.0.0.1:1234/v1/models
>     default_model: hermes
>     expect_running: true
>     cmdline_contains: my-server
>     test_prompt_enabled: false
>
>   # llama.cpp
>   - name: my-llamacpp-host
>     type: local_ai_host
>     provider: llama_cpp
>     base_url: http://127.0.0.1:8080
>     # health_url: http://127.0.0.1:8080/health   # optional override
>     default_model: my-gguf
>     expect_running: true
>     cmdline_contains: llama-server
>     test_prompt_enabled: false
> ```
>
> Make sure the probed endpoint(s) above return the documented JSON shape, keep the server
> local-only, and ensure the host process is matchable by the configured `cmdline_contains`.

---

## generic

> **Prompt — paste into a coding agent working in your project's repo:**
>
> My project will be monitored by an external read-only dashboard called **MayBot** using its
> most basic adapter. It does not import my code; it only watches the universal base signals:
>
> - **Process** — found by `pid_file` (relative to `path`), `cmdline_contains`, or
>   `process_name`; reports `running`, `pid`, `cpu`, `ram_mb`. With `expect_running: true`, a
>   stopped process raises `ERROR: process expected but stopped`.
> - **Git** — if `path` is a git checkout, reports branch, dirty/clean, last commit.
> - **Log file** — if `log_file` is set, MayBot tails it. **Universal health rule:** any recent
>   line containing `ERROR` or `CRITICAL` flags the project unhealthy. A missing configured
>   `log_file` raises a warning; a missing `path` raises an error.
> - **Static metrics** — anything in the `metrics:` map is displayed as-is; the generic adapter
>   parses nothing project-specific.
>
> **`projects.yaml` block** — add this to MayBot's `projects.yaml` under `projects:`:
>
> ```yaml
>   - name: my-project
>     type: generic
>     path: /path/to/project                  # optional, for git status
>     expect_running: false                   # true to require a running process
>     cmdline_contains: my-process            # or pid_file / process_name
>     log_file: /path/to/project/logs/app.log # optional
>     metrics:
>       note: anything here is shown as-is
>     commands:
>       start:
>         argv: ["./run.sh"]
>         cwd: /path/to/project
>         background: true
>       stop:
>         match_cmdline_contains: my-process
> ```
>
> Make the process matchable, point `log_file` at a real file if used, and keep `ERROR`/`CRITICAL`
> out of normal log output.
