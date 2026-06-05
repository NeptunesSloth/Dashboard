import * as THREE from '/vendor/three.module.js';
import { OrbitControls } from '/vendor/OrbitControls.js';
import { $, api, esc, money, mountRail, HEALTH_COLOR } from '/lib.js';

mountRail('map');

/* ====================================================================== *
 *  The Realm — a living cultivation sect you can watch operate.
 *  Projects are halls; disciples are characters that walk to them, work,
 *  roam, meditate, and celebrate breakthroughs. RimWorld-on-a-second-
 *  monitor, driven by real agent + project telemetry (demo synthesizes
 *  activity so the world is alive without live hosts).
 * ====================================================================== */

const canvas = $('scene-canvas');
let renderer;
try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' }); }
catch (_) { document.querySelector('.scene-stage').innerHTML = '<div class="glass" style="padding:30px;margin:auto">WebGL unavailable on this device.</div>'; }

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x05060c, 0.0026);
const camera = new THREE.PerspectiveCamera(52, innerWidth / innerHeight, 0.5, 5000);
camera.position.set(0, 95, 175);

const clock = new THREE.Clock();
let controls;
const rand = (a, b) => a + Math.random() * (b - a);
const pickOne = (arr) => arr[(Math.random() * arr.length) | 0];

if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = false;
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.autoRotate = true; controls.autoRotateSpeed = 0.28;
  controls.minDistance = 40; controls.maxDistance = 480; controls.maxPolarAngle = Math.PI * 0.49;
  controls.target.set(0, 6, 0);
  scene.add(new THREE.AmbientLight(0x5a608a, 1.5));
  const moon = new THREE.DirectionalLight(0xb9c2ff, 1.1); moon.position.set(70, 160, 60); scene.add(moon);
  const key = new THREE.PointLight(0xa78bfa, 2.4, 600); key.position.set(0, 70, 0); scene.add(key);
  scene.add(new THREE.PointLight(0x38bdf8, 1.1, 800, 2).translateX(-160).translateY(70).translateZ(60));
}

/* ---------------- shared soft sprite ---------------- */
function softSprite(stops) {
  const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  (stops || [[0, '#fff'], [0.3, 'rgba(220,210,255,.8)'], [1, 'rgba(255,255,255,0)']]).forEach(([o, col]) => grd.addColorStop(o, col));
  g.fillStyle = grd; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c);
}
const GLOW = softSprite();

/* ---------------- starry sky ---------------- */
(function sky() {
  const n = 2200, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const r = 900 + Math.random() * 1400, th = Math.random() * 6.28, ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th); pos[i * 3 + 1] = Math.abs(r * Math.cos(ph)) * 0.7 + 40; pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 2.6, map: GLOW, transparent: true, opacity: .8, depthWrite: false, blending: THREE.AdditiveBlending })));
})();

/* ---------------- ground ---------------- */
const GROUND_R = 150;
(function ground() {
  const disc = new THREE.Mesh(new THREE.CircleGeometry(GROUND_R, 96),
    new THREE.MeshStandardMaterial({ color: 0x0c0e1a, roughness: 1, metalness: 0 }));
  disc.rotation.x = -Math.PI / 2; disc.position.y = -0.02; scene.add(disc);
  const ring = new THREE.Mesh(new THREE.RingGeometry(GROUND_R - 2, GROUND_R, 96),
    new THREE.MeshBasicMaterial({ color: 0x6b5bd6, transparent: true, opacity: .35, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = 0.02; scene.add(ring);
  const grid = new THREE.PolarGridHelper(GROUND_R, 16, 10, 96, 0x2a2f55, 0x1a1e38);
  grid.position.y = 0.01; scene.add(grid);
})();

/* ---------------- the Sect Hall (home / origin) ---------------- */
const HOME = new THREE.Vector3(0, 0, 0);
(function sectHall() {
  const grp = new THREE.Group();
  const mat = (c, e, ei) => new THREE.MeshStandardMaterial({ color: c, emissive: e, emissiveIntensity: ei, roughness: .5, metalness: .5, flatShading: true });
  const base = new THREE.Mesh(new THREE.CylinderGeometry(16, 19, 7, 8), mat(0x232847, 0x3b2f7a, .3)); base.position.y = 3.5; grp.add(base);
  const mid = new THREE.Mesh(new THREE.CylinderGeometry(11, 14, 9, 8), mat(0x2b315a, 0x4b3fb0, .35)); mid.position.y = 11; grp.add(mid);
  const roof = new THREE.Mesh(new THREE.ConeGeometry(17, 8, 8), mat(0x7c5cff, 0x5b3df0, 1.1)); roof.position.y = 19; grp.add(roof);
  const spire = new THREE.Mesh(new THREE.ConeGeometry(2.4, 12, 6), mat(0xa78bfa, 0x8b5cff, 1.4)); spire.position.y = 28; grp.add(spire);
  const orb = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: 0xa78bfa, transparent: true, opacity: .9, blending: THREE.AdditiveBlending }));
  orb.scale.set(22, 22, 1); orb.position.y = 34; grp.add(orb);
  scene.add(grp);
  scene.add(makeLabel('Sect Hall', '#cbb9ff', 30).translateY(40));
})();

/* ---------------- label sprites ---------------- */
function makeLabel(text, color, size = 26) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64; const g = c.getContext('2d');
  g.font = `700 ${size}px system-ui, sans-serif`; g.textAlign = 'center'; g.fillStyle = color || '#eaecf6';
  g.shadowColor = 'rgba(0,0,0,.9)'; g.shadowBlur = 8; g.fillText(text, 128, 44);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthTest: false }));
  s.scale.set(text.length * 1.7 + 8, 7, 1); s.renderOrder = 5; return s;
}

/* ====================================================================== *
 *  Buildings (projects)
 * ====================================================================== */
const STYLE = { trading_bot: 'pavilion', trading: 'pavilion', api: 'tower', gateway: 'tower', service: 'tower',
  web: 'hall', site: 'hall', dashboard: 'hall', research: 'temple', ml: 'temple', ai: 'temple' };
const WORK = {
  pavilion: { tag: 'trading', color: 0x38bdf8, glyph: '⟁' },
  tower:    { tag: 'signals', color: 0x34d399, glyph: '⇡' },
  hall:     { tag: 'building', color: 0xfbbf24, glyph: '✦' },
  temple:   { tag: 'research', color: 0xa78bfa, glyph: '✷' },
};
function styleFor(type) { const k = String(type || '').toLowerCase(); return STYLE[k] || (k.includes('trad') ? 'pavilion' : k.includes('api') ? 'tower' : k.includes('research') || k.includes('ml') ? 'temple' : 'hall'); }

const buildings = [];   // {data, style, group, pos, door, color, glowMat, occupants:Set, fx, label}

function buildStructure(style, color) {
  const grp = new THREE.Group();
  const body = (c, e, ei) => new THREE.MeshStandardMaterial({ color: c, emissive: e, emissiveIntensity: ei, roughness: .55, metalness: .45, flatShading: true });
  const trimMat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: .9, roughness: .4, metalness: .5, flatShading: true });
  if (style === 'tower') {
    for (let i = 0; i < 3; i++) { const seg = new THREE.Mesh(new THREE.BoxGeometry(8 - i * 1.6, 7, 8 - i * 1.6), body(0x222845, 0x241f52, .25)); seg.position.y = 3.5 + i * 7; grp.add(seg); }
    const cap = new THREE.Mesh(new THREE.ConeGeometry(3.4, 6, 4), trimMat); cap.position.y = 25; grp.add(cap);
  } else if (style === 'temple') {
    const base = new THREE.Mesh(new THREE.CylinderGeometry(9, 11, 5, 6), body(0x222845, 0x2a2360, .25)); base.position.y = 2.5; grp.add(base);
    const dome = new THREE.Mesh(new THREE.SphereGeometry(7, 16, 12, 0, 6.28, 0, 1.57), trimMat); dome.position.y = 5; grp.add(dome);
  } else if (style === 'pavilion') {
    const base = new THREE.Mesh(new THREE.BoxGeometry(15, 5, 15), body(0x222845, 0x223055, .25)); base.position.y = 2.5; grp.add(base);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(12, 6, 4), trimMat); roof.position.y = 8.5; roof.rotation.y = Math.PI / 4; grp.add(roof);
    const roof2 = new THREE.Mesh(new THREE.ConeGeometry(8, 4, 4), trimMat); roof2.position.y = 12.5; roof2.rotation.y = Math.PI / 4; grp.add(roof2);
  } else { // hall
    const base = new THREE.Mesh(new THREE.BoxGeometry(16, 8, 12), body(0x232a4a, 0x262a55, .25)); base.position.y = 4; grp.add(base);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(12, 5, 4), trimMat); roof.position.y = 10.5; roof.rotation.y = Math.PI / 4; grp.add(roof);
  }
  // glowing doorway
  const door = new THREE.Mesh(new THREE.PlaneGeometry(4, 6), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .8, side: THREE.DoubleSide }));
  door.position.set(0, 3, style === 'tower' ? 4.1 : style === 'temple' ? 8.1 : style === 'pavilion' ? 7.6 : 6.1); grp.add(door);
  return { group: grp, glowMat: trimMat, door };
}

function buildingFootprint(p, i, total) {
  const a = (i / Math.max(1, total)) * Math.PI * 2 - Math.PI / 2;
  const r = 78 + (i % 2) * 16;
  return new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r);
}

function placeBuildings(projects) {
  buildings.forEach((b) => scene.remove(b.group));
  buildings.length = 0;
  projects.forEach((p, i) => {
    const style = styleFor(p.type);
    const color = HEALTH_COLOR[p.health] || HEALTH_COLOR.unknown;
    const { group, glowMat, door } = buildStructure(style, color);
    const pos = buildingFootprint(p, i, projects.length);
    group.position.copy(pos); group.lookAt(0, 0, 0); scene.add(group);
    // road from hall to the doorway
    const doorWorld = pos.clone().multiplyScalar(1 - 9 / pos.length());
    const road = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0.1, 0), doorWorld.clone().setY(0.1)]),
      new THREE.LineBasicMaterial({ color: 0x4a4690, transparent: true, opacity: .3 }));
    scene.add(road);
    const label = makeLabel(p.name, '#dfe3ff', 26); label.position.copy(pos).setY(style === 'tower' ? 32 : 20); scene.add(label);
    const aura = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color, transparent: true, opacity: .25, blending: THREE.AdditiveBlending }));
    aura.scale.set(34, 34, 1); aura.position.copy(pos).setY(8); scene.add(aura);
    buildings.push({ data: p, style, group, pos, door: doorWorld.setY(0), color, glowMat, aura,
      occupants: new Set(), fx: makeWorkFX(WORK[style], doorWorld), label });
  });
}

/* rising work particles above a busy building */
function makeWorkFX(work, at) {
  const n = 16, pos = new Float32Array(n * 3), seed = [];
  for (let i = 0; i < n; i++) { pos[i * 3] = at.x + rand(-3, 3); pos[i * 3 + 1] = rand(0, 16); pos[i * 3 + 2] = at.z + rand(-3, 3); seed.push(rand(6, 14)); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 3.4, map: GLOW, color: work.color, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
  pts.userData = { at, seed }; scene.add(pts);
  return pts;
}
function stepWorkFX(b, dt, intensity) {
  const pts = b.fx, arr = pts.geometry.attributes.position.array, base = pts.userData.at, seed = pts.userData.seed;
  for (let i = 0; i < seed.length; i++) {
    arr[i * 3 + 1] += seed[i] * dt * (0.6 + intensity);
    if (arr[i * 3 + 1] > 20) { arr[i * 3] = base.x + rand(-3, 3); arr[i * 3 + 1] = 0; arr[i * 3 + 2] = base.z + rand(-3, 3); }
  }
  pts.geometry.attributes.position.needsUpdate = true;
  pts.material.opacity += ((intensity > 0 ? 0.55 + 0.3 * intensity : 0) - pts.material.opacity) * Math.min(1, dt * 4);
  b.glowMat.emissiveIntensity = 0.7 + intensity * 0.9 + Math.sin(performance.now() * 0.004) * 0.15 * intensity;
  b.aura.material.opacity = 0.22 + intensity * 0.25;
}

/* ====================================================================== *
 *  Disciples (characters)
 * ====================================================================== */
const STATE_COLOR = { working: '#5ad1ff', traveling: '#9b8cff', idle: '#a78bfa', meditate: '#7c5cff', roaming: '#fbbf24', error: '#fb5e7e' };
const avatarCache = {};
function avatarTexture(robe) {
  if (avatarCache[robe]) return avatarCache[robe];
  const c = document.createElement('canvas'); c.width = 96; c.height = 128; const g = c.getContext('2d');
  g.shadowColor = robe; g.shadowBlur = 14;
  // robe (body)
  g.fillStyle = robe; g.beginPath(); g.moveTo(48, 30); g.lineTo(70, 110); g.quadraticCurveTo(48, 122, 26, 110); g.closePath(); g.fill();
  // sash
  g.shadowBlur = 0; g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 4; g.beginPath(); g.moveTo(34, 66); g.lineTo(62, 60); g.stroke();
  // head
  g.fillStyle = '#f3e9d8'; g.beginPath(); g.arc(48, 24, 13, 0, 6.28); g.fill();
  // hair/hood
  g.fillStyle = robe; g.beginPath(); g.arc(48, 20, 13, Math.PI, 0); g.fill();
  const t = new THREE.CanvasTexture(c); avatarCache[robe] = t; return t;
}

const disciples = [];   // see makeDisciple
const shadowTex = softSprite([[0, 'rgba(0,0,0,.5)'], [0.7, 'rgba(0,0,0,.25)'], [1, 'rgba(0,0,0,0)']]);

function plazaSpot() { const a = Math.random() * 6.28, r = rand(8, 26); return new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r); }

function makeDisciple(ag) {
  const mat = new THREE.SpriteMaterial({ map: avatarTexture(STATE_COLOR.idle), transparent: true, depthTest: true });
  const sp = new THREE.Sprite(mat); sp.scale.set(7, 9.3, 1); sp.center.set(0.5, 0); sp.userData.kind = 'disciple';
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(3, 16), new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, opacity: .6, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.05;
  const label = makeLabel(ag.name, '#cdd3f0', 22); label.scale.multiplyScalar(0.62);
  scene.add(sp); scene.add(shadow); scene.add(label);
  const home = plazaSpot();
  const d = { name: ag.name, data: ag, sp, mat, shadow, label, pos: home.clone(), target: home.clone(),
    state: 'idle', building: null, home, speed: rand(10, 15), bob: Math.random() * 6.28, pauseT: 0, robe: STATE_COLOR.idle };
  sp.userData.ref = d;
  disciples.push(d); return d;
}

function setRobe(d, color) { if (d.robe !== color) { d.robe = color; d.mat.map = avatarTexture(color); d.mat.needsUpdate = true; } }

/* decide where a disciple should be from its (real or simulated) status */
function deriveState(d) {
  const ag = d.data, cult = ag.cultivation || {};
  const sim = ag.__sim;                          // demo driver override
  const st = sim ? sim.state : (cult.in_seclusion ? 'meditate' : cult.in_roaming ? 'roaming'
    : (ag.status === 'working' || ag.status === 'queued') ? 'working' : ag.status === 'error' ? 'error' : 'idle');
  if (st === 'working') {
    const want = sim ? sim.building : matchBuilding(ag.current_task);
    if (want && d.building !== want) assignTo(d, want);
    else if (!want && buildings.length && !d.building) assignTo(d, pickOne(buildings));
    if (!buildings.length) { d.state = 'idle'; return; }
    d.state = (d.pos.distanceTo(d.building.door) < 6) ? 'working' : 'traveling';
    d.target.copy(d.building.door).add(offsetAround(d));
  } else {
    if (d.building) { d.building.occupants.delete(d); d.building = null; }
    if (st === 'roaming') { d.state = 'roaming'; }
    else if (st === 'meditate') { d.state = 'meditate'; d.target.copy(d.medSpot || (d.medSpot = meditationSpot())); }
    else if (st === 'error') { d.state = 'error'; }
    else { if (d.state !== 'idle') { d.state = 'idle'; } }
  }
}
let medCount = 0;
function meditationSpot() { const a = (medCount++) * 1.1; return new THREE.Vector3(Math.cos(a) * 30, 0, Math.sin(a) * 30); }
function offsetAround(d) { const a = (d.name.charCodeAt(0) + (d.idx || 0)) ; return new THREE.Vector3(Math.cos(a) * 5, 0, Math.sin(a) * 5); }
function matchBuilding(task) { if (!task) return null; const t = String(task).toLowerCase(); return buildings.find((b) => t.includes(String(b.data.name).toLowerCase())) || null; }
function assignTo(d, b) { if (d.building) d.building.occupants.delete(d); d.building = b; b.occupants.add(d); }

/* ====================================================================== *
 *  Roaming + breakthroughs (overlays / spectacle)
 * ====================================================================== */
const spectacles = [];
function celebrate(at, color, text) {
  const ring = new THREE.Mesh(new THREE.RingGeometry(1, 2.4, 40), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }));
  ring.rotation.x = -Math.PI / 2; ring.position.copy(at).setY(1); scene.add(ring);
  const lab = makeLabel('✦ ' + text, '#fff3cf', 24); lab.position.copy(at).setY(22); scene.add(lab);
  spectacles.push({ ring, lab, t: 0, at: at.clone() });
}
function stepSpectacles(dt) {
  for (let i = spectacles.length - 1; i >= 0; i--) {
    const s = spectacles[i]; s.t += dt; const k = s.t / 2.8;
    s.ring.scale.setScalar(1 + k * 26); s.ring.material.opacity = Math.max(0, .9 - k);
    s.lab.position.y = 22 + k * 12; s.lab.material.opacity = Math.max(0, 1 - k);
    if (s.t > 2.8) { scene.remove(s.ring); scene.remove(s.lab); spectacles.splice(i, 1); }
  }
}
function renderRoamTicker() {
  const roamers = disciples.filter((d) => d.state === 'roaming');
  const el = $('roam'); if (!roamers.length) { el.hidden = true; return; }
  el.hidden = false;
  const verbs = ['exploring external markets', 'gathering intelligence', 'researching independently', 'seeking rare techniques', 'surveying distant realms'];
  el.innerHTML = `<div class='panel-title'>Beyond the Realm</div>` + roamers.map((d, i) =>
    `<div class='roam-row'>🌄 <b>${esc(d.name)}</b> is ${verbs[(d.name.charCodeAt(0) + i) % verbs.length]}…</div>`).join('');
}

/* ====================================================================== *
 *  Picking + follow camera + detail panel
 * ====================================================================== */
const raycaster = new THREE.Raycaster(); raycaster.params.Sprite = { threshold: 1 };
const pointer = new THREE.Vector2();
let followed = null;
function onClick(e) {
  const r = canvas.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1; pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const dHit = raycaster.intersectObjects(disciples.map((d) => d.sp))[0];
  if (dHit) { follow(dHit.object.userData.ref); return; }
  const bHit = raycaster.intersectObjects(buildings.map((b) => b.group), true)[0];
  if (bHit) { let g = bHit.object; while (g.parent && !buildings.find((b) => b.group === g)) g = g.parent; const b = buildings.find((x) => x.group === g); if (b) selectBuilding(b); }
}
if (renderer) canvas.addEventListener('click', onClick);

function follow(d) {
  followed = d; controls.autoRotate = false;
  const chip = $('follow-chip'); chip.hidden = false;
  chip.innerHTML = `👁 Following <b>${esc(d.name)}</b> · <span class='fc-x'>release ✕</span>`;
  chip.querySelector('.fc-x').onclick = (ev) => { ev.stopPropagation(); unfollow(); };
  selectDisciple(d);
}
function unfollow() { followed = null; controls.autoRotate = true; $('follow-chip').hidden = true; }

function selectDisciple(d) {
  const ag = d.data, c = ag.cultivation || {}, g = ag.governance || {};
  const where = d.building ? `working at <b>${esc(d.building.data.name)}</b>`
    : d.state === 'roaming' ? 'roaming beyond the realm'
    : d.state === 'meditate' ? 'in closed-door meditation' : 'at the Sect Hall';
  const rows = [
    ['Rank', esc(g.is_leader ? 'Sect Leader' : c.rank_title || 'Disciple')],
    ['Realm', esc(c.realm_name || 'Mortal')],
    ['Status', esc(ag.status || 'idle')],
    ag.current_task ? ['Task', esc(String(ag.current_task).slice(0, 60))] : null,
    ['Tasks done', ag.tasks_done || 0],
  ].filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(d.name)}</div>
    <div class='muted' style='margin:8px 0 2px; font-size:12.5px'>Currently ${where}.</div>
    <div class='kvs'>${rows}</div>
    <div class='realm-actions'><button class='cbtn' id='r-cham'>Open Dossier</button>
      <button class='cbtn' id='r-rel'>Release Camera</button></div>`;
  $('r-cham').onclick = () => { location.href = '/chamber'; };
  $('r-rel').onclick = unfollow;
}
function selectBuilding(b) {
  const p = b.data, m = p.metrics || {}, pnl = Number(m.profit_today);
  const busy = b.occupants.size;
  const rows = [
    ['Type', esc(p.type || '')], ['Host', esc(p.device || '')], ['Disciples', busy ? `${busy} working` : 'none on site'],
    p.type === 'trading_bot' && Number.isFinite(pnl) ? ['PnL Today', money(pnl)] : null,
    p.oath ? ['Owner', '🤝 ' + esc(p.oath.who)] : null,
  ].filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(p.name)}</div>
    <div class='realm-health health-${esc(p.health || 'unknown')}'>${esc(p.health || 'unknown')}</div>
    <div class='kvs'>${rows}</div>
    <div class='realm-actions'><button class='cbtn' id='r-logs'>Open Logs</button>
      <button class='cbtn' id='r-assign'>Assign Disciple</button></div>`;
  $('r-logs').onclick = () => { localStorage.setItem('tab', 'overview'); location.href = '/classic'; };
  $('r-assign').onclick = () => { localStorage.setItem('tab', 'disciples'); location.href = '/classic'; };
}

/* ---------------- legend ---------------- */
$('legend').innerHTML = [['health-ok', 'thriving'], ['health-warning', 'strained'], ['health-error', 'failing'], ['', 'busy disciple']]
  .map(([h, l]) => `<span class='lg'><i class='lg-dot ${h || 'lg-link'}'></i>${l}</span>`).join('');

/* ====================================================================== *
 *  Animation loop
 * ====================================================================== */
function stepDisciple(d, dt, t) {
  const toT = d.target.clone().sub(d.pos); toT.y = 0; const dist = toT.length();
  const moving = dist > 1.2 && d.state !== 'roaming' || (d.state === 'roaming');
  // roaming: walk to the rim then fade out, drift, fade back
  if (d.state === 'roaming') {
    if (!d.roamPhase) { d.roamPhase = 'out'; d.target.copy(d.pos).normalize().multiplyScalar(GROUND_R - 6); if (d.target.length() < 1) d.target.set(GROUND_R - 6, 0, 0); }
    if (d.roamPhase === 'out' && dist < 4) { d.roamPhase = 'gone'; d.goneT = t + rand(6, 14); }
    if (d.roamPhase === 'gone') { d.mat.opacity = Math.max(0, d.mat.opacity - dt); if (t > d.goneT) { d.roamPhase = 'back'; d.target.copy(d.home); } }
    else d.mat.opacity = Math.min(1, d.mat.opacity + dt * 1.5);
    if (d.roamPhase === 'back' && dist < 4) { d.roamPhase = null; if (d.data.__sim) d.data.__sim = { state: 'idle' }; }
  }
  if (dist > 1.2) {
    d.pos.addScaledVector(toT.normalize(), Math.min(dist, d.speed * dt));
    d.bob += dt * 12; const bobY = Math.abs(Math.sin(d.bob)) * 0.9;
    d.sp.position.set(d.pos.x, bobY, d.pos.z);
  } else {
    // arrived — idle behaviours
    if (d.state === 'idle') { d.pauseT -= dt; if (d.pauseT <= 0) { d.target.copy(plazaSpot()); d.pauseT = rand(2, 6); } }
    if (d.state === 'meditate') { d.sp.position.y = 0; }
    const breathe = Math.sin(t * 2 + d.bob) * 0.25;
    d.sp.position.set(d.pos.x, d.state === 'working' ? Math.abs(Math.sin(t * 4 + d.bob)) * 0.5 : breathe + 0.2, d.pos.z);
  }
  d.shadow.position.set(d.pos.x, 0.05, d.pos.z);
  d.shadow.material.opacity = 0.55 * d.mat.opacity;
  d.label.position.set(d.pos.x, 11, d.pos.z); d.label.material.opacity = d.mat.opacity;
  // colour by state
  setRobe(d, STATE_COLOR[d.state] || STATE_COLOR.idle);
}

let lastDerive = 0;
function loop() {
  requestAnimationFrame(loop);
  const dt = Math.min(0.05, clock.getDelta()), t = clock.elapsedTime;
  if (t - lastDerive > 0.4) { disciples.forEach(deriveState); lastDerive = t; }
  disciples.forEach((d) => stepDisciple(d, dt, t));
  buildings.forEach((b) => stepWorkFX(b, dt, Math.min(1.6, b.occupants.size * 0.7)));
  stepSpectacles(dt);
  if (followed) { controls.target.lerp(followed.sp.position.clone().setY(6), 0.06); }
  controls.update(); renderer.render(scene, camera);
}
if (renderer) {
  addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); });
  loop();
}

/* ====================================================================== *
 *  Data + demo simulation driver
 * ====================================================================== */
const DEMO_PROJECTS = [
  { name: 'Aurelius', type: 'trading_bot', health: 'ok', device: 'forge-01', metrics: { profit_today: 418.2 } },
  { name: 'Helios', type: 'trading_bot', health: 'ok', device: 'forge-01', metrics: { profit_today: 196.4 } },
  { name: 'Aegis Dashboard', type: 'dashboard', health: 'ok', device: 'core-01' },
  { name: 'Gateway', type: 'api', health: 'warning', device: 'core-01' },
  { name: 'Oracle', type: 'research', health: 'ok', device: 'lab-02' },
  { name: 'Commerce', type: 'web', health: 'ok', device: 'edge-03' },
  { name: 'Sentinel', type: 'service', health: 'error', device: 'edge-03' },
  { name: 'Scriptorium', type: 'ml', health: 'ok', device: 'lab-02' },
];
let DEMO = false;

function ensureDisciples(agents) {
  const have = new Set(disciples.map((d) => d.name));
  agents.forEach((a, i) => { if (!have.has(a.name)) { const d = makeDisciple(a); d.idx = i; } });
  disciples.forEach((d) => { const fresh = agents.find((a) => a.name === d.name); if (fresh) { if (d.data.__sim) fresh.__sim = d.data.__sim; d.data = fresh; } });
}

/* in demo, statuses are mostly idle — synthesise a believable workday */
function simTick() {
  if (!DEMO || !disciples.length || !buildings.length) return;
  disciples.forEach((d) => { if (!d.data.__sim) d.data.__sim = { state: 'idle' }; });
  const roll = Math.random();
  const d = pickOne(disciples);
  if (d.data.__sim.state === 'idle') {
    if (roll < 0.55) d.data.__sim = { state: 'working', building: pickOne(buildings) };
    else if (roll < 0.72) d.data.__sim = { state: 'roaming' };
    else if (roll < 0.8) d.data.__sim = { state: 'meditate' };
  } else if (d.data.__sim.state === 'working' && roll < 0.4) {
    d.data.__sim = { state: 'idle' };
    if (Math.random() < 0.5) celebrate(d.sp.position, 0xfbbf24, `${d.name}: ${pickOne(['milestone', 'profit target', 'deploy', 'breakthrough'])}`);
  }
}

let seenChron = null;
async function pollBreakthroughs() {
  const ch = await api('/api/chronicle?limit=20'); if (!ch) return;
  const entries = ch.recent || [];
  if (seenChron === null) { seenChron = new Set(entries.map((e) => e.id)); return; }
  entries.filter((e) => !seenChron.has(e.id) && ['breakthrough', 'milestone', 'title', 'ascension'].includes(e.kind)).forEach((e) => {
    const d = disciples.find((x) => x.name === e.agent);
    if (d) celebrate(d.sp.position, 0xa78bfa, `${e.agent}: ${String(e.detail || e.kind).slice(0, 28)}`);
  });
  entries.forEach((e) => seenChron.add(e.id));
}

async function load() {
  const [ov, ag, mer, cmd] = await Promise.all([api('/api/overview'), api('/api/agents'), api('/api/meridians'), api('/api/command')]);
  if (window.__needAuth && !ag) { $('scene-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  DEMO = !!(cmd && cmd.demo);
  let projects = (ov && ov.projects) || [];
  if (!projects.length) projects = DEMO_PROJECTS;     // a sect is never empty
  if (!buildings.length || buildings.length !== projects.length) placeBuildings(projects);
  const agents = (ag && ag.agents) || [];
  ensureDisciples(agents);
  $('scene-sub').textContent = `${projects.length} halls · ${disciples.length} disciples · ${DEMO ? 'simulation' : 'live'}`;
}
load();
setInterval(load, 12000);
setInterval(simTick, 2600);
setInterval(pollBreakthroughs, 9000);
