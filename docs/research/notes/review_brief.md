# Review brief — independent content check

You are checking course content you did **not** write. Assume there are
mistakes and hunt for them; fix real errors in place with minimal edits.

Read `docs/ACADEMY_CONTENT.md` for the schema. How items are used (see
`build_exercise`, `check`, `check_typed`, `_distractors` in
`sect_academy/engine.py`): `mcq`/`multi` choices and `order` steps are shuffled;
`multi` and `order` are graded all-or-nothing; for a `concept` the app shows the
definition and asks which term it is (and the reverse), using other concepts in
the same course as wrong options; for language items the learner sees `l1` and
must type `l2` or any `alt`, and for a cloze sees the sentence with `___` plus
its English `l1` and must type `answer` or an `alt`.

Work through every item of every file assigned to you, unit by unit. Do not
sample.

## Certification files

1. **Solve every `mcq`, `multi` and `order` yourself before looking at the key.**
   Any disagreement must be resolved by fixing the item. Exactly one best answer
   for `mcq`; for `multi` every keyed answer unambiguously right and every other
   choice unambiguously wrong, and the stem must say how many to choose; for
   `order` exactly one defensible order.
2. Facts: recompute every number (ports and transport, subnet maths, key sizes,
   risk and availability formulas, PoE wattages, timers), check protocol and
   standard names, and check the vendor's own vocabulary and the right exam
   version (see `docs/research/notes/cert_blueprints.md`).
3. `why` is accurate and consistent with the key.
4. Concepts: the definition is correct, does not name its own term, and cannot
   reasonably be matched to another concept's term **anywhere in the same
   course** (base file plus all its parts). Sharpen or delete near-duplicates.
5. Unit `notes` are factually right.

## Language files

1. Correctness: spelling, accents, gender and article, conjugation, agreement,
   elision, punctuation conventions, natural usage; `ex`/`ex_l1` correct and
   matching.
2. Answerability: given only `l1`, is `l2` what a competent learner would
   produce? Add genuine alternates to `alt` or sharpen the hint; remove any
   `alt` the hint rules out.
3. Clozes: exactly one correct fill given sentence plus translation (else add
   `alt` or reword); the answer is not given away in the sentence; the `note`
   states the right rule.
4. Notes are right about grammar and pronunciation.

## Rules

- Keep ids stable. Do not restructure, reorder, or add or remove units. Delete
  an item only if it cannot be made unambiguous (keep each unit at 4+ items).
- Do not rewrite matters of taste.
- After editing: `cd /home/user/Dashboard && python -m sect_academy.packs` must
  be clean, and `python -m pytest tests/test_engine.py -q` must pass.

Report every change (item id, what was wrong, the fix), grouped by file; what
you judged doubtful but left; and an honest statement of how thoroughly each
file was covered.
