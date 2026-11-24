// The sect screen: a colony sim you watch and steer. The server owns the simulation;
// this module draws it, sends orders, and asks for sim hours as real time passes.
// All text from the server goes through esc(); every number arrives already cast.

import { ICON, SITES, portrait, sectScene, siteRect } from '/art.js';

const SPEED_KEY = 'sect.speed';
const SECS_PER_HOUR = { 1: 4, 2: 2, 3: 1 };          // real seconds per sim hour
const RES_ICON = { rice: '🌾', wood: '🪵', stone: '🪨', herbs: '🌿', pills: '💊', stones: '💎' };
const SITE_OF = { farm: 'fields', quarry: 'spirit_vein', 'cut wood': 'storehouse', 'forage herbs': 'alchemy', 'brew pills': 'alchemy',
  research: 'library', train: 'training', meditate: 'meditation', sleeping: 'dormitory', recovering: 'dormitory' };

export function mountSect(h) {
  const { view, $, esc, api, toast, openSheet, closeSheet } = h;
  let S = h.sect();
  let tab = sessionStorage.getItem('sect.tab') || 'disciples';
  let speed = Number(localStorage.getItem(SPEED_KEY) || 1);
  let sceneSig = '';
  let timer = null;
  let busy = false;
  let owed = 0;

  const face = (p, size = 48, mood) => portrait(p.id + p.name, { root: p.root, size, mood: mood || (p.broken ? 'oops' : p.mood >= 65 ? 'happy' : 'calm') });
  const bar = (v, cls = '') => `<span class="bar thin ${cls}"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span>`;
  const moodCls = (m) => (m < 25 ? 'verm' : m < 45 ? '' : 'jade');
  const clock = () => `${String(S.hod).padStart(2, '0')}:00`;
  const costText = (c) => Object.entries(c).map(([k, v]) => `${v} ${k === 'stones' ? 'spirit stones' : k}`).join(', ');

  async function order(action, body = {}, quiet = false) {
    const res = await api(`/api/sect/${action}`, body);
    if (res.sect) { S = res.sect; h.setSect(S); }
    if (res.ok === false && !quiet) toast(res.error || 'That did not work.');
    else if (res.event && !quiet) toast(res.event.title);
    paint();
    return res;
  }

  /* ---------------- the clock ---------------- */
  function setSpeed(n) { speed = n; localStorage.setItem(SPEED_KEY, String(n)); owed = 0; paintTop(); }
  async function beat() {
    if (!view.isConnected || !$('#sect-root')) { stop(); return; }
    if (!speed || document.hidden || busy || S.pending || S.seclusion || !$('#sheet').hidden) return;
    owed += 1 / SECS_PER_HOUR[speed];
    const hours = Math.floor(owed);
    if (hours < 1) return;
    owed -= hours;
    busy = true;
    const before = S.log.length ? S.log[0].hour + S.log[0].title : '';
    const res = await api('/api/sect/tick', { hours });
    busy = false;
    if (res.sect) {
      S = res.sect; h.setSect(S);
      const top = S.log[0];
      if (top && top.hour + top.title !== before && top.hour > 0) toast(top.title, top.kind === 'bad' ? 6000 : 3500);
      paint();
    }
  }
  function stop() { if (timer) clearInterval(timer); timer = null; }

  /* ---------------- zones ---------------- */
  function paintTop() {
    const z = $('#z-top'); if (!z) return;
    const low = S.food_days < 3;
    z.innerHTML = `<header class="status">
        <h1>${esc(S.name)}<small>Day ${S.season_day} of ${esc(S.season)}, year ${S.year} · ${clock()}${S.seclusion ? ' · gates sealed' : ''}</small></h1>
        <span class="pill flame ${S.streak ? '' : 'off'}" title="Study streak. Best: ${S.best_streak}">${ICON.flame}${S.streak}</span>
        <span class="speed" role="group" aria-label="Game speed">
          <button class="${speed === 0 ? 'on' : ''}" data-speed="0" aria-label="Pause">${ICON.pause}</button>
          ${[1, 2, 3].map((n) => `<button class="${speed === n ? 'on' : ''}" data-speed="${n}" aria-label="Speed ${n}">${'▸'.repeat(n)}</button>`).join('')}
        </span>
      </header>
      <div class="resbar">${S.res.map((r) => `<span class="res ${r.id === 'rice' && low ? 'low' : ''}" title="${esc(r.name)}${r.cap ? ` (store holds ${r.cap})` : ''}">
          <span aria-hidden="true">${RES_ICON[r.id] || ''}</span><b class="num">${r.n}</b><small>${esc(r.name)}</small></span>`).join('')}
        <span class="res" title="Insight from your own study. It is spent on research automatically."><span aria-hidden="true">📜</span><b class="num">${S.insight}</b><small>Insight</small></span>
        <span class="res" title="How strong the sect's defence is"><span aria-hidden="true">🛡</span><b class="num">${S.defense}</b><small>Defence</small></span>
      </div>
      ${low ? `<p class="warn">Only ${S.food_days} day${S.food_days === 1 ? '' : 's'} of rice left. Put more disciples on farming in Work${S.season === 'Winter' ? ' — nothing grows in winter, so trade or wait for spring' : ''}.</p>` : ''}`;
    z.querySelectorAll('[data-speed]').forEach((b) => { b.onclick = () => setSpeed(Number(b.dataset.speed)); });
  }

  function paintEvent() {
    const z = $('#z-event'); if (!z) return;
    const ev = S.pending;
    z.innerHTML = ev ? `<section class="panel event"><h2>${esc(ev.title)}</h2><p>${esc(ev.text)}</p>
      <div class="row">${ev.options.map((o, i) => `<button class="btn ${i === 0 ? 'primary' : ''}" data-opt="${esc(o.id)}">${esc(o.label)}</button>`).join('')}</div>
      <p class="dim small" style="margin:8px 0 0">Time waits while they stand at the gate.</p></section>` : '';
    z.querySelectorAll('[data-opt]').forEach((b) => { b.onclick = () => order('resolve', { option: b.dataset.opt }); });
  }

  function paintScene() {
    const z = $('#z-scene'); if (!z) return;
    const building = S.builds.map((b) => b.room);
    const staff = {};
    S.pawns.forEach((p, i) => {
      const site = p.doing === 'build' ? building[0] : SITE_OF[p.doing] || 'main_hall';
      if (site) (staff[site] = staff[site] || []).push(i);
    });
    const sig = JSON.stringify([S.rooms.map((r) => r.level), building, staff, S.rooms.map((r) => r.affordable)]);
    if (sig === sceneSig && z.firstChild) return;      // keep the clouds drifting between ticks
    sceneSig = sig;
    const rooms = S.rooms.map((r) => {
      const [x, y, w, hh] = siteRect(r.id);
      return `<button class="room ${r.open ? '' : 'closed'}" data-room="${esc(r.id)}" style="left:${x}%;top:${y}%;width:${w}%;height:${hh}%"
        aria-label="${esc(r.name)}, ${r.open ? `level ${r.level}` : 'not built'}${r.affordable ? ', you can afford the next level' : ''}">
        ${r.affordable ? '<span class="can" aria-hidden="true">↑</span>' : ''}
        <span class="plaque">${esc(r.name)}${r.open ? `<em>${r.level}</em>` : ''}</span></button>`;
    }).join('');
    z.innerHTML = `<div class="hq">${sectScene(S.rooms, staff, building)}${rooms}</div>`;
    z.querySelectorAll('[data-room]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.room); });
  }

  function paintTabs() {
    const z = $('#z-tabs'); if (!z) return;
    const tabs = [['disciples', `Disciples ${S.pawns.length}/${S.pawn_cap}`], ['work', 'Work'], ['build', `Build${S.builds.length ? ` (${S.builds.length})` : ''}`],
      ['research', 'Research'], ['chronicle', 'Chronicle']];
    const body = { disciples, work, build, research, chronicle }[tab]();
    z.innerHTML = `<div class="tabs" role="tablist">${tabs.map(([id, label]) => `<button role="tab" aria-selected="${tab === id}" class="${tab === id ? 'on' : ''}" data-tab="${id}">${esc(label)}</button>`).join('')}</div>
      <div class="tabbody">${body}</div>`;
    z.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { tab = b.dataset.tab; sessionStorage.setItem('sect.tab', tab); paintTabs(); }; });
    z.querySelectorAll('[data-pawn]').forEach((b) => { b.onclick = () => pawnSheet(b.dataset.pawn); });
    z.querySelectorAll('[data-prio]').forEach((b) => {
      b.onclick = () => { const [pawn, job, cur] = b.dataset.prio.split('|'); const next = cur === '0' ? 1 : (Number(cur) + 1) % 5; order('priority', { pawn, job, level: next }, true); };
    });
    z.querySelectorAll('[data-build]').forEach((b) => { b.onclick = () => order('build', { room: b.dataset.build }); });
    z.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => order('cancel-build', { index: Number(b.dataset.cancel) }); });
    z.querySelectorAll('[data-tech]').forEach((b) => { b.onclick = () => order('research', { tech: b.dataset.tech }); });
  }

  function disciples() {
    return `<div class="pawns">${S.pawns.map((p) => `<button class="pawn" data-pawn="${esc(p.id)}">
      ${face(p, 56)}
      <span class="grow"><b>${esc(p.name)}</b>${p.master ? ' <span class="tag gold">You</span>' : ''} <span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span>
        <span class="doing">${p.broken ? '<span class="tag red">Qi deviation</span> ' : ''}${p.inspired ? '<span class="tag jade">Inspired</span> ' : ''}${p.sick ? '<span class="tag red">Sick</span> ' : ''}${esc(p.doing)}</span>
        <span class="needs"><span title="Mood ${p.mood}">Mood ${bar(p.mood, moodCls(p.mood))}</span><span title="Food ${p.food}">Food ${bar(p.food, p.food < 25 ? 'verm' : 'azure')}</span>
          <span title="Rest ${p.rest}">Rest ${bar(p.rest, p.rest < 25 ? 'verm' : 'azure')}</span><span title="Health ${p.health}">Health ${bar(p.health, p.health < 50 ? 'verm' : 'jade')}</span></span>
      </span></button>`).join('')}</div>
      <p class="dim small" style="margin:10px 0 0">${S.beds} bed${S.beds === 1 ? '' : 's'} for ${S.pawns.length} disciple${S.pawns.length === 1 ? '' : 's'}. Wanderers sometimes ask to join; the sect can hold ${S.pawn_cap}.${S.graves ? ` ${S.graves} lie in the sect's graveyard.` : ''}</p>`;
  }

  function work() {
    return `<p class="dim small">Tap a cell to set a priority. <b>1</b> is done first, <b>4</b> last, blank never. When two jobs tie, a disciple does what the sect is shortest of.</p>
      <div class="scroll-x"><table class="worktable"><tr><th></th>${S.jobs.map((j) => `<th title="Uses ${esc(j.skill)}">${esc(j.name)}</th>`).join('')}</tr>
      ${S.pawns.map((p) => `<tr><td><b>${esc(p.name.split(' ')[0])}</b></td>${S.jobs.map((j) => {
        const lv = p.prio[j.id]; const sk = p.skills.find((s) => s.name === j.skill);
        return `<td><button class="prio p${lv}" data-prio="${esc(p.id)}|${esc(j.id)}|${lv}" aria-label="${esc(p.name)}: ${esc(j.name)}, priority ${lv || 'off'}; skill ${sk ? sk.lv : 0}">
          ${lv || ''}<small>${sk ? sk.lv : 0}${sk && sk.passion ? '🔥'.repeat(sk.passion) : ''}</small></button></td>`;
      }).join('')}</tr>`).join('')}</table></div>
      <p class="dim small" style="margin:8px 0 0">The small number is their skill; a flame means they love it and learn it fast.</p>`;
  }

  function build() {
    const queue = S.builds.length ? `<ul class="list">${S.builds.map((b, i) => `<li class="row"><span class="grow"><b>${esc(b.name)}</b>${bar(b.pct, 'azure')}</span>
        <span class="dim small num">${b.pct}%</span><button class="btn quiet" data-cancel="${i}">Cancel</button></li>`).join('')}</ul>` : '<p class="dim">Nothing is being built. Disciples with Build as a priority work on the first job in the queue.</p>';
    return `${queue}<div class="buildgrid">${S.rooms.map((r) => `<div class="buildcard ${r.open ? '' : 'new'}">
        <b>${esc(r.name)}</b> <span class="tag ${r.open ? 'blue' : ''}">${r.open ? `Level ${r.level}` : 'Not built'}${r.queued ? ` +${r.queued}` : ''}</span>
        <p class="small dim">${esc(r.effect)}</p>
        ${r.cost ? (r.locked ? `<p class="small" style="font-weight:800;margin:0">${esc(r.locked)}</p>`
          : `<button class="btn ${r.affordable ? 'primary' : ''}" data-build="${esc(r.id)}" ${r.affordable ? '' : 'disabled'}>${r.open ? 'Raise' : 'Build'}: ${esc(costText(r.cost))}</button>`)
          : '<span class="tag gold">Highest level</span>'}</div>`).join('')}</div>`;
  }

  function research() {
    const R = S.research;
    const head = R.has_library ? '' : '<p class="warn">With no Scripture Pavilion, only your own study moves research along (each correct answer is one point of insight). Build one and disciples will research too.</p>';
    return `${head}<ul class="list">${R.items.map((t) => {
      const cur = R.current === t.id;
      return `<li class="row"><span class="grow"><b>${esc(t.name)}</b> ${t.done ? '<span class="tag jade">Known</span>' : ''}<br><span class="small dim">${esc(t.effect)}</span>
        ${cur ? bar(100 * R.progress / t.cost, 'violet') : ''}</span>
        ${t.done ? '' : cur ? `<span class="dim small num">${R.progress}/${t.cost}</span>` : `<button class="btn" data-tech="${esc(t.id)}">Research (${t.cost})</button>`}</li>`;
    }).join('')}</ul>`;
  }

  function chronicle() {
    return S.log.length ? `<ul class="list">${S.log.map((e) => `<li class="letter ${esc(e.kind)}"><b>${esc(e.title)}</b> <span class="dim small">day ${e.day}</span><br><span class="small">${esc(e.text)}</span></li>`).join('')}</ul>`
      : '<p class="dim">Nothing has happened yet.</p>';
  }

  /* ---------------- sheets ---------------- */
  function pawnSheet(id) {
    const p = S.pawns.find((x) => x.id === id); if (!p) return;
    const pills = (S.res.find((r) => r.id === 'pills') || {}).n || 0;
    openSheet(`<div class="row" style="align-items:flex-start">${face(p, 84)}<div class="grow"><h2>${esc(p.name)}</h2>
        <p class="dim" style="margin:0">${p.age} · ${esc(p.root)} spirit root${p.master ? ' · Sect Master (you)' : ''}</p>
        <p style="margin:6px 0 0"><span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span> <span class="small dim">${p.qi} / ${p.qi_need} qi</span></p>${bar(p.qi_pct, 'violet')}</div></div>
      <p style="margin-top:12px">Now: <b>${esc(p.doing)}</b></p>
      <div class="needs big"><span>Mood <b class="num">${p.mood}</b>${bar(p.mood, moodCls(p.mood))}</span><span>Food <b class="num">${p.food}</b>${bar(p.food, 'azure')}</span>
        <span>Rest <b class="num">${p.rest}</b>${bar(p.rest, 'azure')}</span><span>Joy <b class="num">${p.joy}</b>${bar(p.joy, 'azure')}</span><span>Health <b class="num">${p.health}</b>${bar(p.health, 'jade')}</span></div>
      <h3 style="margin-top:14px">On their mind</h3>
      ${p.thoughts.length ? `<ul class="list">${p.thoughts.map((t) => `<li class="row"><span class="grow">${esc(t.label)}</span><b class="num" style="color:var(--${t.v < 0 ? 'verm-d' : 'jade-d'})">${t.v > 0 ? '+' : ''}${t.v}</b></li>`).join('')}</ul>` : '<p class="dim">Nothing in particular.</p>'}
      <h3 style="margin-top:14px">Traits</h3>
      <ul class="list">${p.traits.map((t) => `<li><b>${esc(t.name)}</b> <span class="dim small">${esc(t.text)}</span></li>`).join('')}</ul>
      <h3 style="margin-top:14px">Skills</h3>
      <div class="skills">${p.skills.map((s) => `<span>${esc(s.name)} <b class="num">${s.lv}</b>${s.passion ? ` ${'🔥'.repeat(s.passion)}` : ''}${bar(s.lv * 5, 'jade')}</span>`).join('')}</div>
      <hr><div class="row"><button class="btn" data-heal ${pills && (p.health < 100 || p.sick) ? '' : 'disabled'}>Give a pill (${pills})</button>
        ${p.master ? '' : '<button class="btn quiet" data-banish>Send away</button>'}</div>`);
    const s = $('#sheet');
    const heal = $('[data-heal]', s); if (heal) heal.onclick = async () => { await order('pill', { pawn: id }); pawnSheet(id); };
    const ban = $('[data-banish]', s); if (ban) ban.onclick = async () => { if (!confirm(`Send ${p.name} away from the sect for good?`)) return; closeSheet(); await order('banish', { pawn: id }); };
  }

  function roomSheet(id) {
    const r = S.rooms.find((x) => x.id === id); if (!r) return;
    openSheet(`<h2>${esc(r.name)}</h2><p class="dim">${r.open ? `Level ${r.level} of ${r.max}` : 'Not built yet'}${r.queued ? ' · under construction' : ''}</p><p>${esc(r.effect)}</p>
      ${r.cost ? (r.locked ? `<p class="tag red">${esc(r.locked)}</p>`
        : `<button class="btn ${r.affordable ? 'primary' : ''}" data-go ${r.affordable ? '' : 'disabled'}>${r.open ? 'Raise' : 'Build'}: ${esc(costText(r.cost))}</button>
           ${r.affordable ? '<p class="dim small" style="margin-top:8px">Materials are spent now; disciples with Build as a priority do the work.</p>' : '<p class="dim small" style="margin-top:8px">You do not have the materials yet.</p>'}`)
        : '<p class="tag gold">Highest level reached</p>'}`);
    const go = $('[data-go]', $('#sheet')); if (go) go.onclick = async () => { closeSheet(); await order('build', { room: id }); };
  }

  function paint() { paintTop(); paintEvent(); paintScene(); paintTabs(); }

  view.innerHTML = `<div id="sect-root"><div id="z-top"></div><div class="grid2">${h.todayPanel()}${h.masterPanel()}</div>
    <div id="z-event"></div><section class="panel scenewrap" id="z-scene"></section><section class="panel" id="z-tabs" style="margin-top:14px"></section></div>`;
  h.bindToday(view);
  paint();
  stop();
  timer = setInterval(beat, 1000);
  return { stop, order };
}
