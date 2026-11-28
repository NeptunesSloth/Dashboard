# UI psychology: principles, evidence, and an audit of Sect Academy

Research date: 2026-11-27. Purpose: the owner asked to "learn how to make UI based on human
psychology". Part 1 is the established psychology of interface design and of learning apps,
each principle with its evidence strength and the design rule it implies. Part 2 is an
audit of the real app (server on a fresh state, Playwright at 1366x900 and 390x844), screen
by screen. Part 3 ranks the changes.

**Evidence tags.**
- **[Strong]**: replicated experiments or meta-analyses, or a measurable standard (WCAG).
- **[Moderate]**: good primary studies, but few replications, or effects that depend on context.
- **[Weak/contested]**: replications failed, a meta-analysis finds about zero, or the "law" is
  a practitioner heuristic.
- **[S]** marks a source read this session. **[K]** is a standard reference cited from memory
  and not re-fetched this session. **[I]** marks my inference.

Screenshots are in the session scratchpad (`.../scratchpad/uxa/shots/`), not in the repo.
The audit cites them by filename.

---

## Part 1: Principles

### Attention, choice and working memory

**Hick's law and choice overload.** Decision time grows with the log of the number of
equally likely options. Separately, too many options *can* reduce choosing or satisfaction.
- Evidence: Hick (1952) and Hyman (1953) hold up for simple reaction time with
  equiprobable stimuli [Strong, K]. In real UIs, familiarity, grouping and search swamp the
  log curve, so it is a direction, not a formula [I]. Choice overload is contested:
  Scheibehenne, Greifeneder and Todd's 2010 meta-analysis of 50 experiments (N = 5,036)
  found a mean effect of about zero with large variance, and the famous jam study failed to
  replicate. Chernev et al. (2015) found the effect appears under specific moderators:
  choice-set complexity, preference uncertainty, and the difficulty of the decision task
  [S: scheibehenne.options.2010.pdf; PBS / CSMonitor summaries].
- Rule: do not cut options for their own sake. Reduce the options *that compete at the
  moment of a decision* (one primary action per view), group the rest, and give a
  recommended default when the user has no preference yet (a beginner choosing a course).

**Miller's 7±2, chunking, working memory.** Working memory holds a few chunks. Cowan (2001)
puts the limit at about 4 [Strong, K]. "7 items in a menu" is a misreading of Miller: menus
are recognised, not recalled. The real rule is about what the user must *hold in mind*.
- Rule: never make the learner remember something from one screen to use on another (the
  correct answer, a priority scheme, what a number meant). Chunk long lists into labelled
  groups of a few.

**Cognitive load theory (Sweller).** Intrinsic load is the material itself. Extraneous load
comes from presentation (split attention, redundancy, decoration). Germane load is the
effort that builds schemas. Only extraneous load is pure waste.
- Evidence: the split-attention, redundancy, worked-example and expertise-reversal effects
  are robust across many randomised studies [Strong, K: Sweller, van Merriënboer & Paas
  1998, 2019]. "Germane load" as a separate quantity is now treated as a theoretical
  construct, not something you can measure [Moderate, K].
- Rule: during an exercise, remove everything not needed to answer it (no resource ticker,
  no toasts). Put the explanation *next to* the thing it explains. Scaffold novices
  (worked examples, notes), and fade the scaffolds as they gain skill.

**Progressive disclosure (Nielsen).** Show the few things most people need now, and defer
the rest to a secondary screen or a "more".
- Evidence: a well-established usability principle [Moderate; NN/g, K]. It fails when the
  deferred thing is needed often (then it is hidden cost).
- Rule: the first screen of a returning session should show *today* (study, one alert). The
  sim's depth goes behind tabs that open when wanted.

**Gestalt grouping: proximity, similarity, common region.** Things that are close, look
alike or share a container are read as one group.
- Evidence: Wertheimer and successors. Palmer (1992) showed common region overrides
  proximity [Strong, K].
- Rule: things that look alike must *be* alike. The same badge style for unlike languages, or
  the same gold button for "Study" and "Begin this course", teaches a false grouping.

**Von Restorff (isolation) effect.** The item that differs is noticed and remembered.
- Evidence: robust in memory research since 1933 [Strong, K]. In UI it only works if the
  distinctive treatment is *rare*. Twenty identical "primary" buttons isolate nothing.
- Rule: one primary-coloured button per view. Reserve the strongest colour (here gold) for
  the single next action.

**Serial position effect.** The first and last items in a list are remembered best.
- Evidence: Murdock (1962), Glanzer & Cunitz (1966) [Strong, K] for recall of lists.
  Applying it to UI navigation is an extrapolation [Weak/Moderate].
- Rule: put the most important nav items first and last. In the app: Sect first, Progress
  last. Study should be first or second (it is).

**Reading and scanning: F-pattern, layer-cake.** On text-heavy pages, people scan headings
and the start of lines. Good headings produce a "layer-cake" scan (heading to heading).
- Evidence: NN/g eye-tracking (2006, re-checked 2017) [Moderate, K]. The F-pattern is a
  *failure* mode of unstructured pages, not a goal.
- Rule: front-load headings and button labels ("Study 12 cards", not "There is more, if you
  wish"). Short descriptive headings on panels. Key number first.

### Motor and perceptual limits

**Fitts's law and touch targets.** Time to hit a target grows with distance and shrinks
with size. On touch, the finger pad is about 1 cm.
- Evidence: Fitts (1954), MacKenzie's (1992) Shannon formulation [Strong, K]. NN/g
  recommends about 1 cm × 1 cm [S: via Roselli]. WCAG 2.2 SC 2.5.8 (AA) requires 24×24 CSS
  px or spacing. 2.5.5 (AAA) requires 44×44. Apple: 44 pt. Android: 48 dp [S: w3.org].
- Rule: primary touch targets at least 44 px tall on phone. Frequent actions within thumb
  reach (bottom). Never place a destructive action next to a frequent one.

**Colour and contrast for readability.** WCAG 1.4.3: 4.5:1 for body text, 3:1 for large
text. 1.4.11: 3:1 for UI component boundaries. Colour must not be the only cue (1.4.1).
About 8% of men have a red–green colour-vision deficiency.
- Evidence: a standard [Strong].
- Rule: right/wrong needs an icon or word as well as red/green. Text under about 12 px is
  hard to read on phones whatever the contrast.

**Doherty threshold and feedback latency.** Responses under about 0.1 s feel instant. Under
1 s, flow is kept. At 10 s attention is lost (Nielsen, from Miller 1968 and Card et al.).
The "400 ms Doherty threshold" is a popular attribution: Doherty & Thadani (1982, IBM)
showed productivity rising steeply as response time fell below 1 s, but the 400 ms figure
may not be in the original paper.
- Evidence: Nielsen's three limits [Moderate, S: lawsofux.com, feelsfast]. The 400 ms
  figure itself is [Weak].
- Rule: grading feedback must appear in under 100–200 ms, which a local server allows. Long
  waits (book import) need a progress indicator.

### Familiarity, aesthetics, errors

**Jakob's law.** Users spend most of their time on other products and expect yours to work
the same way.
- Evidence: a practitioner heuristic [Moderate, NN/g]. It is strongly supported in effect by
  research on transfer and mental models (Norman) [K].
- Rule: settings live under a "Settings" label or gear icon. Study apps put "Continue"
  where Duolingo and Anki do. Colony-sim conventions (RimWorld's priority grid, 1 = first)
  are fine for that audience, but explain them for language learners who never played one.

**Aesthetic–usability effect.** Attractive interfaces are *perceived* as easier to use and
are forgiven more.
- Evidence: Kurosu & Kashimura (1995) and Tractinsky (1997) found the correlation.
  Tractinsky, Katz & Ikar (2000) found that aesthetics shaped perceived usability even after
  use. Later work shows the effect is real but can mask actual usability problems in
  testing [Moderate, K].
- Rule: the painted art earns goodwill. Spend it carefully, and do not let beauty hide
  friction during testing (watch behaviour, not ratings).

**Error prevention and forgiveness (Norman, Nielsen heuristic #5 and #9).** Prevent slips
by design. Make errors reversible. Say what went wrong in plain words and how to fix it.
- Evidence: [Strong/Moderate, K: Norman, *The Design of Everyday Things*. Reason's error
  taxonomy].
- Rule: in study, distinguish *slips* (a typo, a missing accent) from *mistakes* (did not
  know). The app already does this ("Right, with a small slip"). Destructive actions need
  undo, not only confirm().

### Motivation

**Self-Determination Theory (Deci & Ryan): autonomy, competence, relatedness.** People
sustain activities that make them feel in control, increasingly capable, and connected.
- Evidence: a large literature. Ryan & Deci (2000). A meta-analysis of SDT in education
  (Howard et al. 2021) links autonomous motivation with achievement and persistence
  [Strong, K].
- Rule: let the learner choose (what, how much, when), show *growth in skill* (not only
  points), and give the study a social meaning. Here, the disciples "hearing the lecture"
  is a nice relatedness hook.

**Overjustification effect / cognitive evaluation theory.** Expected, tangible,
performance-contingent rewards for an activity people already enjoy can reduce intrinsic
interest once the rewards stop. Informational feedback and unexpected rewards do not.
- Evidence: Deci, Koestner & Ryan (1999), a meta-analysis of 128 studies: expected tangible
  rewards undermine free-choice intrinsic motivation, and performance-contingent rewards do
  so too. Verbal (positive feedback) rewards *enhance* it. Unexpected rewards have no
  effect. Cameron & Pierce (1994) dissented, finding small effects [Strong but debated
  magnitude; S: PubMed 10589297; Chicago Booth Review].
- Rule: this is directly relevant, because study pays qi. Keep the reward
  *informational* ("your study made the Master stronger") rather than *controlling* ("you
  must study or the sect suffers"). Do not scale it by accuracy (performance-contingent).
  Show the learning itself as the main payoff (words learned, sentences now readable). The
  CLAUDE.md rule "the sect must not depend on study" is exactly right.

**Fogg Behavior Model (B = MAP).** A behaviour happens when motivation, ability and a
prompt converge at the same moment.
- Evidence: a design model rather than a tested theory [Weak/Moderate. Fogg 2009]. It is
  consistent with habit-formation research (Lally et al. 2010: a median of 66 days to
  automaticity, with wide variance) [Moderate, K].
- Rule: make the daily action tiny and obvious (ability), and put the prompt where the
  learner already looks. In this app that means the sect home, which opens first.

**Goal-gradient effect.** Effort accelerates as a goal nears. Even *illusory* head starts
help.
- Evidence: Kivetz, Urminsky & Zheng (2006, JMR): café customers bought coffee faster near
  the free one. A 12-stamp card with 2 pre-filled completed faster than a 10-stamp card
  (median 10 vs 15 days) [Moderate–Strong, S: Columbia / Chicago Booth].
- Rule: show the session as a short, finite bar ("8 of 12") and show the progress already
  made (start new learners' bars with the placement credit). Do not fake progress.

**Zeigarnik / Ovsiankina effects.** Zeigarnik claimed unfinished tasks are *remembered*
better. Ovsiankina found people tend to *resume* interrupted tasks.
- Evidence: Ghibellini & Meier (2025) meta-analysis: Zeigarnik's memory advantage "lacks
  universal validity" (hard to replicate). The resumption tendency (Ovsiankina) is general
  [S: HSSC 2025, doi 10.1057/s41599-025-05000-w].
- Rule: do not rely on "open loops" to nag. A visible, resumable unfinished session
  ("Resume: 5 left") is supported. Guilt messages are not.

**Peak-end rule.** Experiences are judged largely by their most intense moment and their
end.
- Evidence: Kahneman et al. (1993, cold-water), Redelmeier & Kahneman (1996, colonoscopy)
  [Moderate–Strong. Some later failures for long, multi-episode experiences, K].
- Rule: end every session on a success and a clear, warm summary. Do not lead the summary
  with a low percentage. Order the last items so the session ends on something the learner
  can do.

**Variable rewards and their ethical limits.** Unpredictable rewards produce persistent
responding (variable-ratio schedules: Skinner, Ferster). Eyal's "Hook" model uses this.
- Evidence: robust in animal learning [Strong, K]. In products, it is the mechanism of
  compulsive loops (loot boxes, feeds). Loot-box spending is associated with problem
  gambling (Zendle & Cairns 2018) [Moderate, K].
- Rule: variety and surprise in *content* (events, stories) are fine and make a game
  pleasant. Do not make the *study reward* random, and do not attach random payouts to
  coming back (daily login chests). The app currently does neither.

**Loss aversion and streaks.** Losses weigh about twice gains (Kahneman & Tversky), so a
streak becomes something to protect.
- Evidence: Silverman & Barasch (2023, JCR, 7 studies): intact streaks increase continued
  engagement, and *broken* streaks reduce it. The drop-off is worse when people blame
  themselves and *attenuated when the streak can be repaired* [S: colorado.edu, udel.edu].
  The size is modest (about 66% vs 58% continuing in one study). Duolingo reports streak
  freezes and wagers raise daily activity, but these are company A/B numbers and
  correlational claims ("7-day streak → 3.6× more likely to finish") [S: blog.duolingo.com.
  Moderate, first-party]. Practitioner reports describe streak anxiety and a broken streak as
  the moment loyal users quit [Weak, S: uxdesign.cc].
- Rule: a streak should be a *record*, not a threat. Keep repair (rest days, holiday mode),
  count weeks rather than days, never use guilt copy, never let the game punish a break,
  and celebrate a return as much as a run.

**Gamification in learning overall.** Sailer & Homner (2020) meta-analysis: small positive
effects on cognitive (g = .49), motivational (g = .36) and behavioural outcomes. Game
fiction and social interaction moderate the behavioural effect. The motivational and
behavioural effects were *less stable* in rigorous studies [S: Educ Psych Rev, doi
10.1007/s10648-019-09498-w].
- Rule: the sect fiction is a legitimate lever (game fiction helps), but the learning must
  be the core loop.

**Defaults and status-quo bias.** Most people keep the default.
- Evidence: Johnson & Goldstein (2003) organ donation. Madrian & Shea (2001) 401(k)
  enrolment [Strong, K]. Jachimowicz et al. (2019) meta-analysis: defaults work, with a
  medium effect (d ≈ 0.68) and much heterogeneity [Strong, K].
- Rule: every default is a decision you are making for the user. Default to the
  sustainable choice (one course, 8 new a day, balanced storyteller), and match defaults to
  what you know (the reader's starter shelf should open in a language they study).

### Feedback for learners

**Immediate, specific, task-focused feedback.** Kluger & DeNisi (1996), a meta-analysis of
607 effects: feedback helps on average (d ≈ 0.41), but about *a third* of feedback
interventions *lowered* performance, chiefly when feedback drew attention to the self rather
than the task. Hattie & Timperley (2007): feedback should answer "where am I going, how am I
going, where to next" [Strong, K].

**Growth framing.** Growth-mindset *interventions* have small effects on achievement:
Sisk et al. (2018) found weak effects overall, and Macnamara & Burgoyne (2023) found d ≈
0.05, falling to about 0 in high-quality studies. Burnette et al. (2023) argue for
heterogeneous effects [Weak/contested, S].
- Rule: do not rely on mindset slogans. What works is *task-level* feedback that shows the
  learner improving, plus normalising errors as part of retrieval practice. The app's line
  "A hard session is where memory is built" is accurate (see desirable difficulties), so it
  is fine as information. It cannot carry motivation alone.

**Desirable difficulties (Bjork).** Retrieval practice, spacing, interleaving and
generation slow apparent performance but improve long-term retention. Learners misread the
slowness as failure and prefer the easier, worse method.
- Evidence: testing effect (Roediger & Karpicke 2006). Spacing (Cepeda et al. 2006 meta).
  Interleaving (Rohrer). Bjork & Bjork (2011) [Strong, K].
- Rule: the UI has to *explain and reward* difficulty: show "first-try" scores as normal
  for spaced recall, prefer qi for typed recall over recognition (the app does: 2 vs 1),
  and do not let accuracy-based rewards push learners toward easy modes.

**Fatigue and session length.** Vigilance and accuracy decline over sustained effortful
tasks. Distributed practice beats massed practice (Cepeda et al. 2006) [Strong, K].
"Ego depletion" is *not* a sound basis: the multi-lab replication by Hagger et al. (2016)
found d ≈ 0.04 [Weak/contested].
- Rule: short default sessions with a natural stop ("Done for today. Come back tomorrow"),
  and an optional "keep going". Show the estimated minutes up front.

### Dark patterns

**Deceptive/manipulative design (Brignull; deceptive.design; OECD and Canadian taxonomy).**
Types relevant here: confirmshaming (guilt in the decline option), nagging, false urgency,
hidden costs, obstruction, and "playing on loss aversion" via punitive streaks
[S: NN/g deceptive-patterns, ised-isde.canada.ca, Mozilla].
- Rule: the test is whether the user, fully informed, would endorse the nudge. Study
  reminders and streaks pass if they are honest, opt-out-able and non-punitive.

---

## Part 2: Audit of the real screens

Setup: fresh state, founded "Azure Lantern" with French A1 (default), later enrolled in
Japanese A1 and Security+, ran sessions (with deliberate mistakes), library, trials, a
French verb drill, progress, Read (a Hugo poem, a Daudet story, a lookup), sect tabs, and an
event card and a result scene after advancing time.

### Founding (`01_founding_desk.png`, `01_founding_phone.png`)
- Win: good grouping (Gestalt): one row per language, levels as chips, certificates
  separate. Win: a sensible default (French A1 ticked, "Turning Seasons" storyteller) and the
  honest load note ("about 8 new items a day; two or three is a comfortable load").
- Issue (Hick/defaults): 31 chips. A beginner has no preference among levels, so the choice
  is hard. The tooltip blurbs are on hover only, which does not work on touch.
- Issue: the nav (Study, Read, Library…) is live before the sect exists.
- Issue (phone): "Found the sect" is at y ≈ 1380 on an 844 px screen. That is fine: it is
  the end of a form.

### Placement (`02_placement_offer.png`, `03_placement_q.png`, `04_placement_done.png`)
- Win: "I don't know" is as large as "Next". That is honest, and it prevents guessing
  (error prevention).
- Win: "I am a beginner: start from the first unit" is a clear way out.
- Issue (peak-end): a self-declared beginner ends on three big coloured tiles reading
  **0/20, 0, 0/6**. That is a failure tally at the end of the first experience. Better:
  "You start at Greetings & politeness. Perfect place to begin," with the numbers small or
  hidden when the result is "beginning".

### Sect home (`05_home_desk_fold.png`, `05_home_desk_full.png`, `06_home_phone_fold.png`, `30_event_desk.png`)
- **Main problem: the study action is below the fold on desktop.** At 1366×900 the fold
  shows 9 resource chips (two rows), the speed control, the streak flame, the elder's
  counsel (a colony tutorial) and the hall, with **6 gold "↑" upgrade badges**. The study
  strip ("Study today: 0 to review, 8 new [Begin]") starts at y ≈ 955. With an event
  card pending (`30_event_desk.png`) it is pushed to about 1190. On phone it barely
  peeks above the bottom nav, and with an event it is off-screen
  (`30_event_phone.png`). Principles: Fogg (no prompt where the eye is), Von Restorff (gold
  is used by six upgrade badges and the play button before the study button), cognitive
  load.
- Issue (duplication/Hick): two study panels ("Study today… Begin" strip *and* "Your
  study for today… Begin studying" lower down) plus the "Details ↓" link. Two "Begin"
  buttons with different labels for the same action.
- Issue (perception): 15 hall labels at 8 px on phone, and `−1.9/day` at 9.9 px. Below
  any comfortable reading size.
- Issue: the elder's counsel tutorial ("Open Work and change one disciple's priority")
  still shows "1 of 10" after five sim days. It does not advance until done, and it competes
  for the top slot every visit. Its only exit is "I know colony sims, skip", which is
  mildly confirmshaming for people who don't.
- Issue (Jakob/SDT): the sim auto-plays at ×1 on arrival, so the eye goes to things
  changing.
- Win: rates are shown as `−1.9/day` in red on Rice (loss framing used *informatively*).
  The event card states the odds plainly ("98 vs 14, 7.0 to 1") and "Time waits for your
  answer" (no false urgency). This is the honest version of the genre.

### Study session (`101_desk_choice.png`, `101b_desk_choice_fb.png`, `102b_desk_typed_fb.png`, `101b_phone_typed_fb.png`, `103_phone_intro.png`, `1sec_01_desk_notes.png`, `1sec_03b_desk_choice_fb.png`, `1ja_03_desk_choice.png`)
- Wins: a single column, one question, nothing else on screen (no ticker, low extraneous
  load). A progress bar with "1/4" (goal-gradient). Number keys on options. Enter to
  submit. Accent buttons below the input. Correct feedback shows the pair, a usage note
  and "Next review in 1 day. +1 qi" (specific, task-focused, with the spacing made
  visible). Wrong feedback says "Not quite" (non-shaming), gives the answer and the note,
  and the item "returns later in this session" (immediate retry: retrieval success). The
  new-item intro card offers "I know this already" next to "Got it" (autonomy).
- **Bug (consistency, error state, overflow): the "Continue" button after a wrong answer is
  unstyled.** It is salmon with left-aligned normal-weight text and is about 54 px wider than
  the column. On phone it causes horizontal page scroll: the screenshot is 430 px wide on a
  390 px viewport. Cause: `.btn.seal` (academy.css line 104) is wiped by the later
  `.seal { all: unset; … }` rule (line 829, the precept/"seal" chips), because the
  feedback button uses class `seal`. So the moment of failure is also the one moment the UI
  looks broken. Fix: rename the session variant (e.g. `.btn.miss`) or scope `.seal` to
  `.seals .seal`.
- Issue (feedback specificity): on a wrong cert answer (`1sec_03b`) the feedback repeats
  the definition of the right term. It does not say why the chosen distractor
  ("Operational control") is wrong. Best-answer items do have per-option whys. Add a
  one-line contrast for the picked distractor when the item has one.
- Issue (cognitive load): unit notes for Security+ (`1sec_01`) are one long card (CIA,
  AAA, Zero Trust, a table, six control types, change management) with a sticky "Start
  learning" button that covers text mid-line. Chunk the notes into 2–3 screens or
  collapsible sections, and give a bottom fade above the sticky button.
- The Japanese kana card (`1ja_03`) is clean and large. A win.

### Session end (`1z_desk_summary.png`, `1z_phone_summary.png`)
- Issue (peak-end, Kluger & DeNisi): the first and largest tile is **"13% first try"** in
  gold, then +1 qi, +1 insight. For new items, a low first-try rate is *expected*
  (desirable difficulty), yet it is the headline. The copy under it is good ("A hard
  session is where memory is built") but is set in dim grey.
- Issue (competence/SDT): no list of *what* was learned ("You met: oui, non, merci,
  monsieur…"). Competence is shown as qi rather than as skill.
- Issue (overjustification, minor): qi is shown as a "+1" tile equal in weight to
  accuracy. The reward is small and informational, which is good, but the screen frames the
  session as an exchange.
- Win: "Return to the sect" is primary. "Keep going" is secondary, so there is a natural
  stop.
- Win: the disciples' lecture line ("Your disciples gathered to hear what you learned")
  is relatedness and game fiction done well.

### Library (`20_library_desk.png`, `_top`, `_mid`)
- **Issue (Von Restorff/Hick): 28 gold "Begin this course" buttons** in one flat
  alphabetical list, plus 3 gold "Study this art". Gold stops meaning "the next thing".
- **Bug (similarity): Japanese, Korean and Mandarin courses all show a blue "Fr"
  badge.** In academy.js, `HUE` (line ~889) maps faction `tongues_west` to `['#5bb6ff',
  'Fr']`, so every non-Spanish language gets "Fr". The same visual means different things.
- Issue (grouping): founding groups by language, but the library does not. Mandarin
  Conversations sits between Korean and Network+.
- Win: enrolled cards on top with progress bars and "memory 100%". "Set aside" is a link
  with a reassuring confirm ("your progress is kept").

### Trials and drills (`22_trials_desk.png`, `23_drill_setup_desk.png`)
- Win: the readiness checklist ("Ready for the real exam when all four are ticked") is a
  model goal-gradient plus honest-competence display.
- Issue (affordance/colour): locked "Quick trial" buttons are a dim brick-red. The active
  one is salmon-red. Red reads as danger or error. The unlock reason sits on a separate line
  ("Learn 7 more items to unlock"). Use a neutral disabled style with a lock icon and
  "7 more items".
- Issue: "Missed questions: 20 questions you got wrong" with a gold "Work through them".
  Mistakes are a good review source, but the count is shown on the home page, here and on
  Progress (three places).
- Win: the drill setup has sensible defaults (présent + passé composé, 40 commonest, 10
  questions), and the choices are remembered.

### Progress and settings (`25_progress_desk.png`)
- **Issue (punitive display): "Mistakes to put right", 20 rows**, each "**le chat** should
  be **bonjour**" with red "×4" badges. It shows the learner's wrong answers verbatim, in
  red, as a permanent list. That is self-focused negative feedback (Kluger & DeNisi's
  harmful kind). Collapse it to a count with "Review these" and show the items without the
  wrong answer.
- Bug: Japanese glyph mistakes show no prompt, only "×1 Japanese — A1 Beginner / so should
  be え".
- Issue: "0 minutes studied over 1 day" after two sessions (rounding or a missing secs
  sum).
- Issue (Jakob): **Settings live at the bottom of Progress**, below the mistake list. There
  is no gear and no nav entry. The streak-relevant "Seclusion" (holiday mode) is the 7th
  setting down.
- Win: the forecast bar chart of reviews coming due ("20 today, 3, 6…") makes spacing
  visible. The heatmap is gentle (brightness, no red).

### Read (`27_read_desk.png`, `28_poem_desk.png`, `28b_story_*.png`, `29_lookup_desk.png`, `29_lookup_phone.png`)
- Win: the best-designed section. Serif text at comfortable measure (about 60–70 ch),
  generous line-height, a quiet card that says "Tap a word…", a lookup docked beside on
  desktop and a bottom sheet on phone that never covers the tapped word. One gold button
  ("Save word").
- Issue (defaults): the starter shelf opens on **Spanish** for a learner enrolled in French
  and Japanese. "Language of the book" also defaults to Spanish.
- Issue (order): "Add a book" (file upload, the harder path) is above the ready-made
  starter shelf.
- Issue (lookup order): the warning "No French voice is installed on this device…" appears
  *above* the meaning in every lookup. Show it once per session, or below the senses.

### Sect tabs, event, scene (`32c_work.png`, `32c_build.png`, `32c_world.png`, `33_pawn_sheet_desk.png`, `31_scene_desk.png`)
- Win: the result scene (`31`) is a textbook peak-end moment: painted backdrop, "VICTORY",
  the people involved, one line per fact, a "+5 Fame" chip, one Continue.
- Win: the pawn sheet shows ledgers ("Why they feel this way −5/+5", "Cultivation speed
  ×1.75 × 1.1 × 0.92…"). Transparency is the genre's best answer to opaque systems.
- Issue (mapping/Jakob): the Work grid uses the RimWorld convention (1 = first, click
  raises, right-click or hold lowers). It is efficient for sim players and opaque to
  language learners. The 2-line legend has to be held in working memory. Consider a "Simple"
  mode (one main job per disciple) with the grid behind "Detailed priorities".
- Issue: the Build tab shows 6 gold "Build: …" buttons and 5 greyed ones. Affordable vs
  unaffordable is shown only by colour.
- The study panel follows every tab, which keeps study one scroll away. Good.

### Measurements
- Phone tap targets under 44 px: resource chips (35 px, tappable), speed buttons
  (42×40), hall labels (29–38 px), "Details ↓" (24 px), the "I know colony sims, skip" link
  (24 px), tabs (40 px). All meet WCAG 2.5.8 AA (24 px). Most miss the 44 px platform
  guidance.
- Contrast (dark theme): `--dim #b7a488` on `--bg` 7.98:1 and on surface 7.3:1. Gold
  button text 7.3:1. Salmon "seal" text 6.0:1. All pass AA. `--azure-d #2f6fa8` on surface
  is 3.3:1: fine for large text or borders only.
- Smallest text: hall labels 8.0 px (15 of them on phone), rate deltas 9.9 px, nav labels
  10.6 px.

---

## Part 3: Ranked changes (summary)

See the session report for the ranked list with effort. In short:

1. Put study first on the home view (one hero card above the hall). One gold button.
2. Fix the `.seal` CSS collision (wrong-answer Continue, phone overflow).
3. Rewrite the session-end screen: learned items first, accuracy reframed, end on success.
4. Turn the Progress "Mistakes" list into a count plus review, without the verbatim wrong
   answers.
5. One primary button per view: library "Begin this course" becomes secondary. Group the
   library by language. Fix the "Fr" badge.
6. Settings get their own place (a gear or a Progress tab). Holiday mode is easy to find.
7. Make streaks forgiving and weekly-first, and remove remaining loss-framed copy.
8. Decouple the lecture mood bonus from accuracy (avoid performance-contingent reward).
9. Make the elder's counsel tutorial skippable without shame, and keep it from blocking the
   top slot.
10. Chunk the unit notes. Add distractor-specific feedback on cert items.
11. Raise the minimum readable size (hall labels ≥ 11 px) and tap targets to 44 px on
    phone.
12. Smarter defaults in Read (the learner's language, starter shelf first). Neutral style
    for locked trials. Placement result framed for beginners.

## Sources

- Scheibehenne, Greifeneder & Todd (2010), choice-overload meta-analysis:
  https://abcwest.cogs.indiana.edu/pmwiki/pdf/scheibehenne.options.2010.pdf
- Deci, Koestner & Ryan (1999), Psych Bull 125(6): https://pubmed.ncbi.nlm.nih.gov/10589297/
- Unexpected rewards do not undermine: https://www.chicagobooth.edu/review/short-term-rewards-dont-sap-long-term-motivation
- Kivetz, Urminsky & Zheng (2006): https://business.columbia.edu/sites/default/files-efs/pubfiles/1200/goalgradient.pdf
- Ghibellini & Meier (2025), Zeigarnik/Ovsiankina meta-analysis: https://ideas.repec.org/a/pal/palcom/v12y2025i1d10.1057_s41599-025-05000-w.html
- Silverman & Barasch (2023), broken streaks, JCR: https://www.colorado.edu/business/faculty-research/2023/04/19/or-track-how-broken-streaks-affect-consumer-decisions ;
  https://www.psychologytoday.com/us/blog/ulterior-motives/202306/how-broken-streaks-sap-motivation
- Duolingo on streaks (first-party): https://blog.duolingo.com/how-duolingo-streak-builds-habit ; https://blog.duolingo.com/improving-the-streak
- Streak-reframing critique: https://uxdesign.cc/3-reframing-streaks-on-duolingo-5-ideas-for-a-more-healthy-and-flexible-approach-to-language-8fd89545771e
- Sailer & Homner (2020), gamification meta-analysis: https://link.springer.com/article/10.1007/s10648-019-09498-w
- Macnamara & Burgoyne (2023), growth mindset: https://pubmed.ncbi.nlm.nih.gov/36326645/ ; Sisk et al. (2018): https://englelab.gatech.edu/articles/2018/Sisk,%20Burgoyne%20et%20al.%20(2018)%20-%20Mindset%20and%20Academic%20Achievement.pdf
- WCAG 2.2 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- NN/g touch target via Roselli: https://adrianroselli.com/2019/06/target-size-and-2-5-5.html
- Doherty threshold: https://lawsofux.com/doherty-threshold/ ; attribution caveat: https://feelsfast.vercel.app/concepts/canonical-thresholds
- Deceptive patterns: https://nngroup.com/articles/deceptive-patterns/ ; https://ised-isde.canada.ca/site/office-consumer-affairs/en/types-dark-patterns
- From memory, not re-fetched [K]: Hick 1952; Hyman 1953; Cowan 2001; Sweller et al. 1998/2019;
  Palmer 1992; Murdock 1962; NN/g F-pattern 2006/2017; Fitts 1954; Kurosu & Kashimura 1995;
  Tractinsky 1997/2000; Norman (DOET); Ryan & Deci 2000; Fogg 2009; Lally et al. 2010;
  Kahneman et al. 1993; Redelmeier & Kahneman 1996; Zendle & Cairns 2018; Kahneman & Tversky
  1979; Johnson & Goldstein 2003; Jachimowicz et al. 2019; Kluger & DeNisi 1996; Hattie &
  Timperley 2007; Roediger & Karpicke 2006; Cepeda et al. 2006; Bjork & Bjork 2011; Hagger et
  al. 2016.
