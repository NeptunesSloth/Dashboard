# Realm Map art pipeline

The Realm Map is an **authored illustrated world map with procedural simulation
overlays**. Drop in art and it is used automatically; anything absent falls back
to procedural rendering. Everything is resolved by `GET /api/sect/manifest`.

## 1. Scenery layers (full-screen, parallax)

Drop these PNGs in `static/assets/sect/`:

| File | Renders | Default parallax |
|------|---------|------------------|
| `background.png` | behind all terrain (distant mountains / sky) | 0.25 |
| `midground_clouds.png` | between background and terrain (cloud sea) | 0.55 |
| `foreground_fog.png` | above terrain, below UI (mist/atmosphere) | 1.1 |

They are scaled to cover the viewport and offset by the camera (parallax →
depth). When absent, the procedural sky / cloud sea / fog are used.

## 2. Per-hall landmark sprites

Drop authored hall art in `static/assets/sect/halls/<key>.png`. If present, the
hall is drawn as that **single landmark sprite** instead of assembled voxel
buildings ("landmark placement", not "building placement").

| District | hall key | landmark idea |
|----------|----------|---------------|
| Sect Hall (Sect Master Peak) | `sect_hall` | giant mountain palace |
| Azure Spirit Grounds | `cultivation_peak` | terraced cultivation grounds |
| Spirit Nexus Chamber | `spirit_nexus` | crystal formation cavern |
| Hall of Infinite Inquiry | `archive_hall` | cliffside archive |
| Heavenly Calculation Pavilion | `observatory_peak` | clifftop observatory |
| Forge of Creation | `forge_peak` | forge built into the rock |
| Hall of Heavenly Decrees | `mission_hall` | mission hall |
| Golden Prosperity / markets | `commerce_valley` | market terraces |
| Thousand Paths Gate | `mountain_gate` | giant mountain gate |

## 3. Prop / building sprites (voxel-baked fallbacks)

`static/assets/sect/<name>.png` overrides the baked voxel sprite
`static/assets/sect/baked/<name>.png` by filename. Names:
`grand_pagoda, pagoda, pavilion, lantern, tree, pine, cherry, crane, shrine,
stall, gate, crystal, fountain, observatory, forge, bell`.

## Iso spec (match so art lines up)

- 2:1 isometric, **6 voxels per tile**, tile half-size `40 x 20` px
  (`baked/manifest.json` → `tile`, `voxPerTile`).
- Ground anchor = where the art meets the terrace (foot centre).
- Transparent PNG with alpha.

## Optional metadata — `static/assets/sect/manifest.json`

```json
{
  "sprites":  { "grand_pagoda": { "anchorX": 256, "anchorY": 470, "w": 512, "h": 540, "footTiles": 3.3, "scale": 1.0, "z": 0 } },
  "halls":    { "sect_hall":    { "anchorFx": 0.5, "anchorFy": 0.96, "footTiles": 6.0, "scale": 1.0, "z": 0 } },
  "scenery":  { "background":   { "parallax": 0.25, "alpha": 1.0 },
                "midground_clouds": { "parallax": 0.55 },
                "foreground_fog":   { "parallax": 1.1, "alpha": 0.9 } }
}
```

- Anchors: `anchorX/anchorY` (+`w/h`) → fractional, or `anchorFx/anchorFy` (0..1)
  directly. Hall default `0.5, 0.96`; prop default `0.5, 0.9`.
- `footTiles` controls scale (how many tiles wide the footprint is); `scale` is an
  extra multiplier; `z` nudges draw order.

The browser console logs how many sprites / scenery layers / hall landmarks
loaded as **external** vs **baked/procedural** on every load.
