#!/usr/bin/env bash
# Stop MayBot (one click). Containers stay defined; `launch/maybot.sh` restarts them.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo "Docker not installed."; exit 1; }
echo "Stopping MayBot…"
docker compose stop
echo "Stopped. Click the MayBot launcher to start it again."
