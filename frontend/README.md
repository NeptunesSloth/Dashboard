# Frontend build pipeline (opt-in)

This directory documents the **opt-in, additive** Vite build tooling for the
MayBot Control Center frontend.

## TL;DR — nothing about how the app serves the UI has changed

The FastAPI app (`maybot_control_center/app.py`) still serves the **source**
files in `maybot_control_center/static/` directly via its existing routes
(`/`, `/app.js`, `/style.css`, `/command.css`, `/chamber`, `/lib.js`, ...).
The default dev and prod serving path is **unchanged**. You do not need Node or
npm to run the app.

The Vite pipeline added here only lets you produce an **optimized
(bundled + minified) build** of the existing pages for evaluation. Switching
FastAPI over to serve those built assets is a deliberate **follow-up** and is
intentionally NOT done in this slice (see "Follow-up" below).

## Usage

From the repo root:

```bash
npm install        # installs Vite (devDependency) into ./node_modules
npm run build      # produces an optimized multi-page bundle in ./frontend-dist
```

Other scripts:

- `npm run dev`     – start the Vite dev server (optional, for experimentation)
- `npm run preview` – serve the built `frontend-dist/` locally
- `npm run lint`    – placeholder (no JS linter is configured yet)

Both `node_modules/` and `frontend-dist/` are git-ignored. **Do not commit
built assets or `node_modules/`.**

## What the build does

`vite.config.js` is configured as a **multi-page** build. Every existing HTML
entry point is a Rollup input:

| Input                                  | Served today at |
| -------------------------------------- | --------------- |
| `static/index.html`                    | `/`             |
| `static/command/index.html`            | `/command`      |
| `static/command/login.html`            | `/login`        |
| `static/command/chamber.html`          | `/chamber`      |
| `static/command/trade.html`            | `/trade`        |
| `static/command/treasury.html`         | `/treasury`     |
| `static/command/learn.html`            | `/learn`        |

The source files use **absolute** web paths (e.g. `/command.css`, `/lib.js`,
`/vendor/three.module.js`) because the FastAPI app exposes a flat URL namespace
even though the files live under `static/command/`. To bundle the existing
source **without rewriting it**, `vite.config.js` aliases each absolute path to
its real on-disk location. The command pages (`command.js`, `lib.js` with the
bundled `three.module.js`, `command.css`, and the per-page modules) bundle,
minify, and hash cleanly into `frontend-dist/assets/`.

### Known limitation: the root dashboard `app.js`

The root dashboard page (`static/index.html`) loads `app.js` as a **classic,
non-module** script:

```html
<script src="/app.js?v=2"></script>
```

Vite can only bundle scripts marked `type="module"`, so it emits a warning and
leaves that `<script src="/app.js?v=2">` reference untouched in the built
`frontend-dist/index.html`. The root page's CSS (`/style.css`) **is** bundled
and minified. This is expected for this slice — making the root dashboard's JS
fully bundle would require adding `type="module"` to that tag (a source change
that belongs to the follow-up, since `app.js` would then need to be verified as
module-safe).

## Follow-up (NOT done here): serve the built assets

Switching the running app to serve the optimized bundle is a separate, explicit
change. It would involve:

1. Decide a serving strategy behind a flag/env so the source-serving default is
   preserved (e.g. only serve `frontend-dist/` when an opt-in env var is set).
2. Add `type="module"` to the root `<script src="/app.js">` (and verify
   `app.js` runs as an ES module) so it bundles, OR keep serving `app.js` from
   source.
3. Point the FastAPI routes (or a `StaticFiles` mount) at `frontend-dist/`
   instead of `maybot_control_center/static/`, mapping the hashed asset names.
4. Wire `npm run build` into CI / the Docker image build so the bundle exists at
   deploy time.

Until that follow-up lands, treat this purely as build tooling.
