import * as THREE from '/vendor/three.module.js';
import { OrbitControls } from '/vendor/OrbitControls.js';
import { $, api, esc, money, mountRail, HEALTH_COLOR } from '/lib.js';

mountRail('map');

const canvas = $('scene-canvas');
let renderer;
try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); }
catch (_) { document.querySelector('.scene-stage').innerHTML = '<div class="glass" style="padding:30px;margin:auto">WebGL unavailable.</div>'; }

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x05060c, 0.0019);
const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.1, 4000);
camera.position.set(0, 60, 150);

let controls;
if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.autoRotate = true; controls.autoRotateSpeed = 0.5;
  controls.minDistance = 50; controls.maxDistance = 360; controls.maxPolarAngle = Math.PI * 0.85;
  controls.target.set(0, 0, 0);
  scene.add(new THREE.AmbientLight(0x404a6a, 1.4));
  const key = new THREE.PointLight(0xa78bfa, 2.2, 1200); key.position.set(80, 120, 80); scene.add(key);
  scene.add(new THREE.PointLight(0x38bdf8, 1.4, 1200).translateX(-120).translateY(60));
}

/* starfield backdrop */
function sprite() { const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32); grd.addColorStop(0, '#fff'); grd.addColorStop(.3, 'rgba(220,210,255,.8)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); }
const SP = sprite();
(function stars() { const n = 2600, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { const r = 600 + Math.random() * 900, th = Math.random() * 6.28, ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th); pos[i * 3 + 1] = r * Math.cos(ph) * 0.5; pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 2.4, map: SP, transparent: true, opacity: .85, depthWrite: false, blending: THREE.AdditiveBlending }))); })();

/* sect core */
const core = new THREE.Mesh(new THREE.IcosahedronGeometry(9, 1),
  new THREE.MeshStandardMaterial({ color: 0x7c5cff, emissive: 0x5b3df0, emissiveIntensity: 1.2, roughness: .3, metalness: .6, flatShading: true }));
scene.add(core);
const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: SP, color: 0xa78bfa, transparent: true, opacity: .8, blending: THREE.AdditiveBlending }));
coreGlow.scale.set(60, 60, 1); scene.add(coreGlow);

function labelSprite(text, color) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64; const g = c.getContext('2d');
  g.font = '600 30px system-ui, sans-serif'; g.fillStyle = '#eaecf6'; g.textAlign = 'center'; g.shadowColor = color; g.shadowBlur = 12;
  g.fillText(text, 128, 42);
  const t = new THREE.CanvasTexture(c); const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false }));
  s.scale.set(40, 10, 1); return s;
}

const worlds = [];           // {mesh, glow, data}
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const units = new THREE.Group(); scene.add(units);
const links = new THREE.Group(); scene.add(links);

function build(projects, meridians, agents) {
  worlds.forEach((w) => { scene.remove(w.mesh); scene.remove(w.glow); scene.remove(w.label); });
  worlds.length = 0; units.clear(); links.clear();
  const list = projects.slice(0, 14);
  const R = 70;
  const byKey = {};
  list.forEach((p, i) => {
    const a = (i / list.length) * Math.PI * 2;
    const r = R + (i % 3) * 14;
    const pos = new THREE.Vector3(Math.cos(a) * r, (Math.sin(i * 1.7) * 10), Math.sin(a) * r);
    const col = HEALTH_COLOR[p.health] || HEALTH_COLOR.unknown;
    const size = p.type === 'trading_bot' ? 7 : 5;
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 32, 32),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: .5, roughness: .35, metalness: .4 }));
    mesh.position.copy(pos); mesh.userData = p; scene.add(mesh);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: SP, color: col, transparent: true, opacity: .55, blending: THREE.AdditiveBlending }));
    glow.scale.set(size * 5, size * 5, 1); glow.position.copy(pos); scene.add(glow);
    const label = labelSprite(p.name, '#' + col.toString(16)); label.position.copy(pos).add(new THREE.Vector3(0, size + 8, 0)); scene.add(label);
    worlds.push({ mesh, glow, label, data: p, pos });
    byKey[`${p.device}:${p.name}`] = pos;
    // link to core
    links.add(energyLine(new THREE.Vector3(0, 0, 0), pos, 0x6b5bd6, .18));
  });
  // meridian dependency links (azure)
  Object.entries(meridians || {}).forEach(([proj, deps]) => {
    (deps || []).forEach((dep) => { const a = byKey[proj], b = byKey[dep]; if (a && b) links.add(energyLine(a, b, 0x38bdf8, .5)); });
  });
  // agent units orbiting the core
  (agents || []).slice(0, 18).forEach((ag, i) => {
    const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: SP, color: ag.status === 'working' ? 0x34d399 : 0xa78bfa, transparent: true, opacity: .9, blending: THREE.AdditiveBlending }));
    dot.scale.set(6, 6, 1); dot.userData = { a: (i / 18) * 6.28, r: 26 + (i % 4) * 5, sp: 0.2 + Math.random() * 0.3, y: (Math.random() - .5) * 16 };
    units.add(dot);
  });
}

function energyLine(a, b, color, opacity) {
  const g = new THREE.BufferGeometry().setFromPoints([a, b]);
  return new THREE.Line(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending }));
}

/* picking */
function pick(e) {
  const r = canvas.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1; pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(worlds.map((w) => w.mesh))[0];
  if (hit) selectWorld(hit.object.userData);
}
if (renderer) canvas.addEventListener('click', pick);

function selectWorld(p) {
  const m = p.metrics || {};
  const pnl = Number(m.profit_today);
  const rows = [
    ['Type', esc(p.type || '')], ['Host', esc(p.device || '')], ['Status', esc(p.status || '')],
    p.type === 'trading_bot' && Number.isFinite(pnl) ? ['PnL Today', money(pnl)] : null,
    p.oath ? ['Owner', '🤝 ' + esc(p.oath.who)] : null,
    p.frozen ? ['State', '🔒 frozen'] : null,
  ].filter(Boolean).map(([k, v]) => `<div class='kv'><span>${k}</span><b>${v}</b></div>`).join('');
  $('detail').innerHTML = `<div class='panel-title'>${esc(p.name)}</div>
    <div class='realm-health health-${esc(p.health || 'unknown')}'>${esc(p.health || 'unknown')}</div>
    <div class='kvs'>${rows}</div>
    <div class='realm-actions'>
      <button class='cbtn' id='r-logs'>Open Logs</button>
      <button class='cbtn' id='r-assign'>Assign Disciple</button>
    </div>`;
  $('r-logs').onclick = () => { localStorage.setItem('tab', 'overview'); location.href = '/classic'; };
  $('r-assign').onclick = () => { localStorage.setItem('tab', 'disciples'); location.href = '/classic'; };
}

/* legend */
$('legend').innerHTML = [['ok', 'healthy'], ['warning', 'warning'], ['error', 'error'], ['', 'dependency']]
  .map(([h, l]) => `<span class='lg'><i class='lg-dot ${h ? 'health-' + h : 'lg-link'}'></i>${l}</span>`).join('');

/* animate */
if (renderer) {
  addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); });
  (function loop() {
    requestAnimationFrame(loop); const t = performance.now() * 0.001;
    core.rotation.y += 0.004; core.rotation.x += 0.001;
    worlds.forEach((w, i) => { w.mesh.position.y = w.pos.y + Math.sin(t + i) * 1.5; w.glow.position.copy(w.mesh.position); w.label.position.copy(w.mesh.position).add(new THREE.Vector3(0, 14, 0)); });
    units.children.forEach((d) => { const u = d.userData; u.a += u.sp * 0.02; d.position.set(Math.cos(u.a) * u.r, u.y + Math.sin(u.a * 2) * 3, Math.sin(u.a) * u.r); });
    controls.update(); renderer.render(scene, camera);
  })();
}

async function load() {
  const [ov, mer, ag] = await Promise.all([api('/api/overview'), api('/api/meridians'), api('/api/agents')]);
  if (window.__needAuth && !ov) { $('scene-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  const projects = (ov && ov.projects) || [];
  $('scene-sub').textContent = `${projects.length} realms · ${((ag && ag.agents) || []).length} disciples`;
  if (renderer) build(projects, (mer && mer.meridians) || {}, (ag && ag.agents) || []);
}
load();
setInterval(load, 12000);
