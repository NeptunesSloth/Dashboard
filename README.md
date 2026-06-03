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

## Agent Crew (LLM persona agents — Phase 1)

The dashboard can run **LLM-backed persona agents** against your local AI hosts. Each agent is defined in `agents.yaml` with a name, role, and persona (system prompt), and points at an Ollama or OpenAI-compatible endpoint. In the **Agent Crew** section you assign a task to an agent and it runs one chat completion in the background, streaming the reply (and a transcript) into its card.

```bash
cp agents.yaml.example agents.yaml
nano agents.yaml   # set name/role/persona/provider/base_url/model per agent
# restart the control center; the "Agent Crew" section appears automatically
```

**Backends:** each agent's `provider` selects where it runs:
- `ollama` / `openai_compatible` / `lmstudio` / `llama_cpp` — a local AI host you point at with `base_url` (reachable from the control center).
- `claude` (or `anthropic`) — the Claude API via the official SDK. Set `ANTHROPIC_API_KEY` in the control center's environment; no `base_url` needed. Defaults to `claude-opus-4-8`; the stable persona is sent with prompt caching.

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
