# Competitor notes — IT / cyber-security certification prep

Research date: 2026-11-24. Purpose: what the successful Security+ / Network+ / ISC2 CC prep
products do better than Sect Academy's cert courses, and what an offline, no-AI, single-user app
can copy. Web research only.

**Evidence tags** (same scheme as `ui_inspiration.md`):

- **[S]** = read this session in a first-party source (vendor page, help centre). Link given.
- **[S3]** = sourced this session, but third-party: review blogs, forum posts, search-result
  summaries. Many of the review blogs are affiliate/SEO pages. Approximate.
- **[K]** = my recollection of the product from general knowledge. **Not verified this session.**
- **[I]** = my inference or recommendation.

**Read this before trusting section 2.** The coverage is weaker than the brief wanted:

- **No r/CompTIA thread was read directly.** Reddit and its mirrors were unreachable from this
  session, and searches returned blogs that *describe* Reddit consensus without linking threads.
  Every "Reddit says" below is therefore [S3] at best. The one first-hand community source was
  search snippets of CompTIA's own forum (cin.comptia.org) and Infosec Institute's forum.
- **No credible pass-rate figure exists for any product.** Every number found is a vendor claim
  or an unsourced blog figure (section 3).
- Pocket Prep's site (404) and CompTIA's help centre (403) could not be fetched; their details
  come from search summaries of those pages.
- Almost nothing was verified for Quizlet, Kaplan/Transcender, LinkedIn Learning, Cybrary,
  CertMaster Labs, subnettingpractice.com and subnetting.net. They are [K] throughout.

---

## 1. The short version

1. The products people credit with a pass are **practice-exam engines, not content libraries**.
   The repeated pattern is: one content source (Messer videos) plus one hard question bank (Dion,
   Boson, Messer's book), and the work that matters is reviewing every miss. [S3]
2. What separates the premium engines (Boson, MeasureUp, Pocket Prep) from the free ones
   (ExamCompass, Quizlet) is **what happens after you answer**: an explanation of why each wrong
   option is wrong, a score split by domain/objective, and a one-tap way to re-drill misses and
   weak areas. [S]
3. Sect Academy is already stronger than all of them on **scheduling** (none of the paid engines
   has real spaced repetition; Anki has it but with uneven shared decks) and on **blueprint-weighted
   mocks with a strict pass mark**. [I]
4. Its gaps, in order: thin post-answer feedback (one `why` per item), no review screen or
   missed-question bank after a mock, no weak-area targeting, no study mode, no PBQ-style items
   beyond ordering, no procedural drills (subnets, ports, acronyms), and a readiness check that
   **measures recall of seen questions rather than performance on unseen ones** (section 4, #2).
   [I]

---

## 2. Product by product

### Boson ExSim-Max — the reference design for an exam engine

- Every item has a question, answer and detailed explanation; "each explains not only why the
  correct answer is correct, but why the incorrect answers are wrong", with references. [S] —
  [Boson blog](https://blog.boson.com/what-separates-bosons-exsim-max-practice-exams)
- Two modes: **Study** (answers and explanations shown as you go) and **Simulation** (live-exam
  timing, nothing shown until graded). Custom exams can be built; questions can be sorted by
  category. [S] — same; [user guide](https://help.boson.com/exsim-max/practice-exams-user-guide)
- Simulates the exam's item types: multiple selection, drag and drop, matching, terminal
  simulations. Engine "designed to mimic the look and feel of the test delivery experience". [S]
- Score report on grading, split by category, compared with the pass mark. Boson's pages say
  category/domain/topic, not "objective". [S] — [product page](https://boson.com/?p=1453)
- Typically three exams per product; described by Boson as harder than the real exam; "No Pass –
  No Pay" guarantee. [S] (vendor claim)
- A support ticket can be opened from inside a question and goes to the item's author. [S]
- Complaints: price (roughly US$100 per exam product) and a Windows-era desktop client. [K]
- Community standing: gold standard for Cisco; respected but less used for CompTIA because Dion
  is a tenth of the price. [K]

### Jason Dion / Dion Training — the default Security+ / Network+ question bank

- Six 90-question timed exams per Udemy pack is the usual shape. [K] One review page says "90
  questions per exam" and implies six. [S3] —
  [prepforcerts](https://prepforcerts.org/jason-dion-practice-exams)
- Explanations cover why the right answer is right and why each wrong answer is wrong. [S3] — same
- Udemy's test player gives a per-domain ("knowledge area") breakdown after each attempt and
  lets you filter the review to wrong / flagged / skipped questions. [K] (The review page above
  found no domain breakdown, so this is contested.)
- PBQ walkthroughs and simulators: firewall rules, log analysis, topology, access control,
  vulnerability-scan reading, PKI. About 5–8 scenarios per cert, not randomised, simplified. [S3]
- Dion's own site: unlimited retakes, "dynamic question bank", randomised exams. [S] —
  [Dion Training](https://www.diontraining.com/collections/comptia-practice-test)
- Consensus: the most recommended practice exams; widely described as worded harder than the real
  exam, so scores run low. [S3] —
  [prepforcerts](https://prepforcerts.org/professor-messer-vs-jason-dion),
  [CompTIA forum](https://cin.comptia.org/goto/post?id=6456)
- Complaints: wordy or ambiguous stems; finite bank, so scores inflate on retakes through
  memorisation; Network+ pack needs extra subnetting practice. [S3], [K]

### Professor Messer — free videos, paid notes and practice exams

- Practice-exam book: three 90-question exams (A, B, C), multiple-choice plus performance-based
  questions, detailed explanations, ~380 pages. Course Notes follow the official objectives
  one-to-one. [S] — [Messer store](https://www.professormesser.com/sy0-701-success-bundle/)
- Each answer explanation carries the objective number and a link to the matching video. [K]
- Monthly live study groups work through questions aloud. [K]; a forum poster cites them. [S3]
- Consensus: the default content source; the objective-by-objective structure is the feature.
  Practice questions are considered close to the real exam's style. [S3], [K]
- Complaints: videos are dry; no hands-on; the exams are a PDF/book, so no engine, timing or
  analytics. [K]

### Pocket Prep — the mobile habit product

- About 1,000 Security+ questions; free tier of 30 questions and three modes. [S3] —
  [App Store listing](https://apps.apple.com/us/app/pocket-prep-comptia-security/id1089608501)
- Named modes: **Question of the Day**, **Quick 10**, **Timed Quiz**, **Weakest Subject Quiz**
  (questions from your lowest-scoring subject), **Missed Questions Quiz** (retake what you got
  wrong), build-your-own quiz, and "Level Up". [S3] for the first five; [K] for the last two.
- Every question has an explanation and a textbook reference. [K]
- Flagging, per-subject scores, and a comparison with other users' average. [K]; a store review
  mentions "wrong answers, flagged questions, and overall readiness". [S3]
- Exam date: the app asks for it and shows a countdown. [K] No source found this session.
- Complaints: questions easier than the real exam, no PBQs, subscription price. [K]

### CompTIA CertMaster (Learn / Practice / Labs / Perform)

- Practice is question-first: 8–10 questions per exam objective, and the learner **rates their
  confidence in each answer**; the system then gives tailored feedback and more questions on weak
  areas. [S3] —
  [CompTIA help](https://help.comptia.org/hc/en-us/articles/14358019090580-What-Is-CompTIA-CertMaster-Practice)
- Reporting: mastery score and objective-level views estimating preparedness from performance,
  question difficulty and recency. [S3] — same
- The exact confidence labels could not be verified.
- Labs/Perform: browser-based virtual machines with graded steps. [K]
- Complaints: one CompTIA-forum user calls the confidence rating subjective and not useful. [S3]
  Price is the standing complaint, and the community rarely recommends it over Messer + Dion. [K]

### MeasureUp (and Kaplan / Transcender)

- **Certification mode** (same question count and time limit as the real exam) and **Practice
  mode** (customisable); vendor advises Practice first. [S] —
  [MeasureUp docs](https://docs.measureup.com/knowledgebase/how-to-use-an-online-practice-test)
- Score report with a **breakdown by objective** and a "Preparation Tracker". [S] —
  [MeasureUp docs](https://docs.measureup.com/how-to-review-a-practice-test-score-report)
- Older versions listed Study, Custom, **Missed Question** and **Non-Duplicate** modes (the last
  serves only questions you have not seen). [S3]
- A pass guarantee exists; terms not read. [S3]
- Kaplan/Transcender: the Transcender brand was folded into Kaplan IT Training; same design
  family (study vs exam mode, per-objective reports, flash cards). [K] Nothing verified.

### ExamCompass — free, shallow, useful for drills

- Free 25-question topic quizzes with immediate scoring; counts reported inconsistently (60
  Security+ and 63 Network+ quizzes on one page). [S3] —
  [prepforcerts](https://prepforcerts.org/examcompass-review)
- Has dedicated **acronym quizzes** and **port/protocol quizzes**, which is why it is recommended
  for memorisation rather than exam simulation. [K]
- Complaints: easier than the exam, no score history, definition-heavy, thin explanations; "false
  confidence" if used alone. [S3]

### Anki shared decks / Quizlet

- Shared Security+ and Network+ decks exist (acronyms, ports, Messer-derived). Quality is uneven
  and authors stop maintaining them. [S3] —
  [Anki forum](https://forums.ankiweb.net/t/comptia-security-acronyms-deck/6493)
- A CompTIA-forum poster found Anki's setup too much for someone who just wants to study. [S3]
- Advice that making your own cards beats a downloaded deck is common but unsourced. [S3]
- Quizlet: huge supply of user sets, no quality control, wrong answers in sets, some sets are
  exam dumps. [K]
- Sect Academy already ships what Anki users have to assemble: a curated deck on FSRS. [I]

### Hands-on: TryHackMe, Hack The Box Academy, CertMaster Labs

- TryHackMe is the guided beginner platform; HTB is harder and less guided. [S3]
- Neither is built around the Security+ blueprint; hands-on labs are probably more than these
  exams need, since they test breadth of concepts. [I] They do help with PBQ confidence
  (reading logs, firewall rules, command output). [I]
- PBQ guides recommend practising firewall rules on a real firewall (pfSense, iptables); the
  commonest trap is rule order (top-down, first match wins, implicit deny at the end). [S3] —
  [Training Camp](https://trainingcamp.com/articles/comptia-security-performance-based-questions-what-they-are-and-how-to-prepare/)
- An offline app cannot run labs. It can simulate the *reading and deciding* part. [I]

### ISC2's own CC training

- Official self-paced course includes domain-by-domain study sheets, flash cards and a glossary;
  a 300+ question study eBook comes with some packages. [S3] —
  [ISC2](https://www.isc2.org/training/online-self-paced/cc-online-self-paced)
- Complaint: the course's quiz questions are easier and more definitional than the exam's
  scenario wording, so people add third-party practice tests. [K]
- The CC outline changed on 1 Sep 2026 (already covered in `cert_blueprints.md`); most
  third-party CC material is still written to the old one. [S]

### LinkedIn Learning / Cybrary

- Video-first courses with chapter quizzes; not credited with anything distinctive for these
  exams. [K] Not researched further.

### Subnetting trainers (subnettingpractice.com, subnetting.net and similar)

- Unlimited randomly generated questions by type: network address, broadcast address, first/last
  host, hosts per subnet, mask ↔ CIDR conversion. [K] Features of the two named sites were not
  verified this session.
- What forum users value: **typing** the answer rather than picking it ("forces me to get it
  right"), variety of question types, and being asked for every field of one subnet at once. [S3]
  — [Infosec forum](https://community.infosecinstitute.com/discussion/22995/subnetting-practice)
- A reported real-exam slip: forgetting the first subnet (x.x.x.0). [S3] — same forum
- For Network+ "you mostly need to know the basics", not CCNA-level speed. [S3]

---

## 3. Pass-rate claims: none is usable

| Claim | Source | Verdict |
|---|---|---|
| Boson "No Pass – No Pay" | Vendor [S] | A refund policy, not a pass rate. |
| Dion: students who pass two practice exams have a 96% pass rate (CISSP pack) | Vendor [S] | Self-reported, self-selected, no method. |
| "85% on Dion ≈ 90%+ on Security+"; Dion "5–10 points harder" | Blog [S3] | Rule of thumb; no data. |
| "60% of successful candidates name Dion as decisive" | Blog [S3] | Unsourced. Ignore. |
| "Book when scoring 80–85% on unseen practice exams" | Community heuristic [S3] | Unverified, but consistent across sources and matches this app's 85% bar. |

What can be said: the features in section 4 are the ones the market leaders converge on and that
candidates name when they explain a pass. That is convergence of design and testimony, not
measured effect. [I] The learning-science support for the underlying mechanisms (retrieval
practice, feedback on errors, spacing) is in `spaced_repetition.md`.

---

## 4. What Sect Academy should build — ranked

All of it works offline with no AI. Ranking is by expected effect on passing per unit of effort.
"How" is written against the current code: YAML items (`concept`, `mcq`, `multi`, `order`),
units carrying `domain`, one `why` per item, trials with no feedback until the end, FSRS state
per item. Effort: S = under a day, M = a few days, L = a week or more including content.

Everything in the "why it helps" and "how" columns is [I] unless tagged.

### 1. Trial review screen with per-domain breakdown and a missed-questions bank — S/M, very high

- **Competitor:** every engine (Boson, MeasureUp, Udemy, Pocket Prep "Missed Questions Quiz").
- **Why:** the review of misses is where candidates say the learning happens. A mock that ends
  in one percentage wastes 90 minutes of diagnostic data.
- **How:** store each finished trial's answers (item id, chosen, correct, seconds). Results page:
  score per domain against the blueprint weight, then every question filterable by wrong /
  flagged / all, each showing the learner's answer, the right one and `why`. Keep a per-course
  `missed` set; an item leaves it after two consecutive correct answers. Add a "Drill my misses"
  button that runs them in study mode (#4).
- **Data:** none new in packs. State: trial history (cap at the last 20) and the missed set.

### 2. A held-out mock pool, so readiness measures unseen questions — M, very high

- **Competitor:** MeasureUp's Non-Duplicate mode; the standing complaint about Dion's finite
  bank is score inflation from repeats. [S3]
- **Why:** the readiness checklist requires every item to be met before the mocks count. By then
  every mock question is one the learner has already seen and reviewed, so a trial score partly
  measures memory of the item rather than ability on a new scenario. This is the largest
  validity gap in the current design.
- **How:** mark a share of `mcq`/`multi`/`order` items per domain as `exam_only: true` (about 180
  per course gives two fresh full-length mocks). They never enter study sessions or placement.
  Trials draw unseen exam-only items first and fall back to the general pool. Report two numbers:
  "first-attempt score" (items never seen before this trial) and overall. Base the readiness
  rule on first-attempt scores. After a trial, its exam-only items join the normal pool.
- **Data:** one optional boolean per item; per-item "seen in trial" flag in state.
- **Cheaper first step (S):** record whether each trial question was previously seen and show the
  first-attempt score next to the total.

### 3. Explanations for every wrong option — engine S, content L, very high

- **Competitor:** Boson's defining feature; Dion and Messer do the same. [S], [S3]
- **Why:** these exams turn on near-neighbour distinctions. Knowing why the tempting distractor
  is wrong is the transferable part; one `why` often covers only the right answer.
- **How:** optional `why_not` on `mcq`/`multi`, a list parallel to `choices` (empty string for
  the correct ones). Show under each option after answering; fall back to `why`. Validator: if
  present, length must equal `choices`. Author in order of value: items with the highest miss
  rate first (#16 supplies the data), then the exam-only pool.
- **Data:** roughly 1,100 mcq items across the three courses × 3 distractors if done fully.

### 4. Study mode (custom quiz) alongside exam mode — S/M, high

- **Competitor:** Boson Study vs Simulation; MeasureUp Practice vs Certification; Pocket Prep
  build-your-own. [S]
- **Why:** today the only untimed, immediate-feedback practice is the FSRS session, which the
  learner cannot aim. Before a mock people want "20 questions on domain 4, feedback as I go".
- **How:** a builder with course, domain(s), item types, count, and source (all met / missed /
  flagged / low-confidence). Immediate feedback with explanations. Wrong answers go back to the
  FSRS queue as trials already do; right answers do not reschedule (keeps "only an issued item's
  first answer is scheduled"). Pays no qi, so the game invariant holds.
- **Data:** none.

### 5. Weak-area targeting by domain and objective — M, high

- **Competitor:** Pocket Prep Weakest Subject Quiz; CertMaster objective-level mastery;
  MeasureUp per-objective report. [S3], [S]
- **Why:** the domains are unequal and the learner's weakness is usually two or three objectives.
  Messer's whole structure is objective-by-objective for this reason. [K]
- **How:** add `objective: "2.4"` to cert units (or items where a unit spans several). Compute per
  objective: accuracy over the last N answers and mean FSRS retrievability. Progress page gets a
  table sorted weakest first with a "Drill" button (study mode filtered to that objective). Add a
  readiness condition: no domain below 75% on recent trials.
- **Data:** one field per unit; objective titles in the pack header (already in
  `cert_blueprints.md`).

### 6. Flag for review and free navigation inside a trial — S, high

- **Competitor:** the real CompTIA exam, and every simulator, has flag + review grid. [K]
- **Why:** standard advice is to flag PBQs and long questions and return. [S3 — see
  `cert_blueprints.md`] Pacing is a skill that needs rehearsal.
- **How:** numbered grid (answered / blank / flagged), previous/next, a review page before
  submit. Flags persist into the results filter (#1). Record seconds per question and show
  pacing afterwards (slowest five, time left).
- **Data:** none.

### 7. Confidence marking — S/M, medium-high

- **Competitor:** CertMaster Practice asks for confidence on every answer. [S3]
- **Why:** a lucky guess on a 4-option question is scored as knowledge. Existing notes already
  recommend a "missed + guessed" queue. One forum user found CertMaster's version subjective
  [S3], so keep it light and optional.
- **How:** three buttons on test items in study mode and trials: Sure / Think so / Guess. A
  correct Guess is graded Hard instead of Good and is added to the missed bank; a wrong Sure is
  highlighted in review ("confidently wrong"). Show a calibration line on Progress (accuracy
  when Sure vs when guessing). Off by default in daily sessions to keep them fast.
- **Data:** none. State: confidence stored with each answer.

### 8. Subnetting drill generator (Network+) — M, high for Network+

- **Competitor:** subnetting trainers; Dion's Network+ pack is said to need this added. [S3]
- **Why:** subnetting is a procedure; fixed items get memorised, a generator cannot be. Users
  value typed answers. [S3]
- **How:** `drills.py` with Python's `ipaddress` module. Question kinds: network address,
  broadcast, first/last host, usable hosts, CIDR ↔ dotted mask, "which subnet holds this host",
  "smallest prefix for N hosts", and an "all fields" form. Typed answers, graded server-side,
  with a worked solution (block size, the interesting octet). Levels: /24–/30, then /16–/23, then
  VLSM. Include the first subnet as an answer on purpose. [S3] Track accuracy and median time per
  kind; not FSRS-scheduled, but a streak of 10 correct per kind can count as a unit-style goal.
- **Data:** none.

### 9. Port and acronym drills generated from tables — S, medium-high

- **Competitor:** ExamCompass acronym and port quizzes; Anki acronym decks. [K], [S3]
- **Why:** both exams publish an acronym list, and ports are pure paired-associate memory.
- **How:** two small YAML tables per course: `ports` (number, protocol, TCP/UDP, secure
  counterpart) and `acronyms` (short, expansion, one-line meaning). Generate both directions,
  typed and 4-choice, with distractors taken from the same table (near numbers; acronyms sharing
  a first letter). Each row can be an FSRS card with a derived stable id (`np-port-443`), which
  respects the never-rename rule. Timed 60-second "speed round" as a no-stakes mode.
- **Data:** about 60 ports and 300–400 acronyms per CompTIA course from the public objectives.

### 10. PBQ-style item types: match/categorise first, then rule tables and log reading — M then L, high

- **Competitor:** Boson (drag and drop, matching, simulations), Dion's PBQ simulators, Messer's
  book PBQs. [S], [S3]
- **Why:** PBQs come first on the real exam and are the most-feared part; the app's only
  stand-in is `order`. The spec already lists this under "left for later".
- **How, in stages:**
  1. `match` (M): `pairs: [[left, right], ...]` or `buckets: {name: [items]}`. Tap an item, tap a
     bucket (works on touch, no drag library needed). Partial credit shown; the FSRS grade is
     Good only when all are right. Covers "match attack to description", "control to category",
     "port to protocol", "tool to purpose".
  2. `exhibit` (S): an optional monospace block on any item (log excerpt, config, scan output),
     so ordinary mcq/multi can ask "what does this log show?".
  3. `rules` (L): a firewall/ACL table with a scenario; the learner sets source, destination,
     port, action per row from dropdowns and orders the rows. Grade by **simulating** a list of
     test packets against the learner's rules (first match wins, implicit deny), not by comparing
     with one answer key, so any correct rule set passes. [S3] for the rule-order trap.
  4. `annotate` (M): pick the lines in a log that show the attack, or place devices in zones of a
     small fixed diagram.
- **Data:** new authored items; 15–25 PBQs per course is more than Dion ships (5–8). [S3]
- Trials should put 3–5 PBQ-type items first, to match reported exam shape. [S3, unverified]

### 11. Exam-date study plan — M, medium-high

- **Competitor:** Pocket Prep countdown [K]; MeasureUp Preparation Tracker [S].
- **Why:** an FSRS queue has no deadline. With a date, new-item rationing can be set so every
  item is met early enough to stabilise, with the last fortnight for mocks.
- **How:** optional exam date per course. Compute items left ÷ (days left − 14) to give the daily
  new-item quota (replacing the fixed 8, within a cap), and schedule checkpoints: quick trial
  weekly, full mocks at T-14, T-7, T-3. Show "on track / N items behind". In the last week, pull
  due dates forward so everything is reviewed once before the day. Never punish a missed day;
  just recompute.
- **Data:** none. State: one date per course.

### 12. Readiness as a trend, not only a checklist — S/M, medium

- **Competitor:** CertMaster mastery score (performance, difficulty, recency); community rule of
  consistent 80–85% on unseen exams. [S3]
- **Why:** the 4-point checklist is strict but binary, and says nothing about how far away the
  learner is or which condition is closest.
- **How:** keep the checklist, add a chart of trial scores over time with the 85% line, the
  first-attempt score (#2), and a per-domain floor (#5). State the distance in plain terms
  ("two more trials at 85% and domain 3 above 75%"). Do **not** show a predicted scaled score:
  CompTIA's scaling is unpublished, so any 100–900 mapping would be invented.
- **Data:** trial history from #1.

### 13. Link every explanation back to its notes and objective — S, medium

- **Competitor:** Messer's explanations cite the objective and video; Boson and Pocket Prep cite
  references. [K], [S]
- **Why:** a miss should lead to the teaching text in one tap.
- **How:** after any wrong answer show "Objective 2.4 · Unit: Social engineering → notes",
  opening the unit's Library entry. The unit is already known from the item.
- **Data:** none beyond #5's objective field.

### 14. Printable cheat sheets from unit notes — S, medium

- **Competitor:** Messer's Course Notes are his best-selling paid product; ISC2 ships
  domain study sheets. [S], [S3]
- **Why:** a last-week skim document, and the notes already exist as Markdown.
- **How:** a `/library/<course>/print` view with a print stylesheet: notes per domain, the ports
  and acronym tables from #9, and optionally "my weakest 30 items". The browser's print-to-PDF
  does the rest. No dependency.
- **Data:** none.

### 15. Quick modes: Question of the Day and Quick 10 — S, low-medium

- **Competitor:** Pocket Prep's free tier is exactly these. [S3]
- **Why:** a two-minute entry point on a bad day. The daily session partly covers it, so the
  gain is small; worth it only if it reuses study mode.
- **How:** "Quick 10" = ten due-or-missed test items in study mode. Question of the Day = one
  seeded-by-date item from the weakest objective on the home card.

### 16. Item statistics and a local "report this question" note — S, medium (for content quality)

- **Competitor:** Boson routes in-question tickets to the item author. [S] Dion's main complaint
  is ambiguous wording [S3], which a small app with ~3,000 items will share.
- **Why:** the spec lists an instructor pass as outstanding. Miss-rate data shows which items to
  check first and where to write `why_not` first (#3).
- **How:** per item, count attempts and misses; a hidden `/library/stats` page lists items with
  miss rate above 60% after five attempts. A "something's wrong with this question" button stores
  a free-text note locally; export as JSON for the author.

### 17. Multi-question scenarios — M, low-medium

- **Competitor:** case-study sets in MeasureUp/Boson for other vendors [K]; ISC2 CC lists
  "advanced item types". [S — `cert_blueprints.md`]
- **How:** a `scenario` text shared by 2–4 child items (`scenario: sy-sc-03` on each). Shown
  together in trials, scheduled separately. Useful mainly for incident-response and
  troubleshooting domains.

### 18. Searchable glossary — S, low

- **Competitor:** ISC2 glossary; Messer notes index. [S3], [K]
- **How:** all `concept` items plus the acronym table in one filterable Library list, each with
  its memory state.

---

## 5. Suggested order of work

1. #1 review screen + missed bank, #6 flag/navigation, and the cheap half of #2 (first-attempt
   score). One change to the trial flow; no content work.
2. #4 study mode, then #5 objective tags and weak-area drills, #13 links.
3. #9 ports/acronyms and #8 subnetting (independent of everything else).
4. #2 held-out pool proper, #12 readiness trend, #11 exam-date plan.
5. #10 PBQs: `match` and `exhibit` first; `rules` last.
6. #3 `why_not` authoring continuously, guided by #16.

## 6. What not to copy

- **Pass guarantees and predicted scaled scores.** Nobody's figures are credible, and the app's
  spec already says it "cannot guarantee a pass". [I]
- **Bank size as a goal.** Pocket Prep has ~1,000 Security+ questions and Dion ~540 [S3], [K];
  the app already has more test items than either. Quality of explanation and unseen-question
  measurement matter more. [I]
- **Video and real labs.** Out of scope offline; recommend Messer's free videos and a home
  firewall VM in the README instead. [I]
- **Leaderboards / comparison with other users** (Pocket Prep). Single-user app. [I]
- **Mandatory confidence rating on every question** (CertMaster): the one user complaint found.
  [S3]

## 7. Unverified or missing — check before relying on it

- Any statement about r/CompTIA consensus (no thread read directly).
- Pocket Prep's exam-date feature and "Level Up" mode; Udemy's per-domain breakdown for Dion's
  exams; ExamCompass's acronym and port quizzes; Messer's per-answer video links. All [K].
- Whether Dion Training offers free browser PBQ simulators (one blog says so; not confirmed).
- CertMaster's confidence labels and the current (2026) product line-up and prices.
- Feature lists of subnettingpractice.com and subnetting.net.
- The number and position of PBQs on the real exams (forum reports: 5–6 on Network+; CompTIA
  does not publish this).
- Whether any SY0-801-specific question bank is mature yet; most third-party pages found still
  describe SY0-701.
