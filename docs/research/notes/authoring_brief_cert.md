# Authoring brief — advanced certification parts

You are extending one domain of a certification course in an offline self-study
app. A learner who finishes the course must be able to pass the real exam, so
the practice has to be **harder than the exam**, and the coverage of your domain
has to be **complete**.

## Read first

1. `docs/ACADEMY_CONTENT.md` — the exact YAML schema (follow it precisely),
   including part files (`part_of`), and the `multi` and `order` item types.
2. `docs/research/notes/cert_blueprints.md` — the researched blueprint: the
   objective list and topic lists for your exam and domain. This is your syllabus.
3. The existing base course file named in your task — read every unit of YOUR
   domain so you do not repeat an item, and so you can see what is missing.

## What to write

One part file (path given in your task) containing `part_of: <course id>` and
the units named in your task. Do not touch any other file.

- **Coverage unit(s)**: every objective and listed topic in your domain that the
  base course does not already teach gets a `concept` (and, where it is testable,
  an `mcq`). Work through the blueprint's topic list for your domain line by
  line. When you finish, every topic in the list must be traceable to at least
  one item in the base course or your part.
- **Exam-hard practice unit(s)**: scenario questions at a difficulty above the
  real exam.

Counts are given in your task. Hit them within ±10%.

## What "harder than the exam" means

- Stems are short scenarios (2-4 sentences) that require applying a concept, not
  recalling a definition. Include the kind of detail the exam uses: a log
  excerpt, a firewall rule list, a config snippet, a symptom list, a business
  constraint — written inline in the stem as plain text.
- The four choices come from the same family and are all plausible to someone
  who half-knows the topic (four attack types, four control types, four
  protocols). Never use a throwaway distractor.
- Use the exam's qualifiers — BEST, MOST likely, FIRST, LEAST — and make the
  question turn on the distinction between two near-neighbours (e.g. tokenization
  vs masking, RTO vs RPO, smishing vs vishing, SNMPv2c vs v3, STP vs loop guard).
- Include two-step reasoning: identify what is happening, then choose the
  response.
- `multi` items ("Choose TWO" / "Choose THREE" — say which in the stem): 5-6
  choices; every keyed answer unambiguously right, every other choice
  unambiguously wrong. These stand in for the exam's multiple-response items.
- `order` items stand in for performance-based questions: put a real process in
  order (an incident-response sequence, a handshake, a troubleshooting method,
  firewall rule evaluation, a change-management flow). Only where one order is
  defensible.

## Non-negotiable quality rules

- **Original questions only.** Write against the public objectives. Never
  reproduce real exam items or brain-dump material; paraphrase the objectives.
- **Facts must be right.** If you are not certain of a fact, leave the item out.
  Re-derive every number (ports, subnet maths, key sizes, formulas).
- Exactly ONE defensible best answer per `mcq`; the `answer` index (0-based)
  points at it. Vary the answer position evenly across 0-3.
- `why` explains why the key is right AND why the most tempting distractor is
  wrong, in one to three sentences.
- `concept.def` identifies the term without naming it, and must be
  distinguishable from every other concept in the course (the app uses other
  concepts' terms and definitions as wrong options).
- No "all/none of the above", no "both A and B" (choices are shuffled).
- Item ids: unique across the whole repository; use the prefix given in your
  task. Unit `notes`: 100-200 words of orientation in the light Markdown the
  guide describes. `goal`: one line "I can …".
- Quote YAML strings that contain colons, `#`, or leading special characters;
  quote numeric-looking choices so they stay strings.

## Before you report

1. Validate until clean: `cd /home/user/Dashboard && python -m sect_academy.packs <your file name>`
2. Run a throwaway script (do not save it in the repo) that confirms: answer
   indices are evenly spread; no concept term in your part duplicates a term in
   the base course; every `multi` stem says how many to choose.
3. Do one adversarial pass over every item as a senior instructor: solve each
   question from the stem alone before looking at the key. Fix or delete anything
   with two defensible answers, a wrong key, or a doubtful fact.

Report: units with item counts by type, the blueprint topics you covered, any
topic you could not cover and why, and any fact you were unsure of.
