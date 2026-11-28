# Sect overhaul plan: builders, a Main Hall ladder, raids, leagues and room play

Status: **approved by the owner on 2026-11-27, with the recommended default for every open
question (section 7 records the decisions).** Written 2026-11-27
against `sect_academy/colony.py`, `dao.py`, `road.py` and `tests/balance.py` as they stand on
branch `claude/brave-volta-6tsola`.

The owner's brief: *"Clash of Clans, but actually able to keep players"*, plus four Fallout
Shelter ideas already approved: drag disciples into rooms, tap a room to collect what it made,
rush a room at a risk, and upgrade rooms and merge rooms that sit side by side. The gold "↑"
badges on the home map go; a room you can upgrade gets a soft glow and a "+" in its name label.

Sources are numbered [1]–[14] and listed at the end. "Inference" marks my own reasoning. Every
number below is a starting value to simulate, not a measurement.

---

## 1. What keeps players and what loses them

**What keeps players coming back**

- **Short timers you start before leaving.** Boom Beach units take "5 to 30 minutes" early to
  mid game, which one analysis credits for short- and mid-term retention [3]. Supercell cut Clash
  of Clans building times "up to 50%" for Town Halls 2–11, "to facilitate player progression" [4].
- **Coming back to something finished.** Offline progress "creates a celebratory moment every
  time you return", and well-made idle games keep players well without offline caps [7]. Gold &
  Goblins keeps resources made offline for the player to collect, which "reinforc[es] positive
  return behaviour" [8].
- **Timers of mixed lengths**, so "there's always something to return to" [8].
- **One long goal that reorganises everything** (the Town Hall). This is Inference, but it matches
  how [4] and [5] describe progress being paced by Town Hall levels.
- **Positive reasons to return, not threats.** Boom Beach uses "positive incentivization" and "no
  negative retention incentivization whatsoever" [2].
- **Retention as the first goal.** Hay Day's leads called retention "our one metric" [6]; its
  neighbourhood derbies are credited for long-term retention [13].

**What loses players**

- **Timers of days or weeks.** One long-time Clash player quit when "any upgrade took days to
  complete" [5]. Clash waits can run to "weeks of waiting time" [2]. In idle games, "once timers
  grow, players hit a wall" [8].
- **Losing loot while away.** The same player found that raiders took so much that buying gems
  was the only realistic way to upgrade [5]. Clash's negative incentive is coming back to protect
  your resources; Boom Beach's vault still loses about 59% / 83% / 93% after 1 / 2 / 3 raids [2].
- **The builder gate.** That player's first purchase was an extra builder, "a hard gate designed
  into the game" [5].
- **The wall grind.** "89 need 200,000 gold each to upgrade to level 7" [5].
- **Pay-to-skip.** Upgrading a whole base would have cost "49,225 gems" [5], with "only ever a
  brief plateau of satisfaction" [5].
- **Content that runs out, and no long goal.** Fallout Shelter "can be finished in about a
  weekend". Its new rooms "don't add anything new". A vault "full of happy dwellers just doing
  their jobs" left "nothing left to pull me back", and there was no player-versus-player raiding
  [1]. Nielsen tied drop-off in "big bang" launches to unmet demand for new content [9].
- **Energy caps.** These exist to sell refills, as do Overmortal's retry waits and daily caps
  ([memory, unverified] for energy in general; Overmortal from
  `docs/research/notes/competitors_cultivation_games.md` §1.6).
- **Grind, opacity and micromanagement**, the standing complaints in cultivation games
  (`competitors_cultivation_games.md` §2: ACS micromanagement 69, Tale of Immortal grind 69).

**What follows for us** (Inference). We take the structure of Clash: builders, a Town-Hall
ladder, a defence layout, raids and leagues. We keep every timer to hours at most. Nothing can be
lost while the app is closed. There is nothing to buy. Every step has a visible goal and a
ledger. Fallout Shelter's room play fills the minutes in between. Its failure, no long goal, is
what the Main Hall ladder, the raids and the seasons are for.

---

## 2. Ground rules this plan keeps

- **The sect stays optional** (`colony.enabled()`). Nothing here touches study when it is off, and
  no study feature waits on the sect.
- **Study helps and never gates.** A counted session can shave build time or lend a builder. No
  building, raid or league needs study. The reward is flat per counted session, never scaled by
  accuracy (`ui_psychology.md`, overjustification).
- **Nothing bad happens while the app is closed.** Quiet mode runs no raids, no rush incidents and
  no league losses. AI rivals do not climb while you are away.
- **Time waits for the player.** Events still hold the sim. The one exception (decided, section 7
  question 1): builders keep working while an event waits, because building can only help.
- **Every number is in a ledger**: build time, rush odds, layout factor, star odds, league points.
  They go through the `*_rows` pattern (`dao.qi_rows`, `bt_rows`, `colony.farm_rows`,
  `research_rows`).
- **Painted art only**, in `static/art/` as WebP, from the fixed list in `app.py`. Section 6 has the
  brief.
- **Offline only.** The AI ladder and the rival bases are generated from the seed (`_rng`).
- **Difficulty is tuned by simulation.** Every stage reruns `python tests/balance.py 150 12345,7,99`
  and keeps `tests/test_balance.py` green. Idle play must still starve or lose people on
  balanced and harsh. Careful play must still survive balanced.
- **Excluded outright:** payment of any kind, premium currency, energy or stamina caps, losses
  while offline, timers over a day, per-segment wall upgrades, daily login chests, anything that
  blocks or nags study, and anything that makes the sect required.

---

## 3. The systems

### 3.1 Builders and short upgrade timers

**What it is.** Building moves from "disciples on the Build job work off the hours" to **builder
slots**. Each slot runs one job on its own clock and finishes even if nobody is assigned. You
start with 2 builders and gain one at Main Hall 3, 6 and 9, for 5 in all. Disciples on Build
become **helpers**: each adds +25% speed, up to 2 per site, times their Construction skill. This
keeps the Build job and the Construction skill useful.

**Why it keeps players.** Short timers bring players back [3][4]. A finished job waiting on
return is the celebratory moment [7][8]. A builder that cannot stall removes a frustration point.

**How it fits the sim.**
- `c["builds"]` stays as the queue, with a new `slot` field. `queue_build` checks free builders
  instead of the cap of four.
- `build_hours` becomes the table below.
- `_tick_pawn`'s build work becomes a helper bonus on the slot.
- Materials are still paid when the job is queued, and `cancel_build` still refunds them.
- `build_stall` and its alert are retired, since a slot cannot stall.
- Timers are in **sim hours**, so there stays one clock. Away time runs one sim hour per 30 real
  minutes (`SECS_PER_HOUR_OFFLINE`). A 16-hour job started before bed is done in the morning, and
  watching at ×1 finishes it in about a minute. The UI shows both: "about 8 h if you close the
  app, about 1 min watching".
- Study can add a builder or shave time but never gates:
  - `on_session` (counted) gives a **Master's Blueprint**: −25% off the remaining time of one
    running job. One per real day, and it can be banked for 3 days.
  - Meeting the weekly goal (`WEEK_GOAL`) lends the Master as a **6th builder for 24 sim hours**.

**Numbers to start from** (sim hours, then real hours if you close the app):

| Level reached | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Room | 1 (0.5 h) | 2 | 4 | 6 | 9 | 12 | 16 | 20 (10 h) | – | – |
| Main Hall | – | 4 (2 h) | 8 | 12 | 16 | 20 | 24 | 28 | 32 | 36 (18 h) |

Nothing is longer than 36 sim hours (18 real hours), well inside `MAX_OFFLINE_HOURS`. The cost
curve goes from `1.8**level` to `1.6**level`, because room levels rise from 5 to 8; costs are to
be retuned by simulation.

**How it is tested.**
- `test_colony`: a slot finishes with zero helpers. Helpers speed it by the ledger amount.
  `quiet=True` catch-up finishes a job and writes no bad letter. The Blueprint applies once a day
  and never when the sect is off.
- `balance.py`: the careful profile uses builders. Idle never builds and must still starve.
- A new balance column, `idle_builder_hours`, counts the share of hours a slot stood empty for
  want of materials, the stand-in for the "builder bottleneck". Target: under 35% for careful
  play by day 60.

### 3.2 Main Hall level as the long goal ladder

**What it is.** The Main Hall goes from 5 levels to 10. Each level opens something you can name.
The next level is always shown as a card ("Main Hall 4: what it opens") on the home view, so
there is always a near goal.

**Why it keeps players.** A long goal you can see, broken into near steps, uses the
goal-gradient effect (`ui_psychology.md`). It also answers Fallout Shelter's missing long goal [1].

**How it fits the sim.**
- `ROOMS["main_hall"]["max"] = 10`.
- `pawn_cap` stays `3 + 2·level`, so the cap reaches 23.
- The existing rule, a room at most one level above the Hall, stays.
- A new `HALL_LADDER` table in `colony.py` lists what each level opens. `view()` sends it so the
  UI can draw the card.
- Anti-rushing guard: to raise the Hall to level n+1, three other rooms must be at level n or
  higher. The card shows this as a checklist.

| Hall | Opens |
|---|---|
| 1 | Dormitory, Rice Terraces, Storehouse, Ward Formation. 2 builders. Courtyard: 4 pieces. Rooms up to level 2. |
| 2 | Scripture Pavilion, Training Grounds, Meditation Chamber. **Raiding** (1 rival base). League: Village Sects. |
| 3 | 3rd builder. Alchemy Hall. **Merging** (2 wide). Talisman snares. |
| 4 | Spirit Vein. War party of 3. Second rival base. Rooms up to level 4. |
| 5 | Trade Post. 3-wide merges. Sword-array towers. |
| 6 | 4th builder. Third rival base. War party of 4. Rooms up to level 6. |
| 7 | A second approach to defend (raiders may come by the cliff stair). Grand ward pillar. |
| 8 | Rooms up to level 7. A war party may carry pills. |
| 9 | 5th builder. War party of 5. |
| 10 | Rooms up to level 8. The sect banner (a cosmetic). Eligible for the top league. |

**How it is tested.**
- A table-driven test checks that every ladder unlock exists and is reachable.
- `balance.py` reports `hall_by_day` (the level at days 30, 60, 90, 150). Careful play should
  reach about Hall 4 by day 60 and 7–8 by day 150. Idle play stays at 1.

### 3.3 Defence courtyard layout and raid replays

**What it is.** A painted courtyard in front of the gate, a grid of 8×5 tiles. You place a few
pieces:
- **Ward pillars**, which spread the existing Ward Formation power over the tiles they cover.
- **Sword-array towers**, which multiply the guard posted beside them.
- **Talisman snares**, which work once per raid.
- **Guard posts**, where you drag disciples.
- **One gate wall**, a single ring whose level follows the Main Hall. There are no wall segments
  to upgrade one by one.

Raids by AI rival sects still come as an omen (`_omen`), which now names the approach: "they come
up the west stair". You choose a stance as today. After the fight, a **replay** plays: a 15–20
second top-down storyboard of tokens moving on the courtyard, with a log of 8–15 lines ("The
snare at the stair held three raiders", "Lin Wei held the east post"). It can be replayed from
the Chronicle.

**Why it keeps players.** A defence log is a reason to look and rearrange, and Clash pairs its
log with revenge [12]. Inference: here it works as a puzzle you improve, not a fear of loss.
Because raids never happen while the app is closed, the log only ever shows fights you watched
and chose how to meet. This removes the negative incentive of [2] and [5].

**How it fits the sim.**
- `battle_strength` gains one ledger row: **layout factor**, 0.85–1.25. It is deterministic: the
  share of the named approach's path that ward pillars and towers cover, plus the guard posts
  manned.
- `_battle`'s ratio bands (1.4 / 0.9 / 0.55) and `theft_share` stay as they are, so the existing
  balance tests still hold.
- The replay is **generated from the outcome and the layout** (seeded by `_rng(c, "replay", day)`).
  It never contradicts the verdict or the ledger: a test asserts its end state matches the band.
- The replay is stored compactly on the scene (`_scene(..., replay=[...])`). It goes under the
  scene cap and through `_repair_scenes`.
- Raids still never fire in quiet mode (`_daily_event` only runs when watching), and sieges
  (`dao`) keep working on top.

**Numbers to start from.**
- Pieces by Hall level: 4, 6, 8, 10, 12 at Halls 1, 3, 5, 7, 9.
- Layout factor: 0.85 with nothing covering the path, up to 1.25 with full coverage and every
  post manned.
- A snare takes 6% off the foe's strength, once per raid.
- A tower gives ×1.3 to the disciple posted next to it.

**How it is tested.**
- Unit tests: layout factor bounds; the factor shows in the omen text and the ledger; the replay's
  final state matches the verdict; no raid in `catch_up`.
- `balance.py`: the careful profile places a stock layout. Idle has none (factor 0.85), which
  should make idle play slightly worse. Re-check that "careful loses something on most seeds"
  still holds.

### 3.4 Raiding AI rival sect bases (1–3 stars)

**What it is.** From Main Hall 2, a **war party** (2 disciples at first, 5 at Hall 9) can march on
one of the three rival sects (`c["sects"]`). You see their courtyard (scouting), pick the
approach and a stance, and send them. On arrival a scene plays the assault with a replay, and
pays **1–3 stars**:
- ★ the gate is broken
- ★★ the hall is reached
- ★★★ the sect is humbled

**Why it keeps players.** This is the "social" and competitive layer Fallout Shelter lacked [1].
It is an active use for loot and a reason to train fighters. Boom Beach's all-or-nothing outcome
focused players on protecting their HQ [11]. Inference: graded stars give partial credit, which
softens failure.

**How it fits the sim.**
- It reuses the expedition machinery in `road.py`. A raid is a `PLACES`-like destination with
  travel of 6 sim hours each way, the mid-trip choice (`_trip_mid`), the stance table (`STANCES`)
  and "one party out at a time".
- Rival bases are generated from the seed and from `s["power"]`, and scaled to your Hall level,
  as `tournament_field` scales its field. Each has a stock of loot.
- The star odds are printed on the order button, and the resolver uses the same roll, as
  `tournament_odds` does today.
- Raiding lowers that sect's relation by −10 (`_rel`), so they raid you more often. This is the
  risk that loops back. An allied sect cannot be raided without breaking the alliance (`dao.ally`).

**Numbers to start from.**
- Ratio = party strength / (their defence × their layout factor), rolled in 0.85–1.15.
- Stars: 1★ at 0.8 or better, 2★ at 1.1, 3★ at 1.5.
- Loot: 10%, 25% or 45% of their shown stock. Standing: +8, +14 or +20 (see 3.5).
- A base can be raided again after it rebuilds for 2 sim days.
- Wounds follow the bands in `_battle`. **A war party never loses anyone to death.** Recommended:
  wounds only, on every storyteller.

**How it is tested.**
- Odds shown equal the resolver's odds, as the existing tournament test checks.
- A raid cannot start in quiet mode, and a party away when the app closes waits at its mid-trip
  choice.
- `balance.py`: a careful profile that raids when 2★ odds are ≥60%. New columns: `raids_made`,
  `stars`, and `raided_back` (rival raids after a raid).

### 3.5 Fame leagues and seasons, against an AI ladder

**What it is.** A new number, **Standing**, kept apart from `fame` so recruit and wanderer tuning
is not disturbed. It is earned by raid stars and by defending. There are five leagues: **Village
Sects → County → Province → Kingdom → Under Heaven**, at Standing 0, 200, 500, 900 and 1400. Each
league is a ladder of 15 named AI sects, made from `lore` names, whose Standing drifts each sim
day by a seeded, published rule ("climbs about 9 a day"). A **season is one sim year (48 sim
days)**. At its end, a scene ranks you and pays by league:
- spirit stones
- a treasure (`_loot_treasure`) from Province up
- a banner colour (`dao.set_style`)

Then Standing above the league floor is halved. You never drop below your league's floor.

**Why it keeps players.** Seasons add a second layer of progress that resets friction while the
core timers run [8]. Inference: a ladder of named rivals gives the measuring-stick that Hay Day's
derbies gave socially [13], without other players.

**How it fits the sim.**
- `c["league"] = {"standing", "season", "ladder": [...]}`, coerced in `sanitize`/`_repair`.
- The ladder drifts in `dao.daily` **only when not quiet**. AI rivals do not climb while you are
  away, so you can never fall in rank by being absent.
- Defending gives +4 to +10. Losing a defence costs at most −3. Losses are deliberately smaller
  than gains.
- Every change is a row in a **Standing ledger** on the World tab.

**How it is tested.**
- No Standing change in `catch_up`.
- Standing never goes below the league floor.
- Season-end soft reset arithmetic.
- `balance.py` columns: `league_day` (the day each league is reached) and `season_rank`. Target:
  careful play reaches Province by the end of season 3; idle play stays in Village.

### 3.6 Fallout Shelter room play

**(1) Drag disciples into rooms.**
- Dropping a disciple on a room makes that room's job their **post**: priority 1 for that job,
  the rest unchanged.
- While you drag, each room glows green, amber or grey for how well they suit it (`suit()`, skill
  and passion).
- A slot count per room is shown ("Terraces 3/4").
- Tap a disciple, then a room, for touch and keyboard users.
- Drop them on a courtyard post for defence.
- New `set_post(st, pawn_id, room)` calls the existing `set_priority` and stores `p["post"]`.
  `_pick_job` is unchanged.
- The RimWorld grid stays as **Detailed priorities**. This is the "Simple mode" that
  `ui_psychology.md` already asked for.
- Why: direct manipulation is the quickest way to give an order, and it cuts the micromanagement
  complaint (ACS, 69).

**(2) Tap to collect room output.**
- Output from Terraces (rice), Alchemy Hall (pills), Spirit Vein (spirit stones) and the
  Storehouse yard (gathered wood, stone and herbs) collects in a **tray** on the room.
- The room's lanterns brighten and the plaque shows "🌾 24". Tapping banks it with a short
  count-up.
- **Nothing is lost by not tapping:**
  - Upkeep draws from trays automatically when the store runs short.
  - Trays bank themselves at dawn and whenever they are full.
  - Quiet mode banks them as it goes.
- A tap gives the crew a small "The Master inspected our work" thought: +3 mood for 12 sim hours,
  once per room per day, in `mood_mods` (decided, section 7 question 3).
- Why: the return moment [7][8], made physical.

**(3) Rush a room or a build, at a risk.**
- **Rush a room**: deliver 6 sim hours of its output now.
- **Rush a build**: finish it now.
- Shown odds of an **incident**: base 10%, +15% for each rush of that room in the last 2 sim days
  (decaying 15% a day), −1% for each average crew skill level above 7, capped at 70%. Community
  reports agree that each rush raises the next one's risk and that a failed rush resets the timer
  [10].
- An incident (a pill-furnace fire, a qi deviation, a beast in the terraces) is a small scene:
  - The crew's strength is set against the incident's.
  - On failure, the rushed output is lost, the room is idle for 6 sim hours and the crew take
    5–15 wounds. **Never a death.**
  - A rushed build that fails returns to where it was, plus 2 sim hours, and loses 10% of its
    materials.
  - On success, the crew gain XP and a "Proud of the work" thought.
- Rushing is a player action, so it can never happen while the app is closed.
- Rows go in a new `rush_rows(c, room)`.

**(4) Room upgrades and merging adjacent rooms.**
- Rooms become instances on a grid of 5 floors × 6 slots (`c["plots"]`: type, level, floor,
  slot, width). Floors open with the Hall.
- Building a room next to one of the same type and level **merges** them, up to 2 wide (Hall 3)
  or 3 wide (Hall 5).
- Fallout Shelter's merged rooms take more dwellers and run more efficiently, and upgrading two
  merged rooms costs 25% less than two single rooms (three: 50% less) [10].

| Width | Staff slots | Yield | Upgrade cost | Upgrade time |
|---|---|---|---|---|
| 1 | ×1 | ×1.0 | ×1 | ×1 |
| 2 | ×2 | ×1.1 | ×1.5 | ×1.25 |
| 3 | ×3 | ×1.2 | ×1.5 | ×1.5 |

- `_lvl(c, type)` stays as the compatibility function, returning Σ level × width. Every existing
  formula still works: beds, farmers, ward power, research speed. The merge bonus is its own
  ledger row (`farm_rows`, `research_rows`, `qi_rate` and so on).
- Old saves migrate: each room type becomes one width-1 instance at its level, in the slot that
  matches today's painting.
- Why: room play is a spatial puzzle with a clear reward, and Fallout Shelter's best minute to
  minute feel.

**(5) The home-map badge change.** The gold "↑" (`sect.js` line ~206) is removed. A room you can
afford to upgrade gets a soft lantern glow and a "+" after its level in the plaque ("Rice
Terraces 2 +"). It keeps its aria-label ("you can afford the next level").

**Tests for 3.6.**
- `set_post` respects slot counts.
- Upkeep draws from trays (a test with every tray full and the store empty: nobody goes hungry).
- Trays bank at dawn and in quiet mode.
- Rush odds equal the roll. No rush happens in quiet mode.
- Merge rules: same type and level, adjacent, width at most 3.
- Migration keeps `_lvl` identical for an old save.
- `balance.py` adds a careful profile that collects twice a sim day and one that never collects.
  Their food and death numbers must match within noise, which proves tapping is optional.

---

## 4. Staged build order

Each stage ships on its own, keeps all four CI gates green (packs, pytest, ruff, browser smoke),
reruns the balance table, and ends with **desktop screenshots at 1366×900** (home fold, the new
panel, phone 390 px for the changed screen), added to the playtest notes.

| Stage | What ships | Replaces | Keeps | Screenshot checkpoint |
|---|---|---|---|---|
| **1. Map polish** | Remove the "↑" badges, add glow + "+". Add the tray glow (visual only). Add the "Main Hall: what it opens" card. | `.can` badge | Everything else | Home fold, desktop and phone |
| **2. Builders** | Builder slots, the timer table, helpers, Blueprint and Master-as-builder study hooks, "ready in" times | The disciple-only build model, `build_stall` alert, cap of 4 jobs | `c["builds"]`, cost payment, cancel refund | Build tab with 2 running slots; return-from-away letter |
| **3. Main Hall 1–10** | `HALL_LADDER`, room levels to 8, cost curve 1.6, the three-rooms rule | Hall max 5 | `pawn_cap` formula, the one-above rule | The ladder card at Hall 1 and Hall 4 |
| **4. Drag, tap, rush** | Posts by drag and tap, room slots, trays, rush with incidents and `rush_rows` | Nothing (the Work grid becomes "Detailed") | `_pick_job`, priorities | Drag in progress; a tray tap; a rush odds sheet; an incident scene |
| **5. Grid and merging** | `c["plots"]`, floors, merge, migration, new home painting | Fixed `SITES` in `art.js`, `c["rooms"]` as the stored form | `_lvl` as the API | Home with a 3-wide merged Terraces |
| **6. Courtyard and replays** | Courtyard layout, layout factor row, named approaches in omens, replay storyboard | Nothing | `_omen`, `_battle` bands, sieges | Courtyard editor; an omen naming the approach; a replay mid-play |
| **7. Raiding rivals** | War party, rival bases, stars, scouting | Nothing | Expeditions (`road.py`), relations | Scouting screen; a 2★ result scene |
| **8. Leagues and seasons** | Standing, the AI ladder, season-end scene, reset | Nothing | `fame` and `renown()` as reputation | League ladder; season-end scene |

Stage 5 as built: one room of each kind (its level stays in `c["rooms"]`, `c["plots"]` holds floor, alcove
and width), and merging is a wing built beside the room at its level; the Main Hall stays two alcoves wide.
CLAUDE.md has the rules.

Stages 1–4 work with today's painting. Stage 5 needs the new home art; until it is painted, the
grid can be drawn over a backdrop the way `art.scene()` falls back today.

---

## 5. Balance plan

- **Before stage 2**, record today's table as the baseline: `python tests/balance.py 150
  12345,7,99`. On seed 12345 at 60 days, careful balanced shows 0 deaths, minimum food 5.9 days
  and 13 rooms.
- **New columns**, in order of stages: `idle_builder_hours`, `hall_by_day`, `rush_incidents`,
  `layout_factor`, `raids_made`, `stars`, `raided_back`, `league_day`, `season_rank`, and a
  `no_collect` profile.
- **The pinned shape still holds** (`test_balance.py`):
  - Idle starves or loses people on balanced and harsh.
  - Careful survives balanced and still loses something on most seeds.
  - No gap of more than 6 days without a decision.
  - Great-realm odds stay under `BT_CAP`.
- **New pins:**
  - Careful play reaches Hall 4 by day 60.
  - No build takes more than 36 sim hours.
  - Never-collect play matches collect-twice-a-day play.
  - Standing never changes in quiet mode.
  - A raid that earns 3★ is rare before Hall 5 (under 20% of raids).

---

## 6. New art needed (short brief)

All of it is painted in the existing lantern-night palette (`static/art/hq.webp`), as WebP, with
filenames added to the fixed list in `app.py`. The full brief goes in `docs/ART_PIPELINE.md` as
"Round 4".

1. **`hq_grid.webp`**: the cut-away mountain, 5 floors of rock-cut alcoves, 6 per floor, with
   empty alcoves visible.
2. **Room tiles, `room_<type>_<tier>.webp`**: 11 room types × 2 tiers (levels 1–4 and 5–8), each
   one alcove wide and painted so that 2 or 3 side by side read as one hall (shared
   beams at the edges). That is 22 tiles; the owner chose 11 first (section 7 question 4).
3. **`courtyard.webp`**: the gate courtyard seen from above at three-quarters, with an 8×5 tile
   grid you can just make out and three approaches (the gate road, the west stair, the cliff
   path).
4. **Piece sprites** (small, transparent WebP): ward pillar, grand ward pillar, sword-array
   tower, talisman snare, gate wall (3 tiers), guard post, and three raider tokens (righteous,
   demonic, bandit).
5. **Rival courtyards**: three re-colourings or variants of the courtyard (righteous jade,
   demonic crimson, neutral ochre).
6. **Scenes**: `scene_assault.webp` (your party at a rival gate), `scene_season.webp` (a ranking
   ceremony), `scene_incident.webp` (a furnace fire), `scene_hall.webp` (the Main Hall raised).
   Until they exist, `art.scene()` falls back to a backdrop.
7. **League crests**: 5 small painted emblems.

---

## 7. Open questions: decided

The owner approved every recommended default (2026-11-27).

1. **Builders keep working while an event waits for your answer: yes, builders only, at the away
   rate.** Building can only help, and it stops "I left a choice open and nothing got built" from
   becoming the new churn point. Everything else still holds.
2. **A war party never loses people to death: wounds only, on every storyteller.** Deaths stay
   with defence, plague and tribulation, where the storyteller already rules on them.
3. **Tapping a tray gives a small, once-a-day, ledgered crew mood thought (+3) and nothing
   else.** No extra resources, so a player who never taps loses nothing.
4. **Room art: 11 tiles first** (one look per type, level shown by the plaque), the second tier
   later.
5. **A season is one sim year (48 sim days)**, so a season can never run out while the app is
   closed.

---

## Sources

1. Deconstructor of Fun, "Why Fallout Shelter Popped and Dropped" (2015). https://www.deconstructoroffun.com/blog//2015/07/why-fallout-shelter-popped-and-dropped.html
2. D. Draganov, "Clash of Clans vs Boom Beach, Part 2: The Habit", Game Developer. https://www.gamedeveloper.com/business/clash-of-clans-vs-boom-beach-part-2-the-habit
3. "Retention and competition cycles in Boom Beach" (2014; seen as a search summary only). https://vernon99.github.io/blog/2014/07/08/boom-beach
4. Supercell, "Building upgrade and hero regeneration times reworked" (2018). https://supercell.com/en/games/clashofclans/blog/news/building-upgrade-hero-regeneration-times-reworked ; see also "Cost and time reductions, December 2023": https://supercell.com/en/games/clashofclans/blog/news/cost-and-time-reductions-december-2023/
5. J. Jordan, "I've played Clash of Clans more than any other game, but now it's time to log off", PocketGamer.biz. https://www.pocketgamer.biz/opinion-ive-played-clash-of-clans-more-than-any-other-game-but-now-its-time-to-log-off/
6. PocketGamer.biz, "Supercell: looking back on 10 years of Hay Day, part one" (seen as a search summary only). https://www.pocketgamer.biz/supercell-looking-back-10-years-of-hay-day-part-one
7. A. Pecorella, "Idle Chatter", GDC 2016 (slides; seen as a search summary only). https://pt.slideshare.net/AnthonyPecorella/idle-chatter-gdc-2016-59734260
8. PocketGamer.biz, "Deconstructing a $100m idle game: what 5 years of Gold & Goblins reveals about live ops and retention". https://www.pocketgamer.biz/deconstructing-a-100m-idle-game-what-5-years-of-gold-and-goblins-reveals-about-live-ops-and-retention/
9. Nielsen, "Long-term mobile game success beyond awareness and adoption" (2016; seen as a search summary only). https://www.nielsen.com/insights/2016/long-term-mobile-game-success-beyond-awareness-and-adoption
10. Fallout Shelter rush and merge mechanics, from community sources: the Fallout Shelter FAQ, section 6 (https://github.com/therabidsquirel/The-Fallout-Shelter-FAQ/wiki/Section-6:-Incidents), Fallout Shelter rooms (https://fallout.wiki/wiki/Fallout_Shelter_rooms) and Steam discussions (https://steamcommunity.com/app/588430/discussions/0/135513549094082201). These are anecdotal; no official formula was found.
11. Game Developer, "Clash of Clans vs Boom Beach, Part 1: The Hook" (on all-or-nothing HQ battles; seen as a search summary only). https://www.gamedeveloper.com/business/clash-of-clans-vs-boom-beach-part-1-the-hook
12. Supercell, "Get ready for the Ranked update" (shields, the defence log and Revenge; seen as a search summary only). https://supercell.com/en/games/clashofclans/blog/release-notes/get-ready-for-ranked-update
13. Wikipedia, "Hay Day" (neighbourhoods and derbies, 2014). https://en.wikipedia.org/wiki/Hay_Day
14. In-repo research: `docs/research/notes/competitors_cultivation_games.md` (genre complaints: grind, opacity, micromanagement, wait timers) and `docs/research/notes/ui_psychology.md` (goal gradient, overjustification, the home-map audit that counted 6 gold "↑" badges).

Gaps: no source measures how much the Clash timer cuts changed retention; Supercell gives only
the rationale [4]. Fallout Shelter's rush formula is not published. No official statement was
found on why Hay Day has no energy meter. Sources [3], [6], [7], [9], [11] and [12] were seen
only as search-engine summaries, not opened; quotes credited to them are from those summaries.
