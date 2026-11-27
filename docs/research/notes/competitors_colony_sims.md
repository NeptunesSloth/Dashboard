# What successful colony sims (and study-linked habit games) do well, and what the sect should copy

Research notes, 2026-11-24. Subject: the sect game in `sect_academy/colony.py`.

Reading notes for whoever uses this:
- "Sourced" bullets were retrieved in this session; the link is the page actually read. "(excerpt only)" means I saw a search summary, not the page.
- "[memory, unverified]" marks things I believe from general knowledge but did not re-check. Verify before quoting them anywhere public.
- "Inference" sections and every number in part 5 are my proposals. They are starting values to playtest, not measured results.
- Coverage was uneven. RimWorld is well sourced (wiki pages read in full). Amazing Cultivation Simulator, Banished, Kenshi, Going Medieval, Clanfolk, Kittens Game and Melvor Idle are thin: searches returned little and one fetch was refused. See "Gaps" at the end.

## 0. The game being advised, as read from the code

Facts from `colony.py` that the recommendations lean on:

- Mood already has the right skeleton: timed thoughts (`_think(p, key, label, value, hours)`) plus untimed modifiers computed inline in `_tick_pawn` (traits +/-8, Dao heart +6, tired -8, joyless -8 / joyful +4, hurt -6, crowded -4). Mood drifts 20% of the way to the target each hour.
- One mental break type ("qi deviation": 6-12 hours idle, then +12 catharsis for 36h). Break limit is mood 20 (10 Iron will, 30 Volatile), 4% per hour below it.
- Raid strength is `(wealth/22 + pawns*9 + day*1.1) * uniform(0.7, 1.35) * storyteller`. It is compared once with `defense(c)`; four outcome bands (>=1.4, >=0.9, >=0.55, below). There is no warning, no choice, and no memory of how the last fight went. The `day*1.1` term grows without limit.
- One event roll at dawn. Only two event kinds ask for a decision (wanderer, merchant); both expire in 24 hours and stop the clock.
- Disciples have no relationship to each other. A death gives everyone the same -12.
- Beds go to the first pawns in list order.
- Great-realm breakthrough: 55% + 2% per scholarship level, +25% if a pill is in stores. Failure hurts for 25 and costs 40% of the qi.
- Away: one sim hour per 30 real minutes, capped at 48 hours, no events or deaths. Watching: 4, 2 or 1 real seconds per hour.

Inference: a 10-minute visit is about 6 sim days at 1x and about 25 at 3x. A season is 12 days. So every pacing number below is expressed in sim days, and anything that needs the player (threats, choices, tribulations) should be designed to happen once or twice per visit, not once a week.

## 1. What players and designers credit for making these games compelling

### Sourced

- Tynan Sylvester, "The Simulation Dream" (2013): "The whole value of a game is in the mental model of itself it projects into the player's mind." Simulation that never reaches the player's mental model is wasted; Ultima Online's ecology was removed because, in Garriott's words, "literally no-one ever noticed". [Game Developer](https://www.gamedeveloper.com/design/the-simulation-dream)
- Same essay: players supply the story themselves (apophenia). "The simulation is a co-author of stories with the player." The designer's job is to give simple, legible hints the player can read intent into. [Game Developer](https://www.gamedeveloper.com/design/the-simulation-dream)
- Same essay: "hair complexity" is simulation detail "that doesn't affect anything outside itself" (appearance, histories, conversation bubbles). It is cheap, adds no balance burden, and feeds stories. [Game Developer](https://www.gamedeveloper.com/design/the-simulation-dream)
- Same essay: story-richness is "the percentage of interactions in a game that are interesting to the player". Stake primal human values (life/death, together/alone, wealth/poverty), use familiar archetypes, and avoid emotionally hollow logistics. Rule: "Choose the minimum representation that supports the kinds of stories you want to generate", and prefer reusing an existing variable over adding one. [Game Developer](https://www.gamedeveloper.com/design/the-simulation-dream)
- RimWorld's social layer is small and numeric: opinion from -100 to +100; rival below -20, friend above +20. Random interactions move it: chitchat +0.66, deep talk +15 for 20 days, slight -5, insult -15 (and a -5 mood thought for 2 days). An insult has a 4% chance to start a social fight. Shared history writes opinion too: "Rescued me" +15 for 30 days, "Recruited me" +20 for 120 days, "Crashed together" +25. Family gives a standing bonus (parent/child +30, sibling +20). [RimWorld Wiki: Social](https://rimworldwiki.com/wiki/Social)
- RimWorld mental breaks come in three tiers at mood 35% / 20% / 5%, with mean time between breaks of 4 / 0.8 / 0.5 days below each threshold. Traits move the threshold. After a break the pawn gets +40 "Catharsis" for 3 days, which is the built-in recovery from a mood spiral. Minor breaks are flavourful and low-cost (food binge, sad wander, hide in room, insulting spree); extreme ones are dangerous (berserk, fire starting, giving up and leaving). [RimWorld Wiki: Mental break](https://rimworldwiki.com/wiki/Mental_break)
- RimWorld quests: about one every 10 days in the base game; each must be accepted or declined, often with a timer to accept and a timer to finish; difficulty is shown as 1-3 stars (stars multiply the raid points used); rewards are frequently a choice of three, where taking faction goodwill excludes the items. Types include trade request (deliver goods by a date), bandit camp, refugees who may betray you (about 25%), hospitality (keep guests safe and content), pawn lending, and "threatened joiner" (take the recruit and the people chasing them). [RimWorld Wiki: Quests](https://rimworldwiki.com/wiki/Quests)
- RimWorld endings are quests that are always available and never expire (ship launch, Royal Ascent, Archonexus, the gravship chain). The long-term goal is opt-in and has no clock. [RimWorld Wiki: Quests](https://rimworldwiki.com/wiki/Quests)
- Dwarf Fortress has no win condition; every fortress eventually falls, which is the origin of the community motto "Losing is fun". (excerpt only) [Wikipedia: Dwarf Fortress](https://en.wikipedia.com/wiki/Losing_is_fun)
- Oxygen Not Included: reviewers credit two linked mechanisms, scarcity and a ripple effect (fixing one thing strains another), and the pleasure of working things out unaided. A GamesBeat piece notes the flip side: a closed system "feels like a solvable game" and needs outside disruption to stay alive. (excerpts only) [Gideon's Gaming](https://gideonsgaming.com/the-genius-design-of-oxygen-not-included-a-review/), [GamesBeat](https://gamesbeat.com/want-accessible-survival-strategy-urine-luck-with-oxygen-not-included/), [Game Developer](https://gamedeveloper.com/design/behind-the-design-of-hit-sim-game-i-oxygen-not-included-i-)
- Songs of Syx frames the first winter as the opening test: get food, shelter and clothing in place before it arrives. (excerpt only) [GOG store page](https://gog.com/game/songs_of_syx)
- Duolingo's own data: a learner who reaches a 7-day streak is 2.4 times more likely to come back the next day; a streak-wager test raised day-7 retention by 14%; Streak Freeze exists so a missed day or two does not end the habit. Company-reported, not independent. (excerpts only) [Duolingo blog](https://blog.duolingo.com/how-duolingo-streak-builds-habit), [Duolingo blog: improving the streak](https://blog.duolingo.com/improving-the-streak)
- Habitica takes health points for missed dailies. Reviews report this motivates some users and produces anxiety and avoidance in others; no churn numbers were found. (excerpts only) [Habitica wiki: Death](https://habitica.fandom.com/wiki/Death), [G2 reviews](https://g2.com/products/habitica-habitica/reviews)
- Forest lets the tree die if you leave, and its maker says the small sense of loss is intentional. No outcome study was found. (excerpt only) [forestapp.cc](https://forestapp.cc/)

### Memory, unverified

- RimWorld's Needs tab lists every active thought with its number and remaining time, and the mood bar shows the three break thresholds as tick marks. This is the legibility that makes mood feel fair.
- RimWorld's "Learning helper" shows a short contextual lesson the first time each concept becomes relevant, and marks it learned when the player performs the action. Alerts sit in a permanent column at the right edge ("Colonist needs rescue", "Low food", "Idle colonist", "Major break risk"), each clickable to jump to the cause.
- Sylvester's book *Designing Games* argues for failure that leaves the player something to continue with, and his GDC talk on RimWorld describes the game as a story generator rather than a skill test. I did not re-read either.
- Dwarf Fortress Legends mode and engravings turn the world's generated history into readable text, and players share fortress histories (Boatmurdered) as literature.
- Banished: its praised core is the winter/food/firewood loop and its known failure mode is the ageing population collapse; it is criticised for having nothing to do once the town is stable.
- Clanfolk: family generations and a hard winter you spend the other three seasons preparing for. Going Medieval: RimWorld's formula with room quality and food preservation as the levers. Kenshi: the world does not scale to you, so strength gained is strength felt, and players become attached to individually named squad members who started weak.
- Kittens Game: new resources and tabs "unfold" one at a time, so the game is always teaching exactly one new thing; seasons modify catnip output, with a lean winter. Melvor Idle: time away is simulated up to a cap and summarised in a welcome-back panel listing what was gained.

### Inference: what this means for the sect

1. The sect's simulation is already deeper than what the UI lets the player perceive. By Sylvester's own test, the cheapest improvements are the ones that surface existing state (why is this disciple unhappy, why did we lose that raid), not new systems.
2. The missing story engine is disciples relating to each other. Every death, breakthrough and raid currently produces the same thought for everyone. One opinion number per pair turns each of those events into a different story for each disciple.
3. Decisions are the scarce resource in a 5-10 minute visit. Two decision kinds (wanderer, merchant) is too few; RimWorld's quest cadence of roughly one offer per 10 days maps to one or two per visit here.
4. The game has no ending and no named antagonist. Opt-in, untimed long goals are what the genre uses, and they suit a game that must never punish absence.

## 2. How RimWorld's storyteller and raid scaling actually work

### Sourced (all from the RimWorld Wiki)

- Formula: `Raid points = (wealth points + pawn points) x difficulty x starting factor x adaptation factor`, floored at 35 and capped at 10,000. [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Wealth points: storyteller wealth = items + creatures + half of building wealth. Zero points below 14,000 wealth; 2,400 at 400,000; 3,600 at 700,000; flat at 4,200 from 1,000,000. The curve flattens and then stops. [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Pawn points: 15 per colonist at low wealth, 140 at 400,000, 200 at 1,000,000. Scaled down for wounded colonists (health feeds in at 65% weight), children, and slaves. [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Difficulty multiplier: 0.10 Peaceful, 0.30, 0.60, 1.00 Strive to Survive, 1.55, 2.20 Losing is Fun. [Raid points](https://rimworldwiki.com/wiki/Raid_points), [AI Storytellers](https://rimworldwiki.com/wiki/AI_Storytellers)
- Starting factor: 0.7 until day 10, rising to 1.0 by day 40, then constant. Time alone stops making raids bigger after day 40. [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Adaptation: a hidden "adapt days" counter from -60 to 100. Factor 0.4 at -30, 0.8 at 0 (the start), 1.0 at 30, 1.2 at 60, about 1.47 at the cap. It cannot rise in the first 30 days. It gains about 2 per day while low, 1 per day mid-range, slower above 60. A colonist death removes 20-30 adapt days; a colonist being downed removes 3.5-8. So a bad fight makes the next several raids smaller, and an untouched colony slowly faces more. [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Difficulty also sets how fast adaptation grows (0% on Peaceful, 25%, 75%, then 100%) and how much it counts (100% on easy settings down to 40% on Losing is Fun). On the hardest setting the game mostly stops forgiving you. [AI Storytellers](https://rimworldwiki.com/wiki/AI_Storytellers)
- Cassandra Classic: no major threats before day 11. Then a cycle of 4.6 days "on" and 6.0 days "off". Each on-phase sends one or two major threats (50/50), at least 1.9 days apart; about 8.5 per 60-day year. Minor events arrive on average every 4.8 days throughout. The opening is scripted: one mad animal, then a single raider on day 5. [Cassandra Classic](https://rimworldwiki.com/wiki/Cassandra_Classic)
- Randy Random: no cycle; a 50-150% random multiplier on each threat; long quiet stretches and back-to-back raids are both possible. The wiki notes many players find Cassandra harder on average because she never skips, while Randy is worse in the worst case. [Cassandra Classic](https://rimworldwiki.com/wiki/Cassandra_Classic), [Raid points](https://rimworldwiki.com/wiki/Raid_points)
- Phoebe Chillax: "lots of time between disasters", but at high difficulty "she'll hit as hard as anyone". Her spacing numbers were not on the pages read. [AI Storytellers](https://rimworldwiki.com/wiki/AI_Storytellers)
- Population steering: events that add colonists are weighted by a "population intent" curve: 8.0 with zero colonists, 2.0 with one, 1.0 with five, 0.4 with nine, 0 at twelve, negative beyond. The storyteller refills a gutted colony and stops feeding a full one. [AI Storytellers](https://rimworldwiki.com/wiki/AI_Storytellers)

### Inference: how this avoids death spirals, and where the sect differs

RimWorld stacks five separate brakes: (a) a guaranteed off-phase after every on-phase; (b) adaptation that drops sharply on deaths and downs; (c) wounded colonists count for fewer points; (d) the recruit-event weight rises steeply as population falls; (e) catharsis after a mental break. The sect has a version of (a) (`threat_gap`), a weak accidental version of (c) (lost stores lower wealth), a binary version of (d) (wanderer weight is 16 or 0), and (e). It has no (b) at all, and its time term never stops growing, where RimWorld's stops at day 40.

The 150-day scripted balance check in the design doc would not catch this: a script plays evenly, while a person who has one bad fight has no mechanism pulling the next fight back within reach.

## 3. Amazing Cultivation Simulator: cultivation-specific depth

### Sourced

- A top-down sect-management game whose makers cite Dwarf Fortress and RimWorld as inspiration. Players cultivate disciples' qi toward immortality, balance the feng shui of rooms and of cultivators, trade, spread the sect's influence across a map, repel invaders and subdue powerful monsters. [Wikipedia](https://en.wikipedia.org/wiki/Amazing_Cultivation_Simulator)
- The store page pitches three hooks: prepare "in all aspects" for the Heavenly Tribulation; reach higher states and collect treasures to prolong lifespan; craft almost anything into an artifact. (excerpt only) [Steam](https://store.steampowered.com/app/955900)
- There is a framing plot (rebuild the destroyed Taiyi sect and find who destroyed it) and a mandatory tutorial prologue. [Wikipedia](https://en.wikipedia.org/wiki/Amazing_Cultivation_Simulator)
- Sold over 700,000 copies in China-only early access (PC Gamer, Nov 2020). Metacritic 73 from four critics. [Wikipedia](https://en.wikipedia.org/wiki/Amazing_Cultivation_Simulator)
- A free 2024 update ("Heavenly Chaos") rebalanced the late game and added new qi-deviation effects and Heavenly Dao mechanics, i.e. the developers were still fixing the late game five years on. [Wikipedia](https://en.wikipedia.org/wiki/Amazing_Cultivation_Simulator)

### Memory, unverified (the wiki and guides were not reachable in this session)

- Disciples are split into outer disciples, who do the colony's labour, and inner disciples, who cultivate and are too valuable to farm. Promotion to inner disciple is a decision.
- Each cultivator follows a "law" (a cultivation method) with an element; laws have their own skill trees and suit some characters better than others. The five elements generate and restrain each other, and this applies to people, rooms, items and seasons alike.
- Room feng shui and local qi concentration change cultivation speed, so where a disciple meditates matters.
- The Golden Core breakthrough has a quality grade that depends on preparation (accumulated qi, state of mind, the room, pills, elemental match), and that grade caps the character's later potential. Later breakthroughs draw a tribulation of lightning that must be survived, with prepared defences.
- Lifespan is a clock: a cultivator who does not break through in time dies of old age.
- Other sects exist on a world map with reputation; disciples are sent out on adventures that play as text events with choices.

### Inference

The cultivation-specific ideas that carry over without a tile map are: breakthrough quality from preparation (a checklist the player can work on, in place of a coin flip), element affinity between disciple, technique and season, the inner/outer split as a staffing decision, tribulation as a telegraphed set-piece, and text adventures off-site. Feng shui in ACS depends on spatial placement, which the sect does not have; a reduced form (room elements and a single "harmony" number) is possible but would add an opaque system, which is the thing ACS is most criticised for (next section).

## 4. Common complaints

### Sourced

- ACS: "a learning curve like no other"; "poor tutorials"; a "very entertaining gameplay loop ... let down by the obscurity of its harder mechanics"; one player spent "an hour at least" in tutorials and still found the curve steep; players expect to need the wiki and Discord. One critic (Cubed3, 5/10) found the mix of cosy and hardcore mechanics served neither audience. An aggregator also lists "frustrating micromanagement and AI". (excerpts only) [OpenCritic](https://opencritic.com/game/10750/amazing-cultivation-simulator), [Hooked Gamers](https://www.hookedgamers.com/pc/amazing_cultivation_simulator/review/article-2237.html), [Steam discussion](https://steamcommunity.com/app/955900/discussions/0/3111404628277463814), [Wikipedia](https://en.wikipedia.org/wiki/Amazing_Cultivation_Simulator)
- RimWorld late game (forum posts, anecdotal): raids become either trivial or overwhelming; players describe "just waiting for the inevitable raid they can't beat"; the only thing that scales is raid size, so the late game lacks variety; wealth-driven scaling is felt as a punishment for building nice things and is hard to reason about; killboxes become either mandatory or a cheat. One forum thread proposes upkeep costs in place of raid scaling. (excerpts only) [Ludeon forums](https://ludeon.com/forums/index.php?msg=93631), [Ludeon forums: upkeep instead of raid scaling](https://ludeon.com/forums/index.php?msg=365222), [Steam discussion](https://steamcommunity.com/app/294100/discussions/0/2145343824281035695)
- ONI: can feel "solvable"; once the loops close there is no outside pressure. (excerpt only) [GamesBeat](https://gamesbeat.com/want-accessible-survival-strategy-urine-luck-with-oxygen-not-included/)
- Habitica: punishment for missed days creates anxiety for some users. (excerpt only) [G2 reviews](https://g2.com/products/habitica-habitica/reviews)

### Inference: complaints to design against here

- Opaque causes. Every number that changes an outcome (mood, raid odds, breakthrough odds) should be readable where the outcome is shown.
- Scaling felt as punishment. If the player can see why a raid was the size it was, and can see it shrink after a loss, wealth scaling reads as a rule and stops reading as spite.
- Only size scales. Late threats should differ in kind (siege that blocks trade, a rival's challenge duel, a demonic cultivator who targets one disciple), not only in strength.
- Micromanagement growth. With a cap of roughly a dozen disciples and one priority grid the sect is fairly safe, but each new system below must come with a default that works untouched.
- Punishing absence. Already avoided; nothing below adds a penalty for time away. Anything timed uses sim time while watched, or waits for the player.

## 5. Ranked recommendations for the sect

Everything in this section is inference. Effort: S = under a day, M = a few days, L = a week or more, for one developer with the current code. Impact is my judgment of effect on "is this compelling in a 10-minute visit".

Constraints applied to every item: no tile map; text plus the one scene; hourly server sim; offline with no LLM, so all text is templated; nothing fires during quiet catch-up; study remains optional and is never the only route to anything.

### Tier 1: surface what exists, and fix pacing (do these first)

**1. Mood ledger and "why" lines. Effort S. Impact very high.**
- Reference: RimWorld lists each thought with its value and time left [memory]; Sylvester's essay says unperceived simulation is wasted [sourced].
- Why it works: the player can act on a cause they can read, and reads intent into a named thought.
- Build: in `_tick_pawn`, collect the untimed modifiers that are currently added inline (tired, joyless, hurt, crowded, trait, Dao heart) into a list of `{label, v}` alongside `p["thoughts"]`, and return both from `_pawn_view` with hours remaining. UI: on the disciple panel show the mood bar with the break limit marked, then the ledger sorted by size ("Slept on the ground -6, 14h left"). Add a one-line summary on the portrait hover: "Unhappy mostly because: slept on the ground, hungry". Do the same for the last raid: store `{strength, defense, ratio, parts}` and show "Their strength 140 (wealth 60, numbers 54, years 26) against our 118 (disciples 80, ward 38)".

**2. Alerts strip. Effort S. Impact high.**
- Reference: RimWorld's alert column [memory]; the sect already has one alert-like letter ("The rice is nearly gone").
- Why it works: a short visit starts with "what needs me", and alerts are that list. They also teach the rules by naming them.
- Build: a pure function `alerts(c)` computed in `view()`, no state. Candidates: rice below N days at current headcount (show the days); winter in under 4 days with rice below winter need; disciple without a bed; mood within 8 of break limit; a breakthrough waiting; idle disciples with open jobs they are barred from; build queue empty; no research chosen; unused pills while someone is wounded; decision waiting at the gate. Each alert carries a target panel id so a click opens it. Cap at five, worst first.

**3. Storyteller adaptation, a capped time ramp, and an on/off cycle. Effort M. Impact high.**
- Reference: RimWorld's adaptation factor, day-40 cap and Cassandra's 4.6-on / 6-off cycle [all sourced, section 2].
- Why it works: a loss is followed by smaller threats and guaranteed quiet, so one bad fight cannot become three.
- Build: add `c["adapt"]` (float, starts 0, range -30..60). Each watched sim day with no disciple downed: +1 (x0.5 on Gentle Rain, which has no threats anyway). Disciple reduced below 30 health in a threat: -6 each. Death: -20. "Overrun" outcome: a further -10. Factor = 0.8 at 0, 0.5 at -30, 1.0 at 20, 1.25 at 60, linear between. Replace `day*1.1` with `min(day, 48) * 1.1` so age stops adding after one year. Scale each pawn's contribution by health as RimWorld does. Make the cycle explicit: after any threat, no threat for `threat_gap` days, and after a loss, double it. Make wanderer weight a curve (32 when under 4 disciples, 16 normally, 6 near cap, 0 at cap). On Heaven's Trial, halve adaptation's effect, as RimWorld does on its top setting. Extend the scripted balance test with a "plays badly" profile.

**4. Telegraphed threats with a choice. Effort M. Impact high.**
- Reference: RimWorld threats are fought, not rolled, and its quests show star ratings before you commit [sourced]. The sect resolves a raid in one comparison with no warning.
- Why it works: the comparison stays (no combat sim needed) but the player gets a day to prepare and a real decision, which is where the story comes from.
- Build: the dawn roll produces `c["omen"] = {kind, strength_low, strength_high, arrives: hour+24}` and a letter: "Scouts report a raiding party a day out. They look about as strong as we are." Bands: "far weaker / weaker / about even / stronger / far stronger" from the ratio against current defense. On arrival, a pending decision (clock stops, as with the gate): Fight; Hold the wards (defense x1.25, no loot, no combat xp); Pay them off (spirit stones proportional to strength, small mood penalty for "We paid tribute", rival reputation effects once item 9 exists); for beasts, Lure them away (costs rice). During the warning day the player can reprioritise to Train, brew pills, or finish a ward level. Omens never arrive during quiet catch-up; if the player leaves mid-omen it waits.

**5. First-hour goals (a guided opening). Effort S-M. Impact high for new players, none later.**
- Reference: RimWorld's learning helper and scripted first threats (one mad animal, then one raider on day 5) [sourced for the threats]; ACS's hour-long tutorial is the cautionary case [sourced]; Kittens Game's one-new-thing-at-a-time unfolding [memory].
- Why it works: teaches by doing, in order of need, and hides panels until they matter.
- Build: an ordered list of about ten goals held in `c["guide"]` (index plus done flags), each with a completion test on colony state: set one priority; queue the Dormitory; survive the first night with beds; choose a research; reach 60 rice before winter; brew a pill; win the first (scripted, weak) beast attack on day 5; guide a breakthrough. Show one goal at a time in the guide-elder's speech bubble with the relevant panel highlighted. Small reward on each (a few stones). Hide Research, Trade and Chronicle tabs until their first goal. A "skip, I know colony sims" button. Script the first threat at 0.5x strength so the first fight is always a win with one wound.

### Tier 2: the story engine

**6. Relationships and social thoughts. Effort M. Impact very high.**
- Reference: RimWorld opinion and interactions [sourced numbers in section 1].
- Why it works: it makes every existing event personal. Sylvester's point is that a handful of simple signals is enough for players to see jealousy, loyalty and grief.
- Build: `c["bonds"]` as a dict keyed by sorted id pair, value -100..100, default 0; store only non-zero pairs. Each hour, two disciples doing the same job (or both relaxing) have a small chance of an interaction, chosen by current opinion and traits: talk (+2), deep talk (+12, needs opinion above 0), slight (-4), insult (-12 and a -5 thought for 2 days; Volatile insults more, Optimist less). History writes bigger values: fought the same raid +10; nursed while sick +12; one got the last bed -6; master lectured (after a study session) +3 toward the Master. Thresholds: friend at 30, sworn sibling at 70, rival at -30. Consequences reuse existing variables: friend dies -18 (not the flat -12), rival dies +4, friend breaks through +8, rival breaks through -6 ("envy") and +10% meditation speed for 48h ("spurred on"); working beside a friend +3 mood, beside a rival -3. One relation type worth special-casing for the genre: master and apprentice (highest-realm disciple and a chosen junior; apprentice learns the mentor's best skill faster, each feels the other's fate double). UI: a "Bonds" line on each disciple card ("Sworn sibling of Lin Wei. Rival of Mo Yan."), and chronicle lines when a threshold is crossed. No romance needed for a first version.

**7. Backstories and other "hair". Effort S. Impact medium-high for its cost.**
- Reference: hair complexity [sourced]; RimWorld childhood/adulthood backstories [memory].
- Why it works: nearly free, and it is what players quote when they retell a colony.
- Build: at `_make_pawn`, pick an origin from about 25 ("Orphan of a razed village", "Disgraced scholar", "Runaway outer disciple of the Azure Crane Sect", "Herb-gatherer's daughter"), each with one line of text, a +2/+3 nudge to a skill, and optionally a tag other systems can read (the runaway is hated by that rival sect; the orphan gains double mood from "has a bed"). Add an epithet earned from the first notable thing they do ("the Unbroken" after surviving at under 10 health, "Pill-hand" after 50 pills), shown after the name. Add a favourite season and a dislike (a job they take -2 mood for). Wanderer text becomes a sentence of story instead of a stat line.

**8. Quests with choices and a reward pick. Effort M. Impact high.**
- Reference: RimWorld quests [sourced]: accept/decline, stars, timers, choose one of three rewards, betrayal risk.
- Why it works: gives each visit a decision with a trade-off and a short arc that ends in a later visit.
- Build: generalise `c["pending"]` into a small quest table: `{id, title, text, stars, options[], accept_by, due, state}`, one offer at a time, about one per 8-10 watched days, never while another decision waits. Timers count watched sim hours only. Starter set of eight, all resolvable with existing variables: deliver 60 rice / 12 pills to a mortal village by day N (reward: stones, or reputation, or a recruit); shelter a wounded stranger for 3 days (uses a bed and rice; 20% they rob you, 20% they are an elder who teaches); a wandering alchemist asks for a pavilion workspace (crafting bonus for a season, eats double); escort request (lend your best fighter for 2 days, shown as absent); a rival sect's challenge duel (your champion's combat power against theirs, odds shown); a spirit beast offers a pact (permanent ward bonus, takes rice every week); a persecuted cultivator asks to join (strong recruit, a raid follows in 3 days, shown up front); an auction (bid stones for one of three artifacts once item 12 exists). Each shows stars and offers two or three rewards to choose from.

**9. Named rival sects with reputation. Effort M. Impact medium-high.**
- Reference: RimWorld faction goodwill [sourced via quest rewards]; ACS's other sects and influence [sourced at headline level; details from memory].
- Why it works: "a rival sect's raid" becomes "the Black Lotus again, the ones who killed Yun Mei", a recurring antagonist the player wants to beat.
- Build: generate three or four neighbours at `new_colony`: name, element, a temperament (mercantile, martial, reclusive, demonic), a master's name, and `rep` from -100..100. Raids come from the lowest-rep sect and name their leader. Reputation moves through quests, tribute, trade (mercantile sects send the merchants; better prices at high rep), and declined duels. At rep above 50 a sect sends aid during a raid (adds to defense) or an exchange disciple for a season; below -50 it sends stronger, named raids and a demand for tribute. A small "Neighbours" panel: four rows, a bar each, last interaction. Allow one decisive act late on (see item 10).

**10. Long-term goals and endings. Effort M-L. Impact high for retention past week two.**
- Reference: RimWorld's always-available, untimed ending quests [sourced]; DF's "no win, eventual fall" as the alternative model [sourced]; ONI and RimWorld complaints about an aimless late game [sourced].
- Why it works: gives the middle game a direction and gives "one more visit" a reason. Untimed, so absence costs nothing.
- Build: a "Great Works" panel with three or four goals, each a visible checklist: (a) Ascension: the Sect Master reaches Immortal Ascension and survives the final tribulation (item 11); the sect continues under a chosen successor with a permanent blessing. (b) Found a branch sect: Main Hall 5, twelve disciples, 200 stones, and send three named disciples away for good; unlocks periodic tribute and a "new game plus" seed. (c) Settle the feud: bring every neighbour to +50 or defeat the worst one in a three-stage siege. (d) The Sect Canon: complete all research plus a second tier. Add a sect "renown" rank (Nameless, Local, Regional, Great Sect) computed from wealth, realms and deeds, shown in the header, which also gates quest stars. Study can count toward one optional checklist line (for example a passed trial inscribes a chapter of the Canon) but no goal may require it.

**11. Tribulations and breakthrough preparation. Effort M. Impact high (it is the genre's signature moment).**
- Reference: ACS: prepare "in all aspects" for the Heavenly Tribulation [sourced]; Golden Core quality from preparation [memory].
- Why it works: replaces a hidden coin flip with a visible checklist the player can work on, then a set-piece they chose the timing of. The code already makes major breakthroughs wait for the player.
- Build: when qi is full for a great realm, the disciple enters "at the threshold" (keeps working, shown with a glow in the scene). The disciple panel shows the odds as a ledger: base 45%, scholarship +2% per level, mood above 70 +10%, full health +5%, Meditation Chamber level +3% each, pill +20% (player ticks whether to spend it), a friend standing guard +5%, matching season +5% (item 13), a wound or a recent death -10%. The player presses "Attempt" when satisfied. From Core Formation upward, success is followed by a tribulation: three lightning strikes of rising damage against health plus ward level; the scene flashes; survive and gain a random boon (trait-like: "Thunder-tempered", +15% combat). Failure states stay soft: injury and lost qi, never death below Heaven's Trial. Result quality (barely / steady / perfect, by margin of the roll) sets a small permanent qi-speed modifier, which gives ACS's "quality of the core" without a new system.

### Tier 3: breadth

**12. Artifacts and equipment. Effort M. Impact medium-high.**
- Reference: ACS artifacts [sourced at headline level]; RimWorld item quality and named art [memory].
- Build: one slot per disciple. An artifact is `{name, kind, bonus, origin}`, name generated from two word lists ("Frost-Jade Hairpin"), origin recorded ("taken from the Black Lotus raid, day 41"). Sources: raid loot on clean wins, quest rewards, a new Forge job (uses stone and stones; quality from craft skill with a rare masterwork that writes a chronicle line), expeditions. Bonuses reuse existing multipliers (+combat power, +qi rate, +breakthrough odds, -hunger). Who gets the one good sword is a decision with social fallout once bonds exist (the passed-over rival takes -8).

**13. Elemental spirit roots and techniques. Effort M. Impact medium.**
- Reference: ACS laws and five elements [memory, unverified].
- Build: give each disciple an element (wood, fire, earth, metal, water) beside the existing root grade. Each season favours one (+10% qi) and suppresses one (-10%). Techniques are found or researched ("Verdant Breath: wood; +20% qi, +10% farming"; "Iron Body Scripture: metal; +combat, slower qi"); each disciple practises one, with a bonus if elements match and a penalty if they clash. Keep to about ten techniques and show the match as a plain word ("well suited / neutral / ill suited"). This is the item most at risk of becoming an opaque system, so everything it changes must appear in the ledgers from items 1 and 11.

**14. Expeditions. Effort M. Impact medium-high for short visits.**
- Reference: RimWorld caravans and site quests [sourced via quest list]; ACS adventures [memory]; the design doc lists "caravans you send out" under later work.
- Why it works: a send-and-return timer is the natural shape for a game visited briefly. You dispatch at the end of one visit and open the result at the start of the next.
- Build: choose 1-3 disciples and a destination (herb valley, ruined sect, mortal city, beast forest), each with a duration in sim hours, a risk band and a loot table. They are absent from jobs and defense. Unlike events, expeditions may progress during quiet catch-up, because the outcome is rolled at return and can be capped at "wounded, came home early". On return, a two-step text result with one choice ("The ruin's inner door is sealed. Force it / leave an offering / go home"). Rewards: resources, an artifact, a technique scroll, a recruit, bond gains between the travellers.

**15. Seasonal festivals and a winter forecast. Effort S. Impact medium.**
- Reference: winter as the organising pressure in Songs of Syx [sourced excerpt], Banished and Clanfolk [memory]; RimWorld parties and rituals [memory].
- Build: a forecast line from mid-autumn: "Winter in 5 days. Rice for 9 days at this headcount; winter lasts 12." (This is also an alert.) Four fixed festivals, one per season, on a known day: Spring Sowing Rite, Midsummer Lantern Night, Autumn Harvest Offering, Winter Vigil. Each is a small decision (spend 20 rice and a day of work for +10 mood for 3 days and bond gains, or skip it for "The festival was skipped" -4). The Winter Vigil marks the year's end and triggers item 16's summary.

**16. Sect annals: the story so far. Effort S. Impact medium, rising with every other item.**
- Reference: DF legends and engravings [memory]; Sylvester's "co-author" framing [sourced].
- Build: keep a second, permanent list beside the rolling `log`: only milestone entries (founding, each joiner with origin, deaths with cause, great-realm breakthroughs, raids won and lost by named enemy, bonds formed, artifacts forged, festivals). Render as a year-by-year chronicle page with a memorial list for the dead (name, epithet, realm, how they died, who mourned them). At each Winter Vigil generate a templated year summary ("In the third year the sect grew from five to eight, lost Yun Mei to the Black Lotus, and saw Lin Wei reach Core Formation"). Offer "copy as text".

**17. Varied mental states. Effort S. Impact medium.**
- Reference: RimWorld's tiered breaks and catharsis [sourced].
- Build: keep the single threshold but pick the break by trait and bonds: Glutton raids the storehouse (-8 rice); Volatile picks a fight with a rival (both lightly hurt, 50/50 it clears the air for +15 opinion or -15); Bookworm locks themselves in the pavilion (no work, small research gain); a grieving friend keeps vigil at the grave; default stays the daze. Add a rare severe tier at mood under 8 on Heaven's Trial only: the disciple announces they will leave in 24 hours unless mood recovers, which is a problem the player can solve. Mirror it on the good side: inspirations by passion (a forging inspiration guarantees a masterwork; a meditation inspiration gives one free minor stage).

**18. Welcome-back report and gentle study tie-ins. Effort S. Impact medium.**
- Reference: Melvor Idle's return summary [memory]; Duolingo's streak-freeze logic [sourced], already mirrored by the sect's rest days; Habitica's HP loss as the thing not to copy [sourced].
- Build: replace "The sect carried on for N hours" with a short itemised report: resources gained, rooms finished, skills levelled, who is at a threshold, what is waiting at the gate. For study, add choice in place of volume: after a session the Master picks the lecture's theme (insight to research / a bond gain with one named disciple / +5% to the next breakthrough attempt). A passed trial could let the Master "stand guard" for one tribulation. Keep the invariant from the design doc: no sect system requires study, and nothing decays when study stops. The earlier notes in `game_design.md` on reward design (pay for demonstrated recall, not volume) apply unchanged.

**19. Work grid quality-of-life and inner/outer disciples. Effort S. Impact medium.**
- Reference: RimWorld's priority grid shows skill level and passion in each cell [memory]; ACS's inner/outer split [memory]; micromanagement complaints [sourced].
- Build: show skill and passion flames in each grid cell, shade cells the disciple is best in the sect at, add "suggest" (fills priorities from skills and current shortages) and two saved presets (peace, under threat). Add a per-disciple "inner disciple" toggle: an inner disciple only meditates, trains and researches, cultivates 25% faster, and expects better conditions (mood penalty without a bed or with low joy). The sect can support one inner disciple per three outer. This is a single staffing decision with visible cost, and it removes grid fiddling for those disciples.

### What I would not copy

- Feng shui as spatial placement, or any tile-level system: no map to put it on, and it is ACS's most-criticised kind of depth.
- Wealth as the main raid driver. Keep it, but with adaptation and a visible breakdown (items 1 and 3) so it does not read as a tax on building.
- Lifespan clocks or anything that advances while away. ACS uses old age as pressure [memory]; here it would punish absence.
- Loss-aversion hooks for study (Habitica HP loss, Forest's dead tree). The design's invariant already rules these out and the evidence for them is anecdotal.
- Prestige resets. The branch-sect ending (item 10) gives a fresh start with a legacy bonus without wiping a colony the player is attached to.

### Suggested order

1, 2, 3 (one release: "the sect explains itself and forgives a bad day"), then 6, 7, 16 (one release: "disciples have lives"), then 4, 5, 8, 11, then 9, 10, then the rest. Items 12-14 depend on 8 for their best sources of loot; 13 should wait until 1 and 11 exist so its effects are visible.

## Gaps and unverified claims

- Amazing Cultivation Simulator's mechanics (laws, elements, inner/outer disciples, Golden Core grades, tribulation details, world-map adventures) are from memory. The Wikipedia page confirms only the headline systems; the Fandom wiki and community guides were not read.
- Phoebe's cycle lengths and Randy's event weights were not on the pages read. The shape of the day 10-40 ramp between its endpoints is not given by the wiki.
- RimWorld's Needs tab layout, learning helper and alert list are described from memory. Mood thoughts for a friend's or rival's death were not on the Social page.
- Sylvester's book *Designing Games* and his GDC talk were not consulted; only the 2013 essay was read.
- Banished, Kenshi, Going Medieval and Clanfolk: no usable source retrieved; all statements about them are memory. Songs of Syx and ONI: search excerpts only.
- Kittens Game and Melvor Idle: no source retrieved (the Melvor wiki returned 403). I believe Melvor's offline cap is 24 hours but did not confirm it.
- Dwarf Fortress: only the "no win condition" point is sourced; legends mode is from memory.
- The RimWorld late-game complaints are forum posts chosen by a search engine. They show the complaints exist, not how common they are.
- Duolingo's figures are company-reported. I found no independent data on whether Habitica's or Forest's loss mechanics help or hurt retention.
- I skimmed `colony.py` (constants, pawn tick, threats, events, study hooks) and did not read `_pawn_view`, `view`, `defense` or `wealth` line by line, nor `sect.js`. Item 1 assumes the UI does not already show the untimed mood modifiers; check before building.
