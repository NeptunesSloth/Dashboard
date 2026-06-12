# MayBot Control Center — Improvement Roadmap

A living, impact-ordered backlog of upgrades for the whole dashboard (not just the
Learning Center). Priorities: 🔴 high · 🟡 medium · 🟢 nice-to-have. Items are
delivered in **waves** — each a focused, tested, reviewable PR — rather than one
giant change.

## Wave 1 — additive hardening ✅
Safe, non-conflicting wins that don't require architectural changes:
- ✅ Repo lint cleanup (removed dead imports/vars) + `ruff` gate in CI (`E9,F`).
- ✅ CI: coverage on the test job, `pip-audit` security job (report-only).
- ✅ `dependabot.yml` (pip + GitHub Actions + Docker), `.pre-commit-config.yaml`.
- ✅ Opt-in `Content-Security-Policy` (`MAYBOT_CSP`) and `HSTS` (`MAYBOT_HSTS`).

## 🏗 Architecture & code health
- ✅ **Split `app.py`** into FastAPI `APIRouter`s by domain — done: shared deps
  live in `deps.py`, all routes live in 16 domain routers under `routers/*`, and
  `app.py` keeps only startup wiring, the middleware, the agent tunnel and the
  SSE stream (~230 lines).
- 🔴 **Modularize the frontend** — `app.js` (~230KB) → a small Vite build, split
  per page, shared API types. (Scaffolding exists — `vite.config.js`,
  `frontend/README.md` — but pages are still served unbuilt.)
- 🟡 **Async LLM/agent I/O** — fleet polling has an async path
  (`MAYBOT_ASYNC_POLL`); LLM calls still use blocking `requests`.
- 🟡 **Externalize shared state** — Redis-backed sessions/rate-limit stores exist
  in `authz.py` (`MAYBOT_REDIS_URL`); the rest is global dicts + locks, so
  multi-replica still isn't safe.
- 🟡 Type checking (`mypy`) — runs in CI report-only; tighten config over time.

## 🔒 Security
- ✅ **Password user auth** — `authz.py`: PBKDF2-hashed passwords, `users.yaml`
  accounts + roles, login sessions with expiry, TOTP 2FA. Remaining: an
  OAuth/SSO option, and per-user identity for the Learning Center (the single
  `scholar` learner key).
- 🟡 **mTLS / signed requests** — opt-in TLS with CA pinning + client certs for
  agent calls (`MAYBOT_AGENT_CA`, `MAYBOT_AGENT_CLIENT_CERT/_KEY`). Remaining:
  request signing, and making it the documented default posture.
- 🟡 **Secret management** — encryption-at-rest exists (`MAYBOT_SECRET_KEY`,
  Fernet). Remaining: rotation tooling.
- ✅ **Audit hardening** — the audit log is a SHA-256 hash chain
  (`audit.verify()`, `/api/audit/verify`) with JSONL export for SIEM ingestion
  (`/api/audit/export`).
- 🟢 Distributed rate limiting — Redis-backed store exists, off by default;
  CSRF protection once cookie auth lands.
- 🟢 Enforce CSP/HSTS by default once the UI is verified clean under them.
- ✅ **OpenAPI `/docs` gated** — interactive docs are off by default; opt in
  with `MAYBOT_DOCS=1`.

## 🛠 Reliability & ops
- ✅ **Postgres option + Alembic** — `store.py` speaks SQLite and Postgres
  (psycopg v3); a baseline Alembic migration lives in `alembic/`.
- ✅ Structured JSON logging (`MAYBOT_JSON_LOGS`), **Prometheus `/metrics`** +
  `/metrics/obs`; Sentry is opt-in (`MAYBOT_SENTRY_DSN`). Remaining:
  OpenTelemetry tracing, Grafana dashboards.
- ✅ Startup config validation — `config_check.py` warns (never fails) on
  common misconfig at boot.
- ✅ K8s/Helm — chart under `deploy/helm/maybot` with liveness (`/healthz`) and
  readiness (`/readyz`) probes; **graceful shutdown** closes the persistence
  connection cleanly on SIGTERM.
- 🟢 Scheduled backups exist (`retention.py`); remaining: encrypted + offsite
  destinations and restore drills.

## 🤖 Agent / LLM platform
- ✅ **Streaming responses** — `agents.stream_chat`, applied to the Ops Copilot
  and the Learning tutor. Remaining: stream generated lessons too.
- ✅ **Cost budgets & hard caps with alerts** — `budget.py`: sect-wide and
  per-agent daily/monthly caps with warning thresholds.
- ✅ Model fallback + retry-with-backoff (`MAYBOT_LLM_RETRIES`,
  `fallback_models`) and **context-window management** — message lists are
  trimmed to `MAYBOT_LLM_CONTEXT_CHARS` (oldest turns dropped first, system
  prompt and newest turns kept).
- 🟡 Output guardrails — opt-in secret redaction of model replies
  (`MAYBOT_LLM_REDACT`). Remaining: content moderation and an eval harness for
  agent quality.
- 🟢 Multimodal (image) support.

## 📣 Notifications
- ✅ Channels: Slack, Discord, generic webhook, email, Telegram, PagerDuty,
  Opsgenie — with dedupe, **per-channel severity routing**
  (`MAYBOT_NOTIFY_MIN_LEVEL[_<CHANNEL>]`), and operator **snooze**
  (`/api/notifications/snooze`). Remaining: SMS/Twilio, per-user routing,
  digest batching.
- ✅ Web Push (`push.py`, VAPID) for reminders/alerts.

## 🖥 Frontend / UX
- 🔴 Accessibility audit (ARIA, keyboard nav, contrast).
- 🟡 Mobile/responsive layout; a plain "professional" theme alongside the RPG
  theme. (PWA — manifest, service worker, install — exists; the agent tunnel
  already reconnects with exponential backoff.)
- 🟢 i18n/l10n.

## 🚀 DevEx / CI-CD
- 🟡 Expand CI gates as the code is typed/cleaned (mypy). Note: the coverage
  job deliberately has **no** `--fail-under` gate (documented in `ci.yml`).
  Remaining: release automation + changelog + semver tags.
- 🟡 Docker hardening (non-root user — needs the deployment's volume-ownership
  context); pinned base digests.
- 🟢 Staging / PR preview deploys.

## 📚 Documentation
- ✅ `ARCHITECTURE.md`, `CONTRIBUTING.md`, gated OpenAPI `/docs`
  (`MAYBOT_DOCS=1`). Remaining: diagrams.

## 🎓 Learning Center
- ✅ **End-to-end pentest range** — a SIMULATED virtual network you attack stage
  by stage: enumerate a reachable host, exploit it, loot credentials that unlock
  pivots, and move laterally (web → db → workstation → DC) toward a **concrete
  mission objective** (e.g. exfiltrate a specific file from the deepest host),
  completed via a `/range/capture` step. Exploits are graded on **tradecraft**
  (method/root-cause/post-ex awareness), not buzzwords. Zero command execution.
  (`/api/learning/range`, `/range/{id}`, `/range/enumerate`, `/range/exploit`,
  `/range/capture`.)
- ✅ **Blue-team incident investigation** — given an alert + multi-source logs,
  scope the real degree of compromise (entry vector, every compromised device,
  lateral path, exactly what was exfiltrated) and get graded on scoping accuracy
  + evidence. (`/api/learning/incident`, `/incident/grade`.)
- ✅ **Real-command labs (default-off contract)** — `attach_real_env` +
  `real_targets.yaml` bind a simulated host to an isolated microVM/sandbox target;
  execution routes through the guarded tools allow-list on an in-sandbox agent.
  Spec + topology in `docs/REAL_LABS.md`; surfaced at `/api/learning/real-env`.
  The model never turns free text into a shell command.
- ✅ **Test-out / placement** — prove mastery of a topic and skip it
  (`/api/learning/placement` + `/placement/grade`); tracks `mastered_topics`.
- ✅ **Stays current** — a `threats.yaml` / `MAYBOT_THREAT_CONTEXT` "current
  threat landscape" is woven into generated security lessons/labs/exams so
  content tracks how the field looks now, not just at the model's cutoff.
- ✅ **Real-world curriculum** — added Offensive Security/Red Team, Cloud &
  Container Security, and Blue Team/SOC tracks (AD attacks, privesc, lateral
  movement, cloud IAM, K8s, SIEM/EDR, DFIR).
- ✅ **Language tracks** — immersive, target-language tutor built on proven SLA
  methods (comprehensible input, retrieval, corrective recasts, high-frequency
  first) plus cloze + translation drills wired to spaced repetition
  (`/api/learning/drill` + `/drill/grade`).
- ✅ Lab hint system — spend spirit stones for a mentor nudge
  (`/api/learning/lab/hint`).
- 🔴 Real Docker pentest targets (command-execution labs via the guarded-tools
  allow-list — `attach_real_env()` is deliberately unbuilt until that lands).
- 🟡 Bring-your-own material (RAG over uploads); multi-learner profiles +
  leaderboard. (Auto-built flashcard decks exist — SM-2 spaced repetition.)
- 🟢 Certificates/shareable cards; adaptive difficulty; image-based labs.
