# Authoring brief — an A1 course in Chinese, Japanese or Korean

You are writing a complete beginner (CEFR A1 / HSK 1 / JLPT N5-start / TOPIK I
start) course for an offline self-study app, in one YAML file. The learner knows
no characters at all when they begin.

## Read first

1. `docs/ACADEMY_CONTENT.md` in full: the schema, and especially the last
   section, "Languages not written in the Latin alphabet" (`rom`, `glyph`, how
   typed answers are graded, how word tiles are cut).
2. `docs/research/notes/authoring_brief_language.md`: the general rules for a
   language course (unit shape, notes, item mix, quality bar).
3. `sect_academy/packs/french_a1.yaml`: skim the first three units as the model
   for unit size, notes and tone.

## Shape of the course

- 16 to 18 units, about 300 items in total.
- **The writing system comes first** and keeps coming: the opening units teach
  it with `glyph` items, and later units each add a few more glyphs alongside
  vocabulary. A unit's notes explain what the learner is looking at.
- Then the A1 ground: greetings and politeness, introducing yourself, numbers,
  time and dates, family, food and drink, ordering and shopping, places and
  directions, daily routine, likes and dislikes, simple past or completed
  action as the language handles it, asking questions, and the survival
  phrases (I don't understand, please say it again, slowly please).
- Item mix after the script units: mostly `vocab` (each with `ex` and `ex_l1`
  where it helps) and `phrase`, some `cloze`, and **one short `dialogue` per
  unit from about unit 5 on** (6-8 lines, learner speaks 3-4 times).
- Every `vocab`, `phrase` and dialogue line has `rom`. Every `glyph` has `rom`.

## Rules that matter for these languages

- The language must be correct, natural and current: what a teacher would
  actually teach a beginner. Polite, neutral register throughout.
- Romanisation must be exact and consistent with the standard named in your
  task. It is graded strictly, so a wrong tone mark or vowel teaches an error.
- `l1` cues must lead to one answer. Where English hides a distinction the
  language makes (formal/informal, counters, particles), say so in the cue.
- `alt` holds the other correct ways to write or say the same thing.
- Unit notes (120-250 words) teach: the sound system and script in the early
  units; then grammar points with small tables. Explain, do not just list.
- Item ids are unique across the repository and start with the unit id.
- Quote every YAML string that contains a colon, a question mark at the start,
  or non-Latin text if in doubt.

## Before you report

1. `cd /home/user/Dashboard && python -m sect_academy.packs <your file>` clean,
   then `python -m sect_academy.packs` to confirm no id collisions.
2. A throwaway script (not saved in the repo) confirming: every vocab, phrase
   and dialogue line has `rom`; no duplicate `l2` within a unit; no duplicate
   `l1` within a unit; every glyph `l2` is a single character or a single
   syllable block.
3. Read every item once more as a native-speaking teacher would.

Report: unit titles with counts by type, the glyphs taught, and anything you
were unsure of.
