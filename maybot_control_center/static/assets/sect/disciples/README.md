# Disciple character sprites (optional, authored)

Drop PNG sprites here to replace the procedural characters on the Realm Map.
Filenames are `<key>_<state>.png`, where `<key>` is the disciple's lowercased
name (e.g. `atlas`, `nova`) and `<state>` is one of:

  idle  walk  work  meditate  celebrate

Examples:
  atlas_idle.png   nova_work.png   forge_walk.png   sage_meditate.png

## Animation
- A single frame per state is fine (static pose).
- For an animated sheet, suffix the name with the frame count laid out
  horizontally: `<key>_<state>_<N>f.png`, e.g. `nova_walk_4f.png` (4 frames).

## Specs
- Transparent PNG, character facing RIGHT (the map mirrors it for walking left).
- Anchored at the feet (bottom-centre of the image meets the floor).
- Any size; the map scales to ~50px tall. Keep silhouettes bold and readable.

Missing files fall back to the procedural character automatically; the map
loads only the sprites this endpoint reports (`GET /api/sect/disciples`).
