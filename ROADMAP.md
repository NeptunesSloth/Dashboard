# MayBot Control Center — Improvement Roadmap

A living, impact-ordered backlog of upgrades for the whole dashboard (not just the
Learning Center). Priorities: 🔴 high · 🟡 medium · 🟢 nice-to-have. Items are
delivered in **waves** — each a focused, tested, reviewable PR — rather than one
giant change.

## Wave 1 — additive hardening ✅ (this PR)
Safe, non-conflicting wins that don't require architectural changes:
- ✅ Repo lint cleanup (removed dead imports/vars) + `ruff` gate in CI (`E9,F`).
- ✅ CI: coverage on the test job, `pip-audit` security job (report-only).
- ✅ `dependabot.yml` (pip + GitHub Actions + Docker), `.pre-commit-config.yaml`.
- ✅ Opt-in `Content-Security-Policy` (`MAYBOT_CSP`) and `HSTS` (`MAYBOT_HSTS`).

## 🏗 Architecture & code health
- 🔴 **Split `app.py`** (~3k lines, 100+ routes) into FastAPI `APIRouter`s by
  domain. First extract shared deps (`check_token`/`check_operator`/`resolve_device`)
  into `deps.py`, then move routes domain-by-domain. _(Do after PR #49 merges to
  avoid conflicts on the learning routes.)_
- 🔴 **Modularize the frontend** — `app.js` (~230KB) → a small Vite build, split
  per page, shared API types.
- 🟡 **Async LLM/agent I/O** — replace blocking `requests` in hot paths with
  `httpx`/async or a consistent thread pool.
- 🟡 **Externalize shared state** — global dicts + locks block multi-replica; move
  to DB/Redis so the app can scale horizontally.
- 🟡 Type checking (`mypy`) once the code is router-split.

## 🔒 Security
- 🔴 **Real user auth** — per-user accounts (hashed passwords or OAuth/SSO),
  sessions, per-user identity (also fixes the single `scholar` learner key).
- 🔴 **mTLS / signed requests** between control center and agents (they execute
  commands).
- 🟡 **Secret management** — encrypted-at-rest store + rotation (keys are in env /
  plaintext YAML today).
- 🟡 **Audit hardening** — tamper-evident log + SIEM export.
- 🟢 Distributed rate limiting (Redis); CSRF protection once cookie auth lands.
- 🟢 Enforce CSP/HSTS by default once the UI is verified clean under them.

## 🛠 Reliability & ops
- 🔴 **Postgres option** (SQLite limits concurrency) + **Alembic migrations**.
- 🟡 Structured JSON logging; **Prometheus `/metrics`** + Grafana; **OpenTelemetry**
  tracing; **Sentry** error tracking.
- 🟡 Startup config validation (fail fast with clear messages).
- 🟡 K8s manifests / Helm chart; readiness/liveness probes; graceful shutdown.
- 🟢 Scheduled, encrypted, offsite backups + restore testing.

## 🤖 Agent / LLM platform
- 🔴 **Streaming responses** (chat + lessons feel instant).
- 🔴 **Cost budgets & hard caps with alerts** per agent.
- 🟡 Model fallback/routing + retry-with-backoff; context-window management.
- 🟡 Output guardrails/moderation; an eval harness for agent quality.
- 🟢 Multimodal (image) support.

## 📣 Notifications
- 🟡 More channels (SMS/Twilio, PagerDuty, Opsgenie); per-user/per-severity routing,
  digest batching, dedupe, snooze.
- 🟢 Mobile push (`push.py`) for reminders/alerts.

## 🖥 Frontend / UX
- 🔴 Accessibility audit (ARIA, keyboard nav, contrast).
- 🟡 Mobile/responsive + PWA (installable, offline, push); WebSocket reconnect/backoff;
  a plain "professional" theme alongside the RPG theme.
- 🟢 i18n/l10n.

## 🚀 DevEx / CI-CD
- 🟡 Expand CI gates as the code is typed/cleaned (mypy, coverage threshold);
  release automation + changelog + semver tags.
- 🟡 Docker hardening (non-root user — needs the deployment's volume-ownership
  context); pinned base digests.
- 🟢 Staging / PR preview deploys.

## 📚 Documentation
- 🟡 Architecture docs + diagrams; expose OpenAPI `/docs` (gated); contributing guide.

## 🎓 Learning Center — remaining
- 🔴 Real Docker pentest targets (phase 3, command-execution labs via the
  guarded-tools allow-list).
- 🟡 Bring-your-own material (RAG over uploads); auto-built flashcard decks;
  multi-learner profiles + leaderboard.
- 🟢 Lab hint system (spend stones); certificates/shareable cards; adaptive
  difficulty; image-based labs.
