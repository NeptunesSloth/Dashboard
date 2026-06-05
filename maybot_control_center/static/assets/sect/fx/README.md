# Realm Map effect strips (optional, authored)

Drop effect sprite strips here to replace the procedural spectacles on the
Realm Map. Each file is a horizontal strip named `<name>_<N>f.png` where `<N>`
is the number of evenly-spaced frames laid out left-to-right. The engine
divides the strip width by `<N>` and plays the frames; effects are centered on
the disciple/event, with no character in frame.

The map looks for these names (all optional — missing ones fall back to the
existing procedural drawing, or simply nothing):

  fx_breakthrough_8f.png   expanding golden qi shockwave (breakthrough/milestone spectacle)
  fx_celebrate_6f.png      gold-spark + petal burst over a celebrating disciple
  fx_aura_4f.png           looping rising-qi aura under a meditating disciple
  fx_work_4f.png           small looping work spark (forge/alchemy/general work)
  fx_coin_4f.png           looping coin glint over Commerce / Treasury work
  fx_levelup_6f.png        rising pillar of light (reserved for milestone events)

## Specs
- Transparent PNG, true alpha. No background, text, or border.
- Square cells (e.g. 256x256), effect centered.
- One-shot effects (breakthrough/celebrate) play once over their lifetime;
  loop effects (aura/work/coin) should tile seamlessly across their frames.

Listed by `GET /api/sect/disciples` (the `fx` array).
