# Ephemeral per-learner lab range (CORE 4 — graduation requires execution)

Simulation builds the skill; **graduation** requires the learner to actually
exploit a **real** target in an **isolated, ephemeral** sandbox. This directory
is the operator-run provisioning for that — the control center never provisions
or runs commands itself (see `docs/REAL_LABS.md` for the safety model).

## What it provisions (per learner, per lab)

- An **internal-only Docker network** (`internal = true` → no egress to the host
  LAN or internet) — the containment boundary.
- **Vulnerable targets** (Juice Shop, DVWA) on that network.
- An **attacker box**: a `maybot_agent` inside the network running the
  allow-listed pentest toolkit (`tools.yaml`), scoped to the lab subnet only.

## Lifecycle (spin up → graduate → destroy)

```bash
cd deploy/lab-range
terraform init
terraform apply  -var="learner=scholar" -var="range_id=rng-123"   # provision
# the learner attacks the targets through the dashboard; each tool run is
# guarded (fixed argv, no shell, human-approved) and the agent reports results
# the agent/operator records a VERIFIED execution proof:
#   POST /api/learning/execution-proof  {domain, summary, lab, tool, verified:true}
terraform destroy -var="learner=scholar" -var="range_id=rng-123"  # reclaim — nothing persists
```

A Docker-Compose variant (`docker-compose.range.yml`) is provided for the
non-Terraform path.

## How graduation is gated

`GET /api/learning/graduation` returns the requirements and whether they're met:

1. Reach the **Security Analyst** knowledge rank (simulation progress).
2. **Real-command sandbox labs enabled** (`MAYBOT_REAL_LABS=1` + this range up).
3. **At least one VERIFIED real-sandbox exploitation** — a proof recorded by the
   in-sandbox agent/operator, not self-certified simulation.

Only `verified: true` proofs count, and the proof is recorded server-side and
credits the domain it was earned in. A learner who has only done simulations is
**not graduated**, by design.

## Stronger isolation

For a true separate-kernel boundary (recommended, since targets are intentionally
vulnerable and you're firing real exploits), run the Docker daemon under a
**Kata Containers** or **Firecracker** runtime so each container is a lightweight
VM. Host requirement: a KVM-capable machine. See `docs/REAL_LABS.md`.
