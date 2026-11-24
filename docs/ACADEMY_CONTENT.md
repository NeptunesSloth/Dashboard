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

- `multi` is the exam's "choose TWO / choose THREE": 5-6 distinct choices,
  `answers` lists the 2-3 correct indices, and the stem must say how many to
  choose. It is graded all-or-nothing, so every listed answer must be
  unambiguously right and every other choice unambiguously wrong.
- `order` gives 3-6 `steps` **in the correct order** (the app shuffles them). Use
  it only where one order is defensible (a named process, a handshake, a
  troubleshooting method), never for lists of equally valid things.
- **Original questions only.** Write against the public exam objectives. Never
  copy real exam items or "brain dump" material.
