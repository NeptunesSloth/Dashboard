# UI inspiration notes — gamified learning apps + cozy idle games

Research date: 2026-11-24. Purpose: input for redesigning Sect Academy ("study to raise a
cultivation sect"). Web research only.

**How to read the evidence tags.** Every claim carries one:

- **[S]** = read in a source fetched this session (link given). Mostly first-party posts or
  search-result summaries of them.
- **[S3]** = sourced, but third-party / reverse-engineered / vendor marketing. Approximate.
- **[K]** = my recollection of the shipped product from general knowledge. **Not verified this
  session** — check against the live app or a screenshot library (Mobbin, screensdesign.com)
  before treating as fact.
- **[I]** = my inference / recommendation.

**Coverage gaps (searches returned nothing usable):** no design teardown found for Neko Atsume,
Habitica, Forest, Pocket Camp, Monument Valley, Kahoot, Khan Academy Kids, Elevate, Mochi, or
xianxia mobile-game UI. Those sections are almost entirely [K]. No published px value for
Duolingo's button lip or any of its motion timings was found. No hard retention number tied to a
purely *visual* change was found in a primary source.

---

## 1. Duolingo (2022–2026)

### Home: the path
- Nov 2022 the skill "tree" became a single vertical **path**: "a swirl of pebble-shaped
  circles moving down the screen"; future levels gray and blank; completed levels turn gold;
  tapping a circle opens a popup naming the lesson topic. [S] https://blog.duolingo.com/new-duolingo-home-screen-design/
- Stated reason: learners were unsure they were using the app "the 'correct' or 'best' way",
  so give "a clear path to follow". One circle = one old crown level. [S] (same)
- Units have a header naming the concept in plain language ("get directions", not "City 3");
  a guidebook button sits top-right of the unit header; stories are pebbles with a book icon
  on the path, not a separate tab; a floating arrow bottom-right jumps back to your current
  position. [S] (same)
- Review is interleaved into the path ("Practice is also forward progress"). [S] (same)
- No outcome metrics published in that post. Press framed it as the "biggest ever redesign",
  meant to be less stressful. [S] https://uk.finance.yahoo.com/news/duolingo-language-learning-app-undergoes-135344395.html
- [K] The nodes snake left-right in a sine-like offset; each is a thick disc with a darker
  bottom edge (same depth language as buttons); the current node has a progress ring and a
  bobbing "START" tooltip; a character illustration stands beside the path every few nodes;
  each unit has its own header colour, so scrolling the course shifts hue.

### Tabs / secondary screens (2025 "core tabs" refresh)
- Problem stated: "Headers varied in size, typography lacked hierarchy, and spacing felt
  inconsistent." Four directions explored — Punchy (solid vivid headers), Soft (gradients,
  muted), Modular (everything in rounded cards), Flat (white space, no containers). [S] https://blog.duolingo.com/core-tabs-redesign
- Shipped: left-aligned titles in the same size/position in a bold high-contrast header bar;
  a *minimal* set of text styles; whitespace separates components "instead of forcing
  containers around them"; cards flattened; header illustrations removed where they "took up
  space without conveying useful information". [S] (same)
- Result claimed: "higher engagement across tabs while maintaining our core learning
  metrics" — no figures. [S] (same)
- Takeaway: even the most playful app in the category moved *away* from card-in-card
  borders and decorative header art on utility screens. [I]

### Colour, type, shape (reverse-engineered tokens — approximate)
- Colours: green #58cc02 (pressed/lip #58a700), blue #1cb0f6, red #ff4b4b, orange #ff9600,
  yellow #ffc800, purple #ce82ff; text grays #3c3c3c / #4b4b4b / #777777 / #afafaf; hairline
  #e5e5e5; canvas pure white. Colours carry animal names (macaw, cardinal, fox, bee, eel,
  wolf, hare). [S3] https://www.shadcn.io/design/duolingo/raw
- Type: Feather Bold for display (64/48px, 700); DIN Round / DIN Next Rounded for UI — body
  17px/500, small text 15 and 13px at **700**, button labels 15px/700 **uppercase with 0.8px
  tracking**. Sources disagree on the exact UI face name. [S3] (same); https://fontsinuse.com/uses/59497/duolingo-app
- Shape: radii 8 / 12 / 16 / full; button radius 16px; button height 50px, padding 13×16;
  inputs 48px; secondary buttons and inputs have a **2px** solid border (#e5e5e5/#afafaf);
  cards carry no drop shadow. [S3] (shadcn link above)
- The "3D" button: a flat, un-blurred darker lip under the face, described as "3–4px". No
  blur, no rgba shadow. Exact offset unpublished. [S3] (same)
- [K] On press the face translates down by the lip height and the lip disappears, so the
  button visibly "goes in"; disabled buttons are flat gray with no lip. Widely cloned in CSS
  as `box-shadow: 0 4px 0 <darker>` + `:active { transform: translateY(4px); box-shadow:none }`.
- Spacing scale 8/10/12/16/24/32/48. [S3] (same)

### Exercise screen
- [K] Top row: close (X) at left, a thick rounded progress bar filling most of the width
  (with a lighter highlight stripe inside the fill), hearts at right. Middle: prompt in bold,
  optionally a character with a speech bubble containing the sentence. Answer area: option
  cards with 2px border + lip; selection turns the border and fill light blue. Bottom: one
  full-width CHECK button, gray until an answer exists.
- Feedback: screenshot libraries show a correct-answer confirmation with an "Amazing"-type
  banner and a Continue button. [S] https://screensdesign.com/apps/duolingo-language-lessons/
- [K] The banner is a sheet that slides up from the bottom and replaces the check area:
  light green with dark green text + check icon ("Nice!"), or light red with dark red text,
  the correct answer written out, and a red CONTINUE. Colour + icon + words + sound all
  change, so it is not colour-only. Short streak-of-correct interstitials ("5 in a row!")
  interrupt with a character.
- Quitting mid-lesson triggers a confirmation dialog. [S] https://medium.com/usabilitygeek/ux-case-study-duolingo-ade986ec7450

### Characters
- Ten "World Characters" lip-sync the sentence; between lines they idle (head nods, blinks,
  eyebrow moves); when the challenge ends "the character moves to a final state that reacts
  to whether the answer was right or wrong". 20+ mouth shapes per character. Built in Rive
  with state machines; chosen over video for file size across iOS/Android/web. [S] https://blog.duolingo.com/world-character-visemes
- Stated goal: characters as "lively, engaging study buddies". No metric published. [S] (same)
- Animation is driven by events (isCorrect / isWrong / isSpeaking inputs), not timelines. [S3] https://dev.to/uianimation/how-duolingo-uses-rive-for-their-character-animation-and-how-you-can-build-a-similar-rive-mascot-5d19

### Streak + celebration
- Streak-extended screen: character appears with the day count, "spins in the air and bursts
  into a orange flame". [S] https://blog.duolingo.com/how-duolingo-streak-builds-habit
- Milestones (2022): old art (owl holding number balloons) judged "cute, but not quite
  celebratory enough, energy-wise". New concept is a video-game power-up: the mascot
  *physically transforms* (phoenix). Timing treated as "as important ... as the design
  itself"; several rough passes. Square share card. Result: "more people keeping streaks
  alive" — no number. [S] https://blog.duolingo.com/streak-milestone-design-animation
- A third-party analysis credits the phoenix animation with +1.7% day-7 retention;
  unverified against a primary source. [S3] https://duolingo.deconstructoroffun.com/mechanics/streaks
- Measured streak results (company statements via Mobbin): "Commit to my goal" label
  instead of "Continue" → 10,000 more daily openers; a one-lesson minimum → 40%+ more users
  holding a 7-day streak; two freezes instead of one → 200,000 more daily returners. [S] https://mobbin.com/blog/streaks-are-about-losing-a-study-of-859-streak-designs
- Lesson complete: large mascot illustration and bold yellow text on a bright green
  background. [S] https://screensdesign.com/apps/duolingo-language-lessons/
- [K] Followed by 2–3 stat tiles (XP, accuracy %, time) that count up one after another,
  then a sequence of single-purpose full screens (streak, quest progress, league), one
  button each.
- [K] Top status bar on home: course flag, flame + streak number (orange), gem + count
  (blue), heart + count (red) — icon and number share a colour; each opens a popover.

---

## 2. Other learning apps

- **Brilliant.** Colour-coded learning paths (hue per topic, several node types, connecting
  lines) and an animated day-streak counter whose animation is timed to the number ticking
  up; rebuilt in Rive during a 2023 "game mechanics" redesign; one animation file across
  web/iOS/Android. [S3, vendor case study] https://rive.app/blog/how-brilliant-org-motivates-learners-with-rive-animations
  Unofficial summary of the look: custom "Brilliant Sans", illustrated geometry as hero art.
  [S3] https://www.webdesignhot.com/design.md/brilliant-org/
  [K] Distinguisher: the *content itself* is the illustration — manipulable diagrams — on a
  quiet white canvas with thin outlines; chunky lipped buttons similar to Duolingo's but
  near-black; less mascot, more diagram.
- **Drops.** Praised for illustration; colour denotes category; haptics and
  micro-interactions lead the user. [S] https://www.designrush.com/best-designs/apps/drops
  [K] Full-bleed saturated gradient backgrounds, one flat white pictogram per word, almost no
  text chrome, drag/swipe instead of buttons, a fixed 5-minute session ring.
- **Babbel.** Redesign aimed to let users "clearly see their learning path" and visualise
  progress. [S] https://www.babbel.com/en/magazine/course-overview-update — praised for
  minimalism. [S3] https://xd.adobe.com/ideas/principles/app-design/simple-intuitive-gamified-babbel-language-learning-great-ux-design
  [K] Orange accent on white, photography, adult/"serious" tone — the anti-Duolingo.
- **Memrise.** "Clean, simple and colorful". [S3] https://www.imore.com/apps/iphone-app-memrise-is-a-fresh-take-on-language-learning
  [K] Yellow brand colour on dark navy; native-speaker video clips are the hero content.
- **Kahoot** [K]: four answer tiles, each a fixed colour **and** a fixed shape (triangle,
  diamond, circle, square) — the textbook non-colour-only answer encoding; countdown bar;
  podium finale.
- **Khan Academy Kids** [K]: storybook-textured animal cast, very large touch targets,
  narration replaces text. **Elevate** [K]: flat geometric per-game colour worlds, radial
  score dials, typographic rather than character-led. **Mochi** [K]: near-chromeless
  markdown cards, monochrome + one accent, keyboard-first — appeal through calm, not juice.
- Pattern across the set: each owns **one** signature device (path / diagram / pictogram /
  video / shape-coded tiles) and keeps everything else quiet. [I]

---

## 3. Cozy idle / management / habit games

- **Cats & Soup.** Currency/progress in a simple bar at the top; a row of food icons along
  the bottom that you tap to sell what the cats made; a single hammer icon opens the craft
  menu (Facilities, Recipes, Gift Shop, Quests, Collection, Theme) with a minimal dropdown
  per category; soft palette; subtle tap animations; incremental progress indicators. [S] https://dev.to/jpdengler/exploring-the-charming-uiux-design-of-catssoup-3l9a
  Reviews praise hand-drawn art, smooth animation, satisfying sounds; complaints are about
  ad prompts. [S] https://apps.apple.com/us/app/id1581431235
  The developer has been *consolidating* home-screen icons and adding one-touch upgrade-all
  — clutter is the genre's standing problem. [S] https://nwzrise.oqupie.com/portals/1694/customer-news/3552
  [K] The scene is one tall scrollable painted forest; each facility is a small station
  with a cat visibly performing a looping task; produced goods pop out as floating icons;
  upgrade opens a bottom card with level, output/sec, cost, one button.
- **Finch.** Reviewers single out: not being "punished" or "forced", no leaderboard,
  animations, attachment to the pet. [S] https://apps.apple.com/app/1528595748
  A missed day shows a hammer "repair" icon rather than an empty gap; the bird grows as
  goals are met. [S] https://mobbin.com/blog/streaks-are-about-losing-a-study-of-859-streak-designs
  [K] Pastel flat-colour scenes, a round bird centred on the home screen, goals as a plain
  checklist beneath it, energy bar that fills to send the pet on an "adventure".
- **Cozy theory.** Project Horseshoe: cozy = **safety, abundance, softness**; play at your
  own pace, no timers; notifications were called out as breaking Pocket Camp's coziness.
  [S] https://medium.com/kitfox-games/designing-for-coziness-d33d2519a59e ; https://80.lv/articles/using-coziness-in-game-design
  Softer colours are typical. [S] https://GamaSutra.com/design/the-quest-for-cosy-a-deep-dive-into-cosy-gaming
- **Neko Atsume** [K]: one static yard, flat crayon-like fills, thick soft outlines, almost
  no HUD (one menu button); the reward is *finding who showed up* since last visit.
- **Pocket Camp** [K]: 3D diorama campsite centre-screen; cream rounded-rectangle panels
  with brown text (never black on white); villager portrait bubbles; crafting timers as
  small pills over furniture; leaf-shaped currency icons.
- **Habitica** [K]: pixel-art avatar + HP/XP/mana bars in a purple header above plain task
  lists; loved for identity, often criticised as dense. **Forest** [K]: one screen — a
  circular timer with a sprout growing in the centre on a flat green field; the forest grid
  is a calm isometric record of past sessions; a dead tree on failure is its one punitive
  note. **Monument Valley** [K]: per-level limited palette (2–3 analogous hues + one
  complementary accent), flat shading with soft gradient skies, generous empty space.
- **Xianxia / cultivation mobile UI** — sourced evidence is thin: store listings advertise
  "ink-wash art with golden accents" [S] https://store.steampowered.com/app/4618670 ; jade is
  commonly the premium currency [S] https://apps.apple.com/us/app/immortal-taoists-wuxia-game/id1475870720 ;
  ink-wash is the most-praised aspect of Tale of Immortal [S3] https://gamegeeker.com/games/tale-of-immortal-1468810/review?market=US
  [K] Conventions: home is a painted mountain vista with layered mist; sect buildings
  (main hall, alchemy furnace, library pavilion, spirit field, treasure vault) sit on
  terraces and are tapped directly, each with a name plaque; idle resources float above
  buildings as bubbles to tap; a meditating avatar with an aura whose colour tracks realm;
  a "breakthrough" button that glows when the bar is full; panels styled as scrolls or
  jade tablets with corner filigree; red seal stamps for claimed/complete; brush-serif
  titles with a plain sans for numbers; palette of ink black, rice-paper cream, jade,
  vermilion, gold. Common failure: a home screen ringed by dozens of red-dot event icons.

---

## 4. Evidence on what appeals

- **Curvature.** Bar & Neta (2006): people prefer curved over sharp-angled objects;
  proposed sharp contours signal threat. Later work: curves are liked in themselves, threat
  doesn't fully explain it; the effect is "reliable but not universal". [S] https://pmc.ncbi.nlm.nih.gov/articles/PMC4641621 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC4975689
  No study found that tests this on UI components specifically — rounding is well supported
  as a preference, not as an engagement lever. [I]
- **Juice.** Defined as abundant feedback relative to input. Evidence is mixed: Juul & Begy
  (2016) found null results; other small studies find particles + juicy text improve player
  experience without hurting performance; one warns that overloading amplified feedback
  can interfere with felt competence. [S] https://arxiv.org/pdf/2011.09201 ; https://en.wikipedia.org/wiki/Game_feel
  Read: juice makes it feel better, it does not make people learn or return more by itself. [I]
- **Streak/progress framing.** 859 streak designs surveyed: nearly all headline a day
  count; calendars, rings and growing companions are the three visual families. Cautions:
  fear/urgency, identity damage on a break, counter-chasing. One UCL study: missing a single
  day "did not materially affect the habit formation process". [S] https://mobbin.com/blog/streaks-are-about-losing-a-study-of-859-streak-designs
- **Review themes.** Loved: hand-drawn art, smooth animation, sound, attachment to a
  creature, absence of punishment and leaderboards. Hated: pushy ads/IAP, crashes, cluttered
  home screens. [S] App Store pages linked above.
- **Decorative art has a cost.** Duolingo removed header illustrations that carried no
  information and reported higher engagement. [S] https://blog.duolingo.com/core-tabs-redesign

### Accessibility cautions
- `prefers-reduced-motion`: swap movement for a crossfade/opacity change rather than
  removing feedback entirely. [S] https://web.dev/learn/accessibility/motion ; https://developer.mozilla.org/en-US/docs/Web/CSS/Media_Queries/Using_media_queries_for_accessibility
- WCAG criteria to design against [K — standard, not re-fetched; https://www.w3.org/TR/WCAG22/]:
  1.4.1 no colour-only meaning; 1.4.3 text contrast 4.5:1 (3:1 for large/bold ≥ ~24px or
  ~19px bold); 1.4.11 3:1 for control boundaries and icons; 2.2.2 anything moving >5s needs
  pause/stop; 2.3.1 no more than 3 flashes/sec; 2.3.3 interaction-triggered motion can be
  disabled; 2.5.8 targets ≥24×24 CSS px (44–48 recommended by platform guidelines).
- White label on Duolingo green #58cc02 computes to roughly **2.1:1** — below 4.5:1 and
  below the 3:1 large-text threshold. The candy look and AA contrast are in tension; do not
  copy white-on-bright-green/yellow/orange. [I — my calculation]
- Gold-on-cream and jade-on-mist (the xianxia palette) fail the same way; use gold as trim
  and fill, never as text colour on light surfaces. [I]

---

## 5. Transferable design rules

### Observed in a product
| Rule | Value | Source |
|---|---|---|
| Button radius | 16px | Duolingo [S3] |
| Button height / padding | 50px; 13×16px | Duolingo [S3] |
| Button lip | flat, 0 blur, ~3–4px, a darker shade of the face colour | Duolingo [S3] |
| Button label | 15px, weight 700, uppercase, +0.8px tracking | Duolingo [S3] |
| Outline weight on inputs/secondary | 2px, light gray | Duolingo [S3] |
| Radius scale | 8 / 12 / 16 / pill | Duolingo [S3] |
| Spacing scale | 8 / 12 / 16 / 24 / 32 / 48 | Duolingo [S3] |
| Type scale | 13 / 15 / 17 / 19 / 32 / 48 / 64; small sizes set at 700 | Duolingo [S3] |
| Two faces only | one characterful display face + one rounded UI sans | Duolingo [S3] |
| Colour roles | 1 brand + 5 accents, each bound to one meaning (streak=orange, gems=blue, hearts/wrong=red) | Duolingo [S3]/[K] |
| Cards | no drop shadows; separation by whitespace, not nested borders | Duolingo [S] |
| Path nodes | gray = locked, gold = done, tap → popup with topic | Duolingo [S] |
| "Return to current" floating button | bottom-right | Duolingo [S] |
| Unit labels | plain-language goal, not a code | Duolingo [S] |
| Character states | idle loop (blink/nod) + distinct right and wrong end states | Duolingo [S] |
| Milestones | the mascot transforms; share card | Duolingo [S] |
| Counter animation | synced to the number ticking up | Brilliant [S3] |
| Topic = hue | each course/path has its own colour | Brilliant [S3], Drops [S] |
| Home HUD | currencies in one top bar; one icon opens all building menus | Cats & Soup [S] |
| Missed day | "repair" affordance instead of a blank/broken marker | Finch [S] |
| Commitment wording | "Commit to my goal" beat "Continue" | Duolingo via Mobbin [S] |

### My inference (not observed; starting values to test)
- **Depth:** lip 4px on primary buttons, 2–3px on cards/chips/path nodes; press =
  `translateY(lip)` + lip removed, 80–100ms, no easing needed. One depth language everywhere
  (buttons, nodes, building plaques) is what makes the UI feel like one object set.
- **Motion budget:** taps/presses 80–120ms; state changes (select, banner slide) 180–250ms
  ease-out; celebratory entrances 350–500ms with slight overshoot
  (`cubic-bezier(.34,1.56,.64,1)`); count-ups 600–900ms; whole celebration skippable and
  under ~2.5s. Idle loops slow (3–6s period), small amplitude, at most 2–3 moving things on
  screen at once.
- **Colour count:** 1 primary, 1 "wrong" red, 1 "reward" gold, 1 secondary accent, plus
  neutrals — and a tinted off-white canvas (rice paper) rather than #fff to get the cozy
  register. Per-course hue as a single swappable token.
- **Contrast-safe candy:** keep faces saturated but put **dark** text on light/bright
  faces, or darken the face until white text reaches 4.5:1; let the lip, not the label,
  carry the vividness.
- **Feedback banner:** slide up from bottom over the action area; icon + word + colour +
  correct answer text; primary button moves into the banner so the thumb doesn't travel.
- **Exercise layout:** max content width ~600px centred on desktop, progress bar top,
  single full-width action bottom; one decision per screen.
- **Home (sect) screen:** one painted scene, 5–7 tappable buildings max, each with a
  looping micro-animation only when it is *doing* something; currencies in one top bar; one
  dominant "Begin today's cultivation" button with the lip; collect bubbles float and bob
  only when there's something to collect; no badges that aren't actionable.
- **Upgrade card:** bottom sheet with building art, current → next level, the effect in one
  line, cost, one button; on confirm the building does a squash-and-stretch pop and a seal
  stamp lands.
- **Celebration pattern:** (1) big number/character moment, (2) 2–3 stat tiles counting up
  in sequence, (3) what it did for the sect (qi flowing into a building), (4) one button.
  Reserve the transformation-grade animation for real milestones (realm breakthrough).
- **Theme dosage:** ink-wash and gold belong in the scene art, headers and milestone
  moments; exercise screens stay plain and high-contrast. Brush display face for titles
  only; rounded sans for everything read at speed; numerals always in the sans.
- **Cozy rule:** nothing visibly decays or shames on a missed day (matches the existing
  game invariant); show "the sect waited for you" states, not broken ones.
- **Reduced motion:** every animation has an opacity-only fallback; sound/haptics never the
  sole signal; right/wrong always has icon + text.

---

## 6. What NOT to copy, and how to differentiate

Not legal advice; general trade-dress hygiene. [I] throughout.

- **Mascots/characters:** no green owl, no lookalike cast, no phoenix-owl transformation.
  Build characters from the sect fiction (elder, disciples, spirit beast).
- **Exact palettes and colour names:** don't lift #58cc02 + #1cb0f6 + #ff4b4b + #ffc800 as a
  set, or the animal colour names. A jade/vermilion/gold/ink set is naturally distinct.
- **Fonts:** Feather Bold is proprietary; DIN Next Rounded is commercial (Monotype) [S3]
  https://www.designyourway.net/blog/duolingo-font/ . Use openly licensed faces, and avoid
  the specific "rounded geometric bold + uppercase tracked labels" pairing with a green CTA.
- **Names/terms/icons:** "Duo", "Super", "Legendary", "lingots", "Leagues" tier names, the
  specific flame glyph, heart system art, chest art. Use own vocabulary (qi, spirit stones,
  realms, trials).
- **Whole-screen composition:** a snaking path of lipped circles + green CTA + flame/gem/
  heart top bar *together* is the recognisable trade dress. Individual conventions (a path,
  a pressed-edge button, a streak count, a slide-up feedback banner) are genre-common.
- **Art assets from xianxia games / AI-traced screenshots:** commission or draw original.
- **Dark patterns to leave behind:** guilt-trip notifications, countdown-to-loss timers,
  hearts that block studying, paywalled streak repair, late-night urgency pushes [S] https://mobbin.com/blog/streaks-are-about-losing-a-study-of-859-streak-designs ;
  ad-prompt pressure (top complaint in idle-game reviews) [S].
- **How others differentiate on shared conventions:** one signature device each — Brilliant
  = manipulable diagrams and near-black buttons; Drops = gradient + pictogram + swipe;
  Babbel = orange/photography/adult tone; Finch = pastel pet + no punishment; Cats & Soup =
  painted scene + working animals. Sect Academy's device is the **sect scene that visibly
  grows from study** — make progress a place (mountain ascent, pavilions lighting up)
  rather than a pebble path.
