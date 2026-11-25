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
