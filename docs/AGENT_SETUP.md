# Setting up a local agent (on each bot host)

This guide covers installing and running **`maybot_agent`** on a machine that
runs your bots. The agent is the small service the **control center pulls data
from** — it reads a local `projects.yaml`, inspects your bots (status, health,
logs, metrics), and exposes that over an authenticated HTTP API on port `8100`.

> Reminder on direction of traffic: **the control center reaches out to the
> agent.** The agent never connects to the dashboard. So the agent must listen
> on an address the dashboard can reach, and the two share a secret token.

```
 THIS host (your bot)                      dashboard host
 ┌────────────────────────────┐           ┌────────────────────────┐
 │ your bots                  │            │ maybot_control_center  │
 │ maybot_agent  :8100  ──────┼────◀───────┤  (reads devices.yaml)   │
 │  (reads projects.yaml)     │   HTTP pull│                         │
 └────────────────────────────┘           └────────────────────────┘
```

Run these steps **on every machine that runs bots**.

---

## 1. Prerequisites

- Python 3.10+ (`python3 --version`)
- `git`
- Network reachability from the dashboard host to this host on the agent port
  (a LAN/VPN/Tailscale link is strongly recommended — **do not expose the agent
  to the public internet**).

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git   # Debian/Ubuntu
```

---

## 2. Install

```bash
git clone <your-repo-url> maybot && cd maybot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Generate the shared token

The agent rejects every request unless `MAYBOT_API_TOKEN` is set, and the
control center must present the **same** token for this host in its
`devices.yaml`.

```bash
export MAYBOT_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
echo "$MAYBOT_API_TOKEN"   # copy this — it goes into the dashboard's devices.yaml
```

Persist it for the service (see step 6). Never commit it.

---

## 4. Describe your bots — `projects.yaml`

Create `projects.yaml` next to the repo (or point `MAYBOT_PROJECTS_FILE` at it).
Each entry is one bot/service. Start from `projects.yaml.example`, which has a
full set of templates. The common fields:

| Field | Meaning |
|---|---|
| `name` | Unique label shown on the dashboard |
| `type` | `trading_bot` · `local_ai_host` · `code_project` · `ai_project` · `game_server` · `school` · `website` · `generic` |
| `path` | Project directory (for git status / file checks) |
| `expect_running` | If `true`, a stopped process becomes an **error** |
| `pid_file` / `cmdline_contains` / `process_name` | How to detect the running process |
| `log_file` | Log to tail and scan for `ERROR`/`CRITICAL` |
| `commands.start` / `.stop` / `.run_tests` | Optional actions the dashboard can trigger |

### Per-type examples

**Trading bot** — PnL, positions, fills are parsed from its log/db:
```yaml
projects:
  - name: daybot
    type: trading_bot
    path: /home/me/TradeBot
    expect_running: true
    cmdline_contains: tradebot
    pid_file: run/daybot.pid
    log_file: /home/me/TradeBot/logs/bot.log
    commands:
      start: { argv: ["tradebot"], cwd: /home/me/TradeBot, background: true, pid_file: run/daybot.pid }
      stop:  { pid_file: run/daybot.pid, match_cmdline_contains: tradebot }
      run_tests: { argv: [".venv/bin/python", "-m", "pytest", "-q"], cwd: /home/me/TradeBot, timeout_seconds: 300 }
```

**Local AI host** (Ollama / LM Studio / llama.cpp / vLLM) — model availability + latency:
```yaml
  - name: Hermes Local AI
    type: local_ai_host
    provider: ollama                         # or openai_compatible | lmstudio | llama_cpp
    base_url: http://127.0.0.1:11434
    health_url: http://127.0.0.1:11434/api/tags
    default_model: nous-hermes
    expect_running: true
    cmdline_contains: ollama
    test_prompt_enabled: false               # tiny generation check, opt-in only
```

**Website** — up/down, latency, content check, TLS-cert expiry:
```yaml
  - name: Marketing Site
    type: website
    health_url: https://example.com/health
    expect_text: "OK"        # 200 but missing this marker => error
    max_response_ms: 800     # warn if slower
    check_cert: true         # warn/error as the https cert nears expiry
    cert_warn_days: 21
    cert_error_days: 7
```

**Game server** — players/capacity/map/tick-rate from a JSON status endpoint (or a raw TCP port check):
```yaml
  - name: Minecraft SMP
    type: game_server
    query_url: http://127.0.0.1:8080/status  # JSON: players, max_players, map, tps
    min_tps: 18
    # host: 127.0.0.1                         # alternative: TCP reachability check
    # port: 25565
```

**School / LMS** — enrolment, overdue work, pass rate, attendance:
```yaml
  - name: Online Academy
    type: school
    query_url: http://127.0.0.1:9000/api/summary  # JSON: students, overdue, pass_rate, attendance
    min_pass_rate: 60
    min_attendance: 70
```

**AI / ML project** — training/inference phase, GPU/VRAM, loss, eval, plus a log scan for CUDA OOM / NaN loss:
```yaml
  - name: Vision Trainer
    type: ai_project
    query_url: http://127.0.0.1:7000/status  # JSON: phase, model, gpu_util, loss, eval_score
    log_file: /home/me/train/run.log
```

**Code project** — git status + TODO/FIXME counts + tests:
```yaml
  - name: my-service
    type: code_project
    path: /home/me/my-service
    commands:
      run_tests: { argv: ["pytest", "-q"], cwd: /home/me/my-service, timeout_seconds: 300 }
```

---

## 5. Run the agent (bind to a reachable address)

Bind to `0.0.0.0` (or the specific LAN/VPN IP) so the dashboard can reach it —
`127.0.0.1` only works if the control center runs on the **same** machine.

```bash
# same machine as the dashboard:
uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100

# reachable from another machine over LAN/VPN:
uvicorn maybot_agent.app:app --host 0.0.0.0 --port 8100
```

Override host/port with `MAYBOT_AGENT_HOST` / `MAYBOT_AGENT_PORT` if you prefer.

---

## 6. Keep it running with systemd (recommended)

`/etc/systemd/system/maybot-agent.service`:
```ini
[Unit]
Description=MayBot Agent
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/me/maybot
Environment=MAYBOT_API_TOKEN=PASTE-THE-TOKEN-FROM-STEP-3
Environment=MAYBOT_PROJECTS_FILE=/home/me/maybot/projects.yaml
ExecStart=/home/me/maybot/.venv/bin/uvicorn maybot_agent.app:app --host 0.0.0.0 --port 8100
Restart=always
RestartSec=3
User=me

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now maybot-agent
sudo systemctl status maybot-agent
```

### Or run it in Docker
```bash
docker run -d --name maybot-agent --restart unless-stopped \
  -p 8100:8100 \
  -e MAYBOT_API_TOKEN="$MAYBOT_API_TOKEN" \
  -v "$PWD":/app -w /app \
  python:3.12-slim \
  sh -c "pip install -r requirements.txt && uvicorn maybot_agent.app:app --host 0.0.0.0 --port 8100"
```
(The repo's `docker-compose.yml` already starts a co-located agent for the host running the dashboard.)

---

## 7. Connect it to the dashboard

**Easiest:** in the dashboard go to **Ops → Hosts → “+ Add a host”**, paste this
machine's URL and token, click **Test connection**, then **Save** — it writes
`devices.yaml` for you (no file editing). The "Add a host" panel also has a
built-in walkthrough of steps 1–6 with a copy-paste run command.

Prefer files? On the **control center** host, add this agent to `devices.yaml`:
```yaml
devices:
  - name: trade-server
    url: http://100.64.0.2:8100        # this host's reachable IP + agent port
    api_token: "the-token-from-step-3" # MUST equal this host's MAYBOT_API_TOKEN
```
Then restart the control center. Data appears on the next poll.

---

## 8. Verify

From the dashboard host (or anywhere that can reach the agent):
```bash
scripts/check-agent.sh http://100.64.0.2:8100 the-token-from-step-3
```
A `PASS` line means the link works. You can also hit the API directly:
```bash
curl -s -H "X-API-Token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/ping
curl -s -H "X-API-Token: $MAYBOT_API_TOKEN" http://127.0.0.1:8100/api/projects | python3 -m json.tool
```

---

## Security checklist

- [ ] `MAYBOT_API_TOKEN` is a long random secret, unique per host (not `change-me`).
- [ ] The agent listens only on a private LAN/VPN/Tailscale interface, never the public internet.
- [ ] A firewall restricts port `8100` to the dashboard host.
- [ ] Secrets live in the systemd unit / env, never in committed files.

---

## Troubleshooting

| Symptom (from `check-agent.sh` / dashboard) | Cause & fix |
|---|---|
| `401` / device shows **auth error** | `api_token` in `devices.yaml` ≠ this host's `MAYBOT_API_TOKEN`. |
| `no response (000)` / device **offline** | Agent not running, wrong host/port, agent bound to `127.0.0.1` instead of the LAN IP, or firewall blocking the port. |
| `0 projects` | `projects.yaml` is empty/missing, or `MAYBOT_PROJECTS_FILE` points elsewhere. |
| Bot shows `unknown` status | Process can't be matched — set `pid_file`, `cmdline_contains`, or `process_name`. |
| `expected but stopped` error | `expect_running: true` but the process isn't found (start it, or relax the field). |
| Log panel empty | `log_file` path is wrong or unreadable by the agent's user. |

---

## Reference

**Environment variables (agent):**

| Variable | Default | Purpose |
|---|---|---|
| `MAYBOT_API_TOKEN` | *(none)* | Shared secret; **required** (all requests 401 without it) |
| `MAYBOT_PROJECTS_FILE` | `projects.yaml` | Path to this host's project list |
| `MAYBOT_AGENT_HOST` | `127.0.0.1` | Bind address (the uvicorn `--host` is what actually binds) |
| `MAYBOT_AGENT_PORT` | `8100` | Port reported by `/api/device` |

**Agent API** (all require the `X-API-Token` header):

| Method & path | Purpose |
|---|---|
| `GET /api/ping` | Liveness + auth check |
| `GET /api/device` | Host/port/version |
| `GET /api/projects` | All projects with status/health/metrics (what the dashboard pulls) |
| `GET /api/projects/{name}` | One project |
| `GET /api/projects/{name}/logs?level=ALL\|ERROR\|WARNING\|INFO` | Tail logs |
| `GET /api/projects/{name}/health` | Health only |
| `POST /api/projects/{name}/start` · `/stop` · `/run-tests` | Trigger configured commands |
