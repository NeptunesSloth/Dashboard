# CLAUDE.md

Orientation for AI assistants (and humans) working in this repo. Keep it short;
update it when the shape of the project changes.

## What this is

**Sect Academy** — an offline, self-hosted study app (French A1/A2, Spanish
A1/A2, Security+ SY0-801, Network+ N10-009, ISC2 CC) wrapped in a
cultivation-world colony sim. One FastAPI process, one JSON state file, a
vanilla-JS front end. No network, no database, no LLM.

(The repo used to be "MayBot Control Center", a fleet dashboard. That code was
removed; it lives on in git history before the `sect_academy` restructure.)

## Run / test

```bash
pip install -r requirements.txt
python -m sect_academy              # http://127.0.0.1:8200

python -m sect_academy.packs        # validate every course file (CI gate)
python -m pytest -q                 # tests (CI gate)
ruff check .                        # lint (CI gate)
python -m sect_academy & python tests/smoke_browser.py   # browser smoke (CI gate)
```

`node --check sect_academy/static/<file>.js` catches JS syntax errors. The
smoke test drives the real app with every non-local request blocked and fails
if anything tries to leave the app — that is how "fully offline" is enforced.

## Layout

```
sect_academy/
  app.py        the whole server: study API, sect API, static shell
  packs.py      load + validate packs/*.yaml (courses and their part files)
  packs/        the courses (see docs/ACADEMY_CONTENT.md)
  fsrs.py       FSRS-6 scheduler, published default weights
  engine.py     enrolment, sessions, server-side grading, placement, trials
  colony.py     the sect: pawns, needs, work, building, research, storyteller
  state.py      one JSON file, always on; sanitises everything it loads
  static/       index.html, academy.js (shell + study), sect.js (colony UI),
                art.js (all artwork, vector), academy.css, sw.js
tests/          test_engine.py, test_colony.py, test_api.py, smoke_browser.py
docs/           ACADEMY_CONTENT.md, the design spec, research
```

## Things to know before changing anything

- **Item ids are the keys of saved progress. Never rename an item id.** Ids are
  unique across all packs; a course can be split into part files (`part_of`).
- **Content is the product.** A wrong answer key teaches an error. New or edited
  items need the validator clean and a second, independent check.
- **Cert courses are meant to be harder than the exam**: scenario stems, 85%
  pass mark, `multi` (choose N) and `order` items, a full-length mock.
- **The sect must not depend on study.** Everyone cultivates by meditating; study
  adds Master qi, research insight and mood. Don't make progress study-gated.
- **Nothing bad happens while the app is closed**: time away runs in quiet mode
  (no events, no starvation damage, no deaths), capped at 48 sim hours.
- **Grading and scheduling are server-side.** The server records what each
  session issued; only an issued item's first answer is scheduled and paid.
- **Don't hand-tune FSRS constants.**
- **Escape every string** with `esc()` before `innerHTML`. `colony.view()` casts
  every number server-side; `academy.js` passes other numbers through `num()`.
  `art.js` takes numbers and known ids only — never user text.
- **Offline is a hard rule**: no CDN, no web font, no external URL in anything
  the page loads. The CSP in `app.py` is `default-src 'self'`.
- **State safety** (`state.py`): atomic fsynced writes, a daily `.bak`, a
  damaged file is moved aside (never overwritten), and loaded/imported state is
  coerced and test-driven before use. Tests run with `SECT_ACADEMY_FILE=:memory:`
  (set in the root `conftest.py`).
- One process only: state is held in memory.
