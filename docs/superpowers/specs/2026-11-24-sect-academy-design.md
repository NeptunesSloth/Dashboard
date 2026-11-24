# Sect Academy — design

Status: built. This is the second design; the first (a dashboard add-on with a
study-driven idle game) was replaced after the owner asked for a standalone,
offline app with a real colony sim. Research behind the choices is in
`docs/research/`.

## Intent

A study app you open every day — French, Spanish, entry cyber-security
certifications — inside a game worth playing for its own sake: a
cultivation-world colony sim in the spirit of RimWorld.

## What the owner asked for, and how each is met

| Ask | How |
|---|---|
| Works completely offline | One local process; no CDN, font, API or LLM. CSP `default-src 'self'`. The browser smoke test blocks every non-local request and fails if one is attempted. |
| Cultivation must not depend solely on learning | The sect runs on its own clock; every disciple cultivates by meditating. Study is an optional second engine (see below). |
| Remove everything not needed | The fleet dashboard, host agent, trading, LLM features and AI tutor are gone. The repo is one package, `sect_academy`. |
| Think RimWorld / colony sim; rebuild from the ground up | `colony.py`: pawns with needs, mood and thoughts, skills with passions, traits, work priorities, resources, construction, research, a storyteller with scaling threats, injury and death. |
| Fill out French and Spanish | A1 completed to 20 units each; A2 added (12 units each). |
| Finishing a cert course should mean passing the exam; make it harder than the test | Full objective coverage per domain, scenario questions written above exam difficulty, choose-N and ordering items, 85% pass mark, full-length mocks, a strict readiness checklist. |
| A test at the start to find your level, and adjust | Adaptive placement test per course; units tested out of are skipped and return as reviews. |

## Architecture

```
sect_academy/
  app.py     server (study API, sect API, static shell, optional token)
  packs.py   course loader/validator; packs/*.yaml (+ part files)
  fsrs.py    FSRS-6
  engine.py  sessions, grading, placement, trials, readiness, stats
  colony.py  the sect
  state.py   one JSON file; sanitises what it loads
  static/    academy.js, sect.js, art.js, academy.css, sw.js
```

## Study

- **Scheduling**: FSRS-6, default weights, 90% target recall. Review gaps are
  measured in the learner's calendar days. Due reviews first; new items rationed
  per course per day (8) and held back when the backlog is deep.
- **Formats harden with memory**: meet → recognise → recall → type → dictation
  (languages); definition↔term (concepts); `mcq`, `multi` (choose N,
  all-or-nothing), `order` (put steps in order) are always tests.
- **Server-side grading**. Wrong = Again; right with an accent or one-letter slip
  = Hard; right = Good. A wrong article is never forgiven; on words under four
  letters the accent is the word. The server records what a session issued and
  schedules only an issued item's first answer.
- **Placement**: per unit, three typed questions (languages) or two test
  questions (certs). Pass a unit (2 of 3; 2 of 2) and its unseen items become
  cards due over the next 2–13 days — proven ones as Easy, the rest as Good — so
  a lucky pass is caught by ordinary reviews. Languages stop after two failed
  units in a row; certs sample every unit (their units are not a ladder), capped
  at 60 questions. Placement never counts as study and can be retaken.
- **Trials**: certs draw `mcq`/`multi`/`order` items by largest-remainder
  apportionment of the official domain weights; quick (25–30 questions) or
  full-length (90; 100 for CC). Languages draw 20 typed items from what has been
  met. Timed; overtime fails; no feedback until the end. A wrong answer on a
  studied item sends it back to the queue; blanks and unseen items change nothing.
- **Readiness** (certs): all four of — every item met; memory ≥ 85%; last three
  trials ≥ 85%; a full-length mock passed.

### "Harder than the exam", concretely

The real Security+ pass mark is 750 on a 100–900 scale; Network+ 720; CC
700/1000. Here: 85% on scenario questions written to turn on near-neighbour
distinctions, with every domain's advanced part (about 600 extra items for
Security+, 600 for Network+, 350 for CC) authored against the blueprint topic
list and then independently re-solved by a second reviewer. No real exam items
are used. This raises the odds; it cannot guarantee a pass.

## The sect (colony sim)

- **Time**: one tick = one sim hour; 24-hour days; four 12-day seasons. The page
  requests hours as real time passes (pause / 1× / 2× / 3×; 4, 2 or 1 real
  seconds per hour). Time stops while a wanderer or merchant waits at the gate.
- **Pawns**: food, rest, joy (decay hourly), mood (drifts toward 50 + thoughts +
  traits + need penalties), health, six skills (0–20, with passion 0–2 scaling
  learning), two traits from fourteen, a spirit root (qi multiplier), a realm.
  Each hour a pawn recovers, sleeps, relaxes, or takes the best open job by
  priority (ties go to whatever the sect is shortest of, then to skill).
- **Jobs**: build, farm, cut wood, quarry, forage, brew pills, research, train,
  meditate.
- **Mood**: low mood risks a "qi deviation" (half a day of not working); high
  mood can inspire (+50% work for a day).
- **Rooms** (11, levels to 5; wood/stone, spirit stones from level 3; real build
  hours): Main Hall (caps other rooms' level, sect capacity), Dormitory, Rice
  Terraces, Storehouse, Scripture Pavilion, Meditation Chamber, Alchemy Hall,
  Training Grounds, Ward Formation, Spirit Vein, Trade Post.
- **Research**: eight techniques, advanced by scholars in the pavilion and by
  study insight.
- **Cultivation**: 8 realms × 4 stages. Minor stages just happen; a great realm
  is a gamble (55% + scholarship, +25% with a pill) and failure injures.
- **Storyteller** (Gentle Rain / Turning Seasons / Heaven's Trial): one roll
  each dawn. Wanderers, merchants, herb blooms, meteors, visiting elders,
  harvests, sickness, blight, cold snaps, and — after a grace period and with a
  minimum gap — beast tides and raids whose strength scales with wealth,
  headcount and age. Outcomes run from a clean win to being overrun; disciples
  can die on the two harder settings; the Sect Master cannot.
- **Away**: quiet mode at one sim hour per 30 real minutes, capped at 48 hours:
  work and needs only, no events, no starvation damage, no deaths.

### Where study touches the sect

1. A correct answer: +1 qi for the Sect Master (+1 more if typed) and +1 insight
   (spent on the current research).
2. A finished session: every disciple gets a "the Master lectured" mood lift for
   a day; the study streak advances (two automatic rest days, refilled weekly;
   seclusion freezes everything).
3. A passed trial: every disciple gains 15% of a stage of qi and a mood lift.

Balance was checked by a scripted player over 150 sim days on each storyteller,
with and without study: no starvation spirals; raids hurt but are survivable;
study speeds the Master and research and leaves the rest of the sect unchanged.
The numbers are starting values, tuned against that script, not against people.

## Persistence and safety

Atomic, fsynced writes; a daily `.bak`; a damaged file is moved aside, never
overwritten. Loaded and imported state is coerced to known shapes; the colony
blob is additionally test-driven (26 quiet hours plus a render) and discarded if
it fails, keeping study progress. `colony.view()` casts every number; the UI
escapes every string.

## Art and visual design

Original vector art generated in `art.js`: one mountain scene in which rooms are
marked-out plots until built, gain tiers as they level, show scaffolding while
under construction, and have disciples standing where they are working; a night
palette for dark mode; generated portraits with moods; a guide elder who reacts
to answers. Controls are tactile (solid colour, pressable edge), colour is bound
to meaning, bright faces carry dark text, and motion is removed under
`prefers-reduced-motion`. See `docs/research/notes/ui_inspiration.md`.

## Decisions made on the builder's call

- Security+ targets SY0-801 (launched 17 Nov 2026).
- No accounts; optional single token (`SECT_ACADEMY_TOKEN`).
- The old economy (spirit-stone income from study, quests, missions, recruit
  tokens) was dropped entirely rather than ported.
- Disciples can die on the default storyteller. "Gentle Rain" has no raids.
- A2 was added (the owner said "fill out"); B1 was not.

## Left for later

- A human native-speaker pass on the language courses and a certified
  instructor's pass on the cert courses.
- Performance-based (simulation) exam items beyond ordering and choose-N.
- More colony depth: relationships, individual equipment, a tile map, caravans
  you send out, more research.
- Reminders, and per-learner FSRS weight optimisation.
