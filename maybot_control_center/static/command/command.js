import * as THREE from '/vendor/three.module.js';
import { initAccount, openLogs, liveStream, debounce, post } from '/lib.js';
initAccount();

/* ============================ helpers ============================ */
const $ = (id) => document.getElementById(id);
const TOKEN_KEY = 'maybot.control_token';
const authHeaders = () => { const t = localStorage.getItem(TOKEN_KEY) || ''; return t ? { 'x-control-token': t } : {}; };
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const money = (n) => { const v = Number(n) || 0; const sign = v > 0 ? '+' : v < 0 ? '−' : ''; return `${sign}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; };
async function api(path) { try { const r = await fetch(path, { headers: authHeaders() }); if (r.status === 401) { window.__needAuth = true; return null; } return await r.json(); } catch (_) { return null; } }

/* ============================ 3D background ============================ */
function softSprite() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.25, 'rgba(220,210,255,0.85)');
  grd.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c); return t;
}
function cloud(count, spread, z, color, size, opacity) {
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * spread;
    pos[i * 3 + 1] = (Math.random() - 0.5) * spread * 0.62;
    pos[i * 3 + 2] = z + (Math.random() - 0.5) * spread * 0.5;
  }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ size, map: SPRITE, color, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
  return new THREE.Points(geo, mat);
}
let SPRITE, renderer, scene, camera, group, raf;
const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
function init3D() {
  const canvas = $('bg-canvas');
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' }); }
  catch (_) { canvas.style.display = 'none'; return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x05060c, 0.0016);
  camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 1, 2000); camera.position.set(0, 0, 8);
  SPRITE = softSprite();
  group = new THREE.Group(); scene.add(group);
  group.add(cloud(2600, 1500, -520, 0xffffff, 2.6, 0.95));         // starfield
  group.add(cloud(820, 960, -360, 0x8b5cff, 11, 0.16));             // violet nebula
  group.add(cloud(680, 1040, -540, 0x38bdf8, 10, 0.12));            // azure nebula
  group.add(cloud(480, 860, -300, 0x34d399, 9, 0.09));            // jade nebula
  // qi streams
  STREAMS = [];
  for (let i = 0; i < 5; i++) {
    const n = 60, pos = new Float32Array(n * 3);
    const ox = (Math.random() - 0.5) * 700, oy = (Math.random() - 0.5) * 380, oz = -200 - Math.random() * 400;
    for (let j = 0; j < n; j++) { pos[j * 3] = ox + j * 6; pos[j * 3 + 1] = oy + Math.sin(j * 0.3) * 18; pos[j * 3 + 2] = oz; }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0xa78bfa, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending }));
    line.userData.speed = 0.3 + Math.random() * 0.5; group.add(line); STREAMS.push(line);
  }
  addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); });
  animate();
}
let STREAMS = [];
function animate() {
  raf = requestAnimationFrame(animate);
  const t = performance.now() * 0.0001;
  group.rotation.y = t * 1.4; group.rotation.x = Math.sin(t * 0.6) * 0.04;
  mouse.x += (mouse.tx - mouse.x) * 0.05; mouse.y += (mouse.ty - mouse.y) * 0.05;
  camera.position.x = mouse.x * 6; camera.position.y = -mouse.y * 4; camera.lookAt(0, 0, -200);
  STREAMS.forEach((l) => { l.position.x = ((l.position.x + l.userData.speed) % 700) ; });
  renderer.render(scene, camera);
}
addEventListener('mousemove', (e) => {
  mouse.tx = (e.clientX / innerWidth) * 2 - 1; mouse.ty = (e.clientY / innerHeight) * 2 - 1;
  document.querySelectorAll('[data-depth]').forEach((el) => {
    const d = parseFloat(el.dataset.depth) || 1;
    el.style.transform = `translate3d(${mouse.tx * -6 * d}px, ${mouse.ty * -5 * d}px, 0)`;
  });
});

/* ============================ count-up ============================ */
function countUp(el, to, fmt) {
  const from = el.__v || 0; const start = performance.now(); const dur = 900;
  function step(now) {
    const p = Math.min(1, (now - start) / dur); const e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (p < 1) requestAnimationFrame(step); else el.__v = to;
  }
  requestAnimationFrame(step);
}

/* ============================ data + render ============================ */
/* Fleet-level stats — OPS-focused, NOT trading PnL (that lives on /trade). */
function renderFleetStats(summary, agents) {
  const s = summary || {};
  const online = Number(s.online_devices || 0), total = Number(s.total_devices || 0);
  const bots = Number(s.bots_running || 0);
  const warn = Number(s.projects_with_warnings_errors || 0);
  const tests = Number(s.tests_failing || 0);
  const active = (agents || []).filter((a) => a.current_task || a.status === 'working' || a.status === 'queued').length;
  const hostsClass = total && online < total ? (online === 0 ? 'crit' : 'warn') : 'good';
  const card = (val, lbl, sub, cls) => `<div class='fleet-stat glass ${cls || ''}' data-tilt>
    <div class='fs-val'>${val}</div><div class='fs-lbl'>${lbl}</div>${sub ? `<div class='fs-sub'>${sub}</div>` : ''}</div>`;
  $('fleet-stats').innerHTML = [
    card(`${online}<span class='muted' style='font-size:18px'>/${total}</span>`, 'Hosts Online', total ? 'machines reporting' : 'no hosts yet', hostsClass),
    card(bots, 'Bots Running', 'trading engines live', bots ? 'good' : ''),
    card(warn, 'Realms at Risk', 'warnings + errors', warn ? (warn > 2 ? 'crit' : 'warn') : 'good'),
    card(active, 'Active Missions', 'disciples on task', active ? '' : ''),
    card(tests, 'Tests Failing', 'across the fleet', tests ? 'warn' : 'good'),
  ].join('');
  bindTilt();
}

/* Active Missions / Task Board — disciple activity, replaces trading "opps". */
const STATEMAP = (a) => {
  if (a.current_task) return { txt: `▸ ${a.current_task.slice(0, 70)}`, state: 'ON TASK', cls: 'on', dot: 'dot-working', wcls: 'working' };
  if (a.status === 'working' || a.status === 'queued') return { txt: a.status, state: a.status.toUpperCase(), cls: 'on', dot: 'dot-working', wcls: 'working' };
  if (a.status === 'error') return { txt: a.error || 'error', state: 'ERROR', cls: 'err', dot: 'dot-error', wcls: '' };
  const c = a.cultivation || {};
  if (c.in_roaming) return { txt: '🌄 roaming the web', state: 'ROAMING', cls: '', dot: 'dot-idle', wcls: '' };
  if (c.in_seclusion) return { txt: '🚪 in seclusion', state: 'SECLUSION', cls: '', dot: 'dot-idle', wcls: '' };
  return { txt: 'standing by', state: 'IDLE', cls: '', dot: 'dot-idle', wcls: '' };
};
function renderTaskboard(agents) {
  const list = (agents || []).slice();
  // surface working disciples first
  list.sort((a, b) => (b.current_task ? 1 : 0) - (a.current_task ? 1 : 0));
  const active = list.filter((a) => a.current_task || a.status === 'working' || a.status === 'queued').length;
  $('task-count').textContent = active ? `${active} active` : (list.length ? 'all idle' : '');
  if (!list.length) { $('taskboard').innerHTML = `<div class='muted' style='padding:6px'>No disciples enlisted. Recruit one in the Chamber, then issue a decree.</div>`; return; }
  $('taskboard').innerHTML = list.slice(0, 8).map((a) => {
    const st = STATEMAP(a);
    return `<div class='task-card'>
      <div class='task-av'>${esc((a.name || '?')[0])}<span class='dav-dot ${st.dot}'></span></div>
      <div style='min-width:0'><div class='task-who'>${esc(a.name)}</div>
        <div class='task-what ${st.wcls}'>${esc(st.txt)}</div></div>
      <div class='task-state ${st.cls}'>${esc(st.state)}</div></div>`;
  }).join('');
}

function sparkSvg(history) {
  const pts = (history || []).map((h) => Number(h && (h.pnl ?? h.profit_today ?? h.value))).filter(Number.isFinite);
  if (pts.length < 2) return '';
  const w = 120, h = 26, min = Math.min(...pts), max = Math.max(...pts), rng = (max - min) || 1;
  const coords = pts.map((v, i) => `${(i / (pts.length - 1) * w).toFixed(1)},${(h - 2 - ((v - min) / rng) * (h - 4)).toFixed(1)}`);
  const up = pts[pts.length - 1] >= pts[0];
  return `<svg class='proj-spark' viewBox='0 0 ${w} ${h}' preserveAspectRatio='none'><polyline points='${coords.join(' ')}' fill='none' stroke='${up ? 'var(--jade)' : 'var(--crimson)'}' stroke-width='1.5'/></svg>`;
}

function renderProjects(projects) {
  const list = (projects || []).slice(0, 9);
  const op = window.__isOperator !== false;   // hide mutating actions for viewers
  $('projects').innerHTML = list.map((p) => {
    const m = p.metrics || {};
    const pnl = Number(m.profit_today);
    const hp = p.type === 'trading_bot' && Number.isFinite(pnl) ? `<span class='proj-pnl ${pnl >= 0 ? 'pos' : 'neg'}'>${money(pnl)}</span>` : `<span class='muted'>${esc(p.status || '')}</span>`;
    const prog = p.health === 'ok' ? 100 : p.health === 'warning' ? 60 : p.health === 'error' ? 25 : 50;
    const running = String(p.status || '').toLowerCase() === 'running';
    const ctl = (p.type === 'trading_bot' || p.actions_available) && op ? `<div class='proj-ctl'>
        ${running ? `<button class='cbtn mini' data-act='stop' title='Stop' aria-label='Stop'>■</button><button class='cbtn mini' data-act='restart' title='Restart' aria-label='Restart'>⟳</button>`
                  : `<button class='cbtn mini' data-act='start' title='Start' aria-label='Start'>▶</button>`}
        <button class='cbtn mini' data-act='run-tests' title='Run tests' aria-label='Run tests'>✓</button></div>` : '';
    return `<div class='proj glass' data-tilt data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
      <div class='proj-head'><span class='proj-name'>${esc(p.name)}</span>
        <span class='proj-health health-${esc(p.health || 'unknown')}'>${esc(p.health || '—')}</span></div>
      <div class='proj-type'>${esc(p.type || '')} · ${esc(p.device || '')}</div>
      ${sparkSvg(p.history) || `<div class='proj-bar'><span style='width:${prog}%'></span></div>`}
      <div class='proj-foot'><span>${esc(p.oath ? '🤝 ' + esc(p.oath.who) : (p.frozen ? '🔒 frozen' : 'nominal'))}</span>${hp}</div>
      <div class='proj-actions'>
        <button class='cbtn' data-act='logs'>Logs</button>
        <button class='cbtn' data-act='assign'>Assign</button>
        ${ctl}
      </div></div>`;
  }).join('') || `<div class='muted'>No realms under watch.</div>`;
  $('projects').querySelectorAll('[data-act]').forEach((b) => b.onclick = async (e) => {
    e.stopPropagation();
    const card = b.closest('[data-project]'); const proj = card && card.dataset.project, dev = card && card.dataset.device;
    const act = b.dataset.act;
    if (act === 'logs') { if (dev && proj) openLogs(dev, proj); return; }
    if (act === 'assign') { localStorage.setItem('tab', 'disciples'); location.href = '/console'; return; }
    if (['start', 'stop', 'restart', 'run-tests'].includes(act)) {
      if (!confirm(`${act} ${proj}?`)) return;
      b.disabled = true;
      const r = await post(`/api/action/${encodeURIComponent(dev)}/${encodeURIComponent(proj)}/${act}`, {});
      b.disabled = false;
      if (!r || r.detail) alert(`${act} failed: ${(r && r.detail) || 'error'}`); else debounce(refresh, 600);
    }
  });
  bindTilt();
}

function timeAgo(ts) { if (!ts) return ''; const s = (Date.now() - ts) / 1000; if (s < 60) return `${s | 0}s`; if (s < 3600) return `${s / 60 | 0}m`; return `${s / 3600 | 0}h`; }
function renderEvents(cmd) {
  const ev = (cmd && cmd.events) || [];
  $('events').innerHTML = ev.length ? ev.map((e) => `<div class='evt'><span class='evt-ico'>${esc(e.icon || '•')}</span>
    <span class='evt-txt'>${esc(e.text)}</span><span class='evt-time'>${timeAgo(e.ts)}</span></div>`).join('')
    : `<div class='muted' style='padding:6px'>No recent activity yet.</div>`;
}

const RANKS = ['Outer', 'Inner', 'Core', 'Elder', 'Master'];
function renderDisciples(agents) {
  const list = (agents || []);
  $('disc-count').textContent = `${list.length}`;
  const act = (a) => {
    if (a.current_task) return { t: `▸ ${a.current_task.slice(0, 46)}`, c: 'working', d: 'dot-working' };
    if (a.status === 'working' || a.status === 'queued') return { t: a.status, c: 'working', d: 'dot-working' };
    if (a.status === 'error') return { t: a.error || 'error', c: '', d: 'dot-error' };
    const c = a.cultivation || {};
    if (c.in_roaming) return { t: '🌄 roaming the web', c: '', d: 'dot-idle' };
    if (c.in_seclusion) return { t: '🚪 in seclusion', c: '', d: 'dot-idle' };
    return { t: 'standing by', c: '', d: 'dot-idle' };
  };
  $('disciples').innerHTML = list.map((a) => {
    const g = a.governance || {}; const ac = act(a);
    const rank = g.is_leader ? 'Sect Master' : g.is_master ? 'Master' : g.is_elder ? 'Elder' : (a.cultivation?.rank_title || 'Disciple');
    return `<div class='disciple'><div class='dav'>${esc((a.name || '?')[0])}<span class='dav-dot ${ac.d}'></span></div>
      <div style='min-width:0;flex:1'><div class='d-name'>${esc(a.name)} <span class='d-rank'>${esc(rank)}</span></div>
      <div class='d-act ${ac.c}'>${esc(ac.t)}</div></div></div>`;
  }).join('') || `<div class='muted'>No disciples.</div>`;
}

/* tilt on cards */
function bindTilt() {
  document.querySelectorAll('[data-tilt]').forEach((el) => {
    if (el.__tilt) return; el.__tilt = 1;
    el.addEventListener('mousemove', (e) => {
      const r = el.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width - 0.5; const py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(800px) rotateX(${-py * 6}deg) rotateY(${px * 8}deg) translateY(-4px)`;
    });
    el.addEventListener('mouseleave', () => { el.style.transform = ''; });
  });
}

/* JARVIS line — fleet/ops focused (no trading PnL; that's the Trade page). */
function jarvis(cmd, summary, agents) {
  const name = (cmd && cmd.greeting_name) || 'Sect Master';
  const hr = new Date().getHours(); const part = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
  const s = summary || {};
  const online = Number(s.online_devices || 0), total = Number(s.total_devices || 0);
  const warn = Number(s.projects_with_warnings_errors || 0);
  const active = (agents || []).filter((a) => a.current_task || a.status === 'working' || a.status === 'queued').length;
  const bits = [`Good ${part}, <b>${esc(name)}</b>.`];
  if (total) bits.push(`<b>${online}/${total}</b> hosts online.`);
  if (warn) bits.push(`<b>${warn}</b> realm${warn === 1 ? '' : 's'} need${warn === 1 ? 's' : ''} attention.`);
  if (active) bits.push(`<b>${active}</b> disciple${active === 1 ? '' : 's'} on task.`);
  else bits.push(`Issue a decree to command the fleet.`);
  $('jarvis').innerHTML = bits.join(' ');
}

/* ============================ orchestrate ============================ */
let LAST_AGENTS = [];
async function refresh() {
  const [ov, ag, cmd] = await Promise.all([api('/api/overview'), api('/api/agents'), api('/api/command')]);
  if (window.__needAuth && !ov) { $('jarvis').innerHTML = `Authentication required — <a href='/console' style='color:var(--violet)'>sign in</a>.`; return; }
  const projects = (ov && ov.projects) || [];
  const summary = (ov && ov.summary) || {};
  const agents = (ag && ag.agents) || [];
  LAST_AGENTS = agents;
  renderFleetStats(summary, agents); renderTaskboard(agents);
  renderProjects(projects); renderEvents(cmd); renderDisciples(agents); jarvis(cmd, summary, agents);
  if (typeof renderDecreeParts === 'function') renderDecreeParts();   // keep participant picker in sync
}

/* nav */
const DEST = { disciples: '/chamber', trade: '/trade', treasury: '/treasury' };
const TABMAP = { ops: 'ops', projects: 'overview', missions: 'disciples', map: 'map', halls: 'sect' };
$('rail').querySelectorAll('.nav-item').forEach((n) => {
  const go = () => {
    const k = n.dataset.nav; if (k === 'command') return;
    if (DEST[k]) { location.href = DEST[k]; return; }
    if (TABMAP[k]) localStorage.setItem('tab', TABMAP[k]);
    location.href = '/console';
  };
  n.onclick = go;
  n.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } };
});

/* ============================ Heavenly Decree ============================ *
 * Ask  -> stream the Ops Copilot answer token-by-token (/api/copilot/stream),
 *         render suggested actions as buttons (route to /api/action/...).
 * Command -> dispatch a mission (/api/comms/mission) with the typed text as goal,
 *         optional participant picker (empty = all disciples). Shows a toast.        */
let DECREE_MODE = 'ask';          // 'ask' | 'command'
const DECREE_PARTS = new Set();   // chosen participant names (command mode)

function decreeToast(msg) {
  let el = document.getElementById('toast'); if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show'); clearTimeout(el.__t); el.__t = setTimeout(() => el.classList.remove('show'), 2800);
}

function setDecreeMode(mode) {
  DECREE_MODE = mode;
  const askB = $('decree-ask'), cmdB = $('decree-cmd');
  askB.classList.toggle('on', mode === 'ask'); askB.setAttribute('aria-selected', mode === 'ask');
  cmdB.classList.toggle('on', mode === 'command'); cmdB.setAttribute('aria-selected', mode === 'command');
  $('decree-send').textContent = mode === 'ask' ? 'Ask' : 'Decree';
  $('decree-input').placeholder = mode === 'ask'
    ? 'e.g. what needs attention across the fleet?'
    : 'e.g. audit every realm and report the weakest bot';
  renderDecreeParts();
}

function renderDecreeParts() {
  const box = $('decree-parts');
  if (DECREE_MODE !== 'command' || !LAST_AGENTS.length) { box.hidden = true; box.innerHTML = ''; return; }
  box.hidden = false;
  // prune chosen names that no longer exist
  const names = new Set(LAST_AGENTS.map((a) => a.name));
  [...DECREE_PARTS].forEach((n) => { if (!names.has(n)) DECREE_PARTS.delete(n); });
  box.innerHTML = `<span class='dp-lbl'>To</span>`
    + LAST_AGENTS.map((a) => `<span class='dp-chip ${DECREE_PARTS.has(a.name) ? 'on' : ''}' data-part='${esc(a.name)}' role='button' tabindex='0'>${esc(a.name)}</span>`).join('')
    + `<span class='muted' style='font-size:11px;margin-left:4px'>${DECREE_PARTS.size ? '' : 'none selected = all disciples'}</span>`;
  box.querySelectorAll('.dp-chip').forEach((c) => {
    const toggle = () => { const n = c.dataset.part; DECREE_PARTS.has(n) ? DECREE_PARTS.delete(n) : DECREE_PARTS.add(n); renderDecreeParts(); };
    c.onclick = toggle;
    c.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } };
  });
}

function decreeActionsHtml(actions) {
  const acts = (actions || []).filter((a) => a && a.device && a.project && a.kind);
  if (!acts.length) return '';
  return `<div class='decree-actions'><span class='da-lbl'>Suggested:</span>`
    + acts.map((a) => `<button class='cbtn' data-da-kind='${esc(a.kind)}' data-da-dev='${esc(a.device)}' data-da-proj='${esc(a.project)}'>${esc(a.label || a.kind)}</button>`).join(' ')
    + `</div>`;
}
function bindDecreeActions(out) {
  out.querySelectorAll('[data-da-kind]').forEach((b) => b.onclick = async () => {
    if (!confirm(`${b.textContent} on ${b.dataset.daProj}?`)) return;
    b.disabled = true; const orig = b.textContent; b.textContent = 'Working…';
    const r = await post(`/api/action/${encodeURIComponent(b.dataset.daDev)}/${encodeURIComponent(b.dataset.daProj)}/${encodeURIComponent(b.dataset.daKind)}`, {});
    b.textContent = (r && !r.detail) ? 'Done ✓' : 'Failed';
    if (r && !r.detail) debounce(refresh, 500); else b.disabled = false;
  });
}

async function decreeAsk(question) {
  const out = $('decree-out');
  out.innerHTML = `<div class='decree-answer streaming' id='decree-ans'></div>`;
  const ansEl = $('decree-ans');
  let answer = '', meta = null, errored = null;
  try {
    const resp = await fetch('/api/copilot/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ question }),
    });
    if (!resp.ok || !resp.body) throw new Error('no stream');
    const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n\n')) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 2);
        if (!line.startsWith('data:')) continue;
        let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch (_) { continue; }
        if (ev.type === 'meta') meta = ev;
        else if (ev.type === 'token') { answer += ev.text; ansEl.textContent = answer; }
        else if (ev.type === 'error') { errored = ev.error; if (ev.answer && !answer) { answer = ev.answer; ansEl.textContent = answer; } }
      }
    }
  } catch (_) {
    const r = await post('/api/copilot', { question });
    if (!r) { out.innerHTML = `<div class='decree-note err'>The oracle is silent — copilot unavailable.</div>`; return; }
    answer = r.answer || ''; meta = { actions: r.actions, member: r.member }; errored = r.error;
  }
  ansEl.classList.remove('streaming');
  // Graceful "no AI member configured" handling.
  if ((errored === 'no_backend' || (errored && /no.?backend/i.test(errored))) && !answer) {
    out.innerHTML = `<div class='decree-note'>No AI member is configured yet. Recruit a disciple with an AI backend in the <a href='/chamber' style='color:var(--violet)'>Chamber</a> to receive answers.</div>`;
    return;
  }
  if (!answer && errored) { out.innerHTML = `<div class='decree-note err'>${esc(errored)}</div>`; return; }
  out.innerHTML = `<div class='decree-answer'>${esc(answer)}</div>`
    + decreeActionsHtml(meta && meta.actions)
    + ((meta && meta.member) ? `<div class='decree-by'>— ${esc(meta.member)}</div>` : '');
  bindDecreeActions(out);
}

async function decreeCommand(goal) {
  const out = $('decree-out');
  out.innerHTML = `<div class='decree-note'>Dispatching decree…</div>`;
  // None selected = all disciples. A mission needs >=2 participants, so a single
  // disciple is dispatched as a direct task instead.
  let chosen = [...DECREE_PARTS];
  if (!chosen.length) chosen = (LAST_AGENTS || []).map((a) => a.name);
  if (!chosen.length) {
    out.innerHTML = `<div class='decree-note err'>No disciples enlisted — recruit one in the <a href='/chamber' style='color:var(--violet)'>Chamber</a> first.</div>`;
    return;
  }
  let r, who;
  if (chosen.length === 1) {
    r = await post('/api/agents/' + encodeURIComponent(chosen[0]) + '/task', { task: goal });
    who = chosen[0];
  } else {
    r = await post('/api/comms/mission', { goal, participants: chosen, rounds: 1 });
    who = chosen.join(', ');
  }
  if (!r || r.detail || r.error) {
    out.innerHTML = `<div class='decree-note err'>${esc((r && (r.detail || r.error)) || 'Could not dispatch the decree (operator role required).')}</div>`;
    return;
  }
  out.innerHTML = `<div class='decree-note'>⚔ Decree issued to <b>${esc(who)}</b>. The mission is underway.</div>`;
  decreeToast('Decree dispatched');
  $('decree-input').value = '';
  debounce(refresh, 600);
}

function submitDecree() {
  const inp = $('decree-input'); const text = (inp.value || '').trim();
  if (!text) return;
  if (DECREE_MODE === 'ask') decreeAsk(text); else decreeCommand(text);
}

(function mountDecree() {
  $('decree-ask').onclick = () => setDecreeMode('ask');
  $('decree-cmd').onclick = () => setDecreeMode('command');
  $('decree-send').onclick = submitDecree;
  $('decree-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); submitDecree(); } });
  setDecreeMode('ask');
})();

/* clock */
setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

init3D();
refresh();
setInterval(refresh, 15000);
liveStream((t) => { if (['tick','agents','tasks','tools','command','overview'].includes(t)) debounce(refresh); });

/* ---- first-run onboarding checklist ---- */
async function renderSetup() {
  const el = document.getElementById('setup-banner'); if (!el) return;
  if (localStorage.getItem('maybot.setup_dismissed')) { el.innerHTML = ''; return; }
  const s = await api('/api/setup');
  if (!s || s.done) { el.innerHTML = ''; return; }
  const steps = [
    ['account', 'Create your account', 'Secure the dashboard', '/login', null],
    ['host', 'Add a host', 'Connect a machine running your bots', '/console', 'ops'],
    ['member', 'Recruit a sect member', 'Add an AI agent', '/chamber', null],
    ['ai', 'Connect an AI backend', 'Local AI or an API key', '/chamber', null],
    ['notifications', 'Set up notifications', 'Slack / Discord / webhook / email', '/console', 'ops'],
  ];
  const done = Object.values(s.steps).filter(Boolean).length;
  el.innerHTML = `<section class='glass rise setup-card'>
    <div class='setup-head'><div class='panel-title'>Get started · ${done}/${steps.length}</div>
      <button class='setup-x' id='setup-x' title='dismiss' aria-label='Dismiss'>✕</button></div>
    <div class='setup-steps'>${steps.map(([k, t, d, href, tab]) => `
      <a class='setup-step ${s.steps[k] ? 'ok' : ''}' href='${href}'${tab ? ` data-tab='${tab}'` : ''}>
        <span class='setup-check'>${s.steps[k] ? '✓' : ''}</span>
        <span class='setup-txt'><b>${t}</b><span>${d}</span></span></a>`).join('')}</div>
  </section>`;
  el.querySelectorAll('.setup-step[data-tab]').forEach((a) => a.onclick = () => localStorage.setItem('tab', a.dataset.tab));
  const x = document.getElementById('setup-x'); if (x) x.onclick = () => { localStorage.setItem('maybot.setup_dismissed', '1'); el.innerHTML = ''; };
}
renderSetup();
