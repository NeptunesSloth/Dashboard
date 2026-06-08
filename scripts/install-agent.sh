#!/usr/bin/env bash
# MayBot agent — one-command installer. Downloads the agent from your dashboard,
# installs it, runs it as a service, and self-enrolls (the host then appears on
# the dashboard automatically). No git clone, no registry.
#
#   curl -fsSL http://DASH:8200/install-agent.sh | CONTROL_URL=http://DASH:8200 REGISTER_TOKEN=secret bash
#
# Env: CONTROL_URL (required), REGISTER_TOKEN, API_TOKEN (auto), AGENT_NAME (hostname),
#      AGENT_PORT (8100), AGENT_DIR (~/maybot-agent).
set -euo pipefail

CONTROL_URL="${CONTROL_URL:?Set CONTROL_URL=http://your-dashboard:8200}"
CONTROL_URL="${CONTROL_URL%/}"
DIR="${AGENT_DIR:-$HOME/maybot-agent}"
PORT="${AGENT_PORT:-8100}"
NAME="${AGENT_NAME:-$(hostname)}"
REG="${REGISTER_TOKEN:-}"
API_TOKEN="${API_TOKEN:-$(python3 -c 'import secrets;print(secrets.token_hex(32))')}"

echo "MayBot agent → installing into $DIR (enrolling to $CONTROL_URL)"

# --- Preflight: fail fast with a clear message instead of a confusing later error.
command -v python3 >/dev/null 2>&1 || { echo "✗ python3 is required. Install python3 + venv, then re-run."; exit 1; }
case "$CONTROL_URL" in
  *localhost*|*127.0.0.1*)
    echo "⚠ CONTROL_URL points at localhost/127.0.0.1 — that only works if the dashboard runs on THIS machine."
    echo "  On a separate host use the dashboard's LAN/VPN IP or hostname (e.g. http://192.168.1.50:8200)." ;;
esac
if ! curl -fsS --connect-timeout 10 --max-time 25 "$CONTROL_URL/healthz" >/dev/null 2>&1; then
  echo "✗ Can't reach the dashboard at $CONTROL_URL (tried $CONTROL_URL/healthz)."
  echo "  Check the IP/port and that the dashboard is running and reachable from this machine, then re-run."
  exit 1
fi
echo "✓ Dashboard reachable at $CONTROL_URL"

mkdir -p "$DIR"; cd "$DIR"
curl -fsSL --connect-timeout 10 "$CONTROL_URL/agent-bundle.tgz" -o bundle.tgz
tar xzf bundle.tgz && rm -f bundle.tgz
python3 -m venv .venv
./.venv/bin/pip install -q -U pip
./.venv/bin/pip install -q -r requirements-agent.txt
# Start with a clean, empty bot list — add bots later from the dashboard
# (Hosts → Manage bots → Discover) so a fresh host shows up tidy, not with
# the example bots that don't exist on this machine.
[ -f projects.yaml ] || printf 'projects: []\n' > projects.yaml

cat > .env <<EOF
MAYBOT_API_TOKEN=$API_TOKEN
MAYBOT_CONTROL_CENTER_URL=$CONTROL_URL
MAYBOT_REGISTER_TOKEN=$REG
MAYBOT_AGENT_NAME=$NAME
MAYBOT_AGENT_PORT=$PORT
MAYBOT_PROJECTS_FILE=$DIR/projects.yaml
EOF

if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
  cat > /etc/systemd/system/maybot-agent.service <<EOF
[Unit]
Description=MayBot Agent
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$DIR/.venv/bin/uvicorn maybot_agent.app:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now maybot-agent
  echo "✓ Installed as a systemd service (auto-starts on boot). It will appear on your dashboard shortly."
else
  set -a; . "$DIR/.env"; set +a
  pkill -f "uvicorn maybot_agent.app:app" 2>/dev/null || true
  nohup ./.venv/bin/uvicorn maybot_agent.app:app --host 0.0.0.0 --port "$PORT" >"$DIR/agent.log" 2>&1 &
  echo "✓ Agent started in the background (log: $DIR/agent.log)."
  echo "  For a boot-persistent service, re-run this as root on a systemd host."
fi

# --- Self-test + diagnostics: confirm the agent answers locally before we claim success.
( for i in 1 2 3 4 5; do
    curl -fsS --connect-timeout 3 "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && exit 0
    sleep 1
  done; exit 1 ) \
  && echo "✓ Agent is answering on http://127.0.0.1:$PORT (/healthz OK)." \
  || echo "⚠ Agent isn't answering on http://127.0.0.1:$PORT yet — check the logs above / 'systemctl status maybot-agent'."

set -a; . "$DIR/.env"; set +a
echo
"$DIR/.venv/bin/python" -m maybot_agent doctor 2>/dev/null || true
echo
echo "Next steps:"
echo "  1. Open your dashboard → Ops → Hosts. This host should appear within a few seconds."
echo "  2. Add its bots there: Manage bots → Discover (no SSH, no YAML)."
echo "  3. Make sure port $PORT is firewalled to the dashboard host only — don't expose it to the public internet."
