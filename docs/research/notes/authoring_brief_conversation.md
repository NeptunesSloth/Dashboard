# Authoring brief — conversation courses

The goal of these courses is that a learner can hold a real conversation with a
native speaker. Vocabulary drills do not get anyone there; rehearsed, varied
exchanges do. You are writing a course made only of `dialogue` items.

## Read first

1. `docs/ACADEMY_CONTENT.md` — schema, especially `dialogue`.
2. The same language's existing course files (named in your task), so the
   dialogues use what learners have been taught at each level and recycle it.

## How a dialogue is used

The app speaks each partner line aloud and shows it; the learner then has to
produce their own line from an English cue — first by arranging the words,
later by typing it from memory — and is told to say it aloud. So:

- Write what people **actually say**: contractions, fillers and reactions
  appropriate to the level ("Ah bon ?", "¡Qué bien!", "D'accord", "Vale"),
  natural register (tu/vous, tú/usted chosen to fit the scene and consistent).
- **Learner lines**: short (about 3-10 words), one idea each, and reusable in
  real life. `l1` is the cue: say what to express, including register hints
  where English hides them ("(to a stranger)"). Put every other natural way to
  say the same thing in `alt` — be generous here, because in a conversation
  several answers are right; never list something that means something else.
- **Partner lines** can be longer and a little above the learner's level, the
  way real speech is. Their `l1` is a faithful translation.
- 6-10 lines per dialogue, the learner speaking 3-5 times. Vary who opens.
- Each dialogue should rehearse **conversation moves**, not just topics:
  opening and closing, asking back ("Et toi ?"), asking someone to repeat or
  slow down, saying you did not understand, buying time, agreeing and
  disagreeing politely, changing the subject, reacting to news, making and
  declining invitations, apologising, thanking, clarifying a misunderstanding.
- Across a unit, reuse key phrases in different situations so they stick.
- `title` is a short English label; `scene` is one or two English sentences
  setting the situation and who the learner is.
- Unit `notes` (100-180 words): the conversation strategies of the unit and
  the handful of survival phrases to lean on. `goal`: a CEFR-style "I can …".
- The language must be correct, natural and current, with correct accents and
  punctuation conventions. Item ids unique across the repository (prefix in
  your task). Quote YAML strings that need it.

## Before you report

1. `cd /home/user/Dashboard && python -m sect_academy.packs <your file>` clean.
2. Read every dialogue aloud in your head as both speakers: would a native
   speaker say exactly this? Fix anything stiff or textbook-ish.
3. For each learner line, ask what else a learner might reasonably type for
   that cue and make sure it is in `alt` (or sharpen the cue).

Report: unit titles with dialogue counts, and anything you were unsure about.
