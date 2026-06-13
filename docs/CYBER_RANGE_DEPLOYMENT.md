# Cyber Range — operator deployment (connecting real VM infrastructure)

The dashboard ships a **control plane** for VM labs (`orchestration.py`,
`/api/range-infra/*`). It does **not** host VMs and does not fake them: with no
provider connected, every launch honestly returns `unavailable` and no session is
marked running. This doc is what an operator must stand up to make labs **live**.

## What is real today (no infrastructure needed)

- The lab catalog (`lab_catalog.yaml`) — lab + template definitions.
- The provider abstraction + lifecycle state machine (`orchestration.py`).
- The API: `GET /api/range-infra/{providers,health,labs,sessions,session/{id},events}`,
  `POST /api/range-infra/{launch,stop,reset,destroy}`.
- The dashboard "Cyber Range" panel, which shows an honest **"infrastructure not
  connected yet"** banner until a provider reports healthy.
- Provider health: `none` (default) and `proxmox` (interface skeleton).

All of the above is unit-tested. None of it boots a VM.

## What still requires operator deployment (to go live)

| Need | What to deploy |
|---|---|
| Hypervisor | A **Proxmox VE** node/cluster (baseline) — or ESXi / Firecracker / KVM. |
| Templates | The VM templates named in `lab_catalog.yaml` (Kali attacker, vulnerable targets, DC, etc.), snapshotted for instant clone. |
| Isolated networks | Per-session VLAN/VNet with **no egress** (Proxmox SDN + nftables). |
| Browser access | **Apache Guacamole** (`guacd` + client) for RDP/VNC/SSH in the browser. |
| Orchestration | **Temporal** (durable provision/teardown) for production; the in-process seam suffices for a single node initially. |
| Validation | An in-VM agent that reports **deterministic, signed evidence** (uid==0, file hashes, per-session HMAC flags) to the control plane. |
| Monitoring | Prometheus + Grafana + Loki (libvirt/node/cAdvisor exporters). |

See `docs/CYBER_RANGE_ARCHITECTURE.md` for the full design and rationale.

## Connecting a Proxmox node (the driver is implemented)

The `proxmox` provider in `orchestration.py` is now a **real driver** (Proxmox VE
REST API, token auth, in `proxmox.py`): it clones templates into per-session VMs
on an isolated VLAN, starts them, confirms `running` via the API, and rolls back
on failure. It is unit-tested against a mocked API (`tests/test_proxmox.py`) — but
it has **not** been run against a live node here, and it still returns **no
console URL** because browser access (Guacamole) isn't wired yet.

### 1. Stand up Proxmox + a token

A Proxmox VE node, and an API token (`Datacenter → Permissions → API Tokens`).

### 2. A VLAN-aware lab bridge with NO uplink

Create a Linux bridge (default `vmbrLAB`) that is **VLAN-aware** and has **no
physical uplink / no gateway** — this is the egress boundary. The driver attaches
every session VM to it with a unique VLAN tag + per-NIC firewall, so sessions
can't see each other or the internet.

### 3. Templates → VMIDs

Build each VM named in `lab_catalog.yaml`, "Convert to template", and map the
logical name to its VMID in `proxmox_templates.yaml` (copy
`proxmox_templates.yaml.example`).

### 4. Point the control center at it

```bash
export MAYBOT_RANGE_PROVIDER=proxmox
export MAYBOT_PROXMOX_URL=https://your-pve:8006     # /api2/json is appended automatically
export MAYBOT_PROXMOX_TOKEN='user@pam!labtoken=SECRET'
export MAYBOT_PROXMOX_NODE=pve1
export MAYBOT_PROXMOX_LAB_BRIDGE=vmbrLAB
export MAYBOT_PROXMOX_TEMPLATES_FILE=proxmox_templates.yaml
# self-signed cert? export MAYBOT_PROXMOX_VERIFY_TLS=0  (use a real cert in prod)
```

`GET /api/range-infra/health?provider=proxmox` now returns **`ok`** only after a
live `/version` reachability check (`error` if unreachable). `POST
/api/range-infra/launch {"lab_id":"linux_privesc_001"}` clones + isolates + starts
the VMs and returns a **`running`** session — but `connect_url` is still `null`.

### 5. Verify against your node, then enable browser access

- Run the gated integration test on a staging node:
  ```bash
  MAYBOT_PROXMOX_INTEGRATION=1 \
  MAYBOT_PROXMOX_URL=… MAYBOT_PROXMOX_TOKEN=… MAYBOT_PROXMOX_NODE=… \
  python -m pytest -q tests/test_proxmox.py::test_integration_launch_and_destroy_real_node
  ```
- **Browser access is still required to actually use a lab from the website.**
  Deploy Apache Guacamole and implement `proxmox.guacamole_connect_url()` to
  register an RDP/VNC/SSH connection for the session and return a short-lived
  signed URL. Until then the VM runs but the dashboard honestly shows it has no
  console URL.

## Browser access — Apache Guacamole (implemented driver)

The `guacamole.py` client + the provider integration are real: when a Proxmox
session reaches `running`, the control center registers a **per-VM Guacamole
connection** (one per browser-accessible VM), and the session's `connect_url`
becomes a **short-lived signed link** to the broker endpoint. It is mock-tested
(`tests/test_guacamole.py`); a real Guacamole server is required to actually open
a console.

### Deploy Guacamole

1. Run **guacd + the Guacamole webapp** (the official `guacamole/guacd` +
   `guacamole/guacamole` containers, with a Postgres/MySQL auth DB), behind your
   reverse proxy with TLS.
2. **Network**: guacd must reach the isolated lab VLAN (give it an interface on
   `vmbrLAB`, or route to it). The lab VLAN still has **no internet egress** — only
   guacd can reach the guests.
3. **Guests** need the service Guacamole connects to **and the qemu-guest-agent**
   (so the driver can discover the guest IP): Kali → VNC server (or SSH), Windows
   → RDP enabled, Linux targets → SSH.
4. Point the control center at it:
   ```bash
   export MAYBOT_GUACAMOLE_URL=https://guac.internal
   export MAYBOT_GUACAMOLE_USER=maybot
   export MAYBOT_GUACAMOLE_PASSWORD=…            # a Guacamole admin that can create connections
   export MAYBOT_GUACAMOLE_DATASOURCE=postgresql  # or mysql
   # optional hardening (default ON): MAYBOT_GUAC_DISABLE_CLIPBOARD / _FILE_TRANSFER
   ```
5. Optional per-template access creds (`access:` section in
   `proxmox_templates.yaml`): protocol/port/username/password per template.
   Absent creds → Guacamole prompts in-browser. For true **per-session
   credentials**, inject them into the guest at clone time with cloud-init and put
   the same values in the access config (documented enhancement; the control
   center never invents creds the guest won't honour).

### How browser access behaves

- Guacamole **not configured** → labs still launch (VMs run), but `connect_url`
  is `null`. No fake console link — ever.
- Guacamole configured + a guest IP found → a connection is created and a signed
  `connect_url` is returned. The dashboard "Open Browser Lab" button resolves it
  into the real Guacamole client URL (no raw VM IPs in the response).
- Connection **create failure** rolls back the whole launch (VMs + any partial
  connections). Connections are **deleted** from Guacamole on stop/destroy/reset.
- Clipboard + file transfer are **restricted by default**; connect links expire
  (`MAYBOT_CONNECT_TTL_SEC`, default 600s); opens are written to the audit log.

## Hygiene

`POST /api/range-infra/reap` destroys sessions past their lab TTL; `POST
/api/range-infra/cleanup-orphans` destroys lab VMs on the node whose session no
longer exists (run both on a cron/timer in production).
