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
- **Host (bot machine):** `curl -fsSL <DASH>/install-agent.sh | CONTROL_URL=<DASH> REGISTER_TOKEN=<tok> bash` — self-enrolls.
- **Local AI member:** `curl -fsSL <DASH>/install-ai.sh | CONTROL_URL=<DASH> CONTROL_TOKEN=<op> bash` — installs Ollama + model, registers the member.
(Windows: the `.ps1` equivalents at `/install-agent.ps1` and `/install-ai.ps1`.)
