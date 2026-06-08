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
mkdir -p "$DIR"; cd "$DIR"
curl -fsSL --connect-timeout 10 "$CONTROL_URL/agent-bundle.tgz" -o bundle.tgz
tar xzf bundle.tgz && rm -f bundle.tgz
python3 -m venv .venv
./.venv/bin/pip install -q -U pip
./.venv/bin/pip install -q -r requirements-agent.txt
[ -f projects.yaml ] || { [ -f projects.yaml.example ] && cp projects.yaml.example projects.yaml || echo "projects: []" > projects.yaml; }

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
echo "  Edit $DIR/projects.yaml to list this machine's bots."
