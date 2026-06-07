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
function tradingFromProjects(projects) {
  const bots = (projects || []).filter((p) => p.type === 'trading_bot');
  const num = (m, k) => { const v = Number((m || {})[k]); return Number.isFinite(v) ? v : 0; };
  let today = 0, week = 0, month = 0, realized = 0, exposure = 0, positions = 0, trades = 0, fillSum = 0, fillN = 0;
  bots.forEach((p) => {
    const m = p.metrics || {};
    today += num(m, 'profit_today'); week += num(m, 'profit_this_week'); month += num(m, 'profit_this_month');
    realized += num(m, 'realized_pnl'); exposure += num(m, 'open_exposure'); positions += num(m, 'open_positions'); trades += num(m, 'trades_today');
    const fr = Number(m.fill_rate); if (Number.isFinite(fr)) { fillSum += fr; fillN++; }
  });
  return { today, week, month, realized, exposure, positions, trades, fillRate: fillN ? fillSum / fillN : null, botCount: bots.length };
}

function renderHero(t, cmd) {
  const base = (cmd && cmd.account_base) || 0;
  const total = base + t.realized;
  const cell = (lbl, val, cls, big) => `<div class='hero-cell'><div class='hero-lbl'>${lbl}</div>
    <div class='hero-val ${cls} ${big ? 'big' : ''}' data-num='${val}'>—</div></div>`;
  $('hero').innerHTML =
    cell('Today', t.today, t.today >= 0 ? 'pos' : 'neg') +
    cell('This Week', t.week, t.week >= 0 ? 'pos' : 'neg') +
    cell('This Month', t.month, t.month >= 0 ? 'pos' : 'neg') +
    cell('Total Value', total, '', true);
  $('hero').querySelectorAll('.hero-val').forEach((el, i) => {
    const v = Number(el.dataset.num);
    countUp(el, v, i === 3 ? (x) => `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : (x) => money(x));
  });
}

function renderMetrics(t, cmd, summary) {
  const base = (cmd && cmd.account_base) || 0;
  const acct = base + t.realized;
  const goal = (cmd && cmd.monthly_goal) || 10000;
  const goalPct = Math.max(0, Math.min(100, Math.round((t.month / goal) * 100)));
  const winRate = t.fillRate != null ? Math.round(t.fillRate * 100) : null;
  const pf = t.demoPF != null ? t.demoPF : (t.realized > 0 ? (1 + Math.min(3, Math.abs(t.realized) / Math.max(1, Math.abs(t.exposure) || 1000))) : null);
  const card = (lbl, val, sub, accent) => `<div class='metric-card glass ${accent || ''}' data-tilt>
    <div class='metric-lbl'>${lbl}</div><div class='metric-val'>${val}</div>${sub ? `<div class='metric-sub'>${sub}</div>` : ''}</div>`;
  const ring = `<div class='metric-card glass accent-jade' data-tilt><div class='metric-lbl'>Monthly Goal</div>
    <div class='goal-card' style='margin-top:8px'><div class='ring' style='--p:${goalPct}'><b>${goalPct}%</b></div>
      <div><div class='metric-val' style='font-size:18px'>${money(t.month)}</div><div class='metric-sub'>of $${goal.toLocaleString()}</div></div></div></div>`;
  $('metrics').innerHTML = [
    card('Account Value', `$${acct.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'buying power ready', 'accent-azure'),
    card('Open Exposure', money(t.exposure).replace('+', ''), `${t.botCount} bot${t.botCount === 1 ? '' : 's'} active`, 'accent-gold'),
    card('Open Positions', t.positions, 'live', ''),
    card('Trades Today', t.trades, 'executed', ''),
    card('Win Rate', winRate != null ? `${winRate}%` : '—', 'fill rate', 'accent-jade'),
    card('Profit Factor', pf != null ? pf.toFixed(2) : '—', t.realized >= 0 ? 'positive' : 'drawdown', t.realized >= 0 ? 'accent-jade' : 'accent-crimson'),
    ring,
    card('Risk', t.exposure > 0 ? 'Moderate' : 'Minimal', 'exposure-based', 'accent-azure'),
  ].join('');
  bindTilt();
}

function renderOpps(cmd) {
  const opps = (cmd && cmd.opportunities) || [];
  $('opp-count').textContent = opps.length ? `${opps.length} signals` : '';
  if (!opps.length) { $('opps').innerHTML = `<div class='muted' style='padding:6px'>No active signals. Wire a signals feed or set MAYBOT_DEMO=1.</div>`; return; }
  $('opps').innerHTML = opps.map((o) => `<div class='opp'>
    <div class='opp-tick'>${esc(o.ticker)}</div>
    <div class='opp-meta'>
      <div class='opp-row'><span>Edge <b>${Number(o.edge).toFixed(1)}%</b></span><span>Confidence <b>${o.confidence}%</b></span></div>
      <div class='signal'><span style='width:${Math.max(6, Math.min(100, o.confidence))}%'></span></div>
    </div>
    <div class='opp-status st-${esc(o.status)}'>${esc(o.status)}</div></div>`).join('');
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
        ${running ? `<button class='cbtn mini' data-act='stop' title='Stop'>■</button><button class='cbtn mini' data-act='restart' title='Restart'>⟳</button>`
                  : `<button class='cbtn mini' data-act='start' title='Start'>▶</button>`}
        <button class='cbtn mini' data-act='run-tests' title='Run tests'>✓</button></div>` : '';
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

/* JARVIS line */
function jarvis(cmd, t) {
  const name = (cmd && cmd.greeting_name) || 'Sect Master';
  const hr = new Date().getHours(); const part = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
  const goal = (cmd && cmd.monthly_goal) || 10000; const pct = Math.round((t.month / goal) * 100);
  const opps = ((cmd && cmd.opportunities) || []).filter((o) => o.status === 'EXECUTE' || o.status === 'READY').length;
  const bits = [`Good ${part}, <b>${esc(name)}</b>.`];
  if (t.today) bits.push(`Today's PnL is <b>${money(t.today)}</b>.`);
  if (opps) bits.push(`<b>${opps}</b> opportunit${opps === 1 ? 'y requires' : 'ies require'} review.`);
  if (pct) bits.push(`Monthly goal <b>${pct}%</b> complete.`);
  $('jarvis').innerHTML = bits.join(' ');
}

/* ============================ orchestrate ============================ */
async function refresh() {
  const [ov, ag, cmd] = await Promise.all([api('/api/overview'), api('/api/agents'), api('/api/command')]);
  if (window.__needAuth && !ov) { $('jarvis').innerHTML = `Authentication required — <a href='/console' style='color:var(--violet)'>sign in</a>.`; return; }
  const projects = (ov && ov.projects) || [];
  let t = tradingFromProjects(projects);
  if (cmd && cmd.demo && cmd.pnl) {   // vivid demo figures override the (empty) live ones
    const d = cmd.pnl, tr = cmd.trading || {};
    t = { today: d.today, week: d.week, month: d.month, realized: d.total - (cmd.account_base || 0),
          exposure: tr.exposure || 0, positions: tr.positions || 0, trades: tr.trades_today || 0,
          fillRate: (tr.win_rate || 0) / 100, botCount: tr.bots || t.botCount, demoPF: tr.profit_factor };
  }
  renderHero(t, cmd); renderMetrics(t, cmd, (ov && ov.summary) || {}); renderOpps(cmd);
  renderProjects(projects); renderEvents(cmd); renderDisciples((ag && ag.agents) || []); jarvis(cmd, t);
}

/* nav */
const DEST = { disciples: '/chamber', trade: '/trade', treasury: '/treasury' };
const TABMAP = { ops: 'ops', projects: 'overview', missions: 'disciples', map: 'map', halls: 'sect' };
$('rail').querySelectorAll('.nav-item').forEach((n) => n.onclick = () => {
  const k = n.dataset.nav; if (k === 'command') return;
  if (DEST[k]) { location.href = DEST[k]; return; }
  if (TABMAP[k]) localStorage.setItem('tab', TABMAP[k]);
  location.href = '/console';
});

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
      <button class='setup-x' id='setup-x' title='dismiss'>✕</button></div>
    <div class='setup-steps'>${steps.map(([k, t, d, href, tab]) => `
      <a class='setup-step ${s.steps[k] ? 'ok' : ''}' href='${href}'${tab ? ` data-tab='${tab}'` : ''}>
        <span class='setup-check'>${s.steps[k] ? '✓' : ''}</span>
        <span class='setup-txt'><b>${t}</b><span>${d}</span></span></a>`).join('')}</div>
  </section>`;
  el.querySelectorAll('.setup-step[data-tab]').forEach((a) => a.onclick = () => localStorage.setItem('tab', a.dataset.tab));
  const x = document.getElementById('setup-x'); if (x) x.onclick = () => { localStorage.setItem('maybot.setup_dismissed', '1'); el.innerHTML = ''; };
}
renderSetup();
