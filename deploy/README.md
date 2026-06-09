# Deploying MayBot Control Center to Kubernetes

Two equivalent ways to deploy the **control center** (the dashboard on port
`8200`, with `/healthz`) to a Kubernetes cluster:

- **Raw manifests + Kustomize** — `deploy/k8s/`
- **Helm chart** — `deploy/helm/maybot/`

Both pull the prebuilt image `ghcr.io/neptunessloth/dashboard:latest` (the same
image the `docker-compose.images.yml` deploy uses).

> These files are **additive** — they do not change the app, the `Dockerfile`,
> or the compose files.

---

## Important: single-replica caveat

**Keep the control center at `replicaCount: 1`.** It holds in-memory state
(login sessions, fleet/health status) and writes a SQLite DB to `/data`. Running
more than one replica would split that state and contend over the
`ReadWriteOnce` volume. Multi-replica / HA needs the planned Redis-backed shared
state (see `ROADMAP.md`); until then, scale **up** (bigger pod), not **out**.

The Deployment uses `strategy: Recreate` so a rolling update never runs two pods
against the same PVC/DB at once.

---

## Important: agents run on bot hosts, not in-cluster

An **agent** (`maybot_agent.app:app` on port `8100`) monitors the *host it runs
on* — the machine where your bots/processes live. In production agents run **on
each bot host** (via the `agent` service in `docker-compose.yml`, or a systemd
unit), **not** inside this cluster: an in-cluster pod can only see its own
namespace, not your bot hosts.

An **optional** in-cluster agent (`DaemonSet`, one per node) is provided for the
case where your bots themselves run as workloads in *this* cluster. It is
**disabled / not applied by default**:

- Kustomize: `deploy/k8s/agent-daemonset.yaml` is **not** in `kustomization.yaml`
  — apply it explicitly if you want it.
- Helm: gated behind `agent.enabled=false`.

Every agent must share `MAYBOT_API_TOKEN` with the control center and be
registered in `devices.yaml` (or self-register via `MAYBOT_REGISTER_TOKEN`).

---

## Secrets to set

Set these before exposing the control center on any network (see
`.env.example` for the full list). At minimum:

| Key | Purpose |
| --- | --- |
| `MAYBOT_CONTROL_CENTER_TOKEN` | Protects the dashboard. Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `MAYBOT_API_TOKEN` | Shared secret between the control center and each agent. Must match each agent host. |
| `MAYBOT_REGISTER_TOKEN` | (optional) Agent self-enrollment. |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM backend for the disciple agents. |
| `GH_TOKEN` | (optional) Real GitHub PR creation. |
| notify creds | `MAYBOT_SLACK_WEBHOOK`, `MAYBOT_DISCORD_WEBHOOK`, `MAYBOT_SMTP_*`, `MAYBOT_TELEGRAM_*`, `MAYBOT_PAGERDUTY_ROUTING_KEY`, `MAYBOT_OPSGENIE_API_KEY` |

---

## Option A — raw manifests (Kustomize)

```bash
# 1) Provide secrets. EITHER edit deploy/k8s/secret.yaml in place, OR (better)
#    create the Secret out-of-band so it never lives in git:
kubectl create secret generic maybot-secrets \
  --from-literal=MAYBOT_CONTROL_CENTER_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  --from-literal=MAYBOT_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..."
# (if you create it this way, remove secret.yaml from kustomization.yaml)

# 2) Edit the ingress host in deploy/k8s/ingress.yaml (default maybot.example.com).

# 3) Apply the control-center stack:
kubectl apply -k deploy/k8s

# 4) (optional) in-cluster agent, only if your bots run as workloads here:
kubectl apply -f deploy/k8s/agent-daemonset.yaml
```

What gets created: `ConfigMap`, `Secret`, `PersistentVolumeClaim` (5Gi,
`ReadWriteOnce`), `Deployment` (1 replica), `Service` (ClusterIP :8200),
`Ingress`.

---

## Option B — Helm

```bash
helm install maybot deploy/helm/maybot \
  --namespace maybot --create-namespace \
  --set secrets.data.MAYBOT_CONTROL_CENTER_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  --set secrets.data.MAYBOT_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  --set secrets.data.ANTHROPIC_API_KEY="sk-ant-..." \
  --set ingress.enabled=true \
  --set ingress.host=maybot.example.com
```

Or use your own values file: `helm install maybot deploy/helm/maybot -f my-values.yaml`.

Prefer not to put secrets in Helm values? Create the Secret yourself and point
the chart at it:

```bash
helm install maybot deploy/helm/maybot \
  --set secrets.existingSecret=maybot-secrets
```

### Key values (see `deploy/helm/maybot/values.yaml` for all)

| Value | Default | Notes |
| --- | --- | --- |
| `image.repository` / `image.tag` | `ghcr.io/neptunessloth/dashboard` / `latest` | |
| `replicaCount` | `1` | **Do not raise** — in-memory state. |
| `persistence.enabled` / `.size` | `true` / `5Gi` | `/data` PVC, `ReadWriteOnce`. |
| `persistence.existingClaim` | `""` | Reuse an existing PVC. |
| `ingress.enabled` / `.host` | `false` / `maybot.example.com` | |
| `secrets.data.*` | empty / `change-me` | Token & API key values. |
| `secrets.existingSecret` | `""` | Use a pre-made Secret instead. |
| `resources` | 100m/256Mi → 1/1Gi | requests → limits. |
| `agent.enabled` | `false` | Optional in-cluster agent DaemonSet. |
| `fixDataPermissions.enabled` | `false` | Root init container to `chown /data` (see below). |

Upgrade / uninstall:

```bash
helm upgrade maybot deploy/helm/maybot -f my-values.yaml
helm uninstall maybot --namespace maybot   # PVC is retained; delete it manually if desired
```

---

## Volume permissions caveat

The container runs as **non-root** (`runAsNonRoot: true`, uid/gid `1000`) for
safety, but it must write to the `/data` volume. Two mechanisms handle this:

1. **`fsGroup: 1000`** (set in the pod security context) tells the kubelet to
   `chown` the mounted volume to that group. Most storage classes honour this
   and it's all you need.
2. If your storage class does **not** honour `fsGroup` and the app can't write
   `/data`, enable the one-shot root init container that `chown`s the volume:
   - Helm: `--set fixDataPermissions.enabled=true`
   - Kustomize: the init container is already present in
     `control-center-deployment.yaml`; remove it if `fsGroup` alone suffices.

---

## Verifying the manifests

```bash
# Raw YAML parses:
python -c "import glob,yaml; [list(yaml.safe_load_all(open(f))) for f in glob.glob('deploy/k8s/*.yaml')]; print('k8s yaml OK')"

# Helm (if installed):
helm lint deploy/helm/maybot
helm template deploy/helm/maybot >/dev/null && echo 'helm template OK'

# Kustomize render (if kubectl/kustomize installed):
kubectl kustomize deploy/k8s >/dev/null && echo 'kustomize OK'
```
