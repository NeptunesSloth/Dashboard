# Run MayBot as a desktop app (one click, auto-restarts)

Turn the dashboard into an icon you double-click — no typing commands, and it
**stays running on its own** (across crashes and reboots) once started. This uses
Docker; the compose stack is configured with `restart: unless-stopped`, so the
single click is normally a one-time action.

**Prerequisite:** install **Docker Desktop** (<https://www.docker.com/products/docker-desktop/>)
and make sure it's running. That's the only dependency.

---

## One-time setup

```bash
git clone <your-repo-url> maybot
cd maybot
cp .env.example .env        # then edit .env to add your secrets (see below)
```

Edit `.env` and set at least:
- `MAYBOT_CONTROL_CENTER_TOKEN` — your dashboard login token (recommended before any network exposure).
- `ANTHROPIC_API_KEY` — only if you use Claude-backed disciples (see [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md)).

Then install the clickable launcher for your OS:

### Linux
```bash
bash launch/install-linux.sh            # adds a "MayBot Control Center" app icon
# or, to also start it automatically when you log in:
bash launch/install-linux.sh --autostart
```
Find **MayBot Control Center** in your applications menu (search "MayBot").

### Windows
Double-click `launch\install-windows.bat` (or run it once from a terminal). It
creates **MayBot** shortcuts on your Desktop and Start Menu:
```bat
launch\install-windows.bat
:: or also start on login:
launch\install-windows.bat --autostart
```

---

## Daily use

- **Start / open:** double-click the **MayBot** icon. It launches the stack (building
  the first time), waits for the dashboard, and opens <http://localhost:8200> in your browser.
- **It keeps itself running:** thanks to `restart: unless-stopped`, the containers
  come back automatically after a crash or a reboot — you don't re-run anything.
- **Stop it:** run `launch/stop.sh` (Linux) or `launch\stop.bat` (Windows). Click the
  MayBot icon again to bring it back.
- **Update to a new version:**
  ```bash
  git pull
  ```
  then click the MayBot icon — the launcher passes `--build`, so it rebuilds with your changes.

> You can always do the same thing by hand: `docker compose up -d` in the repo
> folder. The launcher just adds the icon, the health-wait, and the browser-open.

---

## What the launcher does

`launch/maybot.sh` / `launch/maybot.bat`:
1. Check Docker is installed and running (friendly message if not).
2. Create `.env` from `.env.example` on first run if it's missing.
3. `docker compose up -d --build` (detached, with the restart policy).
4. Poll `http://localhost:8200/healthz` until healthy (up to 60s).
5. Open `http://localhost:8200` in your default browser.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Docker is not installed" | Install Docker Desktop and try again. |
| "Docker isn't running" | Start Docker Desktop (wait for the whale icon), then click MayBot. |
| Browser didn't open / "didn't answer within 60s" | First build can be slow; wait and re-open <http://localhost:8200>, or check `docker compose logs control-center`. |
| Port 8200 already in use | Stop whatever uses it, or change the `8200:8200` mapping in `docker-compose.yml`. |
| Dashboard asks for a token | Set `MAYBOT_CONTROL_CENTER_TOKEN` in `.env`, then restart (re-click). |
| Disciples don't reply | Configure an LLM backend — see [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md). |

Related: [AGENT_SETUP.md](AGENT_SETUP.md) (connect bot hosts) · [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md) (LLM backend).
