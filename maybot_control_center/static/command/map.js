import { $, api, esc, money, mountRail } from '/lib.js';

mountRail('map');

/* ====================================================================== *
 *  AEGIS — Living Sect Headquarters (isometric)
 *  A hand-authored 2D isometric base: every project is a physical hall,
 *  every agent is a character that walks the courtyard, works at stations,
 *  meditates, and roams. Canvas2D for crisp, bright, dependable rendering.
 * ====================================================================== */

const canvas = $('scene-canvas');
const ctx = canvas.getContext('2d');
const TW2 = 34, TH2 = 17;                 // half tile width / height (2:1 iso)
const ROOM_W = 5, ROOM_H = 4;             // room footprint in tiles
const cam = { x: 0, y: 0, zoom: 1, userMoved: false };
const view = { cx: 0, cy: 0, w: 0, h: 0, dpr: 1 };

/* ---------------- palette / room identities ---------------- */
const BG0 = '#070812', BG1 = '#0d1024';
const HEALTH = { ok: '#34d399', warning: '#fbbf24', error: '#fb5e7e', unknown: '#8b92ac' };
const KIND = {
  hall:        { name: 'Sect Hall',          floor: '#20264a', wall: '#2c356a', accent: '#a78bfa', robe: '#b9a7ff', fx: '✦', prop: 'altar' },
  market:      { name: 'Trading Pavilion',   floor: '#13261f', wall: '#1c3a2e', accent: '#34d399', robe: '#f5c542', fx: '$', prop: 'charts' },
  engineering: { name: 'Engineering Hall',   floor: '#122039', wall: '#1b3055', accent: '#38bdf8', robe: '#5ac8ff', fx: '<>', prop: 'monitors' },
  library:     { name: 'Research Library',   floor: '#1d1838', wall: '#2a2356', accent: '#c4b5fd', robe: '#c4b5fd', fx: '✷', prop: 'scrolls' },
  comms:       { name: 'Comms Tower',        floor: '#0f2238', wall: '#163a52', accent: '#22d3ee', robe: '#3fe0e0', fx: '⇡', prop: 'tower' },
  mission:     { name: 'Mission Hall',       floor: '#291a33', wall: '#3a2550', accent: '#fb7185', robe: '#fbbf24', fx: '⚑', prop: 'board' },
  server:      { name: 'Server Core',        floor: '#0e1730', wall: '#172548', accent: '#60a5fa', robe: '#7bb0ff', fx: '▦', prop: 'racks' },
  cultivation: { name: 'Cultivation Chamber', floor: '#1e1940', wall: '#2a2160', accent: '#a78bfa', robe: '#caa9ff', fx: '☯', prop: 'mats' },
  commerce:    { name: 'Commerce Pavilion',  floor: '#231d10', wall: '#3a2f18', accent: '#fbbf24', robe: '#fbbf24', fx: '❖', prop: 'banner' },
};
function kindForType(type) {
  const t = String(type || '').toLowerCase();
  if (t.includes('trad') || t.includes('bot')) return 'market';
  if (t.includes('api') || t.includes('gateway') || t.includes('service')) return 'comms';
  if (t.includes('research') || t.includes('ml') || t.includes('ai') || t.includes('llm')) return 'library';
  if (t.includes('market') || t.includes('commerce') || t.includes('shop')) return 'commerce';
  return 'engineering';
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

/* ====================================================================== *
 *  Layout — build rooms on a grid with the Sect Hall at the centre
 * ====================================================================== */
const rooms = [];
function buildLayout(projects) {
  rooms.length = 0;
  const fixed = [
    { id: '__hall', title: 'Sect Hall', kind: 'hall' },
    { id: '__mission', title: 'Mission Hall', kind: 'mission' },
    { id: '__cultivation', title: 'Cultivation Chamber', kind: 'cultivation' },
    { id: '__server', title: 'Server Core', kind: 'server' },
  ];
  const projRooms = projects.map((p) => ({ id: p.device + ':' + p.name, title: p.name, kind: kindForType(p.type), data: p }));
  const all = [fixed[0], ...projRooms, fixed[1], fixed[2], fixed[3]];
  const C = Math.max(3, Math.ceil(Math.sqrt(all.length)));
  const rowsN = Math.ceil(all.length / C);
  const STRIDE_X = ROOM_W + 3, STRIDE_Y = ROOM_H + 3;
  const centerCell = Math.floor(rowsN / 2) * C + Math.floor(C / 2);
  const order = [];           // cell index -> room
  order[centerCell] = all[0]; // hall in the middle
  let q = 1;
  for (let cell = 0; cell < rowsN * C && q < all.length; cell++) { if (cell === centerCell) continue; order[cell] = all[q++]; }
  order.forEach((r, cell) => {
    if (!r) return;
    const col = cell % C, row = (cell / C) | 0;
    const gx = col * STRIDE_X, gy = row * STRIDE_Y;
    const K = KIND[r.kind];
    rooms.push({ ...r, K, gx, gy, w: ROOM_W, h: ROOM_H,
      cx: gx + ROOM_W / 2, cyc: gy + ROOM_H / 2,
      door: { gx: gx + ROOM_W / 2, gy: gy + ROOM_H + 0.6 },
      occupants: new Set(), depth: gx + gy + ROOM_W / 2 + ROOM_H / 2, fxT: 0 });
  });
  autoFit();
}
const roomById = (id) => rooms.find((r) => r.id === id);
const hall = () => roomById('__hall');
const chamber = () => roomById('__cultivation');

function autoFit() {
  if (!rooms.length) return;
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  rooms.forEach((r) => { for (const [gx, gy] of [[r.gx, r.gy], [r.gx + r.w, r.gy], [r.gx + r.w, r.gy + r.h], [r.gx, r.gy + r.h]]) {
    const wx = (gx - gy) * TW2, wy = (gx + gy) * TH2; minX = Math.min(minX, wx); maxX = Math.max(maxX, wx); minY = Math.min(minY, wy); maxY = Math.max(maxY, wy); } });
  cam.x = (minX + maxX) / 2; cam.y = (minY + maxY) / 2;
  const zx = (view.w * 0.84) / (maxX - minX + 80), zy = (view.h * 0.66) / (maxY - minY + 120);
  cam.zoom = Math.max(0.42, Math.min(1.5, Math.min(zx, zy)));
}

/* ====================================================================== *
 *  Disciples (characters)
 * ====================================================================== */
const ROLE_ROBE = { working: null, idle: '#9a8cff', roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' };
const disciples = [];
function plazaSpot() { const h = hall(); const a = Math.random() * 6.28, r = 2 + Math.random() * 5;
  return { gx: (h ? h.cx : 0) + Math.cos(a) * r, gy: (h ? h.cyc : 0) + 2 + Math.sin(a) * r }; }

function makeDisciple(ag, i) {
  const home = plazaSpot();
  return { name: ag.name, data: ag, gx: home.gx, gy: home.gy, tx: home.gx, ty: home.gy,
    state: 'idle', room: null, speed: 1.7 + Math.random() * 0.7, phase: Math.random() * 6.28,
    pause: 0, alpha: 1, roamPhase: null, idx: i, robe: '#9a8cff', home };
}
function ensureDisciples(agents) {
  const have = new Set(disciples.map((d) => d.name));
  agents.forEach((a, i) => { if (!have.has(a.name)) disciples.push(makeDisciple(a, i)); });
  disciples.forEach((d) => { const fresh = agents.find((a) => a.name === d.name); if (fresh) { if (d.data.__sim) fresh.__sim = d.data.__sim; d.data = fresh; } });
}

function matchRoom(task) { if (!task) return null; const t = String(task).toLowerCase();
  return rooms.find((r) => r.data && t.includes(String(r.title).toLowerCase())) || null; }
function workRoom(d) {
  const sim = d.data.__sim;
  if (sim && sim.room) return roomById(sim.room) || null;
  return matchRoom(d.data.current_task) || rooms.find((r) => r.data) || null;
}
function interiorSpot(r, d) {
  const a = (d.name.charCodeAt(0) + d.idx * 2.3), rad = 1.2;
  return { gx: r.cx + Math.cos(a) * rad, gy: r.cyc + Math.sin(a) * rad - 0.3 };
}

function deriveState(d) {
  const ag = d.data, cult = ag.cultivation || {}, sim = ag.__sim;
  const st = sim ? sim.state : (cult.in_seclusion ? 'meditate' : cult.in_roaming ? 'roaming'
    : (ag.status === 'working' || ag.status === 'queued') ? 'working' : ag.status === 'error' ? 'error' : 'idle');
  if (st === 'working') {
    const r = workRoom(d);
    if (!r) { setIdle(d); return; }
    if (d.room !== r) { if (d.room) d.room.occupants.delete(d); d.room = r; r.occupants.add(d); d.spot = interiorSpot(r, d); }
    const near = Math.hypot(d.gx - d.spot.gx, d.gy - d.spot.gy) < 0.6;
    d.state = near ? 'working' : 'traveling';
    d.tx = d.spot.gx; d.ty = d.spot.gy;
  } else {
    if (d.room) { d.room.occupants.delete(d); d.room = null; }
    if (st === 'roaming') { if (d.state !== 'roaming') { d.state = 'roaming'; d.roamPhase = null; } }
    else if (st === 'meditate') { d.state = 'meditate'; const c = chamber(); if (c) { d.tx = c.cx + (d.idx % 3 - 1) * 1.1; d.ty = c.cyc + 0.4; } }
    else if (st === 'error') { d.state = 'error'; }
    else setIdle(d);
  }
}
function setIdle(d) { if (d.state !== 'idle') { d.state = 'idle'; d.pause = 0; } }

/* ====================================================================== *
 *  Movement
 * ====================================================================== */
function step(d, dt, t) {
  if (d.state === 'roaming') return stepRoam(d, dt, t);
  d.alpha = Math.min(1, d.alpha + dt * 2);
  const dx = d.tx - d.gx, dy = d.ty - d.gy, dist = Math.hypot(dx, dy);
  if (dist > 0.05) {
    const v = Math.min(dist, d.speed * dt);
    d.gx += (dx / dist) * v; d.gy += (dy / dist) * v;
    d.phase += dt * 9; d.moving = true;
  } else {
    d.moving = false;
    if (d.state === 'idle') { d.pause -= dt; if (d.pause <= 0) { const s = plazaSpot(); d.tx = s.gx; d.ty = s.gy; d.pause = 2 + Math.random() * 5; } }
  }
}
function stepRoam(d, dt, t) {
  if (!d.roamPhase) { d.roamPhase = 'out'; const h = hall(); const ang = Math.atan2(d.gy - (h ? h.cyc : 0), d.gx - (h ? h.cx : 0)) || Math.random() * 6.28;
    d.tx = d.gx + Math.cos(ang) * 14; d.ty = d.gy + Math.sin(ang) * 14; }
  const dx = d.tx - d.gx, dy = d.ty - d.gy, dist = Math.hypot(dx, dy);
  if (dist > 0.05) { const v = Math.min(dist, d.speed * dt); d.gx += (dx / dist) * v; d.gy += (dy / dist) * v; d.phase += dt * 9; d.moving = true; }
  if (d.roamPhase === 'out' && dist < 0.5) { d.roamPhase = 'gone'; d.goneUntil = t + 6 + Math.random() * 8; }
  if (d.roamPhase === 'gone') { d.alpha = Math.max(0, d.alpha - dt); if (t > d.goneUntil) { d.roamPhase = 'back'; const s = plazaSpot(); d.tx = s.gx; d.ty = s.gy; } }
  else if (d.roamPhase === 'back') { d.alpha = Math.min(1, d.alpha + dt); if (dist < 0.5) { d.roamPhase = null; if (d.data.__sim) d.data.__sim = { state: 'idle' }; } }
}

/* ====================================================================== *
 *  Drawing
 * ====================================================================== */
function diamond(p, hw, hh) { ctx.beginPath(); ctx.moveTo(p.x, p.y - hh); ctx.lineTo(p.x + hw, p.y); ctx.lineTo(p.x, p.y + hh); ctx.lineTo(p.x - hw, p.y); ctx.closePath(); }

function drawRoom(r, t) {
  const z = cam.zoom, K = r.K;
  const A = toScreen(r.gx, r.gy), B = toScreen(r.gx + r.w, r.gy), Cc = toScreen(r.gx + r.w, r.gy + r.h), D = toScreen(r.gx, r.gy + r.h);
  const occ = r.occupants.size, busy = Math.min(1, occ * 0.5);
  const TH = 16 * z;          // slab thickness
  // ground shadow
  ctx.save(); ctx.globalAlpha = 0.5; ctx.fillStyle = '#000';
  ctx.beginPath(); ctx.moveTo(A.x, A.y + TH + 4); ctx.lineTo(B.x, B.y + TH + 4); ctx.lineTo(Cc.x, Cc.y + TH + 8); ctx.lineTo(D.x, D.y + TH + 8); ctx.closePath(); ctx.filter = 'blur(4px)'; ctx.fill(); ctx.restore();
  // slab sides
  ctx.fillStyle = shade(K.floor, -0.45);
  ctx.beginPath(); ctx.moveTo(D.x, D.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(D.x, D.y + TH); ctx.closePath(); ctx.fill();
  ctx.fillStyle = shade(K.floor, -0.6);
  ctx.beginPath(); ctx.moveTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(B.x, B.y + TH); ctx.closePath(); ctx.fill();
  // floor
  const g = ctx.createLinearGradient(A.x, A.y, Cc.x, Cc.y); g.addColorStop(0, shade(K.floor, 0.12)); g.addColorStop(1, K.floor);
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.fill();
  // floor grid
  ctx.strokeStyle = 'rgba(255,255,255,.045)'; ctx.lineWidth = 1;
  for (let i = 1; i < r.w; i++) { const p1 = toScreen(r.gx + i, r.gy), p2 = toScreen(r.gx + i, r.gy + r.h); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke(); }
  for (let i = 1; i < r.h; i++) { const p1 = toScreen(r.gx, r.gy + i), p2 = toScreen(r.gx + r.w, r.gy + i); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke(); }
  // accent border (health-tinted if troubled)
  const trouble = r.data && (r.data.health === 'error' || r.data.health === 'warning');
  ctx.strokeStyle = trouble ? HEALTH[r.data.health] : K.accent; ctx.lineWidth = 2; ctx.globalAlpha = 0.65 + busy * 0.35;
  ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1;
  // back walls (NW + NE edges) — low, so interior stays visible
  drawWall(A, B, K, z, busy);   // back-right
  drawWall(A, D, K, z, busy);   // back-left
  // props
  drawProp(r, t, busy);
  // activity beacon + work fx
  if (occ > 0) drawWorkFX(r, t, busy);
  // hover/selection highlight
  if (hover.room === r || selected.room === r) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.globalAlpha = .8;
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1; }
}

function drawWall(p1, p2, K, z, busy) {
  const H = 22 * z;
  ctx.fillStyle = shade(K.wall, -0.05);
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(p2.x, p2.y - H); ctx.lineTo(p1.x, p1.y - H); ctx.closePath(); ctx.fill();
  // glowing trim along the top
  ctx.strokeStyle = K.accent; ctx.globalAlpha = 0.5 + busy * 0.4; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y - H); ctx.lineTo(p2.x, p2.y - H); ctx.stroke(); ctx.globalAlpha = 1;
}

function drawProp(r, t, busy) {
  const c = toScreen(r.cx, r.cyc), z = cam.zoom, K = r.K, A = K.accent;
  ctx.save(); ctx.translate(c.x, c.y - 6 * z); const s = z;
  ctx.lineWidth = 2 * s; ctx.strokeStyle = A; ctx.fillStyle = A;
  const glow = (on) => { ctx.shadowColor = A; ctx.shadowBlur = (on ? 10 : 0) * s; };
  switch (K.prop) {
    case 'charts': { glow(busy); for (let i = 0; i < 3; i++) { const bx = (i - 1) * 12 * s, bh = (6 + (i * 5 + (t * 30 % 14))) * s;
      ctx.fillStyle = i === 1 ? '#34d399' : A; ctx.fillRect(bx - 3 * s, -bh, 6 * s, bh); }
      ctx.strokeStyle = '#f5c542'; ctx.beginPath(); ctx.moveTo(-16 * s, -4 * s); ctx.lineTo(-4 * s, -12 * s); ctx.lineTo(6 * s, -7 * s); ctx.lineTo(16 * s, -16 * s); ctx.stroke(); break; }
    case 'monitors': { glow(busy); for (let i = -1; i <= 1; i++) { ctx.fillStyle = shade('#0a1426', 0.1); ctx.fillRect(i * 13 * s - 5 * s, -14 * s, 10 * s, 10 * s);
      ctx.strokeStyle = A; ctx.strokeRect(i * 13 * s - 5 * s, -14 * s, 10 * s, 10 * s);
      ctx.fillStyle = A; for (let l = 0; l < 3; l++) ctx.fillRect(i * 13 * s - 3 * s, -12 * s + l * 3 * s, (4 + (l + i + (t | 0)) % 4) * s, 1.4 * s); } break; }
    case 'scrolls': { glow(busy); for (let i = -1; i <= 1; i++) { ctx.fillStyle = shade(A, -0.2); ctx.fillRect(i * 11 * s - 3 * s, -16 * s, 6 * s, 14 * s);
      ctx.fillStyle = '#efe6c8'; ctx.fillRect(i * 11 * s - 2 * s, -15 * s, 4 * s, 12 * s); } break; }
    case 'tower': { glow(busy); ctx.beginPath(); ctx.moveTo(-6 * s, 0); ctx.lineTo(-2 * s, -20 * s); ctx.lineTo(2 * s, -20 * s); ctx.lineTo(6 * s, 0); ctx.closePath(); ctx.stroke();
      for (let i = 1; i <= 3; i++) { ctx.globalAlpha = 0.8 - i * 0.2 + Math.sin(t * 3) * 0.15; ctx.beginPath(); ctx.arc(0, -22 * s, i * 6 * s, Math.PI, 0); ctx.stroke(); } ctx.globalAlpha = 1; break; }
    case 'board': { glow(busy); ctx.fillStyle = shade('#1a1326', 0.1); ctx.fillRect(-15 * s, -18 * s, 30 * s, 16 * s); ctx.strokeStyle = A; ctx.strokeRect(-15 * s, -18 * s, 30 * s, 16 * s);
      ctx.fillStyle = '#fbbf24'; for (let i = 0; i < 3; i++) ctx.fillRect(-12 * s + i * 9 * s, -15 * s, 6 * s, 10 * s); break; }
    case 'racks': { glow(busy); for (let i = -1; i <= 1; i++) { ctx.fillStyle = shade('#0c1730', 0.15); ctx.fillRect(i * 11 * s - 4 * s, -18 * s, 8 * s, 16 * s); ctx.strokeStyle = A; ctx.strokeRect(i * 11 * s - 4 * s, -18 * s, 8 * s, 16 * s);
      for (let l = 0; l < 4; l++) { ctx.fillStyle = (l + i + (t * 2 | 0)) % 3 ? '#34d399' : A; ctx.fillRect(i * 11 * s - 2 * s, -16 * s + l * 4 * s, 2 * s, 2 * s); } } break; }
    case 'mats': { glow(true); for (let i = -1; i <= 1; i++) { ctx.fillStyle = shade(A, -0.3); ctx.beginPath(); ctx.ellipse(i * 12 * s, -2 * s, 5 * s, 2.5 * s, 0, 0, 6.28); ctx.fill(); }
      ctx.globalAlpha = 0.4 + Math.sin(t * 2) * 0.2; ctx.beginPath(); ctx.arc(0, -10 * s, 8 * s, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1; break; }
    case 'banner': { glow(busy); ctx.fillStyle = A; ctx.fillRect(-12 * s, -20 * s, 24 * s, 4 * s); ctx.beginPath(); ctx.moveTo(-12 * s, -16 * s); ctx.lineTo(12 * s, -16 * s); ctx.lineTo(8 * s, -6 * s); ctx.lineTo(-8 * s, -6 * s); ctx.closePath(); ctx.fill(); break; }
    case 'altar': default: { glow(true); ctx.fillStyle = shade(A, -0.2); ctx.beginPath(); ctx.moveTo(-9 * s, 0); ctx.lineTo(9 * s, 0); ctx.lineTo(6 * s, -10 * s); ctx.lineTo(-6 * s, -10 * s); ctx.closePath(); ctx.fill();
      const fy = -10 * s - (4 + Math.sin(t * 4) * 2) * s; ctx.fillStyle = A; ctx.beginPath(); ctx.ellipse(0, fy, 4 * s, 7 * s, 0, 0, 6.28); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.globalAlpha = .8; ctx.beginPath(); ctx.ellipse(0, fy + 2 * s, 2 * s, 3.5 * s, 0, 0, 6.28); ctx.fill(); ctx.globalAlpha = 1; break; }
  }
  ctx.restore();
}

const FX = [];
function drawWorkFX(r, t, busy) {
  const z = cam.zoom, c = toScreen(r.cx, r.cyc);
  for (let i = 0; i < 3 + r.occupants.size; i++) {
    const ph = (t * (0.5 + busy) + i * 0.7) % 2;
    ctx.globalAlpha = Math.max(0, 0.5 - ph * 0.25) * (0.5 + busy);
    ctx.fillStyle = r.K.accent; ctx.font = `${(9 + busy * 3) * z}px system-ui`;
    ctx.fillText(r.K.fx, c.x + ((i % 3) - 1) * 14 * z, c.y - 18 * z - ph * 22 * z);
  }
  ctx.globalAlpha = 1;
}

function drawDisciple(d, t) {
  const p = toScreen(d.gx, d.gy), z = cam.zoom;
  const robe = d.state === 'working' && d.room ? d.room.K.robe : (ROLE_ROBE[d.state] || '#9a8cff');
  const hovd = hover.disc === d, sel = selected.disc === d, foll = followed === d;
  const sc = z * (hovd || foll ? 1.12 : 1);
  ctx.globalAlpha = d.alpha;
  // shadow
  ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 7 * sc, 3 * sc, 0, 0, 6.28); ctx.fill();
  const bob = d.moving ? Math.abs(Math.sin(d.phase)) * 2.4 * sc : (d.state === 'working' ? Math.abs(Math.sin(t * 5 + d.phase)) * 1.5 * sc : Math.sin(t * 2 + d.phase) * 0.8 * sc);
  const fy = p.y - bob;
  // body / robe
  const bodyH = 17 * sc, headR = 4.2 * sc;
  const grd = ctx.createLinearGradient(0, fy - bodyH, 0, fy); grd.addColorStop(0, shade(robe, 0.18)); grd.addColorStop(1, shade(robe, -0.25));
  ctx.fillStyle = grd; ctx.strokeStyle = shade(robe, -0.5); ctx.lineWidth = 1 * sc;
  ctx.beginPath(); ctx.moveTo(p.x, fy - bodyH + 2 * sc); ctx.lineTo(p.x + 6 * sc, fy); ctx.quadraticCurveTo(p.x, fy + 2 * sc, p.x - 6 * sc, fy); ctx.closePath(); ctx.fill(); ctx.stroke();
  // sash
  ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth = 1.4 * sc; ctx.beginPath(); ctx.moveTo(p.x - 4 * sc, fy - 7 * sc); ctx.lineTo(p.x + 4 * sc, fy - 9 * sc); ctx.stroke();
  // head + hood
  ctx.fillStyle = '#f2e2c8'; ctx.beginPath(); ctx.arc(p.x, fy - bodyH + 2 * sc, headR, 0, 6.28); ctx.fill();
  ctx.fillStyle = shade(robe, -0.1); ctx.beginPath(); ctx.arc(p.x, fy - bodyH + 1 * sc, headR + 0.4 * sc, Math.PI, 0); ctx.fill();
  // status pip
  const pip = { working: '#34d399', idle: '#9a8cff', traveling: '#cbb9ff', roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' }[d.state] || '#9a8cff';
  ctx.fillStyle = pip; if (d.state === 'working' || d.state === 'meditate') { ctx.shadowColor = pip; ctx.shadowBlur = 8 * sc; }
  ctx.beginPath(); ctx.arc(p.x + 5 * sc, fy - bodyH + 1 * sc, 1.8 * sc, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
  // name
  if (hovd || foll || sel || cam.zoom > 1.0) {
    ctx.font = `600 ${10 * z}px system-ui`; ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(8,10,20,.7)'; const w = ctx.measureText(d.name).width + 8 * z;
    ctx.fillRect(p.x - w / 2, fy - bodyH - 13 * sc, w, 13 * z);
    ctx.fillStyle = (hovd || foll) ? '#fff' : '#cdd3f0'; ctx.fillText(d.name, p.x, fy - bodyH - 3 * sc); ctx.textAlign = 'left';
  }
  ctx.globalAlpha = 1;
}

/* breakthrough spectacles */
const spectacles = [];
function celebrate(gx, gy, color, text) { spectacles.push({ gx, gy, color, text, t: 0 }); }
function drawSpectacles(dt) {
  for (let i = spectacles.length - 1; i >= 0; i--) {
    const s = spectacles[i]; s.t += dt; const k = s.t / 2.6, p = toScreen(s.gx, s.gy), z = cam.zoom;
    ctx.strokeStyle = s.color; ctx.globalAlpha = Math.max(0, 0.9 - k); ctx.lineWidth = 3 * z;
    ctx.beginPath(); ctx.ellipse(p.x, p.y, (8 + k * 80) * z, (4 + k * 40) * z, 0, 0, 6.28); ctx.stroke();
    ctx.globalAlpha = Math.max(0, 1 - k); ctx.font = `700 ${13 * z}px system-ui`; ctx.textAlign = 'center';
    ctx.fillStyle = '#fff3cf'; ctx.fillText('✦ ' + s.text, p.x, p.y - (24 + k * 26) * z); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
    if (s.t > 2.6) spectacles.splice(i, 1);
  }
}

function drawRoomLabel(r) {
  const p = toScreen(r.cx, r.gy), z = cam.zoom;
  ctx.font = `700 ${12 * z}px system-ui`; ctx.textAlign = 'center';
  const w = ctx.measureText(r.title).width + 16 * z, y = p.y - 40 * z;
  ctx.fillStyle = 'rgba(8,10,20,.72)'; roundRect(p.x - w / 2, y - 13 * z, w, 18 * z, 5 * z); ctx.fill();
  ctx.fillStyle = r.K.accent; ctx.fillText(r.title, p.x, y); ctx.textAlign = 'left';
  if (r.data) { ctx.fillStyle = HEALTH[r.data.health] || HEALTH.unknown; ctx.beginPath(); ctx.arc(p.x - w / 2 + 7 * z, y - 4 * z, 3 * z, 0, 6.28); ctx.fill(); }
}

/* ---------------- helpers ---------------- */
function shade(hex, amt) { const n = parseInt(hex.slice(1), 16); let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const f = (v) => Math.max(0, Math.min(255, Math.round(v + (amt > 0 ? (255 - v) * amt : v * amt))));
  return `rgb(${f(r)},${f(g)},${f(b)})`; }
function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

/* ====================================================================== *
 *  Render loop
 * ====================================================================== */
let last = performance.now(), elapsed = 0, lastDerive = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000); last = now; elapsed += dt; const t = elapsed;
  if (followed) { const p = { x: (followed.gx - followed.gy) * TW2, y: (followed.gx + followed.gy) * TH2 }; cam.x += (p.x - cam.x) * 0.06; cam.y += (p.y - cam.y) * 0.06; }
  if (t - lastDerive > 0.35) { disciples.forEach(deriveState); lastDerive = t; }
  disciples.forEach((d) => step(d, dt, t));

  // background
  const bg = ctx.createLinearGradient(0, 0, 0, view.h); bg.addColorStop(0, BG1); bg.addColorStop(1, BG0);
  ctx.fillStyle = bg; ctx.fillRect(0, 0, view.w, view.h);
  drawCourtyard(t);

  // depth-sorted rooms, then disciples
  rooms.slice().sort((a, b) => a.depth - b.depth).forEach((r) => drawRoom(r, t));
  rooms.forEach(drawRoomLabel);
  disciples.slice().sort((a, b) => (a.gx + a.gy) - (b.gx + b.gy)).forEach((d) => drawDisciple(d, t));
  drawSpectacles(dt);
}
function drawCourtyard(t) {
  if (!rooms.length) return;
  // faint iso ground tiles spanning the base
  let minGx = 1e9, minGy = 1e9, maxGx = -1e9, maxGy = -1e9;
  rooms.forEach((r) => { minGx = Math.min(minGx, r.gx); minGy = Math.min(minGy, r.gy); maxGx = Math.max(maxGx, r.gx + r.w); maxGy = Math.max(maxGy, r.gy + r.h); });
  ctx.strokeStyle = 'rgba(124,92,255,.05)'; ctx.lineWidth = 1;
  for (let gx = minGx - 3; gx <= maxGx + 3; gx += 1) { const a = toScreen(gx, minGy - 3), b = toScreen(gx, maxGy + 3); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
  for (let gy = minGy - 3; gy <= maxGy + 3; gy += 1) { const a = toScreen(minGx - 3, gy), b = toScreen(maxGx + 3, gy); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
}

/* ====================================================================== *
 *  Input — pan / zoom / hover / click
 * ====================================================================== */
const hover = { room: null, disc: null }, selected = { room: null, disc: null };
let followed = null, drag = null;
function pickAt(mx, my) {
  let best = null, bestD = 22;
  disciples.forEach((d) => { const p = toScreen(d.gx, d.gy); const dist = Math.hypot(p.x - mx, p.y - my - 14 * cam.zoom);
    if (d.alpha > 0.3 && dist < bestD) { bestD = dist; best = d; } });
  if (best) return { disc: best };
  const gp = toGrid(mx, my); const r = rooms.find((R) => gp.gx >= R.gx && gp.gx <= R.gx + R.w && gp.gy >= R.gy && gp.gy <= R.gy + R.h);
  return { room: r || null };
}
canvas.addEventListener('mousedown', (e) => { drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false }; });
addEventListener('mousemove', (e) => {
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  if (drag) { const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.hypot(dx, dy) > 4) { drag.moved = true; cam.userMoved = true; followed = null; updateFollowChip();
    cam.x = drag.cx - dx / cam.zoom; cam.y = drag.cy - dy / cam.zoom; } canvas.style.cursor = 'grabbing'; return; }
  const hit = pickAt(mx, my); hover.disc = hit.disc || null; hover.room = hit.disc ? null : hit.room;
  canvas.style.cursor = (hover.disc || hover.room) ? 'pointer' : 'grab';
});
addEventListener('mouseup', (e) => {
  if (drag && !drag.moved) { const r = canvas.getBoundingClientRect(); const hit = pickAt(e.clientX - r.left, e.clientY - r.top);
    if (hit.disc) selectDisc(hit.disc); else if (hit.room) selectRoom(hit.room); }
  drag = null; canvas.style.cursor = 'grab';
});
canvas.addEventListener('wheel', (e) => { e.preventDefault(); cam.userMoved = true;
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const before = toGrid(mx, my); cam.zoom = Math.max(0.4, Math.min(2.4, cam.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
  const after = toGrid(mx, my); cam.x += ((before.gx - after.gx) - (before.gy - after.gy)) * TW2; cam.y += ((before.gx - after.gx) + (before.gy - after.gy)) * TH2;
}, { passive: false });

/* ====================================================================== *
 *  Panels
 * ====================================================================== */
function selectRoom(r) {
  selected.room = r; selected.disc = null;
  const p = r.data, busy = r.occupants.size;
  const who = [...r.occupants].map((d) => esc(d.name)).join(', ') || 'none on site';
  const rows = [
    ['Area', esc(r.K.name)],
    p ? ['Type', esc(p.type || '')] : null,
    p ? ['Host', esc(p.device || '')] : null,
    ['Disciples', busy ? `${busy} working` : '—'],
    p && p.type === 'trading_bot' && Number.isFinite(Number((p.metrics || {}).profit_today)) ? ['PnL Today', money(p.metrics.profit_today)] : null,
  ].filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(r.title)}</div>
    ${p ? `<div class='realm-health health-${esc(p.health || 'unknown')}'>${esc(p.health || 'unknown')}</div>` : ''}
    <div class='kvs'>${rows}</div>
    <div class='muted' style='font-size:11.5px;margin-top:10px'>On site: ${who}</div>
    <div class='realm-actions'>
      <button class='cbtn' id='r-logs'>View Logs</button>
      <button class='cbtn' id='r-assign'>Assign Disciple</button>
    </div>`;
  $('r-logs').onclick = () => { localStorage.setItem('tab', 'overview'); location.href = '/classic'; };
  $('r-assign').onclick = () => { localStorage.setItem('tab', 'disciples'); location.href = '/classic'; };
}
function selectDisc(d) {
  selected.disc = d; selected.room = null; followed = d; cam.userMoved = true; updateFollowChip();
  const ag = d.data, c = ag.cultivation || {}, g = ag.governance || {};
  const where = d.room ? `working at <b>${esc(d.room.title)}</b>` : d.state === 'roaming' ? 'roaming beyond the realm'
    : d.state === 'meditate' ? 'meditating in the Cultivation Chamber' : 'at the Sect Hall';
  const rows = [
    ['Rank', esc(g.is_leader ? 'Sect Leader' : c.rank_title || 'Disciple')],
    ['Realm', esc(c.realm_name || 'Mortal')],
    ['Status', esc(ag.status || 'idle')],
    ag.current_task ? ['Task', esc(String(ag.current_task).slice(0, 64))] : null,
    ['Tasks done', ag.tasks_done || 0],
  ].filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(d.name)}</div>
    <div class='muted' style='margin:8px 0 2px;font-size:12.5px'>Following — currently ${where}.</div>
    <div class='kvs'>${rows}</div>
    <div class='realm-actions'>
      <button class='cbtn' id='r-cham'>Open Dossier</button>
      <button class='cbtn' id='r-rel'>Release Camera</button>
    </div>`;
  $('r-cham').onclick = () => { location.href = '/chamber'; };
  $('r-rel').onclick = () => { followed = null; updateFollowChip(); };
}
function updateFollowChip() {
  const chip = $('follow-chip');
  if (!followed) { chip.hidden = true; return; }
  chip.hidden = false; chip.innerHTML = `👁 Following <b>${esc(followed.name)}</b> · <span class='fc-x'>release ✕</span>`;
  chip.querySelector('.fc-x').onclick = () => { followed = null; updateFollowChip(); };
}

/* legend */
$('legend').innerHTML = [['#34d399', 'working'], ['#9a8cff', 'idle'], ['#fbbf24', 'roaming'], ['#fb5e7e', 'needs aid']]
  .map(([c, l]) => `<span class='lg'><i class='lg-dot' style='background:${c};color:${c}'></i>${l}</span>`).join('');

function renderRoamTicker() {
  const roamers = disciples.filter((d) => d.state === 'roaming');
  const el = $('roam'); if (!roamers.length) { el.hidden = true; return; } el.hidden = false;
  const verbs = ['exploring external markets', 'gathering intelligence', 'researching independently', 'seeking rare techniques', 'returning from a mission'];
  el.innerHTML = `<div class='panel-title'>Beyond the Realm</div>` + roamers.map((d, i) =>
    `<div class='roam-row'>🌄 <b>${esc(d.name)}</b> is ${verbs[(d.name.charCodeAt(0) + i) % verbs.length]}…</div>`).join('');
}
setInterval(renderRoamTicker, 1200);

/* ====================================================================== *
 *  Resize
 * ====================================================================== */
function resize() {
  view.dpr = Math.min(devicePixelRatio || 1, 2);
  view.w = innerWidth; view.h = innerHeight;
  canvas.width = view.w * view.dpr; canvas.height = view.h * view.dpr;
  canvas.style.width = view.w + 'px'; canvas.style.height = view.h + 'px';
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
  view.cx = view.w / 2; view.cy = view.h * 0.52;
  if (!cam.userMoved) autoFit();
}
addEventListener('resize', resize); resize();

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
  if (!DEMO || !disciples.length) return;
  const projRooms = rooms.filter((r) => r.data);
  disciples.forEach((d) => { if (!d.data.__sim) d.data.__sim = { state: 'idle' }; });
  const d = disciples[(Math.random() * disciples.length) | 0], roll = Math.random(), s = d.data.__sim.state;
  if (s === 'idle') {
    if (roll < 0.5 && projRooms.length) d.data.__sim = { state: 'working', room: projRooms[(Math.random() * projRooms.length) | 0].id };
    else if (roll < 0.68) d.data.__sim = { state: 'roaming' };
    else if (roll < 0.76) d.data.__sim = { state: 'meditate' };
  } else if (s === 'working' && roll < 0.35) {
    d.data.__sim = { state: 'idle' };
    if (Math.random() < 0.5) celebrate(d.gx, d.gy, '#fbbf24', `${d.name}: ${['milestone', 'profit target', 'deploy', 'breakthrough'][(Math.random() * 4) | 0]}`);
  }
}
let seenChron = null;
async function pollBreakthroughs() {
  const ch = await api('/api/chronicle?limit=20'); if (!ch) return;
  const entries = ch.recent || [];
  if (seenChron === null) { seenChron = new Set(entries.map((e) => e.id)); return; }
  entries.filter((e) => !seenChron.has(e.id) && ['breakthrough', 'milestone', 'title', 'ascension'].includes(e.kind)).forEach((e) => {
    const d = disciples.find((x) => x.name === e.agent); if (d) celebrate(d.gx, d.gy, '#a78bfa', `${e.agent}: ${String(e.detail || e.kind).slice(0, 26)}`);
  });
  entries.forEach((e) => seenChron.add(e.id));
}

async function load() {
  const [ov, ag, cmd] = await Promise.all([api('/api/overview'), api('/api/agents'), api('/api/command')]);
  if (window.__needAuth && !ag) { $('scene-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  DEMO = !!(cmd && cmd.demo);
  let projects = (ov && ov.projects) || [];
  if (!projects.length) projects = DEMO_PROJECTS;
  if (!rooms.length || rooms.filter((r) => r.data).length !== projects.length) buildLayout(projects);
  ensureDisciples((ag && ag.agents) || []);
  $('scene-sub').textContent = `${rooms.length} halls · ${disciples.length} disciples · ${DEMO ? 'simulation' : 'live'}`;
}
load();
setInterval(load, 12000);
setInterval(simTick, 2400);
setInterval(pollBreakthroughs, 9000);
requestAnimationFrame(frame);
