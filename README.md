# MayBot Control Center (Distributed)

## Components
- `maybot_agent`: runs on each host and exposes authenticated local project telemetry API.
- `maybot_control_center`: central dashboard that polls multiple agents from `devices.yaml`.

## Setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy examples:
   - `cp projects.yaml.example projects.yaml` on each agent host.
   - `cp devices.yaml.example devices.yaml` on the control center host.
4. Set token on each agent host:
   - `export MAYBOT_API_TOKEN='strong-token'`
5. Start agent:
   - `uvicorn maybot_agent.app:app --host 127.0.0.1 --port 8100`
6. Configure `devices.yaml` with per-device URL/token.
7. Start control center:
   - `uvicorn maybot_control_center.app:app --host 127.0.0.1 --port 8200`
8. Open `http://127.0.0.1:8200`.

## Safety
- Agents are local/private by default.
- API token is required on every agent route.
- Start/stop/test actions only run commands explicitly listed in `projects.yaml`.
- Missing files/paths return `unknown` without crashing.
