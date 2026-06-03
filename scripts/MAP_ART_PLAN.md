# Sect Map — reference-quality art plan

Goal: replace the hand-drawn SVG Sect Map with real painted assets so it matches
the xianxia reference art, keeping the existing engine (peak layout, click-to-
zoom, hall, status→activity mapping).

## Provider
OpenAI `gpt-image-1` (only image API reachable from this sandbox; Replicate/fal
are TLS-blocked). Requires `OPENAI_API_KEY` set in the environment.

## Step 1 — generate assets
```
OPENAI_API_KEY=...  python scripts/generate_map_assets.py
```
Writes PNGs to `maybot_control_center/static/assets/map/`:
- `bg_sky.png` — dawn sky + distant ranges (world backdrop)
- `cloudsea.png` — transparent cloud-sea overlay (foreground band)
- `peak_a/b/c.png` — transparent floating-peak sprites (placed dynamically, scaled by realm)
- `peak_leader.png` — grand peak w/ pavilion + sacred tree (the Sect Leader)
- `hall_bg.png` — pavilion-on-a-cliff backdrop for the zoomed hall
- `char_cultivate/sweep/struggle/seclude/roam.png` — transparent cultivator figures per activity

These ARE app assets → commit them (served at `/assets/map/...`).

## Step 2 — re-render using the assets (rewrite in app.js `renderSectMap` + `enterHall`)
- World: `bg_sky.png` as the scene background; place each disciple as an absolutely-
  positioned `<img>` peak sprite (peak_leader for the leader, else peak_a/b/c by
  hash), `bottom`/`width` scaled by realm, name plaque overlaid, click → `enterHall`.
  Overlay `cloudsea.png` at the base; keep the drifting-leaves layer.
- Hall: `hall_bg.png` as the backdrop; the `char_*.png` for the current activity as
  the centered figure with subtle CSS motion (bob/glow/qi-pulse). Keep the stats +
  chronicle side panel and the return-to-heavens zoom-out.
- Keep `hallActivity()` status mapping and the reduced-motion guard.
- Delete the now-unused SVG spire/foliage/figure CSS+JS once the image path works.

## Step 3 — verify + commit
Screenshot world + each hall activity via the Playwright harness (Chromium at
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, `--no-sandbox`,
`device_scale_factor=1`, width ≤ 980), iterate prompts if needed, then commit to
the PR branch.
