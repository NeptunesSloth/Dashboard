// Sect Academy — one small app shell: sect home, study sessions, library, trials, progress.
// Vanilla JS, no build step. All server/user text goes through esc() before innerHTML.

import { ICON, SITES, portrait, sectScene, siteRect } from '/art.js';

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
// Anything shown as a number is forced to be one, so a doctored save file cannot inject markup.
const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
const TOKEN_KEY = 'maybot.control_token';
const headers = () => { const t = localStorage.getItem(TOKEN_KEY) || ''; return t ? { 'x-control-token': t } : {}; };

async function api(path, body, method) {
  try {
    const opts = { headers: headers() };
    if (body !== undefined) { opts.method = method || 'POST'; opts.headers = { 'Content-Type': 'application/json', ...headers() }; opts.body = JSON.stringify(body); }
    const r = await fetch(path, opts);
    if (r.status === 401) { location.href = '/login'; return { ok: false, error: 'Sign in again.' }; }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, error: data.detail || `The server answered ${r.status}.` };
    return data;
  } catch (_) { return { ok: false, error: 'Cannot reach the server. Check your connection and try again.' }; }
}

const view = $('#view');
let OV = null;            // last overview
let leaveGuard = null;    // set while a session/trial is in flight

function toast(text, ms = 4200) {
  const t = document.createElement('div'); t.className = 'toast'; t.textContent = text;
  $('#toasts').appendChild(t); setTimeout(() => t.remove(), ms);
}
let lastProblem = '';
// Every field the UI prints as a bare number, by object. Strings are always esc()'d at the point of use.
const NUMERIC = {
  game: ['qi', 'qi_into', 'qi_need', 'qi_pct', 'stones', 'pending', 'rate', 'per_day', 'storage_hours', 'flow', 'streak', 'best_streak',
    'grace', 'grace_cap', 'pill_cost', 'disciple_cap', 'recruit_tokens', 'mission_tokens', 'learned', 'power', 'step', 'tier_level'],
  today: ['due', 'new_left', 'answers', 'correct', 'sessions', 'new', 'reviews'],
  settings: ['new_per_day', 'session_size', 'retention', 'tz_offset_min'],
  course: ['total', 'seen', 'mastered', 'due', 'new_left', 'strength', 'units_done'],
  unit: ['items', 'seen', 'mastered'],
  room: ['level', 'max', 'strength', 'capacity'],
  quest: ['goal', 'progress'],
  disciple: ['level', 'xp', 'xp_need', 'talent', 'away_until'],
  trial: ['pct', 'right', 'total', 'ts'],
};
const fix = (o, keys) => { if (o && typeof o === 'object') keys.forEach((k) => { if (k in o && o[k] !== null) o[k] = num(o[k]); }); return o; };
function scrub(ov) {
  fix(ov.game, NUMERIC.game); fix(ov.today, NUMERIC.today); fix(ov.settings, NUMERIC.settings);
  (ov.courses || []).forEach((c) => { fix(c, NUMERIC.course); (c.units || []).forEach((u) => fix(u, NUMERIC.unit)); });
  const g = ov.game || {};
  (g.rooms || []).forEach((r) => { fix(r, NUMERIC.room); if (r.cost !== null && r.cost !== undefined) r.cost = num(r.cost); });
  (g.quests || []).forEach((q) => fix(q, NUMERIC.quest));
  (g.disciples || []).concat(g.candidates || []).forEach((d) => fix(d, NUMERIC.disciple));
  (g.missions || []).forEach((m) => { m.ends = num(m.ends); });
  (g.mission_kinds || []).forEach((k) => { k.hours = num(k.hours); });
  (g.chronicle || []).forEach((e) => { e.ts = num(e.ts); });
  if (g.week) fix(g.week, ['days', 'goal']);
  return ov;
}
function showEvents(events) { (events || []).slice(0, 4).forEach((e, i) => setTimeout(() => toast(e.text), i * 700)); }

/* ---------------- light markdown for unit notes ---------------- */
function md(src) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, '$1<i>$2</i>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const lines = String(src || '').replace(/\r/g, '').split('\n');
  let out = '', para = [], list = [], table = [];
  const flush = () => {
    if (para.length) { out += `<p>${inline(para.join(' '))}</p>`; para = []; }
    if (list.length) { out += `<ul>${list.map((l) => `<li>${inline(l)}</li>`).join('')}</ul>`; list = []; }
    if (table.length) {
      const rows = table.filter((r) => !/^\|?[\s:|-]+\|?$/.test(r)).map((r) => r.replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
      out += `<div class="scroll-x"><table>${rows.map((r, i) => `<tr>${r.map((c) => (i ? `<td>${inline(c)}</td>` : `<th>${inline(c)}</th>`)).join('')}</tr>`).join('')}</table></div>`;
      table = [];
    }
  };
  for (const raw of lines) {
    const l = raw.trim();
    if (!l) { flush(); continue; }
    if (/^#{1,4}\s/.test(l)) { flush(); out += `<h3>${inline(l.replace(/^#+\s*/, ''))}</h3>`; continue; }
    if (/^[-*•]\s+/.test(l)) { if (para.length || table.length) flush(); list.push(l.replace(/^[-*•]\s+/, '')); continue; }
    if (l.startsWith('|')) { if (para.length || list.length) flush(); table.push(l); continue; }
    if (list.length || table.length) flush();
    para.push(l);
  }
  flush();
  return `<div class="md">${out}</div>`;
}

/* ---------------- speech ---------------- */
let voices = [];
const synth = window.speechSynthesis;
function loadVoices() { try { voices = synth ? synth.getVoices() : []; } catch (_) { voices = []; } }
if (synth) { loadVoices(); try { synth.addEventListener('voiceschanged', loadVoices); } catch (_) { /* old Safari */ } }
function voiceFor(lang) {
  if (!lang) return null;
  const norm = (v) => String(v.lang || '').replace('_', '-').toLowerCase();
  const want = lang.toLowerCase(); const base = want.split('-')[0];
  return voices.find((v) => norm(v) === want) || voices.find((v) => norm(v).split('-')[0] === base) || null;
}
const audioOn = () => !!(OV && OV.settings.audio) && !!synth;
const canSpeak = (lang) => audioOn() && !!voiceFor(lang);
function speak(text, lang) {
  if (!audioOn() || !text) return;
  const v = voiceFor(lang); if (!v) return;
  try { synth.cancel(); const u = new SpeechSynthesisUtterance(String(text).replace(/_+/g, ' ')); u.voice = v; u.lang = v.lang.replace('_', '-'); u.rate = 0.9; synth.speak(u); } catch (_) { /* ignore */ }
}

/* ---------------- routing ---------------- */
const ROUTES = { '/': renderSect, '/study': renderStudy, '/library': renderLibrary, '/trials': renderTrials, '/progress': renderProgress };
const NAV = [['/', 'sect', 'Sect'], ['/study', 'study', 'Study'], ['/library', 'library', 'Library'], ['/trials', 'trials', 'Trials'], ['/progress', 'progress', 'Progress']];
const GUIDE = 'Elder Bai';
const guide = (mood = 'calm', size = 56) => portrait(GUIDE, { kind: 'elder', mood, size });
const face = (d, size = 48) => portrait(d.id + d.name, { root: d.root, size });

function drawNav() {
  const path = ROUTES[location.pathname] ? location.pathname : '/';
  const due = OV ? OV.today.due : 0;
  $('#nav').innerHTML = NAV.map(([href, glyph, label]) =>
    `<a href="${href}" data-link ${href === path ? 'aria-current="page"' : ''}>${ICON[glyph]}${label}${href === '/study' && due ? `<span class="badge">${due > 99 ? '99+' : due}</span>` : ''}</a>`).join('')
    + `<a class="extra" href="/learn">${ICON.scroll}AI tutor</a><a class="extra" href="/command">${ICON.fleet}Fleet</a>`;
}
async function refresh() {
  const tz = -new Date().getTimezoneOffset();
  const ov = await api(`/api/academy/overview?tz=${tz}`);
  if (ov && ov.courses) {
    OV = scrub(ov);
    if (ov.events && ov.events.length) showEvents(ov.events);
    if (ov.problem && ov.problem !== lastProblem) { lastProblem = ov.problem; toast(ov.problem, 12000); }
  }
  drawNav();
  return OV;
}
let herePath = location.pathname + location.search;
async function go(path, push = true) {
  if (leaveGuard && !(await leaveGuard())) {
    // The learner chose to stay: put the address bar back where the session lives.
    if (!push && location.pathname + location.search !== herePath) history.pushState({}, '', herePath);
    return;
  }
  leaveGuard = null; keyHandler = null;
  document.body.classList.remove('in-session');
  closeSheet();
  if (push && path !== location.pathname + location.search) history.pushState({}, '', path);
  herePath = path;
  const url = new URL(path, location.origin);
  await refresh();
  if (!OV) { view.innerHTML = `<div class="panel"><h2>The mountain gate is closed</h2><p class="dim">The server did not answer. Check that it is running, then try again.</p><button class="btn primary" id="retry">Try again</button></div>`; $('#retry').onclick = () => go(path, false); return; }
  if (!OV.game.founded) { renderFounding(); return; }
  (ROUTES[url.pathname] || renderSect)(url.searchParams);
  view.focus({ preventScroll: true }); window.scrollTo(0, 0);
}
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-link]'); if (!a) return;
  e.preventDefault(); go(a.getAttribute('href'));
});
window.addEventListener('popstate', () => go(location.pathname + location.search, false));

/* ---------------- sheet ---------------- */
function openSheet(html) {
  const s = $('#sheet'); s.innerHTML = `<div class="body" role="dialog" aria-modal="true"><button class="btn quiet close" data-close>Close</button>${html}</div>`;
  s.hidden = false; s.onclick = (e) => { if (e.target === s || e.target.closest('[data-close]')) closeSheet(); };
  const f = $('.body', s); f.tabIndex = -1; f.focus();
}
function closeSheet() { const s = $('#sheet'); s.hidden = true; s.innerHTML = ''; }
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#sheet').hidden) closeSheet(); });

/* ================= founding ================= */
function renderFounding() {
  const courses = OV.courses;
  const preview = ['grand_hall', 'tongues_west', 'tongues_south', 'ward_hall', 'spirit_vein', 'meditation'].map((id) => ({ id, level: id === 'grand_hall' ? 3 : 2 }));
  view.innerHTML = `<div class="found">
    <div class="hero">${sectScene(preview)}</div>
    <h1>Found your sect</h1>
    <p class="dim">Every answer you give from memory becomes qi. Qi raises your realm, and your realm raises the sect. Choose what you will cultivate — you can change this later in the library.</p>
    <label class="field"><span>Name of the sect</span><input type="text" id="f-name" maxlength="40" placeholder="Azure Lantern Sect" autocomplete="off"></label>
    <label class="field"><span>Your name as Sect Master</span><input type="text" id="f-master" maxlength="30" placeholder="Master Jay" autocomplete="off"></label>
    <h3 style="margin-top:20px">Arts to cultivate</h3>
    ${courses.length ? courses.map((c) => `<label class="pick"><input type="checkbox" value="${esc(c.id)}" ${c.kind === 'language' || c.id === 'isc2-cc' ? 'checked' : ''}>
      <span><b>${esc(c.title)}</b><br><span class="dim small">${esc(c.blurb)} ${c.total} items in ${c.units.length} units.</span></span></label>`).join('')
    : '<p class="dim">No courses are installed. Add a pack under <code>academy/packs</code> and reload.</p>'}
    <p class="dim small" style="margin-top:14px">Each art adds about 8 new items a day. Two or three arts is a comfortable daily load; more is possible but the reviews add up.</p>
    <p id="f-err" class="small" style="color:var(--verm-d);font-weight:800" role="alert"></p>
    <button class="btn primary big" id="f-go" style="width:100%">Found the sect</button>
  </div>`;
  $('#f-go').onclick = async () => {
    const picked = [...view.querySelectorAll('.pick input:checked')].map((i) => i.value);
    if (!picked.length) { $('#f-err').textContent = 'Choose at least one art to cultivate.'; return; }
    const res = await api('/api/academy/setup', { name: $('#f-name').value, master: $('#f-master').value, courses: picked });
    if (res.ok === false) { $('#f-err').textContent = res.error; return; }
    go('/', false);
  };
}

/* ================= sect home ================= */
const ago = (ts) => { const s = Date.now() / 1000 - ts; if (s < 90) return 'now'; if (s < 3600) return `${Math.round(s / 60)}m`; if (s < 86400) return `${Math.round(s / 3600)}h`; return `${Math.round(s / 86400)}d`; };
const until = (ts) => { const s = Math.max(0, ts - Date.now() / 1000); return s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m` : `${Math.max(1, Math.round(s / 60))}m`; };

function canUpgrade(r, g) { return !r.course_hall && r.cost != null && !r.locked && g.stones >= r.cost; }

function todayPanel() {
  const t = OV.today, g = OV.game;
  const mine = OV.courses.filter((c) => c.enrolled);
  const work = t.due + t.new_left;
  let head, sub, btn, mood = 'calm', tone = '';
  if (!mine.length) {
    head = 'Choose an art to cultivate'; sub = 'You are not enrolled in any course yet. Pick one in the library to begin.';
    btn = `<a class="btn primary big" href="/library" data-link>Open the library</a>`; mood = 'think'; tone = 'rest';
  } else if (g.seclusion) {
    head = 'The gates are sealed'; sub = 'You are in closed-door seclusion. Your streak is frozen until you return.';
    btn = `<button class="btn primary big" data-act="unseclude">Reopen the gates</button>`; tone = 'rest';
  } else if (g.tribulation) {
    head = 'A tribulation gathers'; sub = `Your qi is full. Pass a trial to break through to ${esc(g.next_realm)}.`;
    btn = `<a class="btn seal big" href="/trials" data-link>Face a trial</a>${work > 0 ? ' <a class="btn big" href="/study" data-link>Study first</a>' : ''}`; mood = 'think'; tone = 'alert';
  } else if (work > 0) {
    head = g.studied_today ? 'There is more, if you wish' : 'Your cultivation for today';
    sub = `<span class="counts"><span class="count"><b class="num">${t.due}</b>to review</span><span class="count new"><b class="num">${t.new_left}</b>new</span></span>`;
    btn = `<a class="btn primary big" href="/study" data-link>${g.studied_today ? 'Keep cultivating' : 'Begin cultivation'}</a>`;
    mood = g.studied_today ? 'happy' : 'calm';
  } else {
    head = 'Today is complete'; sub = 'Nothing more is due until tomorrow. Rest, tend the sect, or sharpen your weakest items.';
    btn = `<a class="btn big" href="/study?practice=1" data-link>Practice weak items</a>`; mood = 'happy'; tone = 'rest';
  }
  const risk = g.streak_at_risk && !g.seclusion && work > 0 ? `<p class="small" style="margin:6px 0 0;font-weight:700">Study today to keep your ${g.streak}-day streak${g.grace ? ` (${g.grace} grace pill${g.grace > 1 ? 's' : ''} in reserve)` : ''}.</p>` : '';
  const chips = mine.length > 1 && work > 0 && !g.seclusion ? `<div class="chips">${mine.filter((c) => c.due + c.new_left > 0).map((c) =>
    `<a class="chip" href="/study?course=${encodeURIComponent(c.id)}" data-link>${esc(c.title.split(' — ')[0])} <span class="dim num">${c.due + c.new_left}</span></a>`).join('')}</div>` : '';
  return `<section class="panel today ${tone}"><div class="says">${guide(mood)}<div class="bubble"><h2>${head}</h2><div style="margin-top:6px">${sub}</div>${risk}</div></div>
    <div class="row">${btn}</div>${chips}</section>`;
}

function renderSect() {
  const g = OV.game;
  const week = Array.from({ length: g.week.goal }, (_, i) => `<i class="${i < g.week.days ? 'on' : ''}"></i>`).join('');
  // which robe colour stands outside which room
  const staff = {};
  g.disciples.forEach((d, i) => { if (d.room && !d.away) (staff[d.room] = staff[d.room] || []).push(i); });
  const rooms = g.rooms.map((r) => {
    const [x, y, w, h] = siteRect(r.id); const open = r.open;
    return `<button class="room ${open ? '' : 'closed'}" data-room="${esc(r.id)}" style="left:${x}%;top:${y}%;width:${w}%;height:${h}%"
      aria-label="${esc(r.name)}, ${open ? `level ${r.level}` : 'not built'}${canUpgrade(r, g) ? ', you can afford the next level' : ''}">
      ${canUpgrade(r, g) ? '<span class="can" aria-hidden="true">↑</span>' : ''}
      <span class="plaque">${esc(r.name)}${open ? `<em>${r.level}</em>` : ''}</span>
    </button>`;
  }).join('');
  const vein = SITES.spirit_vein;
  const bubble = g.pending > 0 ? `<button class="bubble-collect" data-act="collect" style="left:${(vein.x - 30) / 10}%;top:${(vein.y - vein.h - 46) / 7}%" aria-label="Collect ${g.pending} spirit stones">${ICON.stone}+${g.pending}</button>` : '';
  const cards = g.rooms.map((r) => `<button class="hallcard ${r.open ? '' : 'closed'} ${canUpgrade(r, g) ? 'afford' : ''}" data-room="${esc(r.id)}">
      <b>${esc(r.name)}</b><span>${r.open ? `Level ${r.level}` : 'Not built'}${canUpgrade(r, g) ? ` · ${r.open ? 'upgrade' : 'build'} for ${r.cost}` : ''}</span></button>`).join('');
  const quests = g.quests.length ? g.quests.map((q) => `<li class="quest ${q.done ? 'done' : ''}"><span class="mark">${q.done ? ICON.check : ''}</span>
      <div class="grow">${esc(q.text)}${q.done ? '' : `<div class="bar thin jade"><i style="width:${Math.round(100 * q.progress / Math.max(q.goal, 1))}%"></i></div>`}</div>
      <span class="dim small num">${q.progress}/${q.goal}</span></li>`).join('')
    : '<li class="dim">Quests appear once you are enrolled in a course.</li>';
  const chron = g.chronicle.slice(0, 10).map((e) => `<li class="chron"><time>${ago(e.ts)}</time>${esc(e.text)}</li>`).join('') || '<li class="dim">The chronicle is empty. Your first session will write its first line.</li>';
  view.innerHTML = `
    <header class="status">
      <h1>${esc(g.name)}<small>${esc(g.tier)}, led by ${esc(g.master)}</small></h1>
      <span class="pill flame ${g.streak ? '' : 'off'}" title="Day streak. Best: ${g.best_streak}">${ICON.flame}${g.streak}</span>
      <span class="pill pillc" title="Grace pills: each one covers a missed day">${ICON.pill}${g.grace}</span>
      <span class="pill stone" title="Spirit stones${g.per_day ? `. Up to +${g.per_day} idle a day` : ''}">${ICON.stone}${g.stones.toLocaleString()}</span>
    </header>
    <div class="grid2">
      ${todayPanel()}
      <div>
        <section class="panel realm"><div class="who">${portrait(g.master + g.name, { root: 'Heaven Grade', size: 64 })}<span class="ring"></span></div>
          <div class="grow"><b>${esc(g.realm)}</b> <span class="tag ${g.tribulation ? 'red' : 'blue'}">${g.tribulation ? 'Tribulation ready' : `${esc(g.stage)} stage`}</span>
            <div class="bar violet" title="${g.qi_into} of ${g.qi_need} qi"><i style="width:${g.qi_pct}%"></i></div>
            <div class="small dim" style="margin-top:4px">${ICON.qi} ${g.qi_into.toLocaleString()} / ${g.qi_need.toLocaleString()} qi to the next stage</div>
            <div class="mini"><span><b class="num">${g.learned}</b>items learned</span><span><b class="num">${g.power.toLocaleString()}</b>sect power</span><span><b class="num">×${g.flow}</b>qi flow</span></div></div></section>
      </div>
    </div>
    <section class="panel scenewrap">
      <div class="hq">${sectScene(g.rooms, staff)}${rooms}${bubble}</div>
      <div class="halls">${cards}</div>
      <p class="dim small" style="margin:10px 4px 0">Tap a hall to build it, raise it, or see who works there. An arrow marks what you can afford.</p>
    </section>
    <div class="grid3">
        <section class="panel"><div class="row"><h2 class="grow">Daily quests</h2><span class="week" title="${g.week.days} of ${g.week.goal} study days this week">${week}</span></div>
          <ul class="list" style="margin-top:6px">${quests}</ul></section>
        <section class="panel"><div class="row"><h2 class="grow">Disciples <span class="dim small num">${g.disciples.length}/${g.disciple_cap}</span></h2>
          <button class="btn ${g.recruit_tokens || g.candidates.length ? 'gold' : ''}" data-act="recruit">${g.candidates.length ? 'See candidates' : `Recruit (${g.recruit_tokens})`}</button></div>
          <ul class="list" style="margin-top:6px">${disciplesList(g)}</ul></section>
        <section class="panel"><h2>Chronicle</h2><ul class="list" style="margin-top:6px">${chron}</ul>
</section>
    </div>`;
  view.querySelectorAll('[data-room]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.room); });
  bindActs(view);
}

function disciplesList(g) {
  if (!g.disciples.length) return `<li class="dim">No disciples yet. ${g.recruit_tokens ? 'You hold a recruitment token — invite your first.' : 'Learn 30 items or pass a trial to earn a recruitment token.'}</li>`;
  const posts = g.rooms.filter((r) => 'capacity' in r && r.capacity > 0);
  return g.disciples.map((d) => {
    const mission = g.missions.find((m) => m.disciple === d.id);
    const where = d.away && mission ? `<span class="tag gold">${esc(mission.name)}, back in ${until(mission.ends)}</span>`
      : `<select data-assign="${esc(d.id)}" aria-label="Post for ${esc(d.name)}"><option value="">Resting</option>${posts.map((r) =>
        `<option value="${esc(r.id)}" ${d.room === r.id ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}</select>`;
    return `<li class="disciple">${face(d)}<div class="grow"><b>${esc(d.name)}</b>
      <div class="dim small">${esc(d.rank)}, level ${d.level}. ${esc(d.root)} root</div></div>${where}</li>`;
  }).join('');
}

async function gameAct(action, body = {}) {
  const res = await api(`/api/academy/game/${action}`, body);
  if (res.game) OV.game = scrub({ game: res.game }).game;
  if (res.ok === false) toast(res.error);
  else if (res.event) toast(res.event.text);
  return res;
}

function bindActs(root) {
  root.querySelectorAll('[data-act]').forEach((b) => {
    b.onclick = async () => {
      const act = b.dataset.act;
      if (act === 'collect') { const r = await gameAct('collect'); if (r.ok !== false) toast(`Collected ${r.stones} spirit stones.`); renderSect(); }
      else if (act === 'recruit') recruitSheet();
      else if (act === 'unseclude') { await gameAct('seclusion', { on: false }); await refresh(); renderSect(); }
    };
  });
  root.querySelectorAll('[data-assign]').forEach((s) => {
    s.onchange = async () => { await gameAct('assign', { disciple: s.dataset.assign, room: s.value }); await refresh(); if (location.pathname === '/') renderSect(); };
  });
}

async function recruitSheet() {
  const res = await gameAct('recruit');
  if (res.ok === false) return;
  res.candidates.forEach((c) => fix(c, NUMERIC.disciple));
  openSheet(`<h2>Three seekers wait at the gate</h2><p class="dim">Choose one to join the sect. A finer spirit root earns more and grows faster.</p>
    <div class="cands">${res.candidates.map((c) => `<div class="cand">${face(c, 72)}<b>${esc(c.name)}</b>
      <span class="tag ${c.talent >= 1.45 ? 'gold' : ''}">${esc(c.root)}</span><div class="dim small">${esc(c.traits.join(', '))}</div>
      <button class="btn primary" data-cand="${esc(c.id)}">Accept</button></div>`).join('')}</div>`);
  $('#sheet').querySelectorAll('[data-cand]').forEach((b) => {
    b.onclick = async () => { await gameAct('recruit-pick', { candidate: b.dataset.cand }); closeSheet(); await refresh(); renderSect(); };
  });
}

function roomSheet(id) {
  const g = OV.game; const r = g.rooms.find((x) => x.id === id); if (!r) return;
  let html = `<h2>${esc(r.name)}</h2><p class="dim">${r.open ? `Level ${r.level} of ${r.max}` : 'Not built yet'}</p><p>${esc(r.effect)}</p>`;
  if (r.course_hall) {
    html += r.open ? `<p>Cultivated here: ${esc(r.courses.join(', '))}.</p>
      <div class="row"><span class="grow">Memory strength</span><b class="num">${r.strength}%</b></div><div class="bar jade"><i style="width:${r.strength}%"></i></div>
      <p class="dim small" style="margin-top:8px">Disciples posted here earn spirit stones in proportion to how well you remember this art. Keep up your reviews and the hall prospers.</p>
      <a class="btn primary" href="/library" data-link>Open the library</a>`
      : `<p class="dim">${esc(r.locked)}</p><a class="btn primary" href="/library" data-link>Choose a course</a>`;
  } else {
    if (r.cost != null) {
      html += r.locked ? `<p class="tag red">${esc(r.locked)}</p>`
        : `<button class="btn primary" data-up ${g.stones < r.cost ? 'disabled' : ''}>${r.open ? 'Upgrade' : 'Build'} for ${r.cost} spirit stones</button>
           ${g.stones < r.cost ? `<p class="dim small" style="margin-top:6px">You have ${g.stones}. Finish sessions and quests to earn more.</p>` : ''}`;
    } else html += '<p class="tag gold">Highest level reached</p>';
    if (id === 'alchemy' && r.open) html += `<hr style="border-color:var(--edge)"><p>Grace pills in the cabinet: <b>${g.grace}/${g.grace_cap}</b>. Each one covers a missed day automatically.</p>
      <button class="btn" data-pill ${g.grace >= g.grace_cap || g.stones < g.pill_cost ? 'disabled' : ''}>Brew a pill for ${g.pill_cost} spirit stones</button>`;
    if (id === 'mission_hall' && r.open) html += missionHtml(g);
    if (id === 'quarters') html += `<hr style="border-color:var(--edge)"><p>${g.disciples.length} of ${g.disciple_cap} beds are taken. You hold ${g.recruit_tokens} recruitment token${g.recruit_tokens === 1 ? '' : 's'}.</p>`;
    if (id === 'trial_grounds') html += `<hr style="border-color:var(--edge)"><a class="btn" href="/trials" data-link>Go to the trials</a>`;
    if (id === 'grand_hall') html += `<hr style="border-color:var(--edge)"><p>${esc(g.master)}, ${esc(g.realm)} (${esc(g.stage)}). ${g.qi_into} of ${g.qi_need} qi toward the next stage.</p>
      <button class="btn" data-seclude>${g.seclusion ? 'Reopen the gates' : 'Enter seclusion (holiday mode)'}</button>
      <p class="dim small" style="margin-top:6px">Seclusion freezes your streak and pauses the sect's income while you are away.</p>`;
  }
  if ('capacity' in r && r.capacity > 0) {
    const here = g.disciples.filter((d) => d.room === id);
    html += `<hr style="border-color:var(--edge)"><p>Posted here: ${here.length ? esc(here.map((d) => d.name).join(', ')) : 'no one'} (${here.length}/${r.capacity}). Post disciples from the list on the sect page.</p>`;
  }
  openSheet(html);
  const s = $('#sheet');
  const again = async () => { await refresh(); renderSect(); roomSheet(id); };
  const up = $('[data-up]', s); if (up) up.onclick = async () => { await gameAct('upgrade', { room: id }); again(); };
  const pill = $('[data-pill]', s); if (pill) pill.onclick = async () => { await gameAct('pill'); again(); };
  const sec = $('[data-seclude]', s); if (sec) sec.onclick = async () => { await gameAct('seclusion', { on: !g.seclusion }); closeSheet(); await refresh(); renderSect(); };
  s.querySelectorAll('[data-dispatch]').forEach((b) => {
    b.onclick = async () => { const d = $('#m-who', s).value; if (!d) return; await gameAct('dispatch', { disciple: d, kind: b.dataset.dispatch }); again(); };
  });
}

function missionHtml(g) {
  const free = g.disciples.filter((d) => !d.away);
  const away = g.missions.map((m) => { const d = g.disciples.find((x) => x.id === m.disciple); return `<li>${esc(d ? d.name : 'A disciple')}: ${esc(m.name)}, back in ${until(m.ends)}</li>`; }).join('');
  return `<hr style="border-color:var(--edge)"><p>Mission orders: <b>${g.mission_tokens}</b>. Each completed study session earns one (you can hold three).</p>
    ${away ? `<ul class="list">${away}</ul>` : ''}
    ${free.length ? `<label class="field"><span>Send</span><select class="in" id="m-who">${free.map((d) => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join('')}</select></label>
      <div class="chips">${g.mission_kinds.map((k) => `<button class="chip" data-dispatch="${esc(k.id)}" ${g.mission_tokens ? '' : 'disabled'}>${esc(k.name)}, ${k.hours}h</button>`).join('')}</div>`
    : '<p class="dim">No disciples are free to send.</p>'}`;
}

/* ================= study session ================= */
const ACCENTS = { fr: 'é è ê à ç ù â î ô û ë ï œ'.split(' '), es: 'á é í ó ú ñ ü ¿ ¡'.split(' ') };
const TYPED = new Set(['type_l2', 'listen', 'cloze_type']);

async function renderStudy(params) {
  const practice = params && params.get('practice') === '1';
  const course = (params && params.get('course')) || '';
  view.innerHTML = '<p class="loading">Preparing your session…</p>';
  const s = await api('/api/academy/session', { course, practice });
  if (!s.exercises || !s.exercises.length) {
    const t = OV.today;
    view.innerHTML = `<div class="panel summary" style="max-width:560px;margin:8vh auto"><h1>${practice ? 'Nothing to practice yet' : 'Nothing is due'}</h1>
      <p class="dim">${practice ? 'Practice draws on items you have already learned. Finish a first session and come back.'
        : (t.sessions ? 'You have finished today\'s reviews and new items. They will return when your memory needs them.' : 'There is nothing scheduled right now.')}</p>
      <div class="row" style="justify-content:center;margin-top:16px">
        ${!practice && OV.game.learned ? '<a class="btn" href="/study?practice=1" data-link>Practice weak items</a>' : ''}
        ${!practice ? '<a class="btn" href="/library" data-link>Learn more today</a>' : ''}
        <a class="btn primary" href="/" data-link>Return to the sect</a></div></div>`;
    return;
  }
  runSession(s);
}

function runSession(s) {
  document.body.classList.add('in-session');
  const queue = s.exercises.slice();
  const notes = (s.notes || []).slice();
  const total = queue.filter((e) => e.mode !== 'intro').length;
  const st = { done: 0, first: 0, correct: 0, qi: 0, start: Date.now(), events: [], finished: false };
  leaveGuard = async () => {
    if (st.finished || !st.first) return true;
    if (!confirm('Leave this session? Your answers so far are saved.')) return false;
    await finish(true); return true;
  };
  const shell = (inner) => {
    view.innerHTML = `<div class="session"><div class="top"><button aria-label="Leave session" id="s-exit">✕</button>
      <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${st.done}"><i style="width:${Math.round(100 * st.done / Math.max(total, 1))}%"></i></div>
      <span class="dim small num">${st.done}/${total}</span></div><div class="ex">${inner}</div></div>`;
    $('#s-exit').onclick = () => go('/');
  };
  const sayBtn = (text, lang, cls = '') => (canSpeak(lang) ? `<button class="say ${cls}" data-say="${esc(text)}" data-lang="${esc(lang)}" aria-label="Play audio">${ICON.sound}</button>` : '');
  const bindSay = () => view.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => speak(b.dataset.say, b.dataset.lang); });

  async function finish(silent) {
    if (st.finished) return null; st.finished = true;
    const body = { session: s.session, secs: Math.round((Date.now() - st.start) / 1000) };
    let res = await api('/api/academy/session/finish', body);
    if (res.ok === false) res = await api('/api/academy/session/finish', body);      // one retry on a dropped connection
    if (silent) return res;
    if (res.ok === false) {
      leaveGuard = null;
      view.innerHTML = `<div class="session summary"><h1>Your answers are saved</h1>
        <p class="dim">The session could not be closed, so today's reward has not been paid yet: ${esc(res.error)}</p>
        <div class="foot"><button class="btn primary big" id="s-again">Try again</button></div></div>`;
      $('#s-again').onclick = () => { st.finished = false; finish(false); };
      return res;
    }
    summary(res);
    return res;
  }

  function summary(res) {
    leaveGuard = null;
    const acc = st.first ? Math.round(100 * st.correct / st.first) : 0;
    const events = [...st.events, ...((res && res.events) || [])];
    const petals = acc >= 70 ? `<div class="petals" aria-hidden="true">${Array.from({ length: 18 }, (_, i) => `<i style="left:${(i * 53) % 100}%;animation-delay:${(i % 6) * 0.18}s"></i>`).join('')}</div>` : '';
    view.innerHTML = `<div class="session summary">${petals}${guide(acc >= 70 ? 'happy' : 'calm', 96)}<h1>${s.practice ? 'Practice complete' : 'Session complete'}</h1>
      <p class="dim">${acc >= 90 ? 'Clean recall. The sect grows stronger.' : acc >= 70 ? 'Solid work. The misses will come back until they stick.' : 'A hard session is where memory is built. The misses come back until they stick.'}</p>
      <div class="gains"><div><b class="num">${acc}%</b><span>first try</span></div><div><b class="num">+${num(st.qi)}</b><span>qi</span></div><div><b class="num">+${num(res && res.stones)}</b><span>spirit stones</span></div></div>
      ${res && res.counted === false && !s.practice ? '<p class="dim small">Finish a whole session for it to count toward your streak.</p>' : ''}
      ${events.length ? `<ul class="list panel">${events.map((e) => `<li>${esc(e.text)}</li>`).join('')}</ul>` : ''}
      <div class="foot"><div class="row">
        ${res && res.due_left > 0 && !s.practice ? '<a class="btn grow" href="/study" data-link>Keep going</a>' : ''}
        <a class="btn primary grow" href="/" data-link>Return to the sect</a></div></div></div>`;
    refresh();
  }

  function showNotes() {
    const n = notes.shift();
    shell(`<div class="guide">${guide('calm')}<div class="speech">A new chapter opens. Read this once, then we practise.</div></div>
      <div class="introcard"><span class="newtag">New unit</span><h2 style="margin:2px 0 4px">${esc(n.title)}</h2>
      <p class="dim">${esc(n.goal)}</p>${md(n.notes)}</div><div class="foot"><button class="btn primary big" id="s-next">Start learning</button></div>`);
    $('#s-next').onclick = next; $('#s-next').focus();
  }

  function next() {
    if (notes.length) return showNotes();
    const ex = queue.shift();
    if (!ex) return finish(false);
    if (ex.mode === 'intro') return intro(ex);
    if (ex.mode === 'listen' && !canSpeak(ex.lang)) { ex.mode = 'type_l2'; ex.prompt = ex.hint; ex.ask = 'Type the translation'; }
    exercise(ex);
  }

  function intro(ex) {
    const c = ex.card; const lang = ex.lang;
    let body;
    if (c.type === 'concept') body = `<div class="l2">${esc(c.term)}</div><div class="l1">${esc(c.def)}</div>`;
    else if (c.type === 'cloze') body = `<div class="l2">${esc(c.full)} ${sayBtn(c.full, lang)}</div><div class="l1">${esc(c.l1 || '')}</div>`;
    else body = `<div class="l2">${esc(c.l2)} ${sayBtn(c.l2, lang)}</div><div class="l1">${esc(c.l1)}</div>
      ${c.ex ? `<div class="exm"><div>${esc(c.ex)} ${sayBtn(c.ex, lang)}</div><div class="dim">${esc(c.ex_l1 || '')}</div></div>` : ''}`;
    const canClaim = c.type !== 'concept';
    shell(`<div class="guide">${guide('calm')}<div class="speech">Something new. Read it, say it aloud, then continue.</div></div>
      <div class="introcard"><span class="newtag">New</span>${body}${c.note ? `<div class="note">${esc(c.note)}</div>` : ''}</div>
      <div class="foot"><div class="row">${canClaim ? '<button class="btn grow" id="s-know">I know this already</button>' : ''}<button class="btn primary big grow" id="s-next">Got it</button></div></div>`);
    bindSay();
    if (c.type !== 'concept') speak(c.type === 'cloze' ? c.full : c.l2, lang);
    $('#s-next').onclick = next; $('#s-next').focus();
    if (canClaim) $('#s-know').onclick = () => {
      // Prove it: the upcoming check becomes a typed answer from memory.
      const later = queue.find((q) => q.item === ex.item && q.mode !== 'intro');
      if (later) {
        if (c.type === 'cloze') Object.assign(later, { mode: 'cloze_type', prompt: c.text, sub: c.l1 || '', ask: 'Type the missing word', claim: true });
        else Object.assign(later, { mode: 'type_l2', prompt: c.l1, ask: 'Type it from memory', claim: true });
        delete later.choices;
      }
      next();
    };
  }

  function exercise(ex) {
    const lang = ex.lang; const typed = TYPED.has(ex.mode);
    const long = (ex.prompt || '').length > 90;
    let top;
    if (ex.mode === 'listen') top = `<div style="text-align:center">${sayBtn(ex.say, lang, 'huge')}<p class="dim small">Tap to hear it again. <button class="btn quiet" id="s-mute" style="min-height:32px;padding:0 8px">I can't listen now</button></p></div>`;
    else top = `<div class="prompt ${long ? 'long' : ''}">${esc(ex.prompt)} ${ex.say ? sayBtn(ex.say, lang) : ''}</div>${ex.sub ? `<div class="sub">${esc(ex.sub)}</div>` : ''}`;
    const accents = typed ? (ACCENTS[(lang || '').slice(0, 2)] || []) : [];
    const input = typed ? `<div class="typed"><input type="text" id="s-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" lang="${esc(lang)}" aria-label="Your answer" enterkeyhint="done">
        ${accents.length ? `<div class="accents">${accents.map((a) => `<button type="button" data-acc="${a}" tabindex="-1">${a}</button>`).join('')}</div>` : ''}</div>`
      : `<div class="opts">${ex.choices.map((c, i) => `<button class="opt" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(c)}</span></button>`).join('')}</div>`;
    shell(`<div class="guide">${guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || '')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>${top}${input}
      <div class="foot" id="s-foot">${typed ? '<button class="btn primary big" id="s-check">Check</button>' : ''}</div>`);
    bindSay();
    if (ex.say && ex.mode !== 'choose_l2') speak(ex.say, lang);
    let locked = false;
    const submit = async (given, btn) => {
      if (locked) return; locked = true;
      const res = await api('/api/academy/answer', { session: s.session, item: ex.item, mode: ex.mode, answer: given, retry: !!ex.retry, claim: !!ex.claim });
      if (res.ok === false) { locked = false; toast(res.error); return; }
      if (!ex.retry) {
        st.first += 1; st.correct += res.correct ? 1 : 0; st.qi += (res.rewards && res.rewards.qi) || 0;
        if (res.rewards && res.rewards.events && res.rewards.events.length) { st.events.push(...res.rewards.events); showEvents(res.rewards.events); }
      }
      if (res.correct) st.done += 1;
      else queue.splice(Math.min(3, queue.length), 0, { ...ex, retry: true, claim: false });   // it comes back until it is right
      view.querySelectorAll('.opt').forEach((o) => {
        o.disabled = true; const txt = ex.choices[+o.dataset.i];
        if (txt === res.expected) o.classList.add('right'); else if (o === btn) o.classList.add('wrong');
      });
      const inp = $('#s-in'); if (inp) inp.disabled = true;
      feedback(ex, res, given);
    };
    if (typed) {
      const inp = $('#s-in'); inp.focus();
      $('#s-check').onclick = () => { if (inp.value.trim()) submit(inp.value); else inp.focus(); };
      inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); $('#s-check') && $('#s-check').click(); } };
      view.querySelectorAll('[data-acc]').forEach((b) => {
        b.onclick = () => { const p = inp.selectionStart ?? inp.value.length; inp.value = inp.value.slice(0, p) + b.dataset.acc + inp.value.slice(inp.selectionEnd ?? p); inp.focus(); inp.setSelectionRange(p + 1, p + 1); };
      });
      const mute = $('#s-mute'); if (mute) mute.onclick = () => { ex.mode = 'type_l2'; ex.prompt = ex.hint; ex.ask = 'Type the translation'; exercise(ex); };
    } else {
      view.querySelectorAll('.opt').forEach((o) => { o.onclick = () => submit(ex.choices[+o.dataset.i], o); });
    }
    keyHandler = (e) => {
      if (!typed && !locked && /^[1-4]$/.test(e.key)) { const o = view.querySelector(`.opt[data-i="${+e.key - 1}"]`); if (o) o.click(); }
    };
  }

  function feedback(ex, res, given) {
    const x = res.explain || {};
    const flag = res.flag === 'accent' ? 'Right — mind the accents.' : res.flag === 'typo' ? 'Right — with a small slip.' : 'Correct';
    const when = !ex.retry && !s.practice && res.next_days != null ? (num(res.next_days) <= 0 ? 'It returns later in this session.' : `Next review in ${num(res.next_days)} day${num(res.next_days) === 1 ? '' : 's'}.`) : '';
    let detail;
    if (x.why) detail = `<p>${esc(x.why)}</p>`;
    else {
      // Show the pair once: the target-language form, then its meaning.
      const pair = x.l2 ? `<div class="ans">${esc(x.l2)}</div>${x.l1 ? `<p class="dim">${esc(x.l1)}</p>` : ''}` : '';
      const typedWrong = TYPED.has(ex.mode) && (!res.correct || res.flag) && res.expected !== x.l2 ? `<p>Answer: <b>${esc(res.expected)}</b></p>` : '';
      detail = `${pair}${typedWrong}${x.note ? `<p class="dim small">${esc(x.note)}</p>` : ''}`;
    }
    const showExpected = x.why && !res.correct;
    $('#s-foot').innerHTML = `<div class="verdict ${res.correct ? 'ok' : 'no'}" role="status">${guide(res.correct ? 'happy' : 'oops', 52)}<div class="grow"><h3>${res.correct ? flag : 'Not quite'}</h3>
      ${showExpected ? `<div class="ans">${esc(res.expected)}</div>` : ''}${detail}
      ${when ? `<p class="dim small">${when}${!ex.retry && res.rewards && res.rewards.qi ? ` +${num(res.rewards.qi)} qi` : ''}</p>` : ''}</div></div>
      <button class="btn ${res.correct ? 'primary' : 'seal'} big" id="s-next">Continue</button>`;
    if (TYPED.has(ex.mode) || ex.mode === 'choose_l2') speak(x.l2 || res.expected, ex.lang);
    const b = $('#s-next'); b.onclick = next; b.focus();
    keyHandler = null;
  }

  next();
}
let keyHandler = null;
document.addEventListener('keydown', (e) => { if (keyHandler && !e.metaKey && !e.ctrlKey && !e.altKey) keyHandler(e); });
window.addEventListener('beforeunload', (e) => { if (leaveGuard && document.body.classList.contains('in-session')) { e.preventDefault(); e.returnValue = ''; } });

/* ================= library ================= */
function renderLibrary(params) {
  const cid = params && params.get('course'); const uid = params && params.get('unit');
  if (cid && uid) return renderUnit(cid, uid);
  const mine = OV.courses.filter((c) => c.enrolled), rest = OV.courses.filter((c) => !c.enrolled);
  const HUE = { tongues_west: ['#5bb6ff', 'Fr'], tongues_south: ['#ff8a5c', 'Es'], ward_hall: ['#2fd39a', '盾'] };
  const card = (c) => {
    const [hue, mark] = HUE[c.hall] || ['#a78bfa', '道'];
    const cur = c.units.find((u) => u.unlocked && !u.done);
    return `<section class="panel course">
    <header><span class="crest" style="background:${hue};color:#10233f" aria-hidden="true">${c.hall === 'ward_hall' ? esc((c.exam && c.exam.code || 'Sec').slice(0, 3)) : mark}</span>
      <div class="grow"><h2>${esc(c.title)}</h2><p class="dim small" style="margin:2px 0 0">${esc(c.blurb)}</p></div>
      ${c.enrolled ? `<span class="tag jade">Enrolled</span>` : `<button class="btn primary" data-enroll="${esc(c.id)}">Begin this art</button>`}</header>
    ${c.enrolled ? `<div class="row small"><span class="grow dim">${c.seen} of ${c.total} learned · ${c.mastered} mastered · memory ${c.strength}%</span></div>
      <div class="bar jade" style="margin:6px 0 12px"><i style="width:${Math.round(100 * c.seen / Math.max(c.total, 1))}%"></i></div>
      <div class="row"><a class="btn primary" href="/study?course=${encodeURIComponent(c.id)}" data-link>Study this art <span class="num">${c.due + c.new_left}</span></a>
        ${c.seen < c.total ? `<button class="btn" data-more="${esc(c.id)}">Learn 5 more today</button>` : ''}
        <button class="btn quiet" data-drop="${esc(c.id)}">Set aside</button></div>` : ''}
    <div class="path">${c.units.map((u, i) => {
      const state = !c.enrolled ? '' : u.done ? 'done' : (cur && cur.id === u.id) ? 'now' : u.unlocked ? '' : 'locked';
      return `<button class="step ${state}" data-unit="${esc(u.id)}" data-course="${esc(c.id)}">
        <span class="node">${state === 'done' ? ICON.check : state === 'locked' ? ICON.lock : i + 1}</span>
        <span><b>${esc(u.title)}</b><span class="dim small">${esc(u.goal)}</span>
        ${c.enrolled && u.seen > 0 && !u.done ? `<span class="bar thin jade" style="display:block"><i style="width:${Math.round(100 * u.seen / u.items)}%"></i></span>` : ''}</span></button>`;
    }).join('')}</div>
  </section>`;
  };
  view.innerHTML = `<h1 style="margin-bottom:14px">Library</h1>${mine.map(card).join('')}
    ${rest.length ? `<h2 style="margin:22px 0 10px">Other arts you can take up</h2>${rest.map(card).join('')}` : ''}`;
  view.querySelectorAll('[data-unit]').forEach((b) => { b.onclick = () => go(`/library?course=${encodeURIComponent(b.dataset.course)}&unit=${encodeURIComponent(b.dataset.unit)}`); });
  view.querySelectorAll('[data-enroll]').forEach((b) => { b.onclick = async () => { await api('/api/academy/enroll', { course: b.dataset.enroll, on: true }); toast('A new hall opens in the sect.'); go('/library', false); }; });
  view.querySelectorAll('[data-drop]').forEach((b) => { b.onclick = async () => { if (!confirm('Set this art aside? Your progress is kept, and you can take it up again any time.')) return; await api('/api/academy/enroll', { course: b.dataset.drop, on: false }); go('/library', false); }; });
  view.querySelectorAll('[data-more]').forEach((b) => { b.onclick = async () => { const r = await api('/api/academy/learn-more', { course: b.dataset.more, n: 5 }); if (r.ok !== false) { toast('5 more new items added to today.'); go(`/study?course=${encodeURIComponent(b.dataset.more)}`); } else toast(r.error); }; });
}

async function renderUnit(cid, uid) {
  view.innerHTML = '<p class="loading">Unrolling the scroll…</p>';
  const u = await api(`/api/academy/unit?course=${encodeURIComponent(cid)}&unit=${encodeURIComponent(uid)}`);
  if (u.ok === false) { view.innerHTML = `<div class="panel"><p>${esc(u.error)}</p><a class="btn" href="/library" data-link>Back to the library</a></div>`; return; }
  const lang = u.lang;
  const row = (it) => {
    let a, b;
    if (it.type === 'concept') { a = esc(it.term); b = esc(it.def); }
    else if (it.type === 'mcq') { a = esc(it.q); b = `<span class="dim">${esc(it.correct)}.</span> ${esc(it.why || '')}`; }
    else if (it.type === 'cloze') { const full = it.full; a = `${esc(full)} ${canSpeak(lang) ? `<button class="say tiny" data-say="${esc(full)}" aria-label="Play audio">${ICON.sound}</button>` : ''}`; b = esc(it.l1 || ''); }
    else { a = `${esc(it.l2)} ${canSpeak(lang) ? `<button class="say tiny" data-say="${esc(it.l2)}" aria-label="Play audio">${ICON.sound}</button>` : ''}`; b = `${esc(it.l1)}${it.note ? `<br><span class="dim small">${esc(it.note)}</span>` : ''}`; }
    const hide = it.type === 'mcq' && it.state === 'new';
    return `<tr><td><span class="dot ${esc(it.state)}" title="${esc(it.state)}"></span>${a}</td><td>${hide ? '<span class="dim">Answer hidden until you have met this question.</span>' : b}</td>
      <td class="dim small num" style="white-space:nowrap">${it.state === 'new' ? '' : `${num(it.strength)}%`}</td></tr>`;
  };
  view.innerHTML = `<p><a href="/library" data-link>Library</a></p><h1>${esc(u.title)}</h1><p class="dim">${esc(u.goal)}</p>
    <section class="panel">${md(u.notes)}</section>
    <section class="panel"><h2>Items</h2><p class="dim small"><span class="dot"></span>new <span class="dot learning" style="margin-left:10px"></span>learning <span class="dot mastered" style="margin-left:10px"></span>mastered. The percentage is the chance you would recall it right now.</p>
      <div class="scroll-x"><table class="items">${u.items.map(row).join('')}</table></div></section>`;
  view.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => speak(b.dataset.say, lang); });
}

/* ================= trials ================= */
async function renderTrials() {
  const mine = OV.courses.filter((c) => c.enrolled);
  view.innerHTML = '<p class="loading">Reading the heavens…</p>';
  const infos = await Promise.all(mine.map((c) => api(`/api/academy/trial?course=${encodeURIComponent(c.id)}`)));
  const g = OV.game;
  view.innerHTML = `<h1>Trials</h1><p class="dim" style="max-width:68ch">A trial is a timed test with no hints. Passing one is how you survive a tribulation and enter the next great realm. Anything you get wrong that you have already studied goes back into your review queue.</p>
    ${g.tribulation ? `<div class="panel today"><h2>A tribulation gathers</h2><p style="margin:0">Your qi is full at ${esc(g.realm)}, ${esc(g.stage)} stage. Pass any trial below to break through to ${esc(g.next_realm)}.</p></div>` : ''}
    ${infos.map((t, i) => (t.ok === false ? '' : `<section class="panel"><div class="row"><div class="grow"><h2>${esc(t.name)}</h2>
        <p class="dim small" style="margin:2px 0 0">${num(t.questions)} questions, ${num(t.minutes)} minutes, ${num(t.pass_pct)}% to pass${t.best != null ? `. Your best: ${num(t.best)}%` : ''}</p></div>
        <button class="btn seal" data-trial="${esc(mine[i].id)}" ${t.ready ? '' : 'disabled'}>Face the trial</button></div>
        ${t.need ? `<p class="dim small" style="margin:8px 0 0">${esc(t.need)}</p>` : ''}
        ${mine[i].exam ? `<p class="dim small" style="margin:8px 0 0">Modelled on ${esc(mine[i].exam.name)} ${esc(mine[i].exam.code)}: questions are drawn across the official domains by their exam weights. Scoring ${num(t.pass_pct)}% here consistently is a sign you are ready for the real exam.</p>` : ''}
        ${t.history.length ? `<ul class="list small" style="margin-top:8px">${t.history.slice().reverse().slice(0, 5).map((h) => `<li><span class="tag ${h.passed ? 'jade' : 'red'}">${h.passed ? 'Passed' : 'Failed'}</span> ${num(h.pct)}% (${num(h.right)}/${num(h.total)}) <span class="dim">${ago(num(h.ts))} ago</span></li>`).join('')}</ul>` : ''}
      </section>`)).join('') || '<div class="panel dim">Enrol in a course to unlock its trial.</div>'}`;
  view.querySelectorAll('[data-trial]').forEach((b) => { b.onclick = () => startTrial(b.dataset.trial); });
}

async function startTrial(course) {
  const t = await api('/api/academy/trial/start', { course });
  if (t.ok === false) { toast(t.error); return; }
  document.body.classList.add('in-session');
  const qs = t.questions; const answers = qs.map(() => null); let cur = 0; let over = false; let sending = false;
  const deadline = Date.now() + num(t.minutes) * 60000;
  let timer = null;
  leaveGuard = async () => {
    if (over) return true;
    if (!confirm('Abandon this trial? Nothing will be recorded.')) return false;
    over = true; clearInterval(timer);                       // this trial's clock must never fire again
    api('/api/academy/trial/abandon', { trial: t.trial });
    return true;
  };
  const draw = () => {
    const q = qs[cur]; const typed = TYPED.has(q.mode);
    const accents = typed ? (ACCENTS[(q.lang || '').slice(0, 2)] || []) : [];
    view.innerHTML = `<div class="session"><div class="top"><b class="grow">${esc(t.name)}</b><span class="timer" id="t-clock"></span></div>
      <div class="ex"><p class="ask">Question ${cur + 1} of ${qs.length}. ${esc(q.ask || '')}</p>
      <div class="prompt ${(q.prompt || '').length > 90 ? 'long' : ''}">${esc(q.prompt)}</div>${q.sub ? `<div class="sub">${esc(q.sub)}</div>` : ''}
      ${typed ? `<div class="typed"><input type="text" id="t-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" value="${esc(answers[cur] || '')}" aria-label="Your answer">
          ${accents.length ? `<div class="accents">${accents.map((a) => `<button type="button" data-acc="${a}" tabindex="-1">${a}</button>`).join('')}</div>` : ''}</div>`
        : `<div class="opts">${q.choices.map((c, i) => `<button class="opt ${answers[cur] === c ? 'picked' : ''}" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(c)}</span></button>`).join('')}</div>`}
      <div class="qnav">${qs.map((_, i) => `<button class="${i === cur ? 'cur' : ''} ${answers[i] ? 'done' : ''}" data-q="${i}" aria-label="Question ${i + 1}">${i + 1}</button>`).join('')}</div>
      <div class="foot"><div class="row"><button class="btn grow" id="t-prev" ${cur ? '' : 'disabled'}>Back</button>
        ${cur < qs.length - 1 ? '<button class="btn primary grow" id="t-next">Next</button>' : '<button class="btn seal grow" id="t-done">Submit trial</button>'}</div></div></div></div>`;
    tick();
    const keep = () => { const i = $('#t-in'); if (i) answers[cur] = i.value.trim() || null; };
    const move = (n) => { keep(); cur = n; draw(); };
    view.querySelectorAll('.opt').forEach((o) => { o.onclick = () => { answers[cur] = q.choices[+o.dataset.i]; if (cur < qs.length - 1) move(cur + 1); else draw(); }; });
    view.querySelectorAll('[data-q]').forEach((b) => { b.onclick = () => move(+b.dataset.q); });
    const inp = $('#t-in');
    if (inp) {
      inp.focus(); inp.onkeydown = (e) => { if (e.key === 'Enter' && cur < qs.length - 1) move(cur + 1); };
      view.querySelectorAll('[data-acc]').forEach((b) => {
        b.onclick = () => { const at = inp.selectionStart ?? inp.value.length; inp.value = inp.value.slice(0, at) + b.dataset.acc + inp.value.slice(inp.selectionEnd ?? at); inp.focus(); inp.setSelectionRange(at + 1, at + 1); };
      });
    }
    $('#t-prev').onclick = () => move(cur - 1);
    if ($('#t-next')) $('#t-next').onclick = () => move(cur + 1);
    if ($('#t-done')) $('#t-done').onclick = () => { keep(); const blank = answers.filter((a) => !a).length; if (!blank || confirm(`${blank} question${blank > 1 ? 's are' : ' is'} unanswered. Submit anyway?`)) submit(); };
    keyHandler = (e) => { if (!typed && /^[1-4]$/.test(e.key)) { const o = view.querySelector(`.opt[data-i="${+e.key - 1}"]`); if (o) o.click(); } };
  };
  const tick = () => {
    if (over) return;
    const el = $('#t-clock'); if (!el) return;
    const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
    el.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`; el.classList.toggle('low', left < 60);
    if (left <= 0 && !over) submit();
  };
  timer = setInterval(() => { if (over) clearInterval(timer); else tick(); }, 1000);
  const submit = async () => {
    if (over || sending) return; sending = true;
    const i = $('#t-in'); if (i) answers[cur] = i.value.trim() || null;
    const res = await api('/api/academy/trial/submit', { trial: t.trial, answers });
    sending = false;
    if (res.ok === false) {
      // Keep every answer: the learner can submit again once the connection is back.
      toast(`${res.error} Your answers are still here — submit again.`, 8000);
      if (Date.now() >= deadline) { over = true; clearInterval(timer); leaveGuard = null; }
      return;
    }
    over = true; keyHandler = null; clearInterval(timer);
    leaveGuard = null; document.body.classList.remove('in-session');
    showEvents(res.events);
    const misses = res.review.filter((r) => !r.correct);
    view.innerHTML = `<div class="summary" style="max-width:720px;margin:0 auto">${guide(res.passed ? 'happy' : 'think', 96)}<h1>${res.passed ? 'You passed the trial' : 'The trial stands unbroken'}</h1>
      <p class="dim">${res.passed ? 'Your foundation holds.' : res.overtime ? 'The time ran out before you finished.' : `You need ${num(res.pass_pct)}% to pass. What you missed is listed below, and the ones you have studied are back in your review queue.`}</p>
      <div class="gains"><div><b class="num">${num(res.pct)}%</b><span>score</span></div><div><b class="num">${num(res.right)}/${num(res.total)}</b><span>correct</span></div><div><b class="num">+${num(res.stones)}</b><span>spirit stones</span></div></div>
      ${res.domains.length > 1 ? `<section class="panel" style="text-align:left"><h2>By domain</h2>${res.domains.map((d) => `<div style="margin-top:10px"><div class="row small"><span class="grow">${esc(d.title)}</span><b class="num">${num(d.pct)}%</b></div>
        <div class="bar ${num(d.pct) >= num(res.pass_pct) ? 'jade' : ''}"><i style="width:${num(d.pct)}%"></i></div></div>`).join('')}</section>` : ''}
      ${misses.length ? `<section class="panel" style="text-align:left"><h2>What you missed</h2><ul class="list">${misses.map((m) => `<li><b>${esc(m.prompt)}</b>
        <div class="small"><span style="color:#ff9a8a">${m.given ? esc(m.given) : 'No answer'}</span> <span class="dim">should be</span> <span style="color:var(--jade)">${esc(m.expected)}</span></div>
        ${m.explain.why ? `<div class="dim small">${esc(m.explain.why)}</div>` : ''}</li>`).join('')}</ul></section>` : ''}
      <div class="row" style="justify-content:center;margin-top:16px"><a class="btn" href="/trials" data-link>Back to trials</a><a class="btn primary" href="/" data-link>Return to the sect</a></div></div>`;
    window.scrollTo(0, 0); refresh();
  };
  draw();
}

/* ================= progress ================= */
async function renderProgress() {
  view.innerHTML = '<p class="loading">Counting the days…</p>';
  const s = await api('/api/academy/stats?days=119');
  if (s.ok === false) { view.innerHTML = `<div class="panel">${esc(s.error)}</div>`; return; }
  const set = OV.settings; const g = OV.game;
  ['cards', 'mastered', 'minutes', 'active_days', 'answers'].forEach((k) => { s[k] = num(s[k]); });
  s.accuracy = s.accuracy == null ? null : num(s.accuracy);
  s.forecast = (s.forecast || []).map(num); s.days.forEach((d) => { d.answers = num(d.answers); });
  const max = Math.max(1, ...s.forecast);
  const first = new Date(`${s.days[0].day}T12:00:00`); const pad = (first.getDay() + 6) % 7;
  const heat = `${'<i style="visibility:hidden"></i>'.repeat(pad)}${s.days.map((d) => `<i class="${d.answers >= 40 ? 'l3' : d.answers >= 15 ? 'l2' : d.answers ? 'l1' : ''}" title="${esc(d.day)}: ${d.answers} answers"></i>`).join('')}`;
  const mine = OV.courses.filter((c) => c.enrolled);
  view.innerHTML = `<h1 style="margin-bottom:14px">Progress</h1>
    <div class="stats">
      <div class="stat"><b class="num">${s.cards}</b><span>items learned</span></div>
      <div class="stat"><b class="num">${s.mastered}</b><span>mastered (3+ weeks stable)</span></div>
      <div class="stat"><b class="num">${s.accuracy == null ? '–' : `${s.accuracy}%`}</b><span>first-try accuracy</span></div>
      <div class="stat"><b class="num">${s.minutes}</b><span>minutes studied over ${s.active_days} day${s.active_days === 1 ? '' : 's'}</span></div>
    </div>
    <section class="panel" style="margin-top:14px"><h2>The last 17 weeks</h2><p class="dim small">Each square is a day. Brighter means more answers. Best streak: ${g.best_streak} day${g.best_streak === 1 ? '' : 's'}.</p><div class="heat">${heat}</div></section>
    <section class="panel"><h2>Reviews coming due</h2><p class="dim small">How many items your memory will need you to revisit over the next two weeks.</p>
      <div class="cols" style="margin-top:22px">${s.forecast.map((n, i) => `<div class="${i ? '' : 'today'}" style="height:${Math.round(100 * n / max)}%" title="${i ? `In ${i} day${i > 1 ? 's' : ''}` : 'Today'}: ${n}"><span>${n || ''}</span></div>`).join('')}</div>
      <div class="row small dim" style="justify-content:space-between;margin-top:4px"><span>Today</span><span>In 2 weeks</span></div></section>
    <section class="panel"><h2>Arts</h2>${mine.map((c) => `<div style="margin-top:12px"><div class="row small"><span class="grow"><b>${esc(c.title)}</b></span><span class="dim num">${c.seen}/${c.total} learned, ${c.mastered} mastered</span></div>
      <div class="bar jade" style="margin-top:4px"><i style="width:${Math.round(100 * c.seen / Math.max(c.total, 1))}%"></i></div></div>`).join('')}</section>
    <section class="panel"><h2>Settings</h2>
      <div class="setting"><div class="grow"><b>New items a day, per art</b><span>More items now means more reviews later. 8 is a steady pace.</span></div><input type="number" id="set-new" min="0" max="40" value="${set.new_per_day}"></div>
      <div class="setting"><div class="grow"><b>Session length</b><span>The number of exercises in one session.</span></div><input type="number" id="set-size" min="5" max="60" value="${set.session_size}"></div>
      <div class="setting"><div class="grow"><b>Target recall</b><span>How sure you want to be of remembering an item when it comes back. Higher means more reviews.</span></div>
        <select class="in" id="set-ret" style="width:110px">${[0.85, 0.9, 0.93].map((r) => `<option value="${r}" ${Math.abs(set.retention - r) < 0.005 ? 'selected' : ''}>${Math.round(r * 100)}%</option>`).join('')}</select></div>
      <div class="setting"><div class="grow"><b>Spoken audio</b><span>${synth ? 'Uses the voices installed on this device.' : 'This browser has no speech voices, so listening exercises become typing ones.'}</span></div>
        <input type="checkbox" id="set-audio" style="width:24px;height:24px;accent-color:var(--jade)" ${set.audio ? 'checked' : ''}></div>
      <div class="setting"><div class="grow"><b>Seclusion</b><span>Holiday mode: freezes your streak and the sect's income until you return.</span></div>
        <button class="btn" id="set-sec">${g.seclusion ? 'Reopen the gates' : 'Enter seclusion'}</button></div>
      <div class="setting"><div class="grow"><b>Backup</b><span>Download everything (progress and sect) as one file, or restore from one.</span></div>
        <button class="btn" id="set-exp">Download backup</button><label class="btn">Restore<input type="file" id="set-imp" accept="application/json" hidden></label></div>
    </section>
    <p class="dim small" style="margin-top:18px">Also here: the <a href="/learn">AI tutor</a> (needs a model backend) and the <a href="/command">fleet command hall</a>.</p>`;
  const save = async (patch) => { const r = await api('/api/academy/settings', patch, 'PUT'); if (r.ok === false) toast(r.error); else { Object.assign(OV.settings, r); toast('Saved.'); } };
  $('#set-new').onchange = (e) => save({ new_per_day: +e.target.value });
  $('#set-size').onchange = (e) => save({ session_size: +e.target.value });
  $('#set-ret').onchange = (e) => save({ retention: +e.target.value });
  $('#set-audio').onchange = (e) => save({ audio: e.target.checked });
  $('#set-sec').onclick = async () => { await gameAct('seclusion', { on: !g.seclusion }); go('/progress', false); };
  $('#set-exp').onclick = async () => {
    const data = await api('/api/academy/export'); if (data.ok === false) { toast(data.error); return; }
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    a.download = `sect-academy-${OV.today.day}.json`; a.click(); URL.revokeObjectURL(a.href);
  };
  $('#set-imp').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    let data; try { data = JSON.parse(await f.text()); } catch (_) { toast('That file is not a Sect Academy backup.'); return; }
    if (!confirm('Replace all current progress with this backup?')) return;
    const r = await api('/api/academy/import', data); if (r.ok === false) toast(r.error); else { toast('Backup restored.'); go('/', false); }
  };
}

go(location.pathname + location.search, false);
