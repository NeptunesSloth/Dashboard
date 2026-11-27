# Art pipeline: repainting the art with ComfyUI on the owner's PC

A brief for a Claude Code session running **on the owner's Windows PC**, next to
ComfyUI Desktop. The cloud session that wrote this cannot reach the PC, so this
session does the generating; the owner chooses between variants.

## The machine

- Windows, **NVIDIA RTX 4060 Ti with 8 GB** of video memory.
- ComfyUI Desktop is installed and the **Z-Image-Turbo** template works (tested:
  a 1152x768 picture came out fine). Its models are already downloaded:
  `diffusion_models/z_image_turbo_bf16.safetensors`,
  `text_encoders/qwen_3_4b.safetensors`, `vae/ae.safetensors`.
  The bf16 model is larger than 8 GB, so ComfyUI offloads; the first run is slow.
  Do not switch to the Qwen Image Edit models: they are too big for this card.
- Work folder: `C:\Users\littl\OneDrive\Documents\SectArt` (put clones, scripts,
  variants and contact sheets here).

## Getting set up

1. Clone the repo into the work folder and check out branch
   `claude/brave-volta-6tsola` (`git clone`, then `git checkout`). The current art
   is in `sect_academy/static/art/`.
2. ComfyUI must be open. Find its local API: try `GET http://127.0.0.1:8000/system_stats`
   (Desktop's default), else port 8188. Everything stays on this machine.
3. Get the exact workflow in **API format**: ask the owner to open the
   Z-Image-Turbo template in ComfyUI and use **Workflow → Export (API)**, saving it as
   `SectArt\zimage_api.json`. Use it as the base (it names the real nodes and
   settings). If it is a subgraph, the export is already flattened.
4. Write one small Python script that, for each job: uploads the reference picture
   (`POST /upload/image`), edits the API JSON (prompt text, size, seed, and for
   repaints swaps the empty-latent input for `LoadImage` → `VAEEncode` using the
   workflow's own VAE, with the KSampler's `denoise` set as below), queues it
   (`POST /prompt`), waits on `/history/<id>`, and downloads the result (`/view`).
   Run jobs one at a time (8 GB card).

## The look

Keep the **lantern-night painterly pixel-art** of the current set (look at it
first): warm gold paper lanterns, deep indigo and blue shadows, red lacquered
pillars, grey stone floors, high three-quarter view, dense small detail. The owner
asked for it **richer and more detailed**, same palette. Never bright, flat or
vector (the owner rejected that look).

Start every prompt with:

> detailed painterly pixel-art, xianxia cultivation sect, night, warm gold paper
> lanterns, deep indigo shadows, red lacquered pillars, rich fine detail,

and end with:

> no text, no writing, no characters, no letters, no signs, no watermark

The first test drew fake Chinese characters on scrolls and signs; ask for blank
scrolls or ink landscape paintings instead. Z-Image-Turbo uses cfg 1 and ignores a
negative prompt, so keep the "no text" words in the positive prompt.

## The jobs

Make **3 variants** of each (different seeds), save them as
`variants/<name>_<n>.png`, and build one contact sheet per batch so the owner can
pick (show it to them; ask which number to keep, or to re-roll).

### Repaints (use the current picture as the reference)

`denoise` is how much changes: lower keeps the layout, higher repaints more.

| File | Size (final) | Generate at | denoise | Subject (what the current picture shows) |
|---|---|---|---|---|
| `hq` | 1620x971 | 1616x976 | 0.40-0.45 | cut-away of the sect: five lantern-lit floors of rooms, side by side |
| `bg_hall` | 1152x768 | 1152x768 | 0.55 | open hall of pillars looking out on misty peaks, a glowing blue array circle on the floor |
| `bg_leader` | 1152x768 | 1152x768 | 0.55 | throne hall: dragon banners, a dais and throne, dark blue carpet |
| `bg_map` | 1152x768 | 1152x768 | 0.55 | daytime mountain peaks above clouds, temples and waterfalls, rope bridges, a violet crystal |
| `bg_mission` | 1152x768 | 1152x768 | 0.55 | mission hall: map table on a red carpet, notice boards, weapon racks, sect banners |
| `bg_pill` | 1152x768 | 1152x768 | 0.55 | alchemy room: bronze cauldron with steam, herb shelves, potion bottles |
| `bg_seclusion` | 1152x768 | 1152x768 | 0.55 | cave of blue crystals, a waterfall, a round stone meditation platform in water |
| `bg_technique` | 1152x768 | 1152x768 | 0.55 | technique hall: training mat, scroll shelves, training dummies (keep the mat and scrolls blank) |
| `bg_treasure` | 1152x768 | 1152x768 | 0.55 | treasure vault: jade statues, a glowing sword, chests of jewels, red carpet |
| `p_leader` | 192x192 | 1024x1024 | 0.6 | chibi portrait bust, young sect master with a gold crown ornament, holding a gold staff |
| `p_elder` | 192x192 | 1024x1024 | 0.6 | chibi portrait bust, kind old elder with white hair and long white beard |
| `p_disciple`, `p_analyst`, `p_architect`, `p_engineer`, `p_researcher`, `p_trader` | 192x192 | 1024x1024 | 0.65 | chibi portrait busts of disciples on a dark background with gold sparkles |

For portraits, upscale the 192px original to 1024 before using it as the
reference. The six disciple faces are nearly identical today; make them clearly
different people (men and women, different ages, hair, robes and colours) while
keeping the chibi style, face centred, head and shoulders, dark background.

**`hq` must keep its layout.** The game places clickable rooms over it at fixed
percentages (`SITES` and `VAULT` in `sect_academy/static/art.js`). After
generating, draw those rectangles over each variant (scale the percentages to the
image size) and show the owner; reject any variant where a room has moved out of
its box. Lower the denoise if they drift.

**Do `hq` room by room.** A whole-picture repaint (tried once, reverted) kept the
boxes but lost what each room is: Buddha shrines in the storehouse and dormitory,
a cauldron in training, the market no longer a market. Instead crop each box from
the original, repaint each crop on its own at denoise about 0.5 with a
room-specific prompt, and paste it back into the same box, keeping the original
between the boxes (floors, beams):

| Box | Prompt subject |
|---|---|
| dormitory | disciples' sleeping quarters: rows of sleeping mats and folded bedding, small chests |
| main_hall | sect main hall: a golden seated patriarch statue on a dais, incense |
| fields | spirit rice terraces and a blossoming spirit tree under the eaves |
| market | trade post: market stalls with goods, hanging banners, merchants' counters |
| storehouse | storehouse: sacks of rice, crates, barrels and stacked lumber |
| library | scripture library: tall shelves of scrolls, a glowing blue array on the reading table |
| ward | healing ward: beds with patients, herb cabinets, a physician's table |
| alchemy | alchemy room: bronze pill furnace, shelves of bottles and herbs |
| training | training yard: wooden dummies, weapon racks, a sparring circle |
| vault | treasure vault: round vault door, jade guardian statues, treasure chests |
| spirit_vein | spirit vein: a great blue spirit crystal over a glowing pool, carved steps |
| meditation | meditation hall: round moon window, meditation cushions, violet qi flames |

Show the owner 2 versions of the whole assembled painting, with the boxes drawn
over them, before pushing.

### New result scenes (no reference; text to image)

The game shows these on result cards; until they exist it borrows a backdrop.
Generate at 1152x768.

| File | Subject |
|---|---|
| `scene_raid` | the sect's outer gate at night under attack by a beast tide: huge shadowy spirit wolves and a horned boar with glowing eyes surging up the stone steps, disciples in robes on the wall with swords and glowing talismans, a blue formation barrier cracking |
| `scene_tournament` | the Hundred Sects Tournament: a great stone arena on a mountain, two cultivators clashing in the centre in bursts of qi, crowds of sects under coloured banners, lanterns |
| `scene_festival` | a lantern festival in the sect courtyard: hundreds of floating paper lanterns, disciples celebrating, food stalls, fireworks over the peaks |
| `scene_funeral` | a quiet funeral at dusk: a white-draped bier, incense smoke, mourning disciples in white, white paper lanterns, falling petals |
| `scene_tribulation` | a heavenly tribulation: a lone cultivator on a peak beneath a vortex of black clouds, purple-white lightning striking down |
| `scene_realm` | entering a secret realm: a glowing rift in a cliff opening onto an ancient ruined palace with floating islands and strange plants |
| `scene_breakthrough` | a cultivator in seclusion breaking through: seated cross-legged in a cave, a pillar of golden qi rising, the air rippling |

## Delivering

For each chosen picture: crop/resize to the final size with Pillow
(`ImageOps.fit(img, size, Image.LANCZOS)`) and save as WebP, quality about 82
(backdrops should land around 150-250 KB, portraits 10-20 KB), straight into
`sect_academy/static/art/` with the exact filename above. Keep the PNG originals
in the work folder, not in the repo.

Then commit to `claude/brave-volta-6tsola` ("Art: repaint <names>") and push. If
Python and the requirements are installed, run `python -m pytest -q` first. Commit
in batches (backdrops, portraits, hq, scenes) so a bad batch is easy to revert.
The cloud session will pull, check sizes and the room layout, and run the
offline smoke test.

## Round 2: more faces and scenes for the new threats

### Extra disciple faces

Any `sect_academy/static/art/p_<name>.webp` beyond the six originals is used
automatically (lower-case letters, digits and `_` only; not `leader` or
`elder`). Make **10**, chibi busts in the same style as the repainted
portraits (1024x1024 from a portrait reference at denoise ~0.7, final 192x192
WebP), each clearly a different person, with a prop for flavour:

| File | Who |
|---|---|
| `p_swordswoman` | young woman, high ponytail, sword over the shoulder |
| `p_monk` | shaven-headed young monk, prayer beads |
| `p_herbalist` | older woman, grey bun, basket of herbs |
| `p_scholar` | thin young man, scroll and brush, ink-stained fingers |
| `p_hunter` | rugged young man, fur collar, bow |
| `p_noble` | haughty young noblewoman, jade hairpin, folding fan |
| `p_farmer` | sun-tanned boy, straw hat, rice sheaf |
| `p_twin` | cheerful girl with two short braids, spinning top |
| `p_veteran` | middle-aged man, scar across the brow, spear |
| `p_mystic` | pale young woman, white hair, glowing talisman |

Existing disciples may get a different face once these land (faces are picked
from a hash of the disciple), which is fine.

### Scenes for the new events

Same rules as the first scenes (1152x768, a backdrop as style reference at
denoise ~0.85, no text, trim the corner stamp):

| File | Subject |
|---|---|
| `scene_sickness` | a plague ward at night: disciples on sickbeds, a physician with a lantern, herb smoke, pale green light |
| `scene_blight` | rice terraces withered grey and black under a sickly moon, a disciple kneeling in dead stalks |
| `scene_infiltrator` | a masked figure in black robes slipping through the sect at night, a dagger glinting, a disciple turning to look |
| `scene_theft` | raiders fleeing over the wall with sacks of rice and spirit stones, an open storehouse door, lanterns overturned |
| `scene_festival_spring` | Lantern Festival: paper lanterns released over the peaks, disciples guessing riddles at stalls |
| `scene_festival_moon` | Mid-Autumn: a huge full moon, mooncakes and tea on a terrace, disciples admiring the moon |
| `scene_festival_ghost` | Ghost Festival: river lanterns floating on dark water, offerings, incense, a gentle eerie mist |
| `scene_festival_winter` | Winter solstice: snow on the eaves, disciples sharing dumplings around a brazier |

The game picks these up once the matching event kinds exist (the cloud session
wires them); until then they are simply unused.

### Read tab backdrop

| File | Size | Subject |
|---|---|---|
| `bg_library` | 1152x768 | a scripture pavilion at night: tall shelves of scrolls and bound books, a low reading desk with an open book and a single lantern, a window onto misty peaks; calm, quiet, plenty of dark empty space in the centre for text |

Use `bg_mission` as the style reference at denoise ~0.85. The cloud session wires
it into the Read shelf once the file exists.

## Round 3: picture lessons

The language courses now have **picture lessons**: the learner drags words onto
numbered pins on a painting, taps the pin a word names, or types the word for a lit
pin. Ten paintings serve all five languages (the same picture and pin positions for
Spanish, French, Mandarin, Japanese and Korean). Until a painting exists its lesson
is held back and shown as "Picture coming soon", so each one can land on its own.

### What every picture needs

- **File**: `sect_academy/static/art/pic_<id>.webp`, **1200x900** (4:3). Generate at
  1216x912 (or the nearest size the model likes, 4:3) and fit to 1200x900.
- **Readable at phone size.** The picture is shown about 360 px wide on a phone.
  Every labelled thing must be **large, clearly visible and separated** from its
  neighbours (no two labelled things touching), drawn plainly from the front or
  a gentle three-quarter view, with nothing overlapping it.
- **Clean and uncluttered**: a plain, dark, softly lit background (deep indigo,
  a faint lantern glow), few extra props. Leave a little empty space round each
  labelled thing so a numbered pin and its label can sit on it.
- **No text of any kind**: no labels, letters, numbers, arrows, lines, signs, or
  writing on scrolls, boards, books or shop fronts (the app draws the pins and
  labels itself). The blackboard is blank or holds a simple drawing.
- **The same look** as the rest of `static/art`: lantern-night painterly
  pixel-art, warm gold lanterns, deep indigo shadows, rich fine detail. Not
  bright, flat or vector. Modern everyday objects (a fridge, a bus stop, a
  traffic light) are fine: draw them in the same painterly style, softly lit at
  night, as if in a xianxia town at dusk.

Start each prompt with the usual opening line, then the subject from the table,
then: *clean uncluttered composition, plain dark background, every object large
and clearly separated, centred, educational picture-dictionary illustration*, and
end with the usual *no text, no writing, no letters, no signs, no watermark*. Make
3 variants each and a contact sheet, as before.

### The ten pictures

| File | Subject and composition (the pins assume this layout) |
|---|---|
| `pic_body` | **A cultivator's anatomy chart**: an old unrolled paper scroll on a dark table, showing one young cultivator twice, standing, barefoot, in plain short trousers and bare-chested: on the left from the **front** (centred about a third of the way across), on the right from the **back** (about two thirds across). Arms held a little away from the sides, fingers slightly spread, feet a little apart. Head at the top of the scroll, feet near the bottom; the figures fill the height. |
| `pic_skeleton` | **The same anatomy scroll, the skeleton**: one human skeleton, front view, standing, centred, arms a little away from the sides, filling the height. Clear, friendly, not scary (no gore, no horror lighting); the skull, collarbones, breastbone, ribs, spine below the ribs, pelvis, thighbones, kneecaps and shinbones clearly drawn. |
| `pic_face` | **A close front portrait** of a young cultivator, the head filling the frame from the top of the hair (tied in a topknot) to the chin, ears visible, both eyes and eyebrows clear, mouth open wide as if saying "aah" so the upper teeth and the tongue show. Plain dark background. |
| `pic_house` | **A cut-away of a two-storey house**, the front wall removed like a doll's house, centred-left (about 15-75% across). Pitched roof with a chimney on the right of the roof. Upstairs: a **bedroom** on the left (a bed), a **window** in the middle wall, a **bathroom** on the right (a bathtub). Downstairs: a **living room** on the left (a sofa), the **stairs** rising in the middle, the front **door** at the bottom middle, a **kitchen** on the right (a stove and counter). A small **garden** with flowers and a tree outside on the right. |
| `pic_kitchen` | **A kitchen from the front**: along the back wall a tall **fridge** on the far left, a **stove** with a pot, a **sink** under a small window. In the front half, a wooden **table** laid for one: a white **plate** in the middle, a **fork** to its left, a **knife** to its right, a **spoon** lying across the top of the plate, a **cup** further right; a **chair** at the table's left end. The cutlery large enough to see. |
| `pic_clothes` | **Two people standing side by side**, full length, facing us, dressed for a cold evening. Left (about 30% across): a **hat**, a **scarf**, an open **jacket** over a **shirt**, a **belt**, long **trousers**, **shoes**. Right (about 68% across): **gloves** on hands held a little out, a knee-length **skirt**, long **socks** visible above the shoes. Plain dark background. |
| `pic_town` | **A town street at lantern-lit dusk**, seen from a little above. Along the back, five buildings, each obvious **without any writing**: a **bank** (stone columns, a big gold coin emblem), a **hospital** (a red cross symbol), a **school** (a bell tower, a small playground), a **station** (a train at a platform under a canopy), a **shop** (an awning, goods in the window). On the left a **restaurant** (tables outside, steaming bowls); on the right a **park** (trees, a bench, a pond). In front, a road with a striped **crosswalk** in the middle, a **traffic light** on the left of it, a **bus stop** shelter with a waiting bus on the right. |
| `pic_classroom` | **A classroom seen from the back**: on the far wall a large blank **blackboard**, a round wall **clock** up on the right, the **teacher** standing beside the board on the left, a tall **window** on the right wall. In front, a **student** sitting at a desk (right of centre), and an empty **desk** in the front left holding an open **book**, a **pen** and a **pencil** laid apart; a school **bag** on the floor at the far left. |
| `pic_meal` | **A long table of food seen from above** at a slight angle, ten dishes in three loose rows with space between: top row a loaf of **bread**, a bowl of white **rice**, a whole cooked **fish** on a plate, a plate of sliced roast **meat**; middle row two boiled **eggs** in a dish, a red **apple**, a basket of green **vegetables**, a bowl of **soup**; bottom row a glass jug of **water** (left of centre) and a teapot with a cup of **tea** (right of centre). |
| `pic_sky` | **One wide landscape whose sky changes from left to right**: on the left a bright **sun** and a white **cloud** over green hills with a **rainbow**; in the middle a dark storm cloud with falling **rain**, a bolt of **lightning**, and trees bent by the **wind** with leaves blowing; on the right a night sky with **stars** and a crescent **moon** over snowy pines, **snow** falling. Painterly, soft transitions; keep each part clear. |

### After painting: placing the pins

The pin positions are **best guesses for the compositions above**, in
`sect_academy/packs/pictures/<id>.yaml` (`x`, `y` in percent of the picture from
the top-left). Do not try to make the painting fit the pins exactly; paint the
best picture, deliver it, and the **cloud session sets the pin coordinates by
looking at the image**. To check them:

```bash
python scripts/pin_preview.py body              # pin_preview_body.png: the painting, a 10% grid and the pins
python scripts/pin_preview.py body --lang ja    # labelled with a course's words
python scripts/pin_preview.py body --html pins.html   # drag the pins; copy the printed pins: block back
python scripts/pin_preview.py --all             # every picture
```

Pin ids never change (they are the keys of the learner's progress); only `x` and
`y` move. Commit each delivered painting as "Art: picture <id>"; the lesson opens
on the next start of the app.
