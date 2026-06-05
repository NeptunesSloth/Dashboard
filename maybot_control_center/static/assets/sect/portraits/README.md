# Disciple inspect portraits (optional, authored)

Drop a bust portrait per archetype here. When a disciple is clicked on the
Realm Map, the inspect panel shows the portrait for that disciple's archetype.
Missing portraits simply fall back to the text-only panel.

Files are named `<role>.png`, one per archetype:

  leader.png  elder.png  researcher.png  analyst.png
  engineer.png  architect.png  trader.png  disciple.png

(Leaders use `leader.png`; everyone else uses their role.)

## Specs
- Transparent PNG, head-and-shoulders bust, facing the viewer (slight 3/4).
- Square (e.g. 512x512); the panel renders it ~84px, object-fit: contain.
- Match the archetype's robe colour and signature item from the sprite pack.

Listed by `GET /api/sect/disciples` (the `portraits` array).
