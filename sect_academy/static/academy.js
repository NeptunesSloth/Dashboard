// Sect Academy — the app shell: the sect (a colony sim), study sessions, library, trials, progress.
// Everything is served from this origin; nothing is fetched from anywhere else.
// Vanilla JS, no build step. All server/user text goes through esc() before innerHTML.

import { ICON, backdrop, portrait } from '/art.js';
import { mountSect } from '/sect.js';

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
// Anything shown as a number is forced to be one, so a doctored save file cannot inject markup.
const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
const TOKEN_KEY = 'sect.token';
const headers = () => { const t = localStorage.getItem(TOKEN_KEY) || ''; return t ? { 'x-academy-token': t } : {}; };

async function api(path, body, method) {
  try {
    const opts = { headers: headers() };
    if (body !== undefined) { opts.method = method || 'POST'; opts.headers = { 'Content-Type': 'application/json', ...headers() }; opts.body = JSON.stringify(body); }
    const r = await fetch(path, opts);
    if (r.status === 401) {
      // This copy of the app was started with an access token (SECT_ACADEMY_TOKEN).
      const t = prompt('This Sect Academy needs its access token:');
      if (t) { localStorage.setItem(TOKEN_KEY, t.trim()); return api(path, body, method); }
      return { ok: false, error: 'An access token is needed.' };
    }
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
  today: ['due', 'new_left', 'answers', 'correct', 'sessions', 'new', 'reviews'],
  settings: ['new_per_day', 'session_size', 'retention', 'tz_offset_min'],
  course: ['total', 'seen', 'mastered', 'due', 'new_left', 'strength', 'units_done'],
  unit: ['items', 'seen', 'mastered'],
};
const fix = (o, keys) => { if (o && typeof o === 'object') keys.forEach((k) => { if (k in o && o[k] !== null) o[k] = num(o[k]); }); return o; };
function scrub(ov) {
  fix(ov.today, NUMERIC.today); fix(ov.settings, NUMERIC.settings);
  (ov.courses || []).forEach((c) => { fix(c, NUMERIC.course); (c.units || []).forEach((u) => fix(u, NUMERIC.unit)); });
  Object.values(ov.placements || {}).forEach((pl) => fix(pl, ['passed_units', 'units', 'placed', 'asked', 'right']));
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
    `<a href="${href}" data-link ${href === path ? 'aria-current="page"' : ''}>${ICON[glyph]}${label}${href === '/study' && due ? `<span class="badge">${due > 99 ? '99+' : due}</span>` : ''}</a>`).join('');
}
async function refresh() {
  const tz = -new Date().getTimezoneOffset();
  const ov = await api(`/api/overview?tz=${tz}`);
  if (ov && ov.courses) {
    OV = scrub(ov);
    if (ov.events && ov.events.length) showEvents(ov.events);
    if (ov.problem && ov.problem !== lastProblem) { lastProblem = ov.problem; toast(ov.problem, 12000); }
  }
  drawNav();
  return OV;
}
let herePath = location.pathname + location.search;
let sectView = null;
async function go(path, push = true) {
  if (leaveGuard && !(await leaveGuard())) {
    // The learner chose to stay: put the address bar back where the session lives.
    if (!push && location.pathname + location.search !== herePath) history.pushState({}, '', herePath);
    return;
  }
  leaveGuard = null; keyHandler = null;
  if (sectView) { sectView.stop(); sectView = null; }
  document.body.classList.remove('in-session');
  closeSheet();
  if (push && path !== location.pathname + location.search) history.pushState({}, '', path);
  herePath = path;
  const url = new URL(path, location.origin);
  await refresh();
  if (!OV) { view.innerHTML = `<div class="panel"><h2>The mountain gate is closed</h2><p class="dim">The server did not answer. Check that it is running, then try again.</p><button class="btn primary" id="retry">Try again</button></div>`; $('#retry').onclick = () => go(path, false); return; }
  if (!OV.sect.founded) { renderFounding(); return; }
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
  const firstPick = (courses.find((c) => c.id.endsWith('-a1')) || courses[0] || {}).id;   // one art ticked to start; the learner adds the rest
  view.innerHTML = `<div class="found">
    <div class="hero"><img src="${backdrop('map')}" alt="A sect of pavilions on mountain peaks above the clouds"></div>
    <h1>Found your sect</h1>
    <p class="dim">Every answer you give from memory becomes qi. Qi raises your realm, and your realm raises the sect. Choose what you will cultivate — you can change this later in the library.</p>
    <label class="field"><span>Name of the sect</span><input type="text" id="f-name" maxlength="40" placeholder="Azure Lantern Sect" autocomplete="off"></label>
    <label class="field"><span>Your name as Sect Master</span><input type="text" id="f-master" maxlength="30" placeholder="Master Jay" autocomplete="off"></label>
    <h3 style="margin-top:20px">Arts to cultivate</h3>
    ${courses.length ? courses.map((c) => `<label class="pick"><input type="checkbox" value="${esc(c.id)}" ${c.id === firstPick ? 'checked' : ''}>
      <span><b>${esc(c.title)}</b><br><span class="dim small">${esc(c.blurb)} ${c.total} items in ${c.units.length} units.</span></span></label>`).join('')
    : '<p class="dim">No courses are installed. Add a pack under <code>sect_academy/packs</code> and reload.</p>'}
    <p class="dim small" style="margin-top:14px">Each art adds about 8 new items a day. One is ticked to start; two or three is a comfortable daily load, and more arts can be added later in the library.</p>
    <h3 style="margin-top:20px">How harsh should the world be?</h3>
    ${OV.sect.storytellers.map((t) => `<label class="pick"><input type="radio" name="f-tell" value="${esc(t.id)}" ${t.id === 'balanced' ? 'checked' : ''}>
      <span><b>${esc(t.name)}</b><br><span class="dim small">${esc(t.blurb)}</span></span></label>`).join('')}
    <p class="dim small" style="margin-top:10px">The sect lives on its own clock: disciples farm, build and cultivate whether or not you study. Studying makes them better at it.</p>
    <p id="f-err" class="small" style="color:var(--verm-d);font-weight:800" role="alert"></p>
    <button class="btn primary big" id="f-go" style="width:100%">Found the sect</button>
  </div>`;
  $('#f-go').onclick = async () => {
    const picked = [...view.querySelectorAll('.pick input:checked')].map((i) => i.value);
    if (!picked.length) { $('#f-err').textContent = 'Choose at least one art to cultivate.'; return; }
    const tell = (view.querySelector('input[name="f-tell"]:checked') || {}).value || 'balanced';
    const res = await api('/api/setup', { name: $('#f-name').value, master: $('#f-master').value, courses: picked, storyteller: tell });
    if (res.ok === false) { $('#f-err').textContent = res.error; return; }
    await refresh();
    offerPlacement(picked);
  };
}

/* ================= sect home ================= */
const ago = (ts) => { const s = Date.now() / 1000 - ts; if (s < 90) return 'now'; if (s < 3600) return `${Math.round(s / 60)}m`; if (s < 86400) return `${Math.round(s / 3600)}h`; return `${Math.round(s / 86400)}d`; };

const shortName = (c) => { const [a, b] = String(c.title).split(' — '); return c.kind === 'language' && b ? `${a} ${b.split(' ')[0]}` : a; };

function todayPanel() {
  const t = OV.today, g = OV.sect;
  const mine = OV.courses.filter((c) => c.enrolled);
  const work = t.due + t.new_left;
  let head, sub, btn, mood = 'calm', tone = '';
  if (!mine.length) {
    head = 'Choose an art to study'; sub = 'You are not enrolled in any course yet. Pick one in the library to begin.';
    btn = `<a class="btn primary big" href="/library" data-link>Open the library</a>`; mood = 'think'; tone = 'rest';
  } else if (g.seclusion) {
    head = 'The gates are sealed'; sub = 'You are in seclusion. Your study streak is frozen and the sect stands still until you return.';
    btn = `<button class="btn primary big" data-act="unseclude">Reopen the gates</button>`; tone = 'rest';
  } else if (work > 0) {
    head = g.studied_today ? 'There is more, if you wish' : 'Your study for today';
    sub = `<span class="counts"><span class="count"><b class="num">${t.due}</b>to review</span><span class="count new"><b class="num">${t.new_left}</b>new</span></span>`;
    btn = `<a class="btn primary big" href="/study" data-link>${g.studied_today ? 'Keep studying' : 'Begin studying'}</a>`;
    mood = g.studied_today ? 'happy' : 'calm';
  } else {
    head = 'Today is complete'; sub = 'Nothing more is due until tomorrow. Tend the sect, or sharpen your weakest items.';
    btn = `<a class="btn big" href="/study?practice=1" data-link>Practice weak items</a>`; mood = 'happy'; tone = 'rest';
  }
  const extras = [OV.mistakes ? `<a class="chip" href="/study?kind=mistakes" data-link>Put right ${num(OV.mistakes)} mistake${num(OV.mistakes) === 1 ? '' : 's'}</a>` : '',
    OV.can_listen && synth ? '<a class="chip" href="/study?kind=listen" data-link>Listening practice</a>' : ''].join('');
  const risk = g.streak_at_risk && !g.seclusion && work > 0 ? `<p class="small" style="margin:6px 0 0;font-weight:700">Study today to keep your ${g.streak}-day streak${g.grace ? ` (${g.grace} rest day${g.grace > 1 ? 's' : ''} in reserve)` : ''}.</p>` : '';
  const chips = mine.length > 1 && work > 0 && !g.seclusion ? `<div class="chips">${mine.filter((c) => c.due + c.new_left > 0).map((c) =>
    `<a class="chip" href="/study?course=${encodeURIComponent(c.id)}" data-link>${esc(shortName(c))} <span class="dim num">${c.due + c.new_left}</span></a>`).join('')}</div>` : '';
  return `<section class="panel today ${tone}"><div class="says">${guide(mood)}<div class="bubble"><h2>${head}</h2><div style="margin-top:6px">${sub}</div>${risk}
      <p class="dim small" style="margin:8px 0 0">Each correct answer gives you qi and the sect a point of insight for research. A finished session lifts every disciple's mood.</p></div></div>
    <div class="row">${btn}</div>${chips}${extras ? `<div class="chips">${extras}</div>` : ''}</section>`;
}

function masterPanel() {
  const g = OV.sect; const m = g.pawns.find((p) => p.master);
  if (!m) return '<section class="panel"></section>';
  const week = Array.from({ length: g.week.goal }, (_, i) => `<i class="${i < g.week.days ? 'on' : ''}"></i>`).join('');
  return `<section class="panel realm"><div class="who">${portrait(m.id + m.name, { root: m.root, size: 64, kind: 'master', mood: m.mood >= 65 ? 'happy' : 'calm' })}<span class="ring"></span></div>
    <div class="grow"><b>${esc(m.name)}</b> <span class="tag blue">${esc(m.realm)} · ${esc(m.stage)}</span>
      <div class="bar violet" title="${m.qi} of ${m.qi_need} qi"><i style="width:${m.qi_pct}%"></i></div>
      <div class="small dim" style="margin-top:4px">${ICON.qi} ${m.qi} / ${m.qi_need} qi. You gain it by meditating in the sect and by studying.</div>
      <div class="mini"><span><b class="num">${g.pawns.length}</b>disciples</span><span><b class="num">${g.wealth.toLocaleString()}</b>sect wealth</span>
        <span title="${g.week.days} of ${g.week.goal} study days this week"><b class="week">${week}</b>study week</span></div></div></section>`;
}

function renderSect() {
  sectView = mountSect({
    view, $, esc, api, toast, openSheet, closeSheet,
    sect: () => OV.sect, setSect: (s) => { OV.sect = s; }, todayPanel, masterPanel,
    bindToday: (root) => {
      const un = root.querySelector('[data-act="unseclude"]');
      if (un) un.onclick = async () => { await api('/api/sect/seclusion', { on: false }); go('/', false); };
    },
  });
}

/* ================= placement ================= */
function offerPlacement(courses) {
  const list = OV.courses.filter((c) => courses.includes(c.id));
  view.innerHTML = `<div class="found"><div class="guide">${guide('think', 72)}<div class="speech">Before we begin: how much do you already know?</div></div>
    <h1>Find your level</h1>
    <p class="dim">A short placement test checks each course a unit at a time and stops when it finds your level. Units you already know are skipped (they come back as reviews, so a lucky guess is caught). It takes a few minutes per course, and you can do it later from the library.</p>
    ${list.map((c) => `<div class="pick" style="cursor:default"><span class="grow"><b>${esc(c.title)}</b><br><span class="dim small">${c.units.length} units</span></span>
      <button class="btn primary" data-place="${esc(c.id)}">Take the test</button></div>`).join('')}
    <div class="foot"><button class="btn big" id="pl-skip">I am a beginner — start from the first unit</button></div></div>`;
  view.querySelectorAll('[data-place]').forEach((b) => { b.onclick = () => runPlacement(b.dataset.place, () => offerPlacement(courses)); });
  $('#pl-skip').onclick = () => go('/', false);
}

async function runPlacement(course, done) {
  const first = await api('/api/placement/start', { course });
  if (first.ok === false) { toast(first.error); return; }
  document.body.classList.add('in-session');
  let over = false;
  leaveGuard = async () => over || confirm('Stop the placement test? What you have proven so far is kept.');
  const title = (OV.courses.find((c) => c.id === course) || {}).title || '';
  const block = (b) => {
    const qs = b.questions; const answers = qs.map(() => null); let cur = 0; let sending = false;
    const draw = () => {
      const q = qs[cur];
      view.innerHTML = `<div class="session"><div class="top"><button aria-label="Stop the test" id="pl-exit">✕</button>
          <div class="bar azure"><i style="width:${Math.round(100 * b.unit / b.units)}%"></i></div><span class="dim small num">unit ${b.unit + 1}/${b.units}</span></div>
        <div class="ex"><div class="guide">${guide('think')}<div class="speech">${esc(b.unit_title)}: ${esc(q.ask || '')}</div></div>
          ${questionHtml(q, answers[cur], 'pl')}
          <div class="foot"><div class="row"><button class="btn grow" id="pl-idk">I don't know</button><button class="btn primary big grow" id="pl-next">Next</button></div></div></div></div>`;
      $('#pl-exit').onclick = async () => { if (await leaveGuard()) { over = true; leaveGuard = null; document.body.classList.remove('in-session'); (done || (() => go('/library', false)))(); } };
      const read = bindQuestion(q, answers[cur], (v) => { answers[cur] = v; });
      const advance = async (skip) => {
        if (sending) return;                       // a double tap must not answer the next block
        answers[cur] = skip ? null : read();
        if (cur < qs.length - 1) { cur += 1; draw(); return; }
        sending = true;
        const res = await api('/api/placement/answer', { placement: first.placement, unit: b.unit, answers });
        sending = false;
        if (res.ok === false) { toast(res.error); return; }
        if (!res.done) { block(res); return; }
        over = true; leaveGuard = null; document.body.classList.remove('in-session');
        await refresh();
        view.innerHTML = `<div class="session summary">${guide(res.passed_units ? 'happy' : 'calm', 96)}<h1>${res.passed_units ? 'Your level is found' : 'You start at the beginning'}</h1>
          <p class="dim">${esc(title)}</p>
          <div class="gains"><div><b class="num">${num(res.passed_units)}/${num(res.units)}</b><span>units known</span></div><div><b class="num">${num(res.placed)}</b><span>items skipped</span></div>
            <div><b class="num">${num(res.right)}/${num(res.asked)}</b><span>answered right</span></div></div>
          <p>${res.start_at ? `You will start at <b>${esc(res.start_at)}</b>.` : 'You tested out of the whole course. It will come back as reviews.'}
            ${res.placed ? ' The items you skipped return for a quick check over the next two weeks.' : ''}</p>
          <div class="foot"><button class="btn primary big" id="pl-done">Continue</button></div></div>`;
        $('#pl-done').onclick = () => (done || (() => go('/library', false)))();
      };
      $('#pl-next').onclick = () => advance(false);
      $('#pl-idk').onclick = () => advance(true);
    };
    draw();
  };
  block(first);
}

/* A question with no feedback (placement, trials): text box, single choice, choose-N or put-in-order. */
function questionHtml(q, value, idp) {
  const long = (q.prompt || '').length > 90;
  const head = `<div class="prompt ${long ? 'long' : ''} ${q.big ? 'big' : ''}" lang="${esc(q.lang || '')}">${esc(q.prompt || '')}</div>${q.rom ? `<div class="rom">${esc(q.rom)}</div>` : ''}${q.sub ? `<div class="sub">${esc(q.sub)}</div>` : ''}`;
  if (q.mode === 'order') {
    const picked = Array.isArray(value) ? value : [];
    return `${head}<p class="dim small">Tap the steps in the order they happen. Tap a numbered step to take it back.</p>
      <div class="opts">${q.steps.map((c, i) => { const at = picked.indexOf(c); return `<button class="opt ${at >= 0 ? 'picked' : ''}" data-step="${i}"><kbd>${at >= 0 ? at + 1 : ''}</kbd><span>${esc(c)}</span></button>`; }).join('')}</div>`;
  }
  if (q.mode === 'multi') {
    const picked = Array.isArray(value) ? value : [];
    return `${head}<p class="dim small">Choose ${num(q.pick)}.</p>
      <div class="opts">${q.choices.map((c, i) => `<button class="opt ${picked.includes(c) ? 'picked' : ''}" data-multi="${i}"><kbd>${picked.includes(c) ? '✓' : ''}</kbd><span>${esc(c)}</span></button>`).join('')}</div>`;
  }
  if (TYPED.has(q.mode)) {
    const accents = ACCENTS[(q.lang || '').slice(0, 2)] || [];
    return `${head}<div class="typed"><input type="text" id="${idp}-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" value="${esc(typeof value === 'string' ? value : '')}" aria-label="Your answer">
      ${accents.length ? `<div class="accents">${accents.map((a) => `<button type="button" data-acc="${a}" tabindex="-1">${a}</button>`).join('')}</div>` : ''}</div>`;
  }
  return `${head}<div class="opts">${q.choices.map((c, i) => `<button class="opt ${value === c ? 'picked' : ''}" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(c)}</span></button>`).join('')}</div>`;
}

/* Wire a questionHtml() block; returns a function that reads the current answer. */
function bindQuestion(q, value, onChange) {
  let cur = Array.isArray(value) ? value.slice() : value;
  const repaint = (sel, isOn, label) => view.querySelectorAll(sel).forEach((b) => {
    const text = b.querySelector('span').textContent; b.classList.toggle('picked', isOn(text)); b.querySelector('kbd').textContent = label(text);
  });
  if (q.mode === 'order' || q.mode === 'multi') {
    cur = Array.isArray(cur) ? cur : [];
    const sel = q.mode === 'order' ? '[data-step]' : '[data-multi]';
    view.querySelectorAll(sel).forEach((b) => {
      b.onclick = () => {
        const text = b.querySelector('span').textContent;
        if (cur.includes(text)) cur = cur.filter((x) => x !== text);
        else if (q.mode === 'order' || cur.length < num(q.pick)) cur.push(text);
        repaint(sel, (t) => cur.includes(t), (t) => (q.mode === 'order' ? (cur.indexOf(t) >= 0 ? cur.indexOf(t) + 1 : '') : (cur.includes(t) ? '✓' : '')));
        onChange(cur.length ? cur.slice() : null);
      };
    });
    return () => (cur.length ? cur.slice() : null);
  }
  const inp = view.querySelector('.typed input');
  if (inp) {
    inp.focus();
    inp.oninput = () => onChange(inp.value.trim() || null);
    view.querySelectorAll('[data-acc]').forEach((b) => {
      b.onclick = () => { const at = inp.selectionStart ?? inp.value.length; inp.value = inp.value.slice(0, at) + b.dataset.acc + inp.value.slice(inp.selectionEnd ?? at); inp.focus(); inp.setSelectionRange(at + 1, at + 1); onChange(inp.value.trim() || null); };
    });
    return () => inp.value.trim() || null;
  }
  view.querySelectorAll('.opt[data-i]').forEach((b) => {
    b.onclick = () => { cur = q.choices[+b.dataset.i]; view.querySelectorAll('.opt[data-i]').forEach((o) => o.classList.toggle('picked', o === b)); onChange(cur); };
  });
  return () => cur || null;
}

/* ================= study session ================= */
const ACCENTS = { fr: 'é è ê à ç ù â î ô û ë ï œ'.split(' '), es: 'á é í ó ú ñ ü ¿ ¡'.split(' '),
  zh: 'ā á ǎ à ē é ě è ī í ǐ ì ō ó ǒ ò ū ú ǔ ù ǖ ǘ ǚ ǜ'.split(' '), ja: 'ā ī ū ē ō'.split(' ') };
const TYPED = new Set(['type_l2', 'listen', 'cloze_type', 'build_l2', 'glyph_type']);
const TILES = new Set(['build_l2']);

async function renderStudy(params) {
  const practice = params && params.get('practice') === '1';
  const course = (params && params.get('course')) || '';
  view.innerHTML = '<p class="loading">Preparing your session…</p>';
  const kind = params && ['mistakes', 'listen'].includes(params.get('kind')) ? params.get('kind') : '';
  const s = await api('/api/session', { course, practice, kind });
  if (!s.exercises || !s.exercises.length) {
    const t = OV.today;
    view.innerHTML = `<div class="panel summary" style="max-width:560px;margin:8vh auto"><h1>${kind ? 'Nothing here yet' : practice ? 'Nothing to practice yet' : 'Nothing is due'}</h1>
      <p class="dim">${kind ? esc(s.error || '') : practice ? 'Practice draws on items you have already learned. Finish a first session and come back.'
        : (t.sessions ? 'You have finished today\'s reviews and new items. They will return when your memory needs them.' : 'There is nothing scheduled right now.')}</p>
      <div class="row" style="justify-content:center;margin-top:16px">
        ${!practice && OV.courses.some((c) => c.seen > 0) ? '<a class="btn" href="/study?practice=1" data-link>Practice weak items</a>' : ''}
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
  const st = { done: 0, first: 0, correct: 0, qi: 0, insight: 0, start: Date.now(), events: [], finished: false };
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
    let res = await api('/api/session/finish', body);
    if (res.ok === false) res = await api('/api/session/finish', body);      // one retry on a dropped connection
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
      <div class="gains"><div><b class="num">${acc}%</b><span>first try</span></div><div><b class="num">+${num(st.qi)}</b><span>qi</span></div><div><b class="num">+${num(st.insight)}</b><span>insight</span></div></div>
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
    else body = `<div class="l2 ${c.type === 'glyph' ? 'prompt big' : ''}" lang="${esc(lang)}">${esc(c.l2)} ${sayBtn(c.l2, lang)}</div>${c.rom ? `<div class="rom">${esc(c.rom)}</div>` : ''}<div class="l1">${esc(c.l1 || '')}</div>
      ${c.ex ? `<div class="exm"><div lang="${esc(lang)}">${esc(c.ex)} ${sayBtn(c.ex, lang)}</div>${c.ex_rom ? `<div class="rom">${esc(c.ex_rom)}</div>` : ''}<div class="dim">${esc(c.ex_l1 || '')}</div></div>` : ''}`;
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

  // "Choose TWO" and "put these in order": build the answer, then check it.
  function listExercise(ex) {
    let locked = false;
    shell(`<div class="guide">${guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || '')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>
      ${questionHtml(ex, null, 's')}<div class="foot" id="s-foot"><button class="btn primary big" id="s-check">Check</button></div>`);
    const read = bindQuestion(ex, null, () => {});
    keyHandler = null;
    $('#s-check').onclick = async () => {
      const given = read();
      if (locked || !given || (ex.mode === 'multi' && given.length !== num(ex.pick)) || (ex.mode === 'order' && given.length !== ex.steps.length)) {
        if (!locked) toast(ex.mode === 'multi' ? `Choose ${num(ex.pick)}.` : 'Place every step first.');
        return;
      }
      locked = true;
      const res = await api('/api/answer', { session: s.session, item: ex.item, mode: ex.mode, answer: given, retry: !!ex.retry });
      if (res.ok === false) { locked = false; toast(res.error); return; }
      if (!ex.retry) {
        st.first += 1; st.correct += res.correct ? 1 : 0; st.qi += (res.rewards && res.rewards.qi) || 0; st.insight += (res.rewards && res.rewards.insight) || 0;
        if (res.rewards && res.rewards.events && res.rewards.events.length) { st.events.push(...res.rewards.events); showEvents(res.rewards.events); }
      }
      if (res.correct) st.done += 1; else queue.splice(Math.min(3, queue.length), 0, { ...ex, retry: true });
      const want = res.expected_list || [];
      view.querySelectorAll('.opt').forEach((o) => {
        o.disabled = true; const text = o.querySelector('span').textContent;
        if (ex.mode === 'multi') { if (want.includes(text)) o.classList.add('right'); else if (given.includes(text)) o.classList.add('wrong'); o.classList.remove('picked'); }
        else { const ok = want.indexOf(text) === given.indexOf(text); o.classList.remove('picked'); o.classList.add(ok ? 'right' : 'wrong'); o.querySelector('kbd').textContent = want.indexOf(text) + 1; }
      });
      feedback(ex, res, given);
    };
  }

  // Sentence tiles: tap words into order. Returns {html, bind(onReady) -> read()}.
  function tiles(bank) {
    const html = `<div class="built" id="s-built" aria-label="Your sentence"></div><div class="bank" id="s-bank">${bank.map((w, i) => `<button class="tile" data-t="${i}">${esc(w)}</button>`).join('')}</div>`;
    const bind = () => {
      const picked = [];
      const paint = () => {
        $('#s-built').innerHTML = picked.map((i, k) => `<button class="tile on" data-k="${k}">${esc(bank[i])}</button>`).join('') || '<span class="dim">Tap the words in order</span>';
        view.querySelectorAll('#s-bank .tile').forEach((b) => { b.disabled = picked.includes(+b.dataset.t); });
        view.querySelectorAll('#s-built .tile').forEach((b) => { b.onclick = () => { picked.splice(+b.dataset.k, 1); paint(); }; });
      };
      view.querySelectorAll('#s-bank .tile').forEach((b) => { b.onclick = () => { picked.push(+b.dataset.t); paint(); }; });
      paint();
      return () => picked.map((i) => bank[i]).join(' ');
    };
    return { html, bind };
  }

  // A conversation: the partner speaks, you answer line by line, then the whole exchange is graded.
  function dialogue(ex) {
    const build = ex.mode === 'dialogue_build';
    const mine = ex.lines.filter((l) => l.mine);
    const given = []; const marks = [];
    let at = 0;                                   // index into ex.lines
    const log = [];                               // rendered bubbles so far
    const bubble = (who, l2, l1, cls = '', rom = '') => `<div class="say ${who === 'me' ? 'me' : 'them'} ${cls}"><div class="l2" lang="${esc(ex.lang)}">${esc(l2)}</div>${rom ? `<div class="rom">${esc(rom)}</div>` : ''}<div class="l1">${esc(l1)}</div></div>`;
    const step = () => {
      while (at < ex.lines.length && !ex.lines[at].mine) {
        const ln = ex.lines[at]; log.push(bubble('them', ln.l2, ln.l1, '', ln.rom)); speak(ln.l2, ex.lang); at += 1;
      }
      if (at >= ex.lines.length) return finishDialogue();
      const ln = ex.lines[at];
      const t = build ? tiles(ln.bank) : null;
      const accents = ACCENTS[(ex.lang || '').slice(0, 2)] || [];
      shell(`<div class="guide">${guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.title)}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>
        <p class="dim small" style="margin:-6px 0 10px">${esc(ex.scene)}</p>
        <div class="chat">${log.join('')}<div class="say me cue"><div class="l1">Say: ${esc(ln.l1)}</div></div></div>
        ${build ? t.html : `<div class="typed"><input type="text" id="s-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" lang="${esc(ex.lang)}" aria-label="Your reply" enterkeyhint="done">
          ${accents.length ? `<div class="accents">${accents.map((a) => `<button type="button" data-acc="${a}" tabindex="-1">${a}</button>`).join('')}</div>` : ''}</div>`}
        <div class="foot" id="s-foot"><button class="btn primary big" id="s-check">Reply</button></div>`);
      const chat = view.querySelector('.chat'); chat.scrollTop = chat.scrollHeight;
      let read;
      if (build) read = t.bind();
      else {
        const inp = $('#s-in'); inp.focus(); read = () => inp.value;
        inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); $('#s-check').click(); } };
        view.querySelectorAll('[data-acc]').forEach((b) => { b.onclick = () => { const p = inp.selectionStart ?? inp.value.length; inp.value = inp.value.slice(0, p) + b.dataset.acc + inp.value.slice(inp.selectionEnd ?? p); inp.focus(); inp.setSelectionRange(p + 1, p + 1); }; });
      }
      let locked = false;
      $('#s-check').onclick = async () => {
        const said = read().trim();
        if (locked || !said) return;
        locked = true;
        const res = await api('/api/line', { item: ex.item, index: ln.index, answer: said });
        if (res.ok === false) { locked = false; toast(res.error); return; }
        given.push(said); marks.push(!!res.correct);
        log.push(bubble('me', res.l2 || res.expected, ln.l1, res.correct ? 'ok' : 'no', res.rom));
        speak(res.expected, ex.lang);
        $('#s-foot').innerHTML = `<div class="verdict ${res.correct ? 'ok' : 'no'}" role="status">${guide(res.correct ? 'happy' : 'oops', 52)}<div class="grow">
            <h3>${res.correct ? (res.flag ? 'Right, with a small slip' : 'Good') : 'A native speaker would say'}</h3><div class="ans" lang="${esc(ex.lang)}">${esc(res.l2 || res.expected)}</div>${res.rom ? `<div class="rom">${esc(res.rom)}</div>` : ''}
            ${res.correct ? '' : `<p class="dim small">You said: ${esc(said)}</p>`}<p class="dim small">Now say it aloud.</p></div></div>
          <button class="btn ${res.correct ? 'primary' : 'seal'} big" id="s-next">Continue</button>`;
        const b = $('#s-next'); b.focus(); b.onclick = () => { at += 1; step(); };
      };
      keyHandler = null;
    };
    const finishDialogue = async () => {
      const res = await api('/api/answer', { session: s.session, item: ex.item, mode: ex.mode, answer: given, retry: !!ex.retry });
      if (res.ok === false) { toast(res.error); return; }
      if (!ex.retry) {
        st.first += 1; st.correct += res.correct ? 1 : 0; st.qi += (res.rewards && res.rewards.qi) || 0; st.insight += (res.rewards && res.rewards.insight) || 0;
        if (res.rewards && res.rewards.events && res.rewards.events.length) { st.events.push(...res.rewards.events); showEvents(res.rewards.events); }
      }
      if (res.correct) st.done += 1; else queue.splice(Math.min(3, queue.length), 0, { ...ex, retry: true });
      const right = marks.filter(Boolean).length;
      shell(`<div class="guide">${guide(res.correct ? 'happy' : 'think')}<div class="speech">${res.correct ? (right === mine.length ? 'That conversation went well.' : 'You got through it. A few lines to polish.') : 'Let us run that conversation again.'}</div></div>
        <div class="chat full">${(res.explain.dialogue || []).map((l) => bubble(l.mine ? 'me' : 'them', l.l2, l.l1, '', l.rom)).join('')}</div>
        <p class="dim small">${right} of ${mine.length} of your lines were right${!ex.retry && res.next_days != null ? (num(res.next_days) <= 0 ? '. It returns later in this session.' : `. Next rehearsal in ${num(res.next_days)} day${num(res.next_days) === 1 ? '' : 's'}.`) : '.'}</p>
        <div class="foot"><button class="btn primary big" id="s-next">Continue</button></div>`);
      const b = $('#s-next'); b.onclick = next; b.focus();
    };
    step();
  }

  function exercise(ex) {
    if (ex.mode === 'multi' || ex.mode === 'order') return listExercise(ex);
    if (ex.mode === 'dialogue_build' || ex.mode === 'dialogue_type') return dialogue(ex);
    const lang = ex.lang; const typed = TYPED.has(ex.mode);
    const long = (ex.prompt || '').length > 90;
    let top;
    if (ex.mode === 'listen') top = `<div style="text-align:center">${sayBtn(ex.say, lang, 'huge')}<p class="dim small">Tap to hear it again. <button class="btn quiet" id="s-mute" style="min-height:32px;padding:0 8px">I can't listen now</button></p></div>`;
    else top = `<div class="prompt ${long ? 'long' : ''} ${ex.big ? 'big' : ''}" lang="${esc(lang)}">${esc(ex.prompt)} ${ex.say ? sayBtn(ex.say, lang) : ''}</div>${ex.rom ? `<div class="rom">${esc(ex.rom)}</div>` : ''}${ex.sub ? `<div class="sub">${esc(ex.sub)}</div>` : ''}`;
    const tile = TILES.has(ex.mode) ? tiles(ex.bank) : null;
    const accents = typed && !tile ? (ACCENTS[(lang || '').slice(0, 2)] || []) : [];
    const input = tile ? tile.html : typed ? `<div class="typed"><input type="text" id="s-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" lang="${esc(lang)}" aria-label="Your answer" enterkeyhint="done">
        ${accents.length ? `<div class="accents">${accents.map((a) => `<button type="button" data-acc="${a}" tabindex="-1">${a}</button>`).join('')}</div>` : ''}</div>`
      : `<div class="opts">${ex.choices.map((c, i) => `<button class="opt" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(c)}</span></button>`).join('')}</div>`;
    shell(`<div class="guide">${guide(ex.retry ? 'think' : 'calm')}<div class="speech">${esc(ex.ask || '')}${ex.retry ? ' <span class="tag gold">once more</span>' : ''}</div></div>${top}${input}
      <div class="foot" id="s-foot">${typed ? '<button class="btn primary big" id="s-check">Check</button>' : ''}</div>`);
    bindSay();
    if (ex.say && ex.mode !== 'choose_l2') speak(ex.say, lang);
    let locked = false;
    const submit = async (given, btn) => {
      if (locked) return; locked = true;
      const res = await api('/api/answer', { session: s.session, item: ex.item, mode: ex.mode, answer: given, retry: !!ex.retry, claim: !!ex.claim });
      if (res.ok === false) { locked = false; toast(res.error); return; }
      if (!ex.retry) {
        st.first += 1; st.correct += res.correct ? 1 : 0; st.qi += (res.rewards && res.rewards.qi) || 0; st.insight += (res.rewards && res.rewards.insight) || 0;
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
    if (tile) {
      const read = tile.bind();
      $('#s-check').onclick = () => { if (read().trim()) { view.querySelectorAll('.tile').forEach((b) => { b.disabled = true; }); submit(read()); } };
    } else if (typed) {
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
    const flag = res.flag === 'tone' ? 'Right — but mind the tones.' : res.flag === 'accent' ? 'Right — mind the accents.' : res.flag === 'typo' ? 'Right — with a small slip.' : 'Correct';
    const when = !ex.retry && !s.practice && res.next_days != null ? (num(res.next_days) <= 0 ? 'It returns later in this session.' : `Next review in ${num(res.next_days)} day${num(res.next_days) === 1 ? '' : 's'}.`) : '';
    let detail;
    if (x.whys) {
      // Best-answer questions: say under each option why it is best or why it is weaker.
      view.querySelectorAll('.opt').forEach((o) => {
        const text = ex.choices[+o.dataset.i]; const why = x.whys[text];
        if (why && !o.querySelector('.whyopt')) { const d = document.createElement('small'); d.className = 'whyopt'; d.textContent = why; o.querySelector('span').appendChild(d); }
      });
    }
    if (x.why) detail = `<p>${esc(x.why)}</p>`;
    else {
      // Show the pair once: the target-language form, then its meaning.
      const pair = x.l2 ? `<div class="ans" lang="${esc(ex.lang)}">${esc(x.l2)}</div>${x.rom ? `<div class="rom">${esc(x.rom)}</div>` : ''}${x.l1 ? `<p class="dim">${esc(x.l1)}</p>` : ''}` : '';
      const typedWrong = TYPED.has(ex.mode) && (!res.correct || res.flag) && res.expected !== x.l2 ? `<p>Answer: <b>${esc(res.expected)}</b></p>` : '';
      detail = `${pair}${typedWrong}${x.note ? `<p class="dim small">${esc(x.note)}</p>` : ''}`;
    }
    const showExpected = x.why && !res.correct && ex.mode !== 'order';
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
  const HUE = { tongues_west: ['#5bb6ff', 'Fr'], tongues_south: ['#ff8a5c', 'Es'], ward_hall: ['#2fd39a', 'Sec'] };
  const card = (c) => {
    const [hue, mark] = HUE[c.hall] || ['#a78bfa', '·'];
    const cur = c.units.find((u) => u.unlocked && !u.done);
    return `<section class="panel course">
    <header><span class="crest" style="background:${hue};color:#10233f" aria-hidden="true">${c.hall === 'ward_hall' ? esc((c.exam && c.exam.code || 'Sec').slice(0, 3)) : mark}</span>
      <div class="grow"><h2>${esc(c.title)}</h2><p class="dim small" style="margin:2px 0 0">${esc(c.blurb)}</p></div>
      ${c.enrolled ? `<span class="tag jade">Enrolled</span>` : `<button class="btn primary" data-enroll="${esc(c.id)}">Begin this course</button>`}</header>
    ${c.enrolled ? `<div class="row small"><span class="grow dim">${c.seen} of ${c.total} learned · ${c.mastered} mastered · memory ${c.strength}%</span></div>
      <div class="bar jade" style="margin:6px 0 12px"><i style="width:${Math.round(100 * c.seen / Math.max(c.total, 1))}%"></i></div>
      <div class="row"><a class="btn primary" href="/study?course=${encodeURIComponent(c.id)}" data-link>Study this art <span class="num">${c.due + c.new_left}</span></a>
        ${c.seen < c.total ? `<button class="btn" data-more="${esc(c.id)}">Learn 5 more today</button>` : ''}
        ${c.seen < c.total ? `<button class="btn" data-place="${esc(c.id)}">${(OV.placements || {})[c.id] ? 'Retake the placement test' : 'Placement test'}</button>` : ''}
        <button class="btn quiet" data-drop="${esc(c.id)}">Set aside</button></div>` : ''}
    <details class="units" ${c.enrolled && mine.length <= 2 ? 'open' : ''}><summary>${c.units.length} units${c.enrolled ? `, ${c.units_done} finished` : ''}</summary>
    <div class="path">${c.units.map((u, i) => {
      const state = !c.enrolled ? '' : u.done ? 'done' : (cur && cur.id === u.id) ? 'now' : u.unlocked ? '' : 'locked';
      return `<button class="step ${state}" data-unit="${esc(u.id)}" data-course="${esc(c.id)}">
        <span class="node">${state === 'done' ? ICON.check : state === 'locked' ? ICON.lock : i + 1}</span>
        <span><b>${esc(u.title)}</b><span class="dim small">${esc(u.goal)}</span>
        ${c.enrolled && u.seen > 0 && !u.done ? `<span class="bar thin jade" style="display:block"><i style="width:${Math.round(100 * u.seen / u.items)}%"></i></span>` : ''}</span></button>`;
    }).join('')}</div></details>
  </section>`;
  };
  view.innerHTML = `<h1 style="margin-bottom:14px">Library</h1>${mine.map(card).join('')}
    ${rest.length ? `<h2 style="margin:22px 0 10px">Other arts you can take up</h2>${rest.map(card).join('')}` : ''}`;
  view.querySelectorAll('[data-unit]').forEach((b) => { b.onclick = () => go(`/library?course=${encodeURIComponent(b.dataset.course)}&unit=${encodeURIComponent(b.dataset.unit)}`); });
  view.querySelectorAll('[data-enroll]').forEach((b) => { b.onclick = async () => { await api('/api/enroll', { course: b.dataset.enroll, on: true }); await refresh(); offerPlacement([b.dataset.enroll]); }; });
  view.querySelectorAll('[data-place]').forEach((b) => { b.onclick = () => runPlacement(b.dataset.place, () => go('/library', false)); });
  view.querySelectorAll('[data-drop]').forEach((b) => { b.onclick = async () => { if (!confirm('Set this art aside? Your progress is kept, and you can take it up again any time.')) return; await api('/api/enroll', { course: b.dataset.drop, on: false }); go('/library', false); }; });
  view.querySelectorAll('[data-more]').forEach((b) => { b.onclick = async () => { const r = await api('/api/learn-more', { course: b.dataset.more, n: 5 }); if (r.ok !== false) { toast('5 more new items added to today.'); go(`/study?course=${encodeURIComponent(b.dataset.more)}`); } else toast(r.error); }; });
}

async function renderUnit(cid, uid) {
  view.innerHTML = '<p class="loading">Unrolling the scroll…</p>';
  const u = await api(`/api/unit?course=${encodeURIComponent(cid)}&unit=${encodeURIComponent(uid)}`);
  if (u.ok === false) { view.innerHTML = `<div class="panel"><p>${esc(u.error)}</p><a class="btn" href="/library" data-link>Back to the library</a></div>`; return; }
  const lang = u.lang;
  const row = (it) => {
    let a, b;
    if (it.type === 'concept') { a = esc(it.term); b = esc(it.def); }
    else if (it.type === 'mcq' || it.type === 'multi' || it.type === 'order') { a = esc(it.q); b = `<span class="dim">${esc(it.correct)}.</span> ${esc(it.why || '')}`; }
    else if (it.type === 'dialogue') { a = `<b>${esc(it.title)}</b>`; b = esc(it.scene || ''); }
    else if (it.type === 'cloze') { const full = it.full; a = `${esc(full)} ${canSpeak(lang) ? `<button class="say tiny" data-say="${esc(full)}" aria-label="Play audio">${ICON.sound}</button>` : ''}`; b = esc(it.l1 || ''); }
    else if (it.type === 'glyph') { a = `<span class="glyph" lang="${esc(lang)}">${esc(it.l2)}</span> ${canSpeak(lang) ? `<button class="say tiny" data-say="${esc(it.l2)}" aria-label="Play audio">${ICON.sound}</button>` : ''}`; b = `${esc(it.rom)}${it.l1 ? ` <span class="dim small">${esc(it.l1)}</span>` : ''}`; }
    else { a = `<span lang="${esc(lang)}">${esc(it.l2)}</span>${it.rom ? ` <span class="rom">${esc(it.rom)}</span>` : ''} ${canSpeak(lang) ? `<button class="say tiny" data-say="${esc(it.l2)}" aria-label="Play audio">${ICON.sound}</button>` : ''}`; b = `${esc(it.l1)}${it.note ? `<br><span class="dim small">${esc(it.note)}</span>` : ''}`; }
    const hide = (it.type === 'mcq' || it.type === 'multi' || it.type === 'order') && it.state === 'new';
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
  const infos = await Promise.all(mine.map((c) => api(`/api/trial?course=${encodeURIComponent(c.id)}`)));
  view.innerHTML = `<h1>Trials</h1><p class="dim" style="max-width:68ch">A trial is a timed test with no hints and no feedback until the end. The pass mark here is set above the real exam's, and the questions are harder, so that passing here means something. Passing lifts the whole sect; anything you get wrong that you have studied goes back into your review queue.</p>
    ${infos.map((t, i) => (t.ok === false ? '' : `<section class="panel"><div class="row"><div class="grow"><h2>${esc(t.name)}</h2>
        <p class="dim small" style="margin:2px 0 0">${num(t.questions)} questions, ${num(t.minutes)} minutes, ${num(t.pass_pct)}% to pass${t.best != null ? `. Your best: ${num(t.best)}%` : ''}</p></div>
        <button class="btn seal" data-trial="${esc(mine[i].id)}" ${t.ready ? '' : 'disabled'}>Quick trial</button>
        ${t.full ? `<button class="btn" data-full="${esc(mine[i].id)}">Full mock: ${num(t.full.questions)} questions, ${num(t.full.minutes)} min</button>` : ''}</div>
        ${t.need ? `<p class="dim small" style="margin:8px 0 0">${esc(t.need)}</p>` : ''}
        ${mine[i].exam ? `<p class="dim small" style="margin:8px 0 0">Modelled on ${esc(mine[i].exam.name)} ${esc(mine[i].exam.code)}: questions are drawn across the official domains by their exam weights, including choose-two and put-in-order questions.</p>` : ''}
        ${t.readiness ? `<div class="ready ${t.readiness.ready ? 'yes' : ''}"><b>${t.readiness.ready ? 'You are ready to book the real exam.' : 'Ready for the real exam when all four are ticked:'}</b>
          <ul class="list">${t.readiness.checks.map((c) => `<li class="quest ${c.ok ? 'done' : ''}"><span class="mark">${c.ok ? ICON.check : ''}</span><span class="grow">${esc(c.label)}</span><span class="dim small">${esc(c.detail)}</span></li>`).join('')}</ul></div>` : ''}
        ${t.weak && t.weak.length ? `<p class="small" style="margin:8px 0 0"><b>Where the marks are going</b> (last three trials): ${t.weak.map((w) => `${esc(w.title)} <span class="tag ${num(w.pct) >= num(t.pass_pct) ? 'jade' : 'red'}">${num(w.pct)}%</span>`).join(' · ')}</p>` : ''}
        ${t.history.length ? `<ul class="list small" style="margin-top:8px">${t.history.slice().reverse().slice(0, 5).map((h) => `<li><span class="tag ${h.passed ? 'jade' : 'red'}">${h.passed ? 'Passed' : 'Failed'}</span> ${num(h.pct)}% (${num(h.right)}/${num(h.total)})${h.full ? ' full mock' : ''} <span class="dim">${ago(num(h.ts))} ago</span></li>`).join('')}</ul>` : ''}
      </section>`)).join('') || '<div class="panel dim">Enrol in a course to unlock its trial.</div>'}`;
  if (mine.some((c) => c.kind === 'cert')) {
    const best = (k) => (OV.drills && OV.drills[k] ? ` <span class="dim small">best ${num(OV.drills[k].best)}%, ${num(OV.drills[k].runs)} run${num(OV.drills[k].runs) === 1 ? '' : 's'}</span>` : '');
    view.insertAdjacentHTML('beforeend', `<section class="panel"><h2>Drills</h2><p class="dim small">Ten fresh questions made on the spot, with the working shown. Speed at these comes only from doing a great many.</p>
      <div class="row"><button class="btn" data-drill="subnet">Subnetting</button>${best('subnet')}<button class="btn" data-drill="ports">Ports and protocols</button>${best('ports')}</div></section>`);
    view.querySelectorAll('[data-drill]').forEach((b) => { b.onclick = () => runDrill(b.dataset.drill); });
  }
  if (OV.mistakes) view.insertAdjacentHTML('beforeend', `<section class="panel"><h2>Missed questions</h2><p class="dim small">${num(OV.mistakes)} question${num(OV.mistakes) === 1 ? '' : 's'} you got wrong, in sessions or trials, and have not yet put right.</p>
    <a class="btn primary" href="/study?kind=mistakes" data-link>Work through them</a></section>`);
  view.querySelectorAll('[data-trial]').forEach((b) => { b.onclick = () => startTrial(b.dataset.trial, false); });
  view.querySelectorAll('[data-full]').forEach((b) => { b.onclick = () => startTrial(b.dataset.full, true); });
}

async function runDrill(kind) {
  const d = await api('/api/drill', { kind });
  if (d.ok === false) { toast(d.error); return; }
  document.body.classList.add('in-session');
  leaveGuard = null;
  let cur = 0; let score = 0;
  const done = () => {
    document.body.classList.remove('in-session');
    view.innerHTML = `<div class="session summary">${guide(score >= 8 ? 'happy' : 'calm', 96)}<h1>${esc(d.name)}: ${score}/${d.questions.length}</h1>
      <p class="dim">${score === d.questions.length ? 'Clean. Do it again tomorrow, faster.' : 'Read the working on the ones you missed, then go again.'}</p>
      <div class="foot"><div class="row"><button class="btn grow" id="d-again">Another ten</button><a class="btn primary grow" href="/trials" data-link>Done</a></div></div></div>`;
    $('#d-again').onclick = () => runDrill(kind);
    refresh();
  };
  const draw = () => {
    const q = d.questions[cur];
    view.innerHTML = `<div class="session"><div class="top"><button aria-label="Stop the drill" id="d-exit">✕</button><div class="bar azure"><i style="width:${Math.round(100 * cur / d.questions.length)}%"></i></div><span class="dim small num">${cur + 1}/${d.questions.length}</span></div>
      <div class="ex"><p class="ask">${esc(d.name)}</p><h2 class="prompt">${esc(q.q)}</h2>
      ${q.choices ? `<div class="opts">${q.choices.map((c, i) => `<button class="opt" data-c="${i}"><span>${esc(c)}</span></button>`).join('')}</div>`
        : '<div class="typed"><input type="text" id="d-in" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" inputmode="text" aria-label="Your answer" enterkeyhint="done"></div>'}
      <div class="foot" id="d-foot">${q.choices ? '' : '<button class="btn primary big" id="d-check">Check</button>'}</div></div></div>`;
    $('#d-exit').onclick = () => { document.body.classList.remove('in-session'); go('/trials', false); };
    let locked = false;
    const send = async (val) => {
      if (locked || !String(val).trim()) return; locked = true;
      const res = await api('/api/drill/answer', { drill: d.drill, n: q.n, answer: String(val) });
      if (res.ok === false) { toast(res.error); locked = false; return; }
      if (res.correct) score += 1;
      view.querySelectorAll('.opt').forEach((o) => { o.disabled = true; if (q.choices[+o.dataset.c] === res.expected) o.classList.add('right'); else if (q.choices[+o.dataset.c] === val) o.classList.add('wrong'); });
      $('#d-foot').innerHTML = `<div class="verdict ${res.correct ? 'ok' : 'no'}" role="status">${guide(res.correct ? 'happy' : 'oops', 52)}<div class="grow"><h3>${res.correct ? 'Right' : 'Not quite'}</h3>
        <div class="ans">${esc(res.expected)}</div><p class="small">${esc(res.why)}</p></div></div><button class="btn ${res.correct ? 'primary' : 'seal'} big" id="d-next">Continue</button>`;
      const b = $('#d-next'); b.focus(); b.onclick = () => { cur += 1; if (cur >= d.questions.length) done(); else draw(); };
    };
    if (q.choices) view.querySelectorAll('.opt').forEach((o) => { o.onclick = () => send(q.choices[+o.dataset.c]); });
    else { const inp = $('#d-in'); inp.focus(); inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); send(inp.value); } }; $('#d-check').onclick = () => send(inp.value); }
  };
  draw();
}

async function startTrial(course, full) {
  const t = await api('/api/trial/start', { course, full: !!full });
  if (t.ok === false) { toast(t.error); return; }
  document.body.classList.add('in-session');
  const qs = t.questions; const answers = qs.map(() => null); const flagged = new Set(); let cur = 0; let over = false; let sending = false;
  const deadline = Date.now() + num(t.minutes) * 60000;
  let timer = null;
  leaveGuard = async () => {
    if (over) return true;
    if (!confirm('Abandon this trial? Nothing will be recorded.')) return false;
    over = true; clearInterval(timer);                       // this trial's clock must never fire again
    api('/api/trial/abandon', { trial: t.trial });
    return true;
  };
  const draw = () => {
    const q = qs[cur]; const typed = TYPED.has(q.mode); const listq = q.mode === 'multi' || q.mode === 'order';
    view.innerHTML = `<div class="session"><div class="top"><b class="grow">${esc(t.name)}</b><span class="timer" id="t-clock"></span></div>
      <div class="ex"><p class="ask">Question ${cur + 1} of ${qs.length}. ${esc(q.ask || '')}</p>
      ${questionHtml(q, answers[cur], 't')}
      <p style="margin:10px 0 0"><button class="btn quiet" id="t-flag" aria-pressed="${flagged.has(cur)}">${flagged.has(cur) ? '⚑ Flagged for review (tap to clear)' : '⚐ Flag for review'}</button></p>
      <div class="qnav">${qs.map((_, i) => `<button class="${i === cur ? 'cur' : ''} ${answers[i] ? 'done' : ''} ${flagged.has(i) ? 'flag' : ''}" data-q="${i}" aria-label="Question ${i + 1}${flagged.has(i) ? ', flagged' : ''}${answers[i] ? '' : ', unanswered'}">${i + 1}</button>`).join('')}</div>
      <div class="foot"><div class="row"><button class="btn grow" id="t-prev" ${cur ? '' : 'disabled'}>Back</button>
        ${cur < qs.length - 1 ? '<button class="btn primary grow" id="t-next">Next</button>' : '<button class="btn seal grow" id="t-done">Submit trial</button>'}</div></div></div></div>`;
    const read = bindQuestion(q, answers[cur], (v) => {
      answers[cur] = v;
      if (!typed && !listq && v) { if (cur < qs.length - 1) move(cur + 1); else draw(); }
    });
    tick();
    const keep = () => { answers[cur] = read(); };
    function move(n) { keep(); cur = n; draw(); }
    view.querySelectorAll('[data-q]').forEach((b) => { b.onclick = () => move(+b.dataset.q); });
    const inp = $('#t-in');
    if (inp) inp.onkeydown = (e) => { if (e.key === 'Enter' && cur < qs.length - 1) move(cur + 1); };
    $('#t-flag').onclick = () => { keep(); if (flagged.has(cur)) flagged.delete(cur); else flagged.add(cur); draw(); };
    $('#t-prev').onclick = () => move(cur - 1);
    if ($('#t-next')) $('#t-next').onclick = () => move(cur + 1);
    if ($('#t-done')) $('#t-done').onclick = () => { keep(); const blank = answers.filter((a) => !a).length; const fl = flagged.size;
      const msg = [blank ? `${blank} unanswered` : '', fl ? `${fl} flagged for review` : ''].filter(Boolean).join(' and ');
      if (!msg || confirm(`You have ${msg}. Submit anyway?`)) submit(); else { const first = [...flagged].sort((a, b) => a - b)[0]; const b0 = answers.findIndex((a) => !a); move(first != null ? first : b0 >= 0 ? b0 : cur); } };
    keyHandler = (e) => { if (!typed && !listq && /^[1-4]$/.test(e.key)) { const o = view.querySelector(`.opt[data-i="${+e.key - 1}"]`); if (o) o.click(); } };
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
    const live = $('#t-in'); if (live) answers[cur] = live.value.trim() || null;
    const res = await api('/api/trial/submit', { trial: t.trial, answers });
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
      <div class="gains"><div><b class="num">${num(res.pct)}%</b><span>score</span></div><div><b class="num">${num(res.right)}/${num(res.total)}</b><span>correct</span></div><div><b class="num">${res.passed ? '✓' : '—'}</b><span>${res.passed ? 'the sect surges' : 'try again'}</span></div></div>
      ${res.domains.length > 1 ? `<section class="panel" style="text-align:left"><h2>By domain</h2>${res.domains.map((d) => `<div style="margin-top:10px"><div class="row small"><span class="grow">${esc(d.title)}</span><b class="num">${num(d.pct)}%</b></div>
        <div class="bar ${num(d.pct) >= num(res.pass_pct) ? 'jade' : ''}"><i style="width:${num(d.pct)}%"></i></div></div>`).join('')}</section>` : ''}
      ${misses.length ? `<section class="panel" style="text-align:left"><h2>What you missed</h2><ul class="list">${misses.map((m) => `<li><b>${esc(m.prompt)}</b>
        <div class="small"><span style="color:#ff9a8a">${m.given ? esc(m.given) : 'No answer'}</span> <span class="dim">should be</span> <span style="color:var(--jade)">${esc(m.expected)}</span></div>
        ${m.explain.whys && m.explain.whys[m.given] ? `<div class="small">Your choice: ${esc(m.explain.whys[m.given])}</div>` : ''}
        ${m.explain.why ? `<div class="dim small">${esc(m.explain.why)}</div>` : ''}</li>`).join('')}</ul></section>` : ''}
      <div class="row" style="justify-content:center;margin-top:16px"><a class="btn" href="/trials" data-link>Back to trials</a><a class="btn primary" href="/" data-link>Return to the sect</a></div></div>`;
    window.scrollTo(0, 0); refresh();
  };
  draw();
}

/* ================= progress ================= */
async function renderProgress() {
  view.innerHTML = '<p class="loading">Counting the days…</p>';
  const s = await api('/api/stats?days=119');
  if (s.ok === false) { view.innerHTML = `<div class="panel">${esc(s.error)}</div>`; return; }
  const set = OV.settings; const g = OV.sect;
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
    <section class="panel" id="mistakes-panel" hidden></section>
    <section class="panel"><h2>Settings</h2>
      <div class="setting"><div class="grow"><b>New items a day, per art</b><span>More items now means more reviews later. 8 is a steady pace.</span></div><input type="number" id="set-new" min="0" max="40" value="${set.new_per_day}"></div>
      <div class="setting"><div class="grow"><b>Session length</b><span>The number of exercises in one session.</span></div><input type="number" id="set-size" min="5" max="60" value="${set.session_size}"></div>
      <div class="setting"><div class="grow"><b>Target recall</b><span>How sure you want to be of remembering an item when it comes back. Higher means more reviews.</span></div>
        <select class="in" id="set-ret" style="width:110px">${[0.85, 0.9, 0.93].map((r) => `<option value="${r}" ${Math.abs(set.retention - r) < 0.005 ? 'selected' : ''}>${Math.round(r * 100)}%</option>`).join('')}</select></div>
      <div class="setting"><div class="grow"><b>Spoken audio</b><span>${synth ? 'Uses the voices installed on this device.' : 'This browser has no speech voices, so listening exercises become typing ones.'}</span></div>
        <input type="checkbox" id="set-audio" style="width:24px;height:24px;accent-color:var(--jade)" ${set.audio ? 'checked' : ''}></div>
      <div class="setting"><div class="grow"><b>Seclusion</b><span>Holiday mode: freezes your study streak and the sect until you return.</span></div>
        <button class="btn" id="set-sec">${g.seclusion ? 'Reopen the gates' : 'Enter seclusion'}</button></div>
      <div class="setting"><div class="grow"><b>Storyteller</b><span>How often trouble finds the sect.</span></div>
        <select class="in" id="set-tell" style="width:190px">${g.storytellers.map((t) => `<option value="${esc(t.id)}" ${t.id === g.storyteller ? 'selected' : ''}>${esc(t.name)}</option>`).join('')}</select></div>
      <div class="setting"><div class="grow"><b>Backup</b><span>Download everything (progress and sect) as one file, or restore from one.</span></div>
        <button class="btn" id="set-exp">Download backup</button><label class="btn">Restore<input type="file" id="set-imp" accept="application/json" hidden></label></div>
    </section>
    <p class="dim small" style="margin-top:18px">Everything runs on this device: no account, no internet, nothing sent anywhere.</p>`;
  const save = async (patch) => { const r = await api('/api/settings', patch, 'PUT'); if (r.ok === false) toast(r.error); else { Object.assign(OV.settings, r); toast('Saved.'); } };
  api('/api/mistakes').then((m) => {
    const el = $('#mistakes-panel'); if (!el || m.ok === false || !m.count) return;
    el.hidden = false;
    el.innerHTML = `<h2>Mistakes to put right <span class="tag red">${num(m.count)}</span></h2>
      <p class="dim small">Everything you answered wrong in a session or a trial stays here until you get it right. The number is how many times it still has to be answered correctly.</p>
      <ul class="list">${m.items.slice(0, 20).map((x) => `<li><b>${esc(x.prompt)}</b> <span class="tag red">×${num(x.n)}</span> <span class="dim small">${esc(x.course)}</span>
        <div class="small"><span style="color:#ff9a8a">${x.given ? esc(x.given) : 'No answer'}</span> <span class="dim">should be</span> <span style="color:var(--jade)">${esc(x.expected)}</span></div></li>`).join('')}</ul>
      <a class="btn primary" href="/study?kind=mistakes" data-link style="margin-top:10px">Work through them</a>`;
  });
  $('#set-new').onchange = (e) => save({ new_per_day: +e.target.value });
  $('#set-size').onchange = (e) => save({ session_size: +e.target.value });
  $('#set-ret').onchange = (e) => save({ retention: +e.target.value });
  $('#set-audio').onchange = (e) => save({ audio: e.target.checked });
  $('#set-sec').onclick = async () => { await api('/api/sect/seclusion', { on: !g.seclusion }); go('/progress', false); };
  $('#set-tell').onchange = async (e) => { await api('/api/sect/storyteller', { storyteller: e.target.value }); toast('Saved.'); };
  $('#set-exp').onclick = async () => {
    const data = await api('/api/export'); if (data.ok === false) { toast(data.error); return; }
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    a.download = `sect-academy-${esc(OV.today.day)}.json`; a.click(); URL.revokeObjectURL(a.href);
  };
  $('#set-imp').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    let data; try { data = JSON.parse(await f.text()); } catch (_) { toast('That file is not a Sect Academy backup.'); return; }
    if (!confirm('Replace all current progress with this backup?')) return;
    const r = await api('/api/import', data); if (r.ok === false) toast(r.error); else { toast('Backup restored.'); go('/', false); }
  };
}

// Offline shell: after the first visit the pages load even with the server stopped
// (study itself needs the local server, which holds your progress).
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});

go(location.pathname + location.search, false);
