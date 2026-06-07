# Local AI setup (the brains behind the disciples)

The "disciple" agents (Nova, Forge, Atlas, …) think by calling an LLM. This guide
shows how to give them one — either a **local model** you run yourself (Ollama or
any OpenAI-compatible server) or **Claude** in the cloud. Configure each disciple
in `agents.yaml` (start from `agents.yaml.example`).

> Two different "AI" things — don't confuse them:
> - **Disciple backend** (this guide): the LLM that *powers* an agent. Set per agent
>   in `agents.yaml` via `provider` + `base_url` + `model`.
> - **`local_ai_host` project** (see [AGENT_SETUP.md](AGENT_SETUP.md)): a model server
>   you *monitor* as a project on the dashboard. Different thing, same servers.

---

## Option A — Ollama (recommended local backend)

1. **Install & start Ollama** — <https://ollama.com/download> (Linux: `curl -fsSL https://ollama.com/install.sh | sh`). It listens on `http://localhost:11434`.
2. **Pull a model:**
   ```bash
   ollama pull llama3
   ```
3. **Verify it's serving:**
   ```bash
   curl http://localhost:11434/api/tags     # should list llama3
   ```
4. **Point the disciples at it** in `agents.yaml`:
   ```yaml
   agents:
     - name: Forge
       role: Builder
       persona: "You are Forge, a pragmatic engineer. Smallest thing that works."
       provider: ollama
       base_url: http://127.0.0.1:11434
       model: llama3
       temperature: 0.7
       max_tokens: 512
   ```
5. Restart the control center. Assign a task to Forge from the dashboard and watch the reply.

> ⚠️ **Running the control center in Docker? `127.0.0.1` won't reach Ollama on your host.**
> Inside a container `127.0.0.1` is the container itself. Our `docker-compose.yml`
> maps `host.docker.internal`, so use:
> ```yaml
> base_url: http://host.docker.internal:11434
> ```
> (Native, non-Docker run: `http://127.0.0.1:11434` is correct.)

The Ollama path POSTs to `{base_url}/api/chat`.

---

## Option B — LM Studio / llama.cpp / vLLM (OpenAI-compatible)

Any server that exposes the OpenAI `/v1/chat/completions` API works with
`provider: openai_compatible`. Point `base_url` at the server and set `model` to
the id it serves:

```yaml
agents:
  - name: Nova
    role: Research Analyst
    persona: "You are Nova, a meticulous research analyst. Tight bullets, no padding."
    provider: openai_compatible        # LM Studio / llama.cpp / vLLM all fit here
    base_url: http://127.0.0.1:1234     # the server's address (host.docker.internal in Docker)
    model: hermes                       # the model id the endpoint serves
    temperature: 0.6
    max_tokens: 512
```

- **LM Studio:** start its local server (default port `1234`), load a model, copy the model id.
- **llama.cpp / vLLM:** run with the OpenAI-compatible server enabled; use its host/port.

The OpenAI-compatible path POSTs to `{base_url}/v1/chat/completions`.

---

## Option C — Claude (cloud, zero local setup)

Not "local," but the fastest way to get capable disciples with no model hosting:

```yaml
agents:
  - name: Atlas
    role: Strategist
    persona: "You are Atlas, a sharp strategist. State trade-offs, give one clear rec."
    provider: claude
    model: claude-opus-4-8        # omit base_url; the Anthropic SDK handles the endpoint
    max_tokens: 1024
```

Then set the key in `.env` (auto-loaded by `docker compose`):
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

You can mix providers — e.g. cheap local Ollama for routine disciples and Claude for your strategist.

---

## `agents.yaml` field reference

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Unique disciple name (shown on the dashboard / Sect Map) |
| `role` | yes | Title / specialty label |
| `persona` (or `system`) | yes | System prompt that defines the disciple's voice |
| `provider` | yes | `ollama` · `openai_compatible` · `claude`/`anthropic` (default if omitted: `openai_compatible`) |
| `base_url` | local only | LLM server URL (not used for Claude). Use `host.docker.internal` when the control center is dockerized |
| `model` | yes | Model id (`llama3`, `hermes`, `claude-opus-4-8`, …) |
| `temperature` | no | Sampling temperature (default `0.7`) |
| `max_tokens` | no | Max reply length (default `512`; Claude `1024`) |
| `skin` / `sprite` | no | Cosmetic Sect Map appearance |
| `memory: false` | no | Opt out of vault-memory injection for this agent |
| `tools: false` | no | Opt out of guarded tools for this agent |
| `inner_demon: true` | no | Per-agent self-critique pass (global flag: `MAYBOT_INNER_DEMON`) |

**Related environment variables** (set in `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for `provider: claude` |
| `MAYBOT_AGENT_TIMEOUT` | `60` | Per-LLM-call timeout (seconds); raise for big local models |
| `MAYBOT_AGENTS_FILE` | `agents.yaml` | Path to the disciples config |
| `MAYBOT_AUTONOMY`, `MAYBOT_INNER_DEMON`, `MAYBOT_DELEGATION` | see `.env.example` | Agent behaviour toggles (already on in the default `.env`) |

---

## Verify it works

1. Open the dashboard (`http://localhost:8200`) → **Agent Crew**.
2. Assign a disciple a task (e.g. "summarize the fleet status in 3 bullets").
3. Its card should fill in with a reply within `MAYBOT_AGENT_TIMEOUT` seconds.

**Troubleshooting:**

| Symptom | Cause & fix |
|---|---|
| Reply error: connection refused / timeout | Wrong `base_url`, model server not running, or — in Docker — using `127.0.0.1` instead of `host.docker.internal`. |
| Ollama "model not found" | `ollama pull <model>` first; make `model` match exactly. |
| Claude: "authentication failed — set ANTHROPIC_API_KEY" | `ANTHROPIC_API_KEY` missing/invalid in `.env`; restart after setting it. |
| Replies are truncated | Raise `max_tokens` on that agent. |
| Slow / timing out on a big local model | Raise `MAYBOT_AGENT_TIMEOUT`. |

> Want the dashboard to also **monitor** your model server's health (online, models,
> latency)? Add it as a `local_ai_host` *project* on an agent host — see
> [AGENT_SETUP.md](AGENT_SETUP.md#per-type-examples).
