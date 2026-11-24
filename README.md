# Sect Academy

Learn every day, raise a sect.

Sect Academy is a self-hosted study app wrapped in a cultivation-world colony
sim. You study French, Spanish, or for an entry cyber-security certification in
short daily sessions; meanwhile your sect — a handful of disciples with needs,
moods, skills and jobs — farms, builds, researches, fends off raids and
cultivates on its own clock.

It runs **completely offline**: no account, no internet, no AI service, no
database. One Python process and one JSON file.

```bash
pip install -r requirements.txt
python -m sect_academy
# open http://127.0.0.1:8200
```

## What is in it

**Courses** (about 3,800 hand-checked items, all original)

| Course | Size | Notes |
|---|---|---|
| French A1, French A2 | 20 + 12 units | From zero to elementary; typed recall and dictation |
| Spanish A1, Spanish A2 | 20 + 12 units | Spain Spanish, Latin American variants accepted |
| CompTIA Security+ (SY0-801) | 25 units | Every exam domain, plus exam-hard practice |
| CompTIA Network+ (N10-009) | 22 units | Every exam domain, heavy on subnetting and troubleshooting |
| ISC2 Certified in Cybersecurity | 15 units | Sept 2026 outline |

**Studying**

- A **placement test** when you start a course finds your level and skips what
  you already know (skipped items come back as reviews, so a lucky pass is caught).
- A **daily session** is scheduled for you by spaced repetition (FSRS-6): what
  is due for review first, then a ration of new items.
- Exercises get harder as you remember more: recognise, recall, type from
  memory, type from audio. Certification items include single-answer,
  choose-two and put-in-order questions.
- **Trials** are timed mock exams drawn across the official domains by their
  exam weights. They are deliberately harder than the real thing: the questions
  are scenario-based and the pass mark is 85%. Each cert course has a
  full-length mock and a four-point "ready for the real exam" checklist.

**The sect** (the game)

- Disciples have food, rest, joy, mood, health, six skills with passions, two
  traits, and a cultivation realm. You set their **work priorities**; they
  decide hour by hour what to do.
- You gather rice, wood, stone and herbs, **build and raise eleven rooms**,
  **research** eight techniques, brew pills, and take in wanderers.
- A **storyteller** sends events: merchants, windfalls, sickness, cold snaps,
  beast tides and raids that scale with your wealth. Pick a gentle, balanced or
  harsh one.
- The sect **does not depend on studying**: everyone cultivates by meditating.
  Study is a second engine — each correct answer gives the Sect Master qi and
  the sect a point of research insight, a finished session lifts every
  disciple's mood for a day, and a passed trial gives everyone a surge of qi.
- While the app is closed the sect carries on quietly (no events, nobody
  starves or dies) for at most two sim days per real day.

## Running it

| Setting | Default | What it does |
|---|---|---|
| `SECT_ACADEMY_FILE` | `./academy_state.json` | Where progress and the sect are saved |
| `SECT_ACADEMY_HOST` | `127.0.0.1` | Bind address |
| `SECT_ACADEMY_PORT` | `8200` | Port |
| `SECT_ACADEMY_TOKEN` | unset | If set, every API call needs this token (the page asks for it once). Set it before binding to anything but localhost. |

- **Backups:** Progress → Download backup. A damaged save file is never
  overwritten; it is moved aside and yesterday's automatic backup is restored.
- **Phone:** open it in the phone's browser and "Add to Home Screen". (The
  server must be reachable from the phone, so bind it to your LAN address and
  set a token.)
- **Audio** uses the speech voices installed on your device. With no voice for
  a language, listening exercises become typing ones.
- **Docker:** `docker compose up -d` (progress is kept in a named volume).
- Run a single process: the app holds its state in memory.

## Developing

```bash
python -m sect_academy.packs        # validate every course file
python -m pytest -q                 # tests
ruff check .                        # lint
python -m sect_academy & python tests/smoke_browser.py   # browser test, outside network blocked
```

- `docs/ACADEMY_CONTENT.md` — how to write or extend a course.
- `docs/superpowers/specs/2026-11-24-sect-academy-design.md` — the design and
  the reasons behind it.
- `docs/research/` — the research the design rests on.

## Honest limits

- The course content was written and then independently checked by AI models,
  not by a human teacher or a certified instructor. Treat it as a strong study
  aid, and for the certifications check anything surprising against the vendor's
  current objectives.
- No app can guarantee an exam pass. The readiness checklist is deliberately
  strict so that ticking all four boxes means something.
- One learner, one sect, one process.
