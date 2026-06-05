import { $, api, esc, money, mountRail } from '/lib.js';

mountRail('map');

/* ====================================================================== *
 *  AEGIS — Sect Headquarters (Fallout-Shelter style cross-section)
 *  Every hall is a room, all visible at once; disciples walk between them.
 * ====================================================================== */
const canvas = $('scene-canvas');
const ctx = canvas.getContext('2d');
const view = { w: 0, h: 0, dpr: 1 };
const rand = (a, b) => a + Math.random() * (b - a);
const hashStr = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };

const COLS = 6, ROWS = 5;
/* floor, col0, cols, key, name, kind */
const ROOMS = [
  { f: 0, c: 0, cw: 6, key: 'ancestor', name: 'Grand Ancestor Chamber', kind: 'ancestor' },
  { f: 1, c: 0, cw: 6, key: 'hall', name: 'Sect Hall', kind: 'hall' },
  { f: 2, c: 0, cw: 2, key: 'commerce', name: 'Commerce Hall', kind: 'commerce' },
  { f: 2, c: 2, cw: 2, key: 'research', name: 'Research Hall', kind: 'research' },
  { f: 2, c: 4, cw: 2, key: 'mission', name: 'Mission Hall', kind: 'mission' },
  { f: 3, c: 0, cw: 2, key: 'alchemy', name: 'Alchemy Hall', kind: 'alchemy' },
  { f: 3, c: 2, cw: 2, key: 'martial', name: 'Martial Hall', kind: 'martial' },
  { f: 3, c: 4, cw: 2, key: 'treasury', name: 'Treasury', kind: 'treasury' },
  { f: 4, c: 0, cw: 3, key: 'nexus', name: 'Spirit Nexus', kind: 'nexus' },
  { f: 4, c: 3, cw: 3, key: 'cultivation', name: 'Cultivation Chamber', kind: 'cultivation' },
];
const roomByKey = (k) => ROOMS.find((r) => r.key === k);
const WORK_ROOMS = ['commerce', 'research', 'mission', 'alchemy', 'martial', 'treasury', 'nexus'];
const ROLE_ROOM = { trader: 'commerce', researcher: 'research', analyst: 'mission', engineer: 'alchemy', architect: 'nexus', elder: 'hall', disciple: 'martial' };
const KIND = {
  ancestor:    { floor: '#241d33', back: '#1a1528', accent: '#ffd36a' },
  hall:        { floor: '#241f3e', back: '#191534', accent: '#a78bfa' },
  commerce:    { floor: '#26210f', back: '#1b170a', accent: '#f5c542' },
  research:    { floor: '#1c1c38', back: '#13132a', accent: '#c4b5fd' },
  mission:     { floor: '#2a1622', back: '#1d0f18', accent: '#fb7185' },
  alchemy:     { floor: '#142b1f', back: '#0d1d15', accent: '#34d399' },
  martial:     { floor: '#2a1a14', back: '#1d110d', accent: '#fb8e5e' },
  treasury:    { floor: '#2b2410', back: '#1e190a', accent: '#ffd36a' },
  nexus:       { floor: '#102338', back: '#0b1726', accent: '#38bdf8' },
  cultivation: { floor: '#1d1840', back: '#140f2c', accent: '#caa9ff' },
};

/* ---- geometry (recomputed on resize; fits the screen, no pan/zoom) ---- */
const B = { x: 0, y: 0, w: 0, h: 0, colW: 0, floorH: 0, shaftX: 0 };
function layout() {
  const leftPad = 108, rightPad = 348, topPad = 84, botPad = 40;
  B.w = Math.max(420, view.w - leftPad - rightPad); B.h = Math.max(360, view.h - topPad - botPad);
  B.x = leftPad; B.y = topPad; B.colW = B.w / COLS; B.floorH = B.h / ROWS; B.shaftX = B.x + B.w * 0.5;
  ROOMS.forEach((r) => { r.x = B.x + r.c * B.colW; r.y = B.y + r.f * B.floorH; r.w = r.cw * B.colW; r.h = B.floorH;
    r.cx = r.x + r.w / 2; r.cyc = r.y + r.h / 2; });
}
const floorWalkY = (f) => B.y + f * B.floorH + B.floorH - 12;
const roomFloorY = (r) => floorWalkY(r.f);

/* ====================================================================== *
 *  Disciples
 * ====================================================================== */
const ROLE_STYLE = { trader: '#f5c542', engineer: '#5ac8ff', researcher: '#c4b5fd', analyst: '#34d399', architect: '#7bb0ff', elder: '#ecd9a6', disciple: '#9a8cff' };
const ROLE_LIST = ['trader', 'engineer', 'researcher', 'analyst', 'architect'];
function roleOf(ag) {
  const g = ag.governance || {}; if (g.is_leader || g.is_elder || g.is_master) return 'elder';
  const r = String(ag.role || '').toLowerCase();
  if (/trad|market|invest|fund/.test(r)) return 'trader';
  if (/eng|develop|code|build|deploy/.test(r)) return 'engineer';
  if (/research|scholar|study/.test(r)) return 'researcher';
  if (/analy|data|quant|signal/.test(r)) return 'analyst';
  if (/architect|infra|ops|server|system|network/.test(r)) return 'architect';
  return ROLE_LIST[hashStr(ag.name) % ROLE_LIST.length];
}
const disciples = [];
function makeDisc(ag, i) {
  const role = roleOf(ag);
  const home = roomByKey(ROLE_ROOM[role] || WORK_ROOMS[i % WORK_ROOMS.length]) || roomByKey('martial');
  const r0 = home; const x = r0.x + rand(0.3, 0.7) * r0.w;
  return { name: ag.name, data: ag, role, home, room: r0, x, y: roomFloorY(r0), tx: x, ty: roomFloorY(r0),
    path: [], state: 'idle', phase: Math.random() * 6.28, speed: rand(70, 95), facing: 1, idleT: 0, prog: 0, alpha: 1, gone: false, idx: i, extra: false };
}
/* background "outer disciples" so the sect feels populated */
const EXTRA_ROLES = ['disciple', 'researcher', 'trader', 'analyst', 'engineer'];
function makeExtra(i) {
  const role = EXTRA_ROLES[i % EXTRA_ROLES.length], home = roomByKey(WORK_ROOMS[i % WORK_ROOMS.length]);
  const x = home.x + rand(0.2, 0.8) * home.w;
  return { name: 'Outer Disciple', data: { status: 'idle' }, role, home, room: home, x, y: roomFloorY(home), tx: x, ty: roomFloorY(home),
    path: [], state: 'idle', phase: Math.random() * 6.28, speed: rand(60, 85), facing: 1, idleT: 0, prog: 0, alpha: 1, gone: false, idx: 100 + i, extra: true };
}
function ensureDisciples(agents) {
  const have = new Set(disciples.filter((d) => !d.extra).map((d) => d.name));
  agents.forEach((a, i) => { if (!have.has(a.name)) disciples.push(makeDisc(a, i)); });
  disciples.forEach((d) => { if (d.extra) return; const fresh = agents.find((a) => a.name === d.name); if (fresh) { if (d.data.__sim) fresh.__sim = d.data.__sim; d.data = fresh; } });
  if (disciples.filter((d) => d.extra).length === 0) for (let i = 0; i < 14; i++) disciples.push(makeExtra(i));
}

/* where should this disciple be right now? */
function targetRoom(d) {
  const ag = d.data, cult = ag.cultivation || {}, sim = ag.__sim;
  const st = sim ? sim.state : (cult.in_seclusion ? 'meditate' : cult.in_roaming ? 'roaming'
    : (ag.status === 'working' || ag.status === 'queued') ? 'working' : ag.status === 'error' ? 'error' : 'idle');
  d.state = st;
  if (st === 'meditate') return roomByKey('cultivation');
  if (st === 'roaming') return 'exit';
  if (st === 'working' || st === 'error') return (sim && sim.room && roomByKey(sim.room)) || d.home;
  // idle: mostly home, sometimes attend the Sect Hall
  if (assemblyT > 0 && d.idleAttend) return roomByKey('hall');
  return d.home;
}
function pathTo(d, room) {
  if (room === 'exit') { d.path = [{ x: B.x - 50, y: floorWalkY(d.room ? d.room.f : 2) }]; d.goingOut = true; return; }
  d.goingOut = false;
  const tx = room.x + rand(0.3, 0.7) * room.w, ty = roomFloorY(room);
  if (d.room && d.room.f === room.f) { d.path = [{ x: tx, y: ty }]; }
  else { d.path = [{ x: B.shaftX, y: floorWalkY(d.room ? d.room.f : 2) }, { x: B.shaftX, y: ty }, { x: tx, y: ty }]; }
  d.destRoom = room;
}
function step(d, dt, t) {
  if (d.gone) { d.alpha = Math.max(0, d.alpha - dt); return; }
  const want = targetRoom(d);
  if (want !== d.wantCache) { d.wantCache = want; pathTo(d, want); }
  if (d.path.length) {
    const wp = d.path[0], dx = wp.x - d.x, dy = wp.y - d.y, dist = Math.hypot(dx, dy);
    const sp = (Math.abs(dy) > Math.abs(dx) ? d.speed * 0.8 : d.speed) * dt;
    if (dist <= sp) { d.x = wp.x; d.y = wp.y; d.path.shift(); if (!d.path.length && d.destRoom) d.room = d.destRoom; }
    else { d.x += dx / dist * sp; d.y += dy / dist * sp; if (Math.abs(dx) > 0.5) d.facing = dx > 0 ? 1 : -1; }
    d.moving = true; d.phase += dt * 9;
    if (d.goingOut && d.x <= B.x - 48) { d.gone = true; d.goneUntil = t + rand(6, 13); }
  } else {
    d.moving = false;
    if (d.state === 'working') d.prog = Math.min(1, d.prog + dt * 0.03);
    if (d.state === 'idle') { d.idleT -= dt; if (d.idleT <= 0) { const r = d.room || d.home; d.path = [{ x: r.x + rand(0.25, 0.75) * r.w, y: roomFloorY(r) }]; d.idleT = rand(2.5, 6); } }
  }
}

/* ====================================================================== *
 *  Drawing
 * ====================================================================== */
function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function shade(hex, amt) { const n = parseInt(hex.slice(1), 16); let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255; const f = (v) => Math.max(0, Math.min(255, Math.round(v + (amt > 0 ? (255 - v) * amt : v * amt)))); return `rgb(${f(r)},${f(g)},${f(b)})`; }

function drawBackdrop(t) {
  const g = ctx.createLinearGradient(0, 0, 0, view.h); g.addColorStop(0, '#0a0c1a'); g.addColorStop(1, '#05060d'); ctx.fillStyle = g; ctx.fillRect(0, 0, view.w, view.h);
  ctx.fillStyle = 'rgba(167,139,250,.05)';
  for (let i = 0; i < 40; i++) { const x = (i * 89 % view.w), y = (view.h - ((t * 12 + i * 53) % view.h)); ctx.fillRect(x, y, 2, 2); }
}
function pagodaRoof(r, accent) {                 // a thin tiered eave along the room top = cultivation identity
  const n = Math.max(3, Math.round(r.w / 26));
  ctx.fillStyle = shade(accent, -0.5);
  ctx.beginPath(); ctx.moveTo(r.x - 4, r.y + 6); ctx.lineTo(r.x + r.w + 4, r.y + 6); ctx.lineTo(r.x + r.w - 6, r.y); ctx.lineTo(r.x + 6, r.y); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = accent; ctx.globalAlpha = 0.5; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(r.x + 6, r.y); ctx.lineTo(r.x + r.w - 6, r.y); ctx.stroke(); ctx.globalAlpha = 1;
  ctx.fillStyle = accent; for (let i = 0; i <= n; i++) { const x = r.x + 6 + i * (r.w - 12) / n; ctx.fillRect(x - 1, r.y + 6, 2, 3); }
}
function lantern(x, y, t, i) { const sw = Math.sin(t * 1.5 + i) * 1.5; ctx.strokeStyle = 'rgba(120,110,90,.6)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y - 10); ctx.lineTo(x + sw, y); ctx.stroke();
  ctx.fillStyle = '#ffce6a'; ctx.shadowColor = '#ffce6a'; ctx.shadowBlur = 8; ctx.beginPath(); ctx.ellipse(x + sw, y + 3, 3.2, 4.2, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; }

function drawRoom(r, t) {
  const K = KIND[r.kind], occ = roomOcc(r);
  // interior
  const bg = ctx.createLinearGradient(0, r.y, 0, r.y + r.h); bg.addColorStop(0, K.back); bg.addColorStop(1, shade(K.floor, -0.15));
  ctx.fillStyle = bg; ctx.fillRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4);
  // floor
  ctx.fillStyle = shade(K.floor, 0.08); ctx.fillRect(r.x + 2, r.y + r.h - 9, r.w - 4, 7);
  // activity wash
  if (occ > 0) { ctx.globalAlpha = 0.06 + Math.min(0.16, occ * 0.04); const rg = ctx.createRadialGradient(r.cx, r.cyc, 0, r.cx, r.cyc, r.w * 0.5); rg.addColorStop(0, K.accent); rg.addColorStop(1, 'transparent'); ctx.fillStyle = rg; ctx.fillRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4); ctx.globalAlpha = 1; }
  drawProp(r, t, occ);
  pagodaRoof(r, K.accent);
  lantern(r.x + 16, r.y + 22, t, r.f + r.c); lantern(r.x + r.w - 16, r.y + 22, t, r.f + r.c + 3);
  // frame + hover
  const hot = hover.room === r || selected.room === r;
  ctx.strokeStyle = hot ? '#fff' : 'rgba(150,150,184,.22)'; ctx.lineWidth = hot ? 2 : 1; ctx.strokeRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4);
  // label
  ctx.font = '600 12px system-ui'; ctx.textAlign = 'left'; ctx.fillStyle = 'rgba(8,10,20,.6)'; const lw = ctx.measureText(r.name).width + 12;
  roundRect(r.x + 8, r.y + 9, lw, 17, 4); ctx.fill(); ctx.fillStyle = K.accent; ctx.fillText(r.name, r.x + 14, r.y + 21);
  if (occ > 0) { ctx.fillStyle = '#cdd3f0'; ctx.font = '600 11px system-ui'; ctx.textAlign = 'right'; ctx.fillText('▸ ' + occ, r.x + r.w - 8, r.y + 21); ctx.textAlign = 'left'; }
}
function roomOcc(r) { let n = 0; disciples.forEach((d) => { if (!d.gone && !d.extra && d.room === r && !d.path.length) n++; }); return n; }

function drawProp(r, t, occ) {
  const K = KIND[r.kind], cx = r.cx, by = r.y + r.h - 12, x0 = r.x + 14, x1 = r.x + r.w - 14, A = K.accent; ctx.save();
  const carpet = (col) => { ctx.fillStyle = col; ctx.globalAlpha = 0.5; ctx.beginPath(); ctx.ellipse(cx, by, Math.min(70, r.w * 0.32), 5, 0, 0, 6.28); ctx.fill(); ctx.globalAlpha = 1; };
  const banner = (bx, col) => { ctx.fillStyle = col; ctx.fillRect(bx - 3, r.y + 26, 6, 26); ctx.beginPath(); ctx.moveTo(bx - 3, r.y + 52); ctx.lineTo(bx + 3, r.y + 52); ctx.lineTo(bx, r.y + 57); ctx.closePath(); ctx.fill(); };
  const shelf = (sx, col) => { ctx.fillStyle = shade(col, -0.35); ctx.fillRect(sx - 5, by - 34, 10, 30); ctx.fillStyle = '#efe6c8'; for (let s = 0; s < 3; s++) ctx.fillRect(sx - 4, by - 32 + s * 9, 8, 6); };
  const smoke = (sx, sy, col) => { for (let i = 0; i < 3; i++) { const ph = (t * 0.5 + i * 0.4) % 1; ctx.globalAlpha = (1 - ph) * 0.5; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(sx + Math.sin(ph * 6 + i) * 3, sy - ph * 30, 2 + ph * 3, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1; };
  switch (r.kind) {
    case 'ancestor': {                           // statue + sacred tree + incense + tablets
      carpet('#3a2a4a');
      ctx.strokeStyle = '#5a4430'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x0 + 16, by); ctx.lineTo(x0 + 16, by - 22); ctx.stroke();
      ctx.fillStyle = '#2f6f4a'; ctx.shadowColor = '#34d399'; ctx.shadowBlur = 12; ctx.beginPath(); ctx.ellipse(x0 + 16, by - 30, 14, 12, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;     // sacred tree
      ctx.fillStyle = '#3a3f5e'; ctx.beginPath(); ctx.moveTo(cx, by - 62); ctx.lineTo(cx + 14, by); ctx.quadraticCurveTo(cx, by + 5, cx - 14, by); ctx.closePath(); ctx.fill();           // statue
      ctx.fillStyle = '#4a5072'; ctx.beginPath(); ctx.arc(cx, by - 66, 9, 0, 6.28); ctx.fill();
      ctx.globalAlpha = 0.3 + Math.sin(t * 1.4) * 0.12; ctx.strokeStyle = '#ffd36a'; ctx.shadowColor = '#ffd36a'; ctx.shadowBlur = 24; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx, by - 60, 26, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
      [x1 - 30, x1 - 12].forEach((ix, i) => { ctx.fillStyle = '#5a4632'; ctx.fillRect(ix - 2, by - 14, 4, 12); ctx.fillStyle = '#ff9a3a'; ctx.beginPath(); ctx.arc(ix, by - 15, 1.4, 0, 6.28); ctx.fill(); smoke(ix, by - 16, 'rgba(220,210,255,.6)'); });   // incense
      ctx.fillStyle = shade('#caa24a', -0.1); for (let i = 0; i < 3; i++) ctx.fillRect(x1 - 8 - i * 0, r.y + 28 + i * 10, 6, 7); break; }   // ancestor tablets
    case 'hall': {                               // throne + council table + banners + carpet
      carpet('#5a2440'); banner(x0 + 6, A); banner(x1 - 6, A);
      ctx.fillStyle = shade(A, -0.25); ctx.fillRect(cx - 18, by - 34, 36, 30); ctx.fillStyle = shade(A, -0.1); ctx.fillRect(cx - 14, by - 44, 28, 12);   // throne
      ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 12; ctx.beginPath(); ctx.arc(cx, by - 48, 5, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
      ctx.fillStyle = '#3a2f22'; ctx.fillRect(cx - 34, by - 8, 22, 6); ctx.fillRect(cx + 12, by - 8, 22, 6);   // council tables
      [x0 + 24, x1 - 24].forEach((bx) => { const fy = by - 16 - Math.abs(Math.sin(t * 4 + bx)) * 4; ctx.fillStyle = '#ffb04a'; ctx.shadowColor = '#ffb04a'; ctx.shadowBlur = 12; ctx.beginPath(); ctx.ellipse(bx, fy, 3, 6, 0, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; }); break; }
    case 'commerce': {                           // stalls + chests + crates + ledger
      carpet('#3a3216');
      for (let i = 0; i < 4; i++) { const sx = x0 + 14 + i * ((x1 - x0 - 28) / 3); ctx.fillStyle = i % 2 ? '#b9503c' : '#3f7a52'; ctx.fillRect(sx - 12, by - 28, 24, 6); ctx.fillStyle = '#5a3f2a'; ctx.fillRect(sx - 11, by - 22, 22, 14);
        ctx.fillStyle = '#caa24a'; for (let c = 0; c < 3; c++) ctx.fillRect(sx - 8 + c * 6, by - 20, 4, 4); }
      ctx.fillStyle = '#5a4632'; ctx.fillRect(x1 - 18, by - 12, 14, 10); ctx.fillStyle = '#ffdf6e'; for (let i = 0; i < 5; i++) ctx.beginPath(), ctx.arc(x0 + 6 + i * 5, by - 3, 1.8, 0, 6.28), ctx.fill(); break; }
    case 'research': {                           // bookshelves + study desk + manuscript
      [x0 + 8, x0 + 28, x1 - 28, x1 - 8].forEach((sx) => shelf(sx, A));
      ctx.fillStyle = '#3a2f22'; ctx.fillRect(cx - 16, by - 8, 32, 6);   // study desk
      ctx.fillStyle = '#efe6c8'; ctx.shadowColor = A; ctx.shadowBlur = 8 + Math.sin(t * 3) * 4; ctx.fillRect(cx - 6, by - 14, 12, 6); ctx.shadowBlur = 0; break; }   // glowing manuscript
    case 'mission': {                            // quest board + maps + dispatch desk
      ctx.fillStyle = '#1a1326'; ctx.fillRect(cx - 34, by - 38, 68, 30); ctx.strokeStyle = A; ctx.strokeRect(cx - 34, by - 38, 68, 30);
      ctx.fillStyle = '#fbbf24'; for (let i = 0; i < 4; i++) ctx.fillRect(cx - 30 + i * 17, by - 34, 12, 13);
      ctx.fillStyle = '#3a5a6a'; for (let i = 0; i < 4; i++) ctx.fillRect(cx - 30 + i * 17, by - 19, 12, 9);   // map pins row
      ctx.fillStyle = '#3a2f22'; ctx.fillRect(cx - 14, by - 7, 28, 5); break; }
    case 'alchemy': {                            // cauldron(bubbling) + herb shelves + jars + smoke
      [x0 + 10, x0 + 26].forEach((sx) => { ctx.fillStyle = '#2a3a2a'; ctx.fillRect(sx - 5, by - 30, 10, 26); ctx.fillStyle = '#5fae6a'; for (let s = 0; s < 3; s++) ctx.fillRect(sx - 4, by - 28 + s * 8, 8, 4); });
      ctx.fillStyle = '#2a2230'; ctx.beginPath(); ctx.ellipse(cx + 8, by - 10, 16, 11, 0, 0, 6.28); ctx.fill();
      ctx.fillStyle = A; ctx.globalAlpha = 0.7; ctx.beginPath(); ctx.ellipse(cx + 8, by - 14, 12, 5, 0, 0, 6.28); ctx.fill(); ctx.globalAlpha = 1;
      for (let i = 0; i < 3; i++) { const ph = (t * 0.8 + i * 0.4) % 1; ctx.globalAlpha = 1 - ph; ctx.fillStyle = A; ctx.beginPath(); ctx.arc(cx + 8 + (i - 1) * 5, by - 16 - ph * 24, 1.8, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1;
      [x1 - 8, x1 - 18].forEach((jx, i) => { ctx.fillStyle = i ? '#caa24a' : '#5fae6a'; ctx.fillRect(jx - 3, by - 12, 6, 9); }); break; }
    case 'martial': {                            // weapon rack + 2 dummies + sparring circle + banner
      banner(x0 + 6, A);
      [x0 + 26, x1 - 26].forEach((dx) => { ctx.strokeStyle = '#b9925a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(dx, by); ctx.lineTo(dx, by - 28); ctx.moveTo(dx - 9, by - 21); ctx.lineTo(dx + 9, by - 21); ctx.stroke(); ctx.fillStyle = '#c9a06a'; ctx.beginPath(); ctx.arc(dx, by - 31, 4.5, 0, 6.28); ctx.fill(); });
      ctx.strokeStyle = shade(A, -0.1); ctx.lineWidth = 2; [x1 - 12, x1 - 8, x1 - 4].forEach((dx) => { ctx.beginPath(); ctx.moveTo(dx, by); ctx.lineTo(dx, by - 24); ctx.stroke(); });   // weapon rack
      ctx.strokeStyle = A; ctx.globalAlpha = 0.4; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(cx, by - 2, 26, 6, 0, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1; break; }
    case 'treasury': {                           // gold piles + chest + vault door + jade
      ctx.fillStyle = shade('#2a2418', 0.1); ctx.fillRect(x1 - 26, r.y + 24, 24, by - r.y - 24); ctx.strokeStyle = '#caa24a'; ctx.strokeRect(x1 - 26, r.y + 24, 24, by - r.y - 24);   // vault door
      ctx.fillStyle = '#caa24a'; ctx.beginPath(); ctx.arc(x1 - 14, (r.y + 24 + by) / 2, 4, 0, 6.28); ctx.fill();
      ctx.fillStyle = '#caa24a'; [-1, 1].forEach((sgn) => { ctx.beginPath(); ctx.moveTo(cx + sgn * 6, by); ctx.quadraticCurveTo(cx + sgn * 18, by - 16, cx + sgn * 30, by); ctx.fill(); });
      ctx.fillStyle = '#5a4632'; ctx.fillRect(cx - 9, by - 16, 18, 12); ctx.fillStyle = '#ffdf6e'; ctx.shadowColor = '#ffdf6e'; ctx.shadowBlur = 8; ctx.fillRect(cx - 1, by - 11, 4, 4); ctx.shadowBlur = 0;
      ctx.fillStyle = '#5fd3a0'; ctx.fillRect(x0 + 8, by - 8, 5, 6); ctx.fillRect(x0 + 16, by - 6, 4, 4); break; }   // jade
    case 'nexus': {                              // giant crystal + spring + qi streams + runes
      ctx.fillStyle = 'rgba(60,150,210,.4)'; ctx.beginPath(); ctx.ellipse(x0 + 24, by - 4, 16, 5, 0, 0, 6.28); ctx.fill();   // spring
      [[0, -42, 12], [-16, -24, 7], [16, -26, 7]].forEach(([dx, dy, s]) => { ctx.fillStyle = A; ctx.shadowColor = A; ctx.shadowBlur = 16; ctx.beginPath(); ctx.moveTo(cx + dx, by + dy - s); ctx.lineTo(cx + dx + s * 0.7, by + dy); ctx.lineTo(cx + dx, by + dy + s); ctx.lineTo(cx + dx - s * 0.7, by + dy); ctx.closePath(); ctx.fill(); }); ctx.shadowBlur = 0;
      ctx.strokeStyle = A; ctx.globalAlpha = 0.4; for (let i = 0; i < 3; i++) { const yy = by - 8 - ((t * 18 + i * 14) % 40); ctx.beginPath(); ctx.moveTo(cx - 20, yy); ctx.lineTo(cx + 20, yy - 6); ctx.stroke(); } ctx.globalAlpha = 1; break; }   // qi streams
    case 'cultivation': {                        // platforms + cushions + lamps + formation + qi
      const xs = [cx - 44, cx, cx + 44].filter((v) => v > x0 && v < x1);
      xs.forEach((dx) => { ctx.fillStyle = shade(A, -0.4); ctx.beginPath(); ctx.ellipse(dx, by - 2, 12, 4, 0, 0, 6.28); ctx.fill();   // platform/cushion
        ctx.strokeStyle = A; ctx.globalAlpha = 0.4 + Math.sin(t * 2 + dx) * 0.2; ctx.shadowColor = A; ctx.shadowBlur = 8; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.ellipse(dx, by - 4, 13, 4.5, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; });
      ctx.strokeStyle = A; ctx.globalAlpha = 0.25; ctx.lineWidth = 1; ctx.beginPath(); ctx.ellipse(cx, by - 4, Math.min(70, r.w * 0.34), 8, 0, 0, 6.28); ctx.stroke(); ctx.globalAlpha = 1;   // formation array
      for (let i = 0; i < 4; i++) { const ph = (t * 0.4 + i * 0.25) % 1; ctx.globalAlpha = (1 - ph) * 0.6; ctx.fillStyle = A; ctx.beginPath(); ctx.arc(cx + (i - 1.5) * 18, by - 6 - ph * 22, 1.4, 0, 6.28); ctx.fill(); } ctx.globalAlpha = 1; break; }
  }
  // ambient dust motes drifting in every room
  ctx.fillStyle = 'rgba(255,255,255,.05)';
  for (let i = 0; i < 4; i++) { const mx = r.x + ((i * 71 + t * 6) % (r.w - 12)) + 6, my = r.y + 30 + ((i * 53 + t * 9) % (r.h - 40)); ctx.fillRect(mx, my, 1.5, 1.5); }
  ctx.restore();
}

function drawShaft(t) {
  ctx.fillStyle = 'rgba(60,64,96,.18)'; ctx.fillRect(B.shaftX - 11, B.y + B.floorH * 2, 22, B.h - B.floorH * 2);
  ctx.strokeStyle = 'rgba(150,150,184,.18)'; ctx.lineWidth = 1; ctx.strokeRect(B.shaftX - 11, B.y + B.floorH * 2, 22, B.h - B.floorH * 2);
  for (let f = 2; f < ROWS; f++) { const y = B.y + f * B.floorH; ctx.beginPath(); ctx.moveTo(B.shaftX - 11, y); ctx.lineTo(B.shaftX + 11, y); ctx.stroke(); }
}

/* ---- per-disciple visual identity (recognisable without the nameplate) ---- */
const HAIRS = ['topknot', 'bun', 'pony', 'hood', 'crown', 'long'];
const NAME_FLAVOR = {
  atlas: { robe: '#ecd9a6', aura: '#ffd36a', prop: 'staff', size: 1.4, hair: 'crown', leader: true },
  sage: { robe: '#c9b6ff', aura: '#caa9ff', prop: 'staff', size: 1.18, hair: 'bun', elder: true },
  nova: { robe: '#c4b5fd', prop: 'book', hair: 'long' },
  quill: { robe: '#a9c0ff', prop: 'brush', hair: 'topknot' },
  forge: { robe: '#5ac8ff', prop: 'tools', spark: true, size: 1.12, hair: 'topknot' },
  ember: { robe: '#fb8e5e', aura: '#ff7a3a', prop: 'flame', hair: 'pony' },
  wren: { robe: '#9be8c2', prop: 'dagger', fast: true, size: 0.94, hair: 'pony' },
  pip: { robe: '#f5c542', prop: 'coin', size: 0.96, hair: 'bun' },
  marlo: { robe: '#7bb0ff', prop: 'tools', hair: 'hood' },
};
const ROLE_PROP = { trader: 'coin', researcher: 'book', analyst: 'book', engineer: 'tools', architect: 'tools', elder: 'staff', disciple: 'blade' };
const HAIR_COLS = ['#241a14', '#3a2a1c', '#1c1c24', '#5a4636', '#8a7a6a'];
function tintByName(hex, h) { const n = parseInt(hex.slice(1), 16); const cl = (v) => Math.max(0, Math.min(255, v));
  const r = cl(((n >> 16) & 255) + ((h % 48) - 24)), g = cl(((n >> 8) & 255) + (((h >> 3) % 44) - 22)), b = cl((n & 255) + (((h >> 6) % 44) - 22));
  return `#${(r << 16 | g << 8 | b).toString(16).padStart(6, '0')}`; }
function identity(d) {
  if (d.ident) return d.ident; const h = hashStr(d.name), fl = NAME_FLAVOR[d.name.toLowerCase()] || {};
  const g = d.data.governance || {}, leader = fl.leader || g.is_leader, elder = fl.elder || d.role === 'elder' || g.is_elder;
  d.ident = {
    robe: fl.robe || tintByName(ROLE_STYLE[d.role] || '#9a8cff', h),
    hair: fl.hair || HAIRS[h % HAIRS.length], hairCol: HAIR_COLS[(h >> 2) % HAIR_COLS.length],
    prop: fl.prop || ROLE_PROP[d.role] || 'none', aura: fl.aura || (leader ? '#ffd36a' : elder ? '#caa9ff' : null),
    size: fl.size || (leader ? 1.4 : elder ? 1.18 : 1.0), spark: fl.spark, flame: fl.prop === 'flame' || fl.flame, idle: h % 3, leader, elder,
  };
  return d.ident;
}
function drawHair(x, y, headR, style, col, s) {
  ctx.fillStyle = col;
  switch (style) {
    case 'topknot': ctx.beginPath(); ctx.arc(x, y - 0.4 * s, headR + 0.6 * s, Math.PI, 0); ctx.fill(); ctx.beginPath(); ctx.arc(x, y - headR - 1.4 * s, 1.4 * s, 0, 6.28); ctx.fill(); break;
    case 'bun': ctx.beginPath(); ctx.arc(x, y - 0.4 * s, headR + 0.6 * s, Math.PI, 0); ctx.fill(); ctx.beginPath(); ctx.arc(x - headR, y - 0.6 * s, 1.6 * s, 0, 6.28); ctx.fill(); break;
    case 'pony': ctx.beginPath(); ctx.arc(x, y - 0.4 * s, headR + 0.6 * s, Math.PI, 0); ctx.fill(); ctx.fillRect(x - headR - 1.6 * s, y - 1 * s, 1.6 * s, 5 * s); break;
    case 'hood': ctx.fillStyle = shade(col, -0.2); ctx.beginPath(); ctx.arc(x, y - 0.6 * s, headR + 1.6 * s, Math.PI, 0); ctx.fill(); ctx.fillRect(x - headR - 1.4 * s, y - 0.6 * s, (headR + 1.4 * s) * 2, 2 * s); break;
    case 'crown': ctx.beginPath(); ctx.arc(x, y - 0.4 * s, headR + 0.5 * s, Math.PI, 0); ctx.fill(); ctx.fillStyle = '#ffd36a'; ctx.beginPath(); ctx.moveTo(x - 2.4 * s, y - headR); ctx.lineTo(x - 2.4 * s, y - headR - 2.4 * s); ctx.lineTo(x, y - headR - 1 * s); ctx.lineTo(x + 2.4 * s, y - headR - 2.4 * s); ctx.lineTo(x + 2.4 * s, y - headR); ctx.closePath(); ctx.fill(); break;
    case 'long': default: ctx.beginPath(); ctx.arc(x, y - 0.4 * s, headR + 0.7 * s, Math.PI, 0); ctx.fill(); ctx.fillRect(x - headR - 0.8 * s, y - 0.8 * s, 1.4 * s, 4 * s); ctx.fillRect(x + headR - 0.6 * s, y - 0.8 * s, 1.4 * s, 4 * s); break;
  }
}
function drawHeld(d, x, fy, bodyH, s, fx, t, id) {
  const px = x + 5 * s * fx, py = fy - 5 * s;
  switch (id.prop) {
    case 'staff': ctx.strokeStyle = '#7a5a2a'; ctx.lineWidth = 1.4 * s; ctx.beginPath(); ctx.moveTo(px, fy); ctx.lineTo(px, fy - bodyH - 4 * s); ctx.stroke();
      ctx.fillStyle = id.aura || '#a78bfa'; ctx.shadowColor = id.aura || '#a78bfa'; ctx.shadowBlur = 8 * s; ctx.beginPath(); ctx.arc(px, fy - bodyH - 5 * s, 1.8 * s, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0; break;
    case 'book': for (let i = 0; i < 2; i++) { const yy = py - 5 * s - i * 3 * s + Math.sin(t * 2 + d.phase + i) * 1.5 * s; ctx.fillStyle = '#efe6c8'; ctx.fillRect(px - 2 * s, yy, 4 * s, 3 * s); ctx.strokeStyle = '#a9c0ff'; ctx.lineWidth = 0.6 * s; ctx.strokeRect(px - 2 * s, yy, 4 * s, 3 * s); } break;
    case 'coin': for (let i = 0; i < 3; i++) { const ph = (t * 0.9 + i * 0.4 + d.phase) % 1; ctx.globalAlpha = (1 - ph) * d.alpha; ctx.fillStyle = '#ffdf6e'; ctx.shadowColor = '#ffdf6e'; ctx.shadowBlur = 5 * s; ctx.beginPath(); ctx.arc(px, fy - 6 * s - ph * 12 * s, 1.4 * s, 0, 6.28); ctx.fill(); } ctx.shadowBlur = 0; ctx.globalAlpha = d.alpha; break;
    case 'tools': ctx.fillStyle = '#9aa0b0'; ctx.fillRect(px - 0.8 * s, py - 4 * s, 1.6 * s, 5 * s); if (id.spark) for (let i = 0; i < 3; i++) { const ph = (t * 1.6 + i * 0.3 + d.phase) % 1; ctx.globalAlpha = (1 - ph) * d.alpha; ctx.fillStyle = '#ffd27a'; ctx.beginPath(); ctx.arc(px + (i - 1) * 2 * s, py - 4 * s - ph * 8 * s, 1 * s, 0, 6.28); ctx.fill(); } ctx.globalAlpha = d.alpha; break;
    case 'brush': ctx.strokeStyle = '#3a2a1c'; ctx.lineWidth = 1 * s; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px + 1.5 * s, py - 4 * s); ctx.stroke(); ctx.fillStyle = '#1c1c2c'; ctx.beginPath(); ctx.arc(px, py + 0.5 * s, 1.1 * s, 0, 6.28); ctx.fill(); break;
    case 'dagger': ctx.strokeStyle = '#cdd6f0'; ctx.lineWidth = 1.2 * s; ctx.beginPath(); ctx.moveTo(px, fy - 2 * s); ctx.lineTo(px + 3 * s * fx, fy - 6 * s); ctx.stroke(); break;
    case 'blade': ctx.strokeStyle = 'rgba(205,214,255,.8)'; ctx.lineWidth = 1.2 * s; ctx.beginPath(); ctx.moveTo(px, fy - 1 * s); ctx.lineTo(px + 4 * s * fx, fy - 7 * s); ctx.stroke(); break;
    case 'flame': for (let i = 0; i < 3; i++) { const ph = (t * 1.4 + i * 0.33 + d.phase) % 1; ctx.globalAlpha = (1 - ph) * 0.9 * d.alpha; ctx.fillStyle = i % 2 ? '#ff7a3a' : '#ffd36a'; ctx.beginPath(); ctx.ellipse(px - 4 * s + i * 3 * s, fy - 6 * s - ph * 12 * s, 1.4 * s, 2.4 * s, 0, 0, 6.28); ctx.fill(); } ctx.globalAlpha = d.alpha; break;
  }
}
/* a working disciple's activity reads from the room they're in */
function drawActivity(d, x, fy, s, t) {
  const r = d.room; if (!r) return; const A = KIND[r.kind].accent;
  ctx.globalAlpha = (0.5 + Math.sin(t * 3 + d.phase) * 0.3) * d.alpha;
  if (r.kind === 'alchemy') { ctx.fillStyle = A; for (let i = 0; i < 2; i++) { const ph = (t * 0.9 + i * 0.5) % 1; ctx.beginPath(); ctx.arc(x + 4 * s, fy - 12 * s - ph * 14 * s, 1.4 * s, 0, 6.28); ctx.fill(); } }
  else if (r.kind === 'martial') { ctx.strokeStyle = 'rgba(205,214,255,.7)'; ctx.lineWidth = 1.2 * s; const a = Math.sin(t * 8 + d.phase); ctx.beginPath(); ctx.arc(x, fy - 8 * s, 7 * s, -0.6 + a, 0.4 + a); ctx.stroke(); }
  else if (r.kind === 'nexus' || r.kind === 'cultivation') { ctx.fillStyle = A; for (let i = 0; i < 3; i++) { const ph = (t + i * 0.33) % 1; ctx.beginPath(); ctx.arc(x + Math.cos(ph * 6.28) * 5 * s, fy - 8 * s - ph * 6 * s, 1 * s, 0, 6.28); ctx.fill(); } }
  else if (r.kind === 'research' || r.kind === 'mission') { ctx.fillStyle = '#efe6c8'; const yy = fy - 14 * s + Math.sin(t * 2 + d.phase) * 1.5 * s; ctx.fillRect(x - 5 * s, yy, 4 * s, 3 * s); }
  else if (r.kind === 'commerce' || r.kind === 'treasury') { ctx.fillStyle = '#ffdf6e'; const ph = (t * 0.8) % 1; ctx.beginPath(); ctx.arc(x - 4 * s, fy - 8 * s - ph * 10 * s, 1.4 * s, 0, 6.28); ctx.fill(); }
  ctx.globalAlpha = d.alpha;
}
function drawDisc(d, t) {
  const id = d.extra ? null : identity(d);
  const sc = (d.extra ? 1.5 : 2.0) * (id ? id.size : 1), hovd = hover.disc === d, sel = selected.disc === d;
  const s = sc * (hovd || sel ? 1.18 : 1), robe = id ? id.robe : (ROLE_STYLE[d.role] || '#8b92ac');
  const meditate = d.state === 'meditate' && !d.path.length, working = d.state === 'working' && !d.path.length;
  const idleK = id ? id.idle : 0;
  const bob = d.moving ? Math.abs(Math.sin(d.phase)) * (d.ident && d.ident.fast ? 2.6 : 2.0) * s : working ? Math.abs(Math.sin(t * 5 + d.phase)) * 1.2 * s : meditate ? 0 : Math.sin(t * (1.6 + idleK * 0.5) + d.phase) * 0.6 * s;
  const x = d.x, fy = d.y - bob, fx = d.facing, bodyH = (meditate ? 8 : 12) * s, headR = 3 * s, headY = fy - bodyH;
  ctx.globalAlpha = d.alpha;
  ctx.fillStyle = 'rgba(0,0,0,.4)'; ctx.beginPath(); ctx.ellipse(x, d.y, 5 * s, 2 * s, 0, 0, 6.28); ctx.fill();
  // cultivation aura (elders/leaders) or meditation aura
  if (meditate || (id && id.aura)) { const ac = meditate ? '#a78bfa' : id.aura; ctx.globalAlpha = d.alpha * (0.3 + Math.sin(t * 2 + d.phase) * 0.18); ctx.strokeStyle = ac; ctx.shadowColor = ac; ctx.shadowBlur = 9; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.ellipse(x, d.y, (meditate ? 8 : 6.5) * s, (meditate ? 3.5 : 3) * s, 0, 0, 6.28); ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = d.alpha; }
  // robe
  const grd = ctx.createLinearGradient(0, headY, 0, fy); grd.addColorStop(0, shade(robe, 0.2)); grd.addColorStop(1, shade(robe, -0.3));
  ctx.fillStyle = grd; ctx.strokeStyle = shade(robe, -0.5); ctx.lineWidth = 0.9 * s;
  const bw = (id && id.leader ? 5.4 : 4.5) * s;
  ctx.beginPath(); ctx.moveTo(x, headY + 1.5 * s); ctx.lineTo(x + bw, fy); ctx.quadraticCurveTo(x, fy + 1.7 * s, x - bw, fy); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.fillStyle = shade(robe, 0.34); ctx.beginPath(); ctx.ellipse(x, headY + 4 * s, bw * 0.85, 2 * s, 0, 0, 6.28); ctx.fill();
  if (id && id.leader) { ctx.strokeStyle = '#ffd36a'; ctx.globalAlpha = d.alpha * 0.7; ctx.lineWidth = 0.8 * s; ctx.beginPath(); ctx.moveTo(x, headY + 5 * s); ctx.lineTo(x, fy); ctx.stroke(); ctx.globalAlpha = d.alpha; }
  if (working) { ctx.strokeStyle = shade(robe, -0.1); ctx.lineWidth = 1.6 * s; ctx.lineCap = 'round'; const a = Math.sin(t * 10 + d.phase) * 1.4 * s; ctx.beginPath(); ctx.moveTo(x, fy - 6 * s); ctx.lineTo(x + 5 * s * fx, fy - 3 * s + a); ctx.stroke(); ctx.lineCap = 'butt'; }
  // head + hair
  ctx.fillStyle = '#f2e2c8'; ctx.beginPath(); ctx.arc(x, headY, headR, 0, 6.28); ctx.fill();
  if (id) drawHair(x, headY, headR, id.hair, id.hairCol, s); else { ctx.fillStyle = shade(robe, -0.1); ctx.beginPath(); ctx.arc(x, headY - 0.5 * s, headR + 0.5 * s, Math.PI, 0); ctx.fill(); }
  if (id) drawHeld(d, x, fy, bodyH, s, fx, t, id);
  if (working && !d.extra) drawActivity(d, x, fy, s, t);
  // status pip
  const pip = { working: '#34d399', idle: robe, roaming: '#fbbf24', meditate: '#caa9ff', error: '#fb5e7e' }[d.state] || robe;
  ctx.fillStyle = pip; if (working || meditate) { ctx.shadowColor = pip; ctx.shadowBlur = 7 * s; } ctx.beginPath(); ctx.arc(x + headR + 1 * s, headY - 1 * s, 1.5 * s, 0, 6.28); ctx.fill(); ctx.shadowBlur = 0;
  if (working && d.prog > 0.02) { ctx.strokeStyle = '#34d399'; ctx.lineWidth = 1.4 * s; ctx.beginPath(); ctx.arc(x, headY, headR + 2.5 * s, -1.57, -1.57 + d.prog * 6.28); ctx.stroke(); }
  if (!d.extra && (hovd || sel || d.state === 'working' || d.state === 'meditate')) {
    ctx.font = `600 ${10 * (hovd || sel ? 1.1 : 1)}px system-ui`; ctx.textAlign = 'center'; const w = ctx.measureText(d.name).width + 8;
    ctx.fillStyle = 'rgba(8,10,20,.72)'; roundRect(x - w / 2, headY - 16 * s, w, 13, 3); ctx.fill();
    ctx.fillStyle = (hovd || sel) ? '#fff' : '#cdd3f0'; ctx.fillText(d.name, x, headY - 16 * s + 10); ctx.textAlign = 'left';
  }
  ctx.globalAlpha = 1;
}

/* spectacles + assembly events */
const spectacles = [];
function celebrate(x, y, color, text) { spectacles.push({ x, y, color, text, t: 0 }); }
function drawSpectacles(dt) {
  for (let i = spectacles.length - 1; i >= 0; i--) { const s = spectacles[i]; s.t += dt; const k = s.t / 2.4;
    ctx.strokeStyle = s.color; ctx.globalAlpha = Math.max(0, 0.9 - k); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(s.x, s.y, 8 + k * 50, 0, 6.28); ctx.stroke();
    ctx.globalAlpha = Math.max(0, 1 - k); ctx.font = '700 12px system-ui'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff3cf'; ctx.fillText('✦ ' + s.text, s.x, s.y - 26 - k * 22); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
    if (s.t > 2.4) spectacles.splice(i, 1); }
}
let assemblyT = 0;
function assembly() {
  assemblyT = 9; const idlers = disciples.filter((d) => !d.extra && d.state === 'idle'); idlers.forEach((d) => d.idleAttend = true);
  setTimeout(() => { assemblyT = 0; disciples.forEach((d) => d.idleAttend = false); }, 9000);
}

/* ====================================================================== *
 *  Render loop
 * ====================================================================== */
let last = performance.now(), elapsed = 0, lastDerive = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000); last = now; elapsed += dt; const t = elapsed;
  if (assemblyT > 0) assemblyT -= dt;
  disciples.forEach((d) => { if (d.gone && t > d.goneUntil) { d.gone = false; d.alpha = 0; if (d.data.__sim) d.data.__sim = { state: 'idle' }; const r = d.home; d.x = B.x - 40; d.y = floorWalkY(r.f); d.room = r; d.wantCache = null; } step(d, dt, t); });
  drawBackdrop(t);
  // building frame
  ctx.fillStyle = 'rgba(10,12,24,.6)'; ctx.fillRect(B.x - 6, B.y - 6, B.w + 12, B.h + 12);
  ROOMS.forEach((r) => drawRoom(r, t));
  drawShaft(t);
  disciples.slice().sort((a, b) => (a.y - b.y) || (a.x - b.x)).forEach((d) => drawDisc(d, t));
  drawSpectacles(dt);
}

/* ====================================================================== *
 *  Input + panels
 * ====================================================================== */
const hover = { disc: null, room: null }, selected = { disc: null, room: null };
function pick(mx, my) {
  let best = null, bd = 18;
  disciples.forEach((d) => { if (d.gone || d.extra) return; const dist = Math.hypot(d.x - mx, d.y - my - 12); if (dist < bd) { bd = dist; best = d; } });
  if (best) return { disc: best };
  const r = ROOMS.find((R) => mx >= R.x && mx <= R.x + R.w && my >= R.y && my <= R.y + R.h);
  return { room: r || null };
}
canvas.addEventListener('mousemove', (e) => { const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top; const h = pick(mx, my); hover.disc = h.disc || null; hover.room = h.disc ? null : h.room; canvas.style.cursor = (hover.disc || hover.room) ? 'pointer' : 'default'; });
canvas.addEventListener('click', (e) => { const r = canvas.getBoundingClientRect(), h = pick(e.clientX - r.left, e.clientY - r.top); if (h.disc) selectDisc(h.disc); else if (h.room) selectRoom(h.room); });

function selectDisc(d) {
  selected.disc = d; selected.room = null; const ag = d.data, c = ag.cultivation || {}, g = ag.governance || {};
  const where = d.path.length ? `walking to <b>${esc((d.destRoom || d.home).name)}</b>` : `in the <b>${esc((d.room || d.home).name)}</b>`;
  const doing = { working: 'Working', idle: 'Resting', roaming: 'Roaming beyond the sect', meditate: 'Meditating', error: 'Needs aid' }[d.state] || d.state;
  const rows = [['Role', esc(ag.role || c.rank_title || d.role)], ['Realm', esc(c.realm_name || 'Mortal')], ['Doing', esc(doing)],
    ag.current_task ? ['Task', esc(String(ag.current_task).slice(0, 56))] : null, ['Tasks done', ag.tasks_done || 0]]
    .filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(d.name)}</div>
    <div class='muted' style='margin:8px 0 2px;font-size:12.5px'>${doing} — ${where}.</div>
    <div class='kvs'>${rows}</div>
    <div class='realm-actions'><button class='cbtn' id='r-cham'>Open Dossier</button></div>`;
  const b = $('r-cham'); if (b) b.onclick = () => { location.href = '/chamber'; };
}
function selectRoom(r) {
  selected.room = r; selected.disc = null;
  const here = disciples.filter((d) => !d.gone && !d.extra && d.room === r && !d.path.length).map((d) => esc(d.name));
  $('detail').innerHTML = `<div class='panel-title'>${esc(r.name)}</div>
    <div class='muted' style='margin-top:10px;font-size:12.5px'>${here.length ? here.join(', ') : 'No disciples on duty.'}</div>
    <div class='realm-actions'><button class='cbtn' id='r-assign'>Assign Disciple</button><button class='cbtn' id='r-logs'>View Logs</button></div>`;
  const a = $('r-assign'); if (a) a.onclick = () => { localStorage.setItem('tab', 'disciples'); location.href = '/classic'; };
  const l = $('r-logs'); if (l) l.onclick = () => { localStorage.setItem('tab', 'overview'); location.href = '/classic'; };
}

/* legend + roam ticker */
$('legend').innerHTML = [['#34d399', 'working'], ['#9a8cff', 'idle'], ['#fbbf24', 'roaming'], ['#fb5e7e', 'needs aid']]
  .map(([c, l]) => `<span class='lg'><i class='lg-dot' style='background:${c};color:${c}'></i>${l}</span>`).join('');
function renderRoam() {
  const roamers = disciples.filter((d) => !d.extra && d.state === 'roaming'); const el = $('roam'); if (!roamers.length) { el.hidden = true; return; } el.hidden = false;
  const verbs = ['gathering intelligence', 'seeking rare techniques', 'roaming the lower realm', 'returning from a mission'];
  el.innerHTML = `<div class='panel-title'>Beyond the Sect</div>` + roamers.map((d, i) => `<div class='roam-row'>🌄 <b>${esc(d.name)}</b> is ${verbs[(d.name.charCodeAt(0) + i) % verbs.length]}…</div>`).join('');
}
setInterval(renderRoam, 1200);

/* ====================================================================== *
 *  Demo simulation + data
 * ====================================================================== */
let DEMO = false;
function simTick() {
  if (!DEMO || !disciples.length) return;
  disciples.forEach((d) => { if (!d.data.__sim) d.data.__sim = { state: 'idle' }; });
  const reals = disciples.filter((d) => !d.extra), d = reals[(Math.random() * reals.length) | 0]; if (!d) return; const roll = Math.random(), s = d.data.__sim.state;
  if (s === 'idle') { if (roll < 0.5) d.data.__sim = { state: 'working', room: roomByKey(WORK_ROOMS[(Math.random() * WORK_ROOMS.length) | 0]).key };
    else if (roll < 0.66) d.data.__sim = { state: 'roaming' }; else if (roll < 0.76) d.data.__sim = { state: 'meditate' }; }
  else if (s === 'working' && roll < 0.32) { d.data.__sim = { state: 'idle' }; if (Math.random() < 0.5) celebrate(d.x, d.y - 30, '#fbbf24', `${d.name}: ${['milestone', 'breakthrough', 'deploy', 'profit'][(Math.random() * 4) | 0]}`); }
  // extras drift among work rooms
  disciples.filter((e) => e.extra && Math.random() < 0.04).forEach((e) => { e.data.__sim = { state: Math.random() < 0.7 ? 'working' : 'idle', room: roomByKey(WORK_ROOMS[(Math.random() * WORK_ROOMS.length) | 0]).key }; });
}
let seenChron = null;
async function pollBreak() {
  const ch = await api('/api/chronicle?limit=20'); if (!ch) return; const entries = ch.recent || [];
  if (seenChron === null) { seenChron = new Set(entries.map((e) => e.id)); return; }
  entries.filter((e) => !seenChron.has(e.id) && ['breakthrough', 'milestone', 'title', 'ascension'].includes(e.kind)).forEach((e) => { const d = disciples.find((x) => x.name === e.agent); if (d) celebrate(d.x, d.y - 30, '#a78bfa', `${e.agent}: ${String(e.detail || e.kind).slice(0, 22)}`); });
  entries.forEach((e) => seenChron.add(e.id));
}
async function load() {
  const [ag, cmd] = await Promise.all([api('/api/agents'), api('/api/command')]);
  if (window.__needAuth && !ag) { $('scene-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  DEMO = !!(cmd && cmd.demo);
  ensureDisciples((ag && ag.agents) || []);
  const reals = disciples.filter((d) => !d.extra).length;
  $('scene-sub').textContent = `${ROOMS.length} halls · ${reals} disciples · ${DEMO ? 'simulation' : 'live'}`;
}

function resize() {
  view.dpr = Math.min(devicePixelRatio || 1, 2); view.w = innerWidth; view.h = innerHeight;
  canvas.width = view.w * view.dpr; canvas.height = view.h * view.dpr; canvas.style.width = view.w + 'px'; canvas.style.height = view.h + 'px';
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0); layout();
  disciples.forEach((d) => { if (!d.path.length) { d.x = Math.max(B.x + 10, Math.min(B.x + B.w - 10, d.x)); d.y = roomFloorY(d.room || d.home); } });
}
addEventListener('resize', resize); resize();
load(); setInterval(load, 12000); setInterval(simTick, 2200); setInterval(pollBreak, 9000); setInterval(assembly, 22000);
requestAnimationFrame(frame);
