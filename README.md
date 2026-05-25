# MayBot Control Center

MayBot Control Center is a **distributed, monitoring-first dashboard** for tracking projects across multiple machines.

It has two components:
- **`maybot_agent`**: runs on each device that hosts projects/bots; reads local status/logs/metrics and exposes an authenticated HTTP API.
- **`maybot_control_center`**: central web dashboard that polls all configured agents and shows a unified view.

> ⚠️ Security posture: this system is intended for **private/local networks (LAN/VPN)** and should **not be exposed publicly** by default.

---

## 1) Architecture

```text
[TradeBot Server] -> maybot_agent -> [Control Center Dashboard]
[DayBot Server]   -> maybot_agent -> [Control Center Dashboard]
[Other Device]    -> maybot_agent -> [Control Center Dashboard]
```

Each agent uses a local `projects.yaml`. The control center uses `devices.yaml` to discover agents.

---

## 2) Requirements

- Python **3.10+**
- Linux/Ubuntu recommended
- `pip` + `venv`
- Git installed (for code project metrics)
- `psutil` (already in `requirements.txt`)
- Network connectivity from control center to each agent (prefer **LAN/VPN/Tailscale/WireGuard**)

---

## 3) Install (both agent host and control-center host)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4) Agent setup (run on each project-hosting device)

1. Copy template config:
   ```bash
   cp projects.yaml.example projects.yaml
   ```
2. Edit `projects.yaml` for that specific machine.
3. Set agent token:
   ```bash
   export MAYBOT_API_TOKEN="replace-me-with-a-long-random-token"
   ```
4. Start agent on loopback (default-safe):
   ```bash
   uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100
   ```

### LAN/VPN bind example

```bash
uvicorn maybot_agent.app:app --host 100.x.x.x --port 8100
```

> ⚠️ Do **not** bind to `0.0.0.0` unless protected by firewall/VPN and strict network controls.

---

## 5) Control center setup (main dashboard machine)

1. Copy template:
   ```bash
   cp devices.yaml.example devices.yaml
   ```
2. Edit `devices.yaml` with each agent URL + token.
3. Start dashboard:
   ```bash
   uvicorn maybot_control_center.app:app --host 127.0.0.1 --port 8200
   ```
4. Open:
   - `http://127.0.0.1:8200`

---

## 6) Configuration examples

### `projects.yaml` example (trading bot)

```yaml
projects:
  - name: tradebot-main
    type: trading_bot
    path: /opt/tradebot
    log_file: /opt/tradebot/logs/bot.log
    database: /opt/tradebot/data/trading.sqlite3

    # Process detection (prefer pid_file/cmdline_contains over broad process_name)
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

### `devices.yaml` example

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

## 7) Verify agent health/API

> Current implementation expects `x-api-token` header.

```bash
curl -H "x-api-token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/ping
curl -H "x-api-token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/projects
```

Expected:
- `/api/ping` returns JSON like `{"status":"ok"}`.
- `/api/projects` returns a JSON array of project cards including fields such as `name`, `type`, `status`, `health`, `metrics`, and `alerts`.

> If you specifically prefer Bearer auth, update agent auth middleware and then use:
> `curl -H "Authorization: Bearer $MAYBOT_API_TOKEN" ...`

---

## 8) How to add a new project

1. Ensure `maybot_agent` is installed/running on the device that hosts the project.
2. Add the project entry to that device’s `projects.yaml`.
3. Restart agent on that device.
4. If this is a brand-new device, add it to control-center `devices.yaml`.
5. Refresh/open dashboard page.

---

## 9) Supported project types

- `trading_bot`
  - Intended metrics: PnL/exposure/trades/fills/rejections/risk-blocked/mode/last trade.
  - Sources: SQLite + logs + process state.
- `code_project`
  - Branch, clean/dirty, modified files, last commit, TODO/FIXME, test status, log/db sizes.
- `game_server`
  - Running state, PID, CPU/RAM, optional player counts/world size/crash signals.
- `website`
  - `health_url` online/offline, HTTP status, response time.
- `school`
  - Task/progress/deadline metadata from configured inputs.
- `ai_project`
  - Current task/status/log outputs/diff/test-review signals.
- `generic`
  - Path/log existence, folder/basic health fallback signals.

---

## 10) Safety rules

- The dashboard does **not** push to GitHub.
- The dashboard does **not** merge branches.
- The dashboard does **not** delete files.
- The dashboard must **not** start live trading automatically.
- Start/stop/test actions run **only** commands explicitly configured in `projects.yaml`.
- Prefer paper-trading commands for `start` actions.

---

## 11) Troubleshooting

### Agent shows offline in dashboard
- Check agent process on device.
- Verify `devices.yaml` URL/port.
- Verify LAN/VPN reachability.

### 401 Unauthorized
- Confirm `x-api-token` matches `MAYBOT_API_TOKEN` on that agent.
- Re-export token and restart service if needed.

### Connection refused
- Agent not running, wrong host/port, or firewall blocked.
- Validate with local curl on agent host first.

### Missing `projects.yaml`
- Agent returns empty project list. Copy and edit from example:
  - `cp projects.yaml.example projects.yaml`

### Missing `devices.yaml`
- Control center has nothing to poll. Copy and edit from example:
  - `cp devices.yaml.example devices.yaml`

### Bot shows `unknown`
- Missing schema/columns/log keys for that adapter.
- Add fields in config and confirm data source paths exist.

### Log file missing
- Ensure `log_file` path exists and is readable by agent user.
- Ensure `start` redirection points to correct relative/absolute path.

### SQLite database locked
- Temporary lock can occur under heavy bot writes.
- Adapter marks warning; retry after lock clears.

### Git status not showing
- Confirm `path` points to a valid git repo.
- Ensure `git` executable is installed and available in PATH.

### Start action does nothing
- Ensure `commands.start.argv` is valid.
- Ensure `background: true` is present.
- Check stdout/stderr logs and pid_file output path.

### Running across different devices
- Each device needs its own agent + local `projects.yaml`.
- Control center needs all devices listed in `devices.yaml`.

### Firewall/VPN issues
- Open agent port only within private network.
- Prefer VPN addresses (Tailscale/WireGuard) over public interfaces.

---

## 12) Limitations

- Advanced PnL extraction depends on bot DB/log schema compatibility.
- Some fields may remain `unknown` until adapter support is extended.
- This is a monitoring/control helper, **not** a deployment/orchestration system.
- This is not a replacement for broker/exchange-native risk controls.

---

## 13) Recommended deployment (optional systemd)

### `/etc/systemd/system/maybot-agent.service`

```ini
[Unit]
Description=MayBot Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/maybot
Environment=MAYBOT_API_TOKEN=replace-me
ExecStart=/opt/maybot/.venv/bin/uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### `/etc/systemd/system/maybot-control-center.service`

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

Enable/start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now maybot-agent
sudo systemctl enable --now maybot-control-center
sudo systemctl status maybot-agent maybot-control-center
```

---

## 14) Developer notes

### Repo structure

```text
maybot_agent/
  app.py
  auth.py
  config.py
  adapters/
  services/

maybot_control_center/
  app.py
  config.py
  agent_client.py
  aggregator.py
  static/

tests/
projects.yaml.example
devices.yaml.example
```

### Where to change logic
- Add/extend project-type behavior in `maybot_agent/adapters/`.
- Extend process/log/git/db helpers in `maybot_agent/services/`.
- Config loaders are in:
  - `maybot_agent/config.py`
  - `maybot_control_center/config.py`
- Dashboard aggregation logic: `maybot_control_center/aggregator.py`.
- Frontend rendering: `maybot_control_center/static/app.js`.

### Run tests

```bash
PYTHONPATH=. pytest -q
```


## 15) Local AI / LLM Host Projects

Use `type: local_ai_host` to monitor locally hosted model services (Hermes, Ollama, llama.cpp, LM Studio, Open WebUI, or other OpenAI-compatible local APIs) **separately** from `ai_project` coding-workflow tracking.

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

### Example: OpenAI-compatible local API

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

Safety notes for local AI hosts:
- Test prompt checks are disabled by default.
- Tiny generation checks run only when `test_prompt_enabled: true`.
- Do not expose local model hosts publicly unless protected by VPN/firewall (LAN/VPN/local-only strongly recommended).
- API secrets are not included in dashboard project cards.
