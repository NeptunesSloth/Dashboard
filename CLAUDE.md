# CLAUDE.md

Orientation for AI assistants (and humans) working in this repo. Keep it short;
update it when the shape of the project changes.

## What this is

**Sect Academy** — an offline, self-hosted study app (French and Spanish A1 to
B1 plus conversation courses, Mandarin, Japanese and Korean A1, Security+,
Network+, ISC2 CC, A+ Core 1 and 2, CySA+, CCNA)
wrapped in a cultivation-world colony sim. One FastAPI process, one JSON state file, a
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
  drills.py     generated subnetting and port drills (graded here, never scheduled)
  engine.py     enrolment, sessions, server-side grading, placement, trials
  colony.py     the sect: pawns, needs, work, building, research, storyteller,
                breakthroughs, rival sects, choice events (see _RESOLVERS)
  lore.py       names and tables for the cultivation world (data only)
  dao.py        the deeper systems (lineage, companions, heart demons, precepts,
                merit, council, alchemy, paths, kingdom, alliances, sieges,
                demonic path, succession); colony.py calls its small hooks
  road.py       staffed expeditions, master-disciple trust, named rivals,
                meridians, per-realm requirements, standing orders (dao.py
                calls its hooks)
  state.py      one JSON file, always on; sanitises everything it loads
  reader.py     the Read section: routes lookups to lexicon/, your own entries and
                saved words (per language, in the state), the "My words" courses
                (served to packs via packs.set_personal), the book shelf
  lexicon/      per-language lookup modules + registry (__init__.py: the module
                contract; es.py: Spanish lookup, candidates, segmentation;
                fr.py: elisions, inversions; ko.py: jamo, particles, endings,
                irregulars, Revised Romanization; kaikki.py: the shared table
                and search for the kaikki.org-built dictionaries)
  dict/<lang>/  dictionary data, one folder per language, each with a README
                naming source and licence (es/: Wiktionary via doozan/spanish_data,
                CC BY-SA 4.0 — that file is under that licence, not ours;
                fr/, ko/: English Wiktionary via kaikki.org, same licence)
  static/       index.html, academy.js (shell + study), sect.js (colony UI),
                reader.js (Read: shelf, pages, lookup card, dictionary, My words),
                art.js (places the painted art), art/*.webp, academy.css, sw.js,
                vendor/pdfjs/ (Mozilla pdf.js 3.11.174, Apache-2.0, LICENSE there)
tests/          test_engine.py, test_colony.py, test_dao.py, test_api.py, test_reader.py, test_lexicon_fr_ko.py,
                balance.py + test_balance.py (scripted 150-day games),
                smoke_browser.py
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
- **Work choice** (`colony._pick_job`): meditation is not a chore; level with the
  work a disciple would do it takes half their hours (`MED_SHARE`), and any
  store under `LOW_STORE_DAYS` of use (not share of capacity) comes first. The
  stall alert names the exact priority to set (`stall_advice`).
- **Nothing bad happens while the app is closed**: time away runs in quiet mode
  (no events, no starvation damage, no deaths), capped at 48 sim hours.
- **Grading and scheduling are server-side.** The server records what each
  session issued; only an issued item's first answer is scheduled and paid.
- **Don't hand-tune FSRS constants.**
- **Escape every string** with `esc()` before `innerHTML`. `colony.view()` casts
  every number server-side; `academy.js` passes other numbers through `num()`.
  `art.js` takes numbers and known ids only — never user text.
- **The art is painted, not vector.** The owner disliked the bright vector look;
  keep the lantern-night palette that matches `static/art/`. New images go in
  `static/art/` as WebP and are served from the fixed list in `app.py`.
- **Result scenes**: big outcomes (raid, tournament, festival, funeral,
  tribulation, breakthrough, realm) queue a card via `colony._scene` (cap 5,
  repaired on load). Painting `static/art/scene_<kind>.webp` is used when the
  file exists; until then `art.scene()` falls back to a backdrop.
- **Time waits for the player**: while an event is pending or the gates are
  sealed the sim does not advance (watching or away). Great-realm breakthroughs
  are never automatic; the player orders them (`colony.attempt`).
- **Difficulty is tuned by simulation, not by feel.** Before changing yields,
  appetite or threat strength, run a 150-day scripted game on each storyteller
  with an idle profile and a careful one: idle should starve or lose people on
  balanced/harsh, careful should survive balanced. `python tests/balance.py 150
  12345,7,99` prints the table; `tests/test_balance.py` pins its shape. Daily
  costs (eating, winter, repairs, spoilage) all come from `colony.upkeep`.
- **A new event needs** a branch in `_daily_event`, a `_res_<kind>` in
  `_RESOLVERS`, and to survive `test_every_trope_event_can_be_raised...`.
- **Every number the player is affected by must appear in a ledger** (mood,
  cultivation speed, breakthrough odds, breakthrough grade). Opaque systems are
  the genre's standing complaint (docs/research/notes/competitors_cultivation_games.md).
  A new modifier goes through the `dao.*_rows` hooks, not a hidden multiplier.
- **Only known hostnames are answered** (`_allowed_hosts` in `app.py`); serving
  on a LAN name needs `SECT_ACADEMY_HOSTS`.
- **Chinese, Japanese, Korean**: `rom` (romanisation) on items and dialogue
  lines, `ex_rom` on example sentences, `glyph` items for the script. Typed
  answers in these scripts are graded by `_check_script` in engine.py (script
  or romanisation, spacing ignored, pinyin tone numbers accepted, no typo
  forgiveness). An alternative answer written in the script needs its own
  romanisation listed in `alt` too.
- **Exam versions**: CySA+ is CS0-004 (June 2026). CCNA follows v2.0 (first
  test 3 February 2027; v1.1 is live until then). Topics v2.0 dropped sit in
  `cn-bg-*` units under domain `x` (weight 0), so trials never draw them.
- **Offline is a hard rule**: no CDN, no web font, no external URL in anything
  the page loads. The CSP in `app.py` is `default-src 'self'`.
- **State safety** (`state.py`): atomic fsynced writes, a daily `.bak`, a
  damaged file is moved aside (never overwritten), and loaded/imported state is
  coerced and test-driven before use. Tests run with `SECT_ACADEMY_FILE=:memory:`
  (set in the root `conftest.py`).
- **Reader**: books are text only, extracted in the browser (EPUB by hand,
  PDF by vendored pdf.js loaded on demand, `isEvalSupported: false`, same-origin
  worker, so the CSP needed no change), stored in `<state file>.books/`
  (`<id>.txt` + `<id>.json`; ids are 12 hex, checked before any path is built;
  capped at 200 books / 64 MB; `:memory:` keeps them in a dict). Only reading
  positions (`book_pos`) live in the state. Personal item ids are
  `my-<lang>-<word>` (hashed suffix when the word is not plain a-z) and the
  `my-` prefix is refused in YAML packs. Adding a language's lookup = a data
  folder in `dict/<lang>/` with its README + a module in `lexicon/` registered
  in `MODULES`; the reader asks the server to segment each page
  (`POST /api/dict/segment`) so CJK can segment by dictionary.
- **Dictionary licence**: `dict/es/es_en.tsv.gz` is CC BY-SA 4.0 (Wiktionary
  contributors, via doozan/spanish_data). Keep the credit line (`CREDIT` in
  `lexicon/es.py`) shown with results, and keep `dict/es/README.md`.
  `dict/fr/` and `dict/ko/` are CC BY-SA 4.0 too (English Wiktionary via
  kaikki.org); rebuild them with `python scripts/build_dict_fr_ko.py` (streams
  the JSONL, never stores it). `python scripts/lexicon_hit_rate.py fr ko`
  measures lookup on every course sentence (99.9% / 99.7% when built;
  `tests/test_lexicon_fr_ko.py` holds a floor). Korean results carry `rom`,
  `lemma_rom` and `gram` (the particle or ending taken off); My words (Korean)
  items get `rom` so the deck accepts romanised answers.
- One process only: state is held in memory.
