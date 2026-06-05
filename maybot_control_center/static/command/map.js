import { $, api, esc, money, mountRail } from '/lib.js';

mountRail('map');

/* ====================================================================== *
 *  AEGIS — Living Sect Headquarters (isometric)
 *  Furnished halls, sizeable disciples with routines, work that you can see.
 *  Canvas2D for bright, crisp, dependable rendering everywhere.
 * ====================================================================== */

const canvas = $('scene-canvas');
const ctx = canvas.getContext('2d');
const TW2 = 40, TH2 = 20;                  // half tile width / height (2:1 iso)
const cam = { x: 0, y: 0, zoom: 0.9, userMoved: false };
const view = { cx: 0, cy: 0, w: 0, h: 0, dpr: 1 };
const rand = (a, b) => a + Math.random() * (b - a);
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function mulberry(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

/* ---------------- palette / room identities ---------------- */
const BG0 = '#070812', BG1 = '#0d1024';
const HEALTH = { ok: '#34d399', warning: '#fbbf24', error: '#fb5e7e', unknown: '#8b92ac' };
const KIND = {
  hall:        { name: 'Sect Hall',           floor: '#1d2348', wall: '#2c356a', accent: '#a78bfa', robe: '#b9a7ff', fx: '✦', plan: 'hall' },
  market:      { name: 'Trade Hall',          floor: '#12271f', wall: '#1c3a2e', accent: '#34d399', robe: '#f5c542', fx: '$', plan: 'market' },
  engineering: { name: 'Engineering Hall',    floor: '#11203b', wall: '#1b3055', accent: '#38bdf8', robe: '#5ac8ff', fx: '<>', plan: 'engineering' },
  library:     { name: 'Research Library',    floor: '#1d1838', wall: '#2a2356', accent: '#c4b5fd', robe: '#c4b5fd', fx: '✷', plan: 'library' },
  comms:       { name: 'Comms Tower',         floor: '#0f2238', wall: '#163a52', accent: '#22d3ee', robe: '#3fe0e0', fx: '⇡', plan: 'comms' },
  mission:     { name: 'Mission Hall',        floor: '#281a33', wall: '#3a2550', accent: '#fb7185', robe: '#fbbf24', fx: '⚑', plan: 'mission' },
  server:      { name: 'Server Core',         floor: '#0e1730', wall: '#172548', accent: '#60a5fa', robe: '#7bb0ff', fx: '▦', plan: 'server' },
  cultivation: { name: 'Cultivation Chamber', floor: '#1e1940', wall: '#2a2160', accent: '#a78bfa', robe: '#caa9ff', fx: '☯', plan: 'cultivation' },
  commerce:    { name: 'Commerce Pavilion',   floor: '#231d10', wall: '#3a2f18', accent: '#fbbf24', robe: '#fbbf24', fx: '❖', plan: 'commerce' },
};
function kindForType(type) {
  const t = String(type || '').toLowerCase();
  if (t.includes('trad') || t.includes('bot')) return 'market';
  if (t.includes('api') || t.includes('gateway') || t.includes('service')) return 'comms';
  if (t.includes('research') || t.includes('ml') || t.includes('ai') || t.includes('llm')) return 'library';
  if (t.includes('market') || t.includes('commerce') || t.includes('shop')) return 'commerce';
  return 'engineering';
}
/* cultivation identity — the sect name leads; the project is a secondary label */
const SECT_NAME = {
  hall: 'Sect Hall', mission: 'Hall of Heavenly Decrees', cultivation: 'Azure Spirit Grounds', server: 'Spirit Nexus Chamber',
  market: 'Hall of Myriad Treasures', engineering: 'Forge of Creation', library: 'Hall of Infinite Inquiry', comms: 'Thousand Paths Gate', commerce: 'Golden Prosperity Hall',
};
function sectNameForType(type) {
  const t = String(type || '').toLowerCase();
  if (/dashboard|analytic|metric|monitor|calc/.test(t)) return 'Heavenly Calculation Pavilion';
  if (/trad|bot|fund|invest/.test(t)) return 'Hall of Myriad Treasures';
  if (/commerce|shop|store|web|site|market/.test(t)) return 'Golden Prosperity Hall';
  if (/api|gateway|service|proxy/.test(t)) return 'Thousand Paths Gate';
  if (/research|ml|ai|llm|model|data/.test(t)) return 'Hall of Infinite Inquiry';
  return 'Forge of Creation';
}
/* one iconic landmark per district — a city is remembered by its landmarks */
function landmarkFor(room) {
  if (room.kind === 'hall') return 'monument';
  if (room.kind === 'mission') return 'bell';
  if (room.kind === 'cultivation') return 'vortex';
  if (room.kind === 'server') return 'nexus';
  return ({ 'Hall of Myriad Treasures': 'fountain', 'Heavenly Calculation Pavilion': 'observatory',
    'Golden Prosperity Hall': 'prosperity', 'Thousand Paths Gate': 'gate', 'Hall of Infinite Inquiry': 'tome',
    'Forge of Creation': 'forge' }[room.title]) || ({ market: 'fountain', engineering: 'forge', library: 'tome', comms: 'gate', commerce: 'prosperity' }[room.kind]) || 'monument';
}

/* ---------------- iso transforms ---------------- */
function toScreen(gx, gy) {
  const wx = (gx - gy) * TW2, wy = (gx + gy) * TH2;
  return { x: view.cx + (wx - cam.x) * cam.zoom, y: view.cy + (wy - cam.y) * cam.zoom };
}
function toGrid(sx, sy) {
  const wx = (sx - view.cx) / cam.zoom + cam.x, wy = (sy - view.cy) / cam.zoom + cam.y;
  return { gx: (wx / TW2 + wy / TH2) / 2, gy: (wy / TH2 - wx / TW2) / 2 };
}

/* ---------------- sprite layer: authored PNGs override baked voxel fallbacks ---------------- */
const SPR = { ready: false, meta: {}, img: {} };
(async function loadSprites() {
  try {
    const r = await fetch('/api/sect/manifest'); if (!r.ok) return; const man = await r.json();
    SPR.meta = man.sprites || {}; const names = Object.keys(SPR.meta); let n = 0;
    const done = () => { if (++n >= names.length) {
      SPR.ready = true;
      console.log(`%c[Realm Map] sprites — ${(man.external || []).length} external, ${(man.baked || []).length} baked fallback`, 'color:#a78bfa');
      if ((man.external || []).length) console.log('[Realm Map] external art:', man.external.join(', '));
      console.log('[Realm Map] baked fallback:', (man.baked || []).join(', '));
    } };
    if (!names.length) SPR.ready = true;
    names.forEach((name) => { const im = new Image(); im.onload = done; im.onerror = done; im.src = SPR.meta[name].url; SPR.img[name] = im; });
  } catch (_) { /* fall back to procedural drawing */ }
})();
function spriteZ(it) { return it.type === 'sprite' && SPR.meta[it.name] ? SPR.meta[it.name].z || 0 : 0; }
function blit(name, gx, gy, footTiles) {
  if (!SPR.ready) return false; const m = SPR.meta[name], img = SPR.img[name];
  if (!m || !img || !img.complete || !img.naturalWidth) return false;
  const w = img.naturalWidth, h = img.naturalHeight, s = toScreen(gx, gy);
  const sc = cam.zoom * footTiles / m.footTiles * (m.scale || 1);
  ctx.drawImage(img, s.x - m.anchorFx * w * sc, s.y - m.anchorFy * h * sc, w * sc, h * sc); return true;
}
const LM_SPRITE = { fountain: 'fountain', prosperity: 'fountain', observatory: 'observatory', forge: 'forge', tome: 'pavilion', gate: 'gate', bell: 'bell', nexus: 'crystal', vortex: 'tree' };
function drawBuildingBack(r, busy) {
  if (r.kind === 'hall') { if (blit('grand_pagoda', r.cx, r.cyc - 0.1, 4.6)) return; }
  else if (blit('pagoda', r.cx, r.gy + 1.7, 3.0)) return;
  drawPagoda(r, busy);
}
const LM_FT = { gate: 3.4, nexus: 1.9, observatory: 2.6, forge: 2.6, tome: 2.8, fountain: 2.4, prosperity: 2.4, bell: 2.2, vortex: 1.7 };
function drawLandmarkSprite(r, t, busy) {
  const nm = LM_SPRITE[r.landmark];
  if (nm) { if (blit(nm, r.cx, r.cyc + 0.8, LM_FT[r.landmark] || 2.4)) return; }
  if (r.landmark === 'monument') return;   // the grand pagoda is the centerpiece
  drawLandmark(r, t, busy);
}

/* ====================================================================== *
 *  Layout — rooms on a grid, Sect Hall (larger) at the centre
 * ====================================================================== */
const rooms = [];
let grounds = null;
function buildLayout(projects) {
  rooms.length = 0;
  const fixed = [
    { id: '__hall', title: 'Sect Hall', kind: 'hall' },
    { id: '__mission', title: 'Hall of Heavenly Decrees', kind: 'mission' },
    { id: '__cultivation', title: 'Azure Spirit Grounds', kind: 'cultivation' },
    { id: '__server', title: 'Spirit Nexus Chamber', kind: 'server' },
  ];
  const projRooms = projects.map((p) => ({ id: p.device + ':' + p.name, title: sectNameForType(p.type), sub: p.name, kind: kindForType(p.type), data: p }));
  const all = [fixed[0], ...projRooms, fixed[1], fixed[2], fixed[3]];
  const C = Math.max(3, Math.ceil(Math.sqrt(all.length)));
  const rowsN = Math.ceil(all.length / C);
  const STRIDE_X = 12, STRIDE_Y = 10;
  const centerCell = Math.floor(rowsN / 2) * C + Math.floor(C / 2);
  const order = []; order[centerCell] = all[0]; let q = 1;
  for (let cell = 0; cell < rowsN * C && q < all.length; cell++) { if (cell === centerCell) continue; order[cell] = all[q++]; }
  order.forEach((r, cell) => {
    if (!r) return;
    const col = cell % C, row = (cell / C) | 0;
    const big = r.kind === 'hall';
    const w = big ? 10 : 8, h = big ? 8 : 6;
    const gx = col * STRIDE_X + (big ? -1 : 0), gy = row * STRIDE_Y + (big ? -1 : 0);
    const K = KIND[r.kind];
    const room = { ...r, K, gx, gy, w, h, cx: gx + w / 2, cyc: gy + h / 2,
      door: { gx: gx + w / 2, gy: gy + h + 0.6 }, occupants: new Set(), depth: gx + gy + w / 2 + h / 2 };
    room.landmark = landmarkFor(room);
    furnish(room);
    rooms.push(room);
  });
  // elevation: the Sect Hall is the high summit; outer peaks step down toward the cloud sea
  const h0 = hall();
  rooms.forEach((r) => {
    if (!h0) { r.elev = 0; return; }
    const ring = Math.hypot((r.cx - h0.cx) / STRIDE_X, (r.cyc - h0.cyc) / STRIDE_Y);
    const jit = mulberry(hashStr((r.id || '') + ':e'))() * 16;
    r.elev = r.kind === 'hall' ? 58 : Math.max(4, 44 - ring * 17) + jit;
  });
  computeGrounds(); initAmbient(); initExtras(); centerOnHall();
}
function elevAt(gx, gy) {
  for (const r of rooms) if (gx >= r.gx - 0.6 && gx <= r.gx + r.w + 0.6 && gy >= r.gy - 0.6 && gy <= r.gy + r.h + 0.6) return r.elev || 0;
  return 0;
}
function computeGrounds() {
  let minGx = 1e9, minGy = 1e9, maxGx = -1e9, maxGy = -1e9;
  rooms.forEach((r) => { minGx = Math.min(minGx, r.gx); minGy = Math.min(minGy, r.gy); maxGx = Math.max(maxGx, r.gx + r.w); maxGy = Math.max(maxGy, r.gy + r.h); });
  const M = 2.6; grounds = { minGx: minGx - M, minGy: minGy - M, maxGx: maxGx + M, maxGy: maxGy + M };
}
const roomById = (id) => rooms.find((r) => r.id === id);
const hall = () => roomById('__hall');
const chamber = () => roomById('__cultivation');

function centerOnHall() {
  const h = hall(); if (!h) return;
  cam.x = (h.cx - h.cyc) * TW2; cam.y = (h.cx + h.cyc) * TH2;
  cam.zoom = Math.max(0.55, Math.min(1.0, view.w / 2000 + 0.55));
}

/* compose a whole district: main hall + landmark + secondary buildings + props, painted back-to-front */
function furnish(r) {
  const W = r.w, H = r.h, cx = W / 2, f = [], st = [];
  const B = (name, gx, gy, ft) => f.push({ type: 'sprite', name, gx, gy, ft });
  const P = (type, gx, gy, opt) => f.push({ type, gx, gy, ...opt });
  const lant = (gx, gy) => B('lantern', gx, gy, 0.5);
  const ring = () => { lant(0.7, 0.7); lant(W - 0.7, 0.7); lant(0.7, H - 0.7); lant(W - 0.7, H - 0.7); };
  switch (r.landmark) {
    case 'fountain': case 'prosperity':          // crowded market district
      B('pagoda', cx, 1.7, 3.0); B('pagoda', 1.5, 1.4, 1.8); B('pagoda', W - 1.5, 1.4, 1.8); B('fountain', cx, 4.1, 2.4);
      for (let i = 0; i < 4; i++) B('stall', 1.4 + i * (W - 2.8) / 3, H - 1.0, 1.4);
      B('stall', 1.4, 3.2, 1.4); B('stall', W - 1.4, 3.2, 1.4);
      P('cart', cx + 1.9, H - 1.9); P('crate', 1.1, H - 2.0); P('crate', 1.6, H - 1.7); P('crate', W - 1.2, H - 2.0);
      P('banner', 1.0, 0.5); P('banner', W - 1.6, 0.5); ring();
      st.push([cx - 1.4, H - 1.7]); st.push([cx + 0.6, H - 1.7]); st.push([1.9, 3.4]); st.push([W - 1.9, 3.4]); break;
    case 'observatory':                          // scholar complex
      B('pagoda', cx, 1.6, 2.8); B('observatory', cx, 4.0, 2.6); B('pavilion', 1.6, 2.6, 2.0); B('pavilion', W - 1.6, 2.6, 2.0);
      for (let i = 0; i < 3; i++) { P('desk', 1.4 + i * 1.2, H - 1.1); P('screen', 1.7 + i * 1.2, H - 1.2, { content: 'graph' }); st.push([1.9 + i * 1.2, H - 0.6]); }
      P('pillar', 1.0, H - 2.2); P('pillar', W - 1.0, H - 2.2); ring(); break;
    case 'forge':                                // workshop yard
      B('pagoda', cx, 1.6, 2.6); B('forge', cx, 4.0, 2.6); B('pavilion', W - 1.7, 2.6, 2.0);
      for (let i = 0; i < 3; i++) { P('bench', 1.4, 2.2 + i * 1.5); st.push([2.0, 2.4 + i * 1.5]); }
      P('crate', 1.0, H - 1.0); P('crate', 1.7, H - 1.2); P('crate', W - 1.4, H - 1.0); ring(); break;
    case 'tome':                                 // archive + study garden
      B('pagoda', cx, 1.6, 2.8); B('pavilion', cx, 4.1, 2.6); B('cherry', 1.5, 4.4, 1.1); B('cherry', W - 1.5, 4.4, 1.1);
      for (let i = 0; i < 4; i++) P('shelf', 1.2 + i * 0.9, 3.0);
      P('desk', cx - 1.6, H - 1.1); P('desk', cx + 0.8, H - 1.1); st.push([cx - 1.0, H - 0.6]); st.push([cx + 1.4, H - 0.6]);
      P('bench', 1.5, H - 1.0); P('bench', W - 1.7, H - 1.0); ring(); break;
    case 'gate':                                 // arrival plaza
      B('gate', cx, 2.2, 3.4); B('pavilion', 1.6, 2.6, 2.0); B('pavilion', W - 1.6, 2.6, 2.0);
      P('cart', 1.6, H - 1.3); P('cart', W - 2.0, H - 1.6); P('crate', 1.0, H - 0.9); P('crate', 1.7, H - 1.1); P('crate', W - 1.2, H - 0.9);
      P('board', 2.4, H - 1.7); P('bench', cx, H - 1.0); P('banner', 0.9, 0.5); P('banner', W - 1.5, 0.5); ring();
      st.push([cx - 1.4, H - 0.8]); st.push([cx + 1.2, H - 0.8]); break;
    case 'bell':                                 // hall of decrees
      B('pagoda', cx, 1.6, 2.8); B('bell', cx, 3.8, 2.2); B('pavilion', W - 1.7, 2.6, 1.9);
      P('board', 1.4, 2.6); P('board', 1.4, 3.8); P('bench', cx - 1.6, H - 1.2); P('bench', cx + 1.2, H - 1.2); P('bench', W - 1.8, H - 1.2);
      P('banner', cx - 0.6, 0.4); ring(); st.push([1.9, 3.2]); st.push([cx, H - 0.7]); break;
    case 'nexus':                                // operational energy complex
      B('crystal', cx, 3.6, 1.9); B('pavilion', 1.6, 1.9, 1.8); B('pavilion', W - 1.6, 1.9, 1.8);
      [[1.3, H - 1.3], [W - 1.3, H - 1.3], [cx - 2, 2.2], [cx + 2, 2.2]].forEach(([x, y]) => P('pillar', x, y));
      [[1.3, H - 1.3], [W - 1.3, H - 1.3]].forEach(([x, y]) => P('conduit', x, y, { to: [cx, H / 2] }));
      P('crate', 1.2, H - 2.0); ring(); st.push([1.9, H - 1.1]); st.push([W - 1.9, H - 1.1]); break;
    case 'vortex':                               // spirit grounds
      B('pavilion', cx, 1.7, 2.6); B('tree', cx, 4.0, 1.7); B('pine', 1.5, 1.6, 1.1); B('pine', W - 1.5, 1.6, 1.1); B('crane', cx + 2.4, H - 1.4, 1.0);
      P('circle', cx - 1.8, H - 1.6); P('circle', cx + 1.8, H - 1.6); P('bench', 1.4, H - 1.0); P('bench', W - 1.6, H - 1.0); ring();
      st.push([cx - 1.8, H - 1.6]); st.push([cx + 1.8, H - 1.6]); break;
    case 'monument': default:                    // sect capital
      B('grand_pagoda', cx, 3.0, 4.6); B('pavilion', 1.6, 1.8, 2.2); B('pavilion', W - 1.8, 1.8, 2.2);
      B('cherry', 1.4, H - 1.6, 1.2); B('pine', W - 1.4, H - 1.6, 1.2); B('crane', cx - 2.6, H - 0.9, 1.0);
      P('dais', cx - 1.4, H - 2.4); P('circle', cx, H - 1.0);
      P('bench', cx - 2.6, H - 1.6); P('bench', cx + 1.8, H - 1.6); P('banner', cx - 2.4, 0.4); P('banner', cx + 1.6, 0.4);
      P('brazier', 2.2, H / 2 + 1); P('brazier', W - 2.2, H / 2 + 1); ring(); break;
  }
  // rocks + groves around the rim so terrain (not a square) frames the location
  const rg2 = mulberry(hashStr((r.id || r.title) + ':n'));
  for (let i = 0; i < 6; i++) { const a = (i / 6) * 6.28 + rg2(); const gx = cx + Math.cos(a) * (W * 0.46), gy = H / 2 + Math.sin(a) * (H * 0.46);
    f.push({ type: 'rock', gx: Math.max(0.3, Math.min(W - 0.3, gx)), gy: Math.max(0.3, Math.min(H - 0.3, gy)), s: 0.6 + rg2() * 0.8 }); }
  for (let i = 0; i < 3; i++) { const a = rg2() * 6.28; f.push({ type: 'sprite', name: rg2() < 0.5 ? 'pine' : 'cherry', gx: cx + Math.cos(a) * (W * 0.4), gy: H / 2 + Math.sin(a) * (H * 0.4), ft: 1.0 }); }
  f.sort((a, b) => (a.gx + a.gy) - (b.gx + b.gy));     // back-to-front so structures overlap correctly
  r.furniture = f; r.stations = st.length ? st : [[W / 2, H * 0.62]];
  // organic terrace outline replaces the square boundary
  const ro = mulberry(hashStr((r.id || r.title) + ':o')); r.outline = [];
  [[0, 0, W, 0], [W, 0, W, H], [W, H, 0, H], [0, H, 0, 0]].forEach(([x0, y0, x1, y1]) => {
    for (let s = 0; s < 4; s++) { const fp = s / 4, gx = x0 + (x1 - x0) * fp, gy = y0 + (y1 - y0) * fp; let nx = gx - W / 2, ny = gy - H / 2; const L = Math.hypot(nx, ny) || 1; const j = 0.5 + ro() * 1.3; r.outline.push({ gx: gx + nx / L * j, gy: gy + ny / L * j }); }
  });
  const rng = mulberry(hashStr(r.id || r.title || 'x')); r.spots = [];
  for (let i = 0; i < 18; i++) r.spots.push({ x: 0.7 + rng() * (W - 1.4), y: 0.7 + rng() * (H - 1.4), r: rng() });
}

/* ====================================================================== *
 *  Disciples
 * ====================================================================== */
const ROLE_STYLE = {
  trader:     { color: '#f5c542', prop: 'tablet' },
  engineer:   { color: '#5ac8ff', prop: 'visor' },
  researcher: { color: '#c4b5fd', prop: 'scroll' },
  analyst:    { color: '#34d399', prop: 'clip' },
  architect:  { color: '#7bb0ff', prop: 'tools' },
  elder:      { color: '#ecd9a6', prop: 'staff' },
  disciple:   { color: '#9a8cff', prop: 'none' },
};
const ROLE_LIST = ['trader', 'engineer', 'researcher', 'analyst', 'architect'];
function roleOf(ag) {
  const g = ag.governance || {}; if (g.is_leader || g.is_elder || g.is_master) return 'elder';
  const r = String(ag.role || '').toLowerCase();
  if (/trad|market|invest|fund/.test(r)) return 'trader';
  if (/eng|develop|code|build|deploy/.test(r)) return 'engineer';
  if (/research|scholar|study/.test(r)) return 'researcher';
  if (/analy|data|quant|signal/.test(r)) return 'analyst';
  if (/architect|infra|ops|server|system|network/.test(r)) return 'architect';
  let h = 0; for (const c of ag.name) h = (h * 31 + c.charCodeAt(0)) | 0;
  return ROLE_LIST[Math.abs(h) % ROLE_LIST.length];
}
const disciples = [];
function hallSpot() { const h = hall(); if (!h) return { gx: 0, gy: 0 };
  return { gx: h.gx + 1 + Math.random() * (h.w - 2), gy: h.gy + h.h * 0.45 + Math.random() * (h.h * 0.5) }; }

function makeDisciple(ag, i) {
  const s = hallSpot();
  return { name: ag.name, data: ag, role: roleOf(ag), gx: s.gx, gy: s.gy, tx: s.gx, ty: s.gy, state: 'idle', room: null,
    speed: 1.6 + Math.random() * 0.7, phase: Math.random() * 6.28, idleAct: 'wander', idleT: 0, alpha: 1, roamPhase: null,
    idx: i, progress: 0, chat: 0, facing: 1 };
}
function ensureDisciples(agents) {
  const have = new Set(disciples.map((d) => d.name));
  agents.forEach((a, i) => { if (!have.has(a.name)) disciples.push(makeDisciple(a, i)); });
  disciples.forEach((d) => { const fresh = agents.find((a) => a.name === d.name); if (fresh) { if (d.data.__sim) fresh.__sim = d.data.__sim; d.data = fresh; } });
}

function matchRoom(task) { if (!task) return null; const t = String(task).toLowerCase();
  return rooms.find((r) => r.data && t.includes(String(r.title).toLowerCase())) || null; }
function workRoom(d) { const sim = d.data.__sim; if (sim && sim.room) return roomById(sim.room) || null; return matchRoom(d.data.current_task) || rooms.find((r) => r.data) || null; }
function stationSpot(r, d) { const s = r.stations[d.idx % r.stations.length]; const j = (d.idx * 0.37) % 0.5;
  return { gx: r.gx + s[0] + j - 0.25, gy: r.gy + s[1] }; }

function deriveState(d) {
  const ag = d.data, cult = ag.cultivation || {}, sim = ag.__sim;
  const stt = sim ? sim.state : (cult.in_seclusion ? 'meditate' : cult.in_roaming ? 'roaming'
    : (ag.status === 'working' || ag.status === 'queued') ? 'working' : ag.status === 'error' ? 'error' : 'idle');
  if (stt === 'working') {
    const r = workRoom(d); if (!r) { setIdle(d); return; }
    if (d.room !== r) { if (d.room) d.room.occupants.delete(d); d.room = r; r.occupants.add(d); d.spot = stationSpot(r, d); d.progress = 0; }
    const near = Math.hypot(d.gx - d.spot.gx, d.gy - d.spot.gy) < 0.6;
    d.state = near ? 'working' : 'traveling'; d.tx = d.spot.gx; d.ty = d.spot.gy;
  } else {
    if (d.room) { d.room.occupants.delete(d); d.room = null; }
    if (stt === 'roaming') { if (d.state !== 'roaming') { d.state = 'roaming'; d.roamPhase = null; } }
    else if (stt === 'meditate') { d.state = 'meditate'; const c = chamber(); if (c) { const s = c.stations[d.idx % c.stations.length]; d.tx = c.gx + s[0]; d.ty = c.gy + s[1]; } }
    else if (stt === 'error') { d.state = 'error'; }
    else setIdle(d);
  }
}
function setIdle(d) { if (d.state !== 'idle') { d.state = 'idle'; d.pause = 0; } }

/* movement */
function step(d, dt, t) {
  if (d.chat > 0) { d.chat -= dt; d.moving = false; return; }
  if (d.state === 'roaming') return stepRoam(d, dt, t);
  d.alpha = Math.min(1, d.alpha + dt * 2);
  const dx = d.tx - d.gx, dy = d.ty - d.gy, dist = Math.hypot(dx, dy);
  if (dist > 0.05) {
    const v = Math.min(dist, d.speed * dt); d.gx += (dx / dist) * v; d.gy += (dy / dist) * v;
    d.phase += dt * 9; d.moving = true; d.facing = (dx - dy) >= 0 ? 1 : -1;
  } else {
    d.moving = false;
    if (d.state === 'working') d.progress = Math.min(1, d.progress + dt * 0.03);
    if (d.state === 'idle') {
      d.idleT -= dt;
      if (d.idleT <= 0) {
        const r = Math.random();
        d.idleAct = r < 0.45 ? 'wander' : r < 0.65 ? 'train' : r < 0.82 ? 'observe' : 'meditate';
        d.idleT = 3 + Math.random() * 5;
        if (d.idleAct === 'wander') { const s = hallSpot(); d.tx = s.gx; d.ty = s.gy; } else { d.tx = d.gx; d.ty = d.gy; }
      }
    }
  }
}
function stepRoam(d, dt, t) {
  if (!d.roamPhase) { d.roamPhase = 'out'; const h = hall(); const ang = Math.atan2(d.gy - (h ? h.cyc : 0), d.gx - (h ? h.cx : 0)) || Math.random() * 6.28;
    d.tx = d.gx + Math.cos(ang) * 16; d.ty = d.gy + Math.sin(ang) * 16; }
  const dx = d.tx - d.gx, dy = d.ty - d.gy, dist = Math.hypot(dx, dy);
  if (dist > 0.05) { const v = Math.min(dist, d.speed * dt); d.gx += (dx / dist) * v; d.gy += (dy / dist) * v; d.phase += dt * 9; d.moving = true; }
  if (d.roamPhase === 'out' && dist < 0.5) { d.roamPhase = 'gone'; d.goneUntil = t + 6 + Math.random() * 8; }
  if (d.roamPhase === 'gone') { d.alpha = Math.max(0, d.alpha - dt); if (t > d.goneUntil) { d.roamPhase = 'back'; const s = hallSpot(); d.tx = s.gx; d.ty = s.gy; } }
  else if (d.roamPhase === 'back') { d.alpha = Math.min(1, d.alpha + dt); if (dist < 0.5) { d.roamPhase = null; if (d.data.__sim) d.data.__sim = { state: 'idle' }; } }
}

/* socialising — idle disciples in the hall occasionally pair up */
function socialTick() {
  const idle = disciples.filter((d) => d.state === 'idle' && d.chat <= 0 && !d.moving);
  for (let i = 0; i < idle.length; i++) for (let j = i + 1; j < idle.length; j++) {
    if (Math.hypot(idle[i].gx - idle[j].gx, idle[i].gy - idle[j].gy) < 2.2 && Math.random() < 0.25) { idle[i].chat = idle[j].chat = 2.5 + Math.random() * 2; return; }
  }
}

/* ====================================================================== *
 *  Drawing primitives
 * ====================================================================== */
function shade(hex, amt) { const n = parseInt(hex.slice(1), 16); let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const f = (v) => Math.max(0, Math.min(255, Math.round(v + (amt > 0 ? (255 - v) * amt : v * amt)))); return `rgb(${f(r)},${f(g)},${f(b)})`; }
function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function isoBox(gx, gy, fw, fh, hpx, top, left, right) {
  const z = cam.zoom, h = hpx * z;
  const A0 = toScreen(gx, gy), B0 = toScreen(gx + fw, gy), C0 = toScreen(gx + fw, gy + fh), D0 = toScreen(gx, gy + fh);
  ctx.fillStyle = left; ctx.beginPath(); ctx.moveTo(D0.x, D0.y); ctx.lineTo(C0.x, C0.y); ctx.lineTo(C0.x, C0.y - h); ctx.lineTo(D0.x, D0.y - h); ctx.closePath(); ctx.fill();
  ctx.fillStyle = right; ctx.beginPath(); ctx.moveTo(B0.x, B0.y); ctx.lineTo(C0.x, C0.y); ctx.lineTo(C0.x, C0.y - h); ctx.lineTo(B0.x, B0.y - h); ctx.closePath(); ctx.fill();
  ctx.fillStyle = top; ctx.beginPath(); ctx.moveTo(A0.x, A0.y - h); ctx.lineTo(B0.x, B0.y - h); ctx.lineTo(C0.x, C0.y - h); ctx.lineTo(D0.x, D0.y - h); ctx.closePath(); ctx.fill();
}
function holoScreen(gx, gy, wpx, hpx, lift, color, content, t, on) {
  const z = cam.zoom, p = toScreen(gx, gy), w = wpx * z, h = hpx * z, x = p.x - w / 2, y = p.y - lift * z - h;
  ctx.save(); ctx.globalAlpha = on ? 0.95 : 0.55;
  ctx.fillStyle = 'rgba(8,12,24,.82)'; roundRect(x, y, w, h, 3 * z); ctx.fill();
  ctx.strokeStyle = color; ctx.lineWidth = 1.4 * z; ctx.shadowColor = color; ctx.shadowBlur = (on ? 9 : 3) * z; roundRect(x, y, w, h, 3 * z); ctx.stroke(); ctx.shadowBlur = 0;
  ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.4 * z;
  const tk = (t * 30) | 0;
  if (content === 'chart') { ctx.beginPath(); for (let i = 0; i < 6; i++) ctx[i ? 'lineTo' : 'moveTo'](x + (i / 5) * w, y + h * 0.7 - (Math.sin(i + tk * 0.1) * 0.5 + 0.5) * h * 0.5); ctx.stroke();
    ctx.fillStyle = '#34d399'; for (let i = 0; i < 4; i++) { const bh = ((i + tk) % 5 + 1) / 6 * h * 0.5; ctx.fillRect(x + 3 * z + i * (w - 6 * z) / 4, y + h - bh - 2 * z, (w - 8 * z) / 6, bh); } }
  else if (content === 'code') { for (let i = 0; i < 4; i++) { ctx.globalAlpha = (on ? 0.9 : 0.5); ctx.fillRect(x + 3 * z, y + 3 * z + i * h / 4, ((i + tk) % 4 + 2) / 7 * w, 1.6 * z); } }
  else if (content === 'graph') { ctx.beginPath(); for (let i = 0; i <= 8; i++) ctx[i ? 'lineTo' : 'moveTo'](x + (i / 8) * w, y + h - (i / 8) * h * 0.8 - Math.sin(i + tk * 0.1) * 3 * z); ctx.stroke(); }
  else if (content === 'board') { ctx.fillStyle = '#fbbf24'; for (let i = 0; i < 3; i++) ctx.fillRect(x + 4 * z + i * (w / 3), y + 4 * z, w / 4, h - 8 * z); }
  else { for (let i = 0; i < 3; i++) ctx.fillRect(x + 3 * z, y + 4 * z + i * h / 3, (((i + tk) % 3 + 1) / 4) * w, 2 * z); }
  ctx.restore();
}

/* ====================================================================== *
 *  Rooms
 * ====================================================================== */
function drawWaterfall(x, y, TH, t) {
  const z = cam.zoom;
  ctx.fillStyle = 'rgba(150,210,255,.32)'; ctx.fillRect(x - 4 * z, y, 8 * z, TH);
  ctx.strokeStyle = 'rgba(230,245,255,.6)'; ctx.lineWidth = 1.3 * z;
  for (let i = 0; i < 5; i++) { const yy = y + ((t * 140 * z + i * TH / 5) % TH); ctx.beginPath(); ctx.moveTo(x - 3 * z + i * 1.6 * z, yy); ctx.lineTo(x - 3 * z + i * 1.6 * z, yy + 9 * z); ctx.stroke(); }
  ctx.fillStyle = 'rgba(220,235,255,.5)'; for (let i = 0; i < 2; i++) { ctx.beginPath(); ctx.ellipse(x + (i - 0.5) * 8 * z, y + TH + Math.sin(t * 2 + i) * 2 * z, 11 * z, 4 * z, 0, 0, 6.28); ctx.fill(); }
}
function drawCliff(r, A, B, Cc, D, TH, t) {
  const z = cam.zoom, rock = '#2c2b3c', rockD = '#1b1a27';
  ctx.fillStyle = rock; ctx.beginPath(); ctx.moveTo(D.x, D.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(D.x, D.y + TH); ctx.closePath(); ctx.fill();
  ctx.fillStyle = rockD; ctx.beginPath(); ctx.moveTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(B.x, B.y + TH); ctx.closePath(); ctx.fill();
  // rock striations
  ctx.strokeStyle = 'rgba(0,0,0,.28)'; ctx.lineWidth = 1;
  for (let i = 1; i < r.h; i++) { const p = toScreen(r.gx, r.gy + i); ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x, p.y + TH); ctx.stroke(); }
  for (let i = 1; i < r.w; i++) { const p = toScreen(r.gx + i, r.gy + r.h); ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x, p.y + TH); ctx.stroke(); }
  // top edge highlight
  ctx.strokeStyle = 'rgba(150,150,184,.28)'; ctx.lineWidth = 1.4 * z; ctx.beginPath(); ctx.moveTo(D.x, D.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(B.x, B.y); ctx.stroke();
  // waterfalls for the watery/spirit terraces
  if (r.landmark === 'vortex' || r.landmark === 'nexus' || r.kind === 'hall') drawWaterfall(Cc.x, Cc.y, TH, t);
  // clinging mist at the cliff base
  const mb = toScreen(r.cx, r.gy + r.h); ctx.globalAlpha = 0.5; ctx.fillStyle = 'rgba(205,214,236,.5)';
  for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.ellipse(mb.x + (i - 1.5) * 28 * z, mb.y + TH - 4 * z + Math.sin(t * 1.5 + i) * 3 * z, 22 * z, 6 * z, 0, 0, 6.28); ctx.fill(); }
  ctx.globalAlpha = 1;
}
function outlinePath(O) { ctx.beginPath(); O.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)); ctx.closePath(); }
function drawRoom(r, t) {
  const z = cam.zoom, K = r.K, occ = r.occupants.size, busy = Math.min(1, occ * 0.45);
  ctx.save(); ctx.translate(0, -(r.elev || 0) * z);    // raise this peak to its elevation
  const O = r.outline.map((p) => toScreen(p.gx, p.gy));
  const TH = (38 + (r.elev || 0) + (r.kind === 'hall' ? 12 : 0)) * z;   // cliff drops to the cloud sea
  let minY = 1e9, maxY = -1e9; O.forEach((p) => { minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); });
  // ---- rocky cliff face (follows the irregular outline) ----
  ctx.beginPath(); O.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
  for (let i = O.length - 1; i >= 0; i--) ctx.lineTo(O[i].x, O[i].y + TH); ctx.closePath();
  const cg = ctx.createLinearGradient(0, minY, 0, maxY + TH); cg.addColorStop(0, '#34323f'); cg.addColorStop(0.5, '#26242f'); cg.addColorStop(1, '#15131c');
  ctx.fillStyle = cg; ctx.fill();
  ctx.strokeStyle = 'rgba(0,0,0,.3)'; ctx.lineWidth = 1;            // striations
  for (let i = 0; i < O.length; i += 2) { ctx.beginPath(); ctx.moveTo(O[i].x, O[i].y); ctx.lineTo(O[i].x + (i % 4 ? 2 : -2), O[i].y + TH); ctx.stroke(); }
  if (['vortex', 'nexus', 'observatory', 'gate', 'tome'].includes(r.landmark) || r.kind === 'hall') {
    const lo = O.reduce((a, b) => b.y > a.y ? b : a, O[0]); drawWaterfall(lo.x, lo.y, TH, t);
    if (r.kind === 'hall') { const l2 = O.reduce((a, b) => (b.x < a.x ? b : a), O[0]); drawWaterfall(l2.x, l2.y, TH * 0.8, t); }
  }
  // clinging mist at the base
  ctx.globalAlpha = 0.5; ctx.fillStyle = 'rgba(205,214,236,.5)';
  for (let i = 0; i < O.length; i += 2) { ctx.beginPath(); ctx.ellipse(O[i].x, O[i].y + TH - 2 * z + Math.sin(t * 1.5 + i) * 2 * z, 16 * z, 5 * z, 0, 0, 6.28); ctx.fill(); }
  ctx.globalAlpha = 1;
  // ---- terrace top (earth/stone, no square, no grid) ----
  const trouble = r.data && (r.data.health === 'error' || r.data.health === 'warning');
  outlinePath(O); const tg = ctx.createLinearGradient(0, minY, 0, maxY); tg.addColorStop(0, shade(K.floor, 0.18)); tg.addColorStop(1, shade(K.floor, -0.12));
  ctx.fillStyle = tg; ctx.fill();
  ctx.save(); outlinePath(O); ctx.clip();
  if (trouble) { ctx.globalAlpha = 0.18; ctx.fillStyle = HEALTH[r.data.health]; ctx.fillRect(O[0].x - 400, minY - 100, 800, (maxY - minY) + 200); ctx.globalAlpha = 1; }
  if (busy > 0) { const c = toScreen(r.cx, r.cyc); const rg = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, 130 * z); rg.addColorStop(0, K.accent); rg.addColorStop(1, 'transparent'); ctx.globalAlpha = 0.1 + busy * 0.14; ctx.fillStyle = rg; ctx.fillRect(c.x - 150 * z, c.y - 150 * z, 300 * z, 300 * z); ctx.globalAlpha = 1; }
  drawDistrictGround(r); drawTerrainDressing(r, t);
  ctx.restore();
  // soft rocky rim highlight (not a hard square border)
  ctx.strokeStyle = 'rgba(150,150,180,.2)'; ctx.lineWidth = 1.5 * z; outlinePath(O); ctx.stroke();
  // ---- the location's scene (buildings + props), painted back-to-front (+authored z) ----
  r.furniture.slice().sort((a, b) => (a.gx + a.gy + spriteZ(a)) - (b.gx + b.gy + spriteZ(b))).forEach((it) => drawFurniture(r, it, t, busy));
  if (hover.room === r || selected.room === r) { ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 2 * z; outlinePath(O); ctx.stroke(); }
  ctx.restore();
}
function drawWall(p1, p2, K, busy) {
  const H = 26 * cam.zoom;
  ctx.fillStyle = shade(K.wall, -0.05); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(p2.x, p2.y - H); ctx.lineTo(p1.x, p1.y - H); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = K.accent; ctx.globalAlpha = 0.45 + busy * 0.4; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(p1.x, p1.y - H); ctx.lineTo(p2.x, p2.y - H); ctx.stroke(); ctx.globalAlpha = 1;
}
function drawArchitecture(r, busy) {
  const z = cam.zoom, K = r.K, w = r.w, h = r.h;
  // front railings (the two camera-facing edges) with a central doorway gap
  railing(r.gx, r.gy + h, r.gx + w, r.gy + h, K);
  railing(r.gx + w, r.gy, r.gx + w, r.gy + h, K);
  // corner columns + lamp fixtures
  const corners = [[r.gx, r.gy, 0.18, 0.18], [r.gx + w, r.gy, -0.5, 0.18], [r.gx + w, r.gy + h, -0.5, -0.5], [r.gx, r.gy + h, 0.18, -0.5]];
  corners.forEach(([cgx, cgy, ox, oy], i) => {
    isoBox(cgx + ox, cgy + oy, 0.32, 0.32, 30, shade(K.wall, 0.08), shade(K.wall, -0.22), shade(K.wall, -0.34));
    const p = toScreen(cgx + ox + 0.16, cgy + oy + 0.16);
    ctx.fillStyle = K.accent; ctx.globalAlpha = 0.7 + busy * 0.3; ctx.shadowColor = K.accent; ctx.shadowBlur = (8 + busy * 6) * z;
    ctx.beginPath(); ctx.arc(p.x, p.y - 31 * z, 2.3 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  });
}
function drawPagoda(r, busy) {
  const z = cam.zoom, K = r.K, A = toScreen(r.gx, r.gy), B = toScreen(r.gx + r.w, r.gy);
  const cx = (A.x + B.x) / 2, backY = Math.min(A.y, B.y) - 30 * z;     // sits above the back wall
  const w = Math.abs(B.x - A.x) * 0.95 + 8 * z, roofCol = shade(K.accent, -0.58), tiers = r.kind === 'hall' ? 3 : 2;
  const tier = (yy, ww, hh) => {
    ctx.fillStyle = roofCol; ctx.beginPath();
    ctx.moveTo(cx - ww / 2, yy); ctx.quadraticCurveTo(cx - ww / 2 - 7 * z, yy - 3 * z, cx - ww * 0.34, yy - 3 * z);
    ctx.lineTo(cx, yy - hh); ctx.lineTo(cx + ww * 0.34, yy - 3 * z); ctx.quadraticCurveTo(cx + ww / 2 + 7 * z, yy - 3 * z, cx + ww / 2, yy); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = K.accent; ctx.globalAlpha = 0.55 + busy * 0.35; ctx.lineWidth = 1.3 * z; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillStyle = shade(roofCol, 0.18); ctx.fillRect(cx - ww / 2, yy - 1.5 * z, ww, 1.6 * z);   // eave board
    ctx.fillStyle = '#fbbf24'; ctx.shadowColor = '#fbbf24'; ctx.shadowBlur = 6 * z;               // eave lanterns
    ctx.beginPath(); ctx.arc(cx - ww / 2, yy + 3 * z, 1.5 * z, 0, 6.28); ctx.arc(cx + ww / 2, yy + 3 * z, 1.5 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
  };
  for (let i = 0; i < tiers; i++) tier(backY - i * 17 * z, w * (1 - i * 0.26), 15 * z);
  ctx.fillStyle = K.accent; ctx.shadowColor = K.accent; ctx.shadowBlur = 8 * z;                    // finial
  ctx.beginPath(); ctx.arc(cx, backY - tiers * 17 * z + 2 * z, 2.6 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
}
function railing(ax, ay, bx, by, K) {
  const N = 6, z = cam.zoom, H = 9; let prevTop = null;
  for (let i = 0; i <= N; i++) {
    const gx = ax + (bx - ax) * i / N, gy = ay + (by - ay) * i / N, inGap = i >= 2 && i <= 4;     // doorway in the middle
    const p = toScreen(gx, gy), top = { x: p.x, y: p.y - H * z };
    if (!inGap) { ctx.strokeStyle = shade(K.wall, 0.12); ctx.lineWidth = 1.4 * z; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(top.x, top.y); ctx.stroke(); }
    if (prevTop && !inGap) { ctx.strokeStyle = K.accent; ctx.globalAlpha = 0.45; ctx.lineWidth = 1.4 * z; ctx.beginPath(); ctx.moveTo(prevTop.x, prevTop.y); ctx.lineTo(top.x, top.y); ctx.stroke(); ctx.globalAlpha = 1; }
    prevTop = inGap ? null : top;
  }
}

function drawFurniture(r, it, t, busy) {
  const A = r.K.accent, gx = r.gx + it.gx, gy = r.gy + it.gy, z = cam.zoom, on = busy > 0;
  if (it.type === 'sprite') { const small = ['lantern', 'crane', 'pine', 'cherry', 'tree'].includes(it.name);
    const ft = it.ft * (small ? 0.85 : 0.44);         // halls are one feature in a location, not the whole place
    if (blit(it.name, gx, gy, ft)) return; isoBox(gx - 0.5, gy - 0.5, 1, 1, 12, shade(r.K.wall, 0.05), shade(r.K.wall, -0.25), shade(r.K.wall, -0.35)); return; }
  if (it.type === 'rock') { const p = toScreen(gx, gy), s = (it.s || 1);
    ctx.fillStyle = '#3a3947'; ctx.beginPath(); ctx.moveTo(p.x - 7 * s * z, p.y); ctx.lineTo(p.x - 3 * s * z, p.y - 8 * s * z); ctx.lineTo(p.x + 4 * s * z, p.y - 9 * s * z); ctx.lineTo(p.x + 7 * s * z, p.y); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#4a4857'; ctx.beginPath(); ctx.moveTo(p.x - 3 * s * z, p.y - 8 * s * z); ctx.lineTo(p.x + 4 * s * z, p.y - 9 * s * z); ctx.lineTo(p.x + 1 * s * z, p.y - 4 * s * z); ctx.lineTo(p.x - 1 * s * z, p.y - 4 * s * z); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#2a2935'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 7 * s * z, 2.4 * s * z, 0, 0, 6.28); ctx.fill(); return; }
  switch (it.type) {
    case 'desk': isoBox(gx, gy, 1.3, 0.7, 9, shade(r.K.floor, 0.3), shade(r.K.floor, 0.05), shade(r.K.floor, -0.1)); break;
    case 'counter': isoBox(gx, gy, 2.2, 0.8, 11, shade(A, -0.1), shade(A, -0.4), shade(A, -0.5)); break;
    case 'screen': holoScreen(gx + 0.6, gy, 30, 20, 12, A, it.content, t, on); break;
    case 'holo': { const p = toScreen(gx, gy); ctx.save(); ctx.globalAlpha = 0.3 + busy * 0.3; ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 12 * z;
      for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.ellipse(p.x, p.y - (22 + i * 9) * z, (16 - i * 4) * z, (7 - i * 1.6) * z, 0, 0, 6.28); ctx.stroke(); } ctx.restore();
      holoScreen(gx, gy, 34, 22, 30, A, it.content, t, on); break; }
    case 'table': isoBox(gx, gy, 1.8, 1.1, 7, shade(r.K.floor, 0.22), shade(r.K.floor, 0), shade(r.K.floor, -0.12));
      if (it.content) { const p = toScreen(gx + 0.9, gy + 0.55); ctx.globalAlpha = 0.5 + busy * 0.3; ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 8 * z;
        ctx.beginPath(); ctx.ellipse(p.x, p.y - 14 * z, 9 * z, 4 * z, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; } break;
    case 'shelf': isoBox(gx, gy, 1.0, 0.6, 22, shade(A, -0.25), shade(A, -0.5), shade(A, -0.6)); {
      const top = toScreen(gx, gy); ctx.fillStyle = shade(A, 0.2); for (let l = 0; l < 3; l++) ctx.fillRect(top.x - 7 * z, top.y - (8 + l * 6) * z, 14 * z, 2 * z); } break;
    case 'rack': isoBox(gx, gy, 0.9, 0.9, 24, shade('#16233f', 0.1), shade('#0e1830', -0.1), shade('#0c1428', -0.2)); {
      const p = toScreen(gx + 0.45, gy); for (let l = 0; l < 5; l++) { ctx.fillStyle = (l + (t * 2 | 0) + it.gx) % 3 ? '#34d399' : A; ctx.globalAlpha = on ? 1 : 0.6; ctx.fillRect(p.x - 5 * z, p.y - (6 + l * 4) * z, 3 * z, 2 * z); } ctx.globalAlpha = 1; } break;
    case 'tower': { isoBox(gx, gy, 1.4, 1.4, 30, shade(A, -0.15), shade(A, -0.45), shade(A, -0.55)); const p = toScreen(gx + 0.7, gy + 0.7);
      ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 10 * z; for (let i = 1; i <= 3; i++) { ctx.globalAlpha = 0.7 - i * 0.18 + Math.sin(t * 3) * 0.12; ctx.beginPath(); ctx.arc(p.x, p.y - 34 * z, i * 7 * z, Math.PI, 0); ctx.stroke(); } ctx.globalAlpha = 1; ctx.shadowBlur = 0; break; }
    case 'board': { isoBox(gx, gy, 2.0, 0.4, 26, shade(r.K.floor, 0.1), shade(r.K.floor, -0.2), shade(r.K.floor, -0.3)); const top = toScreen(gx, gy);
      ctx.fillStyle = 'rgba(8,12,24,.85)'; ctx.fillRect(top.x - 4 * z, top.y - 24 * z, 40 * z, 18 * z); ctx.strokeStyle = A; ctx.strokeRect(top.x - 4 * z, top.y - 24 * z, 40 * z, 18 * z);
      ctx.fillStyle = '#fbbf24'; for (let i = 0; i < 3; i++) ctx.fillRect(top.x - 1 * z + i * 13 * z, top.y - 21 * z, 9 * z, 12 * z); break; }
    case 'crystal': { const p = toScreen(gx, gy); const yy = p.y - (18 + Math.sin(t * 2) * 3) * z; ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 16 * z;
      ctx.beginPath(); ctx.moveTo(p.x, yy - 12 * z); ctx.lineTo(p.x + 7 * z, yy); ctx.lineTo(p.x, yy + 12 * z); ctx.lineTo(p.x - 7 * z, yy); ctx.closePath(); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'mat': { const p = toScreen(gx, gy); ctx.fillStyle = shade(A, -0.3); ctx.beginPath(); ctx.ellipse(p.x, p.y, 11 * z, 5.5 * z, 0, 0, 6.28); ctx.fill();
      ctx.globalAlpha = 0.4 + Math.sin(t * 2 + gx) * 0.2; ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 8 * z; ctx.beginPath(); ctx.ellipse(p.x, p.y, 13 * z, 6.5 * z, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'conduit': { const a = toScreen(gx, gy), b = toScreen(r.gx + it.to[0], r.gy + it.to[1]); ctx.strokeStyle = A; ctx.globalAlpha = 0.5; ctx.lineWidth = 2 * z; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      const k = (t * 0.4) % 1; ctx.globalAlpha = on ? 0.95 : 0.4; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k, 2.4 * z, 0, 6.28); ctx.fill(); ctx.globalAlpha = 1; break; }
    case 'banner': { const top = toScreen(gx, gy); ctx.fillStyle = A; ctx.fillRect(top.x - 2 * z, top.y - 30 * z, 30 * z, 5 * z);
      ctx.beginPath(); ctx.moveTo(top.x, top.y - 25 * z); ctx.lineTo(top.x + 26 * z, top.y - 25 * z); ctx.lineTo(top.x + 20 * z, top.y - 10 * z); ctx.lineTo(top.x + 6 * z, top.y - 10 * z); ctx.closePath(); ctx.fill(); break; }
    case 'rug': { const p = toScreen(gx, gy); ctx.fillStyle = shade(A, -0.45); ctx.globalAlpha = .5; ctx.beginPath(); ctx.ellipse(p.x, p.y, 26 * z, 13 * z, 0, 0, 6.28); ctx.fill(); ctx.globalAlpha = 1; break; }
    case 'throne': { isoBox(gx, gy, 1.4, 1.0, 12, shade(A, -0.1), shade(A, -0.4), shade(A, -0.5)); const top = toScreen(gx, gy);
      ctx.fillStyle = shade(A, -0.15); ctx.fillRect(top.x - 3 * z, top.y - 34 * z, 18 * z, 24 * z); ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 14 * z;
      ctx.beginPath(); ctx.arc(top.x + 6 * z, top.y - 38 * z, 5 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'brazier': { const p = toScreen(gx, gy); isoBox(gx, gy, 0.4, 0.4, 12, shade(A, -0.3), shade(A, -0.5), shade(A, -0.6));
      const fy = p.y - (14 + Math.sin(t * 5 + gx) * 3) * z; ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 14 * z; ctx.beginPath(); ctx.ellipse(p.x, fy, 4 * z, 8 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'datawall': { holoScreen(gx, gy, 54, 34, 22, A, it.content, t, on);
      const p = toScreen(gx, gy); ctx.fillStyle = A; ctx.globalAlpha = 0.6; ctx.font = `${6 * z}px system-ui`; ctx.fillText('●', p.x - 25 * z, p.y - 52 * z); ctx.globalAlpha = 1; break; }
    case 'ticker': { const a = toScreen(gx, gy), b = toScreen(gx + (r.w - 0.8), gy), w = b.x - a.x;
      ctx.save(); ctx.fillStyle = 'rgba(6,12,20,.8)'; ctx.fillRect(a.x, a.y - 7 * z, w, 9 * z); ctx.beginPath(); ctx.rect(a.x, a.y - 7 * z, w, 9 * z); ctx.clip();
      ctx.font = `${6.5 * z}px system-ui`; const syms = ['NVDA +2.4%', 'META ▲', 'AMD +1.1%', 'TSLA ▼', 'BTC +0.8%', 'SPY ▲'], off = (t * 40 * z) % (w + 60 * z);
      for (let i = 0; i < 8; i++) { const x = a.x + w - off + i * 60 * z; const s = syms[i % syms.length]; ctx.fillStyle = s.includes('▼') ? '#fb5e7e' : '#34d399'; ctx.fillText(s, x, a.y - 0.5 * z); } ctx.restore(); break; }
    case 'mist': { const p = toScreen(gx, gy); for (let i = 0; i < 3; i++) { const ph = (t * 0.4 + i * 0.5) % 1; ctx.globalAlpha = (1 - ph) * 0.16; ctx.fillStyle = A;
      ctx.beginPath(); ctx.ellipse(p.x, p.y - ph * 28 * z, (6 + ph * 8) * z, (3 + ph * 4) * z, 0, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1; break; }
    case 'dais': { isoBox(gx, gy, 2.8, 1.9, 6, shade(A, -0.28), shade(A, -0.5), shade(A, -0.6)); isoBox(gx + 0.55, gy + 0.45, 1.7, 1.0, 12, shade(A, -0.14), shade(A, -0.4), shade(A, -0.5));
      const p = toScreen(gx + 1.4, gy + 0.95); ctx.strokeStyle = A; ctx.globalAlpha = 0.4 + Math.sin(t * 2) * 0.15; ctx.shadowColor = A; ctx.shadowBlur = 10 * z; ctx.lineWidth = 1.4 * z;
      ctx.beginPath(); ctx.ellipse(p.x, p.y - 18 * z, 15 * z, 7.5 * z, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'statue': { const p = toScreen(gx, gy), baseY = p.y - 18 * z, Hh = 32 * z;
      ctx.fillStyle = '#3a3f5e'; ctx.beginPath(); ctx.moveTo(p.x, baseY - Hh); ctx.lineTo(p.x + 7 * z, baseY); ctx.quadraticCurveTo(p.x, baseY + 3 * z, p.x - 7 * z, baseY); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#474d70'; ctx.beginPath(); ctx.ellipse(p.x, baseY - Hh + 4 * z, 4.6 * z, 2.4 * z, 0, 0, 6.28); ctx.fill();
      ctx.fillStyle = '#525984'; ctx.beginPath(); ctx.arc(p.x, baseY - Hh - 2 * z, 4.8 * z, 0, 6.28); ctx.fill();
      ctx.globalAlpha = 0.28 + Math.sin(t * 1.4) * 0.12; ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 16 * z; ctx.lineWidth = 1.6 * z;
      ctx.beginPath(); ctx.ellipse(p.x, baseY - Hh * 0.55, 13 * z, 16 * z, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'medcircle': { const p = toScreen(gx, gy); ctx.strokeStyle = A; ctx.globalAlpha = 0.5 + Math.sin(t * 2) * 0.2; ctx.shadowColor = A; ctx.shadowBlur = 9 * z; ctx.lineWidth = 1.6 * z;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, 16 * z, 8 * z, 0, 0, 6.28); ctx.stroke(); ctx.beginPath(); ctx.ellipse(p.x, p.y, 10 * z, 5 * z, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'dummy': { const p = toScreen(gx, gy); ctx.strokeStyle = '#b9925a'; ctx.lineCap = 'round'; ctx.lineWidth = 2.6 * z;
      ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x, p.y - 16 * z); ctx.stroke(); ctx.beginPath(); ctx.moveTo(p.x - 6 * z, p.y - 11 * z); ctx.lineTo(p.x + 6 * z, p.y - 11 * z); ctx.stroke();
      ctx.lineCap = 'butt'; ctx.fillStyle = '#c9a06a'; ctx.beginPath(); ctx.arc(p.x, p.y - 18 * z, 3 * z, 0, 6.28); ctx.fill(); break; }
    case 'plant': { const p = toScreen(gx, gy); isoBox(gx, gy, 0.42, 0.42, 5, '#3a2f22', '#2a2118', '#22190f'); ctx.fillStyle = '#2f6f4a'; ctx.shadowColor = '#34d399'; ctx.shadowBlur = 6 * z;
      for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.ellipse(p.x + (i - 1) * 3 * z, p.y - (8 + (i % 2) * 3) * z, 3.2 * z, 5 * z, 0, 0, 6.28); ctx.fill(); } ctx.shadowBlur = 0; break; }
    case 'stall': { const p = toScreen(gx, gy); isoBox(gx - 0.5, gy - 0.35, 1.0, 0.5, 6, '#5a3f2a', '#3f2c1c', '#33231a');
      ctx.fillStyle = (Math.round(it.gy) % 2) ? '#b9503c' : '#3f7a52'; ctx.beginPath(); ctx.moveTo(p.x - 11 * z, p.y - 17 * z); ctx.lineTo(p.x + 11 * z, p.y - 17 * z); ctx.lineTo(p.x + 8 * z, p.y - 11 * z); ctx.lineTo(p.x - 8 * z, p.y - 11 * z); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#3a2a1a'; ctx.lineWidth = 1.6 * z; ctx.beginPath(); ctx.moveTo(p.x - 8 * z, p.y - 11 * z); ctx.lineTo(p.x - 8 * z, p.y - 1 * z); ctx.moveTo(p.x + 8 * z, p.y - 11 * z); ctx.lineTo(p.x + 8 * z, p.y - 1 * z); ctx.stroke();
      ctx.fillStyle = '#caa24a'; for (let i = 0; i < 3; i++) ctx.fillRect(p.x - 5 * z + i * 4 * z, p.y - 8 * z, 2.4 * z, 2.4 * z); break; }
    case 'crate': { isoBox(gx - 0.35, gy - 0.35, 0.7, 0.7, 7, '#6b4f2e', '#4a3620', '#3a2a18'); isoBox(gx - 0.18, gy - 0.18, 0.42, 0.42, 12, '#735634', '#4a3620', '#3a2a18'); break; }
    case 'cart': { const p = toScreen(gx, gy); isoBox(gx - 0.75, gy - 0.45, 1.5, 0.9, 8, '#4a3826', '#33271a', '#281f14');
      ctx.fillStyle = '#241a12'; ctx.beginPath(); ctx.arc(p.x - 8 * z, p.y, 3.2 * z, 0, 6.28); ctx.arc(p.x + 8 * z, p.y, 3.2 * z, 0, 6.28); ctx.fill();
      ctx.fillStyle = '#5a4632'; ctx.beginPath(); ctx.arc(p.x - 8 * z, p.y, 1.2 * z, 0, 6.28); ctx.arc(p.x + 8 * z, p.y, 1.2 * z, 0, 6.28); ctx.fill();
      isoBox(gx - 0.4, gy - 0.3, 0.8, 0.55, 14, '#6b4f2e', '#4a3620', '#3a2a18'); break; }
    case 'bench': { isoBox(gx - 0.55, gy - 0.18, 1.1, 0.36, 4, '#4a3826', '#33271a', '#281f14'); break; }
    case 'pillar': { const p = toScreen(gx, gy); isoBox(gx - 0.25, gy - 0.25, 0.5, 0.5, 30, shade(r.K.wall, 0.06), shade(r.K.wall, -0.24), shade(r.K.wall, -0.34));
      ctx.fillStyle = A; ctx.globalAlpha = 0.45 + Math.sin(t * 2 + gx) * 0.22; ctx.shadowColor = A; ctx.shadowBlur = 10 * z; ctx.fillRect(p.x - 1.3 * z, p.y - 30 * z, 2.6 * z, 30 * z);
      ctx.beginPath(); ctx.arc(p.x, p.y - 31 * z, 2.4 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'tree': { const p = toScreen(gx, gy); ctx.strokeStyle = '#5a4430'; ctx.lineWidth = 3.4 * z; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x, p.y - 20 * z); ctx.stroke();
      ctx.fillStyle = '#2f6f4a'; ctx.shadowColor = '#34d399'; ctx.shadowBlur = 13 * z; ctx.beginPath(); ctx.ellipse(p.x, p.y - 27 * z, 12 * z, 10 * z, 0, 0, 6.28); ctx.fill();
      ctx.beginPath(); ctx.ellipse(p.x - 8 * z, p.y - 20 * z, 6 * z, 5 * z, 0, 0, 6.28); ctx.fill(); ctx.beginPath(); ctx.ellipse(p.x + 8 * z, p.y - 21 * z, 6 * z, 5 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
      for (let i = 0; i < 3; i++) { const ph = (t * 0.3 + i * 0.33) % 1; ctx.globalAlpha = 0.5 * (1 - ph); ctx.fillStyle = '#9be8c2'; ctx.beginPath(); ctx.arc(p.x + (i - 1) * 7 * z, p.y - 26 * z + ph * 24 * z, 1.3 * z, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1; break; }
    case 'circle': { const p = toScreen(gx, gy); ctx.strokeStyle = 'rgba(184,172,140,.35)'; ctx.lineWidth = 1.6 * z; ctx.beginPath(); ctx.ellipse(p.x, p.y, TW2 * z, TH2 * z, 0, 0, 6.28); ctx.stroke();
      ctx.strokeStyle = 'rgba(184,172,140,.2)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 0.55 * TW2 * z, 0.55 * TH2 * z, 0, 0, 6.28); ctx.stroke(); break; }
    case 'pavilion': { const z2 = z; isoBox(gx, gy, 2, 1.6, 2, shade(r.K.floor, 0.12), shade(r.K.floor, -0.1), shade(r.K.floor, -0.22));
      [[gx + 0.12, gy + 0.12], [gx + 1.88, gy + 0.12], [gx + 1.88, gy + 1.48], [gx + 0.12, gy + 1.48]].forEach(([cx, cy]) => isoBox(cx - 0.06, cy - 0.06, 0.12, 0.12, 20, shade(r.K.wall, 0.05), shade(r.K.wall, -0.2), shade(r.K.wall, -0.3)));
      const c = toScreen(gx + 1, gy + 0.8), roofY = c.y - 22 * z2, ww = 2.6 * TW2 * z2;
      ctx.fillStyle = shade(r.K.accent, -0.55); ctx.beginPath(); ctx.moveTo(c.x - ww / 2, roofY); ctx.quadraticCurveTo(c.x - ww / 2 - 6 * z2, roofY - 3 * z2, c.x - ww * 0.32, roofY - 3 * z2); ctx.lineTo(c.x, roofY - 13 * z2); ctx.lineTo(c.x + ww * 0.32, roofY - 3 * z2); ctx.quadraticCurveTo(c.x + ww / 2 + 6 * z2, roofY - 3 * z2, c.x + ww / 2, roofY); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = r.K.accent; ctx.globalAlpha = 0.5; ctx.lineWidth = 1.2 * z2; ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillStyle = r.K.accent; ctx.shadowColor = r.K.accent; ctx.shadowBlur = 6 * z2; ctx.beginPath(); ctx.arc(c.x, roofY - 13 * z2, 2 * z2, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'lanternpost': { const p = toScreen(gx, gy); ctx.fillStyle = '#565049'; ctx.fillRect(p.x - 1.4 * z, p.y - 13 * z, 2.8 * z, 13 * z);
      ctx.fillStyle = '#6a645c'; ctx.fillRect(p.x - 3 * z, p.y - 18 * z, 6 * z, 5 * z); ctx.beginPath(); ctx.moveTo(p.x - 4 * z, p.y - 18 * z); ctx.lineTo(p.x + 4 * z, p.y - 18 * z); ctx.lineTo(p.x, p.y - 22 * z); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#ffce6a'; ctx.shadowColor = '#ffce6a'; ctx.shadowBlur = 9 * z; ctx.fillRect(p.x - 1.6 * z, p.y - 17 * z, 3.2 * z, 3.4 * z); ctx.shadowBlur = 0; break; }
  }
  ctx.globalAlpha = 1; ctx.shadowBlur = 0;
}

/* ====================================================================== *
 *  Per-district floor terrain — the handcrafted diorama beneath each hall
 * ====================================================================== */
function clipFloor(r) { const A = toScreen(r.gx, r.gy), B = toScreen(r.gx + r.w, r.gy), C = toScreen(r.gx + r.w, r.gy + r.h), D = toScreen(r.gx, r.gy + r.h);
  ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(C.x, C.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.clip(); }
function pond(gx, gy, rT, t) { const z = cam.zoom, c = toScreen(gx, gy), rx = rT * TW2 * z, ry = rT * TH2 * z;
  const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, rx); g.addColorStop(0, '#1d4066'); g.addColorStop(.7, '#13293f'); g.addColorStop(1, '#0d1c2e');
  ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(c.x, c.y, rx, ry, 0, 0, 6.28); ctx.fill();
  ctx.strokeStyle = 'rgba(120,200,255,.35)'; ctx.lineWidth = 1 * z;
  for (let i = 0; i < 3; i++) { const ph = (t * 0.3 + i * 0.34) % 1; ctx.globalAlpha = 0.4 * (1 - ph); ctx.beginPath(); ctx.ellipse(c.x, c.y, rx * ph, ry * ph, 0, 0, 6.28); ctx.stroke(); }
  ctx.globalAlpha = 1; ctx.fillStyle = '#2f6f4a'; ctx.beginPath(); ctx.ellipse(c.x - rx * 0.45, c.y, 3 * z, 1.5 * z, 0, 0, 6.28); ctx.fill(); }
function grassBlade(gx, gy) { const z = cam.zoom, p = toScreen(gx, gy); ctx.strokeStyle = 'rgba(70,150,95,.5)'; ctx.lineWidth = 1 * z;
  ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - 1 * z, p.y - 3 * z); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + 1.5 * z, p.y - 3.5 * z); ctx.stroke(); }
function stonePath(r) { const z = cam.zoom, a = toScreen(r.gx + 0.5, r.gy + r.h - 0.5), b = toScreen(r.gx + r.w - 0.5, r.gy + 0.5);
  ctx.strokeStyle = 'rgba(150,150,170,.16)'; ctx.lineCap = 'round'; ctx.lineWidth = 7 * z; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); ctx.lineCap = 'butt'; }
function formationRing(r, t) { const z = cam.zoom, c = toScreen(r.cx, r.cyc); ctx.strokeStyle = r.K.accent; ctx.shadowColor = r.K.accent; ctx.shadowBlur = 6 * z;
  for (let i = 1; i <= 3; i++) { ctx.globalAlpha = 0.3; ctx.lineWidth = 1.4 * z; ctx.beginPath(); ctx.ellipse(c.x, c.y, i * TW2 * z, i * TH2 * z, 0, 0, 6.28); ctx.stroke(); }
  for (let i = 0; i < 10; i++) { const a = t * 0.4 + i * 0.628; ctx.globalAlpha = 0.5; ctx.fillStyle = r.K.accent; ctx.fillRect(c.x + Math.cos(a) * 2.6 * TW2 * z - z, c.y + Math.sin(a) * 2.6 * TH2 * z - z, 2 * z, 2 * z); }
  ctx.shadowBlur = 0; ctx.globalAlpha = 1; }
function hexArray(r, t) { const z = cam.zoom, c = toScreen(r.cx, r.cyc);
  const hex = (s) => { ctx.beginPath(); for (let k = 0; k < 6; k++) { const a = k * 1.047 + 0.5, x = c.x + Math.cos(a) * s * TW2 * z, y = c.y + Math.sin(a) * s * TH2 * z; ctx[k ? 'lineTo' : 'moveTo'](x, y); } ctx.closePath(); ctx.stroke(); };
  ctx.strokeStyle = r.K.accent; ctx.globalAlpha = 0.3; ctx.lineWidth = 1.2 * z; hex(2.4); hex(1.5);
  for (let k = 0; k < 6; k++) { const a = k * 1.047 + 0.5, ph = (t * 0.5 + k * 0.16) % 1; ctx.globalAlpha = 0.6 * (1 - ph); ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(c.x + Math.cos(a) * 2.4 * TW2 * z * ph, c.y + Math.sin(a) * 2.4 * TH2 * z * ph); ctx.stroke(); }
  ctx.globalAlpha = 1; }
function starMap(r, t) { const z = cam.zoom, pts = r.spots.slice(0, 9).map((s) => toScreen(r.gx + s.x, r.gy + s.y));
  ctx.strokeStyle = 'rgba(120,150,255,.22)'; ctx.lineWidth = 1 * z; ctx.beginPath(); pts.forEach((p, i) => ctx[i ? 'lineTo' : 'moveTo'](p.x, p.y)); ctx.stroke();
  pts.forEach((p, i) => { ctx.globalAlpha = 0.5 + Math.sin(t * 2 + i) * 0.3; ctx.fillStyle = '#cbd6ff'; ctx.beginPath(); ctx.arc(p.x, p.y, 1.4 * z, 0, 6.28); ctx.fill(); }); ctx.globalAlpha = 1; }
function scorch(gx, gy, rT) { const z = cam.zoom, c = toScreen(gx, gy); ctx.fillStyle = 'rgba(16,8,6,.4)'; ctx.beginPath(); ctx.ellipse(c.x, c.y, rT * TW2 * z, rT * TH2 * z, 0, 0, 6.28); ctx.fill(); }
function emberFloor(r, t) { const z = cam.zoom; r.spots.slice(0, 5).forEach((s, i) => { const p = toScreen(r.gx + s.x, r.gy + s.y); ctx.globalAlpha = 0.4 + Math.sin(t * 3 + i) * 0.3; ctx.fillStyle = '#ff8c1a'; ctx.shadowColor = '#ff8c1a'; ctx.shadowBlur = 6 * z; ctx.beginPath(); ctx.arc(p.x, p.y, 1.4 * z, 0, 6.28); ctx.fill(); }); ctx.shadowBlur = 0; ctx.globalAlpha = 1; }
function rug(r) { const z = cam.zoom, A = toScreen(r.cx - 1.6, r.cyc - 1), B = toScreen(r.cx + 1.6, r.cyc - 1), C = toScreen(r.cx + 1.6, r.cyc + 1.4), D = toScreen(r.cx - 1.6, r.cyc + 1.4);
  ctx.fillStyle = shade(r.K.accent, -0.55); ctx.globalAlpha = 0.5; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(C.x, C.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = r.K.accent; ctx.globalAlpha = 0.4; ctx.lineWidth = 1 * z; ctx.stroke(); ctx.globalAlpha = 1; }
function scrollDot(gx, gy) { const z = cam.zoom, p = toScreen(gx, gy); ctx.fillStyle = '#efe6c8'; ctx.fillRect(p.x - 2 * z, p.y - 1.4 * z, 4 * z, 2.8 * z); }
function goldInlay(r, t) { const z = cam.zoom, c = toScreen(r.cx, r.cyc); ctx.strokeStyle = 'rgba(245,197,66,.28)'; ctx.lineWidth = 1.4 * z;
  for (let i = 0; i < 6; i++) { const a = i * 1.047; ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(c.x + Math.cos(a) * 2.6 * TW2 * z, c.y + Math.sin(a) * 2.6 * TH2 * z); ctx.stroke(); }
  ctx.globalAlpha = 0.4; ctx.beginPath(); ctx.ellipse(c.x, c.y, 1.6 * TW2 * z, 1.6 * TH2 * z, 0, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1; }
function ceremonial(r) { const z = cam.zoom, A = toScreen(r.cx - 1, r.gy + 0.6), B = toScreen(r.cx + 1, r.gy + 0.6), C = toScreen(r.cx + 1, r.gy + r.h - 0.6), D = toScreen(r.cx - 1, r.gy + r.h - 0.6);
  ctx.fillStyle = shade(r.K.accent, -0.5); ctx.globalAlpha = 0.45; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(C.x, C.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1; }
function sectEmblem(r, t) { const z = cam.zoom, c = toScreen(r.cx, r.cyc); ctx.save(); ctx.strokeStyle = r.K.accent; ctx.globalAlpha = 0.28; ctx.lineWidth = 1.6 * z;
  ctx.beginPath(); ctx.ellipse(c.x, c.y, 2.6 * TW2 * z, 2.6 * TH2 * z, 0, 0, 6.28); ctx.stroke(); ctx.beginPath(); ctx.ellipse(c.x, c.y, 1.8 * TW2 * z, 1.8 * TH2 * z, 0, 0, 6.28); ctx.stroke();
  ctx.translate(c.x, c.y); ctx.scale(1, TH2 / TW2); ctx.rotate(t * 0.12); ctx.fillStyle = r.K.accent; ctx.globalAlpha = 0.3;
  for (let i = 0; i < 8; i++) { ctx.rotate(0.785); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(6 * z, 10 * z); ctx.lineTo(-6 * z, 10 * z); ctx.closePath(); ctx.fill(); } ctx.restore(); ctx.globalAlpha = 1; }
function drawDistrictGround(r) {
  const z = cam.zoom;
  const c = toScreen(r.cx, r.cyc + 0.4);              // central courtyard pad
  ctx.fillStyle = 'rgba(190,188,205,.05)'; ctx.beginPath(); ctx.ellipse(c.x, c.y, 2.5 * TW2 * z, 2.5 * TH2 * z, 0, 0, 6.28); ctx.fill();
  ctx.strokeStyle = 'rgba(150,150,172,.14)'; ctx.lineCap = 'round'; ctx.lineWidth = 8 * z;
  const a = toScreen(r.cx, r.gy + r.h - 0.4), b = toScreen(r.cx, r.gy + 1.2);   // spine path front->back
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  const e = toScreen(r.gx + 1, r.cyc + 0.4), g = toScreen(r.gx + r.w - 1, r.cyc + 0.4);   // cross path
  ctx.beginPath(); ctx.moveTo(e.x, e.y); ctx.lineTo(g.x, g.y); ctx.stroke(); ctx.lineCap = 'butt';
}
function drawTerrainDressing(r, t) {     // caller has already clipped to the terrace outline
  switch (r.landmark) {
    case 'vortex': pond(r.gx + 1.5, r.gy + 1.3, 1.0, t); stonePath(r); r.spots.slice(0, 9).forEach((s) => grassBlade(r.gx + s.x, r.gy + s.y)); break;
    case 'gate': formationRing(r, t); break;
    case 'nexus': hexArray(r, t); break;
    case 'observatory': starMap(r, t); break;
    case 'forge': r.spots.slice(0, 5).forEach((s) => scorch(r.gx + s.x, r.gy + s.y, 0.4 + s.r * 0.3)); emberFloor(r, t); break;
    case 'tome': rug(r); r.spots.slice(0, 7).forEach((s) => scrollDot(r.gx + s.x, r.gy + s.y)); break;
    case 'fountain': case 'prosperity': goldInlay(r, t); break;
    case 'bell': ceremonial(r); break;
    case 'monument': default: sectEmblem(r, t); r.spots.slice(0, 6).forEach((s) => grassBlade(r.gx + s.x, r.gy + s.y)); break;
  }
}

/* ====================================================================== *
 *  Landmarks — one unforgettable structure per district
 * ====================================================================== */
function disc(gx, gy, rT, hpx, topc, sidec) {
  const z = cam.zoom, c = toScreen(gx, gy), rx = rT * TW2 * z, ry = rT * TH2 * z, h = hpx * z;
  ctx.fillStyle = sidec; ctx.fillRect(c.x - rx, c.y - h, rx * 2, h);
  ctx.beginPath(); ctx.ellipse(c.x, c.y, rx, ry, 0, 0, 6.28); ctx.fill();
  ctx.fillStyle = topc; ctx.beginPath(); ctx.ellipse(c.x, c.y - h, rx, ry, 0, 0, 6.28); ctx.fill();
  return { c, rx, ry, h };
}
function landmarkGlow(r, color) { const c = toScreen(r.cx, r.cyc), z = cam.zoom, g = ctx.createRadialGradient(c.x, c.y - 14 * z, 0, c.x, c.y - 14 * z, 80 * z);
  g.addColorStop(0, color); g.addColorStop(1, 'transparent'); ctx.globalAlpha = 0.16; ctx.fillStyle = g; ctx.fillRect(c.x - 90 * z, c.y - 100 * z, 180 * z, 180 * z); ctx.globalAlpha = 1; }
function drawLandmark(r, t, busy) {
  const z = cam.zoom, A = r.K.accent, c = toScreen(r.cx, r.cyc);
  switch (r.landmark) {
    case 'fountain': {            // Wealth Fountain — golden tiers, coins arcing on jets of qi
      landmarkGlow(r, '#f5c542'); disc(r.cx, r.cyc, 1.7, 5, '#caa24a', '#7c5f28'); disc(r.cx, r.cyc, 1.05, 11, shade('#caa24a', 0.12), '#7c5f28');
      const top = disc(r.cx, r.cyc, 0.5, 17, shade('#caa24a', 0.22), '#7c5f28'), cy = top.c.y - 17 * z;
      ctx.fillStyle = 'rgba(120,200,255,.55)'; ctx.beginPath(); ctx.ellipse(top.c.x, cy, top.rx, top.ry, 0, 0, 6.28); ctx.fill();
      for (let i = 0; i < 12; i++) { const ph = (t * 0.9 + i * 0.55) % 1, ang = i * 0.9, rr = ph * 2.4 * TW2 * z;
        ctx.globalAlpha = 1 - ph * 0.6; ctx.fillStyle = '#ffdf6e'; ctx.shadowColor = '#f5c542'; ctx.shadowBlur = 6 * z;
        ctx.beginPath(); ctx.arc(top.c.x + Math.cos(ang) * rr, cy - Math.sin(ph * Math.PI) * 34 * z, 1.9 * z, 0, 6.28); ctx.fill(); }
      ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
    case 'observatory': {         // Celestial Observatory — armillary rings + a caught star
      landmarkGlow(r, A); disc(r.cx, r.cyc, 1.6, 8, '#22304e', '#121a2e'); const cy = c.y - 8 * z;
      ctx.fillStyle = '#2a3a5e'; ctx.beginPath(); ctx.ellipse(c.x, cy, 1.45 * TW2 * z, 15 * z, 0, Math.PI, 0, true); ctx.fill();
      ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 10 * z; ctx.lineWidth = 1.6 * z;
      for (let i = 0; i < 3; i++) { const a = t * 0.7 + i * 2.1; ctx.globalAlpha = 0.75; ctx.beginPath(); ctx.ellipse(c.x, cy - 20 * z, 15 * z, (4 + Math.abs(Math.sin(a)) * 10) * z, 0, 0, 6.28); ctx.stroke(); }
      ctx.shadowBlur = 0; ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.shadowColor = '#cbd6ff'; ctx.shadowBlur = 14 * z; ctx.beginPath(); ctx.arc(c.x, cy - 20 * z, 3 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'forge': {               // Great Forge — molten core, anvil, flying sparks
      landmarkGlow(r, '#ff8c1a'); disc(r.cx, r.cyc, 1.4, 7, '#2a2230', '#16121a'); const cy = c.y - 7 * z, pulse = 0.6 + Math.sin(t * 4) * 0.4;
      ctx.fillStyle = 'rgba(255,150,40,.8)'; ctx.shadowColor = '#ff8c1a'; ctx.shadowBlur = (14 + pulse * 16) * z; ctx.beginPath(); ctx.ellipse(c.x, cy - 6 * z, 7 * z, 3.6 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
      ctx.fillStyle = '#3a3f55'; ctx.fillRect(c.x - 7 * z, cy - 13 * z, 14 * z, 4 * z); ctx.fillRect(c.x - 2 * z, cy - 13 * z, 4 * z, 9 * z);
      for (let i = 0; i < 9; i++) { const ph = (t * 1.6 + i * 0.4) % 1; ctx.globalAlpha = 1 - ph; ctx.fillStyle = '#ffd27a'; ctx.beginPath(); ctx.arc(c.x + (i - 4) * 2.4 * z * (0.4 + ph), cy - 13 * z - ph * 24 * z, 1.5 * z, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1; break; }
    case 'tome': {                // Tome of Ten Thousand Texts — a great floating book
      landmarkGlow(r, A); disc(r.cx, r.cyc, 1.0, 9, '#2a2356', '#181238'); const cy = c.y - 9 * z - (15 + Math.sin(t * 1.5) * 3) * z;
      ctx.fillStyle = '#efe6c8'; ctx.beginPath(); ctx.moveTo(c.x, cy); ctx.lineTo(c.x - 13 * z, cy - 4 * z); ctx.lineTo(c.x - 13 * z, cy + 7 * z); ctx.lineTo(c.x, cy + 9 * z); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(c.x, cy); ctx.lineTo(c.x + 13 * z, cy - 4 * z); ctx.lineTo(c.x + 13 * z, cy + 7 * z); ctx.lineTo(c.x, cy + 9 * z); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = A; ctx.lineWidth = 1 * z; ctx.stroke();
      for (let i = 0; i < 5; i++) { const ph = (t * 0.6 + i * 0.4) % 1; ctx.globalAlpha = 1 - ph; ctx.fillStyle = A; ctx.font = `${7 * z}px system-ui`; ctx.fillText('✶', c.x + (i - 2) * 6 * z, cy - ph * 28 * z); } ctx.globalAlpha = 1; break; }
    case 'gate': {                // Thousand-Path Gate — a great paifang with an energy portal
      landmarkGlow(r, A); const pw = 13 * z, ph2 = 36 * z;
      ctx.globalAlpha = 0.32 + Math.sin(t * 2) * 0.12; const pg = ctx.createLinearGradient(0, c.y - ph2, 0, c.y); pg.addColorStop(0, A); pg.addColorStop(1, 'transparent');
      ctx.fillStyle = pg; ctx.fillRect(c.x - pw, c.y - ph2 + 5 * z, pw * 2, ph2 - 5 * z); ctx.globalAlpha = 1;
      ctx.fillStyle = '#243a4a'; ctx.fillRect(c.x - pw - 3 * z, c.y - ph2, 6 * z, ph2); ctx.fillRect(c.x + pw - 3 * z, c.y - ph2, 6 * z, ph2);
      ctx.fillStyle = shade(A, -0.5);
      const lintel = (yy, hh) => { ctx.beginPath(); ctx.moveTo(c.x - pw - 8 * z, yy); ctx.quadraticCurveTo(c.x, yy - hh, c.x + pw + 8 * z, yy); ctx.lineTo(c.x + pw + 8 * z, yy + 4 * z); ctx.quadraticCurveTo(c.x, yy - hh + 4 * z, c.x - pw - 8 * z, yy + 4 * z); ctx.closePath(); ctx.fill(); };
      lintel(c.y - ph2, 9 * z); lintel(c.y - ph2 - 11 * z, 7 * z);
      ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 8 * z; ctx.lineWidth = 1.4 * z; ctx.strokeRect(c.x - pw - 3 * z, c.y - ph2, 6 * z, ph2); ctx.strokeRect(c.x + pw - 3 * z, c.y - ph2, 6 * z, ph2); ctx.shadowBlur = 0; break; }
    case 'bell': {                // Heavenly Bell — a great suspended bell tolling rings
      landmarkGlow(r, A); ctx.strokeStyle = '#5a4632'; ctx.lineWidth = 3 * z; ctx.beginPath(); ctx.moveTo(c.x - 13 * z, c.y); ctx.lineTo(c.x - 9 * z, c.y - 28 * z); ctx.lineTo(c.x + 9 * z, c.y - 28 * z); ctx.lineTo(c.x + 13 * z, c.y); ctx.stroke();
      const sway = Math.sin(t * 1.2) * 3 * z; ctx.save(); ctx.translate(c.x + sway, c.y - 28 * z);
      ctx.fillStyle = shade(A, -0.3); ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 9 * z; ctx.lineWidth = 1.4 * z;
      ctx.beginPath(); ctx.moveTo(-8 * z, 19 * z); ctx.quadraticCurveTo(-9 * z, 2 * z, 0, 0); ctx.quadraticCurveTo(9 * z, 2 * z, 8 * z, 19 * z); ctx.quadraticCurveTo(0, 23 * z, -8 * z, 19 * z); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0; ctx.restore();
      for (let i = 0; i < 2; i++) { const ph = (t * 0.5 + i * 0.5) % 1; ctx.globalAlpha = 0.4 * (1 - ph); ctx.strokeStyle = A; ctx.lineWidth = 1.4 * z; ctx.beginPath(); ctx.ellipse(c.x, c.y - 9 * z, (10 + ph * 32) * z, (5 + ph * 16) * z, 0, 0, 6.28); ctx.stroke(); } ctx.globalAlpha = 1; break; }
    case 'nexus': {               // Spirit Crystal Nexus — a floating crystal cluster, arcing energy
      landmarkGlow(r, A); disc(r.cx, r.cyc, 1.2, 6, '#16203a', '#0a1226'); const cy = c.y - 6 * z;
      ctx.strokeStyle = A; ctx.globalAlpha = 0.5 + Math.sin(t * 3) * 0.2; ctx.shadowColor = A; ctx.shadowBlur = 8 * z; ctx.lineWidth = 1 * z;
      ctx.beginPath(); ctx.moveTo(c.x - 10 * z, cy - 14 * z); ctx.lineTo(c.x, cy - 28 * z); ctx.lineTo(c.x + 10 * z, cy - 16 * z); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
      [[0, -28, 6.5], [-10, -14, 4.5], [10, -16, 4.5], [-5, -6, 3.5], [6, -5, 3.5]].forEach(([gx, gy, s]) => { const x = c.x + gx * z, y = cy + gy * z;
        ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 12 * z; ctx.beginPath(); ctx.moveTo(x, y - s * z); ctx.lineTo(x + s * 0.7 * z, y); ctx.lineTo(x, y + s * z); ctx.lineTo(x - s * 0.7 * z, y); ctx.closePath(); ctx.fill(); }); ctx.shadowBlur = 0; break; }
    case 'vortex': {              // Qi Convergence — a rising spiral of spirit energy
      landmarkGlow(r, A); ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 9 * z;
      for (let i = 0; i < 26; i++) { const a = t * 2 + i * 0.5, rr = (1 - i / 26) * 15 * z, yy = c.y - (i / 26) * 34 * z; ctx.globalAlpha = 0.7 * (1 - i / 32);
        ctx.beginPath(); ctx.arc(c.x + Math.cos(a) * rr, yy, 1.5 * z, 0, 6.28); ctx.fill(); } ctx.shadowBlur = 0; ctx.globalAlpha = 1;
      ctx.strokeStyle = A; ctx.globalAlpha = 0.5; ctx.lineWidth = 1.6 * z; ctx.beginPath(); ctx.ellipse(c.x, c.y, 1.5 * TW2 * z, 1.5 * TH2 * z, 0, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1; break; }
    case 'prosperity': {          // Golden Prosperity Tree — coin-laden boughs
      landmarkGlow(r, '#f5c542'); disc(r.cx, r.cyc, 0.85, 6, '#3a2f18', '#241a0c'); const cy = c.y - 6 * z;
      ctx.strokeStyle = '#7a5a2a'; ctx.lineWidth = 3.4 * z; ctx.beginPath(); ctx.moveTo(c.x, cy); ctx.lineTo(c.x, cy - 19 * z); ctx.stroke();
      ctx.fillStyle = '#caa24a'; ctx.shadowColor = '#f5c542'; ctx.shadowBlur = 13 * z; ctx.beginPath(); ctx.ellipse(c.x, cy - 24 * z, 13 * z, 10 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
      for (let i = 0; i < 7; i++) { const a = i * 0.9 + Math.sin(t + i) * 0.1; ctx.fillStyle = '#ffdf6e'; ctx.beginPath(); ctx.arc(c.x + Math.cos(a) * 10 * z, cy - 24 * z + Math.sin(a) * 7 * z, 1.7 * z, 0, 6.28); ctx.fill(); } break; }
    case 'monument': default: {   // Ancestral Monument — a towering statue, haloed
      landmarkGlow(r, A); const baseY = c.y - 14 * z, H = 42 * z;
      ctx.fillStyle = '#3a3f5e'; ctx.beginPath(); ctx.moveTo(c.x, baseY - H); ctx.lineTo(c.x + 9 * z, baseY); ctx.quadraticCurveTo(c.x, baseY + 4 * z, c.x - 9 * z, baseY); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#474d70'; ctx.beginPath(); ctx.ellipse(c.x, baseY - H + 6 * z, 5 * z, 2.6 * z, 0, 0, 6.28); ctx.fill();
      ctx.fillStyle = '#525984'; ctx.beginPath(); ctx.arc(c.x, baseY - H - 3 * z, 5.6 * z, 0, 6.28); ctx.fill();
      ctx.strokeStyle = A; ctx.globalAlpha = 0.4 + Math.sin(t * 1.5) * 0.16; ctx.shadowColor = A; ctx.shadowBlur = 16 * z; ctx.lineWidth = 2 * z; ctx.beginPath(); ctx.arc(c.x, baseY - H - 3 * z, 10 * z, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; break; }
  }
}

/* rising work glyphs above busy rooms */
function drawWorkFX(r, t) {
  const occ = r.occupants.size; if (!occ) return; const z = cam.zoom, c = toScreen(r.cx, r.gy + 0.5), busy = Math.min(1, occ * 0.45), ev = (r.elev || 0) * z;
  for (let i = 0; i < 2 + occ; i++) { const ph = (t * (0.5 + busy) + i * 0.7) % 2; ctx.globalAlpha = Math.max(0, 0.5 - ph * 0.25);
    ctx.fillStyle = r.K.accent; ctx.font = `${(10 + busy * 3) * z}px system-ui`; ctx.fillText(r.K.fx, c.x + ((i % 3) - 1) * 16 * z, c.y - ev - 30 * z - ph * 24 * z); }
  ctx.globalAlpha = 1;
}

/* ---------------- disciples ---------------- */
function drawDisciple(d, t) {
  const p = toScreen(d.gx, d.gy), z = cam.zoom; p.y -= elevAt(d.gx, d.gy) * z;   // stand on the terrace
  const rs = ROLE_STYLE[d.role] || ROLE_STYLE.disciple, robe = rs.color;
  const hovd = hover.disc === d, sel = selected.disc === d, foll = followed === d, elder = d.role === 'elder';
  const sc = z * (elder ? 1.72 : 1.55) * (hovd || foll ? 1.12 : 1);
  const working = d.state === 'working';
  const meditating = d.state === 'meditate' || (d.state === 'idle' && d.idleAct === 'meditate');
  const training = d.state === 'idle' && d.idleAct === 'train';
  const fx = d.facing;
  ctx.globalAlpha = d.alpha;
  ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 6 * sc, 2.6 * sc, 0, 0, 6.28); ctx.fill();
  const bob = d.moving ? Math.abs(Math.sin(d.phase)) * 2.2 * sc
    : working ? Math.abs(Math.sin(t * 5 + d.phase)) * 0.9 * sc
    : training ? Math.abs(Math.sin(t * 6 + d.phase)) * 1.6 * sc
    : meditating ? 0 : Math.sin(t * 2 + d.phase) * 0.7 * sc;
  const fy = p.y - bob, bodyH = (meditating ? 11 : 15) * sc, headR = (elder ? 4 : 3.6) * sc, baseW = (meditating ? 6.5 : 5) * sc;
  const headY = fy - bodyH;
  // meditation qi ring
  if (meditating) { ctx.globalAlpha = d.alpha * (0.35 + Math.sin(t * 2 + d.phase) * 0.2); ctx.strokeStyle = '#a78bfa'; ctx.shadowColor = '#a78bfa'; ctx.shadowBlur = 8 * sc; ctx.lineWidth = 1.4 * sc;
    ctx.beginPath(); ctx.ellipse(p.x, fy, 9 * sc, 4.5 * sc, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = d.alpha; }
  // robe
  const grd = ctx.createLinearGradient(0, headY, 0, fy); grd.addColorStop(0, shade(robe, 0.2)); grd.addColorStop(1, shade(robe, -0.3));
  ctx.fillStyle = grd; ctx.strokeStyle = shade(robe, -0.55); ctx.lineWidth = 1 * sc;
  ctx.beginPath(); ctx.moveTo(p.x, headY + 1.5 * sc); ctx.lineTo(p.x + baseW, fy); ctx.quadraticCurveTo(p.x, fy + 1.8 * sc, p.x - baseW, fy); ctx.closePath(); ctx.fill(); ctx.stroke();
  // shoulder mantle
  ctx.fillStyle = shade(robe, 0.34); ctx.beginPath(); ctx.ellipse(p.x, headY + 4 * sc, 4.4 * sc, 2.1 * sc, 0, 0, 6.28); ctx.fill();
  // ---- arms / work poses ----
  ctx.strokeStyle = shade(robe, -0.1); ctx.lineWidth = 1.7 * sc; ctx.lineCap = 'round';
  const sh = headY + 5 * sc;                       // shoulder height
  if (working) {
    if (d.role === 'engineer' || d.role === 'architect') {       // typing
      const tap = Math.sin(t * 14 + d.phase) * 1.4 * sc;
      arm(p.x, sh, p.x + 5 * sc, fy - 3 * sc + tap); arm(p.x, sh, p.x + 4 * sc, fy - 4 * sc - tap);
    } else if (d.role === 'researcher') {                         // reading scroll held up
      arm(p.x, sh, p.x + 5 * sc * fx, sh + 1 * sc);
    } else {                                                       // trader/analyst pointing at screen
      const pt = Math.sin(t * 3 + d.phase) * 1.5 * sc;
      arm(p.x, sh, p.x + 6 * sc * fx, headY + 2 * sc + pt);
    }
  } else if (training) {                                          // sword form
    const sw = Math.sin(t * 6 + d.phase), hx = p.x + 6 * sc * sw, hy = sh - 4 * sc * Math.abs(sw);
    arm(p.x, sh, hx, hy); arm(p.x, sh, p.x - 5 * sc * sw, fy - 2 * sc);
    ctx.strokeStyle = 'rgba(205,214,255,.85)'; ctx.shadowColor = '#aab6ff'; ctx.shadowBlur = 5 * sc; ctx.lineWidth = 1.2 * sc;
    ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(hx + 8 * sc * sw, hy - 7 * sc); ctx.stroke(); ctx.shadowBlur = 0; ctx.strokeStyle = shade(robe, -0.1);
  } else if (meditating) {                                        // hands resting
    arm(p.x, sh, p.x + 3.5 * sc, fy - 1 * sc); arm(p.x, sh, p.x - 3.5 * sc, fy - 1 * sc);
  }
  ctx.lineCap = 'butt';
  // head + hood
  ctx.fillStyle = '#f2e2c8'; ctx.beginPath(); ctx.arc(p.x, headY, headR, 0, 6.28); ctx.fill();
  ctx.fillStyle = shade(robe, -0.06); ctx.beginPath(); ctx.arc(p.x, headY - 0.6 * sc, headR + 0.5 * sc, Math.PI, 0); ctx.fill();
  // ---- role insignia ----
  drawRoleProp(d, p.x, headY, fy, sh, sc, fx, robe, working, t, elder);
  // status pip
  const pip = { working: '#34d399', idle: rs.color, traveling: '#cbb9ff', roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' }[d.state] || rs.color;
  ctx.fillStyle = pip; if (working || meditating) { ctx.shadowColor = pip; ctx.shadowBlur = 7 * sc; }
  ctx.beginPath(); ctx.arc(p.x + 4.6 * sc, headY - 1.5 * sc, 1.7 * sc, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
  // chat bubble
  if (d.chat > 0) { ctx.font = `${9 * sc}px system-ui`; ctx.globalAlpha = d.alpha * (0.6 + Math.sin(t * 6) * 0.3); ctx.fillText('💬', p.x + 3 * sc, headY - 8 * sc); ctx.globalAlpha = d.alpha; }
  // work progress ring
  if (working && d.progress > 0.02) { ctx.strokeStyle = '#34d399'; ctx.lineWidth = 1.6 * sc; ctx.beginPath(); ctx.arc(p.x, headY, headR + 3 * sc, -1.57, -1.57 + d.progress * 6.28); ctx.stroke(); }
  // name plate
  if (hovd || foll || sel || cam.zoom > 0.62) {
    ctx.font = `600 ${9.5 * z}px system-ui`; ctx.textAlign = 'center';
    const w = ctx.measureText(d.name).width + 8 * z; ctx.fillStyle = 'rgba(8,10,20,.72)';
    roundRect(p.x - w / 2, headY - 16 * sc, w, 13 * z, 3 * z); ctx.fill();
    ctx.fillStyle = (hovd || foll) ? '#fff' : '#cdd3f0'; ctx.fillText(d.name, p.x, headY - 16 * sc + 10 * z); ctx.textAlign = 'left';
  }
  ctx.globalAlpha = 1;
}
function arm(x0, y0, x1, y1) { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }
function drawRoleProp(d, x, headY, fy, sh, sc, fx, robe, working, t, elder) {
  const A = (ROLE_STYLE[d.role] || ROLE_STYLE.disciple).color;
  switch (d.role) {
    case 'elder': {                                     // beard + staff
      ctx.fillStyle = '#e8e2d0'; ctx.beginPath(); ctx.moveTo(x - 2 * sc, headY + 2 * sc); ctx.lineTo(x + 2 * sc, headY + 2 * sc); ctx.lineTo(x, headY + 6 * sc); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = shade('#7a5a2a', 0.1); ctx.lineWidth = 1.6 * sc; ctx.beginPath(); ctx.moveTo(x + 6 * sc * fx, fy + 1 * sc); ctx.lineTo(x + 6 * sc * fx, headY - 6 * sc); ctx.stroke();
      ctx.fillStyle = '#a78bfa'; ctx.shadowColor = '#a78bfa'; ctx.shadowBlur = 8 * sc; ctx.beginPath(); ctx.arc(x + 6 * sc * fx, headY - 7 * sc, 2.2 * sc, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break; }
    case 'trader': {                                    // glowing market tablet
      const tx = x + 5.5 * sc * fx, ty = working ? headY + 2 * sc : sh + 1 * sc;
      ctx.fillStyle = 'rgba(8,14,22,.9)'; ctx.fillRect(tx - 3 * sc, ty - 4 * sc, 6 * sc, 7 * sc);
      ctx.strokeStyle = A; ctx.shadowColor = A; ctx.shadowBlur = (working ? 7 : 3) * sc; ctx.strokeRect(tx - 3 * sc, ty - 4 * sc, 6 * sc, 7 * sc);
      ctx.fillStyle = '#34d399'; for (let i = 0; i < 3; i++) ctx.fillRect(tx - 2 * sc + i * 2 * sc, ty + 1 * sc - ((i + (t * 4 | 0)) % 3) * sc, 1.2 * sc, 2 * sc); ctx.shadowBlur = 0; break; }
    case 'researcher': {                                // scroll
      const tx = x + 5 * sc * fx, ty = sh + 1 * sc; ctx.fillStyle = '#efe6c8'; ctx.fillRect(tx - 2.5 * sc, ty - 4 * sc, 5 * sc, 8 * sc);
      ctx.strokeStyle = shade(A, -0.2); ctx.lineWidth = 1 * sc; for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(tx - 1.5 * sc, ty - 4 * sc + i * 2 * sc); ctx.lineTo(tx + 1.5 * sc, ty - 4 * sc + i * 2 * sc); ctx.stroke(); } break; }
    case 'engineer': {                                  // visor
      ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 6 * sc; ctx.fillRect(x - 3.4 * sc, headY - 1 * sc, 6.8 * sc, 1.6 * sc); ctx.shadowBlur = 0; break; }
    case 'architect': {                                 // tool belt
      ctx.fillStyle = shade(A, -0.2); ctx.fillRect(x - 4 * sc, fy - 6 * sc, 8 * sc, 1.6 * sc);
      ctx.fillStyle = A; ctx.beginPath(); ctx.arc(x - 2 * sc, fy - 5 * sc, 1 * sc, 0, 6.28); ctx.arc(x + 2 * sc, fy - 5 * sc, 1 * sc, 0, 6.28); ctx.fill(); break; }
    case 'analyst': {                                   // clipboard
      const tx = x + 5 * sc * fx, ty = sh + 2 * sc; ctx.fillStyle = '#e7ecf5'; ctx.fillRect(tx - 2.5 * sc, ty - 3 * sc, 5 * sc, 7 * sc);
      ctx.strokeStyle = A; ctx.lineWidth = 0.9 * sc; for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(tx - 1.6 * sc, ty - 3 * sc + i * 1.8 * sc); ctx.lineTo(tx + 1.6 * sc, ty - 3 * sc + i * 1.8 * sc); ctx.stroke(); } break; }
  }
  ctx.shadowBlur = 0;
}

/* breakthrough spectacles */
const spectacles = [];
function celebrate(gx, gy, color, text) { spectacles.push({ gx, gy, color, text, t: 0 }); }
function drawSpectacles(dt) {
  for (let i = spectacles.length - 1; i >= 0; i--) { const s = spectacles[i]; s.t += dt; const k = s.t / 2.6, p = toScreen(s.gx, s.gy), z = cam.zoom; p.y -= elevAt(s.gx, s.gy) * z;
    ctx.strokeStyle = s.color; ctx.globalAlpha = Math.max(0, 0.9 - k); ctx.lineWidth = 3 * z; ctx.beginPath(); ctx.ellipse(p.x, p.y, (10 + k * 90) * z, (5 + k * 45) * z, 0, 0, 6.28); ctx.stroke();
    ctx.globalAlpha = Math.max(0, 1 - k); ctx.font = `700 ${13 * z}px system-ui`; ctx.textAlign = 'center'; ctx.fillStyle = '#fff3cf'; ctx.fillText('✦ ' + s.text, p.x, p.y - (26 + k * 28) * z); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
    if (s.t > 2.6) spectacles.splice(i, 1); }
}

/* micro-events — brief gatherings that make the HQ feel inhabited */
const microEvents = [];
const EVENT_TEXT = { market: 'Trade review', engineering: 'Deploy review', library: 'Research discussion', mission: 'Mission briefing',
  server: 'Systems check', cultivation: 'Group meditation', hall: 'Sect assembly', commerce: 'Market report' };
function microTick() {
  if (!rooms.length) return;
  const r = Math.random() < 0.4 ? hall() : rooms[(Math.random() * rooms.length) | 0]; if (!r) return;
  microEvents.push({ room: r, text: EVENT_TEXT[r.kind] || 'Gathering', t: 0, ttl: 7 });
  disciples.filter((d) => d.state === 'idle' && d.chat <= 0).slice(0, 2 + (Math.random() * 2 | 0)).forEach((d, k) => {
    d.tx = r.gx + r.w * 0.35 + k * 1.2; d.ty = r.gy + r.h + 0.6; d.idleAct = 'observe'; d.idleT = 7;
  });
}
function drawMicro(dt) {
  for (let i = microEvents.length - 1; i >= 0; i--) {
    const e = microEvents[i]; e.t += dt; const p = toScreen(e.room.cx, e.room.gy), z = cam.zoom; p.y -= (e.room.elev || 0) * z;
    const a = Math.min(1, e.t * 2) * Math.min(1, (e.ttl - e.t) * 1.5);
    ctx.globalAlpha = Math.max(0, a); ctx.font = `700 ${11 * z}px system-ui`; ctx.textAlign = 'center';
    const w = ctx.measureText(e.text).width + 22 * z, y = p.y - 70 * z;
    ctx.fillStyle = 'rgba(18,14,30,.92)'; roundRect(p.x - w / 2, y - 13 * z, w, 19 * z, 6 * z); ctx.fill();
    ctx.strokeStyle = e.room.K.accent; ctx.lineWidth = 1.4 * z; ctx.shadowColor = e.room.K.accent; ctx.shadowBlur = 8 * z; roundRect(p.x - w / 2, y - 13 * z, w, 19 * z, 6 * z); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.fillStyle = '#fff'; ctx.fillText('✦ ' + e.text, p.x, y); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
    if (e.t > e.ttl) microEvents.splice(i, 1);
  }
}

function drawRoomLabel(r) {
  const p = toScreen(r.cx, r.gy), z = cam.zoom, y = p.y - (82 + (r.elev || 0)) * z; ctx.textAlign = 'center';
  ctx.font = `700 ${12 * z}px system-ui`; const tw = ctx.measureText(r.title).width;
  const sub = r.sub && r.sub !== r.title ? r.sub : '';
  ctx.font = `${8.5 * z}px system-ui`; const sw = sub ? ctx.measureText(sub).width : 0;
  const w = Math.max(tw, sw) + 18 * z, hgt = sub ? 28 * z : 18 * z;
  ctx.fillStyle = 'rgba(8,10,20,.78)'; roundRect(p.x - w / 2, y - 13 * z, w, hgt, 5 * z); ctx.fill();
  ctx.font = `700 ${12 * z}px system-ui`; ctx.fillStyle = r.K.accent; ctx.fillText(r.title, p.x, y);
  if (sub) { ctx.font = `${8.5 * z}px system-ui`; ctx.fillStyle = 'rgba(184,190,214,.85)'; ctx.fillText(sub, p.x, y + 11 * z); }
  if (r.data) { ctx.fillStyle = HEALTH[r.data.health] || HEALTH.unknown; ctx.beginPath(); ctx.arc(p.x - w / 2 + 8 * z, y - 4 * z, 3 * z, 0, 6.28); ctx.fill(); }
  if (r.occupants.size) { ctx.fillStyle = '#cdd3f0'; ctx.font = `${9 * z}px system-ui`; ctx.fillText('▸ ' + r.occupants.size, p.x + w / 2 + 8 * z, y); }
  ctx.textAlign = 'left';
}

/* ====================================================================== *
 *  Render loop
 * ====================================================================== */
let last = performance.now(), elapsed = 0, lastDerive = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000); last = now; elapsed += dt; const t = elapsed;
  if (followed) { const wp = { x: (followed.gx - followed.gy) * TW2, y: (followed.gx + followed.gy) * TH2 }; cam.x += (wp.x - cam.x) * 0.06; cam.y += (wp.y - cam.y) * 0.06; updateFollowChip(); }
  if (t - lastDerive > 0.35) { disciples.forEach(deriveState); lastDerive = t; }
  disciples.forEach((d) => step(d, dt, t)); updateAmbient(dt, t); updateExtras(dt, t);

  const bg = ctx.createLinearGradient(0, 0, 0, view.h); bg.addColorStop(0, '#12183a'); bg.addColorStop(0.55, '#1a2247'); bg.addColorStop(1, '#0c1024'); ctx.fillStyle = bg; ctx.fillRect(0, 0, view.w, view.h);
  drawHorizon(t);
  drawBridges();
  drawAncestor(t);
  drawCouriers(t);
  const ordered = rooms.slice().sort((a, b) => a.depth - b.depth);
  ordered.forEach((r) => drawRoom(r, t));
  drawExtras(t);
  ordered.forEach((r) => drawWorkFX(r, t));
  rooms.forEach(drawRoomLabel);
  disciples.slice().sort((a, b) => (a.gx + a.gy) - (b.gx + b.gy)).forEach((d) => drawDisciple(d, t));
  drawLanterns(t);
  drawForegroundClouds(t);
  drawSpectacles(dt); drawMicro(dt);
  drawAtmosphere(t);
}
/* low cloud layer drifting in front of the peaks — the sect floats in a cloud sea */
function drawForegroundClouds(t) {
  const w = view.w, h = view.h, px = -cam.x * 0.05;
  for (let i = 0; i < 7; i++) {
    const cx = (((i / 7) * (w + 460) - 230 + t * (10 + i * 2) + px) % (w + 460)) - 0;
    const cy = h * (0.74 + (i % 3) * 0.08) + Math.sin(t * 0.25 + i) * 6;
    ctx.globalAlpha = 0.10 + (i % 2) * 0.05; ctx.fillStyle = '#cdd6ee';
    ctx.beginPath(); ctx.ellipse(cx, cy, 150 + (i % 3) * 40, 30, 0, 0, 6.28); ctx.ellipse(cx + 90, cy + 8, 110, 24, 0, 0, 6.28); ctx.fill();
  }
  ctx.globalAlpha = 1;
}
/* spirit bridges spanning the cloud gaps between mountain terraces */
function drawBridge(p1, p2) {
  const z = cam.zoom, mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2 - 7 * z;
  ctx.strokeStyle = 'rgba(118,116,134,.95)'; ctx.lineCap = 'round'; ctx.lineWidth = 7 * z;
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.quadraticCurveTo(mx, my, p2.x, p2.y); ctx.stroke();
  ctx.strokeStyle = 'rgba(156,152,172,.7)'; ctx.lineWidth = 1.4 * z;
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y - 4 * z); ctx.quadraticCurveTo(mx, my - 4 * z, p2.x, p2.y - 4 * z); ctx.stroke();
  ctx.lineCap = 'butt';
  [p1, p2].forEach((p) => { ctx.fillStyle = '#ffce6a'; ctx.shadowColor = '#ffce6a'; ctx.shadowBlur = 7 * z; ctx.beginPath(); ctx.arc(p.x, p.y - 7 * z, 1.8 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; });
}
function drawBridges() {
  rooms.forEach((a) => {
    let right = null, down = null;
    rooms.forEach((b) => { if (b === a) return;
      if (b.gx > a.gx + a.w - 1 && Math.abs(b.cyc - a.cyc) < 3 && (!right || b.gx < right.gx)) right = b;
      if (b.gy > a.gy + a.h - 1 && Math.abs(b.cx - a.cx) < 3 && (!down || b.gy < down.gy)) down = b;
    });
    const lift = (p, e) => ({ x: p.x, y: p.y - (e || 0) * cam.zoom });
    if (right) drawBridge(lift(toScreen(a.gx + a.w, a.cyc), a.elev), lift(toScreen(right.gx, right.cyc), right.elev));
    if (down) drawBridge(lift(toScreen(a.cx, a.gy + a.h), a.elev), lift(toScreen(down.cx, down.gy), down.elev));
  });
}
/* the Grand Ancestor's peak — ancestral shrine above the sect, with rare golden manifestations */
function drawAncestor(t) {
  const h = hall(); if (!h) return; const gx = h.cx, gy = h.gy - 2.4, z = cam.zoom;
  ctx.save(); ctx.translate(0, -(h.elev + 34) * z);     // the ancestral peak crowns the summit
  const p = toScreen(gx, gy);
  // a rock spire rising from the summit up to the shrine
  ctx.fillStyle = '#241f33'; ctx.beginPath(); ctx.moveTo(p.x - 22 * z, p.y); ctx.lineTo(p.x + 22 * z, p.y); ctx.lineTo(p.x + 12 * z, p.y + 110 * z); ctx.lineTo(p.x - 12 * z, p.y + 110 * z); ctx.closePath(); ctx.fill();
  blit('shrine', gx, gy, 1.7);
  const cyc = t % 26;                                  // a rare manifestation every ~26s
  if (cyc < 6) {
    const a = (cyc < 2 ? cyc / 2 : cyc > 5 ? (6 - cyc) : 1);
    ctx.globalAlpha = 0.22 * a; const g = ctx.createLinearGradient(0, p.y - 230 * z, 0, p.y); g.addColorStop(0, 'rgba(255,212,110,0)'); g.addColorStop(1, 'rgba(255,212,110,.85)');
    ctx.fillStyle = g; ctx.fillRect(p.x - 28 * z, p.y - 230 * z, 56 * z, 230 * z);
    const cy = p.y - 150 * z;                          // golden immortal projection
    ctx.globalAlpha = 0.24 * a; ctx.fillStyle = '#ffe39a'; ctx.shadowColor = '#ffd36a'; ctx.shadowBlur = 30 * z;
    ctx.beginPath(); ctx.moveTo(p.x, cy - 42 * z); ctx.lineTo(p.x + 28 * z, cy + 22 * z); ctx.quadraticCurveTo(p.x, cy + 32 * z, p.x - 28 * z, cy + 22 * z); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.arc(p.x, cy - 50 * z, 13 * z, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
    ctx.globalAlpha = 0.4 * a; ctx.strokeStyle = '#ffe39a'; ctx.lineWidth = 2 * z;
    for (let i = 0; i < 3; i++) { const rr = (t * 0.5 + i * 0.34) % 1; ctx.beginPath(); ctx.ellipse(p.x, p.y, (12 + rr * 64) * z, (6 + rr * 32) * z, 0, 0, 6.28); ctx.stroke(); }
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

/* ---------------- the wider sect (background, parallax) ---------------- */
const FAR_ISLES = [];
function initHorizon() { FAR_ISLES.length = 0; for (let i = 0; i < 5; i++) FAR_ISLES.push({ x: 0.08 + Math.random() * 0.84, y: 0.16 + Math.random() * 0.16, s: 0.6 + Math.random() * 0.8, ph: Math.random() * 6.28 }); }
function mountainRange(baseY, amp, peaks, off, color) {
  const w = view.w; ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(-50, view.h);
  for (let i = 0; i <= peaks; i++) { const x = ((i / peaks) * (w + 200) - 100 + off); const y = baseY - Math.abs(Math.sin(i * 1.7 + off * 0.01)) * amp; ctx.lineTo(x, y); }
  ctx.lineTo(w + 50, view.h); ctx.closePath(); ctx.fill();
}
function drawFarIsle(x, y, s, t) {
  const z = s; ctx.save(); ctx.globalAlpha = 0.5;
  ctx.fillStyle = '#161a30'; ctx.beginPath(); ctx.ellipse(x, y, 26 * z, 7 * z, 0, 0, 6.28); ctx.fill();
  ctx.beginPath(); ctx.moveTo(x - 24 * z, y); ctx.lineTo(x, y + 16 * z); ctx.lineTo(x + 24 * z, y); ctx.closePath(); ctx.fill();
  ctx.fillStyle = shade('#a78bfa', -0.5); ctx.beginPath(); ctx.moveTo(x - 8 * z, y - 4 * z); ctx.lineTo(x, y - 14 * z); ctx.lineTo(x + 8 * z, y - 4 * z); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = 'rgba(167,139,250,.5)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = '#fbbf24'; ctx.globalAlpha = 0.6; ctx.beginPath(); ctx.arc(x, y - 15 * z, 1.4 * z, 0, 6.28); ctx.fill();
  ctx.restore();
}
function drawHorizon(t) {
  const w = view.w, h = view.h, px = -cam.x * 0.02, py = -cam.y * 0.015;
  // sun shafts from the upper sky
  ctx.save(); ctx.globalAlpha = 0.05; ctx.fillStyle = '#ffe7b0'; ctx.translate(w * 0.66, -80); ctx.rotate(0.5);
  for (let i = 0; i < 4; i++) ctx.fillRect(i * 110 - 80, 0, 38, h * 1.8); ctx.restore();
  // layered distant peaks (far -> near)
  mountainRange(h * 0.44 + py, h * 0.16, 6, px * 0.4, '#1a2350');
  mountainRange(h * 0.50 + py, h * 0.18, 7, px * 0.6, '#141a3c');
  mountainRange(h * 0.57 + py, h * 0.22, 6, px * 0.9, '#0d1228');
  // a neighbouring sect on a far peak
  (function () { const sx = w * 0.2 + px * 0.6, sy = h * 0.44 + py; ctx.fillStyle = '#0a0e22';
    ctx.beginPath(); ctx.moveTo(sx - 10, sy); ctx.lineTo(sx, sy - 22); ctx.lineTo(sx + 10, sy); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(167,139,250,.4)'; ctx.fillRect(sx - 2, sy - 26, 4, 6); })();
  // rolling cloud sea (the peaks emerge from it)
  for (let i = 0; i < 10; i++) { ctx.fillStyle = `rgba(150,162,205,${0.05 + (i % 3) * 0.02})`; const cx = (((i / 10) * (w + 320) - 160 + t * (6 + i) + px * 1.4) % (w + 320)) - 0;
    ctx.beginPath(); ctx.ellipse(cx, h * (0.60 + (i % 4) * 0.05) + py + Math.sin(t * 0.2 + i) * 5, 150, 28, 0, 0, 6.28); ctx.fill(); }
  FAR_ISLES.forEach((I) => drawFarIsle(I.x * w + px * 1.6, h * I.y + py + Math.sin(t * 0.4 + I.ph) * 6, I.s, t));
  // sky life: a gliding crane and a flying-sword cultivator crossing the heavens
  const cax = (t * 26 % (w + 200)) - 100, cay = h * 0.26 + Math.sin(t * 0.6) * 16;
  ctx.save(); ctx.globalAlpha = 0.85; ctx.strokeStyle = '#e8edff'; ctx.lineWidth = 2; const fl = Math.sin(t * 6) * 6;
  ctx.beginPath(); ctx.moveTo(cax - 10, cay - fl); ctx.lineTo(cax, cay); ctx.lineTo(cax + 10, cay - fl); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cax - 26, cay + 6 - fl * 0.6); ctx.lineTo(cax - 16, cay + 6); ctx.lineTo(cax - 6, cay + 6 - fl * 0.6); ctx.stroke(); ctx.restore();
  const sw = ((t * 90 + 300) % (w + 240)) - 120, swy = h * 0.18 + Math.sin(t * 0.8) * 10;
  ctx.save(); ctx.globalAlpha = 0.6; ctx.strokeStyle = '#bcd0ff'; ctx.shadowColor = '#9ec0ff'; ctx.shadowBlur = 8; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(sw, swy); ctx.lineTo(sw + 26, swy - 4); ctx.stroke();
  ctx.fillStyle = '#cdd9ff'; ctx.beginPath(); ctx.arc(sw + 28, swy - 4, 2, 0, 6.28); ctx.fill(); ctx.restore();
}

/* ---------------- ambient world life ---------------- */
const lanterns = [], couriers = [];
function newCourier() { const a = rooms[(Math.random() * rooms.length) | 0], b = rooms[(Math.random() * rooms.length) | 0];
  return { gx: a ? a.cx : 0, gy: a ? a.gy + a.h : 0, tx: b ? b.cx : 0, ty: b ? b.gy + b.h : 0 }; }
function initAmbient() {
  lanterns.length = 0; couriers.length = 0; if (!grounds) return;
  for (let i = 0; i < 8; i++) lanterns.push({ gx: rand(grounds.minGx, grounds.maxGx), gy: rand(grounds.minGy, grounds.maxGy), phase: Math.random() * 6.28, h: 24 + Math.random() * 20, hue: Math.random() < 0.5 ? '#fbbf24' : '#a78bfa' });
  for (let i = 0; i < 2; i++) couriers.push(newCourier());
}
function updateAmbient(dt, t) {
  lanterns.forEach((l) => { l.gx += Math.sin(t * 0.2 + l.phase) * dt * 0.18; l.gy += Math.cos(t * 0.16 + l.phase) * dt * 0.14; });
  couriers.forEach((c) => { const dx = c.tx - c.gx, dy = c.ty - c.gy, d = Math.hypot(dx, dy);
    if (d < 0.25) { const n = newCourier(); c.gx = n.gx; c.gy = n.gy; c.tx = n.tx; c.ty = n.ty; } else { const v = Math.min(d, 2.3 * dt); c.gx += dx / d * v; c.gy += dy / d * v; } });
}
function drawCouriers(t) {
  const z = cam.zoom; couriers.forEach((c) => { const p = toScreen(c.gx, c.gy), fy = p.y - (11 + Math.sin(t * 4 + c.gx) * 2) * z;
    ctx.fillStyle = 'rgba(0,0,0,.3)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 4 * z, 2 * z, 0, 0, 6.28); ctx.fill();
    ctx.fillStyle = '#aeb6d8'; ctx.shadowColor = '#7c5cff'; ctx.shadowBlur = 6 * z; ctx.beginPath(); ctx.ellipse(p.x, fy, 4 * z, 2.4 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
    ctx.fillStyle = '#efe6c8'; ctx.fillRect(p.x - 1.4 * z, fy - 5 * z, 2.8 * z, 4 * z); });
}
function drawLanterns(t) {
  const z = cam.zoom; lanterns.forEach((l) => { const p = toScreen(l.gx, l.gy), y = p.y - (l.h + Math.sin(t * 1.5 + l.phase) * 4) * z;
    ctx.globalAlpha = 0.85; ctx.fillStyle = l.hue; ctx.shadowColor = l.hue; ctx.shadowBlur = 14 * z; ctx.beginPath(); ctx.ellipse(p.x, y, 3.2 * z, 4.2 * z, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255,255,255,.3)'; ctx.lineWidth = 0.8 * z; ctx.beginPath(); ctx.moveTo(p.x, y - 4.2 * z); ctx.lineTo(p.x, y - 9 * z); ctx.stroke(); ctx.globalAlpha = 1; });
}

/* ---------------- background life — decorative extras (no AI) ---------------- */
const extras = [];
const EXTRA_ROBE = { novice: '#8b92ac', keeper: '#6f7a52', visitor: '#a98c6a', meditator: '#9a8cff', scholar: '#c4b5fd', smith: '#5ac8ff', maint: '#7bb0ff', traveler: '#a98c6a', spar: '#9a8cff' };
const EXTRA_ACT = { meditator: 'sit', scholar: 'work', smith: 'work', maint: 'work' };          // others wander
const EXTRA_SET = {
  fountain: ['visitor', 'visitor', 'visitor', 'keeper'], prosperity: ['visitor', 'visitor', 'visitor', 'keeper'],
  observatory: ['scholar', 'scholar', 'scholar'], forge: ['smith', 'smith', 'smith'], tome: ['scholar', 'scholar', 'scholar'],
  gate: ['traveler', 'traveler', 'visitor', 'visitor'], bell: ['novice', 'novice', 'visitor'], nexus: ['maint', 'maint', 'maint'],
  vortex: ['meditator', 'meditator', 'spar', 'spar', 'keeper'], monument: ['novice', 'novice', 'novice', 'keeper', 'keeper'],
};
function mkExtra(r, kind, court) {
  const gx = r.gx + rand(1, r.w - 1), gy = r.gy + rand(1.2, r.h - 1);
  return { kind, act: EXTRA_ACT[kind] || 'wander', gx, gy, tx: gx, ty: gy, home: { gx, gy }, phase: Math.random() * 6.28,
    speed: (kind === 'traveler' ? 1.2 : 0.7) + Math.random() * 0.5, court: !!court, pause: 0, moving: false, facing: 1 };
}
function initExtras() {
  extras.length = 0; if (!rooms.length) return;
  rooms.forEach((r) => (EXTRA_SET[r.landmark] || ['novice']).forEach((k) => extras.push(mkExtra(r, k))));
  for (let i = 0; i < 8; i++) extras.push(mkExtra(rooms[(Math.random() * rooms.length) | 0], 'visitor', true));
}
function updateExtras(dt, t) {
  extras.forEach((e) => { if (e.act !== 'wander') { e.moving = false; return; }
    const dx = e.tx - e.gx, dy = e.ty - e.gy, d = Math.hypot(dx, dy);
    if (d > 0.05) { const v = Math.min(d, e.speed * dt); e.gx += dx / d * v; e.gy += dy / d * v; e.phase += dt * 8; e.moving = true; e.facing = (dx - dy) >= 0 ? 1 : -1; }
    else { e.moving = false; e.pause -= dt; if (e.pause <= 0) { const rad = e.court ? 8 : 2; e.tx = e.home.gx + rand(-rad, rad); e.ty = e.home.gy + rand(-rad, rad); e.pause = 2 + Math.random() * 4; } } });
}
function drawExtras(t) {
  extras.slice().sort((a, b) => (a.gx + a.gy) - (b.gx + b.gy)).forEach((e) => {
    const p = toScreen(e.gx, e.gy), z = cam.zoom, sc = z * 1.12, robe = EXTRA_ROBE[e.kind] || '#8b92ac', sit = e.act === 'sit', work = e.act === 'work', fx = e.facing; p.y -= elevAt(e.gx, e.gy) * z;
    ctx.fillStyle = 'rgba(0,0,0,.4)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 4 * sc, 1.8 * sc, 0, 0, 6.28); ctx.fill();
    const bob = sit ? 0 : work ? Math.abs(Math.sin(t * 4 + e.phase)) * 1 * sc : e.moving ? Math.abs(Math.sin(e.phase)) * 1.6 * sc : Math.sin(t * 2 + e.phase) * 0.5 * sc;
    const fy = p.y - bob, bodyH = (sit ? 8 : 11) * sc, headR = 2.6 * sc;
    ctx.fillStyle = shade(robe, -0.08); ctx.strokeStyle = shade(robe, -0.5); ctx.lineWidth = 0.8 * sc;
    ctx.beginPath(); ctx.moveTo(p.x, fy - bodyH); ctx.lineTo(p.x + 3.6 * sc, fy); ctx.quadraticCurveTo(p.x, fy + 1.4 * sc, p.x - 3.6 * sc, fy); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#e8ddc8'; ctx.beginPath(); ctx.arc(p.x, fy - bodyH, headR, 0, 6.28); ctx.fill();
    if (sit) { ctx.globalAlpha = 0.3 + Math.sin(t * 2 + e.phase) * 0.15; ctx.strokeStyle = '#a78bfa'; ctx.lineWidth = 1 * sc; ctx.beginPath(); ctx.ellipse(p.x, fy, 6 * sc, 3 * sc, 0, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1; }
    if (e.kind === 'keeper') { const sw = Math.sin(t * 4 + e.phase); ctx.strokeStyle = '#7a5a2a'; ctx.lineWidth = 1.1 * sc; ctx.beginPath(); ctx.moveTo(p.x + 2 * sc, fy - 7 * sc); ctx.lineTo(p.x + 6 * sc + sw * 2 * sc, fy + 1 * sc); ctx.stroke(); }
    else if (e.kind === 'smith') { const h = Math.abs(Math.sin(t * 8 + e.phase)); ctx.strokeStyle = shade(robe, -0.2); ctx.lineWidth = 1.2 * sc; ctx.beginPath(); ctx.moveTo(p.x + 1 * sc, fy - 7 * sc); ctx.lineTo(p.x + 5 * sc, fy - 6 * sc - h * 4 * sc); ctx.stroke(); }
    else if (e.kind === 'scholar') { ctx.fillStyle = '#efe6c8'; ctx.fillRect(p.x + 3 * sc * fx - 1.5 * sc, fy - 7 * sc, 3 * sc, 5 * sc); }
    else if (e.kind === 'spar') { const sw = Math.sin(t * 6 + e.phase); ctx.strokeStyle = shade(robe, -0.2); ctx.lineWidth = 1.1 * sc; ctx.beginPath(); ctx.moveTo(p.x, fy - 7 * sc); ctx.lineTo(p.x + 5 * sc * sw, fy - 8 * sc); ctx.stroke(); }
  });
}

/* ---------------- atmosphere — haze, light, drifting spirit motes ---------------- */
const petals = [];
function initAtmos() { petals.length = 0; for (let i = 0; i < 24; i++) petals.push({ x: Math.random(), y: Math.random(), s: 0.5 + Math.random(), v: 0.2 + Math.random() * 0.35, ph: Math.random() * 6.28 }); }
function drawAtmosphere(t) {
  const w = view.w, h = view.h;
  const hz = ctx.createLinearGradient(0, 0, 0, h); hz.addColorStop(0, 'rgba(124,92,255,.06)'); hz.addColorStop(0.5, 'rgba(0,0,0,0)'); hz.addColorStop(1, 'rgba(8,6,18,.30)');
  ctx.fillStyle = hz; ctx.fillRect(0, 0, w, h);
  ctx.save(); ctx.globalAlpha = 0.04; ctx.fillStyle = '#cbd6ff'; ctx.translate(w * 0.72, -60); ctx.rotate(0.5); for (let i = 0; i < 3; i++) ctx.fillRect(i * 130 - 90, 0, 46, h * 1.7); ctx.restore();
  petals.forEach((pt) => { pt.x += pt.v * 0.0007; if (pt.x > 1.12) pt.x = -0.12; const x = pt.x * w, y = (pt.y + Math.sin(t * 0.3 + pt.ph) * 0.02) * h;
    ctx.globalAlpha = 0.5; ctx.fillStyle = pt.ph > 3 ? '#ffd0e0' : '#cbb9ff'; ctx.beginPath(); ctx.ellipse(x, y, 2 * pt.s, 1.2 * pt.s, t + pt.ph, 0, 6.28); ctx.fill(); }); ctx.globalAlpha = 1;
  const vg = ctx.createRadialGradient(w / 2, h * 0.45, h * 0.32, w / 2, h * 0.5, h * 0.92); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.45)'); ctx.fillStyle = vg; ctx.fillRect(0, 0, w, h);
}

/* ====================================================================== *
 *  Input
 * ====================================================================== */
const hover = { room: null, disc: null }, selected = { room: null, disc: null };
let followed = null, drag = null;
function pickAt(mx, my) {
  let best = null, bestD = 26;
  disciples.forEach((d) => { const p = toScreen(d.gx, d.gy); p.y -= elevAt(d.gx, d.gy) * cam.zoom; const dist = Math.hypot(p.x - mx, p.y - my - 16 * cam.zoom); if (d.alpha > 0.3 && dist < bestD) { bestD = dist; best = d; } });
  if (best) return { disc: best };
  const gp = toGrid(mx, my); const r = rooms.find((R) => gp.gx >= R.gx && gp.gx <= R.gx + R.w && gp.gy >= R.gy && gp.gy <= R.gy + R.h);
  return { room: r || null };
}
canvas.addEventListener('mousedown', (e) => { drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false }; });
addEventListener('mousemove', (e) => {
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  if (drag) { const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.hypot(dx, dy) > 4) { drag.moved = true; cam.userMoved = true; followed = null; updateFollowChip(); cam.x = drag.cx - dx / cam.zoom; cam.y = drag.cy - dy / cam.zoom; } canvas.style.cursor = 'grabbing'; return; }
  const hit = pickAt(mx, my); hover.disc = hit.disc || null; hover.room = hit.disc ? null : hit.room; canvas.style.cursor = (hover.disc || hover.room) ? 'pointer' : 'grab';
});
addEventListener('mouseup', (e) => {
  if (drag && !drag.moved) { const r = canvas.getBoundingClientRect(); const hit = pickAt(e.clientX - r.left, e.clientY - r.top); if (hit.disc) selectDisc(hit.disc); else if (hit.room) selectRoom(hit.room); }
  drag = null; canvas.style.cursor = 'grab';
});
canvas.addEventListener('wheel', (e) => { e.preventDefault(); cam.userMoved = true; const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const before = toGrid(mx, my); cam.zoom = Math.max(0.4, Math.min(2.4, cam.zoom * (e.deltaY < 0 ? 1.1 : 0.9))); const after = toGrid(mx, my);
  cam.x += ((before.gx - after.gx) - (before.gy - after.gy)) * TW2; cam.y += ((before.gx - after.gx) + (before.gy - after.gy)) * TH2; }, { passive: false });

/* ====================================================================== *
 *  Panels
 * ====================================================================== */
function selectRoom(r) {
  selected.room = r; selected.disc = null; const p = r.data, busy = r.occupants.size;
  const who = [...r.occupants].map((d) => esc(d.name)).join(', ') || 'none on site';
  const rows = [['Area', esc(r.K.name)], p ? ['Type', esc(p.type || '')] : null, p ? ['Host', esc(p.device || '')] : null, ['On site', busy ? `${busy} disciples` : '—'],
    p && p.type === 'trading_bot' && Number.isFinite(Number((p.metrics || {}).profit_today)) ? ['PnL Today', money(p.metrics.profit_today)] : null]
    .filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(r.title)}</div>
    ${r.sub ? `<div class='muted' style='font-size:12px;margin-top:6px'>overseeing <b style='color:var(--text)'>${esc(r.sub)}</b></div>` : ''}
    ${p ? `<div class='realm-health health-${esc(p.health || 'unknown')}'>${esc(p.health || 'unknown')}</div>` : ''}
    <div class='kvs'>${rows}</div><div class='muted' style='font-size:11.5px;margin-top:10px'>${esc(who)}</div>
    <div class='realm-actions'><button class='cbtn' id='r-logs'>View Logs</button><button class='cbtn' id='r-assign'>Assign Disciple</button></div>`;
  $('r-logs').onclick = () => { localStorage.setItem('tab', 'overview'); location.href = '/classic'; };
  $('r-assign').onclick = () => { localStorage.setItem('tab', 'disciples'); location.href = '/classic'; };
}
function selectDisc(d) {
  selected.disc = d; selected.room = null; followed = d; cam.userMoved = true; updateFollowChip(); renderFollowPanel(d);
}
function renderFollowPanel(d) {
  const ag = d.data, c = ag.cultivation || {}, g = ag.governance || {};
  const dest = d.state === 'traveling' && d.room ? d.room.title : d.state === 'roaming' ? 'beyond the realm' : d.state === 'meditate' ? 'Cultivation Chamber' : (d.room ? d.room.title : 'Sect Hall');
  const doing = { working: 'Working', traveling: 'Walking to ' + dest, roaming: 'Roaming', meditate: 'Meditating', idle: 'Resting at the Sect Hall', error: 'Needs aid' }[d.state] || d.state;
  const rows = [['Role', esc(ag.role || (g.is_leader ? 'Sect Leader' : c.rank_title) || 'Disciple')], ['Rank', esc(c.rank_title || 'Disciple')], ['Realm', esc(c.realm_name || 'Mortal')],
    ['Doing', esc(doing)], ['Destination', esc(dest)], ag.current_task ? ['Task', esc(String(ag.current_task).slice(0, 60))] : null, ['Tasks done', ag.tasks_done || 0]]
    .filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  const prog = Math.round(d.progress * 100);
  $('detail').innerHTML = `<div class='panel-title'>${esc(d.name)}</div>
    <div class='muted' style='margin:8px 0 2px;font-size:12.5px'>📷 Following — ${esc(doing)}.</div>
    <div class='kvs'>${rows}</div>
    ${d.state === 'working' ? `<div style='margin-top:12px'><div class='metric-lbl'>Task progress</div><div class='conf-bar' style='margin-top:6px'><span style='width:${prog}%'></span></div></div>` : ''}
    <div class='realm-actions'><button class='cbtn' id='r-cham'>Open Dossier</button><button class='cbtn' id='r-rel'>Release Camera</button></div>`;
  $('r-cham').onclick = () => { location.href = '/chamber'; };
  $('r-rel').onclick = () => { followed = null; updateFollowChip(); };
}
function updateFollowChip() {
  const chip = $('follow-chip'); if (!followed) { chip.hidden = true; return; }
  chip.hidden = false; chip.innerHTML = `👁 Following <b>${esc(followed.name)}</b> · <span class='fc-x'>release ✕</span>`;
  chip.querySelector('.fc-x').onclick = () => { followed = null; updateFollowChip(); };
}

/* legend + roam ticker */
$('legend').innerHTML = [['#34d399', 'working'], ['#9a8cff', 'idle'], ['#fbbf24', 'roaming'], ['#fb5e7e', 'needs aid']]
  .map(([c, l]) => `<span class='lg'><i class='lg-dot' style='background:${c};color:${c}'></i>${l}</span>`).join('');
function renderRoamTicker() {
  const roamers = disciples.filter((d) => d.state === 'roaming'); const el = $('roam'); if (!roamers.length) { el.hidden = true; return; } el.hidden = false;
  const verbs = ['exploring external markets', 'gathering intelligence', 'researching independently', 'seeking rare techniques', 'returning from a mission'];
  el.innerHTML = `<div class='panel-title'>Beyond the Realm</div>` + roamers.map((d, i) => `<div class='roam-row'>🌄 <b>${esc(d.name)}</b> is ${verbs[(d.name.charCodeAt(0) + i) % verbs.length]}…</div>`).join('');
}
setInterval(renderRoamTicker, 1200);
setInterval(socialTick, 2000);

/* resize */
function resize() {
  view.dpr = Math.min(devicePixelRatio || 1, 2); view.w = innerWidth; view.h = innerHeight;
  canvas.width = view.w * view.dpr; canvas.height = view.h * view.dpr; canvas.style.width = view.w + 'px'; canvas.style.height = view.h + 'px';
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0); view.cx = view.w / 2; view.cy = view.h * 0.54;
  if (!cam.userMoved) centerOnHall();
}
addEventListener('resize', resize); resize(); initHorizon(); initAtmos();

/* ====================================================================== *
 *  Data + demo simulation
 * ====================================================================== */
const DEMO_PROJECTS = [
  { name: 'Aurelius', type: 'trading_bot', health: 'ok', device: 'forge-01', metrics: { profit_today: 418.2 } },
  { name: 'Helios', type: 'trading_bot', health: 'ok', device: 'forge-01', metrics: { profit_today: 196.4 } },
  { name: 'Aegis Dashboard', type: 'dashboard', health: 'ok', device: 'core-01' },
  { name: 'Gateway', type: 'api', health: 'warning', device: 'core-01' },
  { name: 'Oracle', type: 'research', health: 'ok', device: 'lab-02' },
  { name: 'Commerce', type: 'web', health: 'ok', device: 'edge-03' },
  { name: 'Sentinel', type: 'service', health: 'error', device: 'edge-03' },
];
let DEMO = false;
function simTick() {
  if (!DEMO || !disciples.length) return; const projRooms = rooms.filter((r) => r.data);
  disciples.forEach((d) => { if (!d.data.__sim) d.data.__sim = { state: 'idle' }; });
  const d = disciples[(Math.random() * disciples.length) | 0], roll = Math.random(), s = d.data.__sim.state;
  if (s === 'idle') { if (roll < 0.5 && projRooms.length) d.data.__sim = { state: 'working', room: projRooms[(Math.random() * projRooms.length) | 0].id };
    else if (roll < 0.66) d.data.__sim = { state: 'roaming' }; else if (roll < 0.74) d.data.__sim = { state: 'meditate' }; }
  else if (s === 'working' && roll < 0.32) { d.data.__sim = { state: 'idle' }; if (Math.random() < 0.5) celebrate(d.gx, d.gy, '#fbbf24', `${d.name}: ${['milestone', 'profit target', 'deploy', 'breakthrough'][(Math.random() * 4) | 0]}`); }
}
let seenChron = null;
async function pollBreakthroughs() {
  const ch = await api('/api/chronicle?limit=20'); if (!ch) return; const entries = ch.recent || [];
  if (seenChron === null) { seenChron = new Set(entries.map((e) => e.id)); return; }
  entries.filter((e) => !seenChron.has(e.id) && ['breakthrough', 'milestone', 'title', 'ascension'].includes(e.kind)).forEach((e) => { const d = disciples.find((x) => x.name === e.agent); if (d) celebrate(d.gx, d.gy, '#a78bfa', `${e.agent}: ${String(e.detail || e.kind).slice(0, 24)}`); });
  entries.forEach((e) => seenChron.add(e.id));
}
async function load() {
  const [ov, ag, cmd] = await Promise.all([api('/api/overview'), api('/api/agents'), api('/api/command')]);
  if (window.__needAuth && !ag) { $('scene-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  DEMO = !!(cmd && cmd.demo); let projects = (ov && ov.projects) || []; if (!projects.length) projects = DEMO_PROJECTS;
  if (!rooms.length || rooms.filter((r) => r.data).length !== projects.length) buildLayout(projects);
  ensureDisciples((ag && ag.agents) || []);
  $('scene-sub').textContent = `${rooms.length} halls · ${disciples.length} disciples · ${DEMO ? 'simulation' : 'live'}`;
}
load(); setInterval(load, 12000); setInterval(simTick, 2400); setInterval(pollBreakthroughs, 9000); setInterval(microTick, 17000);
requestAnimationFrame(frame);
