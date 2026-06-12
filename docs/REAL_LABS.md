# Real-command pentest labs — design & operator guide

> **Status: default-OFF contract + spec.** The dashboard ships the *simulation*
> (objective-driven ranges, blue-team incidents, tradecraft grading — all
> server-side, zero execution) plus the **binding contract** to a real sandbox
> (`attach_real_env`, `real_targets.yaml`, `MAYBOT_REAL_LABS`). The execution
> backend — the microVM sandbox + a `maybot_agent` inside it — is **operator-
> deployed**, because it requires hardware virtualization that doesn't exist in
> every host (and never in the hosted web session). This doc is the build spec.

## The three tiers (recap)

| Tier | What runs | Status |
|------|-----------|--------|
| Simulated labs / ranges / incidents | Nothing — the model invents the target and grades your free-text finding/plan. | **Built.** |
| Real Log Lab (read-only) | You attack a Docker target yourself; the dashboard only *reads* the resulting logs (`fetch_real_logs`). | **Built.** |
| Real-command labs | The learner drives actual recon/exploit **tools** against a live target. | **This doc — default-off contract; sandbox is operator-run.** |

## The two safety problems (and which layer solves each)

Real execution has two *independent* risks. You need both layers; neither alone is safe.

1. **Containment — "where does an exploit land?"** Solved by an **isolated
   virtual environment**: a microVM/VM with its own kernel, an internal-only
   network with **no egress**, torn down per session. Because the targets are
   *intentionally vulnerable* and you're firing *real* exploits, container escape
   is a live concern — a separate kernel (KVM) is the boundary that matters.

2. **Command origination — "what runs, and who chose it?"** Solved by the
   existing **guarded-tools allow-list** (`tools.py`/`tools.yaml`): deny-by-default,
   fixed `argv` with **no shell**, the agent may fill only validated `{placeholders}`,
   every call is **human-approved unless `auto_approve`**, and **audited**. The
   model can *request an allow-listed tool with parameters*; it can never emit a
   shell command. This rule does not change inside the sandbox.

## Isolation: microVMs

Recommended boundary for this use case:

- **Kata Containers** — keeps the existing `labs/docker-compose.yml` UX but backs
  each pod with a lightweight VM. Lowest migration cost; **recommended default.**
- **Firecracker** — minimal microVMs, ~100–150 ms boot, snapshot/restore, the
  `jailer` for defense-in-depth. Best for truly ephemeral per-session ranges if
  you'll build the kernel/rootfs + a small orchestrator.
- **Full QEMU/KVM** — only if learners need an interactive Kali-style attacker
  desktop with snapshots.

**Host requirement:** a KVM-capable host (bare metal or a cloud instance with
nested virtualization). This will not run inside an ordinary container or CI.

## Topology

```
            control center (this app)  ──tunnel──►  maybot_agent  (ATTACKER microVM)
            • dispatches guarded tools                • runs allow-listed tools here
            • human approval + audit                  • scoped to the lab subnet only
                                                      │
                                          internal-only lab network (NO egress)
                                                      │
                                   ┌──────────────────┼───────────────────┐
                              target VM (web)    target VM (db)      target VM (dc)
                              intentionally-vulnerable, ephemeral, snapshot-booted
```

- The attacker microVM hosts a `maybot_agent`; tools execute **there**, never on
  the control center.
- Targets and attacker share an **internal** virtual network with egress blocked
  (no NAT to the host LAN or internet). Scope is the subnet — tools are
  allow-listed against lab IPs only.
- Environments are **ephemeral**: snapshot-boot per session, destroy on
  completion/timeout, so compromise/escape can't accumulate.

## How a range host binds to a real target

`attach_real_env(exercise, host_id)` returns `None` unless **both**:

1. `MAYBOT_REAL_LABS=1`, and
2. `real_targets.yaml` maps that `host_id` to a sandbox target.

When bound it returns a descriptor — the in-sandbox agent name, the
sandbox-internal target, the isolated network, and the **allow-listed tools** —
and nothing else. Actual enumerate/exploit steps then dispatch a guarded
`tools.run` call to that agent (fixed argv, validated args, approval, audit) and
feed the **real tool output** back into grading, replacing the model's guess.

`GET /api/learning/real-env` reports whether this is wired so the UI can clearly
flag "simulated" vs "live sandbox."

## `real_targets.yaml`

See `real_targets.yaml.example`. Each entry maps a simulated host id to one
isolated target and the guarded tools permitted against it:

```yaml
targets:
  - host_id: web1                 # the simulated range host id
    agent: lab-attacker           # maybot_agent running INSIDE the sandbox
    target: 10.10.0.10            # sandbox-internal address ONLY
    network: 10.10.0.0/24         # the isolated lab subnet (scope guard)
    allowed_tools: [nmap_scan, nikto_scan]   # must exist in tools.yaml
    requires_approval: true
    ephemeral: true
```

## Pentest tools in `tools.yaml`

Define each tool as a fixed `argv` scoped to the lab subnet, human-approved (see
the pentest section of `tools.yaml.example`). Example:

```yaml
  - name: nmap_scan
    description: Service/version scan of a single lab host.
    argv: ["nmap", "-sV", "-Pn", "--top-ports", "200", "{target}"]
    args: [target]          # validated: no spaces/metacharacters, bounded length
    timeout_seconds: 120
    # no auto_approve → a human approves each run in the dashboard
```

`{target}` is validated by the existing guard (no shell metacharacters); the
operator is responsible for only registering an agent whose network reaches the
lab subnet and nothing else.

## Why it's still gated even with all this

Isolation makes it *buildable*, not automatic. Keep deny-by-default, keep the
model out of command origination, block egress, and keep environments
disposable. The simulation already teaches the methodology and OPSEC; this tier
adds real tool output for operators who can stand up the sandbox safely.
