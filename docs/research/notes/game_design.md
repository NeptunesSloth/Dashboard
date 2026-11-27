# Game design for a study-driven sect-management game (single player, self-hosted, no monetisation)

Reading notes for the report writer:
- "Cited Findings" are things I retrieved in this session. Where I only saw a search-result excerpt and not the full page, the bullet says "(excerpt only)".
- "Inferences" contain my design proposals and suggested numbers. Those numbers are starting values to playtest, not measured results.
- Several well-known facts could not be re-verified in the time available (paywalled or 503). They are listed under "Gaps" as unverified, not as findings.

## 1. What the research literature says about gamification in learning

### Takeaway
Meta-analyses agree gamification has a positive but small-to-medium average effect on learning (g roughly 0.5 on cognitive outcomes, about 0.36 on motivation), with high heterogeneity and weaker, less stable evidence for motivation and behaviour. The main documented risk is expected, tangible, performance-contingent rewards undermining intrinsic motivation (d about -0.3 to -0.4), whereas informational positive feedback raises it (d about +0.3), so the game layer should behave as feedback about competence, not as payment for volume.

### Cited Findings
- Sailer & Homner (2020, Educational Psychology Review): cognitive learning outcomes g = .49, 95% CI [0.30, 0.69], k = 19, N = 1686; motivational outcomes g = .36, 95% CI [0.18, 0.54], k = 16, N = 2246 (excerpt only) — [Springer](https://link.springer.com/article/10.1007/s10648-019-09498-w)
- Same paper: the cognitive effect was stable in a sub-split of high-rigor studies; effects on motivational and behavioural outcomes were less stable (excerpt only) — [Springer](https://link.springer.com/article/10.1007/s10648-019-09498-w)
- Same paper: game fiction (narrative) and social interaction were significant moderators for behavioural learning outcomes (excerpt only) — [Univ. Augsburg repository record](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/index/index/docId/109056)
- Bai, Hew & Huang (2020, Educational Research Review): overall Hedges' g = 0.504, 95% CI [0.284, 0.723], 30 independent interventions from 24 studies, no publication bias detected; no significant differences by type or number of game elements, but effects varied with sample size and intervention duration (excerpt only) — [UZH reference page](https://www.gbl.uzh.ch/quartz/references/Bai-et-al.-(2020))
- Li, Ma & Shi (2023, Frontiers in Psychology): larger pooled effect g = 0.822 [0.567, 1.078], 41 studies / 49 independent samples (excerpt only). This is notably higher than the two 2020 meta-analyses; treat the true average as uncertain, somewhere in the small-to-large band — [Frontiers](https://www.frontiersin.org/articles/10.3389/fpsyg.2023.1253549/full)
- Deci, Koestner & Ryan (1999, Psychological Bulletin, 128 experiments): tangible rewards undermined free-choice intrinsic motivation; the abstract reports d = -0.40, -0.36 and -0.28 for three contingency types (engagement-, completion- and performance-contingent, in the abstract's order; the search excerpt was truncated before the labels, so verify the pairing). Positive verbal feedback enhanced free-choice behaviour (d = 0.33) and self-reported interest (d = 0.31). Tangible rewards were more harmful for children than for college students — [PubMed](https://pubmed.ncbi.nlm.nih.gov/10589297/)
- The Deci et al. conclusion is contested: Cameron & Pierce (1994) argued negative effects are limited and avoidable; a later reanalysis found negative effects on high-interest tasks when rewards are tangible, expected and only loosely tied to performance level (excerpt only) — [Springer, Behavior Analyst](https://link.springer.com/doi/10.1007/BF03392017)
- Hanus & Fox (2015, Computers & Education 80:152-161): a semester-long course with leaderboard + badges versus the same course without. The gamified group reported lower motivation over time, and the effect on final exam scores was mediated by intrinsic motivation. The authors attribute the harm to rewarding an already-interesting task, not to the specific elements (abstract via secondary sources only; single course, not replicated) — [citing review, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8916940)
- Mekler et al. (image-annotation task): points, levels and leaderboards significantly increased performance (quantity) but did not affect perceived autonomy, competence or intrinsic motivation (excerpt only) — [Univ. Basel dissertation](https://edoc-vmtest.ub.unibas.ch/44253/1/diss_emekler_ub_noCV.pdf)
- Leaderboards may produce anxiety or frustration in learners who struggle with competition (secondary citation of Hanus & Fox in an accepted manuscript) — [Univ. Essex repository](https://repository.essex.ac.uk/41011/1/Jabbari%2C%20Zarrinabadi%2C%20%26%20Amini%20%28accepted%20copy%29.pdf)

### Inferences
- Points/levels reliably raise the *quantity* of behaviour (Mekler) without touching intrinsic motivation. In a learning app that is exactly the grinding risk: if points pay for volume, volume is what you get. Rewards must therefore be keyed to quality signals (recall accuracy, retention, mastery checks).
- The Deci reanalysis result (harm is worst when rewards are tangible, expected, and loosely tied to performance) gives a concrete rule: make rewards informational and tightly tied to demonstrated competence; add some unexpected rewards; never pay simply for showing up for a long time.
- Game fiction was a significant moderator of behavioural outcomes, which supports investing in the sect narrative (disciples, halls, tribulations) rather than bare points and badges.
- Leaderboards are the element with the clearest downside evidence, and this is a single-player app, so omit them. If a comparison is wanted, compare against the learner's own past self (personal bests, last week's retention).
- SDT mapping for this product (design proposal): autonomy = the learner chooses the track, the daily commitment size, and which hall to build; competence = honest mastery feedback and gates passed by real tests; relatedness = named disciples/NPCs with reactions, since there are no other humans.
- Bai et al. found duration moderates the effect. Novelty decay should be expected; plan new systems to unlock over months rather than front-loading everything.

### Gaps
- Sailer & Homner's behavioural effect size and full moderator table could not be retrieved (Springer redirected to a login, the Augsburg PDF returned 503). My unverified recollection is g = .25, 95% CI [0.04, 0.46], k = 9, N = 951 for behavioural outcomes; verify before quoting. One excerpt also conflicted on whether publication bias was assessed.
- No source was retrieved for Zainuddin et al. (2020, Educational Research Review systematic review). Unverified recollection: it is a qualitative systematic review, not a meta-analysis, so it has no pooled effect size; it reports mostly positive findings on engagement and motivation with points/badges/leaderboards the most-used elements.
- I did not retrieve a meta-analysis that isolates effects of individual elements (points vs badges vs narrative vs progress bars); Bai et al. found no significant differences by element type.
- No primary SDT source (Ryan & Deci) was fetched; the SDT mapping above is my application, not a cited result.

## 2. How existing products tie real effort to game progress; failure modes and mitigations

### Takeaway
The products that retain best make the daily unit of effort very small and protect it with forgiveness mechanics (freezes, rest mode), and the published numbers show that *lowering* the bar for keeping a streak raises retention. Documented hard evidence on harms (streak anxiety, XP farming) is thin: it is mostly journalism and commentary, not controlled studies.

### Cited Findings
Duolingo (all company-reported, internal A/B results, not independently verified):
- Learners who reach a 7-day streak are 2.4 times more likely to continue using Duolingo the next day than learners without a streak — [Duolingo blog, Improving the streak](https://blog.duolingo.com/improving-the-streak)
- A different Duolingo post says learners who reach a 7-day streak are 3.6 times more likely to complete their course. The two figures measure different outcomes (next-day return vs course completion); both are correlational — [Duolingo blog, How the streak builds habit](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- Separating the streak from the daily XP goal, so that one lesson per day extends the streak: Day-14 retention +3.3%, daily active learners +1%, daily learners on a streak +10.5% within 20 days (+19% among new learners), all relative changes. Learners on a 7+ day streak rose by over 40%; about a year later just over half of daily learners had a 7+ day streak versus about a third before. Side effect: fewer learners hit their daily goal — [Duolingo blog, Improving the streak](https://blog.duolingo.com/improving-the-streak)
- Learners with the highest ("intense") daily goal were the least likely to be on a streak: almost 40% of learners who were active two days running but had no streak had that goal — [Duolingo blog, Improving the streak](https://blog.duolingo.com/improving-the-streak)
- Allowing two Streak Freezes to be equipped at once raised daily active learners by +0.38% (relative) "without encouraging more days off" — [Duolingo blog, How the streak builds habit](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- A new streak-extension animation raised 7-day retention of brand-new learners by +1.7%; over 6 million people were on a streak of 7+ days at the time of the post — [Duolingo blog, How the streak builds habit](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- The same post notes the motivational value of each added day shrinks proportionally (2 to 3 days is +50%, 200 to 201 is +0.5%), which is why milestones and extra mechanics are layered on long streaks — [Duolingo blog, How the streak builds habit](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- Streak Wager (bet gems on keeping a 7-day streak) increased Day-1, Day-7 and Day-14 retention, with Day-7 the largest at +14% (excerpt only) — [Making Duolingo](https://making.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals)
- Daily goal tiers reported by third-party guides: time-based on mobile (Casual 5, Regular 10, Serious 15, Intense 20 minutes/day) and XP-based on desktop (10/20/30/50 XP). Sources conflict and the options have changed over time — [lingoly.io guide](https://lingoly.io/change-duolingo-daily-goals/); [Duolingo fan wiki, XP](https://duolingo.fandom.com/wiki/XP)
- Streak anxiety: reported in journalism (a user describing anxiety when the streak is unfinished late in the day; a psychologist saying breaking a habitual streak can create stress), not in a controlled study — [Gulf Today / The Independent](https://gulftoday.ae/Opinion/2023/11/06/The-language-app-you-just-cant-put-down)
- A UX critique proposes reframing streaks toward more flexible measures (opinion piece) — [UX Collective](https://uxdesign.cc/3-reframing-streaks-on-duolingo-5-ideas-for-a-more-healthy-and-flexible-approach-to-language-8fd89545771e)
- A press critique describes Duolingo's XP boost as a UX trap (headline-level only; article not read) — [Android Authority](https://androidauthority.com/duolingo-xp-boost-ux-trap-3674572)

Habitica:
- Missed Dailies cost health at day rollover; Dailies that have turned red or are marked Hard deal much more damage than Easy/blue ones; trivial Dailies give less gold and deal less damage when missed (excerpt only) — [Habitica wiki FAQ](https://habitica.fandom.com/wiki/FAQ)
- On a boss quest, Boss Damage = (Dmg / 2) x Boss Strength, applied to all participants, so the player is hit twice for their own missed Dailies (excerpt only) — [Habitica wiki](https://habitica.fandom.com/wiki/Habitica_Wiki)
- Forgiveness mechanic: "Rest in the Inn" / Pause Damage — while resting, missed Dailies do no damage and the player loses no health or streaks. The wiki page flags itself as partly outdated — [Habitica wiki, Rest in the Inn](https://habitica.fandom.com/wiki/Rest_in_the_Inn)
- Losing all HP causes "death" with losses (page located, details not read) — [Habitica wiki, Death](https://habitica.fandom.com/wiki/Death)

Forest:
- A focus session grows a tree; the app "penalises you by withering your tree" if you break focus. Coins come from focus time (a user reports under half a coin per minute); the developer says longer sessions and achievements give more — [App Store listing](https://apps.apple.com/us/app/id866450515)

Zombies, Run!:
- During real runs the player gathers supplies and rescues survivors, and must speed up when chased (excerpt only) — [App Store story](https://apps.apple.com/gb/story/id1748181882)

Anki:
- FSRS exposes a "desired retention" setting; community guidance is to raise it if intervals feel too long and lower it if too short, and there is forum debate about the default (excerpt only) — [Anki forums, FSRS category](https://forums.ankiweb.net/c/anki/fsrs/19?page=3)

### Inferences
- The strongest published lever is counter-intuitive: decoupling "kept the habit today" from "hit an ambitious target" increased retention, and the most ambitious goal setters were the most likely to lose their streak. For this app: one small valid session (for example clearing due reviews or 5 minutes) keeps the daily chain; bigger goals are optional bonuses.
- Forgiveness mechanics raise activity slightly without increasing skipped days (Duolingo's two-freeze result). Habitica's Inn shows the fully voluntary version. For a single adult with no monetisation, make rest free and explicit: automatic grace days plus a "closed-door seclusion" (vacation) mode that pauses everything.
- Punishment designs (Habitica HP loss, Forest's withered tree) work through loss aversion. They are the likeliest cause of guilt-driven churn: once the player "dies" or the chain breaks, returning is aversive. Proposal: nothing the player built is ever destroyed. Absence only lowers a temporary multiplier (see section 5), and the first session back gives a welcome-back bonus.
- Zombies, Run! is the cleanest model for this project: real effort yields a resource (supplies) that is spent in a separate, low-pressure management layer. Study yields the scarce resource; the sect layer is where it is spent, at leisure.
- XP farming arises when the cheapest repeatable activity pays the same as hard work. Mitigations to build in from day one: pay per *scheduled* item rather than per action, zero or tiny pay for repeating already-mastered material, daily soft cap, and no timed "double XP" windows that encourage binges.
- Duolingo's results are relative percentage changes from a company optimising daily active users. They show what keeps people opening the app, not what makes them learn more. Use them for habit mechanics only.

### Gaps
- No controlled study measuring streak anxiety or guilt-driven churn among language-app users was found; evidence is anecdotal.
- No source found on XP farming in Duolingo leagues, on hearts, on friend quests, on streak-freeze *introduction* effects, on Weekend Amulet outcomes, or on the count of daily quests (commonly three, unverified).
- Habitica's exact non-boss damage formula, gold/XP formulas, task-value/colour decay and pet/drop rates were not retrieved. The code is open source, so these can be read from the repository if needed.
- Zombies, Run! base-building details (what supplies buy) were not confirmed. Forest: not confirmed whether coins are lost when a tree withers.
- Anki FSRS default desired retention (commonly stated as 0.90) was not confirmed from official documentation. No source retrieved on specific Anki gamification add-ons.
- Independent research on Duolingo learning efficacy (as opposed to retention) was not searched.

## 3. Core loops and standard formulas in idle / incremental and cultivation management games

### Takeaway
Idle games run on a small set of formulas: exponential building cost (base x r^owned, with r = 1.07 in AdVenture Capitalist and 1.15 in Cookie Clicker), linear production boosted by milestone multipliers, capped offline income (2 hours in Egg, Inc.; 12 to 18 hours in Melvor Idle), and prestige currency as a root of earnings. Because cost is exponential and production is roughly linear or polynomial, progress always stalls, and the stall is the designed moment for a new unlock or a reset.

### Cited Findings
- Cost of the next generator: cost_next = cost_base x rate_growth^owned. Total production = (production_base x owned) x multipliers — [Pecorella, The Math of Idle Games Part I](https://gamedeveloper.com/design/the-math-of-idle-games-part-i)
- Bulk cost for n more with k owned: cost = b x r^k x (r^n - 1) / (r - 1). Max affordable with currency c: floor( log( c(r - 1) / (b x r^k) + 1 ) / log(r) ). Valid only for plain exponential costs — [Pecorella Part I](https://gamedeveloper.com/design/the-math-of-idle-games-part-i)
- AdVenture Capitalist lemonade stand: growth rate 1.07, base cost 4 (technically 3.738 because the first is free), base production 1.67/sec; x2 production multipliers at 25 and 50 owned, stacking — [Pecorella Part I](https://gamedeveloper.com/design/the-math-of-idle-games-part-i)
- Cookie Clicker: price = base cost x 1.15^(owned - free), rounded up; each purchase costs 1.15 times the previous one — [Cookie Clicker wiki](https://cookieclicker.wiki.gg/wiki/Buildings)
- Another designer's worked example also uses x1.15 cost per level — [Eric Guan, Idle Game Design Principles](https://ericguan.substack.com/p/idle-game-design-principles)
- Prestige resets generators and multipliers in exchange for a persistent currency or multiplier, like a New Game+; each prestige lets the player get further along the cost curve — [Pecorella Part I](https://gamedeveloper.com/design/the-math-of-idle-games-part-i)
- Prestige formulas: Realm Grinder p = (sqrt(1 + 8 x c_max / 10^12) - 1) / 2 (doubling prestige needs about 4x earnings); AdVenture Capitalist p = 150 x sqrt(c_lifetime / 10^15) (about 3x to 4x); Cookie Clicker p = cuberoot(c_lifetime / 10^12) (about 8x); Egg, Inc. delta-p = (c_run / 10^6)^0.14 (about 128x) — [Pecorella, Math of Idle Games Part III](https://gamedeveloper.com/design/the-math-of-idle-games-part-iii)
- Offline progress: Egg, Inc. caps offline play at 2 hours, which reduces reliance on idle earnings and shifts players toward active play; Clicker Heroes has no offline limit — [Pecorella Part III](https://gamedeveloper.com/design/the-math-of-idle-games-part-iii)
- Melvor Idle offline cap: a third-party guide says 18 hours; an early patch note says 12 hours. Sources conflict, the patch note is old — [itemlevel.net](https://itemlevel.net/is-melvor-idle-online-only/); [Melvor wiki v0.16.2](https://wiki.melvoridle.com/w/V0.16.2)
- Pacing advice: choose the prestige formula deliberately (root formulas give steady gains, flat exponents push toward active play); make cycles uneven with slow and fast stretches; expect wide variance in player behaviour; iterate; identify whether the fun is unlocking, collecting or optimising — [Pecorella Part III](https://gamedeveloper.com/design/the-math-of-idle-games-part-iii)
- Amazing Cultivation Simulator: realm order Qi Refining > Foundation > Golden Core > Nascent Soul, each with three steps (player comment). Golden Core formation converts accumulated progress into core *quality*; the two things that matter are max Qi and conversion rate, at 30 qi per second during the breakthrough — [Steam discussion](https://steamcommunity.com/app/955900/discussions/0/4355621251098840967); [re-actor guide](https://re-actor.net/amazing-cultivation-simulator-golden-cores-for-dummies)

### Inferences
- The requested "typical growth factor 1.07 to 1.15" is supported at both ends by named games (AdVenture Capitalist 1.07, Cookie Clicker 1.15) but no source I read states it as a range.
- In a study-driven game the player earns a bounded amount per day (10 to 20 minutes of study), not an exponentially growing income. Classic idle curves assume income compounds. So use much flatter curves than commercial idlers, or the game stalls in the second week. Proposal: building level cost = base x 1.15^level for a short ladder (5 to 10 levels per hall), and make the hard gates mastery checks, not currency.
- Worked check (my arithmetic): at r = 1.15, level 10 costs about 4.05x level 0 and the first 10 levels cost about 20.3x base in total. At r = 1.07 the same figures are about 1.97x and 13.8x. If a day's study yields roughly 100 stones and a hall's base cost is 100, a 10-level hall takes about 20 study days at 1.15 or about 14 at 1.07. That is a sensible pace for one hall; tune base cost per hall tier.
- ACS's Golden Core quality mechanic is a strong template: the *quality* of a breakthrough depends on what was accumulated before it. Map this to study: breakthrough quality = mock-exam score or measured retention at the moment of the attempt, giving a permanent but modest bonus.
- Prestige resets fit poorly with real knowledge (you cannot un-learn). Proposal: replace prestige with "ascension to a new track/level" (finishing CEFR A2 and opening B1, or passing one cert and starting the next), which carries the sect forward and opens a new realm tier instead of wiping it.
- Egg, Inc.'s 2-hour cap shows a short offline cap pushes active play. For a once-a-day habit, cap passive accrual at about 24 hours so a daily visitor loses nothing, while a week away accrues no more than a day.
- Random events and recruitment: with no monetisation, "gacha" should be a deterministic or pity-bounded recruit roll paid with study-earned tokens. Give no paid currency and no time-limited banners.

### Gaps
- Kittens Game price ratios, Melvor Idle's current official offline cap and mastery formulas, and Clicker Heroes specifics were not retrieved.
- No reliable wiki data retrieved for mobile sect-building idlers, "Immortal Life", or ACS tribulation and disciple-rank mechanics. Random-event and recruit-rate numbers from those games are unsourced.
- Pecorella Part II (alternative growth models, derivative-based generators) was not read.
- No source gives recommended unlock pacing in minutes or sessions; idle-game pacing is typically tuned by spreadsheet simulation.

## 4. Cultivation-novel realm ladders and sect vocabulary

### Takeaway
The realm ladder varies by novel, but the first four rungs are near-universal: Qi Condensation (or Qi Refining), Foundation Establishment, Core Formation (or Golden Core), Nascent Soul, usually with sub-stages inside each. That gives a ready-made two-level progress structure (sub-stage = routine progress, realm = gated breakthrough).

### Cited Findings
- Most sources agree on the core sequence Qi Condensation > Foundation Establishment > Core Formation > Nascent Soul; names vary by work ("Qi Refining" for Qi Condensation, "Golden Core" for Core Formation) — [Wuxiaworld glossary, A Pawn's Passage](https://www.wuxiaworld.com/page/a-pawns-passage/cultivation-level-glossary); [Wuxiaworld, Introduction to xianxia](https://www.wuxiaworld.com/page/introduction-to-chinese-webnovel-genres-xianxia)
- One novel's full list: Unborn (no Qi) > Qi Gathering > Qi Condensation > Foundation Establishment > Core Formation > Astral Manifestation > Divine Transfiguration — [Wuxiaworld, Divine Medallion of Seven Lifetimes](https://www.wuxiaworld.com/page/divine-medallion-of-seven-lifetimes/list-of-cultivation-levels-volume-1)
- A Nascent Soul forms when a core reaches sufficient density and is reshaped — [Xian Ni wiki](https://xian-ni.fandom.com/wiki/Nascent_Soul)
- Sub-stage convention and quality carry-over: a cultivator must reach "Great Perfection" of Foundation Establishment before Core Formation, and Golden Core quality affects the success rate of the Nascent Soul breakthrough (fan reference site, excerpt only) — [mortalsjourney fan site](https://mortalsjourney-com.pages.dev/en/realms/03-core-formation)
- ACS uses Qi Refining > Foundation > Golden Core > Nascent Soul with three steps per realm — [Steam discussion](https://steamcommunity.com/app/955900/discussions/0/4355621251098840967)

### Inferences
- Suggested ladder for the app (design proposal): Mortal > Qi Condensation > Foundation Establishment > Core Formation > Nascent Soul > (later) Soul Transformation and beyond, each with early / middle / late / Great Perfection sub-stages. Sub-stages advance with ordinary study; a realm change requires a tribulation, which is a mastery test.
- Suggested mapping of genre vocabulary to study mechanics (design proposal; vocabulary is genre convention that I did not source individually):
  - Sect master = the learner. Disciples = topics, decks or skill units; a disciple's rank (outer > inner > core > elder) reflects the measured mastery of that unit.
  - Spirit stones = main currency, earned only from study. Contribution points = secondary currency from quests and weekly goals.
  - Spirit vein = the passive generator whose output is scaled by the study multiplier.
  - Scripture Pavilion = new-material lessons and reading. Training grounds / Sword Hall = review drills. Alchemy Hall = turning mistakes into "pills" (a leech or missed-item remediation queue). Trial tower / secret realm = timed mixed quizzes. Tribulation = mock exam or level test. Closed-door seclusion = vacation mode. Inner demons / qi deviation = overdue-review backlog, cleared through study, never a permanent loss. Dao heart = streak or consistency measure.
- The project already has `cultivation.py` (XP/realm ladder, spirit stones) per CLAUDE.md, so the vocabulary fits the existing theme.

### Gaps
- No sourced reference was retrieved for sect structure terms (outer/inner/core disciples, elders, Scripture Pavilion, Alchemy Hall, spirit veins, contribution points, tribulations). They are widely used genre conventions but are uncited here.
- Ladders beyond Nascent Soul differ a lot between novels; there is no canonical list.

## 5. Mapping rewards to learning behaviours so the best game strategy is the best study strategy

### Takeaway
No source I retrieved tests this mapping directly; this section is design reasoning built on sections 1 to 3. The principle is: pay for evidence of retained knowledge on scheduled material, cap volume, and make every large gate a real assessment.

### Cited Findings
- Points and levels raise output quantity without raising intrinsic motivation, so volume-based pay invites grinding — [Mekler et al., Univ. Basel](https://edoc-vmtest.ub.unibas.ch/44253/1/diss_emekler_ub_noCV.pdf)
- Reward harm is greatest when rewards are tangible, expected and loosely tied to performance; positive competence feedback helps (d about +0.3) — [Behavior Analyst reanalysis](https://link.springer.com/doi/10.1007/BF03392017); [Deci, Koestner & Ryan 1999](https://pubmed.ncbi.nlm.nih.gov/10589297/)
- The most ambitious daily goals correlate with losing the habit; a minimal daily unit raises retention — [Duolingo blog](https://blog.duolingo.com/improving-the-streak)
- A hard offline cap shifts players toward active play — [Pecorella Part III](https://gamedeveloper.com/design/the-math-of-idle-games-part-iii)
- Breakthrough quality determined by what was accumulated beforehand (ACS Golden Core) — [re-actor guide](https://re-actor.net/amazing-cultivation-simulator-golden-cores-for-dummies)

### Inferences
All numbers below are proposed starting values, to be tuned by playtest.

Economy rules:
- Only scheduled work pays. A due review pays full value; a new item pays less (for example review 3 stones, new item 2) and new items per day are capped by the scheduler (for example 10 to 20). Extra practice on items that are not due pays about 10%, enough to feel acknowledged, not enough to farm.
- Pay for honest recall, not for pressing "correct". Pay the same for an honest "forgot" as for a success on that card (the review itself is the valuable act), then add an accuracy/retention bonus at session level based on test-style items (typed answers, cloze, multiple choice) that cannot be self-graded. This removes the incentive to lie on self-graded cards.
- Retention bonus: weekly payout scaled by measured retention against the target band (for example 85% to 92%). Pay nothing extra above the band, since 100% retention usually means the material is too easy or the intervals too short.
- Daily diminishing returns: 100% value up to the daily commitment (10 to 20 minutes or the due queue), 50% for the next equal block, 10% after that. No binge bonuses and no timed double-XP.
- Study multiplier on passive income: starts at 1.0, rises with each study day (for example +0.1 per day to a cap of 2.0), holds through grace days, then decays about 10% per missed day down to a floor of 0.5. It never reaches zero and never destroys buildings or disciples.
- Offline accrual capped at 24 hours of spirit-vein output, multiplied by the study multiplier. Passive income should be a minority of total income (aim for at most 20% to 30%) so study remains the only meaningful source.
- Mastery gates: hall tier N+1 requires both stones and a demonstrated outcome (for example a stated share of the unit's items at mature interval, or a unit test at or above 80%). Realm breakthroughs require a tribulation = mock exam or level test. Score sets breakthrough quality (a modest permanent bonus). Failure costs nothing except a short cooldown and produces a targeted remediation list.
- Boss fights = mock exams or mixed cumulative quizzes, scheduled at spaced intervals; boss "damage" comes from correct answers on previously weak items.
- Backlog handling: if overdue reviews exceed a threshold, the game offers a "stabilise qi" plan that spreads them over several days and pays normally, instead of presenting a punishing wall.
- Anti-gaming checks: minimum answer latency and suspiciously fast streaks pay nothing; resetting a deck gives no re-earn; currency cannot buy mastery.

### Gaps
- No empirical study was found that compares reward schemes (accuracy-based vs volume-based) inside a spaced-repetition product.
- Evidence for spacing and retrieval practice themselves (the learning-science basis for prioritising due reviews) was outside what I retrieved; another researcher's notes should cover it.
- The target retention band and all payout numbers are my proposals, not sourced values.

## 6. Session size, reward cadence and first-session experience for a 10 to 20 minute daily habit

### Takeaway
Published product data supports a very small minimum daily unit plus optional stretch goals, forgiveness built in, and a visible celebratory moment when the day's unit is done. Specific numbers for quest counts and onboarding flows are mostly not published, so the cadence below is a proposal.

### Cited Findings
- Requiring only one lesson to extend the streak (rather than the full daily goal) raised Day-14 retention by 3.3% and streak participation by 10.5%, at the cost of fewer learners reaching their daily goal — [Duolingo blog](https://blog.duolingo.com/improving-the-streak)
- Duolingo's goal tiers correspond to roughly 5, 10, 15 and 20 minutes per day (third-party guide; sources conflict) — [lingoly.io guide](https://lingoly.io/change-duolingo-daily-goals/)
- A celebratory streak animation shown after the session raised 7-day retention of new learners by 1.7% — [Duolingo blog](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- Reaching a 7-day streak is the retention inflection Duolingo optimises for (2.4x next-day return; correlational) — [Duolingo blog](https://blog.duolingo.com/improving-the-streak)
- Marginal motivation per added streak day shrinks as streaks lengthen, so long streaks need milestones — [Duolingo blog](https://blog.duolingo.com/how-duolingo-streak-builds-habit)
- Idle-game pacing should alternate slow and fast stretches rather than be uniform — [Pecorella Part III](https://gamedeveloper.com/design/the-math-of-idle-games-part-iii)

### Inferences
Proposed loop (starting values):
- Daily session shape, 10 to 20 minutes: (1) open, collect capped offline income, see one short event (under 30 seconds); (2) due reviews (5 to 10 minutes); (3) a small batch of new material (3 to 8 minutes); (4) spend earnings on one meaningful sect decision (about 1 minute); (5) end screen showing what was learned and what is due tomorrow. Game actions should take well under a quarter of the session.
- Minimum unit that keeps the chain: clearing due reviews or 5 minutes, whichever comes first. The 10 to 20 minute target is a stretch goal, never a requirement.
- Daily quests: three, all study-shaped and all satisfiable inside the normal session (clear due reviews; learn N new items; one test-style drill at or above 80%). No quest should require extra time beyond the commitment.
- Weekly goal: "study on 5 of 7 days" rather than 7 of 7, plus one weekly boss (cumulative quiz). This builds rest days into the definition of success.
- Forgiveness: two automatic grace days per week that need no purchase or action, plus a manual seclusion mode for travel or illness.
- Variable rewards: small random events and recruit rolls triggered by study milestones, drawn from a bounded table with a pity counter. Keep the variance cosmetic or narrative, so that no study session ever feels wasted by bad luck.
- Milestones at 3, 7, 14, 30, 60, 100 days and monthly after that, with a story beat each. Present consistency as "days studied this month" alongside any streak number, so one miss does not erase the visible record.
- First session (target under 5 minutes to first reward): pick a track and a commitment size with the smallest option preselected, do a 2 to 3 minute placement or first lesson immediately, found the sect and recruit the first disciple from that result, see the first building placed, and end with a clear preview of tomorrow. Unlock further halls one at a time over the first two weeks (for example day 1 Scripture Pavilion, day 2 training ground, day 3 spirit vein, day 7 first tribulation).
- No notifications are needed for a self-hosted single-user app; if any reminder exists, make it opt-in, once a day at most, and neutral in tone (no guilt copy).
- Ethics checklist: no loss of owned assets, no countdown timers that create urgency, no artificial scarcity, no pay-to-skip, rest counted as success, and a setting to hide streak numbers entirely.

### Gaps
- No published data found on optimal number of daily quests, on weekly-goal design, or on Duolingo's onboarding experiments (for example delayed sign-up); those commonly-repeated claims are unverified here.
- No research retrieved on habit-formation timelines or on optimal session length for adult self-study.
- No data on variable-reward effects specifically in learning apps; the variable-reward proposals rest on general game practice, not on cited evidence.
