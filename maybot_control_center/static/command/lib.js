import * as THREE from '/vendor/three.module.js';

/* ---------------- helpers ---------------- */
export const $ = (id) => document.getElementById(id);
const TOKEN_KEY = 'maybot.control_token';
export const authHeaders = () => { const t = localStorage.getItem(TOKEN_KEY) || ''; return t ? { 'x-control-token': t } : {}; };
export const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
export const money = (n) => { const v = Number(n) || 0; const sign = v > 0 ? '+' : v < 0 ? '−' : ''; return `${sign}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; };
export async function api(path, opts) { try { const r = await fetch(path, { headers: authHeaders(), ...(opts || {}) }); if (r.status === 401) { window.__needAuth = true; return null; } return await r.json(); } catch (_) { return null; } }
export async function post(path, body) { return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(body) }); }
export const timeAgo = (ts) => { if (!ts) return ''; const s = (Date.now() - ts) / 1000; if (s < 60) return `${s | 0}s`; if (s < 3600) return `${s / 60 | 0}m`; return `${s / 3600 | 0}h`; };
export const HEALTH_COLOR = { ok: 0x34d399, warning: 0xfbbf24, error: 0xfb5e7e, unknown: 0x8b92ac };

/* ---------------- left command rail ---------------- */
const NAV = [
  ['command', '🏛', 'Command', '/'],
  ['trade', '📈', 'Trade', '/trade'],
  ['disciples', '🧠', 'Disciples', '/chamber'],
  ['missions', '⚔', 'Missions', '/classic'],
  ['projects', '📜', 'Realms', '/classic'],
  ['map', '🗺', 'Map', '/realm-map'],
  ['treasury', '🏦', 'Treasury', '/treasury'],
  ['ops', '⚙', 'Ops', '/classic'],
];
const TABMAP = { ops: 'ops', projects: 'overview', missions: 'sect' };
export function mountRail(active) {
  const el = $('rail'); if (!el) return;
  el.innerHTML = `<div class='rail-logo'>◆</div>` + NAV.map(([k, ico, lbl]) =>
    `<div class='nav-item ${k === active ? 'active' : ''}' data-nav='${k}'><span class='ni-ico'>${ico}</span><span class='ni-lbl'>${lbl}</span></div>`).join('');
  el.querySelectorAll('.nav-item').forEach((n) => n.onclick = () => {
    const k = n.dataset.nav; const dest = (NAV.find((x) => x[0] === k) || [])[3];
    if (k === active) return;
    if (dest === '/classic' && TABMAP[k]) localStorage.setItem('tab', TABMAP[k]);
    location.href = dest;
  });
}

/* ---------------- count-up + tilt ---------------- */
export function countUp(el, to, fmt) {
  const from = el.__v || 0; const start = performance.now(); const dur = 900;
  (function step(now) { const p = Math.min(1, (now - start) / dur); const e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(from + (to - from) * e); if (p < 1) requestAnimationFrame(step); else el.__v = to; })(start);
}
export function bindTilt(root = document) {
  root.querySelectorAll('[data-tilt]').forEach((el) => { if (el.__tilt) return; el.__tilt = 1;
    el.addEventListener('mousemove', (e) => { const r = el.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width - 0.5; const py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(800px) rotateX(${-py * 6}deg) rotateY(${px * 8}deg) translateY(-4px)`; });
    el.addEventListener('mouseleave', () => { el.style.transform = ''; });
  });
}

/* ---------------- shared starfield background ---------------- */
function sprite() { const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32); grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.25, 'rgba(220,210,255,.85)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); }
export function starfield(canvasId) {
  const canvas = $(canvasId); let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); } catch (_) { canvas.style.display = 'none'; return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight);
  const scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x05060c, 0.0016);
  const cam = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 1, 2000); cam.position.z = 8;
  const SP = sprite(); const group = new THREE.Group(); scene.add(group);
  const cloud = (n, spread, z, color, size, op) => { const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - .5) * spread; pos[i * 3 + 1] = (Math.random() - .5) * spread * .62; pos[i * 3 + 2] = z + (Math.random() - .5) * spread * .5; }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ size, map: SP, color, transparent: true, opacity: op, depthWrite: false, blending: THREE.AdditiveBlending })); };
  group.add(cloud(2600, 1500, -520, 0xffffff, 2.6, .95));
  group.add(cloud(820, 960, -360, 0x8b5cff, 11, .16));
  group.add(cloud(680, 1040, -540, 0x38bdf8, 10, .12));
  group.add(cloud(480, 860, -300, 0x34d399, 9, .09));
  const m = { x: 0, y: 0, tx: 0, ty: 0 };
  addEventListener('mousemove', (e) => { m.tx = (e.clientX / innerWidth) * 2 - 1; m.ty = (e.clientY / innerHeight) * 2 - 1; });
  addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); });
  (function loop() { requestAnimationFrame(loop); const t = performance.now() * 0.0001; group.rotation.y = t * 1.4;
    m.x += (m.tx - m.x) * .05; m.y += (m.ty - m.y) * .05; cam.position.x = m.x * 6; cam.position.y = -m.y * 4; cam.lookAt(0, 0, -200); renderer.render(scene, cam); })();
}
