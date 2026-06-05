# Disciple character sprites (authored)

Character art for the Realm Map disciples. Disciple names are dynamic, so art is
keyed by **archetype**, not name. Filenames are `<key>_<state>.png` where
`<key>` is one of the eight archetypes:

  leader  elder  researcher  analyst  engineer  architect  trader  disciple

and `<state>` is one of:

  idle  walk  work  meditate  celebrate

Examples:
  leader_idle.png   researcher_work.png   trader_walk.png   elder_meditate.png

The map resolves each disciple to a sprite in this order:
  1. `<name>_<state>` — optional per-name override (e.g. `atlas_walk`)
  2. `<role>_<state>` — the archetype art (most disciples use this)
  3. `disciple_<state>` — generic fallback
  4. the same chain on `_idle`, then the procedural character.

## Animation
- A single frame per state is fine (static pose).
- For an animated sheet, suffix the name with the frame count laid out
  horizontally: `<key>_<state>_<N>f.png`, e.g. `trader_walk_6f.png` (6 frames).
- The engine divides the strip width by `<N>` and cycles the frames, so all
  frames must be evenly spaced and the same width.

## Specs
- Transparent PNG, character facing RIGHT (the map mirrors it for walking left).
- Anchored at the feet (bottom-centre of the image meets the floor).
- Any size; the map scales to ~50px tall. Keep silhouettes bold and readable.

## Regenerating from a contact sheet
The bundled art was sliced from a single 8x5 contact sheet with
`tools/pack_disciple_sheets.py` (rows = the 8 archetypes, columns = the 5
states at 4/6/4/2/4 frames). Re-run it to replace the art:

  python3 tools/pack_disciple_sheets.py path/to/sheet.png

Missing files fall back to the procedural character automatically; the map
loads only the sprites this endpoint reports (`GET /api/sect/disciples`).
