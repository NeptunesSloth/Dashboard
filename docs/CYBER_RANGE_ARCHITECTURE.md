# Browser-based Cyber Range — Architecture

> **Scope honesty (read first).** This document is the architecture and the
> control-plane code seam (`orchestration.py`) that makes it real in the
> codebase. The **VM/hypervisor/gateway runtime is operator-deployed**: it needs
> real hardware or a cloud account, a hypervisor, money, and an ops function. It
> cannot run inside CI or the hosted web sandbox (no nested virtualization), so
> nothing here fakes a VM — the control center *orchestrates* infrastructure it
> does not host, exactly as a control panel should. The dashboard stays a
> **website**; it is the control plane, not the VM host.

## 1. Architecture redesign (the layers)

```
Browser (dashboard SPA + embedded VM viewport)
   │  HTTPS / WSS
Backend API (FastAPI control center)  ── authz, lab catalog, sessions, validation
   │
Orchestration engine (Temporal workflows)  ── durable provision/cleanup, retries
   │
Hypervisor control plane (Proxmox VE API ; Firecracker for dense Linux)
   │
VM infrastructure (attacker + target VMs on a per-session isolated network)
   │
Browser access gateway (Apache Guacamole: RDP/VNC/SSH → WebSocket)
   │
Observability + session recording + DETERMINISTIC validation (in-VM agent → control plane)
```

Every layer is replaceable behind an interface. The control center already owns
the top two layers; this design adds the orchestration seam and specifies the
rest.

## 2. Infrastructure diagram (logical)

```
                         ┌──────────────── control center (website) ───────────────┐
                         │  FastAPI · routers/range_infra.py · orchestration.py     │
                         │  Postgres (labs, sessions, environments, flags, evidence)│
                         └───────────────┬──────────────────────────┬───────────────┘
                                         │ Temporal                  │ Guacamole API
                              ┌──────────▼─────────┐        ┌────────▼─────────┐
                              │ Orchestration       │        │ Guacamole guacd  │
                              │ workflows (durable) │        │ (RDP/VNC/SSH)    │
                              └──────────┬─────────┘        └────────┬─────────┘
                          Proxmox API / Firecracker                  │ WebSocket
                              ┌──────────▼───────────────────────────▼─────────┐
                              │  Per-session isolated network (VLAN/VXLAN, NO   │
                              │  egress)   [attacker VM] … [target VMs] + agent │
                              └─────────────────────────────────────────────────┘
```

## 3. Recommended tech stack (with rationale)

| Layer | Choice | Why (vs alternatives) |
|---|---|---|
| Hypervisor (baseline) | **Proxmox VE cluster** | Real REST API, clustering, snapshots/clone/rollback, SDN for per-session VLANs, **runs Windows + AD + K8s targets**, no licensing cost. ESXi rejected (cost/licensing); raw KVM/QEMU rejected as baseline (you'd rebuild Proxmox's clustering + API). |
| Hypervisor (dense Linux) | **Firecracker microVMs** (phase 2) | ~125ms boot, minimal attack surface, cheap density for ephemeral Linux attacker/target boxes. Can't run Windows/AD (no full device model) — so it's an optimization layer, not the baseline. Kata Containers as the easy on-ramp (keeps Docker UX, VM isolation). |
| Orchestration / queue | **Temporal** | Lab provisioning is a multi-step workflow with compensation (clone → network → boot → inject → monitor → return URL → **guaranteed teardown**). Temporal gives durable execution, retries, and cleanup guarantees Celery/RQ/RabbitMQ don't. Redis for caching/rate-limit/session state. |
| Browser access | **Apache Guacamole** | Clientless RDP (Windows desktop), VNC (Kali desktop), SSH (terminal) → WebSocket; built-in **session recording**, clipboard/file-transfer control, connection brokering. noVNC/WeTTY as narrow fallbacks. WebRTC streaming rejected (heavy, no clear win here). |
| Network isolation | **Proxmox SDN (VNet per session) + nftables, no egress NAT** | One isolated L2 per learner; firewall denies egress by default; teardown destroys the VNet. Firecracker path uses tap devices in a per-session netns. |
| Validation | **Deterministic in-VM agent → control plane** (NOT AI) | Agent reports signed evidence (uid==0, file hashes, per-session HMAC flags, auth/process logs); control plane verifies cryptographically. |
| Monitoring | **Prometheus + Grafana + Loki + OpenTelemetry** | Prometheus (node/libvirt/cAdvisor exporters) for metrics, Loki for logs, OTel traces across API + Temporal. ELK rejected as heavier than Loki for this. |
| DB | **Postgres** (already supported via `store.py`) | Relational data (labs/sessions/flags/evidence) + JSONB for lab configs. |
| Frontend | Incremental SPA (the repo has `vite.config.js`) | Keep vanilla JS near-term; the VM viewport is a Guacamole `<iframe>`/client embed. |

## 4. Frontend redesign

Dashboard sections (control panel, not VM host): **Infrastructure** (cluster
capacity, active VMs, templates, health), **Learning Center** (existing),
**Attack Labs** (launch/reset/stop/connect → Guacamole viewport), **Defensive
Labs** (SIEM/PCAP/IR — feeds the existing incident + purple-team engines),
**Analytics** (progress, exploit success rate, weak domains, cert readiness — all
already built server-side), **Admin** (templates, lab authoring, monitoring,
audit). The VM appears as an embedded Guacamole client; the page never touches a
hypervisor directly — it calls `/api/range-infra/*`.

## 5. Backend redesign

The control center exposes a **range-infrastructure API** (`routers/
range_infra.py`) over an **orchestration provider abstraction**
(`orchestration.py`): `providers()`, `provision(lab)`, `status(env)`,
`connect(env)`, `destroy(env)`. The API is provider-agnostic; the real Proxmox/
Firecracker driver is an operator-installed provider. Long operations are handed
to Temporal; the API returns an environment id immediately and the UI polls
`status`.

## 6. Database schema (additions)

```
lab_templates(id, name, kind[attacker|target], image_ref, os, version, notes, created)
labs(id, name, config JSONB, difficulty, duration_min, network_profile, flags JSONB, success_conditions JSONB)
environments(id, lab_id, owner, provider, status, network_id, ttl_expires_at, connect_url, created, destroyed_at)
env_vms(id, env_id, role, template_id, internal_ip, vm_ref)
session_flags(id, env_id, flag_name, hmac_value, captured_at)         -- per-session signed flags
evidence(id, env_id, kind, payload JSONB, signed, verified, created)  -- deterministic validation inputs
validations(id, env_id, condition, passed, evidence_id, created)
audit_sessions(id, env_id, owner, recording_ref, started, ended)      -- Guacamole recording pointer
```

Postgres + JSONB. Lab configs match the structured definition in §10.

## 7. VM orchestration system

Temporal workflow `ProvisionLab(lab_id, owner)`:
`allocate → clone templates → create isolated VNet → boot attacker+targets →
inject scenario + per-session signed flags → start monitoring → register
Guacamole connection → return connect URL`. Compensation/teardown
(`DestroyEnvironment`) is guaranteed on TTL expiry, completion, or failure.
`orchestration.py` is the in-process seam the API uses; the Temporal worker calls
the same provider interface.

## 8. Browser access implementation

Guacamole `guacd` + the web client behind the control center's auth. On
`provision`, the workflow creates a Guacamole connection (RDP for Windows, VNC
for Kali, SSH for terminal targets) scoped to the session network, with clipboard
and file-transfer disabled by default and **session recording on**. `connect`
returns a short-lived, signed URL to the embedded client. No local VM software.

## 9. Lab deployment engine

Driven entirely by the structured lab config (§10) — no hardcoding. A lab names
its attacker template, target templates, network profile, duration, flags, and
success conditions; the engine resolves templates → clones → networks → boots →
injects → returns access. Reset = destroy + re-provision from snapshot.

## 10. Lab definition (config)

```json
{
  "lab_id": "ad_attack_001",
  "name": "Active Directory Initial Compromise",
  "attacker_vm": "kali_template",
  "target_vms": ["windows_workstation", "domain_controller"],
  "duration_minutes": 120,
  "network_profile": "isolated_ad_network",
  "difficulty": "medium",
  "flags": ["user.txt", "dc_admin.txt"],
  "success_conditions": ["shell_obtained", "domain_admin"]
}
```

Stored in `labs.config` (JSONB). Templates (offensive: Kali/Parrot/Burp/Metasploit;
targets: vulnerable Ubuntu/Apache, DVWA/Juice Shop, DC, Windows workstation,
Linux/Windows privesc boxes, vulnerable Docker/K8s, SIEM box) are versioned,
snapshotted Proxmox templates cloned per session.

## 11. Security hardening plan

- **VM escape**: KVM/Proxmox hardening, microVM (Firecracker) for untrusted Linux,
  no nested virt for learners, per-session ephemeral hosts, patched hypervisor.
- **Network**: deny-egress by default, per-session L2 isolation, nftables, no
  route between sessions; attack traffic physically can't leave the VNet.
- **Browser/session**: signed short-TTL connect URLs, Guacamole behind authz,
  clipboard/file-transfer off, full session recording.
- **Anti-abuse**: cgroup CPU/RAM/disk caps (anti-cryptomining + DoS), per-user
  quota + concurrency limits, API rate limits (already in the middleware).
- **Anti-cheat** (§ below): per-session HMAC-signed flags, deterministic
  evidence, command/session audit logs, AI tutor sealed from answers.

## 12. Scaling plan

Stateless control center (already moving there: Redis sessions/rate-limit in
`authz.py`, Postgres state) → horizontal API replicas behind a LB. Proxmox
cluster scales by adding nodes; Temporal workers scale independently;
provisioning is queue-bounded by cluster capacity with backpressure. Cohorts/CTF
events = batch-provision N environments from one lab. Thousands of concurrent
users = node count × density (Firecracker raises density for Linux labs).

## 13. Automated testing plan

- **Control-plane (CI-runnable, built here)**: the provider abstraction +
  lifecycle state machine are unit-tested with a fake provider (no infra).
- **Infra (operator CI, real hardware)**: a smoke lab provisioned + destroyed on
  a staging Proxmox node per release; validation-engine evidence checks against a
  known-good target.
- **Validation determinism**: golden evidence fixtures → expected pass/fail.

## 14. Monitoring plan

Prometheus scrapes node/libvirt/cAdvisor + the control center's `/metrics`;
Grafana dashboards for cluster capacity, active envs, provision success/latency,
queue depth, VM health; Loki for VM + control-plane logs; OTel traces for the
provision workflow; alerts on provision failure rate, capacity exhaustion, and
stuck teardowns.

## 15. Production deployment plan

Proxmox cluster (3+ nodes, Ceph or ZFS replication) + a control-plane host
running the FastAPI app, Temporal, Guacamole (`guacd`), Postgres, Redis, and the
Prometheus/Grafana/Loki stack — containerized, fronted by a reverse proxy with
TLS. Blue/green for the control center; the cluster is long-lived, environments
are ephemeral.

## 16. Implementation roadmap

1. **Control-plane seam (this PR)** — provider abstraction + lifecycle tracker +
   API + tests. Default provider returns "infra not configured"; the simulated
   range remains the working tier.
2. **Single-node Proxmox provider** — real clone/network/boot/destroy against one
   node; one Linux lab end-to-end.
3. **Guacamole gateway** — browser access to that lab.
4. **Deterministic validation agent** — signed flags + evidence for that lab.
5. **Temporal workflows** — durable provision/teardown, retries, TTL cleanup.
6. **Windows/AD templates + SDN isolation**; monitoring stack.
7. **Multi-node cluster, quotas, Firecracker density, cohorts/CTF, leaderboards.**

## 17. Immediate code changes (in this PR)

`orchestration.py` (provider registry + `RangeProvider` interface + `null` and
`simulated` providers + a store-backed environment lifecycle tracker) and
`routers/range_infra.py` (`/api/range-infra/providers|provision|status|connect|
destroy`). Default-off; honest "not configured" for external hypervisors (no
fake provisioning). Wires to the existing `attach_real_env` + `deploy/lab-range/`
direction.

## 18. Weak points in the current architecture (called out)

- **Single-operator / single-learner core** (`MAYBOT_LEARNER="scholar"`) — blocks
  cohorts/orgs; needs a real identity + tenancy layer for §12.
- **In-memory state with locks** in many modules — caps horizontal scale until
  moved to Postgres/Redis (partially done in `authz.py`).
- **Vanilla-JS no-build frontend** — fine now, but a real range UI (embedded VM
  client, live infra panels) wants the SPA the repo is scaffolded for.
- **No infrastructure layer at all today** — labs/ranges are simulated; this
  design adds the seam, but the runtime is net-new operator infra.
- **Blocking `requests` in the LLM path** — async for scale.

## 19. Fake implementations removed / avoided

The simulated range is honestly labelled as simulation (not pretend-real VMs).
The real-execution path (`attach_real_env`, `real_targets.yaml`) is **default-off
and returns a real "not configured" contract** rather than faking success — and
this orchestration seam follows the same rule: external providers return
`not_configured`, never a fabricated VM.

## 20. Continuous improvements beyond the request

Per-session **signed flags** (anti-replay/anti-sharing) baked into the schema;
**TTL-based guaranteed teardown** (cost control + hygiene); **deterministic
validation as the only grader** (AI never decides correctness — it already
doesn't); **provider abstraction** so Proxmox/Firecracker/Kata/cloud are swappable
without touching the API or UI.
