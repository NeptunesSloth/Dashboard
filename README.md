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

**Courses** (about 8,900 items, all original, each independently re-checked)

| Course | Size | Notes |
|---|---|---|
| French A1, A2, B1 | 20 + 12 + 12 units | From zero to intermediate; typed recall and dictation |
| French Conversations | 8 units, 56 dialogues | Rehearsed exchanges, A1 to B1: you speak one side |
| Spanish A1, A2, B1 | 20 + 12 + 12 units | Spain Spanish, Latin American variants accepted |
| Spanish Conversations | 8 units, 56 dialogues | Rehearsed exchanges, A1 to B1: you speak one side |
| Mandarin Chinese A1 | 18 units, 352 items | Pinyin and tones first; 122 characters; simplified script |
| Japanese A1 | 18 units, 550 items | All hiragana and katakana, 40 kanji, polite style |
| Korean A1 | 18 units, 391 items | Hangul first, then polite speech; Revised Romanization |
| CompTIA Security+ (SY0-801) | 25 units | Every exam domain, plus exam-hard practice |
| CompTIA Network+ (N10-009) | 22 units | Every exam domain, heavy on subnetting and troubleshooting |
| ISC2 Certified in Cybersecurity | 15 units | Sept 2026 outline |
| CompTIA A+ Core 1 (220-1201) | 26 units, 654 items | Hardware, networking, mobile, cloud, troubleshooting |
| CompTIA A+ Core 2 (220-1202) | 26 units, 712 items | Operating systems, security, software troubleshooting, procedures |
| CompTIA CySA+ (CS0-004) | 27 units, 670 items | Analyst practice built on real-looking logs and tool output |
| Cisco CCNA (200-301 v2.0, from 3 Feb 2027) | 43 units, 920 items | v2.0 domains; configuration and verification; subnetting and routing worked; topics v2.0 dropped kept as background units outside the mocks |

**Studying**

- A **placement test** when you start a course finds your level and skips what
  you already know (skipped items come back as reviews, so a lucky pass is caught).
- A **daily session** is scheduled for you by spaced repetition (FSRS-6): what
  is due for review first, then a ration of new items.
- **Chinese, Japanese and Korean** start with the writing system itself. You can
  answer in the script or its romanisation; pinyin takes tone marks or numbers
  (`ni3 hao3`), and a wrong tone is wrong.
- Exercises get harder as you remember more: recognise, recall, type from
  memory, build a sentence from word tiles, type from audio. Certification
  items include single-answer, choose-two and put-in-order questions.
- **Conversations**: the app speaks the other person's lines; you answer from
  an English cue, first by arranging the words and later from memory, and are
  told to say every line aloud. Several natural answers are accepted.
- **Best-answer questions** (300+): four options that are all reasonable, and
  you must pick the BEST, the FIRST or the MOST effective, as on the real exams.
  Afterwards every option gets its own reason.
- **Mistakes log**: anything you get wrong, in a session or a trial, stays on a
  list until you answer it right, and one tap starts a session of just those.
- **Listening practice** (languages): hear a word or phrase you already know,
  and type it.
- **Drills** (certifications): ten freshly generated subnetting or port
  questions at a time, with the working shown.
- **Trials** are timed mock exams drawn across the official domains by their
  exam weights. They are deliberately harder than the real thing: the questions
  are scenario-based and the pass mark is 85%. Each cert course has a
  full-length mock and a four-point "ready for the real exam" checklist.
  You can flag questions for review before submitting, and the trials page
  shows which exam domains have cost you the most marks lately.

**The sect** (the game)

- Disciples have food, rest, joy, mood, health, six skills with passions, two
  traits, and a cultivation realm. You set their **work priorities**; they
  decide hour by hour what to do.
- You gather rice, wood, stone and herbs, **build and raise eleven rooms**,
  **research** eight techniques, brew pills, and take in wanderers.
- A **storyteller** sends events and waits for your decision: merchants,
  windfalls, sickness, cold snaps, and threats you see coming and can fight at
  the gate, sit out behind the wards, or buy off. Pick a gentle, balanced or
  harsh one. The world eases off a sect that has just been beaten.
- **The cultivation world**: disciples rise from Outer to Inner to Core
  disciple to Elder, and rank decides which **manuals** (Yellow to Heaven
  grade) they may study. A great-realm **breakthrough** is yours to order, with
  the odds laid out; from Core Formation up it is a **heavenly tribulation**.
  Three **rival sects** hold opinions of you. Arrogant young masters block the
  road (slap his face and his elder comes for revenge), auctions and **secret
  realms** open, the **Hundred Sects Tournament** comes every autumn, a
  crippled genius with a plain black ring asks for shelter, and a stranger
  offers a forbidden sutra. Fame, treasures and a guardian spirit beast follow.
- **It pushes back.** Rice is tight on the balanced and harsh storytellers,
  winter burns firewood, and a sect that is outmatched takes real wounds and
  can lose people. Idle play fails; careful play survives.
- **Disciples have each other.** Those who work side by side become friends,
  sworn siblings or rivals. Friends guard a breakthrough and grieve a death;
  rivals envy success, sour the mood and sometimes come to blows.
- **Depth you can read.** Every spirit root has one of five elements: the
  season favours one and presses on another, and a manual of your own element
  is half again as strong. Each disciple can carry one **artifact** (won, dug
  up or forged; rivals notice who gets the good sword). You may take a few
  **direct disciples**, who stop labouring and cultivate a quarter faster but
  expect a bed and some ease. A ledger on each disciple's page shows exactly
  what multiplies their cultivation speed.
- **The long road.** Masters take personal disciples who avenge them; sworn
  siblings become dao companions who take blows for each other; grief and
  failed tribulations leave heart demons to be faced. The sect swears up to
  three precepts and pays for breaking them, elders offer counsel you can
  overrule at a cost, brawlers come before the punishment hall, and merit
  earned by work buys artifacts from the vault.
- **More to do**: named pills from rare herbs, a path (sword, body, formation)
  chosen at Foundation Establishment, twelve-day closed-door seclusion, a
  lowland lord to please or defy, sworn alliances, three-stage sieges, the
  demonic path, a reincarnated ancient, succession when the founder ascends,
  tea-house rumours, verses carved for great days, and tomb-sweeping.
- **Breakthroughs are prepared, then chosen.** A second ledger grades the
  breakthrough from Flawed to Heaven-defying by what you arranged beforehand
  (mood, health, a pill, someone keeping vigil, the season, the chamber); the
  grade is a permanent bonus, and afterwards the disciple chooses one of three
  fates, each a trade, fixed so it cannot be rerolled.
- **Each great realm asks for one thing**, always with two ways to have it,
  and each disciple has a small **meridian chart** to spend stage points on.
- **Expeditions are yours to plan**: choose who goes and how boldly; halfway
  there they send word and ask what to do, and the choices depend on who went.
- **Rival cultivators have names** and advance by a rule you can read; you meet
  them at the tournament. A master's **trust** in a disciple grows through
  three stations, each an evening and a gift.
- **Standing orders**: keep N pills in stock, send the same party out again,
  and two saved sets of work priorities.
- **Also**: spirit beasts that choose a disciple, branch sects that pay
  tribute, a quiet karma tally, a map of the region, and a banner colour and
  motto of your own.
- **Things to aim at**: an elder's ten-step guided opening, a festival each
  season, promises to keep by a deadline with a reward you choose, expeditions
  you send out, five untimed **Great Works**, and the sect's permanent annals.
- The sect **does not depend on studying**: everyone cultivates by meditating.
  Study is a second engine — each correct answer gives the Sect Master qi and
  the sect a point of research insight, a finished session lifts every
  disciple's mood for a day, and a passed trial gives everyone a surge of qi.
- While the app is closed the sect carries on quietly (no events, nobody
  starves or dies) for at most two sim days per real day.

**Reading**

- **Read** holds a shelf of your own books: import EPUB, PDF, plain text,
  Markdown or HTML. The text is pulled out in the browser (PDF through a
  vendored copy of Mozilla pdf.js, served by the app itself) and kept by the
  server beside the save file, so a phone and a PC share one shelf and each
  book opens where you left it. Pick the book's language on import.
- **Tap any word** of a Spanish book for its English meaning: an offline
  dictionary of about 85,000 Spanish words and 133,000 of their forms. It finds
  the dictionary form behind plurals, conjugations and pronouns attached to a
  verb (*cúrale* → *curar*, *dímelo* → *decir*), with or without the accents.
  Hear the word (normal or slow) if your device has a voice for the language;
  the card says plainly when it has none.
- **French** books too: about 85,000 French words and 337,000 of their forms.
  Elisions are split (*l'homme* → *homme*, *qu'il* → *il*), inverted verbs
  freed of their pronoun (*dit-il* → *dire*, *va-t-on* → *aller*), plurals and
  feminines taken back (*chevaux* → *cheval*, *heureuses* → *heureux*).
- **Korean** books too: about 33,000 Korean words and 321,000 conjugated
  forms. Particles come off (*학교에서* → *학교*, "에서: at / in"), endings
  are taken back to the dictionary form with the grammar named (*먹었어요* →
  *먹다*, "past polite"; *더워요* → *덥다*, ㅂ irregular), and every word is
  shown with its romanisation. Chinese and Japanese books can be read and
  heard; their lookup is coming.
- **Old text files** are read in their own encoding: UTF-8 first, else EUC-KR
  for a Korean book and windows-1252 for a French or Spanish one. A Project
  Gutenberg licence header and footer are taken off.
- **Dictionary**: search each language → English, or English → it by meaning
  (Korean also by romanisation: *hakgyo* finds 학교), and add your own entries.
- **My words**: "Save word" keeps a word with its meaning and the sentence you
  met it in. Saved words are a course of their own, *My words (Spanish)*,
  scheduled and graded like every other course and paying the same qi and
  insight (*My words (French)*, *My words (Korean)* the same way).
- The Spanish dictionary is Wiktionary data compiled by doozan/spanish_data;
  French and Korean are English Wiktionary via kaikki.org; all CC BY-SA 4.0
  (see `sect_academy/dict/<lang>/README.md`); pdf.js is Apache-2.0
  (`sect_academy/static/vendor/pdfjs/LICENSE`).

## Running it

| Setting | Default | What it does |
|---|---|---|
| `SECT_ACADEMY_FILE` | `./academy_state.json` | Where progress and the sect are saved |
| `SECT_ACADEMY_HOST` | `127.0.0.1` | Bind address |
| `SECT_ACADEMY_PORT` | `8200` | Port |
| `SECT_ACADEMY_TOKEN` | unset | If set, every API call needs this token (the page asks for it once). Set it before binding to anything but localhost. |

- **Books** are kept in `<save file>.books/` (one `.txt` and one small `.json`
  per book; at most 200 books and 64 MB of text). They are not part of the
  backup download: keep that folder if you want your shelf.
- **Backups:** Progress → Download backup. A damaged save file is never
  overwritten; it is moved aside and yesterday's automatic backup is restored.
- **Phone:** open it in the phone's browser and "Add to Home Screen". (The
  server must be reachable from the phone, so bind it to your LAN address and
  set a token.)
- **Audio** uses the speech voices installed on your device. With no voice for
  a language, listening exercises become typing ones.
- **Docker:** `docker compose up -d` (progress is kept in a named volume).
- Run a single process: the app holds its state in memory.

To use it from another device on your network, start it with
`SECT_ACADEMY_HOST=0.0.0.0`, set `SECT_ACADEMY_TOKEN`, and list the name or
address you will type into the browser in `SECT_ACADEMY_HOSTS` (for example
`SECT_ACADEMY_HOSTS=192.168.1.20`). Requests for any other hostname are refused.

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
- **Conversation**: the dialogues rehearse real exchanges and make you produce
  the lines, which is the part most apps skip. They cannot listen to you or
  talk back freely. To converse comfortably with native speakers you also need
  hours of real speaking and listening; finish the B1 course, then find a
  tutor, a language exchange or a conversation group and use what you built.
- No app can guarantee an exam pass. The readiness checklist is deliberately
  strict so that ticking all four boxes means something.
- The Spanish dictionary is as good as its source. Where a common word and a
  name share a spelling, the compiled data sometimes kept only the name
  ("luz" appears as a given name); the card says so, and your own entry fixes it.
  French and Korean lookup has no word-frequency data, so a spelling with two
  readings is a guess (French *joue* shows "cheek" first, *jouer* under Also;
  Korean *삽니다* shows 사다 "buy" first, 살다 "live" under Also).
- One learner, one sect, one process.
