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

## 🎓 Learning Center — remaining
- 🔴 Real Docker pentest targets (phase 3, command-execution labs via the
  guarded-tools allow-list — `attach_real_env()` is deliberately unbuilt until
  that lands).
- 🟡 Bring-your-own material (RAG over uploads); multi-learner profiles +
  leaderboard. (Auto-built flashcard decks exist — SM-2 spaced repetition.)
- ✅ Lab hint system — spend spirit stones for a mentor nudge
  (`/api/learning/lab/hint`).
- 🟢 Certificates/shareable cards; adaptive difficulty; image-based labs.
