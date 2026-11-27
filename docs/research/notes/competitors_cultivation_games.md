# What successful cultivation / xianxia games do right, and what the sect should copy or avoid

Research notes, 2026-11-25. Subject: the sect game in `sect_academy/colony.py` and `dao.py`.
Companion to `competitors_colony_sims.md` (RimWorld-style sims); nothing from that file is repeated here except where a recommendation it made is still unbuilt.

How to read this file:

- `[sourced: URL]` means the page was fetched in this session and the claim was on it. `(search excerpt)` after a URL means I saw only the search engine's summary of that page, not the page.
- `[memory, unverified]` means I believe it from general knowledge and did not confirm it. Do not quote these publicly.
- "Inference" paragraphs and every number in sections 3 and 4 are my proposals: starting values to simulate, not measurements.
- Pages were read through a fetch tool that summarises them with a small model. Quoted phrases are as that tool returned them; a mis-transcription is possible, so re-open the page before quoting anything outside this repo.
- Review-theme counts come from VaporLens, an automated summariser of Steam reviews. Treat its counts as "how often a theme came up in its sample", not as percentages of all reviews.

## 0. Reach and reception at a glance

All-language Steam totals are from the SteamSpy API (fetched 2026-11-25); the percentage is my arithmetic on its positive/negative counts. English-only lines are from the Steam store pages.

| Game | Steam reviews, all languages | Positive | Owners (SteamSpy band) | Median playtime | English-only |
|---|---|---|---|---|---|
| Amazing Cultivation Simulator | 19,150 | 85.9% | 0.5-1M | 27 h | 91% of 1,851 |
| Tale of Immortal | 190,329 | 56.8% | 5-10M | 46 h | 79% of 3,825 |
| Immortal Life | 3,976 | 80.5% | 0.2-0.5M | 22 h | 89% of 917 |
| Wandering Sword | 38,112 | 94.7% | 0.5-1M | 28 h | 95% of 2,406 |
| Hero's Adventure: Road to Passion | 22,733 | 83.5% | 0.5-1M | 35 h | 93% of 2,021 |
| Yi Xian: The Cultivation Card Game | 6,132 | 73.9% | 0.5-1M | 3.6 h | 88% of 868 |
| Path of Wuxia | 28,294 | 78.7% | 0.5-1M | 18 h | not fetched |

Sources: [sourced: https://steamspy.com/api.php?request=appdetails&appid=955900] and the same URL with appid 1468810, 1201230, 1876890, 1948980, 1948800, 1189630. English lines: [sourced: https://store.steampowered.com/app/955900/Amazing_Cultivation_Simulator/], [sourced: https://store.steampowered.com/app/1468810/Tale_of_Immortal/], [sourced: https://store.steampowered.com/app/1201230/Immortal_Life/], [sourced: https://store.steampowered.com/app/1876890/Wandering_Sword/], [sourced: https://store.steampowered.com/app/1948980/Heros_Adventure_Road_to_Passion/], [sourced: https://store.steampowered.com/app/1948800/Yi_Xian_The_Cultivation_Card_Game/].

Two things stand out before any detail:

- Tale of Immortal is the genre's biggest seller by an order of magnitude and its worst-rated: 190k reviews at 57% positive. Part of that is a 2022 review bomb over mod hosting (section 1.2), but the top theme in its reviews is still grind. Scale and satisfaction are different lessons, and this file tries to keep them apart.
- Wandering Sword, the best-rated, is a hand-authored story game. Its lesson for a systemic sim is about relationships and legibility, not content volume.
- Hero's Adventure's recent reviews were "Mostly Negative", 35% of 134, on the day fetched, against 93% all-time in English. I did not find out why. [sourced: https://store.steampowered.com/app/1948980/Heros_Adventure_Road_to_Passion/]

## 1. Game by game

### 1.1 Amazing Cultivation Simulator (GSQ Games, 1.0 on 2020-11-24)

The earlier notes had only Wikipedia. This section replaces their "memory, unverified" list where I could confirm it.

What players praise

- VaporLens themes: "Highly praised overall" 58, "Deep and complex systems" 44, "Vast content and replayability" 42, "Strong RimWorld competitor" 40, "Emergent and humorous stories" 40. [sourced: https://vaporlens.app/app/955900/amazing_cultivation_simulator]
- Hooked Gamers (6.5): "Use of Feng Shui and other cultural touchstones is meaningful and unique"; text adventures "within the general simulation was a welcome change of pace"; the slow unlock of buildings and features "is actually a welcome feature"; "It rewards people that are willing to take on its incredibly steep learning curve." [sourced: https://www.hookedgamers.com/pc/amazing_cultivation_simulator/review/article-2237.html]

The mechanics behind the praise

- Golden Core grade is the game's central optimisation puzzle. Players report that the grade depends on Max Qi at the moment of core shaping plus the breakthrough conditions: "You can jump from a grade 4 to a grade 1 with perfect breakthrough conditions", the conditions being season, timing, cultivation harmony, weather, feng shui and qi density. Lower grade number is better. [sourced: https://steamcommunity.com/app/955900/discussions/0/2967268512115174745]
- Numbers players trade: a grade 2 core at about 6,000-6,500 qi; about 9,000-10,000 for a good chance at grade 1; "Normally, players aim for 7k to 30k qi at core shaping", with min-maxers at "3-4 million". [sourced: same thread]
- The conditions are per element and form a timing window. One guide's table: Fire and Wood break through by day (about 06:00-18:00), Water and Metal at night (about 21:00-04:00), Earth at dusk; each element has a matching weather (Fire: Noxious Air, Water: Thunderstorm, Wood: Rainstorm, Metal: Dust Devil, Earth: Foehn Wind) and a best day of a best season (seasons "peak right before day 15", so about day 12). Mental state should be about 95 of 100; the cultivator's stats should exceed the law's requirements; the room should be built of qi-gathering material with matching elements. [sourced: https://gamepretty.com/amazing-cultivation-simulator-xiandao-golden-core-cultivation/]
- A mentor already at Golden Core speeds a junior's cultivation ("3+ faster"). [sourced: same guide]
- Outer disciples build, hunt, gather and are the ones sent on adventures; with training they become inner disciples, who cultivate. Adventures are "text based mini-game-like" stories with choices. [sourced: https://www.hookedgamers.com/pc/amazing_cultivation_simulator/review/article-2237.html]
- New inner disciples get upset if not given an artifact and a weapon; promote those with good law affinity. [sourced: search excerpts of https://gameplay.tips/guides/8895-amazing-cultivation-simulator.html (search excerpt)]
- Strategy the systems produce: rush "exactly one inner disciple" to a "garbage golden core" to unlock the next tier's tools, then do it properly; keep about three "throwaway" inners on looping resource trips; host other sects' disciples in comfortable rooms for 17 to 50 favour each. [sourced: https://gameplay.tips/guides/12109-amazing-cultivation-simulator.html]
- Tribulations are prepared for with protective gear ("Protection at level 20 is described as enough"). [sourced: gamepretty guide above]
- Lifespan exists but one forum poster says it "doesn't matter much", being hard to run out of. [sourced: search excerpt of a Steam thread (search excerpt)] So the clock is mostly flavour in practice.

Complaints

- VaporLens: "Frustrating micromanagement and AI" 69, "Extremely steep learning curve" 68, "Poorly explained mechanics" 56, "Poor and broken tutorials" 52, "Developer abandonment concerns" 42, crashes 34. [sourced: https://vaporlens.app/app/955900/amazing_cultivation_simulator]
- "The tutorial offered in the game is unhelpful and feels more like a dull textbook with out-of-context information"; without outside guides it is "incredibly daunting to know what to do." [sourced: Hooked Gamers review above]
- The slow "Inner Cauldron" fill in early and mid game frustrates players; the veteran answer is that it is "meant to take that long" and to skip it. [sourced: Steam thread above]

Inference: ACS's best idea is that a breakthrough has a *grade the player earns by preparation and timing*, and the grade lasts. Its worst is that none of it is shown: the complaint counts for micromanagement, learning curve and unexplained mechanics each exceed the count for its top praise. The sect already has the ledger habit (`bt_odds`, `qi_rate`), so it can take the idea without the cost.

### 1.2 Tale of Immortal (鬼谷八荒; early access 2021-01-27, 1.0 on 2023-05-26)

What players praise

- VaporLens: "Stunning art style and music" 95, "Highly engaging and addictive gameplay" 91, "Authentic Xianxia/Wuxia cultivation experience" 87, "Extensive modding support" 51, "Detailed cultivation and combat systems" 27. [sourced: https://vaporlens.app/app/1468810/tale_of_immortal]
- Over 180,000 concurrent players on Steam after launch; briefly above GTA V and Apex Legends on the most-played list. A 1.8 million sales figure appears only in a cited Eurogamer headline. [sourced: https://en.wikipedia.org/wiki/Tale_of_Immortal]

The mechanics behind the praise

- Destinies (先天气运). At creation you pick three from a list of nine and may reroll without limit. Five rarities: grey, green, blue, purple, red. Many are trade-offs: "Sick Genius" removes 20 years of lifespan for percentage bonuses to cultivation and learning; "Intelligent" raises Perception and cuts maximum Mood; "Bald Genius" trades Charisma for Perception. Some legendary ones are locked behind achievements. [sourced: https://gamepretty.com/tale-of-immortal-how-to-create-a-good-starting-character-%e9%ac%bc%e8%b0%b7%e5%85%ab%e8%8d%92/]
- A fate rewritten at each breakthrough (逆天改命). The store page: "With each breakthrough, you'll be able to rewrite your destiny". [sourced: https://store.steampowered.com/app/1468810/Tale_of_Immortal/] These are build-defining and come in tiers that upgrade, e.g. a shield at near-death worth 30% / 50% / 70% of stamina across three ranks, or lifesteal of 7% / 12% / 17%. [sourced: https://www.3dmgame.com/gl/3825466_10.html] That you choose one of three at each realm is [memory, unverified]; the pages read did not state the number offered.
- Lifespan as a visible clock that breakthroughs extend: default maximum 80 years; reaching Foundation adds about 40. [sourced: gamepretty guide above]
- Each realm's breakthrough needs specific things gathered from the world, not just a full bar: Golden Core needs six elemental Qi Pearls from six bosses, with a slower no-combat substitute (combine pearl shards at a workshop). Ten realms, each with early / middle / late stages. [sourced: search excerpts of https://earlyguides.com/tale-of-immortal/walkthrough and /tips (search excerpt); the pages themselves returned 404]
- A populated world: "each character is a unique entity with their own friends, family, and life trajectory", and you can rise from Disciple to Elder to Sect Leader. [sourced: store page above] Actions such as stealing or killing create nemeses and change later NPC behaviour; you can romance, adopt disciples and build reputation. Five difficulty levels, the last with permadeath. [sourced: Wikipedia page above]
- Sect rank gates the manual library and resource halls. [sourced: search excerpt of earlyguides.com (search excerpt)]

Complaints

- VaporLens: "Excessive, repetitive grinding is tedious" 69, "Frequent crashes and poor optimization" 63, "Weak, uninteresting storyline and characters" 61, "Updates cause game-breaking bugs" 33, "Steep learning curve, poor guidance" 27. [sourced: VaporLens page above]
- A player's summary of the base loop: "just a hamster wheel of grinding for more stats." [sourced: https://steamcommunity.com/app/1468810/discussions/0/5019836142097266267]
- "Heaven's Chosen" NPCs were the most resented update: they "randomly have events that permanently boost their ATK rating for no reason", which players felt they could not match. [sourced: same thread]
- May 2022 review bomb: the developer had promised Steam Workshop, shipped mods on a third-party platform (Fanbook) with strict moderation and a tedious upload flow, apologised, and enabled the Workshop on May 31; the rating did not recover at the time. [sourced: https://www.superpixel.com/article/63719/tale-immortal-apologized-controversy-around-not-using-steam-workshop (search excerpt)]
- Infinite rerolls at creation mean a specific destiny combination "might not pop for hours": the game invites a boring optimum. [sourced: gamepretty guide above]

Inference: three things carry ToI. (a) A character is a *build* assembled from discrete, named, rarity-coloured choices made at the dramatic moments, so every breakthrough is also a decision. (b) Each realm asks for different things, so the next goal is always concrete. (c) Named rivals grow alongside you. Its failures are the mirror image: when the realm requirement is "the same loop in a new region" it reads as a hamster wheel, and when rivals grow by rules the player cannot see or use it reads as cheating.

### 1.3 Immortal Life (一方灵田; YiFang Studio, 1.0 in 2024)

- Premise: restore the Guiyun Sect after its near destruction; farming, cooking and crafting grow it. [sourced: search excerpt of the Steam page (search excerpt)]
- Store features: farm with magic through seasons and weather; fish, cook, make elixirs and furniture; "Classes and tests advance your cultivation"; more than 10 Mystic Realms; rebuild by acquiring spirit stones, unlocking territories and starting construction projects; help sect brothers and sisters "with their daily struggles", whose rewards "include items, missions, and skills", and invite them to share your dwelling. [sourced: https://store.steampowered.com/app/1201230/Immortal_Life/]
- Praise (VaporLens): "Gorgeous art style" 29, "Excellent farming sim" 24, "Fun cooking mini-game" 19, "Magic farming system praised" 16. [sourced: https://vaporlens.app/app/1201230/immortal_life]
- Press quoted on the store page: Kotaku, "the best farming game I've played in a decade"; Movies Games and Tech 7/10. [sourced: store page above]
- Complaints (VaporLens): "Slow movement speed issues" 14, "Clunky controls" 12, "No romance system" 12, "Overwhelming quests" 12, "No post-launch updates" 9, crashes 9. [sourced: VaporLens page above]

Inference: the relevant points are small. Cultivation here advances through *classes and tests*, which is the closest any of these games comes to Sect Academy's own premise, and nobody lists it as a complaint. The sect rebuild is a visible list of territories and projects. Helping a named person pays in a skill or a mission, not just a number. The cautionary note is "Overwhelming quests": too many open tasks at once was a top-five complaint in a cosy game.

### 1.4 Wandering Sword (The Swordman Studio, 2023-09-14)

- Praise (VaporLens): "Excellent wuxia atmosphere" 39, "Overall quality highly praised" 32, "Engaging storyline" 27, "Engaging characters and development" 21, "Dual combat modes praised" 18. [sourced: https://vaporlens.app/app/1876890/wandering_sword]
- Store: up to 14 recruitable martial artists, hundreds of techniques, cultivation through meridian points, multiple endings. [sourced: https://store.steampowered.com/app/1876890/Wandering_Sword/]
- Affinity is a number with published gates. From the companion guide: one character's quest line starts at 61 affinity; another's stages at 60 and 80; another's at 40 and 70; another's at 50 and 80; a token is given at 20 or more. Choices in scenes move affinity by +10. In one case reaching 70 changes whether a character lives. [sourced: https://gameplay.tips/guides/wandering-sword-official-companion-guide.html]
- Gifts: each usually adds 4 affinity, occasionally 12 if well liked; 60 to recruit; gift quality matters more than quantity; a story cap can block further gain. Companions earn martial points alongside you and you can learn their methods by "consulting" them. [sourced: search excerpts of finalboss.io and earlyguides.com guides (search excerpt); the guides disagreed on some figures]
- Meridians: six meridian maps per character; nodes cost from 10 and 30 points up to hundreds; some nodes are conditional effects (for example "When an ally dies"); points come mainly from learning and levelling cultivation methods; each character has a separate pool; you need not fill side branches before taking an endpoint. [sourced: https://finalboss.io/wandering-sword-meridian-upgrades-guide]
- Complaints (VaporLens): "Obscure Sidequests Lack Guidance" 39, "Rushed Ending and Late Story" 24, "Guide Dependency for Full Experience" 20, "Permanent Consequences for Missed Quests" 18. [sourced: VaporLens page above] The companion guide confirms the pattern: progress too far in the main story and a companion can never be recruited; one choice "will terminate all subsequent tasks". [sourced: companion guide above]

Inference: relationships work here because a bond is a *track with known stations*: at 40, 60 and 80 something specific happens, and the reward is a person's story plus something you can use (a technique). The complaints are entirely about hidden gates and silent permanent lockouts. Show the stations, and never close a door without saying so.

### 1.5 Hero's Adventure: Road to Passion (Half Amateur Studio, 2023-11-15)

- Praise (VaporLens): "Highly Addictive Gameplay" 65, "Expansive Wuxia Open World" 57, "Meaningful Player Choices" 31, "Rich, Diverse Content" 26, "Deep Choices, High Replayability" 15. [sourced: https://vaporlens.app/app/1948980/heros_adventure_road_to_passion]
- Store numbers: 30+ factions in a power struggle, 80 cities and villages, 300+ martial arts, over 10 endings, 18 bondable characters, 200+ narrative encounters added at 1.0 and 400+ adjusted. Encounters change your standing with the factions involved. A Homestead manages recruited characters and passes martial arts and weapons to another playthrough. [sourced: https://store.steampowered.com/app/1948980/Heros_Adventure_Road_to_Passion/]
- Complaints (VaporLens): "Fragmented Story & Depth" 45, "Unbalanced Combat & Grind" 33, "Poor Translation Quality" 20, "Lacks In-Game Guidance" 18. [sourced: VaporLens page above]
- Gift, favour and recruitment numbers: not found. [not verified]

Inference: its praise is for consequence (your conduct with factions decides which of ten-plus endings you get) and for carrying something forward into the next run. Its top complaint, a fragmented story, is what happens when encounters are many and unconnected. The sect has the same risk: plenty of tropes, little thread between them.

### 1.6 Idle cultivation games (Overmortal, Immortal Taoists)

I could not identify specific titles called "Idle Cultivation" or "Cultivation Simulator" with enough confidence to source them; the two below stand in for the category.

- Overmortal (LTGames). Cultivate in an Abode; three stages (early, middle, late) per realm; failing a bottleneck raises the chance next time "at the cost of the player having to wait some hours"; a Breakthrough Pill raises the odds and is consumed even on failure; two paths (Corporia for HP, Magicka for MP) with no penalty for the first choice; offline gains are capped; one realm farm runs 13 hours; a daily-capped tap activity; sect tasks finish after a set time and pay contribution; four or more currencies, one of them premium. No exact odds are published in the guide. [sourced: https://www.levelwinner.com/?p=75826]
- Overmortal complaints, from app-store aggregators: "Pay to Win"; whales dominate events; combat is tap-through. [sourced: search excerpt of https://justuseapp.com/en/app/6450879111/overmortal-idle-rpg/reviews (search excerpt)] That aggregator's sentiment percentages are machine-generated and I am not quoting them.
- Immortal Taoists. Manual cultivation is capped at 5 minutes a session until Foundation makes it automatic; qi ticks every 5 seconds and workers produce every 10; both accrue offline; the first tribulation is shown at 90% with +5% per Foundation Pill; workers' food upkeep rises with headcount. The guide's criticisms: it "offers no tutorials whatsoever", stats are unexplained, and automation makes goals unclear. [sourced: https://www.bluestacks.com/blog/game-guides/immortal-taoists/it-beginner-guide-en.html]
- One aggregator shows a 73% user score from 1,333 reviews for an Immortal Taoists listing; several apps share the name, so I would not rely on it. [sourced: search excerpt of gamebrain.co (search excerpt)]
- Reincarnation / rebirth loops and lifespan-driven resets in these games: [memory, unverified].

Inference: what the idle games do well is small and specific: the odds are printed, a failure visibly improves the next attempt, and every session opens with something to collect and something to send off. The sect already has all three (the `bt_odds` ledger, "Lessons of past failures", expeditions). What they do badly is the business model leaking into the design: wait timers on retries, daily caps, a currency for everything.

### 1.7 Yi Xian: The Cultivation Card Game (Darksun Studio, 1.0 on 2024-01-21)

- Free-to-play auto-battling deckbuilder, eight-player elimination. "Every time you break through, multiple Immortal Fates will appear randomly" and you pick one; fates depend on sect and character. Each Sub-Profession has its own exclusive cards. [sourced: https://store.steampowered.com/app/1948800/Yi_Xian_The_Cultivation_Card_Game/]
- You "absorb" cards to raise your Cultivation level, which decides who acts first, so every card is either a tool or fuel. Praise: art, the 8-way PvP, the roguelike PvE; cons: "Heavy reliance on RNG", minor translation issues. A reviewer says everything can be unlocked by play and it "avoids a pay-to-win system". [sourced: https://www.taptap.io/post/6866609]
- VaporLens had no analysis for this game. [not verified]

Inference: two independent, successful games (Tale of Immortal and Yi Xian) attach a *pick-one-of-several permanent boon* to the breakthrough moment. That is the strongest single pattern in this file.

### 1.8 Path of Wuxia

Only the SteamSpy numbers in the table were fetched. Its school-calendar structure (schedule each term, raise stats, befriend classmates) is [memory, unverified] and I draw no recommendation from it.

## 2. Patterns across the genre

Inference throughout.

1. **The breakthrough is the decision point, not just the payoff.** ACS grades it by preparation; ToI and Yi Xian hand you a permanent choice at it. In the sect today a great-realm breakthrough is a well-explained roll (`bt_odds`), and "perfect" is the luckiest fifth of successes (`roll < chance * 0.2`) worth +0.05 root multiplier. There is no reason to wait once the odds are acceptable, and nothing to choose afterwards.
2. **Characters are builds made of named, discrete parts.** Destinies, fates, laws, meridian nodes. Players describe a disciple by their parts. The sect's disciples have root, element, two traits, a path and one artifact; that is a start but it is nearly all rolled, not chosen.
3. **Each realm should want something different.** ToI's best and worst feature. A concrete list per realm gives direction; the same list every time is the hamster wheel.
4. **A bond is a track with stations.** Wandering Sword's numbers are public in guides because players need them. Stations pay out a story beat and a usable thing.
5. **Named peers who grow by the same rules.** ToI's world of cultivators is its hook; "Heaven's Chosen" shows what happens when they grow by different rules.
6. **Opacity is the genre's standing complaint.** It is in the top complaints of ACS, ToI, Wandering Sword, Hero's Adventure and Immortal Taoists. The sect's ledgers are a real competitive advantage and every new system below should ship with one.
7. **Micromanagement is the other.** ACS's single most frequent complaint. Standing orders beat more buttons.

## 3. Ranked recommendations (things the sect does not already have)

Checked against the code on 2026-11-25. Effort: S = under a day, M = a few days, L = a week or more, one developer. All text is templated; no real-time anything; everything lives in the one state file; nothing new fires in quiet mode; none of it is study-gated.

**1. Breakthrough grade, earned by preparation and timing. Effort M. Impact very high.**
- Reference: ACS Golden Core grade ("grade 4 to grade 1 with perfect breakthrough conditions").
- Why it works: it turns "the bar is full, press the button" into "press now for a Flawed core, or hold eight days for my season and a better pill and try for a Heaven-grade one, while the Black Lotus are two days out". It is a moment-to-moment decision whose result lasts the disciple's life.
- Build: keep `bt_chance` for *success*. Add a separate, deterministic `bt_grade(c, p)` for great realms, shown as a second ledger beside the odds: start at grade 0 (Flawed) and add one step for each of a short list the player can arrange: qi held past the threshold (let `p["qi"]` overfill to 130% of `step_need`), season favours the disciple's element, a named pill of the right kind rather than a common one, mood 85 or above, Meditation Chamber at level 2+, mentor or companion at home. Five grades (Flawed, Common, Fine, Flawless, Heaven-blessed). Store `p["grades"]` as a list, one per great realm. Effect: a per-realm qi multiplier (say 0.95 to 1.15) and the rarity of the fate offered in item 2. Replace the random `perfect` with grade >= Flawless so the existing poem and root bonus hooks still fire. Show the forecast: "Autumn favours Metal in 7 days."
- Guard: the grade ledger must list unmet rows greyed out with what would satisfy them, or it becomes ACS. Tune by simulation: an idle profile should land Common, a careful one Fine to Flawless.

**2. A fate chosen at each great realm. Effort S-M. Impact very high.**
- Reference: Tale of Immortal ("With each breakthrough, you'll be able to rewrite your destiny"); Yi Xian ("multiple Immortal Fates will appear randomly").
- Why it works: gives every success a second beat, and turns disciples into builds the player authored. It is the most repeated pattern among the successful games.
- Build: on a successful great-realm breakthrough, raise a pending choice (time already waits for pending events) offering three fates drawn from a table in `lore.py` of about 30, filtered by element and path and weighted by the grade from item 1. Each is one line and one hook into existing multipliers: "Sword Heart: +15% duel power, -10% farming"; "Verdant Pulse: herbs gathered +25%"; "Lightning-Tempered: +10 to all later tribulation odds"; "Lonely Peak: +12% qi while no friend is home, cannot take a dao companion". Prefer trade-offs to flat bonuses (ToI's most discussed destinies are the ones with a cost). Store `p["fates"]`; show them as coloured tags on the disciple's page and in `qi_rate` / `bt_odds` rows.
- Guard: no rerolls (ToI's infinite reroll invites hours of tedium). The draw is seeded from `_rng(c, "fate", p["id"], realm)` so reloading cannot fish.

**3. Expeditions you staff and steer. Effort M. Impact high.**
- Reference: ACS text adventures (praised as "a welcome change of pace"); ACS players' looping resource trips.
- Why it works: `expedition()` currently auto-picks the two strongest and resolves on one power roll. Choosing who goes is a real staffing decision (the strong ones are also your gate defence), and one mid-trip choice makes the result feel caused.
- Build: let the player pick 1 to 3 disciples and one of two or three stances (cautious / thorough / bold, trading risk for yield). At the halfway hour raise one pending choice from a small per-place table (about six per place), where the options key off who is on the team: "The den is occupied. [Fight: needs duel power >= X, shown] [Lure it out: needs a Wood or Water root] [Leave]". Fates from item 2, paths and elements become keys. Return report lists what each choice did.
- Guard: one party out at a time stays. In quiet mode a party that reaches its choice simply waits at it, as other events do.

**4. Bond tracks with visible stations for the Master's relationship with each disciple. Effort M. Impact high.**
- Reference: Wandering Sword affinity gates (20 / 40 / 60 / 80); Immortal Life (helping a sect sibling pays "items, missions, and skills").
- Why it works: the sect has disciple-to-disciple bonds but the player's own avatar has no personal relationship track with anyone. A track with three known stations per disciple gives a long-term goal per person and a use for the origin/backstory.
- Build: `p["trust"]` 0..100 with the Master, raised by things the player already does (assigning them their best job, giving an artifact, sparing them from a fight while hurt, honouring a promise) and lowered by the reverse. At 30, 60 and 90 a short templated scene from their origin fires as a pending choice and grants something usable: a small permanent skill, a recipe, a unique manual, their willingness to be named successor. Show the bar with the three stations and what unlocks at each.
- Guard: never lock a station silently. If something would close a thread (their rival's death, exile), say so in the option text before the player commits. This is Wandering Sword's most avoidable complaint.

**5. Named rival cultivators who rise by your rules. Effort M. Impact high.**
- Reference: Tale of Immortal's world of NPCs with their own trajectories; the "Heaven's Chosen" backlash as the limit.
- Why it works: rival sects exist as three opinions. Two named peers per sect, with a realm that advances, give the tournament, the young-master event, sieges and auctions a recurring cast, and give the player someone to measure a prized disciple against.
- Build: at world creation, two cultivators per rival sect: name, element, root, realm step, one fate from item 2's table, an attitude to one of your disciples. Each sim week they roll the same `bt_chance`-style check with a visible simplified ledger. Events draw their named actor from this cast. A "Peers" panel lists them with realm and last deed. Beating one in the tournament, sparing one, or losing a disciple to one writes a `rel` between two named people.
- Guard: they must use the same realm ladder and odds, shown on their card, and must not advance in quiet mode. No hidden stat events.

**6. A meridian chart per disciple. Effort M. Impact medium-high.**
- Reference: Wandering Sword's six meridian maps with 10- and 30-point nodes and conditional effects.
- Why it works: a second, slower build axis fed by ordinary progress, so even a small-stage advance gives the player something to spend. Conditional nodes ("when a friend is wounded", "in their own season") tie into bonds and elements the sect already simulates.
- Build: one shared chart of about 14 nodes in three short branches (body, spirit, heart) plus two element-locked endpoints. One point per small stage, three per great realm. Nodes are plain multipliers on existing hooks. Store `p["nodes"]` as a list of ids. An "elder's suggestion" button fills it for players who do not care.
- Guard: skip this until 1 and 2 are in; three new per-disciple build systems at once would recreate ACS's learning curve.

**7. Realm-specific requirements. Effort S-M. Impact medium-high.**
- Reference: Tale of Immortal (six Qi Pearls for Golden Core, with a slower non-combat substitute).
- Why it works: gives each great realm its own short shopping list, which is what makes "the next breakthrough" a plan and links expeditions, alchemy, the forge and rival relations to cultivation.
- Build: one extra requirement per great realm from Foundation up, each obtainable two ways (ToI's substitute is the important part): Foundation needs a Foundation pill (brew, or buy at auction); Core Formation needs a beast core (Beast Forest expedition, or trade with an allied sect); Nascent Soul needs a soul-calming treasure (Ruined Sect, or a Great Work). Show it as a row in the breakthrough panel with both routes named.
- Guard: one item per realm, never a quantity grind; and never obtainable only through study or only through combat.

**8. Standing orders. Effort S. Impact medium-high (it removes cost rather than adding content).**
- Reference: ACS's top complaint ("Frustrating micromanagement and AI", 69) and its players' workaround of looping trips.
- Build: three toggles stored in `c["orders"]`: repeat the last expedition when the party is rested; keep N pills in stock (brew when below); auto-attempt *small-stage* work as now but never great realms (those stay the player's). Each order writes a letter when it acts, so it is visible. Also let work priorities be saved as two named presets.

**9. Conduct-based epilogues. Effort S-M. Impact medium.**
- Reference: Hero's Adventure (over 10 endings decided by standing with 30+ factions; "Meaningful Player Choices" is its third most cited praise).
- Why it works: the sect already tracks fame, precepts kept or broken, the demonic path, alliances, the lord's favour and who died. Ascension currently produces one letter. Reading back *what kind of sect this was* rewards the long game and invites a second one.
- Build: at ascension (and viewable in progress as "how the annals would remember us"), pick one of about eight epilogue templates from the dominant axes (righteous / demonic, feared / beloved, alone / allied, lineage intact / broken) and fill in named people from the annals. Show the two axes as a small compass on the annals page so the player can steer.

**10. Carry a legacy into a branch sect. Effort M. Impact medium, high for replay.**
- Reference: Hero's Adventure's Homestead ("passing martial arts and weapons to another playthrough"). The colony-sim notes proposed a branch-sect ending; it is not built.
- Build: after succession, offer "found a branch sect": a new colony in the same state file that starts with one chosen manual, one artifact, one disciple and the parent's annals as a read-only first chapter. The parent is archived, not deleted (exportable). No power multipliers carried over.

**11. Hosting guests. Effort S. Impact medium.**
- Reference: ACS (hosting another sect's disciples in comfortable rooms earns 17 to 50 favour each).
- Why it works: relations today move by gifts of spirit stones and by events. Hosting makes room quality and food stock diplomatic assets and creates a visible trade-off (a bed and rice for a guest versus a recruit).
- Build: an action on a rival sect's card: invite a guest for six days. Costs a spare bed and their rice; pays relation scaled by room levels and mood of the house, and a chance of a bond with one of your disciples (or with a named peer from item 5).

**12. A discovered-rules codex. Effort S. Impact medium.**
- Reference: the opacity complaints in section 2, point 6; "Guide Dependency for Full Experience" (Wandering Sword, 20).
- Build: a Codex page generated from the live tables (`lore.MANUALS`, `RECIPES`, `PATHS`, `PRECEPTS`, the fate table, the grade ledger), listing an entry in full once the sect has met it and as "???" with a hint before. It is generated, so it cannot drift from the rules.

Suggested order: 1 and 2 together (one release: "the breakthrough is a decision"), then 8 and 12 (cheap, and they pay for the complexity added), then 3 and 7, then 5 and 4, then 9, 11, 10, and 6 last.

## 4. What not to copy

1. **Wait timers and daily caps as pacing.** Overmortal makes you "wait some hours" after a failed bottleneck and caps a daily tap activity; Immortal Taoists caps manual cultivation at 5 minutes. These exist to sell skips. The sect's rule that time waits for the player is the opposite and should stay.
2. **A requirement that is the same loop again in a new place.** Tale of Immortal's most frequent complaint (69) is repetitive grind. If item 7 is built, each realm's requirement must be a different *kind* of thing, with two routes, and never a count above one.
3. **Rivals who grow by hidden or unmatched rules.** "Heaven's Chosen" NPCs gaining permanent attack "for no reason" was the most resented ToI update. Item 5 must show its working.
4. **Depth without explanation.** ACS's three largest complaint themes (micromanagement 69, learning curve 68, unexplained mechanics 56) each outweigh its top praise theme (58). Do not ship a system without its ledger. In particular do not copy ACS's time-of-day and weather windows as extra hidden axes; the season-element window already in the sect is enough.
5. **Silent permanent lockouts and guide dependence.** Wandering Sword: "Permanent Consequences for Missed Quests" 18, "Guide Dependency" 20, "Obscure Sidequests" 39. Any door that closes must say so first.
6. **Unlimited rerolls and many currencies.** ToI lets you reroll starting destinies forever, which makes the dull strategy the best one. Overmortal runs four-plus currencies. Seed the draws; keep spirit stones and merit as the only two.
7. **Too many open tasks.** "Overwhelming quests" is a top-five complaint for Immortal Life. Keep one promise and one expedition at a time.

## 5. Gaps and unverified claims

- **Reddit** was blocked for the fetch tool, so there are no Reddit threads in this file.
- **Steam review text** was not read directly. The Steam review JSON endpoint redirected to the store front page. Themes come from VaporLens's automated summaries; totals from SteamSpy; English-only percentages from store pages.
- **Fandom wikis** for ACS and Tale of Immortal were not reached; mechanics come from community guides and Steam threads, which may describe older builds. The ACS Golden Core numbers in particular are players' rules of thumb, not a formula.
- **Tale of Immortal**: that you choose one of three fates at each breakthrough, and the exact colour tiers of those fates, are from memory. The earlyguides.com pages returned 404 and are cited only as search excerpts. Per-realm lifespan gains beyond Foundation were not found. The 1.8 million sales figure was not confirmed in body text.
- **Wandering Sword** gift values (4 / 12) and the 60-to-recruit rule come from search excerpts of guide sites that disagreed with each other.
- **Hero's Adventure**: no numbers for gifts, favour or recruitment were found; the reason for its recent "Mostly Negative" reviews was not investigated.
- **Idle games**: no title named exactly "Idle Cultivation" or "Cultivation Simulator" was identified. Overmortal's odds, timer lengths and offline cap are not published in the guide read. Pay-to-win complaints rest on a search excerpt of an app-review aggregator. Reincarnation loops are from memory.
- **Yi Xian**: "side jobs" appear on the store page as Sub-Professions; nothing further was read. No review-theme summary was available.
- **Path of Wuxia**: only review totals.
- **Immortal Life**: the GamesRadar article returned only its headline; its release year is from memory.
- SteamSpy owner bands and playtimes are estimates by that service.
