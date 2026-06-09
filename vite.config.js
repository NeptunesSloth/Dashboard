import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Directory of this config file (repo root).
const repoRoot = fileURLToPath(new URL('.', import.meta.url));

// The existing source UI. Vite treats this as the web root so that the
// absolute asset paths used by the HTML (e.g. "/app.js", "/style.css") resolve
// the same way the FastAPI app serves them.
const staticDir = resolve(repoRoot, 'maybot_control_center/static');
const commandDir = resolve(staticDir, 'command');

// ---------------------------------------------------------------------------
// Opt-in, additive Vite build pipeline for the MayBot Control Center frontend.
//
// IMPORTANT: This does NOT change how the app serves the UI. The FastAPI app
// continues to serve the source files in maybot_control_center/static/ directly.
// Running `npm run build` only produces an optimized bundle in `frontend-dist/`
// for evaluation. Wiring FastAPI up to serve the built assets is a documented
// FOLLOW-UP (see frontend/README.md) and is intentionally NOT done here.
//
// Multi-page build: every existing HTML entry point is a Rollup input.
//
// The source HTML/JS use ABSOLUTE web paths ("/command.css", "/lib.js",
// "/vendor/three.module.js", "/chamber.js", ...). On disk those files live
// under maybot_control_center/static/command/, but the URLs are flat because
// the FastAPI app exposes them via explicit routes. To let Vite bundle the
// existing source UNCHANGED, we alias each absolute path to its real on-disk
// location instead of rewriting the source files.
// ---------------------------------------------------------------------------
export default defineConfig({
  root: staticDir,
  // Keep the public web root semantics ("/foo") for resolved imports.
  base: './',
  resolve: {
    alias: [
      { find: '/lib.js', replacement: resolve(commandDir, 'lib.js') },
      { find: '/command.js', replacement: resolve(commandDir, 'command.js') },
      { find: '/command.css', replacement: resolve(commandDir, 'command.css') },
      { find: '/chamber.js', replacement: resolve(commandDir, 'chamber.js') },
      { find: '/learn.js', replacement: resolve(commandDir, 'learn.js') },
      { find: '/login.js', replacement: resolve(commandDir, 'login.js') },
      { find: '/trade.js', replacement: resolve(commandDir, 'trade.js') },
      { find: '/treasury.js', replacement: resolve(commandDir, 'treasury.js') },
      { find: '/vendor/three.module.js', replacement: resolve(commandDir, 'vendor/three.module.js') },
      { find: '/vendor/OrbitControls.js', replacement: resolve(commandDir, 'vendor/OrbitControls.js') },
      // Root page assets (served by FastAPI from static/).
      { find: '/app.js', replacement: resolve(staticDir, 'app.js') },
      { find: '/style.css', replacement: resolve(staticDir, 'style.css') },
    ],
  },
  build: {
    // Output OUTSIDE the source tree so the running app is never affected.
    outDir: resolve(repoRoot, 'frontend-dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(staticDir, 'index.html'),
        command: resolve(commandDir, 'index.html'),
        login: resolve(commandDir, 'login.html'),
        chamber: resolve(commandDir, 'chamber.html'),
        trade: resolve(commandDir, 'trade.html'),
        treasury: resolve(commandDir, 'treasury.html'),
        learn: resolve(commandDir, 'learn.html'),
      },
    },
  },
});
