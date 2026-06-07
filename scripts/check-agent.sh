#!/usr/bin/env bash
# Verify the control center can pull data from a bot host's agent.
#
# Usage:
#   scripts/check-agent.sh <agent_url> <api_token>
#   scripts/check-agent.sh http://100.64.0.2:8100 my-strong-secret
#
# Checks /api/ping (auth) then /api/projects (the data the dashboard pulls),
# and prints a clear PASS/FAIL with the most likely cause on failure.
set -euo pipefail

URL="${1:-}"
TOKEN="${2:-}"

if [[ -z "$URL" || -z "$TOKEN" ]]; then
  echo "usage: $0 <agent_url> <api_token>" >&2
  echo "  e.g. $0 http://100.64.0.2:8100 my-strong-secret" >&2
  exit 2
fi
URL="${URL%/}"

hdr=(-H "X-API-Token: ${TOKEN}")
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 6 "${hdr[@]}" "$1" 2>/dev/null || true; }

echo "→ ping  ${URL}/api/ping"
PING="$(code "${URL}/api/ping")"
case "$PING" in
  200) echo "  PASS — agent reachable and token accepted" ;;
  401) echo "  FAIL — 401: api_token does not match the host's MAYBOT_API_TOKEN" >&2; exit 1 ;;
  000) echo "  FAIL — no response: agent not running, wrong host/port, or blocked by firewall" >&2; exit 1 ;;
  *)   echo "  FAIL — unexpected HTTP ${PING}" >&2; exit 1 ;;
esac

echo "→ data  ${URL}/api/projects"
PROJ="$(curl -s --max-time 6 "${hdr[@]}" "${URL}/api/projects" 2>/dev/null || true)"
if command -v python3 >/dev/null 2>&1; then
  N="$(printf '%s' "$PROJ" | python3 -c 'import sys,json;
try: print(len(json.load(sys.stdin)))
except Exception: print(-1)')"
  if [[ "$N" == "-1" ]]; then
    echo "  FAIL — could not parse project list" >&2; exit 1
  elif [[ "$N" == "0" ]]; then
    echo "  PASS — agent online, but 0 projects (add your bots to that host's projects.yaml)"
  else
    echo "  PASS — pulling ${N} project(s) from this host"
  fi
else
  echo "  (python3 not found; raw response below)"; printf '%s\n' "$PROJ"
fi

echo "✅ This host is ready. Add it to devices.yaml:"
echo "   - name: my-host"
echo "     url: ${URL}"
echo "     api_token: \"${TOKEN}\""
