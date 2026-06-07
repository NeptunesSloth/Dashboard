#!/usr/bin/env bash
# MayBot one-click launcher (Docker).
#
# Starts the dashboard detached and opens it in your browser. Because the
# containers use `restart: unless-stopped`, once started they stay up across
# crashes and reboots (while Docker is running) — so you normally click this
# only once. Re-running is always safe (it just ensures things are up).
set -euo pipefail

# Repo root = parent of this script's dir, regardless of where it's invoked from.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

URL="http://localhost:8200"

note() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die()  { printf '\n\033[31mMayBot: %s\033[0m\n' "$*" >&2; read -rp "Press Enter to close…" _ 2>/dev/null || true; exit 1; }

# 1. Docker present and running?
command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop, then click again."
docker info >/dev/null 2>&1 || die "Docker isn't running. Start Docker Desktop and click again."

# 2. First-run config: create .env from the template if it's missing.
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  note "Created .env from .env.example — edit it later to add secrets (tokens, ANTHROPIC_API_KEY)."
fi

# 3. Bring the stack up (build the first time / after updates).
note "Starting MayBot…"
docker compose up -d --build

# 4. Wait for the dashboard to answer, then open the browser.
note "Waiting for the dashboard to come online…"
for _ in $(seq 1 60); do
  if curl -fsS "$URL/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done

if [ "${ok:-}" = "1" ]; then
  note "MayBot is up → $URL"
  if   command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open      >/dev/null 2>&1; then open "$URL"      >/dev/null 2>&1 || true
  fi
else
  die "Started, but the dashboard didn't answer on $URL within 60s. Check: docker compose logs control-center"
fi
