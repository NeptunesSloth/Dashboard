# What the big language apps do better, and what Sect Academy can copy offline

Research date: 24 Nov 2026. Scope: the French/Spanish A1-A2 side of the app only.
Constraint for every recommendation: no network, no AI/LLM, no recorded audio
(browser `speechSynthesis` only).

How to read this file:

- **[S]** = sourced in this run (link in "Sources"). Most "sources" are vendor
  pages or affiliate review blogs; where a number comes from the company itself
  it says so.
- **[B]** = my background knowledge of the product, **not re-verified in this
  run**. Treat as probably right, check before quoting.
- **[I]** = my inference or design proposal.

## Where the app stands today (read from the repo, not assumed)

- Formats (`engine._mode_for`): `choose_l1` (rep 0) → `choose_l2` (rep 1) →
  `type_l2`, with `listen` (dictation) on every third rep from rep 3;
  cloze: `cloze_choose` (rep 0) → `cloze_type`.
- Data per language item: `l2`, `l1`, `alt`, `note`; every vocab item has an
  example sentence `ex` + `ex_l1` (787 of them across the five French/Spanish
  files I counted; `spanish_a1_x.yaml` not counted); 268 phrase items and 394
  cloze items in the same five files. No part-of-speech, gender or tag fields.
- Already present, so **not** recommended below: accent key bar, lenient
  accent/typo grading (Hard), "Practice weak items" (lowest-retrievability
  items, never reschedules), same-session re-ask of misses, streak with two
  automatic rest days, adaptive per-unit placement, TTS at rate 0.9.
- Missing: any sentence-level production other than typing a whole phrase, any
  listening task other than full dictation, a record of *what* was answered
  wrong, leech handling (the card stores `lapses` but nothing uses it),
  connected text (dialogues/stories), verb paradigms, any speaking prompt.

## Part 1 — What each product is good at

### Duolingo

- **Known for**: a linear path of very short lessons; a wide exercise mix (tap
  word-bank tiles to build a sentence, match pairs, listen-and-tap, type,
  speak) [B]; Stories (short character dialogues with comprehension checks —
  identifying events, sequencing, inferring a word from context) [S]; a
  Practice Hub with a dedicated **Mistakes** review built from recent errors
  [S]; an adaptive placement test, now moving from all-or-nothing scoring to
  partial credit [S]; "Birdbrain", a model that estimates exercise difficulty
  and learner ability, where exercise *type* is one input to difficulty [S];
  the streak.
- **Evidence**: Jiang et al. (Foreign Language Annals 54(4)): 225 US adults
  using only Duolingo for Spanish/French reached ACTFL Intermediate Low reading
  and Novice High listening, comparable to fourth-semester university students
  [S]. Authors are Duolingo-affiliated; reading and listening only; no
  independent replication found. One independent study found classroom learners
  improved listening more than app users [S, search summary only]. Streak:
  Duolingo's blog reports that separating the daily goal from the streak gave
  +3.3% day-14 retention, +1% daily active learners and +10.5% learners on a
  streak; a streak animation gave +1.7% day-7 retention for new learners (all
  relative, all company-reported) [S]. From this repo's earlier notes: its
  spaced-repetition model raised daily engagement 12% (Settles & Meeder 2016).
- **Complaints**: the 2025-26 switch from hearts to "energy", which drains on
  right answers too, drew petitions and a negative majority in an Android
  Authority reader poll (self-selected) [S]; course rewrites that broke
  learners' progress [S]; word-bank tiles let you recognise instead of recall —
  users install browser add-ons to force typing [S, anecdotal]; I found **no
  published A/B number for Streak Freeze** (a "21% churn reduction" figure
  circulates with no primary source — do not quote it) [S].
- **Could not verify**: any study isolating Stories; any study comparing
  word-bank and typing.

### Babbel

- **Known for**: lessons built around a **dialogue** you first listen to and
  then take one speaker's part in; short grammar/pronunciation/culture tips
  inline; a review manager that lets the learner pick the mode — flashcards,
  listening, speaking or writing [S].
- **Evidence**: Loewen, Isbell & Sporn (2020, Foreign Language Annals), 12
  weeks of Spanish at Michigan State: 54 of ~85 finished; 59% improved oral
  proficiency by at least one ACTFL sublevel, 69% of those with ≥6 hours and
  75% with ≥15 hours; nearly all improved grammar and vocabulary. No control
  group; run in collaboration with Babbel; 36% dropped out [S].
- **Complaints**: thin content above B1; some want more grammar review;
  billing/refund disputes [S].

### Busuu

- **Known for**: CEFR-labelled path; **community corrections** of written and
  spoken exercises by native speakers [S].
- **Evidence**: Vesselinov & Grego (2016), two months of beginner Spanish:
  Busuu's headline is "22 hours = one college semester"; 84% improved on the
  written test. Company-published; its own pages disagree on sample size (196
  vs 144) [S]. A 2021 follow-up included live lessons.
- **Complaints**: corrections are slow and sometimes wrong; little
  pronunciation practice; auto-renewal complaints [S].
- **Relevance here**: the headline feature needs a network of people — not
  copyable. The transferable idea is *free production that gets checked*, which
  offline can only be approximated with model answers and self-comparison.

### Anki (AnkiDroid / AnkiMobile)

- **Known for**: total control — card editing, tags, filtered decks, FSRS, and
  **leeches**: a card that lapses 8 times (default) is tagged and suspended,
  with repeat warnings every half-threshold (12, 16…); lapses only count on
  graduated cards; community guides suggest thresholds of 4-8 [S].
- **Evidence**: FSRS benchmark work is covered in `spaced_repetition.md`. The
  manual's advice for a leech is to edit/reformulate, delete, or wait [B — the
  page loaded only as a heading in this run]. No FSRS-specific leech rule
  exists; the lapse counter is still the trigger [S].
- **Complaints**: steep setup, plain UI, review backlog guilt [B].

### Clozemaster

- **Known for**: thousands of **cloze sentences**, each playable as multiple
  choice or typed; separate Play (new) and Review queues; a listening mode (Pro)
  [S]. Sentences are ordered by the frequency of the missing word and come from
  the Tatoeba corpus [B — a reviewer confirms "Clozemaster doesn't write its
  own sentences", the Tatoeba attribution itself did not surface].
- **Evidence**: none beyond reviews. Fixed intervals 1/10/30/180 days [S].
- **Complaints**: unsuitable for true beginners; unvetted sentences contain
  errors; "shouldn't be used alone"; fill-the-blank gets monotonous [S].

### Lingvist

- **Known for**: placement on first use, then adaptive vocabulary in frequency
  order [S]; every card is a sentence with a typed gap [B]; shows time since a
  word was last seen [S].
- **Complaints**: little context beyond the one sentence; repetitive; "teaches
  in a vacuum" [S].

### Kwiziq (French, Spanish grammar)

- **Known for**: a ~52-question placement test that returns a CEFR level; each
  "kwiz" is **built from the previous kwiz's wrong answers**; a **Brainmap** —
  a colour-coded map of grammar topics per CEFR level showing which are solid
  [S].
- **Complaints**: grammar only (level estimate ignores listening/speaking);
  free tier capped at 10 kwizzes a month; beginners "easily get lost" [S].

### Pimsleur and Language Transfer (audio-first)

- **Pimsleur — known for**: *graduated interval recall* inside one lesson
  (recall after about a minute, then 5, 15…) and the *principle of
  anticipation* — you are prompted and must produce the phrase aloud **before**
  hearing the answer [S]. Backchaining long words from the last syllable [B].
- **Evidence**: no efficacy study surfaced; one academic critique (Choe 2016)
  credits the recall design and criticises other parts [S, summary only].
- **Complaints**: tiny vocabulary, almost no reading or writing [S].
- **Language Transfer — known for**: the "Thinking Method": pause, *construct*
  a new sentence from pieces you already hold instead of memorising phrases
  [S]; heavy use of English cognate patterns [B].
- **Complaints**: no self-assessment, no review system, audio only so nothing
  sticks visually [S].

### Glossika

- **Known for**: mass sentence repetition — hear a sentence, say or type it;
  25-100 "reps" a day; typing and dictation modes [S].
- **Complaints**: boring ("going through the motions"), translation errors,
  expensive [S].

### LingQ and Dreaming Spanish (input-first)

- **LingQ — known for**: reading/listening to imported text with every word
  marked new/learning/known; a **known-words count**; sentence-by-sentence
  mode for hard passages [S].
- **Complaints**: learning curve; the known-word number becomes the goal;
  "remember words but not how to make a sentence" [S].
- **Dreaming Spanish — known for**: graded comprehensible-input video and an
  **hours-based roadmap** (levels at 50/150/300/600/1,000/1,500 hours) [S].
- **Complaints**: long silent period (speak after ~600 hours); it is a content
  library, not a learning system; critics prefer mixing input with study [S].
- **Relevance here**: the app has zero connected text. Graded input cannot be
  generated, but short authored dialogues can be.

### Memrise, Drops, Speakly, Mango

- **Memrise**: native-speaker video clips [B]; dropped community courses from
  the app in March 2024, to user anger, and brought ~800 back as word lists in
  2026 [S]. Lesson: learners value being able to add their own material.
- **Drops**: five-minute visual vocabulary sessions with swipe/match games [B];
  criticised as noun-heavy — "you won't learn" a noun's gender when the article
  doesn't show it; added limited grammar lessons in March 2026 [S].
- **Speakly**: teaches "the 4,000 most statistically relevant words in order of
  importance" [S, app-store listing]; stability complaints [S].
- **Mango**: colour-matches chunks of the L2 sentence to the English and gives
  a literal word-for-word gloss [B — **not confirmed in this run**]; reviewers
  call it repetitive and light on grammar explanation [S].

## Part 2 — Ranked improvements for this app

Ranking is my judgement [I] of (learning value × fit with existing data) ÷
effort. "Competitor" lines carry the [S]/[B] tags from Part 1; everything under
"Build" and "Impact" is [I].

### 1. Sentence building from tiles (word order) — effort S/M, impact high

- **Competitor**: Duolingo's word bank [B].
- **Why**: the app jumps from picking one of four meanings straight to typing a
  whole phrase. Tiles are a cheap middle rung that practises *word order*
  (ne…pas, adjective position, object pronouns, ¿…?) without spelling load.
- **Build**: new mode `build` for `phrase` items and for vocab `ex` sentences.
  Server tokenises `l2` on spaces (keep `l'`, `qu'`, `-vous` attached; strip
  edge punctuation), adds 2-3 distractor tokens from sibling items in the unit,
  shuffles. Client sends the ordered token list; server joins and runs the
  existing `check_typed` against `l2` + `alt`. Keyboard: tiles numbered 1-9,
  Backspace removes the last. No new pack data.
- **Where in the ladder**: one rep only (phrases: rep 2, before `type_l2`).
  Never the final format — the main complaint about Duolingo's version is that
  recognition replaces recall.
- **Risk**: `alt` lists must cover reorderings ("Vous vous appelez comment ?");
  they already do for typed answers.

### 2. A mistakes log and a "Mistakes" review — S/M, high

- **Competitor**: Duolingo Practice Hub → Mistakes [S]; Kwiziq builds each quiz
  from the last one's errors [S].
- **Why**: "Practice weak items" ranks by predicted recall, which is not the
  same as "what I actually got wrong this week and what I typed instead".
- **Build**: in `engine.answer`, on a wrong first answer append
  `{item, mode, given, day}` to a bounded list in state (last ~200). Classify
  with existing helpers: accent-only, article/gender (first token differs),
  one-edit slip, wrong word, blank. UI: a Mistakes page — grouped by class,
  each row showing *your answer* against the right one, and a "Drill these"
  button that opens a practice session (off-schedule, like today's practice).
  Also show on the session summary: "3 of your 4 misses were articles".
- **Note**: when `given` equals another item's `l2`, record the pair; that is
  the input for #5 and #9.

### 3. A listening ladder instead of one dictation format — S/M, high

- **Competitor**: Pimsleur, Glossika, Clozemaster listening mode, Babbel's
  listening review mode [S].
- **Why**: full dictation is the hardest listening task and the only one here.
  Jiang et al. measured listening as the weaker skill even on Duolingo.
- **Build** (all from existing data):
  - `listen_choose`: play `l2`, show four `l1` meanings (no text of the L2).
    Slot it at rep 2 for vocab.
  - Sentence dictation: at high reps, dictate the item's `ex` sentence, not
    just the word.
  - A "slow" button: replay at `rate = 0.6` (currently fixed at 0.9).
  - "Listening session" in practice: only `listen_choose` + dictation.
  - Hide the modes cleanly when no fr/es voice is installed (the earlier
    Web Speech note covers detection).
- **Risk**: synthetic voices mispronounce some liaisons and homographs. Keep
  dictation grading as-is; do not add minimal-pair *discrimination* drills
  (ou/u, pero/perro) on TTS — I would not trust a synthesiser as the reference
  for a contrast the learner cannot yet hear [I].

### 4. Auto-cloze from example sentences — S, medium-high

- **Competitor**: Clozemaster and Lingvist make the sentence gap their whole
  product [S/B].
- **Why**: a mature vocab card is always asked the same way. 787 example
  sentences are already authored and currently only displayed.
- **Build**: at pack load, for each vocab item check whether `l2` minus its
  article appears as a whole word in `ex`; if so the item gains a derived mode
  `ex_cloze` (blank that word, prompt with `ex_l1`, accept the bare word).
  Alternate it with `type_l2` from rep 4. Items whose `ex` uses an inflected
  form simply don't qualify; print the coverage in `python -m
  sect_academy.packs`.
- **Not copied**: Clozemaster's unvetted corpus. Stay with authored sentences.

### 5. Leech handling — S, medium-high

- **Competitor**: Anki tags and suspends at 8 lapses, re-warns at 12, 16… [S].
- **Why**: with FSRS a leech costs many reviews and teaches little; the card
  already counts `lapses`.
- **Build**: threshold 4 lapses (low end of community practice [S]; my choice
  [I]). Do **not** suspend silently. Instead: (a) show a "stubborn item" panel
  the next time it is due — note, example sentence, and the item it was most
  often confused with from #2, side by side; (b) drop it one rung on the format
  ladder for two reps; (c) list leeches on Progress with a "set aside" toggle
  the learner controls. Re-warn every +2 lapses.
- **Fits the game**: nothing is destroyed; setting aside is reversible.

### 6. "I was right" / flag / personal note on an item — S, medium-high

- **Competitor**: Anki lets you edit any card; Duolingo and Clozemaster take
  error reports [S]; Memrise users revolted when their own content went [S].
- **Why**: the spec lists "a human native-speaker pass" as not done. A
  single-user app has no report queue, so a rejected-but-correct answer just
  silently corrupts the schedule.
- **Build**: on the feedback screen: "Accept my answer" (stores a per-item
  personal `alt` in state and regrades that answer as Good; listed on a page so
  it can be undone and later upstreamed into the YAML), "Flag" (adds to a
  flagged list for pack fixing), and a one-line personal mnemonic shown with
  the item thereafter.
- **Risk**: self-forgiveness. Show a count of accepted overrides on Progress.

### 7. Dialogues as a content type — L (authoring), high

- **Competitor**: Babbel's dialogue-then-take-a-role lesson [S]; Duolingo
  Stories with comprehension checks [S]; the comprehensible-input case from
  Dreaming Spanish/LingQ [S].
- **Why**: nothing in the app is longer than one sentence. LingQ's own users
  complain of knowing words but not how they combine [S].
- **Build**: one `dialogue` per unit in YAML: `lines: [{who, l2, l1}]` (6-10
  lines, only vocabulary from this and earlier units) plus 2-3 `checks` (mcq
  about what happened; "what does X mean here"). Three passes in the UI:
  1. Listen/read line by line; tap a line for its translation; alternate two
     TTS voices if two are installed, else change `pitch`.
  2. Answer the checks.
  3. Take a role: your lines are hidden, the prompt is the `l1`, you type (or
     build from tiles, #1).
  Unlocks when the unit's items have all been met; lives in the Library and as
  an optional end-of-session extra. Not FSRS-scheduled.
- **Game invariant**: qi is paid only for scheduled, graded work, so dialogues
  pay nothing or only the session-level mood lift. Decide before building.
- **Effort**: ~64 dialogues across four courses plus a native-speaker check.
  A validator rule (see #13) keeps them inside known vocabulary.

### 8. Conjugation tables as drills — M, high

- **Competitor**: Kwiziq's grammar kwizzes [S]; table drills are standard in
  grammar trainers [B].
- **Why**: verb forms are today scattered across single cloze items; the
  paradigm is never asked as a whole.
- **Build**: optional unit field `tables: [{id, verb, l1, tense, forms: {je:
  suis, tu: es, …}}]`. Two generated exercises: *fill the table* (six inputs,
  graded per cell) and *one cell in context* ("nous ___ (être)"). One FSRS
  card per table; grade = Again if 2+ cells wrong, Hard if 1, Good if none.
  Mix tables of different verbs in the same review session — the repo's own
  notes cite Pan et al. 2019: interleaving conjugations helped across sessions,
  not within the first one.
- **Data**: about 25-30 tables per language cover A1-A2 (regular models plus
  être/avoir/aller/faire, ser/estar/ir/tener, the first past tense).

### 9. Gender and article drill — S, medium

- **Competitor**: none does it well; Drops is criticised precisely for letting
  gender slip [S].
- **Why**: the app already never forgives a wrong article, so a targeted drill
  attacks its most common failure class (measurable once #2 exists).
- **Build**: derive gender from the leading article of noun `l2` values
  (le/la/un/une; el/la/un/una). For `l'` and plural items add an optional
  `g: m|f` field — the validator should demand it only for those. Exercise:
  the bare noun, two buttons (le/la; el/la), 15 in a row, keyboard ←/→.
  Practice-only; feed misses to #2.

### 10. Say-it-first (anticipation) mode — S, medium

- **Competitor**: Pimsleur's anticipation principle [S]; Glossika's spoken
  reps [S]; Language Transfer's pause-and-construct [S].
- **Why**: the app has no speaking at all. Speech recognition is out (network
  in most browsers, and unreliable for beginners) but production aloud does not
  need a judge.
- **Build**: practice mode: show `l1` → 4-second pause bar → reveal `l2` and
  speak it → learner taps "had it" / "not yet". Hands-light: Space advances.
  Self-graded, so keep it off the schedule (or count "not yet" as a reason to
  pull the item into the next session, never as a pass).
- **Could not verify**: any controlled evidence for the anticipation principle
  specifically; it is consistent with retrieval-practice findings already in
  `language_learning_a1.md`.

### 11. Placement: bisect, partial credit, and unit test-out — M, medium

- **Competitor**: Duolingo's adaptive test and its move to partial credit [S];
  Kwiziq's 52-question level test [S]; Lingvist places on first use [S].
- **Build**:
  - Start in the middle unit and bisect instead of walking up from unit 1; the
    existing "two failed units in a row" stop still applies at the boundary.
  - Count an accent/typo-flagged answer as half a point (the grader already
    distinguishes it).
  - Add an explicit "I don't know" button so a blank is not a guess.
  - A "Test out of this unit" button on every locked unit, reusing the same
    three-question block — lets a returning learner skip without retaking the
    whole placement.
- **Keep**: skipped items returning as reviews. None of the competitors
  surveyed describes that safety net.

### 12. Separate the streak from the daily goal — S, medium

- **Competitor**: Duolingo: streak extends on one lesson; the daily goal is a
  separate, self-chosen target. Reported +3.3% day-14 retention [S, company
  A/B, relative].
- **Now**: the streak needs a *whole* session ("Finish a whole session for it
  to count toward your streak").
- **Build**: streak = any 5 graded first answers in a day. Daily goal = a
  setting (light 10 / regular 20 / deep 40 answers) with a ring on the home
  page; meeting it is what triggers the "Master lectured" mood lift.
- **Not copied**: energy/hearts, loss-framed notifications, paid streak repair.
  The existing rest days already do what Streak Freeze does.

### 13. Known-vocabulary linter and novel-sentence items — M, medium

- **Competitor**: Language Transfer builds new sentences from held pieces [S];
  Speakly/Lingvist order by frequency [S]; Dreaming Spanish grades input [S].
- **Build**: (a) in `packs.py`, a warning-level check that every token of each
  `ex`, phrase and dialogue line appears in an item of the same or an earlier
  unit (with a small function-word allow-list). (b) Per unit, 3-5 `phrase`
  items flagged `novel: true` — sentences the learner has never seen, made
  only of taught words; these skip the choose stages and start at tiles/typing.
- **Why**: turns "I memorised this phrase" into "I can build one".

### 14. Practice hall: one page, pick your mode — S (once the modes exist), medium

- **Competitor**: Babbel's review manager (flashcards/listening/speaking/
  writing) [S]; Duolingo's Practice Hub [S].
- **Build**: replace the single "Practice weak items" button with a page:
  Weakest, Mistakes (#2), Listening (#3), Say-it-first (#10), Gender (#9),
  Verb tables (#8), Stubborn items (#5). All off-schedule.

### 15. Grammar map — M, medium

- **Competitor**: Kwiziq Brainmap [S].
- **Build**: optional `tags: [ser-estar, passe-compose]` on items; Progress
  shows one tile per tag coloured by mean retrievability and recent error rate;
  tapping a tile opens the unit note and a drill of that tag. Needs a tagging
  pass over ~1,400 items (cloze `note` fields give a head start).

### 16. Honest progress numbers — S, low-medium

- **Competitor**: LingQ known-words count; Dreaming Spanish hours roadmap [S].
- **Build**: "words in long-term memory" (stability ≥ 21 days — threshold is
  my choice), minutes studied, and the unit `goal` can-do lines as a checklist.
- **Caution**: LingQ users report chasing the number [S]. Count only what
  FSRS says is retained, never items merely seen.

### 17. Literal gloss field — S, low-medium

- **Competitor**: Mango [B, unverified].
- **Build**: optional `lit:` shown on the intro card and in feedback ("How do
  you call yourself?"). Some notes already carry "Literally '…'"; move those
  into the field so they render consistently.

### 18. Timed pair matching as a warm-up — S, low

- **Competitor**: Duolingo match exercises, Drops [B].
- **Build**: six L2/L1 pairs from today's due items, tap to match, timer.
  Unscheduled, unpaid. Fun, weak evidence; build last.

## Things to deliberately not copy

- Energy/hearts or any limit on practice (Duolingo's most complained-about
  change in 2025-26) [S].
- Word bank as the terminal format; multiple choice as the mastery test [S,
  anecdotal + this repo's retrieval-practice notes].
- Unvetted corpus sentences (Clozemaster, Glossika error complaints) [S].
- Vanity counters that count exposure (LingQ) [S].
- Rewriting courses in a way that renames item ids — Duolingo's course
  rebuilds stranded learners [S]; this repo's rule already forbids it.

## Not verified in this run

- Mango's colour mapping and literal glosses; Drops' five-minute cap; Lingvist's
  typed-gap card; Clozemaster's Tatoeba sourcing and frequency ordering;
  Pimsleur backchaining; Memrise native-speaker clips; Anki's own wording of
  leech advice. All from memory.
- No retention data found for Babbel, Busuu, Memrise or any smaller app.
- No efficacy study found for Clozemaster, Lingvist, Kwiziq, Glossika,
  Pimsleur, Language Transfer, LingQ, Dreaming Spanish, Drops, Speakly, Mango.
- No research found comparing tile-building with typing, or testing Stories,
  streak freezes, or the anticipation principle in isolation.
- Every efficacy study found is company-run or company-partnered; none has a
  control group using a different app.
- Search results were read as summaries; I did not open the papers' full text.
- `CLAUDE.md` still describes the older `maybot_control_center/academy/`
  layout; the code is in `sect_academy/`. Function names above are from the
  latter.

## Sources

Efficacy and retention
- Jiang et al., Foreign Language Annals — https://experts.nau.edu/en/publications/evaluating-the-reading-and-listening-outcomes-of-beginning-level-/
- Duolingo investor release on the same study — https://investors.duolingo.com/news-releases/news-release-details/leading-language-research-journal-publishes-study-showing
- Duolingo efficacy summary — https://blog.duolingo.com/results-duolingo-efficacy-studies
- Jiang et al. 2024, CALICO Journal — https://journal.equinoxpub.com/Calico/article/view/26704
- Smith, Jiang & Peters 2024 — https://scholarspace.manoa.hawaii.edu/items/140c6a0c-0035-4c87-b678-a0d74dd53de3
- Babbel/MSU study, MSU coverage — https://msutoday.msu.edu/news/2020/how-effective-are-language-learning-apps and https://cal.msu.edu/news/do-language-learning-apps-really-work/
- Babbel press release — https://babbel.com/press/en-us/releases/2019-01-10-Babbel-SPA-2018-Study.html
- Busuu university study — https://www.busuu.com/en/research/university-study ; 2021 follow-up — https://blog.busuu.com/2021-busuu-efficacy-study/
- Duolingo, improving the streak — https://blog.duolingo.com/improving-the-streak ; streak and habit — https://blog.duolingo.com/how-duolingo-streak-builds-habit

Product mechanics
- Duolingo Practice Hub — https://blog.duolingo.com/guide-to-duolingo-practice-hub/
- Duolingo placement partial credit — https://blog.duolingo.com/partial-credit-improvements-to-duolingos-placement-test/
- Birdbrain — https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain ; https://spectrum.ieee.org/duolingo
- Duolingo energy — https://blog.duolingo.com/duolingo-energy/
- Babbel, how it works — https://www.babbel.com/how-babbel-works ; spaced repetition — https://www.babbel.com/spaced-repetition-language-learning
- Busuu community corrections — https://www.busuu.com/en/how-to/corrections
- Anki manual, leeches — https://docs.ankiweb.net/leeches.html ; forum threads — https://forums.ankiweb.net/t/automated-leech-detection/56887
- Clozemaster FAQ — https://www.clozemaster.com/faq
- Kwiziq Brainmaps — https://kwiziq.com/faq/brainmaps ; tour — https://french.kwiziq.com/tour
- Pimsleur — https://en.wikipedia.org/wiki/Pimsleur_Language_Programs ; Choe 2016 — https://hpu.edu/research-publications/tesol-working-papers/2016/08ChoeTaiAnn.pdf
- Language Transfer — https://www.languagetransfer.org/about
- Dreaming Spanish FAQ — https://www.dreaming.com/faq
- Memrise community courses — https://memrise.zendesk.com/hc/en-us/articles/29804562432913-Will-Memrise-delete-Community-Courses

Reviews and complaints (mostly affiliate blogs or self-selected users)
- Duolingo energy: https://www.androidauthority.com/quitting-duolingo-energy-system-3599842/ ; https://www.change.org/p/duolingo-hearts-not-energy ; course rewrites: https://www.androidauthority.com/duolingo-broken-updated-courses-why-i-quit-3686405/
- Typing add-on (word-bank complaint): https://addons.mozilla.org/firefox/addon/typelingo/
- Babbel: https://www.fluentu.com/blog/babbel-review/
- Busuu: https://www.mezzoguild.com/busuu-review/
- Clozemaster: https://www.alllanguageresources.com/clozemaster-review/ ; https://fluentu.com/blog/reviews/clozemaster
- Lingvist: https://www.fluentu.com/blog/lingvist-review/
- Kwiziq: https://www.alllanguageresources.com/kwiziq-review/
- Pimsleur: https://www.fluentu.com/blog/pimsleur-review/
- Language Transfer: https://www.fluentu.com/blog/language-transfer-review/ ; https://www.alllanguageresources.com/language-transfer/
- Glossika: https://www.alllanguageresources.com/glossika/ ; https://lingopie.com/blog/glossika-review/
- LingQ: https://www.alllanguageresources.com/lingq-review/ ; https://forum.lingq.com/t/lingq-the-illusion-of-learning/975663
- Dreaming Spanish: https://www.fluentu.com/blog/reviews/dreaming-spanish/
- Drops: https://www.mezzoguild.com/drops-review/ ; https://www.alllanguageresources.com/language-drops-app/
- Mango: https://ling-app.com/blog/mango-languages-review/
- Speakly listing: https://apps.apple.com/us/app/id1255478968
