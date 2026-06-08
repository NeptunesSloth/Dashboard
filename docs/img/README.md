# Documentation screenshots

These images are used throughout `docs/` and the top-level `README.md`.

## Regenerate them

They're produced by `scripts/screenshots.py` (headless Chromium via Playwright)
against a running dashboard:

```bash
pip install playwright && playwright install chromium
docker compose up -d                       # or run uvicorn; serve on :8200
python scripts/screenshots.py              # writes the PNGs in this folder
```

Point it elsewhere with `SCREENSHOT_BASE_URL` / `SCREENSHOT_TOKEN`. For
representative (non-empty) shots, run it against an instance that has a few
projects configured.

| File | View | Route |
|---|---|---|
| `dashboard-classic.png` | Operations console (overview, disciples, Sect Map, ops) | `/console` |
| `dashboard-cockpit.png` | Command cockpit (default landing page) | `/` |
| `trade-cockpit.png` | Trading cockpit (advisor, risk, kill-switch) | `/trade` |
| `treasury.png` | Sect treasury | `/treasury` |
| `realm-map.png` | Sect Map (members across the heavens by realm) | `/console` (Map tab) |
