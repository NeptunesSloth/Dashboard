# Deploying & keeping it updated

## Option A — one-click (build locally)
Windows: `launch\maybot.bat` (start) · `launch\update.bat` (pull + restart).
Any OS: `docker compose up -d --build`.

## Option B — prebuilt image + auto-update (hands-off)
On every merge to `main`, CI publishes an image to GHCR
(`ghcr.io/neptunessloth/dashboard`). Run the image-based stack — **Watchtower**
auto-pulls new images every 5 minutes and restarts:

```bash
cp .env.example .env          # set your secrets
docker compose -f docker-compose.images.yml up -d
```

No rebuilds, no manual updates. (First time: make the GHCR package public, or
`docker login ghcr.io` on the host.)

## Adding hosts / AI agents (one command each)
- **Host (bot machine):** `curl -fsSL --connect-timeout 10 --max-time 60 <DASH>/install-agent.sh | CONTROL_URL=<DASH> REGISTER_TOKEN=<tok> bash` — self-enrolls.
- **Local AI member:** `curl -fsSL --connect-timeout 10 --max-time 60 <DASH>/install-ai.sh | CONTROL_URL=<DASH> CONTROL_TOKEN=<op> bash` — installs Ollama + model, registers the member.
(Windows: the `.ps1` equivalents at `/install-agent.ps1` and `/install-ai.ps1`.)

> The `--connect-timeout`/`--max-time` flags make the command **fail fast** if `<DASH>` is unreachable
> (firewall, wrong IP, or the dashboard isn't listening on that port) instead of hanging for minutes.
> If you see `curl: (28) … Couldn't connect to server`, the bot host can't reach the dashboard — check the
> IP/port and that port 8200 is open from that machine (`curl -v <DASH>/healthz`).

## Scaling note (#2)
Run a **single uvicorn worker** for now. Sessions, the kill‑switch, and parts of
the sim live in process memory, so `--workers N` would split that state across
processes (you'd get logged out at random, etc.). Multi‑worker is safe only after
runtime state is moved to the shared store (roadmap #3). The snapshot cache + the
async I/O already give plenty of headroom for a LAN operator.
