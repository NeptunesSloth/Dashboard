# Sect Academy — content authoring guide

Courses are plain YAML "packs" in `sect_academy/packs/`. They are
curated, original, and work with no LLM and no network. Validate with:

```bash
python -m sect_academy.packs            # every pack
python -m sect_academy.packs path.yaml  # one pack
```

A pack that fails validation is skipped at load time (the app still boots).

## Pack header

```yaml
id: french-a1                 # lowercase, [a-z0-9_.-]
title: "French — A1 Foundations"
kind: language                # language | cert
blurb: "One line shown on the course card."
hall: tongues_west            # a short key grouping related courses (tongues_west, tongues_south, ward_hall)
language: French              # language packs only
lang: fr-FR                   # language packs only: BCP-47 tag used for speech
exam:                         # cert packs only
  name: CompTIA Security+
  code: SY0-701
  questions: 30               # length of the quick in-app trial (mock exam)
  minutes: 30
  pass_pct: 85                # in-app pass mark: deliberately above the real exam's
  full: {questions: 90, minutes: 90}   # optional full-length mock
  domains:                    # official blueprint; weights must sum to 100
    - {id: "1", title: General Security Concepts, weight: 12}
units: [...]
```

## Splitting a course across files

A large course can be written as several files. One file carries the header;
each *part* file has only:

```yaml
part_of: security-plus        # the id of the course this extends
units: [...]
```

Part units are appended to the course in filename order. A part must not repeat
a unit id or item id that exists anywhere else. Validate one file with
`python -m sect_academy.packs <file>.yaml` (the course it extends is loaded
automatically).

## Units

Units unlock in order. Each needs `id`, `title`, `goal` (a one-line can-do
statement), `notes` (the teaching text, shown before the unit's first items and in
the Library) and `items` (at least 4). Cert units also need `domain` (an
`exam.domains` id).

`notes` is light Markdown: paragraphs, `**bold**`, `*italic*`, `-` bullets,
`## headings`, and simple `| a | b |` tables. Keep them short (roughly 80–200
words): the item reviews do the teaching, the notes orient.

## Items

Every item needs a unique `id` (unique across **all** packs — prefix with the
pack, e.g. `fr-03-avoir`) and a `type`.

### Language packs

```yaml
- {id: fr-01-bonjour, type: vocab, l2: bonjour, l1: "hello / good morning",
   ex: "Bonjour, madame !", ex_l1: "Hello, ma'am!", note: "Used until early evening."}
- {id: fr-01-cava, type: phrase, l2: "Comment ça va ?", l1: "How are you? (informal)",
   alt: ["Ça va ?", "Comment vas-tu ?"]}
- {id: fr-03-c1, type: cloze, text: "Je ___ étudiant.", answer: suis,
   l1: "I am a student.", note: "être → je suis"}
```

```yaml
- id: frt-01-cafe
  type: dialogue
  title: "Ordering at a café"
  scene: "You are a customer. The waiter comes to your table."
  you: B                      # the learner's role
  lines:
    - {who: A, l2: "Bonjour ! Vous désirez ?", l1: "Hello! What would you like?"}
    - {who: B, l2: "Un café, s'il vous plaît.", l1: "A coffee, please.",
       alt: ["Je voudrais un café, s'il vous plaît."]}
    - {who: A, l2: "Autre chose ?", l1: "Anything else?"}
    - {who: B, l2: "Non merci, c'est tout.", l1: "No thanks, that's all.", alt: ["Non, merci."]}
```

- A `dialogue` is conversation practice: the app speaks the partner's lines and
  the learner must produce their own from the English cue — first by arranging
  the words, later by typing from memory. 4-12 lines; the learner (`you`) has
  at least two. Keep each learner line short (about 3-10 words) and natural;
  list every other natural way to say it in `alt`. The partner's lines can be
  longer and may use words the learner has only met passively.
- `l2` is the target-language answer the learner will eventually **type**; `alt`
  lists other answers that must be accepted. `l1` is the English prompt/meaning.
- Teach nouns **with their article** (`le livre`, `la mesa`) so gender is learned
  with the word.
- `l1` must be unambiguous enough that a learner prompted with it can produce
  `l2` (add a hint in parentheses: `"you (informal, singular)"`).
- Within a unit, no two items may share the same `l1` or the same `l2`.
- `cloze.text` has exactly one `___`; `l1` translates the whole sentence.
- Grading ignores case and edge punctuation; a missing accent is accepted with a
  correction shown, so always write the correctly accented form.

### Cert packs

```yaml
- {id: sy-1-cia, type: concept, term: "CIA triad",
   def: "Confidentiality, integrity and availability — the three core goals of security."}
- {id: sy-1-q01, type: mcq,
   q: "A hash of a downloaded file is compared with the vendor's published value. Which goal is being verified?",
   choices: [Confidentiality, Integrity, Availability, Non-repudiation],
   answer: 1,
   why: "Hash comparison detects modification, which is integrity."}
```

- `concept.def` must identify the term without naming it (the app asks
  "which term matches this definition?" and the reverse, using other concepts in
  the same pack as distractors).
- `mcq` has exactly 4 distinct choices, `answer` is the 0-based index of the one
  correct choice, and `why` explains why it is right (and ideally why the nearest
  distractor is wrong). Choices are shuffled at ask time, so never write "all of
  the above" / "both A and B".
```yaml
- {id: sy-1-m01, type: multi,
   q: "Which TWO of these are detective controls?",
   choices: [Door lock, Audit log review, Security guard patrol report, Firewall deny rule, Encryption at rest],
   answers: [1, 2],
   why: "Log review and patrol reports find events after the fact; the others prevent."}
- {id: sy-4-o01, type: order,
   q: "Put the steps of handling a suspected compromise in order.",
   steps: ["Confirm the event is an incident", "Contain the affected hosts", "Remove the cause", "Restore service", "Review lessons learned"],
   why: "You cannot contain what you have not identified, and recovery follows eradication."}
```

```yaml
- {id: sy-1-b01, type: mcq, best: true,
   q: "A team must stop staff reusing passwords across sites. Every option would help. Which is the BEST control?",
   choices: ["A yearly awareness e-mail", "A password manager issued to all staff", "A longer minimum password length", "A quarterly password change"],
   answer: 1,
   why: "A password manager removes the reason people reuse passwords.",
   whys: ["Raises awareness but changes little behaviour.", "Makes unique passwords effortless - the root cause.", "Stronger passwords are still reused.", "Forced rotation encourages predictable variations."]}
```

- A **best-answer** `mcq` (`best: true`) is the exam's hardest style: **every
  choice is correct or reasonable**, and the candidate must pick the BEST, MOST
  effective, or FIRST one. It needs `whys`: one sentence per choice, in the
  order the choices are written, saying why it is the best or exactly why it is
  weaker than the best. The stem must use the qualifier (BEST / MOST / FIRST /
  LEAST) and must give the deciding constraint (cost, time, order of operations,
  the specific risk) so the best answer is defensible, not a matter of taste.
  `whys` is welcome on ordinary `mcq` items too.
- `multi` is the exam's "choose TWO / choose THREE": 5-6 distinct choices,
  `answers` lists the 2-3 correct indices, and the stem must say how many to
  choose. It is graded all-or-nothing, so every listed answer must be
  unambiguously right and every other choice unambiguously wrong.
- `order` gives 3-6 `steps` **in the correct order** (the app shuffles them). Use
  it only where one order is defensible (a named process, a handshake, a
  troubleshooting method), never for lists of equally valid things.
- **Original questions only.** Write against the public exam objectives. Never
  copy real exam items or "brain dump" material.

## Languages not written in the Latin alphabet (Chinese, Japanese, Korean)

Three additions make these work with the same engine.

**`rom`** — an optional field on `vocab` and `phrase` items and on every line of
a `dialogue`: the romanisation of `l2` (pinyin with tone marks, Hepburn romaji,
Revised Romanization). It is shown under the script wherever the learner is
reading, and it is accepted as a typed answer.

```yaml
- {id: zh-01-nihao, type: phrase, l2: "你好", rom: "nǐ hǎo", l1: "hello"}
```

**`glyph`** — a new item type for learning a writing system: one character or
letter and how it is read. `l2` is the character, `rom` its reading, `l1` an
optional meaning or note. It is practised by choosing the reading, choosing the
character, then typing the reading.

```yaml
- {id: ja-01-a, type: glyph, l2: "あ", rom: "a"}
- {id: zh-02-ren, type: glyph, l2: "人", rom: "rén", l1: "person"}
```

**How typed answers are graded** when `l2` is in one of these scripts:

- The script itself or the romanisation is accepted; spaces never matter
  (`你好`, `nǐ hǎo`, `nǐhǎo`).
- Pinyin may use tone marks or tone numbers (`ni3 hao3`, `lv4` for `lǜ`).
- Pinyin typed with no tones at all is accepted on answers of four letters or
  more, flagged as a slip so the item returns sooner. A wrong tone is wrong.
- No typo is forgiven: one letter is usually a different word.
- Other accepted spellings go in `alt` as usual (for example a romaji variant).

**Word tiles**: text with spaces is split into words; Chinese or Japanese text
with no spaces is split into single characters. Write beginner Japanese in kana
with spaces between words (わたし は がくせい です) so the tiles are words.

For a `cloze`, `text` and `answer` are in the script; put the romanised answer
in `alt`.

An example sentence (`ex`) has its own romanisation field, **`ex_rom`**, shown
between the sentence and its translation `ex_l1`. Do not put romanisation inside
`ex_l1`.
