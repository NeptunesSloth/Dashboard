# MayBot Control Center

MayBot Control Center is a **distributed, monitoring-first dashboard** for tracking projects across multiple machines.

It has two components:
- **`maybot_agent`** — runs on each device that hosts projects/bots; reads local status/logs/metrics and exposes an authenticated HTTP API.
- **`maybot_control_center`** — central web dashboard that polls all configured agents and shows a unified view.

> ⚠️ Security posture: this system is intended for **private/local networks (LAN/VPN)** and should **not be exposed publicly** by default.

---

## What Goes Where

| Machine | What to install | What to configure |
|---|---|---|
| Every device hosting a bot/project | `maybot_agent` | `projects.yaml` |
| The machine running the dashboard | `maybot_control_center` | `devices.yaml` |

One machine can run both if you want to monitor local projects from the same machine.

---

## Architecture

```
[TradeBot Server] -> maybot_agent -> [Control Center Dashboard]
[DayBot Server]   -> maybot_agent -> [Control Center Dashboard]
[Other Device]    -> maybot_agent -> [Control Center Dashboard]
```

Each agent reads a local `projects.yaml`. The control center reads `devices.yaml` to discover agents.

---

## ⭐ Pulling data from the hosts running your bots

**Mental model — the control center PULLS; agents never push.** On every poll the
dashboard reaches *out* over HTTP to each host listed in `devices.yaml`,
authenticates with a shared token, and pulls that host's project status, health,
logs, and metrics:

```
 your bot host                          dashboard host
 ┌───────────────────────────┐          ┌────────────────────────┐
 │ maybot_agent  (port 8100)  │  ◀──────  │ maybot_control_center  │
 │  reads projects.yaml       │   HTTP    │  reads devices.yaml     │
 │  (your bots live here)     │   pull    │  (list of agent URLs)   │
 └───────────────────────────┘          └────────────────────────┘
```

So there are exactly **three things to get right** per bot host:

**1. On the bot host — run the agent and tell it about your bots.**
Create `projects.yaml` (see `projects.yaml.example`) listing each bot, then start the agent bound to an address the dashboard can reach (a LAN/VPN/Tailscale IP — *not* `127.0.0.1` unless it's the same machine):

```bash
export MAYBOT_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
echo "token for this host: $MAYBOT_API_TOKEN"   # you'll paste it into devices.yaml
uvicorn maybot_agent.app:app --host 0.0.0.0 --port 8100
```

**2. On the dashboard host — list that host in `devices.yaml`.**
The `url` is the agent's address; the `api_token` MUST equal that host's `MAYBOT_API_TOKEN`:

```yaml
devices:
  - name: trade-server
    url: http://100.64.0.2:8100        # the bot host's reachable IP + agent port
    api_token: "the-token-printed-above"
```

**3. Verify the link, then (re)start the control center.**
Run the bundled checker from the dashboard host — it tells you PASS/FAIL and the exact cause:

```bash
scripts/check-agent.sh http://100.64.0.2:8100 the-token-printed-above
```

A `PASS` means the dashboard can pull from that host; the data appears on the
next poll. Repeat steps 1–3 for every machine running bots. The
`GET /api/history/{device}/{project}` and per-card sparklines are populated from
this pulled data automatically.

**Troubleshooting (what `check-agent.sh` reports):**
- `401` → the `api_token` in `devices.yaml` doesn't match the host's `MAYBOT_API_TOKEN`.
- `no response (000)` → agent not running, wrong host/port, agent bound to `127.0.0.1` instead of the LAN IP, or a firewall is blocking the port.
- `0 projects` → the link works, but that host's `projects.yaml` is empty or missing.

> 📖 Full step-by-step for the agent side (install, per-type `projects.yaml` examples, systemd/Docker, security, reference): **[docs/AGENT_SETUP.md](docs/AGENT_SETUP.md)**.

---

## Out-of-the-box defaults (everything on)

`docker compose up` ships with **every capability enabled** (see `docker-compose.yml` / `.env.example`): SQLite persistence, 90-day retention, daily disk backups, a daily summary report, alert ack/snooze, self-observability, **and the autonomous tier — Autopilot remediation, agent tool autonomy, task delegation, and real GitHub PRs.**

```bash
cp .env.example .env          # then fill in secrets (tokens, ANTHROPIC_API_KEY, channels)
docker compose up
```

> ⚠️ **Autopilot can restart/stop your live bots and run remediation, and agents can auto-run guarded tools and open real PRs.** This is intentional per the chosen configuration. To dial it back, set any of `MAYBOT_AUTOPILOT`, `MAYBOT_AUTONOMY`, `MAYBOT_DELEGATION`, `MAYBOT_PR_ENABLED` to `0` in `.env`. Always set `MAYBOT_CONTROL_CENTER_TOKEN` before exposing the dashboard on any network. Real PRs additionally need `gh` auth (`GH_TOKEN`) and a repo (`MAYBOT_PR_REPO`); without them, fixes are recorded as review-only "proposed PRs". The public status page stays **off** by default.

---

## Prerequisites

Before you start, confirm these are installed on each machine:

```bash
# Check Python version — must be 3.10 or higher
python3 --version

# Check pip
pip3 --version

# Check git
git --version
```

If `python3 --version` shows below 3.10, install it first:
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv git -y
```

---

## Step 1 — Clone the repo (on every machine)

Run this on **each machine** (agent hosts AND the control center host):

```bash
git clone https://github.com/neptunessloth/dashboard.git /opt/maybot
cd /opt/maybot
```

> If you don't want it in `/opt/maybot`, change that path — just use the same path consistently in all commands below.

---

## Step 2 — Create a virtual environment and install dependencies (on every machine)

Run this on **each machine**:

```bash
cd /opt/maybot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected output ends with something like:
```
Successfully installed fastapi-0.115.0 uvicorn-0.30.6 pyyaml-6.0.2 ...
```

> Every time you open a new terminal, re-run `source /opt/maybot/.venv/bin/activate` before using `uvicorn`.

---

## Step 3 — Set up each agent host (device running a bot/project)

Do this on **each machine that hosts a project**.

### 3a — Generate a secret token

Pick a long random string. Run this to generate one:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output. It will look like:
```
a3f9e2b1c8d7f6e5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1
```

**Save this token** — you will need it again in Step 4.

### 3b — Export the token (current terminal session)

```bash
export MAYBOT_API_TOKEN="paste-your-token-here"
```

Replace `paste-your-token-here` with the token from 3a.

### 3c — Create your projects config

```bash
cd /opt/maybot
cp projects.yaml.example projects.yaml
```

Open `projects.yaml` in a text editor and fill in the details for your project:

```bash
nano projects.yaml
```

At minimum, update:
- `name` — a label for your project
- `path` — the absolute path to your project folder
- `log_file` — the absolute path to the project's log file
- `cmdline_contains` — a keyword that appears in the process command line when it's running

See [Configuration examples](#configuration-examples) below for a full annotated example.

### 3d — Start the agent

```bash
cd /opt/maybot
source .venv/bin/activate

# Bind to localhost only (safest — use this if control center is on the same machine)
uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100

# OR — bind to your LAN/VPN IP so other machines can reach it
# Replace 100.x.x.x with your actual Tailscale/LAN IP
uvicorn maybot_agent.app:app --host 100.x.x.x --port 8100
```

> ⚠️ Do **not** bind to `0.0.0.0` unless the machine is behind a firewall or VPN.

### 3e — Verify the agent is working

Open a second terminal on the same machine and run:

```bash
curl -H "x-api-token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/ping
```

Expected response:
```json
{"status": "ok"}
```

If you see `401 Unauthorized`, the token in your curl command doesn't match what the agent started with — re-export and restart.

If you see `Connection refused`, the agent didn't start — check the terminal where you ran `uvicorn` for errors.

---

## Step 4 — Set up the control center (dashboard machine)

Do this on the **one machine that will display the dashboard**.

### 4a — Create your devices config

```bash
cd /opt/maybot
cp devices.yaml.example devices.yaml
nano devices.yaml
```

Add an entry for each agent host. Use the token from Step 3a for each device:

```yaml
devices:
  - name: tradebot-server          # a label — anything you like
    url: http://100.64.10.20:8100  # the IP/port where that agent is listening
    api_token: "paste-token-here"  # the MAYBOT_API_TOKEN from that agent host

  - name: daybot-server
    url: http://100.64.10.21:8100
    api_token: "paste-other-token-here"
```

> If the control center and agent are on the same machine, use `http://127.0.0.1:8100`.

### 4b — Start the control center

```bash
cd /opt/maybot
source .venv/bin/activate
uvicorn maybot_control_center.app:app --host 127.0.0.1 --port 8200
```

### 4c — Open the dashboard

Open your browser and go to:

```
http://127.0.0.1:8200
```

You should see the dashboard with all configured devices listed. If a device shows **offline**, see [Troubleshooting](#troubleshooting) below.

---

## Configuration examples

### `projects.yaml` — trading bot

```yaml
projects:
  - name: tradebot-main
    type: trading_bot
    path: /opt/tradebot
    log_file: /opt/tradebot/logs/bot.log
    database: /opt/tradebot/data/trading.sqlite3
    trade_csv_glob: logs/paper_trades_*.csv  # DayBot paper/replay CSV fallback

    pid_file: run/tradebot.pid
    cmdline_contains: tradebot
    expect_running: true

    metrics:
      mode: paper

    commands:
      run_tests:
        argv: [".venv/bin/python", "-m", "pytest", "-q"]
        cwd: /opt/tradebot
        timeout_seconds: 300

      start:
        argv: ["./scripts/start_paper.sh"]
        cwd: /opt/tradebot
        stdout: logs/bot.log
        stderr: logs/bot.log
        pid_file: run/tradebot.pid
        background: true

      stop:
        pid_file: run/tradebot.pid
        match_cmdline_contains: tradebot
```

### `devices.yaml`

```yaml
devices:
  - name: tradebot-server
    url: http://100.64.10.20:8100
    api_token: "replace-with-agent-token"

  - name: daybot-server
    url: http://100.64.10.21:8100
    api_token: "replace-with-agent-token"
```

---

## Keep agents running with systemd (recommended)

Running `uvicorn` directly in a terminal stops when you close it. Use systemd to keep agents running permanently.

### Agent service — `/etc/systemd/system/maybot-agent.service`

```ini
[Unit]
Description=MayBot Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/maybot
Environment=MAYBOT_API_TOKEN=paste-your-token-here
ExecStart=/opt/maybot/.venv/bin/uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Control center service — `/etc/systemd/system/maybot-control-center.service`

```ini
[Unit]
Description=MayBot Control Center
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/maybot
ExecStart=/opt/maybot/.venv/bin/uvicorn maybot_control_center.app:app --host 127.0.0.1 --port 8200
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now maybot-agent
sudo systemctl enable --now maybot-control-center

# Check status
sudo systemctl status maybot-agent maybot-control-center
```

To view logs:
```bash
sudo journalctl -u maybot-agent -f
sudo journalctl -u maybot-control-center -f
```

---

## Adding a new project later

1. On the device hosting the project, add it to `projects.yaml`.
2. Restart the agent on that device.
   ```bash
   sudo systemctl restart maybot-agent
   # or if running manually, Ctrl+C and re-run uvicorn
   ```
3. If this is a brand-new device, add it to `devices.yaml` on the control center host and restart the control center.
4. Refresh the dashboard in your browser.

---

## Troubleshooting

### Agent shows offline in dashboard
- Check the agent is actually running: `sudo systemctl status maybot-agent` or look at the terminal where you started uvicorn.
- Verify the URL and port in `devices.yaml` exactly match how the agent was started.
- Test reachability from the control center machine: `curl -H "x-api-token: YOUR_TOKEN" http://AGENT_IP:8100/api/ping`
- Verify VPN/LAN connectivity between the two machines.

### 401 Unauthorized
- The token in `devices.yaml` doesn't match `MAYBOT_API_TOKEN` on that agent.
- If using systemd, check `Environment=MAYBOT_API_TOKEN=...` in the service file, then `sudo systemctl daemon-reload && sudo systemctl restart maybot-agent`.

### Connection refused
- Agent is not running, or bound to a different IP/port than expected.
- Test locally on the agent host first: `curl -H "x-api-token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/ping`

### Missing `projects.yaml`
- Agent returns an empty project list. Copy the example and edit it:
  ```bash
  cp projects.yaml.example projects.yaml
  nano projects.yaml
  ```

### Missing `devices.yaml`
- Control center has nothing to poll. Copy and edit:
  ```bash
  cp devices.yaml.example devices.yaml
  nano devices.yaml
  ```

### Bot shows `unknown` status
- The adapter can't find the expected data (log file missing, DB schema mismatch, wrong path).
- Double-check `path`, `log_file`, and `database` paths exist and are readable by the user running the agent.

### Log file missing
- Ensure `log_file` path exists and is readable.
- If the bot hasn't started yet, the log file may not exist — start the bot first.

- `ai_project` = track AI-assisted coding project workflow/health (Claude/Codex/etc. usage in a software project).
- `local_ai_host` = track availability/health of a locally hosted model API endpoint.

### Example: Ollama / Hermes host

```yaml
projects:
  - name: Hermes Local AI
    type: local_ai_host
    path: /opt/ollama
    provider: ollama
    base_url: http://127.0.0.1:11434
    default_model: nous-hermes
    expect_running: true
    cmdline_contains: ollama
    log_file: /var/log/ollama.log
    test_prompt_enabled: false
    health_url: http://127.0.0.1:11434/api/tags
```

```yaml
projects:
  - name: Local LLM API
    type: local_ai_host
    provider: openai_compatible
    base_url: http://127.0.0.1:1234
    default_model: hermes
    expect_running: true
    health_url: http://127.0.0.1:1234/v1/models
    test_prompt_enabled: false
```

## Operations & deployment

- **One-command run:** `docker compose up` brings up the control center (`:8200`) and a co-located agent (`:8100`). Configure via a `.env` file (`ANTHROPIC_API_KEY`, `MAYBOT_CONTROL_CENTER_TOKEN`, `MAYBOT_API_TOKEN`); persistence is on by default (`MAYBOT_DB=/data/maybot.db`).
- **Prometheus metrics:** `GET /metrics` exposes monitoring + sect stats (devices/projects health, treasury balance, LLM calls/cost, tool calls by status, and per-disciple realm/stones/breakthroughs/techniques) in Prometheus text format for Grafana. It reads only cached/in-memory state, so a scrape never triggers a device poll.
- **Alerting webhooks:** noteworthy events (incidents, heavenly tribulations) route to Discord/Slack/a generic JSON webhook. Set `MAYBOT_DISCORD_WEBHOOK_URL` / `MAYBOT_SLACK_WEBHOOK_URL` / `MAYBOT_ALERT_WEBHOOK_URL` and choose which events with `MAYBOT_ALERT_EVENTS` (default `incident,tribulation`). The existing health-transition alerts (`MAYBOT_ALERT_STATES`) still apply.
- **Alert noise control:** health alerts are **deduplicated** (no repeat page for the same project+state within `MAYBOT_ALERT_COOLDOWN_SECONDS`, default 300), **flap-suppressed** (a project changing state `MAYBOT_ALERT_FLAP_THRESHOLD`+ times within `MAYBOT_ALERT_FLAP_WINDOW_SECONDS` is announced once as *flapping*, then muted until it settles), and followed by a **recovery** notice when it returns to ok (`MAYBOT_ALERT_RECOVERY=1`). Webhook delivery retries with backoff (`MAYBOT_WEBHOOK_RETRIES`, default 2).
- **Health & readiness probes:** `GET /healthz` (liveness) and `GET /readyz` (readiness; reports last-poll device health, returns 503 with `?strict=1` when any device is offline) — both unauthenticated and secret-free, for uptime monitors and the Docker/compose `HEALTHCHECK`.
- **Maintenance windows / alert silencing:** mute alerting (and incident auto-dispatch/remediation) during planned upkeep. `POST /api/maintenance/silence` with `{target, minutes, reason}` where `target` is `*`, `device:*`, or `device:project` (`minutes: 0` = until lifted or recovery); `GET /api/maintenance` lists active silences, `POST /api/maintenance/unsilence` lifts one. Drive it from the dashboard's **Reliability** panel.
- **SLO / uptime (`GET /api/slo?hours=`):** time-weighted rolling **uptime %**, **incident** count, and **MTTR** per project, computed from the recorded health history (`unknown` samples excluded from the denominator). Window defaults to `MAYBOT_SLO_WINDOW_HOURS` (168h / 7d). Also exported to Prometheus (`maybot_project_uptime_ratio`, `maybot_project_incidents`, `maybot_project_mttr_seconds`).
- **Data export:** `GET /api/export/usage` and `GET /api/export/history` stream CSV (or `?fmt=json`) for offline analysis/reporting.
- **Per-device poll timeout:** a slow/hung agent can't stall the whole fleet poll — each request is capped at `MAYBOT_AGENT_TIMEOUT` (default 5s), overridable per device with a `timeout:` field in `devices.yaml`.
- **Error budgets & deploy-freeze — "Karmic Debt / Heavenly Decree" (`GET /api/errorbudget`):** each project gets an SLO target (`MAYBOT_SLO_TARGET_PCT`, default 99.0; per-project overrides via `MAYBOT_SLO_TARGETS="device:project=99.9,…"`). The gap between target and measured uptime is its **error budget**; when a project burns through it, state-changing actions (`start`/`stop`) are **frozen** (`POST /api/action/...` returns 423) until reliability recovers — override with `?force=true`. Surfaced as a 🔒 *Decree* badge and a budget bar in the **Reliability** panel.
- **Dependency-aware alerting — "Meridian Map" (`GET /api/meridians`):** declare project dependencies in `meridians.yaml` (see `meridians.yaml.example`). When an upstream a project `depends_on` is unhealthy, the downstream's own `error` is recognised as a *blocked meridian* (downstream symptom) and its page is suppressed (`MAYBOT_MERIDIAN_SUPPRESS=1`) so only the root cause pages. Tagged ⛓ *downstream* in the UI.
- **Synthetic uptime probes — "Warding Talismans" (`GET /api/talismans`):** control-center-side periodic HTTP checks of arbitrary URLs (status + latency), independent of any agent, defined in `talismans.yaml` (see `talismans.yaml.example`). Results feed the same history/SLO pipeline (synthetic device `warding`). No file → idle.
- **Scheduled / recurring maintenance windows — "Heavenly Calendar":** schedule silences in advance in `calendar.yaml` (see `calendar.yaml.example`) — recurring daily/weekly windows (`days`, `start`, `duration_minutes`) or one-off ISO-8601 windows. An active window silences its target automatically; upcoming/active windows show in `GET /api/maintenance` and the Reliability panel.
- **Incident acknowledgement & ownership — "Sworn Oath" (`GET /api/oaths`):** a disciple/operator *claims* an incident (`POST /api/oaths/claim` `{target, who, note}`); repeat pages are then suppressed (someone owns it), the owner shows on the dashboard, and the oath auto-releases on recovery (`POST /api/oaths/release` to drop it manually). Distinct from silencing — it records ownership rather than ignoring.
- **Escalation policy — "Chain of Command" (`GET /api/escalation`):** an `error` alert that is neither claimed (oath) nor silenced is escalated after `MAYBOT_ESCALATE_AFTER_SECONDS` (default 900) — an `escalation` webhook event plus a notice in the Ancestor's Hall, once per incident. Generalises the Night-Watch escalation to every project.
- **Public status page — "Sect Proclamation":** opt-in (`MAYBOT_PUBLIC_STATUS=1`), unauthenticated read-only page at `GET /status` (HTML) and `GET /api/status/public` (JSON), showing per-service state + uptime% derived from SLO data — no tokens, URLs, costs, or agent internals. Off by default.
- **Autopilot — the Sect Leader's "second brain" (`GET /api/autopilot`, `POST /api/autopilot/pause|resume`):** opt-in (`MAYBOT_AUTOPILOT=1`) autonomous operations. The Sect Leader runs a headless loop over the fleet — **detect → diagnose → act → verify → continue → report** — and *fixes unhealthy projects without you*: it diagnoses the cause (LLM, heuristic fallback) and, in full-auto, restarts the bot, runs a remediation runbook, or dispatches a coding disciple to patch the project and run its tests; on recovery it stands down, and after `MAYBOT_AUTOPILOT_MAX_ATTEMPTS` (default 3) it escalates to the Ancestor. Every step is reported to the **Ancestor's Hall** and the alert **webhooks** (`autopilot` event). A runtime **kill switch** (the Pause button / `POST /api/autopilot/pause`) and the env gate keep it controllable; tune with `MAYBOT_AUTOPILOT_INTERVAL`, `MAYBOT_AUTOPILOT_STATES`, `MAYBOT_AUTOPILOT_CODER`.
- **Disciples ship real PRs (`MAYBOT_PR_ENABLED`):** when the autopilot judges a failure to be a code issue, a coding disciple drafts the fix as a unified diff. With `MAYBOT_PR_ENABLED=1` + the `gh` CLI + a resolvable repo (`MAYBOT_PR_REPO` or a `owner/name` project) it **opens a real pull request**; otherwise it records a reviewable **Proposed PR** (title/body/diff) in the artifact vault. Detect → diagnose → **patch as a PR**.
- **Compounding sect memory (RAG):** task results, post-incident summaries, Elder manuals, and roamed skills accumulate in a shared, searchable memory (`/api/sectmemory`, the *Sect Knowledge* panel); every disciple retrieves the most relevant entries into its prompt before acting, so the sect gets smarter the longer it runs (`MAYBOT_SECT_MEMORY`).
- **Skills are real capabilities:** a skill roamed from the web fetches its how-to from the source page into sect memory, and each disciple's mastered techniques are injected into its prompt — a learned skill changes behavior, not just a label.
- **Ascension:** a disciple's cultivation realm unlocks a stronger model (Haiku→Sonnet→Opus at `MAYBOT_ASCEND_SONNET_REALM`/`_OPUS_REALM`); `run_task` runs high-realm disciples on the ascended model (upgrade-only, same provider family).
- **Login UI + sessions:** a sign-in overlay validates the control token (`POST /api/login`) and persists it for the session; sign-out clears it. The dashboard prompts for a token whenever a request is unauthorized.
- **Inbound alert ingestion (`POST /api/ingest/alert`):** external systems (Alertmanager, CI, cron) push incidents *into* the dashboard — stored in a feed, routed to your webhooks/Hall, and added to sect memory. Auth via the operator token or a dedicated `MAYBOT_INGEST_TOKEN`.
- **State backup / restore (`GET /api/backup`, `POST /api/restore`):** export/import the persisted coordination state (board, oaths, silences, autopilot, sect memory, audit, inbound, registry) as one JSON blob (requires `MAYBOT_DB`).
- **Agent auto-registration (`POST /api/agents/register`):** agents announce themselves (name/url/token) instead of being hand-listed; merged with `devices.yaml`. Gated by `MAYBOT_REGISTER_TOKEN`.
- **Web Push (`MAYBOT_VAPID_PUBLIC`/`_PRIVATE`):** the installable PWA can receive push notifications for alerts even when closed — `pip install pywebpush` and set VAPID keys; without them, subscriptions are stored and sends are a safe no-op.
- **Per-project PR mode:** `autopilot.yaml` `pr: open|propose` overrides the global `MAYBOT_PR_ENABLED` so some repos auto-open PRs while others only propose.
- **Project integration prompts:** `docs/INTEGRATION_PROMPTS.md` has copy-paste prompts to make each project type dashboard-ready.
- **Scheduled missions (cron):** define recurring sect activities in `schedules.yaml` (see `schedules.yaml.example`) — a `task`, `mission`, `quest`, or `debate` per `every_minutes`. A background scheduler fires them (first interval after startup, not at boot); no file → idle.
- **Hall of Fame:** the dashboard ranks disciples by Strongest (realm/stones), Richest, Most Techniques, and Most Breakthroughs.

## Trust, omens & formations

Three features that wear the cultivation costume but earn their keep as real ops value:

- **Reputation / trust tiers (`GET /api/reputation`):** a merit score (0-100) is derived live from the audit log + cultivation state — LLM success rate, guarded-tool reliability (completed vs failed/denied calls), realm/breakthroughs, minus a current failure streak — and maps to a tier shown on each disciple card. **Trusted** (≥75) disciples earn bonus autonomy budget (`MAYBOT_TRUST_AUTONOMY_BONUS`, default 3); **Probation** (<45) disciples are demoted back to human approval — their auto-runs are blocked regardless of `auto_approve`. So autonomy is *earned*: trust-based privilege escalation/de-escalation for autonomous tools. Tune the gates with `MAYBOT_TRUST_TRUSTED` / `MAYBOT_TRUST_PROBATION`.
- **Prophecy / divination (`GET /api/prophecy`):** the **Heavenly Omens** section reads each project's recorded metrics history (the same series behind the sparklines) and forecasts near-term health with a light trend + anomaly model — a recent error, a z-score plunge, or a worsening PnL slope surfaces as an *ill omen* (ominous/caution/favorable, most concerning first). Under the costume it's simple early-warning/anomaly detection on monitoring data.
- **Formations / agent workflows (`GET /api/formations`, `POST /api/formations/run`):** a **formation array** is a saved, reusable multi-agent pipeline run as a DAG of stages (e.g. scout → analyze → propose → review). Each stage's disciple sees the goal plus every prior stage's output and adds its part. Defined in `formations.yaml` (see `formations.yaml.example`; a built-in default works out of the box); stages without an explicit `agent` are auto-assigned round-robin. Reuses the council's one-activity-at-a-time guard. Operator-gated; launch from the **Dao Council** section.

## Sect governance (the Ancestor, the Sect Leader & Elders)

A meritocratic hierarchy over the disciples. **You are the Ancestor** — ultimate authority; disciples address you as such, and you can override any decision. API: `GET /api/governance` plus operator-gated `POST` actions.

- **Sect Leader = the most capable mind.** The seat auto-seeds to the disciple with the highest **aptitude** — a composite of **reasoning** (model capability + spirit-root assessment), **intelligence** (demonstrated LLM reliability), **knowledge** (realm depth + breakthroughs), and **skills** (techniques mastered, incl. those roamed from the web). Leadership challenges are decided by aptitude too. The Ancestor can still appoint/pin anyone (`POST /api/governance/leader`) or release the seat back to merit. Routine tasks assigned to the Leader are auto-delegated to a deputy Elder — the Leader handles only work marked `critical`.
- **Standing** is a composite (0-100) of **merit** (reputation/karma), **performance** (LLM success rate), **leadership** (realm depth + breakthroughs + specialty mastery), and **contribution** (work shipped). It decides challenges.
- **Leadership challenges:** an Elder may challenge the Sect Leader (`POST /api/governance/challenge`). The challenger must beat the Leader's standing by `MAYBOT_CHALLENGE_MARGIN` (default 3) to win — on a win the role swaps immediately (the Ancestor can still override). A per-Elder cooldown (`MAYBOT_CHALLENGE_COOLDOWN`, default 3600s) prevents constant power struggles; a pinned Leader can't be contested.
- **Elder specialties:** Elders pick a path (`POST /api/governance/specialty`) — Sword Dao (backend), Alchemy (data/ML), Formation Dao (DevOps), Talisman Crafting (frontend), Beast Taming (QA), Artifact Refinement (tooling). Good work deepens their **mastery** rating and teaches the path's signature techniques.
- **The Ancestor's Hall:** a direct inbox (`GET/POST /api/governance/inbox`, `/message`) — only the Sect Leader and Elders may petition you; anyone below Elder rank is refused.
- **Personal projects:** disciples may **not** be assigned to act on your personal bot projects. Mark them with `personal: true` in `projects.yaml`, or list them in `MAYBOT_PERSONAL_PROJECTS` (comma-separated `name` or `device:name`); such a task is rejected (403) and the project is flagged in the overview.
- **GitHub:** disciples can act on GitHub through guarded tools — see the `gh_*` examples in `tools.yaml.example` (reads auto-approve; writes stay human-approved).

## Trials Hall & GitHub

- **Night-Watch on-call (`GET /api/nightwatch`, `POST /api/nightwatch/rotation`, `/{id}/handled`):** an on-call rotation — disciples take timed watch shifts (`MAYBOT_WATCH_SHIFT_SECONDS`, default 1h). The on-watch disciple `triage`s incidents (warnings auto-handled, `error` severity escalated to the Ancestor); resolving a watch earns spirit stones. Real value: on-call rotation with first-line auto-triage.
- **Spirit-Root assessment (`GET /api/spirit-root`, `POST /api/spirit-root/assess`):** a capability benchmark — feed in probe results (`reasoning`/`coding`/`reliability`/`latency`) and a weighted score yields a spirit-root grade (Heavenly → Mortal Dust). Real value: automated per-model capability profiling that can feed the trust tier.
- **Dreamscape dry-run (`POST /api/dreamscape/preview`):** preview a formation's full stage→disciple plan and a token-cost estimate **without calling any LLM**, so you can sanity-check and budget before running it for real.
- **Tribulation Trials / chaos (`GET /api/chaos`, `POST /api/chaos/summon`, `/{id}/resolve`):** deliberately inject a fault scenario (process kill, latency storm, disk drought, endpoint seal) and score how fast a disciple recovers — fast recovery earns stones, failure costs cultivation. Real value: game-day / chaos-engineering drills with scored resilience.
- **GitHub repos as projects (`GET /api/github`):** list repos in `MAYBOT_GITHUB_REPOS` (comma-separated `owner/name`) and they appear in the overview as `github_repo` projects with health from open PRs, failing checks, and open issues (cached `MAYBOT_GITHUB_CACHE_TTL`s; needs the `gh` CLI authenticated). Tasks can also carry a `repo`/`issue` reference (`POST /api/agents/{name}/task`) that's prepended as context, and disciples post back through the human-approved `gh_*` guarded tools.

## Sect Lore (drift, bonds, lineage, votes, artifacts, titles)

- **Dao-Heart drift (`GET /api/daoheart`):** each task's output quality signals (success, length, latency) are recorded; drift compares a disciple's recent window to its baseline and flags `drifting`/`degraded`. Real value: behavioral / quality-regression detection.
- **Karmic-bond pairs (`GET /api/bonds`, `POST /api/bonds/bind|unbind`):** bind two disciples and the partner automatically peer-reviews the other's task output before it ships (the review is appended to the transcript). Real value: mandatory cross-check / pair-agent QA.
- **Lineage (`GET /api/lineage`):** a knowledge graph of who originated each technique and who transmitted it to whom (fed by tool-mastery + the `transmit` flow). Real value: knowledge-transfer & ownership graph.
- **Merit-weighted council vote (`POST /api/council/vote`, `GET /api/council/history`):** disciples vote on an ambiguous call; votes are weighted by sect standing and the decision + dissent is logged. Real value: weighted-ensemble decisions with an audit trail.
- **Artifact vault (`GET /api/artifacts`, `POST /api/artifacts/forge|wield`):** disciples forge reusable, versioned artifacts (prompt templates, tool recipes, formations, notes, technique manuals) with provenance (creator/created_at/version/uses). Real value: an attributed prompt/tool library.
- **Technique manuals (automated):** an idle Elder with **no disciples to mentor** authors a technique `manual` artifact from their specialty/mastered skills (one per `MAYBOT_MANUAL_COOLDOWN_SECONDS`, default 30m), so senior agents keep contributing knowledge to the vault even with no one to teach directly.
- **Titles & achievements (`GET /api/titles`):** disciples earn titles (Immortal Ascendant, Sword Saint, Bane of Bugs, …) from cultivation/reputation/governance milestones, shown as badges on their cards. Real value: gamified engagement + an at-a-glance specialization signal.

## Auto-remediation, chronicle, sect map & active chaos

- **Auto-remediation runbooks (`GET /api/runbooks`):** define `runbooks.yaml` (see `runbooks.yaml.example`) mapping a project match (`type`/`health`/`name_pattern`/`alert_contains`) to a guarded tool + args. When a project goes unhealthy, a matching runbook **requests** its remediation tool (debounced per episode, recovers on `ok`) — still subject to the normal approval/autonomy guards, so nothing destructive runs unsanctioned.
- **Cultivation chronicle (`GET /api/chronicle`, `/api/chronicle/{name}`):** a per-disciple event timeline — breakthroughs, tribulations, leadership challenges/appointments, specialties, and karmic bonds are recorded as a chronological story, shown in the Sect Map's chronicle feed.
- **Sect Map:** a spatial view of the sect arrayed across the heavens — disciples rise through the peaks by realm, the Sect Leader crowned at the summit.
- **Active chaos injection:** `POST /api/chaos/summon` with `{"inject": true}` now *actually* inflicts the fault by requesting a mapped guarded tool (`chaos.FAULT_TOOLS`; see the `chaos_*` examples in `tools.yaml.example`) — always approval-gated, never silent. Without `inject` it stays observe-and-score.

## Agent Crew (LLM persona agents — Phase 1)

The dashboard can run **LLM-backed persona agents** against your local AI hosts. Each agent is defined in `agents.yaml` with a name, role, and persona (system prompt), and points at an Ollama or OpenAI-compatible endpoint. In the **Agent Crew** section you assign a task to an agent and it runs one chat completion in the background, streaming the reply (and a transcript) into its card.

```bash
cp agents.yaml.example agents.yaml
nano agents.yaml   # set name/role/persona/provider/base_url/model per agent
# restart the control center; the "Agent Crew" section appears automatically
```

**Backends:** each agent's `provider` selects where it runs:
- `ollama` / `openai_compatible` / `lmstudio` / `llama_cpp` — a local AI host you point at with `base_url` (reachable from the control center). **Nous Hermes works here** — set `provider: openai_compatible` (or `ollama`) and `model:` to whatever id your host serves (e.g. `hermes`, `nous-hermes2`).
- `claude` (or `anthropic`) — the Claude API via the official SDK. Set `ANTHROPIC_API_KEY` in the control center's environment; no `base_url` needed. Defaults to `claude-opus-4-8`; the stable persona is sent with prompt caching.

**Inter-agent comms (Phase 2):** the **Ship Comms** section lets you give the crew a shared goal and run a bounded round-robin "mission" — each agent contributes per round, building on the channel. Guardrails cap rounds (`MAYBOT_COMMS_MAX_ROUNDS`, default 3), participants (`MAYBOT_COMMS_MAX_PARTICIPANTS`, default 6), and allow only one mission at a time, so total LLM calls per mission (rounds × participants) are bounded. API: `GET /api/comms`, `POST /api/comms/mission`.

**Obsidian vault memory (Phase 3):** point `MAYBOT_OBSIDIAN_VAULT` at an Obsidian vault (a folder of markdown notes) and agents gain a shared, persistent memory — they pull relevant notes in as context (on tasks and missions) and write mission summaries back. Reads are confined to `.md` files inside the vault (path traversal is rejected); writes go only to a dedicated subfolder (`MAYBOT_OBSIDIAN_SUBDIR`, default `MayBot/`) with sanitized filenames, so hand-written notes are never clobbered. The **Vault Memory** dashboard section appears when a vault is configured. Per-agent `memory: false` opts an agent out of context injection.

> Notes injected as context are sent to whatever backend the agent uses — a local host stays local; a `claude` agent sends them to the Anthropic API. Don't point an agent at a vault with secrets you wouldn't send to its backend.

**Guarded tools (Phase 4):** agents can *act* — but only through an explicit allow-list, behind human approval. Define tools in `tools.yaml` (no file → the feature is off). Each tool runs as a **fixed argv with no shell**; an agent may only fill the named `{placeholder}` args you declare, and each value is validated (no spaces or shell metacharacters, bounded length). Every call is **pending until you approve it** in the **Tools** dashboard section, unless a tool sets `auto_approve: true` (reserve that for safe, read-only tools). An agent requests a tool by ending its reply with a fenced block:

````text
```tool
{"tool": "list_dir", "args": {"path": "/opt/daybot/logs"}}
```
````

The request is created as **pending** — it never runs until a human approves. (Tool requests are wired into single-agent tasks only, not multi-agent missions, to keep the blast radius small.) See `tools.yaml.example`. API: `GET /api/tools`, `POST /api/tools/run`, `POST /api/tools/{id}/approve|deny`.

> ⚠️ Tools execute real commands on the agent host. Keep the allow-list narrow, prefer absolute `argv`/`cwd`, and only set `auto_approve` on commands that are safe to run unattended.

**Reliability & autonomy:**
- **Persistence (opt-in):** set `MAYBOT_DB` to a SQLite path and metrics history, agent transcripts, the comms feed, and the **tool-call audit log** survive restarts (reloaded on startup). Unset → in-memory only (default).
- **Agentic tool loop:** when a guarded tool an agent requested completes, its result is fed back so the agent can continue (request another tool or finish). Bounded by `MAYBOT_AGENT_MAX_FOLLOWUPS` (default 4) per operator task — each tool step still needs approval unless `auto_approve`.
- **Event-driven missions:** set `MAYBOT_INCIDENT_AGENT` to an agent name and, whenever a project goes unhealthy, that agent is auto-dispatched a diagnostic task (it can request a guarded tool to read logs, then post findings). Debounced: one dispatch per incident until the project recovers.
- **Live updates (SSE):** the dashboard subscribes to `/api/stream` and refreshes the relevant section the instant an agent reply, comms message, or tool status changes — no waiting for the poll.
- **Bounded autonomy (opt-in, default OFF):** by default an agent's tool request is queued for approval *even for `auto_approve` tools* — agents never act unattended. Set `MAYBOT_AUTONOMY=1` and an agent may auto-run an `auto_approve` tool only while under its **per-task budget** (`MAYBOT_AUTONOMY_MAX_CALLS`, default 3; per-tool override via `max_auto_per_task` in `tools.yaml`), within an optional **time window** (`MAYBOT_AUTONOMY_HOURS`, e.g. `9-17`), and while not **paused**. The Tools section shows the budget/window and a **Pause/Resume kill switch** (`POST /api/autonomy/pause|resume`); an **approval audit log** view lists the persisted tool-call history. Operator-initiated runs are never affected.
- **Cultivation (reward & punishment):** disciples (agents) earn **spirit stones** for good work — completing tasks, mastering a new **technique** (first success with a tool), and joining the Dao Council. With enough stones *and* techniques they **break through** realms, each split into **9 sub-realm layers** (e.g. "Core Formation · 7th Layer"; Qi Condensation → Foundation Establishment → Core Formation → … → Immortal Ascension). Failures chip stones; a streak calls down a **heavenly tribulation** that strips stones and can strike a disciple **down a realm** (qi deviation). A **Sect Ranking** leaderboard orders disciples by realm/stones with sect titles (Outer → Inner → Core Disciple → Elder → Sect Master). When a project goes unhealthy, the dispatched incident agent **faces a tribulation trial** — survive (resolve it) for a windfall, or be struck down. Per-disciple cards show realm · layer, qi bar, techniques, and breakthrough/tribulation flourishes; `GET /api/cultivation`; persisted via `MAYBOT_DB`.
- **Inner demon (self-critique):** with `inner_demon: true` on an agent (or `MAYBOT_INNER_DEMON=1` globally), after each reply the disciple's **inner demon** critiques the answer; if it finds flaws, the disciple **revises** it before recording. The demon is **harsher at low realms** (a weaker disciple gets up to 3 critique→revise cycles; an ascended one gets fewer or none) and its tone scales with rank. The critique is saved to the transcript.
- **Pills & elixirs:** spend a disciple's **spirit stones** on temporary buffs — *Enlightenment Elixir* (stronger model), *Qi-Gathering Pill* (deeper responses), *Foundation Pill* (+autonomy budget), *Heart-Demon Pill* (harsher inner demon). Concoct from the disciple's card; buffs are time-limited. **Overuse is dangerous:** beyond `MAYBOT_PILL_SAFE` concurrent pills, each extra one risks **qi deviation** (chance `MAYBOT_PILL_DEVIATION` per excess) — a tribulation that scatters every buff and can strike the disciple down a realm. `GET /api/pills`, `POST /api/pills/buy`.
- **Spirit-stone economy:** all rewards/penalties are env-tunable (`MAYBOT_AWARD_*`, `MAYBOT_PENALTY_FAIL`, `MAYBOT_TRIBULATION_*`).
- **Spirit veins & sect treasury:** the sect holds a shared spirit-stone pool (**Spirit Veins** panel + `GET /api/treasury`). Spirit veins channel ambient qi into it (`MAYBOT_VEIN_RATE` per `MAYBOT_VEIN_HOURS`) and a **tithe** of each disciple's good work (`MAYBOT_TITHE`) refills it. It **funds the daily stipend** (`MAYBOT_STIPEND` per `MAYBOT_STIPEND_HOURS`) — when the coffers run dry, stipends stop until the veins (or an elder's **endowment**, `POST /api/treasury/endow`) refill them.
- **Closed-door seclusion:** pull a disciple offline (`POST /api/agents/{name}/seclusion`, or the card button) to cultivate in seclusion. After `MAYBOT_SECLUSION_MINUTES` sequestered it **researches a new technique** (a "Dao Insight" skill) and is **guaranteed a breakthrough** to the next realm (its stones consolidated into the new realm), repeating while it stays in seclusion — until it emerges or reaches Immortal Ascension.
- **Roaming → real web skill-quests:** send a disciple to **wander the world** (`POST /api/agents/{name}/roaming`, or the card button). After `MAYBOT_ROAMING_MINUTES` it **searches the live web for an actual AI skill** (a real technique like *retrieval-augmented generation*, *function calling*, *reranking*…) via a keyless search (DuckDuckGo by default; override with `MAYBOT_SEARCH_URL`), learns it, and records the **source URL** as a vault note — repeating while it roams. If the web is unreachable it falls back to a curated list of genuine AI skills, so roaming always returns something real. You can also **ask a disciple to learn a specific skill** (`POST /api/agents/{name}/learn-goal`, the card's "skill to learn next roam" box, or the right-click menu) — their next roam searches for that skill (or the closest match). Each disciple's known skills (with source links) show on its card, and across the sect in the **Known Skills** tab.
- **Skill transmission:** a higher-ranked disciple can **pass one of its techniques down** to a subordinate it outranks (`POST /api/agents/{teacher}/transmit`, or the Transmit control). The student inherits the technique (counting toward its breakthroughs) and the mentor earns merit.
- **Mission board:** dispatch a disciple on a **quest** (`GET /api/quests`, `POST /api/agents/{name}/quest`) — it runs the quest as a task and, on success, brings back the quest's **unique reward technique** plus spirit stones.
- **Sect tournament:** hold a single-elimination **bracket of debates** (seeded strongest-first by realm then stones) to crown the sect's strongest disciple — the champion earns a big spirit-stone windfall. Launch with 🏯 in the Dao Council; `POST /api/comms/tournament`.
- **Dao debate:** two disciples argue opposing sides of a proposition for N rounds and a third **judges** and declares a winner (the victor earns spirit stones) — a real debate-and-judge ensemble. Launch from the Dao Council; `POST /api/comms/debate`.
- **Delegation hierarchy:** a disciple may hand a task **downward only** — to one of strictly lower cultivation realm. The **Sect Master** (top realm) can delegate to everyone; an **Elder** only to those beneath; peers can't delegate to each other, and no one delegates upward. On each card the "Assign" control gains a target picker listing the disciples that one outranks (delegating rewards the leader with spirit stones). `POST /api/agents/{name}/delegate`. Set `MAYBOT_DELEGATION=1` to also let agents delegate **autonomously** (they get a ```delegate``` block in their prompt listing valid subordinates), bounded by `MAYBOT_AGENT_MAX_DELEGATIONS` per task.
- **Cost & observability:** every LLM call is metered — per-agent calls, success rate, average latency, tokens, and estimated cost (per-model price table; local models are free). Surfaced in the **Usage & Cost** dashboard section and at `GET /api/usage`.
- **Access control (RBAC):** without a users file the legacy single-token mode applies. Add `users.yaml` (see `users.yaml.example`) to map tokens to **viewer** (read-only) or **operator** (read + mutate) roles. All `/api/*` requests are rate-limited (`MAYBOT_RATE_LIMIT` per `MAYBOT_RATE_WINDOW` seconds).

Optional control-center environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MAYBOT_DB` | _(unset)_ | SQLite path for persistence (unset → in-memory) |
| `MAYBOT_OBSIDIAN_VAULT` | _(unset)_ | Path to your Obsidian vault; enables agent memory |
| `MAYBOT_OBSIDIAN_SUBDIR` | `MayBot` | Subfolder agents write into |
| `MAYBOT_TOOLS_FILE` | `tools.yaml` | Guarded tool allow-list (absent → tools off) |
| `MAYBOT_AGENT_MAX_FOLLOWUPS` | `4` | Tool-result feedbacks per task (loop guard) |
| `MAYBOT_AUTONOMY` | `0` | Enable agents to auto-run `auto_approve` tools |
| `MAYBOT_AUTONOMY_MAX_CALLS` | `3` | Agent auto-runs allowed per task (budget) |
| `MAYBOT_AUTONOMY_HOURS` | _(unset)_ | Local-time window for auto-runs, e.g. `9-17` |
| `MAYBOT_USERS_FILE` | `users.yaml` | RBAC token→role map (absent → single-token mode) |
| `MAYBOT_RATE_LIMIT` | `240` | Max `/api/*` requests per window per client (0 = off) |
| `MAYBOT_RATE_WINDOW` | `60` | Rate-limit window, seconds |
| `MAYBOT_INCIDENT_AGENT` | _(unset)_ | Agent auto-dispatched when a project goes unhealthy |
| `MAYBOT_INCIDENT_STATES` | `error` | Health states that trigger an incident |
| `MAYBOT_COMMS_MAX_ROUNDS` | `3` | Max rounds per mission |
| `MAYBOT_COMMS_MAX_PARTICIPANTS` | `6` | Max agents per mission |

**Phase 1 scope & safety:**
- Agents *think and talk only* — they do **not** execute commands or tools, and do not message each other yet.
- For local-host agents, the control center calls `base_url` directly (running it on the same box as Ollama is simplest).
- State (transcripts) is in-memory and resets on restart.

Optional control-center environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MAYBOT_AGENTS_FILE` | `agents.yaml` | Path to the agent definitions |
| `MAYBOT_AGENT_TIMEOUT` | `60` | Per-task LLM request timeout (seconds) |
| `MAYBOT_AGENT_MAX_TURNS` | `20` | Transcript messages kept as context per agent |

API: `GET /api/agents`, `GET /api/agents/{name}`, `POST /api/agents/{name}/task` (`{"task": "…"}`).

## Dashboard features

- **Base view** — a "Base View" toggle in the top bar renders the dashboard as a "ship station": a **crew roster** down the left lists every project with a live status line, and the main area shows each project as a lit "room" in a bunker-style grid (status badge such as TRADING / INFERENCE / CODING / STANDBY, a type icon, and a health-coloured status bar). Trading bots (incl. DayBot) show live PnL, open positions and a PnL sparkline on the room face. Selecting a crew member or room opens a **Manage / Info panel** with key metrics and start / stop / test / logs controls. Toggle back to "Card View" for the detailed metric cards; the choice is remembered per browser.
- **AI Agents area** — `ai_project` and `local_ai_host` projects are surfaced in a dedicated "AI Agents" section at the top of the dashboard with their start / stop / run-tests controls and an at-a-glance online / needs-attention count.
- **Search & filter** — the Projects section has a search box (matches name, device, type, status) and a health filter (OK / Warning / Error / Unknown).
- **Persistent sparklines** — the control center keeps a server-side, in-memory history of each project's `profit_today` and health, so the per-card PnL sparklines survive page refreshes and are shared across all viewers. History is also available at `GET /api/history/{device}/{project}`.

Optional control-center environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MAYBOT_HISTORY_MAX_POINTS` | `240` | Points retained per project series |
| `MAYBOT_HISTORY_MAX_SERIES` | `500` | Max distinct project series tracked |

> History is in-memory only and resets when the control center restarts — it is a monitoring aid, not a system of record.

Safety notes for local AI hosts:
- Test prompt checks are disabled by default.
- Tiny generation checks run only when `test_prompt_enabled: true`.
- Do not expose local model hosts publicly unless protected by VPN/firewall (LAN/VPN/local-only strongly recommended).
- API secrets are not included in dashboard project cards.

---

## Capability upgrades

A set of "ops bread-and-butter" capabilities layered on top of the monitoring core. All are backward-compatible and degrade gracefully — every new feature is a no-op until you configure it.

### Type-aware project adapters

Previously only `trading_bot`, `local_ai_host`, and `code_project` had domain-specific health logic; `game_server`, `school`, and `ai_project` were stubs. They now inspect their own domain (see `projects.yaml.example`):

- **`website`** — on top of up/down + status + latency: a response-time budget (`max_response_ms`), a content assertion (`expect_text` — a 200 that doesn't render the expected marker is treated as an error), and **TLS certificate expiry** for `https` URLs (`check_cert`, `cert_warn_days`, `cert_error_days`).
- **`game_server`** — players/capacity/map/tick-rate from a JSON `query_url` (or a raw TCP port check via `host`+`port`); warns when the server is full or tick rate drops below `min_tps`.
- **`school`** — LMS health from a JSON `query_url`: enrolment, overdue assignments, pass rate, attendance; warns on overdue work or outcomes below `min_pass_rate` / `min_attendance`.
- **`ai_project`** — ML lifecycle (phase, model, GPU/VRAM, loss, eval score) plus a log scan for AI-specific failures (CUDA OOM, NaN/inf loss).

### Alert acknowledgement & snooze

A lightweight, time-boxed "I've got eyes on it" distinct from a sworn oath (ownership) or a maintenance silence (planned mute). While an alert is acked the notifier suppresses repeat pages and the escalation clock is held off; acks expire after `minutes` and auto-clear on recovery.

- `GET /api/alerts` · `POST /api/alerts/ack` `{target, who, minutes, reason}` · `POST /api/alerts/resolve`
- `MAYBOT_ACK_DEFAULT_MINUTES` (default 60). Persisted via `MAYBOT_DB` and included in backups.

### More notification channels

`notify` now fans out to **email (SMTP)** and **Telegram** alongside Slack/Discord/webhook:

| Variable | Purpose |
|---|---|
| `MAYBOT_SMTP_HOST`, `MAYBOT_SMTP_FROM`, `MAYBOT_SMTP_TO` | Enable email (all three required; `TO` is comma-separated) |
| `MAYBOT_SMTP_PORT` (587), `MAYBOT_SMTP_USER`/`_PASSWORD`, `MAYBOT_SMTP_TLS` (STARTTLS, on), `MAYBOT_SMTP_SSL` (off) | SMTP options |
| `MAYBOT_TELEGRAM_TOKEN` + `MAYBOT_TELEGRAM_CHAT_ID` | Enable Telegram (both required) |

### Scheduled summary reports (Daily Proclamation)

A human-readable digest of fleet health (uptime per project, incidents, trading PnL, worst/unhealthy projects) built from data already in memory.

- `GET /api/reports/daily?hours=` · `POST /api/reports/send` (deliver now to channels)
- `MAYBOT_REPORT_INTERVAL_HOURS` (>0 enables auto-delivery), `MAYBOT_REPORT_WINDOW_HOURS` (default 24).

### Data retention & scheduled backups (Archivist)

Keeps the SQLite store from growing forever and snapshots coordination state to disk on a schedule.

| Variable | Purpose |
|---|---|
| `MAYBOT_RETENTION_DAYS` | Prune time-series rows (history/transcripts/comms/usage) older than N days (needs `MAYBOT_DB`) |
| `MAYBOT_PRUNE_INTERVAL_HOURS` | How often to prune (default 6) |
| `MAYBOT_BACKUP_DIR` | Directory for periodic JSON state snapshots |
| `MAYBOT_BACKUP_INTERVAL_HOURS` (24), `MAYBOT_BACKUP_KEEP` (14) | Snapshot cadence and rotation |

- `GET /api/retention` · `POST /api/retention/prune` · `POST /api/backup/snapshot` · `GET /api/backup/list`

### Auth hardening

- **Session tokens** — `POST /api/login` exchanges a token for a time-boxed session token (use in `X-Control-Token`); `POST /api/logout` revokes it. TTL via `MAYBOT_SESSION_TTL_MINUTES` (default 720; 0 = no expiry).
- **Per-project ACLs** — a user in `users.yaml` may declare a `projects` list (`device:project` patterns with `*` / `device:*` wildcards), enforced on the project-scoped endpoints (logs, history, actions). See `users.yaml.example`.

### Control-center self-observability

The dashboard now monitors itself: poll freshness/duration, staleness, and API request/error counts.

- `GET /api/selfcheck` · new `/metrics` gauges: `maybot_poll_age_seconds`, `maybot_poll_duration_ms`, `maybot_poll_stale`, `maybot_poll_total`, `maybot_api_requests_total`, `maybot_api_errors_total`, `maybot_uptime_seconds`, `maybot_alerts_acknowledged`.
- `MAYBOT_POLL_STALE_AFTER_SECONDS` (default 120) sets the staleness threshold.

> Not included (deliberately out of scope for an in-process change): third-party SSO/OIDC (needs an external identity provider) and true multi-node HA/clustering (needs orchestration infrastructure). The auth hardening above — sessions, expiry, per-project ACLs — and the self-observability signals are the in-process groundwork for both.
