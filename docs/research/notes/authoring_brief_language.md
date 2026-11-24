# Authoring brief — language course units

You are writing units for a language course in an offline self-study app for an
English-speaking adult. Learners meet each item, then recognise it, then must
**type it from memory**, so every item has to be answerable from its English
prompt alone.

## Read first

1. `docs/ACADEMY_CONTENT.md` — the exact YAML schema (follow it precisely),
   including part files (`part_of`).
2. `docs/research/notes/language_learning_a1.md` — the researched syllabus
   inventory and teaching principles.
3. The existing course file(s) named in your task — read them fully so you do
   not repeat an item and so new units build on what is already taught.

## Rules for every unit

- 24-26 items per unit: mostly `vocab`, 4-6 `phrase` (whole useful sentences),
  6-8 `cloze` drilling the unit's grammar point.
- Nouns always with their article. Flag gender exceptions in `note`.
- `l1` (the English prompt) must be specific enough that a learner can produce
  `l2`: add a parenthetical hint where English is ambiguous — "(informal)",
  "(feminine)", "(to a group)", "(past, finished)". Put every other genuinely
  correct answer in `alt`. Never put an answer in `alt` that the `l1` hint rules
  out.
- Within a unit, no two items share an `l1` or an `l2`. Across the whole
  course, do not repeat an `l2` that an earlier unit already teaches.
- Give most vocab an `ex` sentence with `ex_l1`, using only language from this
  or earlier units. Add `note` for what English speakers get wrong.
- `cloze`: exactly one `___`; a one-word answer (or a contraction); `l1`
  translates the whole sentence; `note` names the rule. Given the sentence plus
  its translation there must be exactly one defensible fill — otherwise add the
  alternates to `alt` or reword. The answer must not appear elsewhere in its own
  sentence. Cloze answers within a unit should be distinct (the app draws wrong
  options from sibling cloze answers).
- Unit `notes`: 100-180 words of clear teaching in the light Markdown the guide
  describes; a small conjugation table is welcome (include a header row). `goal`:
  a CEFR-style "I can …" statement.
- The language must be correct, natural and standard, with correct accents and
  punctuation conventions. Check every gender, conjugation and agreement twice.
- Item ids: unique across the whole repository; use the prefix given in your
  task (lowercase ascii and hyphens).
- Quote YAML strings that contain colons, `#`, or leading special characters.

## Before you report

1. Validate until clean: `cd /home/user/Dashboard && python -m sect_academy.packs <your file name>`
2. Run a throwaway script (do not save it in the repo) confirming: no shared
   `l1`/`l2` within a unit; no `l2` duplicated from the existing course file(s);
   no cloze answer present elsewhere in its sentence.
3. Proofread the whole file once more as a strict native-speaker teacher and fix
   every error.

Report: unit titles with counts, and anything you were unsure about.
