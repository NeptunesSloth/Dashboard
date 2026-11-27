# Authoring brief — "all of these are right; which is BEST?" questions

Certification exams' hardest items give four answers that are all true or all
reasonable, and ask for the BEST, MOST effective, FIRST or LEAST one. You are
writing a bank of exactly those for one course.

## Read first

1. `docs/ACADEMY_CONTENT.md` — schema, especially the **best-answer `mcq`**
   (`best: true`, `whys`).
2. `docs/research/notes/cert_blueprints.md` — the exam's domains and objectives.
3. Skim the course's existing files (named in your task) so you do not repeat a
   scenario already there.

## What to write

One part file (path in your task): `part_of: <course id>` and one unit per exam
domain (ids and counts in your task). Every item is an `mcq` with `best: true`
and `whys`. Edit only your file.

## What makes a good one

- **All four choices are things a competent professional might genuinely do.**
  No wrong facts, no throwaways. If a choice is simply false, it is not a
  best-answer question.
- The stem is a short scenario that supplies the **deciding constraint**: a
  budget, a deadline, an order of operations, a stated priority ("the business
  cannot tolerate downtime"), the specific threat, a regulatory duty, who owns
  the decision. The best answer must follow from that constraint, so that an
  expert would not call it a matter of taste.
- Use the exam's qualifier in capitals: BEST, MOST effective, MOST likely,
  FIRST, LEAST. Mix them. FIRST questions should test real sequence logic
  (contain before eradicate; verify before change; life safety before data).
- Typical axes: root cause vs symptom; preventive vs detective; technical vs
  administrative when the question asks for one; least privilege vs
  convenience; cheapest control that meets the requirement vs gold-plating;
  compensating control when the ideal one is impossible; scope (fixes one host
  vs fixes the class); the next step in a defined process.
- `why`: one or two sentences on why the key is best.
- `whys`: one sentence **per choice, in the order written**, each saying why it
  is the best or exactly why it is weaker than the best here ("valid, but
  detective only — it reports the breach after the fact"). Never just "wrong".
- Vary the position of the key evenly across 0-3. Original scenarios only; no
  real exam items. Facts must be right; if unsure, leave the item out.
- Unit `notes` (100-180 words): how to attack best-answer questions in this
  domain — the constraints to look for and the usual traps. `goal`: "I can …".

## Before you report

1. `cd /home/user/Dashboard && python -m sect_academy.packs <your file>` clean.
2. Adversarial pass: for each item, argue for the strongest distractor as hard
   as you can. If you can make an honest expert case that it beats the key, add
   the missing constraint to the stem or delete the item.
3. A throwaway script (not saved) confirming even key spread and that every
   item has `best: true` and four `whys`.

Report: units with counts, and any item you were not fully sure of.
