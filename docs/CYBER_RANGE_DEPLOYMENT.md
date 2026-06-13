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

## Next step — connect a single Proxmox node

The `proxmox` provider in `orchestration.py` is an **interface skeleton**: it
reports whether config is present but, by design, does **not** claim to boot VMs
(it returns `unverified` / `unavailable`). To make it real:

1. Stand up a Proxmox VE node and create an API token.
2. Set the config the skeleton looks for:
   ```bash
   export MAYBOT_RANGE_PROVIDER=proxmox
   export MAYBOT_PROXMOX_URL=https://your-pve:8006/api2/json
   export MAYBOT_PROXMOX_TOKEN='user@pam!token=secret'
   export MAYBOT_PROXMOX_NODE=pve1
   ```
   `GET /api/range-infra/health?provider=proxmox` will now report `unverified`
   (config detected, driver not implemented) — **not** `ok`, and launches still
   return `unavailable`. This is deliberate: no untested production claims.
3. Implement the real driver: replace `ProxmoxProvider.launch/stop/reset/destroy`
   with calls to the Proxmox API (clone template → create isolated VNet → start
   VMs → register a Guacamole connection → return a signed connect URL), and
   `health()` should only return `ok` after a live reachability check.
4. **Add tests against a real (staging) node** in operator CI. Only after the
   driver is implemented and verified should `health()` return `ok` and `launch`
   return a `running` session with a real `connect_url`.

Until step 4 is done, the platform correctly tells learners the cyber range is
not live — which is the whole point of the honest control-plane design.
