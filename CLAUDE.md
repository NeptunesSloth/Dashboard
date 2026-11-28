# CLAUDE.md

Orientation for AI assistants (and humans) working in this repo. Keep it short;
update it when the shape of the project changes.

## What this is

**Sect Academy** — an offline, self-hosted study app (French and Spanish A1 to
B2 plus conversation courses, Mandarin, Japanese and Korean A1–A2 plus conversation
courses, picture lessons, a reader with dictionaries, Security+,
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
  packs/pictures/  shared picture-lesson pictures: pin ids + positions, one file each
  fsrs.py       FSRS-6 scheduler, published default weights
  drills.py     generated drills (graded here, never scheduled): subnetting, ports, and the
                language drills (kinds conj-<lang>, num-<lang>; the learner picks tenses/kinds)
  drills_lang.py verb forms: es/fr read from the dict C lines (bad cells listed in _BAD),
                ja/ko conjugated here (JMdict class; Hangul jamo, irregular class per verb)
  drills_num.py numbers both ways, times, dates, prices, counters in all five languages
  hand.py       handwriting: stroke data lookup + the stroke matcher that grades
                `glyph_write` server-side; hangul.py composes Hangul strokes from jamo
  strokes/<lang>/  stroke data, each folder with a README naming source and licence
                (ja/: KanjiVG, CC BY-SA 3.0; zh/: Make Me a Hanzi, Arphic Public
                License, ARPHICPL.TXT kept unaltered beside it)
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
                and search for the kaikki.org-built dictionaries; zh.py, ja.py
                + ja_rules.py (deinflection, rōmaji), cjk.py (the lattice
                segmenter for unspaced text))
  shelf/        the starter shelf: public-domain stories (<lang>/<slug>.txt) and poems
                (<lang>/poems.yaml, with our own English lines), manifest.yaml with the
                evidence for each; read-only, ids shelf:<lang>:<slug> (see its README)
  dict/<lang>/  dictionary data, one folder per language, each with a README
                naming source and licence (es/, fr/, ko/: English Wiktionary via
                kaikki.org, CC BY-SA 4.0 — those files are under that licence, not ours)
  static/       index.html, academy.js (shell + study), sect.js (colony UI),
                reader.js (Read: shelf, pages, lookup card, dictionary, My words),
                pictures.js (picture lessons: pins, drag/tap exercises),
                handwriting.js (writing pad, live stroke hints, demo, self-check),
                art.js (places the painted art: the room grid, tiles, scenes, emblems), art/*.webp, academy.css, sw.js,
                vendor/pdfjs/ (Mozilla pdf.js 3.11.174, Apache-2.0, LICENSE there)
tests/          test_engine.py, test_tracks.py, test_sect_optional.py, test_drills_lang.py, test_colony.py, test_dao.py, test_api.py, test_reader.py, test_reader_words.py, test_lexicon_fr_ko.py,
                test_handwriting.py, test_overhaul.py (the sect overhaul, stage by stage),
                test_lexicon_zh_ja.py, lexicon_quality.py (zh/ja hit rate and word boundaries on the courses),
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
- **The sect is optional** (`settings.sect_enabled`, default True; `colony.enabled`).
  Off = study only: founding's "Just study, no sect" (`/api/setup` with
  `study_only`, names kept in `settings.sect_name`/`sect_master`) or the Settings
  toggle (`POST /api/sect-mode`). While off: `colony.ensure` pins `last_real` to
  now (no catch-up), `/api/sect/*` answers 409 except `seclusion` (holiday mode),
  study pays no qi/insight/mood (the streak still counts), and the UI shows a
  study home at `/` (`renderHome`) with no Sect tab. Turning it on founds it if
  needed and restarts its clock from now. Study routes never read sect state.
- **Work choice** (`colony._pick_job`): meditation is not a chore; level with the
  work a disciple would do it takes half their hours (`MED_SHARE`), and any
  store under `LOW_STORE_DAYS` of use (not share of capacity) comes first. The
  stall alert names the exact priority to set (`stall_advice`).
- **Mid-game risk** (tuned by `tests/balance.py`): great-realm breakthrough odds
  are capped per realm (`BT_CAP`, shown as a ledger row; pills give less at
  deeper realms), tournaments draw a field scaled to the sect (`tournament_field`,
  odds shown match the resolver's roll), rival pairs are capped (`rival_cap`) and
  mend daily, and disciples at home add research each evening (`PAVILION_READ`,
  in the research ledger) so research never needs study.
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
- **Sect overhaul** (`docs/SECT_OVERHAUL_PLAN.md`, approved; built stage by stage):
  the home map has no upgrade badges and nothing boxed on the painting (a room's name
  is carved on the beam under it with its level as a numeral, and warms to gold when affordable; crews stand on
  the floor line; slots, fit and the rest show on hover, focus or while dragging; `MAP_LOOK` in `sect.js` is a
  temporary A/B: names on the beams, or a ledger rail beside the map, until the owner picks; the Build tab is a ledger: lantern timers, rooms sorted by
  ready / short of materials / waiting on the Hall — the owner's picks, one path only);
  `colony.trays` lights a room with what its crew made since dawn (view
  only until stage 4); `colony.hall_next` feeds the "Main Hall n" card under the map.
  **Builders** (stage 2): building is builder slots (`builders`, ledger `builder_rows`:
  2, +1 at Hall 3/6/9, +1 while the Master is lent by a week of study). The first
  `builders(c)` jobs in `c["builds"]` each gain one sim hour an hour (`_tick_builds`)
  whether or not anyone helps; disciples on Build are helpers (`HELPER_X` each, two
  per job, ledger `build_rate_rows`). Times are `ROOM_HOURS`/`HALL_HOURS` (sim hours,
  none over 36). While an event waits, only the builders work on, at the away rate
  (`_builders_wait`); sealed gates stop them too. A counted session draws a Master's
  Blueprint (`use_blueprint`: 25% off one job, one a real day, 3 kept). The old
  `build_stall` alert is gone: a builder cannot stall.
  **Main Hall ladder** (stage 3): Hall 1–10, rooms to 8 (Trade Post 3). `HALL_LADDER`
  says which rooms each level opens and the room cap (never above Hall+1);
  `build_block` gives the reason a build is refused (also the view's `locked`), and
  raising the Hall to n+1 needs `HALL_ROOMS_NEEDED` other rooms at level n
  (`hall_rooms_check`, the card's checklist). Costs: base × `COST_CURVE`**level,
  spirit stones from level 4. Old saves above the new caps keep their rooms.
  Builders still idle most hours: with timers capped at 36 h, materials pace the
  ladder (balance columns `idle_builder`, `want_mat`, `hall`).
  **Room play** (stage 4): the roster under the map posts a disciple by drag (or tap,
  then a room): `set_post` makes the room's job(s) (`POSTS`) first priority, within
  `room_slots`; the Work grid stays as the detailed view (setting a post's job off 1
  clears the post). A tray (`trays`, since dawn or the last look) is already in the
  stores; tapping it (`inspect_tray`) only cheers the crew (+3 mood, 12 h, once a room
  a day), so never tapping loses nothing (balance profile `collect` pins it). `rush`
  (room: 6 h of its work now; build: finished now) rolls the odds `rush_rows` and
  `contain_rows` show; an uncontained incident idles the room 6 h (`room_idle`,
  checked in `_job_open`) or sets the build back, wounds but never kills, and queues
  an `incident` scene.
  **Grid and merging** (stage 5): the home map is `hq_grid.webp` (5 floors × 6 alcoves) with a painted tile per room
  (`room_<type>.webp`; `art.js` `cellRect` holds the alcove borders, measured on the painting). One room of each kind:
  its level stays in `c["rooms"]`, where it stands is `c["plots"]` (`{room: {f, s, w}}`, floor 0 = the ground; the Hall
  is always 2 wide, the vault 1). `colony._layout` runs on every `_c` and in `_repair`: every standing room, the Hall and
  the vault get alcoves (an old save lands on `DEFAULT_CELL`), nothing overlaps, so tests may still poke `c["rooms"]`.
  Floors open with the Hall (`FLOOR_HALL`); the page shows only the floors in use, cut under the roof. A new room takes
  the empty alcove you pick (`queue_build(..., cell)`; none given = its usual place). **Merging**: `widen` builds a wing
  (a build job with `wing: [f, s]`, cost `wing_cost` = every level so far, a builder like any job) in the empty alcove
  beside a room; when done the room is one alcove wider (2 from Hall 3, 3 from Hall 5, `WIDE_HALL`). Width gives
  places/beds × width and yield `WIDE_X` (1.1 / 1.2), and later levels cost `WIDE_COST` and take `WIDE_TIME` (never
  over 36 h); every one is a ledger row (`merge_rows` in the room and alcove sheets, plus rows in `farm_rows`,
  `research_rows`, `qi_rate`). No level while a wing is built (the halls must match), and a wing is refused if it
  would leave fewer empty alcoves than rooms not yet built. `move_room` is free. Count queued levels with
  `colony._queued` (a wing is not a level). Balance profile `merge` (wings whenever affordable) is pinned level with careful.
- **World map** (`sect.js` `worldMap`): a list of places beside the painting, a
  hanging banner per landmark, the chosen place's card opened under its row in the
  list (never on the painting, so it hides no label). Markers are **painted emblems
  only**: `static/art/place_<kind>.webp` (`colony.PLACE_KINDS`; the view gives each
  place its `emblem` and lists the files that exist in `place_art`, `art.place()`
  builds the path). Until an emblem is painted there is no icon: the banner hangs
  from a soft point of lantern light (cinnabar rival, jade ally, dim not-yet-known)
  and the list row is name + status with a thin coloured left rule. Never draw a
  marker in CSS: the owner rejected dots, flat shapes and both seal looks. Status
  stays in words ("Hostile −26", "Sworn ally", "Not yet known").
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
  positions (`book_pos`: the END of the page last open, so shelf and pager
  show the same "% read") live in the state. The lookup card docks beside the
  page from 1100px wide and is a bottom sheet (with a spacer, `#rd-pad`) below
  that: it must never cover a word. My words items (`personal: True` packs)
  get their modes from `engine._personal_mode` (choose while FSRS stability
  < 2 days, then `type_l2` / `cloze_type` on the saved sentence, built by
  `reader._cloze`), and a small deck borrows distractors from the same
  language's course vocab (`engine._course_vocab`). Personal item ids are
  `my-<lang>-<word>` (hashed suffix when the word is not plain a-z) and the
  `my-` prefix is refused in YAML packs. Adding a language's lookup = a data
  folder in `dict/<lang>/` with its README + a module in `lexicon/` registered
  in `MODULES`; the reader asks the server to segment each page
  (`POST /api/dict/segment`) so CJK can segment by dictionary.
- **Dictionary licence**: `dict/es/`, `dict/fr/` and `dict/ko/` are CC BY-SA 4.0
  (English Wiktionary via kaikki.org). Keep the credit lines (`CREDIT` in each
  module) shown with results, and keep each `dict/<lang>/README.md`. Rebuild
  them with `python scripts/build_dict_kaikki.py` (streams the JSONL, never
  stores it; frequencies from FrequencyWords, CC BY-SA, used at build time
  only). A gloss is sections, one per Wiktionary entry (`pos: sense; sense |
  pos: …`, best first: names, abbreviations and dialect last; `KO_FIRST`
  orders common Korean homographs); `C` lines hold each verb form's
  tense/person, given as `gram` ("ser / ir, preterite, 3rd person singular").
  `dict/<lang>/function_*.tsv` (ours) gives function words a learner's gloss
  shown first (src "core"). `python scripts/lexicon_hit_rate.py es fr ko`
  measures lookup on every course sentence (99.7% / 99.9% / 99.7% when built;
  `tests/test_lexicon_fr_ko.py` holds a floor), and `tests/lexicon_common.py`
  checks the first meaning of ~200 common words per language (all five; held
  at 100% by `tests/test_lexicon_common.py`). Korean results carry `rom`,
  `lemma_rom` and `gram` (the particle or ending taken off); My words (Korean)
  items get `rom` so the deck accepts romanised answers.
  `dict/zh/` is CC-CEDICT (CC BY-SA 4.0) plus jieba word counts (MIT);
  `dict/ja/` is JMdict — the credit "JMdict, Electronic Dictionary Research and
  Development Group" with https://www.edrdg.org/edrdg/licence.html must stay
  in `lexicon/ja.py` `CREDIT` and `dict/ja/README.md`. Rebuild both with
  `python scripts/build_dict_zh_ja.py` (never commit the raw downloads).
- **Chinese / Japanese lookup**: pages are cut by `cjk.lattice` (cheapest path:
  ~1 per word, cheaper for frequent words, dearer for kana spellings of kanji
  words and rare entries). Japanese conjugations are undone by the suffix rules
  in `ja_rules.py`, kept only where the JMdict part of speech agrees. Rōmaji:
  macrons for display (gakkō), kana-as-written for typing (gakkou, the course's
  convention). Before tuning costs, run `python tests/lexicon_quality.py`
  (hit rate and boundary agreement on every course sentence; was zh 100% hit,
  boundaries P 100% / R 90%; ja 99.8% hit, P 95% / R 94%).
- **Dictionary memory** (all five loaded: about 345 MB for the five tables alone): indexes are `cjk.IdMap`
  (a bare int for a key with one entry), JMdict entries stay raw UTF-8 lines
  split on access, kaikki form tables hold one interned lemma string per form
  and build their lowered-gloss list on the first English search. Keep results
  identical when touching these (compare lookups before/after).
- **Picture lessons** (docs/ACADEMY_CONTENT.md): a `picture` item names a shared
  picture (`packs/pictures/<id>.yaml`) and gives each pin its word; each pin is
  its own card `<item id>-<pin id>` (type `pin`). New pins are one drag exercise
  (`engine.group_pictures`, answered by `/api/answer/picture`, which calls
  `engine.answer` once per pin), then `pic_tap`, then `type_l2` with the pin lit.
  A unit whose `static/art/pic_<id>.webp` is missing is held back (`pack["soon"]`,
  "Picture coming soon"). `scripts/pin_preview.py <id>` draws the pins on the
  painting to set coordinates; brief in docs/ART_PIPELINE.md "Round 3".
- **Tracks** (`packs.tracks()`): a language's levels are one course to the learner.
  A pack header with `track: french` + `level: A1` is a stage; `track: french` +
  `addon: talk` is an add-on (conversations, pictures, `swear`: swearing & slang, opt-in), never a stage. Pack and item
  ids are unchanged; `settings.courses` still holds pack ids, but enrolling any
  stage (or the track id) enrols every stage, and `engine.migrate_tracks` widens
  old saves on load. Only the current stage (the lowest with unseen items) gets
  new items, from one allowance per track (`engine.track_state`; it spills into
  the next stage only once the current one is fully introduced); add-ons keep their
  own. Placement for a track is one test that walks on into the next stage only
  when every unit of the stage was passed (`PLACEMENT_MAX_QUESTIONS` per stage,
  `PLACEMENT_TRACK_MAX` overall), saved under the track id. The UI deals in
  `OV.tracks` (library card with a level strip, "French · A2" in today/progress).
- One process only: state is held in memory.
- **Handwriting** (`glyph_write`): a glyph item that is known (FSRS stability >=
  `hand.WRITE_MIN_S`, every other review, setting `handwriting` on) is asked
  written from its sound. The page checks each stroke with a JS port of the
  matcher only to hint; it then posts every stroke drawn (failed ones too) to
  `/api/answer/write`, and `hand.check` replays them: correct when every
  character is complete with <= `slips_allowed` misses (any miss, or the
  outline/demo, makes it Hard). Keep `TOL` in `handwriting.js` equal to the
  constants in `hand.py` (a test compares them). "I wrote it on paper" is
  `glyph_self`, a self-report capped at Hard. Both modes are handled before the
  `_MODES` check in `engine.check` (they are never asked in trials). Stroke
  data covers all kana and every CJK character in the ja/zh course files;
  after adding characters run `python scripts/build_strokes.py` (the coverage
  test names what is missing). Korean needs no file: `hangul.py` is ours.
