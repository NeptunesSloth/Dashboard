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
  ['disciples', '🧠', 'Sect Members', '/chamber'],
  ['missions', '⚔', 'Missions', '/console'],
  ['projects', '📜', 'Realms', '/console'],
  ['map', '🗺', 'Map', '/console'],
  ['halls', '⛩', 'Halls', '/console'],
  ['treasury', '🏦', 'Treasury', '/treasury'],
  ['ops', '⚙', 'Ops', '/console'],
];
const TABMAP = { ops: 'ops', projects: 'overview', missions: 'disciples', map: 'map', halls: 'sect' };
export function mountRail(active) {
  const el = $('rail'); if (!el) return;
  el.innerHTML = `<div class='rail-logo'>◆</div>` + NAV.map(([k, ico, lbl]) =>
    `<div class='nav-item ${k === active ? 'active' : ''}' data-nav='${k}'><span class='ni-ico'>${ico}</span><span class='ni-lbl'>${lbl}</span></div>`).join('');
  el.querySelectorAll('.nav-item').forEach((n) => n.onclick = () => {
    const k = n.dataset.nav; const dest = (NAV.find((x) => x[0] === k) || [])[3];
    if (k === active) return;
    if (dest === '/console' && TABMAP[k]) localStorage.setItem('tab', TABMAP[k]);
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

/* ---------------- account bubble + menu + startup auth guard ------------- */
const _AKEY = 'maybot.control_token';
function _ael(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }

export async function initAccount() {
  let me = {};
  try { me = await api('/api/account/me'); } catch (_) {}
  me = me || {};
  if (!me.authed && me.auth_active) { location.href = '/login'; return; }   // startup guard
  window.__isOperator = (me.role === 'operator') || !!me.open_mode;
  mountAccountBubble(me);
  mountBell();
}

function mountAccountBubble(me) {
  document.getElementById('acct-bubble')?.remove();
  document.getElementById('acct-menu')?.remove();
  const authed = me.authed && me.name;
  const name = authed ? me.name : 'Guest';
  const role = authed ? me.role : 'open access';
  const bubble = _ael('button', 'acct-bubble');
  bubble.id = 'acct-bubble';
  bubble.innerHTML = `<span class='acct-av'>${esc((name[0] || '?').toUpperCase())}</span>
    <span style='display:flex;flex-direction:column;line-height:1.15'><span class='acct-name'>${esc(name)}</span><span class='acct-role'>${esc(role)}</span></span>
    <span class='acct-chev'>▾</span>`;
  const menu = _ael('div', 'acct-menu'); menu.id = 'acct-menu';
  let items = `<div class='acct-head'><b>${esc(name)}</b><span>${esc(role)}</span></div>`;
  if (authed) {
    items += `<button class='acct-item' data-act='pw'><span class='ai-ico'>🔑</span> Change password</button>`;
    const can2fa = (me.channels || []).length > 0;
    items += `<button class='acct-item' data-act='2fa'${can2fa ? '' : ' disabled title="set up a notification channel first"'}>
      <span class='ai-ico'>🛡</span> Two-factor <span class='ai-tag'>${me.tfa ? 'on' : (can2fa ? 'off' : 'unavailable')}</span></button>`;
    if (me.role === 'operator')
      items += `<button class='acct-item' data-act='accounts'><span class='ai-ico'>👥</span> Manage accounts</button>`;
    items += `<button class='acct-item danger' data-act='out'><span class='ai-ico'>⎋</span> Sign out</button>`;
  } else {
    items += `<button class='acct-item' data-act='login'><span class='ai-ico'>＋</span> Create / sign in</button>`;
  }
  menu.innerHTML = items;
  document.body.append(bubble, menu);
  const toggle = (on) => menu.classList.toggle('open', on ?? !menu.classList.contains('open'));
  bubble.onclick = (e) => { e.stopPropagation(); toggle(); };
  document.addEventListener('click', (e) => { if (!menu.contains(e.target) && e.target !== bubble) toggle(false); });
  menu.querySelectorAll('.acct-item').forEach((b) => b.onclick = () => { toggle(false); acctAction(b.dataset.act, me); });
}

async function acctAction(act, me) {
  if (act === 'login') { location.href = '/login'; return; }
  if (act === 'accounts') { localStorage.setItem('tab', 'ops'); location.href = '/console'; return; }
  if (act === 'out') {
    try { await post('/api/logout', { session: localStorage.getItem(_AKEY) || '' }); } catch (_) {}
    localStorage.removeItem(_AKEY); location.href = '/login'; return;
  }
  if (act === '2fa') {
    const r = await post('/api/account/2fa', { enable: !me.tfa });
    if (r && r.ok) initAccount(); else alert((r && r.detail) || 'Could not change 2FA.');
    return;
  }
  if (act === 'pw') openPasswordModal(me);
}

function openPasswordModal(me) {
  document.getElementById('acct-modal')?.remove();
  const m = _ael('div', 'acct-modal'); m.id = 'acct-modal';
  m.innerHTML = `<div class='acct-modal-box glass'>
    <h3>Change password</h3>
    ${me.has_password ? `<label class='lf-label'>Current password</label><input class='lf-input' id='pw-old' type='password'>` : `<p class='muted' style='font-size:12.5px;margin:0 0 6px'>Set a password for this account.</p>`}
    <label class='lf-label'>New password</label><input class='lf-input' id='pw-new' type='password' placeholder='at least 8 characters'>
    <label class='lf-label'>Confirm</label><input class='lf-input' id='pw-new2' type='password'>
    <button class='lf-btn' id='pw-save'>Save</button>
    <div class='lf-err' id='pw-err'></div><div class='lf-ok' id='pw-ok'></div>
    <button class='lf-link' id='pw-cancel'>Cancel</button>
  </div>`;
  document.body.appendChild(m);
  m.addEventListener('click', (e) => { if (e.target === m) m.remove(); });
  m.querySelector('#pw-cancel').onclick = () => m.remove();
  m.querySelector('#pw-save').onclick = async () => {
    const err = m.querySelector('#pw-err'), ok = m.querySelector('#pw-ok');
    err.textContent = ''; ok.textContent = '';
    const nv = m.querySelector('#pw-new').value, nv2 = m.querySelector('#pw-new2').value;
    if (nv.length < 8) { err.textContent = 'Password must be at least 8 characters.'; return; }
    if (nv !== nv2) { err.textContent = 'Passwords do not match.'; return; }
    const body = { new: nv }; const oldEl = m.querySelector('#pw-old'); if (oldEl) body.old = oldEl.value;
    const r = await post('/api/account/password', body);
    if (r && r.ok) { ok.textContent = 'Password updated.'; setTimeout(() => m.remove(), 900); }
    else err.textContent = (r && r.detail) || 'Could not update password.';
  };
}

/* ---------------- notifications bell ---------------- */
function _ago(ts) { if (!ts) return ''; const s = Date.now() / 1000 - ts; if (s < 60) return `${s | 0}s ago`; if (s < 3600) return `${s / 60 | 0}m ago`; if (s < 86400) return `${s / 3600 | 0}h ago`; return `${s / 86400 | 0}d ago`; }
export function mountBell() {
  document.getElementById('bell')?.remove(); document.getElementById('bell-menu')?.remove();
  const bell = _ael('button', 'bell'); bell.id = 'bell'; bell.innerHTML = `🔔<span class='bell-badge' id='bell-badge' hidden>0</span>`;
  const menu = _ael('div', 'bell-menu'); menu.id = 'bell-menu';
  document.body.append(bell, menu);
  const bubble = document.getElementById('acct-bubble');
  const place = () => { const w = bubble ? bubble.offsetWidth : 120; bell.style.right = (16 + w + 10) + 'px'; };
  place(); setTimeout(place, 250); addEventListener('resize', place);
  async function refresh() {
    const d = await api('/api/notifications'); const ev = (d && d.recent) || [];
    const seen = Number(localStorage.getItem('maybot.notif_seen') || 0);
    const unseen = ev.filter((e) => (e.ts * 1000) > seen).length;
    const badge = document.getElementById('bell-badge');
    if (badge) { if (unseen > 0) { badge.hidden = false; badge.textContent = unseen > 9 ? '9+' : String(unseen); } else badge.hidden = true; }
    menu.innerHTML = `<div class='acct-head'><b>Notifications</b><span>${(d && d.channels || []).length ? 'via ' + d.channels.join(', ') : 'no channels configured'}</span></div>`
      + (ev.length ? ev.slice().reverse().slice(0, 20).map((e) => `<div class='notif lvl-${esc(e.level || 'info')}'><div class='notif-t'>${esc(e.title || '')}</div>${e.body ? `<div class='notif-b'>${esc(e.body)}</div>` : ''}<div class='notif-time'>${_ago(e.ts)}</div></div>`).join('') : `<div class='muted' style='padding:12px'>No notifications yet.</div>`);
  }
  bell.onclick = (e) => { e.stopPropagation(); const open = menu.classList.toggle('open'); if (open) { localStorage.setItem('maybot.notif_seen', String(Date.now())); const b = document.getElementById('bell-badge'); if (b) b.hidden = true; } };
  document.addEventListener('click', (e) => { if (!menu.contains(e.target) && e.target !== bell) menu.classList.remove('open'); });
  refresh(); setInterval(refresh, 15000);
}

/* ---------------- per-bot log popover ---------------- */
export async function openLogs(device, project) {
  document.getElementById('logs-pop')?.remove();
  const pop = _ael('div', 'logs-pop'); pop.id = 'logs-pop';
  pop.innerHTML = `<div class='logs-pop-box glass'>
    <div class='logs-pop-head'><b>${esc(project)}</b> <span class='muted'>${esc(device || '')}</span>
      <span class='logs-levels'>${['ALL', 'ERROR', 'WARNING', 'INFO'].map((l) => `<button class='lvl ${l === 'ALL' ? 'on' : ''}' data-lvl='${l}'>${l}</button>`).join('')}
        <button class='lvl' id='logs-dx' title='Heuristic root-cause analysis'>🔍 Diagnose</button></span>
      <button class='logs-pop-x' id='logs-x'>✕</button></div>
    <div class='logs-diag' id='logs-diag' hidden></div>
    <pre class='logs-pre' id='logs-pre'>Loading…</pre></div>`;
  document.body.appendChild(pop);
  document.getElementById('logs-dx').onclick = async () => {
    const box = document.getElementById('logs-diag'); box.hidden = false; box.innerHTML = `<span class='muted'>Diagnosing…</span>`;
    const d = await post(`/api/projects/${encodeURIComponent(device)}/${encodeURIComponent(project)}/explain`, {});
    if (!d || !d.ok) { box.innerHTML = `<span class='money-neg'>${esc((d && (d.error || d.detail)) || 'diagnosis failed')}</span>`; return; }
    box.innerHTML = `<div class='diag-sum'>🩺 ${esc(d.summary)}</div>`
      + (d.explanation ? `<div class='diag-explain'>${esc(d.explanation)}</div>` : '')
      + (d.suggestion ? `<div class='diag-fix'>→ ${esc(d.suggestion)}</div>` : '')
      + (d.findings && d.findings.length ? `<div class='diag-finds'>${d.findings.map((f) => `<span class='diag-chip'>${esc(f.signal)} ·${f.count}</span>`).join('')}</div>` : '')
      + `<div class='muted' style='font-size:11px;margin-top:4px'>scanned ${d.lines_scanned} log lines</div>`;
  };
  pop.addEventListener('click', (e) => { if (e.target === pop) pop.remove(); });
  document.getElementById('logs-x').onclick = () => pop.remove();
  document.addEventListener('keydown', function esc2(e) { if (e.key === 'Escape') { pop.remove(); document.removeEventListener('keydown', esc2); } });
  let level = 'ALL';
  async function load() {
    const pre = document.getElementById('logs-pre'); if (!pre) return; pre.textContent = 'Loading…';
    const d = await api(`/api/logs/${encodeURIComponent(device)}/${encodeURIComponent(project)}?level=${level}`);
    const lines = d && (d.lines || d.log || d.entries);
    pre.textContent = Array.isArray(lines) && lines.length ? lines.join('\n') : ((d && d.detail) ? d.detail : 'No log lines.');
    pre.scrollTop = pre.scrollHeight;
  }
  pop.querySelectorAll('.lvl').forEach((b) => b.onclick = () => { level = b.dataset.lvl; pop.querySelectorAll('.lvl').forEach((x) => x.classList.toggle('on', x === b)); load(); });
  load();
}

/* ---------------- live updates over SSE ---------------- */
export function liveStream(onEvent) {
  let es;
  try { es = new EventSource(`/api/stream?token=${encodeURIComponent(localStorage.getItem(TOKEN_KEY) || '')}`); }
  catch (_) { return null; }
  es.onmessage = (e) => { let m; try { m = JSON.parse(e.data); } catch (_) { return; } onEvent(m.type, m.data); };
  es.onerror = () => {};
  return es;
}
let _liveT;
export function debounce(fn, ms = 400) { clearTimeout(_liveT); _liveT = setTimeout(fn, ms); }
