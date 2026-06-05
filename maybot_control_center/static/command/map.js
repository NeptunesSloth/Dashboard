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
 *  Layout — rooms on a grid, Sect Hall (larger) at the centre
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
  const STRIDE_X = 9, STRIDE_Y = 8;
  const centerCell = Math.floor(rowsN / 2) * C + Math.floor(C / 2);
  const order = []; order[centerCell] = all[0]; let q = 1;
  for (let cell = 0; cell < rowsN * C && q < all.length; cell++) { if (cell === centerCell) continue; order[cell] = all[q++]; }
  order.forEach((r, cell) => {
    if (!r) return;
    const col = cell % C, row = (cell / C) | 0;
    const big = r.kind === 'hall';
    const w = big ? 8 : 6, h = big ? 6 : 5;
    const gx = col * STRIDE_X + (big ? -1 : 0), gy = row * STRIDE_Y + (big ? -0.5 : 0);
    const K = KIND[r.kind];
    const room = { ...r, K, gx, gy, w, h, cx: gx + w / 2, cyc: gy + h / 2,
      door: { gx: gx + w / 2, gy: gy + h + 0.6 }, occupants: new Set(), depth: gx + gy + w / 2 + h / 2 };
    furnish(room);
    rooms.push(room);
  });
  centerOnHall();
}
const roomById = (id) => rooms.find((r) => r.id === id);
const hall = () => roomById('__hall');
const chamber = () => roomById('__cultivation');

function centerOnHall() {
  const h = hall(); if (!h) return;
  cam.x = (h.cx - h.cyc) * TW2; cam.y = (h.cx + h.cyc) * TH2;
  cam.zoom = Math.max(0.55, Math.min(1.0, view.w / 2000 + 0.55));
}

/* furniture + work-stations per room kind (positions are room-relative tiles) */
function furnish(r) {
  const W = r.w, H = r.h, f = [], st = [];
  const back = 1.0, midY = H * 0.5;
  const push = (type, gx, gy, opt) => f.push({ type, gx, gy, ...opt });
  switch (r.kind) {
    case 'market':
      for (let i = 0; i < 3; i++) { const x = 1.2 + i * 1.8; push('desk', x, back); push('screen', x, back - 0.1, { content: 'chart' }); st.push([x, back + 1.2]); }
      push('holo', W / 2, midY + 0.6, { content: 'graph' }); break;
    case 'engineering':
      for (let i = 0; i < 3; i++) { const x = 1.2 + i * 1.8; push('desk', x, back); push('screen', x, back - 0.1, { content: 'code' }); st.push([x, back + 1.2]); }
      push('table', W / 2 - 0.5, midY + 1, { content: 'blueprint' }); break;
    case 'library':
      for (let i = 0; i < 4; i++) push('shelf', 0.8 + i * 1.3, back - 0.2);
      push('table', W / 2 - 0.5, midY + 0.6, { content: 'diagram' }); st.push([W / 2 - 0.6, midY + 1.6]); st.push([W / 2 + 0.6, midY + 1.6]); break;
    case 'comms':
      push('tower', W / 2 - 0.5, back + 0.4); push('desk', 1.4, H - 1.6); push('desk', W - 2.4, H - 1.6);
      st.push([1.6, H - 0.6]); st.push([W - 2.2, H - 0.6]); break;
    case 'mission':
      push('board', W / 2 - 1, back - 0.2); push('table', W / 2 - 0.5, midY + 0.8, { content: 'plan' });
      st.push([W / 2 - 1, midY + 1.7]); st.push([W / 2 + 0.6, midY + 1.7]); break;
    case 'server':
      for (let i = 0; i < 4; i++) push('rack', 1 + i * 1.2, back + 0.2 + (i % 2) * 1.6);
      push('conduit', 0.6, H - 1, { to: [W - 0.6, H - 1] }); st.push([W / 2, H - 0.8]); break;
    case 'cultivation':
      for (let i = 0; i < 3; i++) { push('mat', 1.4 + i * 1.6, midY); st.push([1.4 + i * 1.6, midY]); }
      push('crystal', W / 2 - 0.4, back + 0.2); break;
    case 'commerce':
      push('banner', W / 2 - 1, back - 0.3); push('counter', W / 2 - 1, midY + 0.6); st.push([W / 2 - 0.4, midY + 1.6]); break;
    case 'hall': default:
      push('throne', W / 2 - 0.8, back - 0.2); push('rug', W / 2 - 1.6, midY); push('brazier', 1, back); push('brazier', W - 1.6, back); break;
  }
  r.furniture = f; r.stations = st.length ? st : [[W / 2, H * 0.6]];
}

/* ====================================================================== *
 *  Disciples
 * ====================================================================== */
const ROLE_ROBE = { idle: '#9a8cff', roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' };
const disciples = [];
function hallSpot() { const h = hall(); if (!h) return { gx: 0, gy: 0 };
  return { gx: h.gx + 1 + Math.random() * (h.w - 2), gy: h.gy + h.h * 0.45 + Math.random() * (h.h * 0.5) }; }

function makeDisciple(ag, i) {
  const s = hallSpot();
  return { name: ag.name, data: ag, gx: s.gx, gy: s.gy, tx: s.gx, ty: s.gy, state: 'idle', room: null,
    speed: 1.7 + Math.random() * 0.7, phase: Math.random() * 6.28, pause: 0, alpha: 1, roamPhase: null,
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
    if (d.state === 'idle') { d.pause -= dt; if (d.pause <= 0) { const s = hallSpot(); d.tx = s.gx; d.ty = s.gy; d.pause = 2 + Math.random() * 5; } }
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
function drawRoom(r, t) {
  const z = cam.zoom, K = r.K, occ = r.occupants.size, busy = Math.min(1, occ * 0.45);
  const A = toScreen(r.gx, r.gy), B = toScreen(r.gx + r.w, r.gy), Cc = toScreen(r.gx + r.w, r.gy + r.h), D = toScreen(r.gx, r.gy + r.h);
  const TH = 17 * z;
  // ground shadow
  ctx.save(); ctx.globalAlpha = 0.45; ctx.fillStyle = '#000'; ctx.filter = 'blur(5px)';
  ctx.beginPath(); ctx.moveTo(A.x, A.y + TH + 5); ctx.lineTo(B.x, B.y + TH + 5); ctx.lineTo(Cc.x, Cc.y + TH + 10); ctx.lineTo(D.x, D.y + TH + 10); ctx.closePath(); ctx.fill(); ctx.restore();
  // slab sides
  ctx.fillStyle = shade(K.floor, -0.5); ctx.beginPath(); ctx.moveTo(D.x, D.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(D.x, D.y + TH); ctx.closePath(); ctx.fill();
  ctx.fillStyle = shade(K.floor, -0.62); ctx.beginPath(); ctx.moveTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(Cc.x, Cc.y + TH); ctx.lineTo(B.x, B.y + TH); ctx.closePath(); ctx.fill();
  // floor
  const g = ctx.createLinearGradient(A.x, A.y, Cc.x, Cc.y); g.addColorStop(0, shade(K.floor, 0.14)); g.addColorStop(1, K.floor);
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.fill();
  // activity floor-glow
  if (busy > 0) { ctx.save(); ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.clip();
    const c = toScreen(r.cx, r.cyc); const rg = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, 120 * z); rg.addColorStop(0, K.accent); rg.addColorStop(1, 'transparent');
    ctx.globalAlpha = 0.12 + busy * 0.16; ctx.fillStyle = rg; ctx.fillRect(c.x - 140 * z, c.y - 140 * z, 280 * z, 280 * z); ctx.restore(); }
  // floor grid
  ctx.strokeStyle = 'rgba(255,255,255,.04)'; ctx.lineWidth = 1;
  for (let i = 1; i < r.w; i++) { const a = toScreen(r.gx + i, r.gy), b = toScreen(r.gx + i, r.gy + r.h); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
  for (let i = 1; i < r.h; i++) { const a = toScreen(r.gx, r.gy + i), b = toScreen(r.gx + r.w, r.gy + i); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
  // accent border
  const trouble = r.data && (r.data.health === 'error' || r.data.health === 'warning');
  ctx.strokeStyle = trouble ? HEALTH[r.data.health] : K.accent; ctx.lineWidth = 2; ctx.globalAlpha = 0.6 + busy * 0.4;
  ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1;
  // back walls
  drawWall(A, B, K, busy); drawWall(A, D, K, busy);
  // furniture
  r.furniture.forEach((it) => drawFurniture(r, it, t, busy));
  // selection
  if (hover.room === r || selected.room === r) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.globalAlpha = .85;
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.lineTo(Cc.x, Cc.y); ctx.lineTo(D.x, D.y); ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1; }
}
function drawWall(p1, p2, K, busy) {
  const H = 26 * cam.zoom;
  ctx.fillStyle = shade(K.wall, -0.05); ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(p2.x, p2.y - H); ctx.lineTo(p1.x, p1.y - H); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = K.accent; ctx.globalAlpha = 0.45 + busy * 0.4; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(p1.x, p1.y - H); ctx.lineTo(p2.x, p2.y - H); ctx.stroke(); ctx.globalAlpha = 1;
}

function drawFurniture(r, it, t, busy) {
  const A = r.K.accent, gx = r.gx + it.gx, gy = r.gy + it.gy, z = cam.zoom, on = busy > 0;
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
  }
  ctx.globalAlpha = 1; ctx.shadowBlur = 0;
}

/* rising work glyphs above busy rooms */
function drawWorkFX(r, t) {
  const occ = r.occupants.size; if (!occ) return; const z = cam.zoom, c = toScreen(r.cx, r.gy + 0.5), busy = Math.min(1, occ * 0.45);
  for (let i = 0; i < 2 + occ; i++) { const ph = (t * (0.5 + busy) + i * 0.7) % 2; ctx.globalAlpha = Math.max(0, 0.5 - ph * 0.25);
    ctx.fillStyle = r.K.accent; ctx.font = `${(10 + busy * 3) * z}px system-ui`; ctx.fillText(r.K.fx, c.x + ((i % 3) - 1) * 16 * z, c.y - 30 * z - ph * 24 * z); }
  ctx.globalAlpha = 1;
}

/* ---------------- disciples ---------------- */
function drawDisciple(d, t) {
  const p = toScreen(d.gx, d.gy), z = cam.zoom;
  const robe = d.state === 'working' && d.room ? d.room.K.robe : (ROLE_ROBE[d.state] || '#9a8cff');
  const hovd = hover.disc === d, sel = selected.disc === d, foll = followed === d;
  const sc = z * 1.55 * (hovd || foll ? 1.12 : 1);     // larger silhouettes
  ctx.globalAlpha = d.alpha;
  ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.beginPath(); ctx.ellipse(p.x, p.y, 6 * sc, 2.6 * sc, 0, 0, 6.28); ctx.fill();
  const bob = d.moving ? Math.abs(Math.sin(d.phase)) * 2.2 * sc : (d.state === 'working' ? Math.abs(Math.sin(t * 5 + d.phase)) * 1.4 * sc : (d.state === 'meditate' ? 0 : Math.sin(t * 2 + d.phase) * 0.7 * sc));
  const fy = p.y - bob, bodyH = 15 * sc, headR = 3.6 * sc, fx = d.facing;
  // robe
  const grd = ctx.createLinearGradient(0, fy - bodyH, 0, fy); grd.addColorStop(0, shade(robe, 0.2)); grd.addColorStop(1, shade(robe, -0.28));
  ctx.fillStyle = grd; ctx.strokeStyle = shade(robe, -0.55); ctx.lineWidth = 1 * sc;
  ctx.beginPath(); ctx.moveTo(p.x, fy - bodyH + 1.5 * sc); ctx.lineTo(p.x + 5 * sc, fy); ctx.quadraticCurveTo(p.x, fy + 1.8 * sc, p.x - 5 * sc, fy); ctx.closePath(); ctx.fill(); ctx.stroke();
  // shoulder mantle (role colour accent)
  ctx.fillStyle = shade(robe, 0.32); ctx.beginPath(); ctx.ellipse(p.x, fy - bodyH + 4 * sc, 4.4 * sc, 2.2 * sc, 0, 0, 6.28); ctx.fill();
  // sash
  ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 1.3 * sc; ctx.beginPath(); ctx.moveTo(p.x - 3.5 * sc * fx, fy - 6 * sc); ctx.lineTo(p.x + 3.5 * sc * fx, fy - 8.5 * sc); ctx.stroke();
  // head + hood
  ctx.fillStyle = '#f2e2c8'; ctx.beginPath(); ctx.arc(p.x, fy - bodyH, headR, 0, 6.28); ctx.fill();
  ctx.fillStyle = shade(robe, -0.08); ctx.beginPath(); ctx.arc(p.x, fy - bodyH - 0.6 * sc, headR + 0.5 * sc, Math.PI, 0); ctx.fill();
  // carried item / work tell
  if (d.state === 'working' && d.room) { ctx.fillStyle = d.room.K.accent; ctx.font = `${7 * sc}px system-ui`; ctx.fillText(d.room.K.fx, p.x + 5 * sc * fx, fy - bodyH + 1 * sc); }
  // status pip
  const pip = { working: '#34d399', idle: '#9a8cff', traveling: '#cbb9ff', roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' }[d.state] || '#9a8cff';
  ctx.fillStyle = pip; if (d.state === 'working' || d.state === 'meditate') { ctx.shadowColor = pip; ctx.shadowBlur = 7 * sc; }
  ctx.beginPath(); ctx.arc(p.x + 4.4 * sc, fy - bodyH - 1.5 * sc, 1.7 * sc, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
  // chat bubble
  if (d.chat > 0) { ctx.font = `${9 * sc}px system-ui`; ctx.fillStyle = '#fff'; ctx.globalAlpha = d.alpha * (0.6 + Math.sin(t * 6) * 0.3); ctx.fillText('💬', p.x + 3 * sc, fy - bodyH - 8 * sc); ctx.globalAlpha = d.alpha; }
  // progress ring while working
  if (d.state === 'working' && d.progress > 0.02) { ctx.strokeStyle = '#34d399'; ctx.lineWidth = 1.6 * sc; ctx.beginPath(); ctx.arc(p.x, fy - bodyH, headR + 3 * sc, -1.57, -1.57 + d.progress * 6.28); ctx.stroke(); }
  // name plate
  if (hovd || foll || sel || cam.zoom > 0.62) {
    ctx.font = `600 ${9.5 * z}px system-ui`; ctx.textAlign = 'center';
    const w = ctx.measureText(d.name).width + 8 * z; ctx.fillStyle = 'rgba(8,10,20,.72)';
    roundRect(p.x - w / 2, fy - bodyH - 16 * sc, w, 13 * z, 3 * z); ctx.fill();
    ctx.fillStyle = (hovd || foll) ? '#fff' : '#cdd3f0'; ctx.fillText(d.name, p.x, fy - bodyH - 16 * sc + 10 * z); ctx.textAlign = 'left';
  }
  ctx.globalAlpha = 1;
}

/* breakthrough spectacles */
const spectacles = [];
function celebrate(gx, gy, color, text) { spectacles.push({ gx, gy, color, text, t: 0 }); }
function drawSpectacles(dt) {
  for (let i = spectacles.length - 1; i >= 0; i--) { const s = spectacles[i]; s.t += dt; const k = s.t / 2.6, p = toScreen(s.gx, s.gy), z = cam.zoom;
    ctx.strokeStyle = s.color; ctx.globalAlpha = Math.max(0, 0.9 - k); ctx.lineWidth = 3 * z; ctx.beginPath(); ctx.ellipse(p.x, p.y, (10 + k * 90) * z, (5 + k * 45) * z, 0, 0, 6.28); ctx.stroke();
    ctx.globalAlpha = Math.max(0, 1 - k); ctx.font = `700 ${13 * z}px system-ui`; ctx.textAlign = 'center'; ctx.fillStyle = '#fff3cf'; ctx.fillText('✦ ' + s.text, p.x, p.y - (26 + k * 28) * z); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
    if (s.t > 2.6) spectacles.splice(i, 1); }
}

function drawRoomLabel(r) {
  const p = toScreen(r.cx, r.gy), z = cam.zoom; ctx.font = `700 ${12 * z}px system-ui`; ctx.textAlign = 'center';
  const w = ctx.measureText(r.title).width + 18 * z, y = p.y - 50 * z;
  ctx.fillStyle = 'rgba(8,10,20,.74)'; roundRect(p.x - w / 2, y - 13 * z, w, 18 * z, 5 * z); ctx.fill();
  ctx.fillStyle = r.K.accent; ctx.fillText(r.title, p.x, y); ctx.textAlign = 'left';
  if (r.data) { ctx.fillStyle = HEALTH[r.data.health] || HEALTH.unknown; ctx.beginPath(); ctx.arc(p.x - w / 2 + 8 * z, y - 4 * z, 3 * z, 0, 6.28); ctx.fill(); }
  if (r.occupants.size) { ctx.fillStyle = '#cdd3f0'; ctx.font = `${9 * z}px system-ui`; ctx.textAlign = 'center'; ctx.fillText('▸ ' + r.occupants.size, p.x + w / 2 + 8 * z, y); ctx.textAlign = 'left'; }
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
  disciples.forEach((d) => step(d, dt, t));

  const bg = ctx.createLinearGradient(0, 0, 0, view.h); bg.addColorStop(0, BG1); bg.addColorStop(1, BG0); ctx.fillStyle = bg; ctx.fillRect(0, 0, view.w, view.h);
  drawCourtyard();
  const ordered = rooms.slice().sort((a, b) => a.depth - b.depth);
  ordered.forEach((r) => drawRoom(r, t));
  ordered.forEach((r) => drawWorkFX(r, t));
  rooms.forEach(drawRoomLabel);
  disciples.slice().sort((a, b) => (a.gx + a.gy) - (b.gx + b.gy)).forEach((d) => drawDisciple(d, t));
  drawSpectacles(dt);
}
function drawCourtyard() {
  if (!rooms.length) return; let minGx = 1e9, minGy = 1e9, maxGx = -1e9, maxGy = -1e9;
  rooms.forEach((r) => { minGx = Math.min(minGx, r.gx); minGy = Math.min(minGy, r.gy); maxGx = Math.max(maxGx, r.gx + r.w); maxGy = Math.max(maxGy, r.gy + r.h); });
  ctx.strokeStyle = 'rgba(124,92,255,.05)'; ctx.lineWidth = 1;
  for (let gx = minGx - 3; gx <= maxGx + 3; gx++) { const a = toScreen(gx, minGy - 3), b = toScreen(gx, maxGy + 3); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
  for (let gy = minGy - 3; gy <= maxGy + 3; gy++) { const a = toScreen(minGx - 3, gy), b = toScreen(maxGx + 3, gy); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
}

/* ====================================================================== *
 *  Input
 * ====================================================================== */
const hover = { room: null, disc: null }, selected = { room: null, disc: null };
let followed = null, drag = null;
function pickAt(mx, my) {
  let best = null, bestD = 26;
  disciples.forEach((d) => { const p = toScreen(d.gx, d.gy); const dist = Math.hypot(p.x - mx, p.y - my - 16 * cam.zoom); if (d.alpha > 0.3 && dist < bestD) { bestD = dist; best = d; } });
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
load(); setInterval(load, 12000); setInterval(simTick, 2400); setInterval(pollBreakthroughs, 9000);
requestAnimationFrame(frame);
