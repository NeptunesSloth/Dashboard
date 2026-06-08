#!/usr/bin/env bash
# MayBot AI-agent installer — set up a local AI (Ollama + a model) on this machine
# and register it as a sect member on the dashboard, in one command.
#
#   curl -fsSL http://DASH:8200/install-ai.sh | \
#     CONTROL_URL=http://DASH:8200 CONTROL_TOKEN=<operator-token> bash
#
# Env: MODEL (default nous-hermes), MEMBER_NAME (default the model),
#      MEMBER_ROLE (default Disciple), CONTROL_URL + CONTROL_TOKEN (to auto-register;
#      omit to just install the model and print the base_url for the UI).
set -euo pipefail
MODEL="${MODEL:-nous-hermes}"
NAME="${MEMBER_NAME:-$MODEL}"
ROLE="${MEMBER_ROLE:-Disciple}"
PORT="${OLLAMA_PORT:-11434}"

echo "MayBot AI agent → installing Ollama + '$MODEL'"
if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
# make sure the server is up
if ! curl -fsS "http://127.0.0.1:$PORT/api/tags" >/dev/null 2>&1; then
  (ollama serve >/tmp/ollama.log 2>&1 &) ; sleep 3
fi
echo "Pulling model '$MODEL' (this can take a while)..."
ollama pull "$MODEL"

# reachable base_url for the dashboard to call
ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-127.0.0.1}"
BASE_URL="http://$ip:$PORT"

if [ -n "${CONTROL_URL:-}" ] && [ -n "${CONTROL_TOKEN:-}" ]; then
  echo "Registering member '$NAME' on ${CONTROL_URL%/} ..."
  code=$(curl -s -o /tmp/ai_reg.json -w "%{http_code}" -X POST "${CONTROL_URL%/}/api/members" \
    -H "Content-Type: application/json" -H "x-control-token: $CONTROL_TOKEN" \
    -d "{\"name\":\"$NAME\",\"role\":\"$ROLE\",\"provider\":\"ollama\",\"model\":\"$MODEL\",\"base_url\":\"$BASE_URL\"}")
  if [ "$code" = "200" ]; then echo "✓ Member '$NAME' is on the dashboard."
  else echo "Could not auto-register (HTTP $code): $(cat /tmp/ai_reg.json). Add it in the UI with the base_url below."; fi
else
  echo "✓ Local AI ready. Add a member in the dashboard (Sect Members → Add member):"
fi
echo "    provider: ollama   model: $MODEL   base_url: $BASE_URL"
