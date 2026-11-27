// The sect screen: a colony sim you watch and steer. The server owns the simulation;
// this module draws it, sends orders, and asks for sim hours as real time passes.
// All text from the server goes through esc(); every number arrives already cast.

import { ICON, VAULT, backdrop, portrait, scene, sectScene, setFaces, siteCrop, siteRect } from '/art.js';

const SPEED_KEY = 'sect.speed';
// Two looks each for the map label and the Build tab, for the owner to choose between (A is the default).
const LOOK = (k) => { try { return localStorage.getItem(`sect.look.${k}`) === 'B' ? 'B' : 'A'; } catch (_) { return 'A'; } };
const SECS_PER_HOUR = { 1: 4, 2: 2, 3: 1 };          // real seconds per sim hour
const RES_ICON = { rice: '🌾', wood: '🪵', stone: '🪨', herbs: '🌿', pills: '💊', stones: '💎' };
const SITE_OF = { farm: 'fields', quarry: 'spirit_vein', 'cut wood': 'storehouse', 'forage herbs': 'fields', 'brew pills': 'alchemy',
  research: 'library', train: 'training', meditate: 'meditation', sleeping: 'dormitory', recovering: 'dormitory', relaxing: 'main_hall', idle: 'main_hall' };
const EVENT_ART = { omen: 'mission', young_master: 'leader', auction: 'treasure', secret_realm: 'seclusion', cave: 'seclusion', tournament: 'technique',
  demonic_offer: 'seclusion', trip_choice: 'map', fate: 'seclusion', succession: 'leader', qingming: 'map', lord: 'leader', taxes: 'leader', embrace: 'seclusion', discipline: 'hall', demon: 'seclusion', festival: 'hall', merchant: 'treasure', wanderer: 'hall', recruit: 'hall', engagement: 'leader', spy: 'leader', village: 'map', beast_cub: 'map', pact_duel: 'technique', feud: 'hall', thief: 'treasure' };
const RES_SHORT = { stones: 'Spirit st.' };          // phone chips keep a label; only the long one is cut
const ELEMENT_ICON = { wood: '🌿', fire: '🔥', earth: '⛰', metal: '⚔', water: '💧' };
const store = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } } };

export function mountSect(h) {
  const { view, $, esc, api, toast, openSheet, closeSheet } = h;
  let S = h.sect();
  setFaces(S && S.faces);
  let tab = sessionStorage.getItem('sect.tab') || 'disciples';
  let speed = [0, 1, 2, 3].includes(Number(store.get(SPEED_KEY))) && store.get(SPEED_KEY) !== null ? Number(store.get(SPEED_KEY)) : 1;
  let sceneSig = '';
  let tabSig = '';
  let timer = null;
  let busy = false;
  let owed = 0;
  let idle = 0;
  let seq = 0;
  let heldAt = 0;                                   // when a work cell was last long-pressed (touch)
  let shown = -1;                                   // the result scene on screen, if any
  let openChip = '';                                // the resource chip whose breakdown is open
  let alertsOpen = false;                           // the collapsed alert bar, expanded
  const gone = new Set();                           // scenes dismissed here, while the server catches up
  const sceneTop = () => Math.max(-1, ...(S.scenes || []).map((x) => x.id));
  let lastScene = sceneTop();
  const freshScene = () => { const top = sceneTop(); const f = top > lastScene; lastScene = Math.max(lastScene, top); return f; };

  const face = (p, size = 48, mood) => portrait(p.id + p.name, { root: p.root, size, kind: p.master ? 'master' : '', mood: mood || (p.broken ? 'oops' : p.mood >= 65 ? 'happy' : 'calm') });
  const bar = (v, cls = '') => `<span class="bar thin ${cls}"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span>`;
  const moodCls = (m) => (m < 25 ? 'verm' : m < 45 ? '' : 'jade');
  const clock = () => `${String(S.hod).padStart(2, '0')}:00`;
  const costText = (c) => Object.entries(c).map(([k, v]) => `${v} ${k === 'stones' ? 'spirit stones' : k}`).join(', ');
  const signed = (v) => `<b class="num" style="color:var(--${v < 0 ? 'verm' : 'jade'})">${v > 0 ? '+' : ''}${v}</b>`;
  const flames = (n) => '🔥'.repeat(Math.max(0, Math.min(2, n)));

  function take(res, mine) { if (res.sect && mine >= seq) { seq = mine; S = res.sect; h.setSect(S); setFaces(S.faces); return true; } return false; }

  async function order(action, body = {}, quiet = false) {
    const mine = ++seq;
    const res = await api(`/api/sect/${action}`, body);
    take(res, mine);
    const framed = freshScene();                     // a result scene says it better than a toast
    if (res.ok === false && !quiet) toast(res.error || 'That did not work.');
    else if (res.event && !quiet && !framed) toast(res.event.title, res.event.kind === 'bad' ? 6000 : 3500);
    paint();
    return res;
  }

  /* ---------------- the clock ---------------- */
  function setSpeed(n) { speed = n; store.set(SPEED_KEY, String(n)); owed = 0; paintTop(); }
  async function beat() {
    if (!view.isConnected || !$('#sect-root')) { stop(); return; }
    if (document.hidden || busy) return;
    paintScenes();
    const waiting = !speed || S.pending || S.seclusion || !$('#sheet').hidden;
    let hours = 0;
    if (waiting) {
      // Paused, or waiting on you: tell the server we are here so the time is not counted as time away.
      idle += 1;
      if (idle < 20) return;
    } else {
      owed += 1 / SECS_PER_HOUR[speed];
      hours = Math.floor(owed);
      if (hours < 1) return;
      owed -= hours;
    }
    idle = 0;
    busy = true;
    const before = S.log.length ? S.log[0].hour + S.log[0].title : '';
    const mine = ++seq;
    const res = await api('/api/sect/tick', { hours });
    busy = false;
    if (take(res, mine)) {
      const top = S.log[0];
      if (!freshScene() && top && top.hour + top.title !== before && top.hour > 0) toast(top.title, top.kind === 'bad' ? 6000 : 3500);
      paint();
    }
  }
  function stop() { if (timer) clearInterval(timer); timer = null; }

  /* ---------------- zones ---------------- */
  // A resource chip is a button: it opens a small breakdown under the bar (tooltips do nothing on a phone).
  function chip(id, inner, cls, label) {
    return `<button type="button" class="res ${cls}" data-res="${esc(id)}" data-focus-key="res-${esc(id)}" aria-expanded="${openChip === id}" aria-controls="chippop" aria-label="${esc(label)}. Show the breakdown">${inner}</button>`;
  }
  const netText = (n) => `${n > 0 ? '+' : n < 0 ? '−' : '±'}${Math.abs(n)}`;
  function rate(r) {
    if (!r.full || !(r.made_n || r.spent_n)) return '';
    return `<small class="rate ${r.net > 0 ? 'up' : r.net < 0 ? 'down' : ''}" aria-hidden="true">${netText(r.net)}/day</small>`;
  }
  function chipPop() {
    if (!openChip) return '';
    const r = S.res.find((x) => x.id === openChip);
    const NOTES = {
      insight: ['Insight', 'Insight comes from your own study (each correct answer adds a point) and from what the evening reading in the Pavilion earns with no topic chosen. It is spent on research automatically.'],
      defense: ['Defence', 'How strong the sect stands against raids and beasts.'],
      fame: ['Fame', 'Won in fights, tournaments, festivals, a raised Main Hall and every step a disciple takes. Draws better recruits, and raiders.'],
    };
    let head; let body;
    if (r) {
      const line = (label, n) => `<li class="row"><span class="grow">${esc(label)}</span><b class="num" style="color:var(--${n < 0 ? 'verm' : 'jade'})">${netText(n)}</b></li>`;
      const made = r.made.length ? r.made.map((m) => line(m.label, m.n)).join('') : '<li class="dim small">Nobody worked at it.</li>';
      const spent = r.spent.length ? r.spent.map((u) => line(u.label, -u.n)).join('') : '<li class="dim small">Nothing.</li>';
      head = `${esc(r.name)} <span class="dim small">${r.n}${r.cap ? ` in store, holds ${r.cap}` : ' in store'}</span>`;
      body = `<h4>Made by work, ${r.full ? 'the last day' : `the last ${r.hours} hour${r.hours === 1 ? '' : 's'}`}</h4><ul class="list">${made}</ul>
        <h4>Spent a day</h4><ul class="list">${spent}</ul>
        ${r.full ? `<p class="row net"><span class="grow"><b>Net</b></span><b class="num" style="color:var(--${r.net < 0 ? 'verm' : 'jade'})">${netText(r.net)} a day</b></p>`
    : `<p class="dim small">The net rate shows once a full day of work has been seen (${r.hours} of 24 hours so far).</p>`}
        <p class="dim small">Made is what work actually added over the last day of sect time, nights included; spent is today's upkeep. Trades, gifts and loot are not counted.</p>`;
    } else {
      const n = NOTES[openChip] || ['', ''];
      head = esc(n[0]); body = `<p class="small" style="margin:4px 0 0">${esc(n[1])}</p>`;
    }
    return `<div class="chippop" id="chippop" role="region" aria-label="Breakdown"><div class="row"><b class="grow">${head}</b>
      <button type="button" class="btn quiet" data-chip-close data-focus-key="chip-close" aria-label="Close the breakdown">✕</button></div>${body}</div>`;
  }
  // Alerts fold into one bar when there is more than one, so the sect map stays on screen.
  function alertsHtml() {
    const A = S.alerts; if (!A.length) return '';
    const item = (a) => `<li class="${esc(a.kind)}">${a.pawn ? `<button class="linkish" data-pawn="${esc(a.pawn)}">${esc(a.text)}</button>` : esc(a.text)}</li>`;
    if (A.length === 1) return `<ul class="alerts">${item(A[0])}</ul>`;
    const top = A.find((a) => a.kind === 'bad') || A[0];
    return `<div class="alertbar ${esc(top.kind)}"><button type="button" class="alerthead" data-alerts data-focus-key="alerts" aria-expanded="${alertsOpen}" aria-controls="alertlist">
        <span class="alerttop">${esc(top.text)}</span><span class="alertn">${A.length} things need attention ${alertsOpen ? '▴' : '▾'}</span></button>
      ${alertsOpen ? `<ul class="alerts" id="alertlist">${A.map(item).join('')}</ul>` : ''}</div>`;
  }

  function paintTop() {
    const z = $('#z-top'); if (!z) return;
    const key = z.contains(document.activeElement) ? document.activeElement.getAttribute('data-focus-key') : null;   // repainting must not drop keyboard focus
    z.innerHTML = `<header class="status">
        <h1 style="border-left:6px solid ${S.colours.includes(S.style.colour) ? `var(--sect-colour)` : 'var(--gold)'};padding-left:10px">${esc(S.name)}${S.style.motto ? `<em class="motto">“${esc(S.style.motto)}”</em>` : ''}<small>${esc(S.renown)}${S.demonic ? ' · demonic path' : ''} · <span title="Day ${S.day} since the founding">${esc(S.when)}</span> · ${clock()}${S.seclusion ? ' · gates sealed' : ''}</small></h1>
        <span class="pill flame ${S.streak ? '' : 'off'}" title="Study streak. Best: ${S.best_streak}">${ICON.flame}${S.streak}</span>
        <span class="speed" role="group" aria-label="Game speed">
          <button class="${speed === 0 ? 'on' : ''}" data-speed="0" data-focus-key="speed-0" aria-label="Pause">${ICON.pause}</button>
          ${[1, 2, 3].map((n) => `<button class="${speed === n ? 'on' : ''}" data-speed="${n}" data-focus-key="speed-${n}" aria-label="Speed ${n}">${'▸'.repeat(n)}</button>`).join('')}
        </span>
      </header>
      <div class="resbar">${S.res.map((r) => chip(r.id, `<span aria-hidden="true">${RES_ICON[r.id] || ''}</span><b class="num">${r.n}</b><small class="lbl">${esc(r.name)}</small><small class="lbl-s">${esc(RES_SHORT[r.id] || r.name)}</small>${rate(r)}`,
          r.id === 'rice' && S.food_days < 3 ? 'low' : '', `${r.name}: ${r.n}${r.full && (r.made_n || r.spent_n) ? `, ${r.net >= 0 ? 'gaining' : 'losing'} ${Math.abs(r.net)} a day` : ''}`)).join('')}
        ${chip('insight', `<span aria-hidden="true">📜</span><b class="num">${S.insight}</b><small class="lbl">Insight</small><small class="lbl-s">Insight</small>`, '', `Insight: ${S.insight}`)}
        ${chip('defense', `<span aria-hidden="true">🛡</span><b class="num">${S.defense}</b><small class="lbl">Defence</small><small class="lbl-s">Defence</small>`, '', `Defence: ${S.defense}`)}
        ${chip('fame', `<span aria-hidden="true">🏮</span><b class="num">${S.fame}</b><small class="lbl">Fame</small><small class="lbl-s">Fame</small>`, '', `Fame: ${S.fame}`)}
      </div>${chipPop()}
      ${S.guide ? `<div class="guide tutor">${portrait('guide', { kind: 'elder', size: 52 })}<div class="speech"><small class="dim">The elder's counsel · ${S.guide.n} of ${S.guide.total}</small><br>${esc(S.guide.text)}
          <button class="linkish dim small" data-skipguide style="margin-left:8px">I know colony sims, skip</button></div></div>` : ''}
      ${S.siege ? `<p class="warn">⚔ Under siege by the ${esc(S.siege.sect)}: battle ${S.siege.stage} of three is coming. Train, brew, and mend the wounded.</p>` : ''}
      ${S.quest ? `<p class="questline ${S.quest.ready ? 'ready' : ''}">📜 <b>${esc(S.quest.title)}</b>: ${S.quest.have}/${S.quest.n} ${esc(S.quest.res)}, ${S.quest.days_left} day${S.quest.days_left === 1 ? '' : 's'} left.
          ${S.quest.ready ? '<button class="btn primary" data-deliver>Deliver</button>' : ''}</p>` : ''}
      ${alertsHtml()}`;
    if (key) { const back = z.querySelector(`[data-focus-key="${key}"]`); if (back) back.focus({ preventScroll: true }); }
    z.querySelectorAll('[data-speed]').forEach((b) => { b.onclick = () => setSpeed(Number(b.dataset.speed)); });
    const closeChip = () => { const was = openChip; openChip = ''; paintTop(); const c = $(`[data-res="${was}"]`, z); if (c) c.focus({ preventScroll: true }); };
    z.querySelectorAll('[data-res]').forEach((b) => { b.onclick = () => { if (openChip === b.dataset.res) closeChip(); else { openChip = b.dataset.res; paintTop(); } }; });
    const pc = $('[data-chip-close]', z); if (pc) pc.onclick = closeChip;
    z.onkeydown = (e) => { if (e.key === 'Escape' && openChip) { e.stopPropagation(); closeChip(); } };
    const ab = $('[data-alerts]', z); if (ab) ab.onclick = () => { alertsOpen = !alertsOpen; paintTop(); };
    z.querySelectorAll('[data-pawn]').forEach((b) => { b.onclick = () => pawnSheet(b.dataset.pawn); });
    const sk = $('[data-skipguide]', z); if (sk) sk.onclick = () => order('guide-skip', {}, true);
    const dv = $('[data-deliver]', z); if (dv) dv.onclick = () => order('deliver');
  }

  function paintEvent() {
    const z = $('#z-event'); if (!z) return;
    const ev = S.pending;
    const sig = ev ? ev.title + ev.text + ev.options.map((o) => o.id + o.warn + o.counsel).join() : '';
    if (z.dataset.sig === sig) return;
    z.dataset.sig = sig;
    z.innerHTML = ev ? `<section class="panel event" style="background-image:linear-gradient(90deg,#120d0af2 0%,#120d0ad9 55%,#120d0a66 100%),url(${backdrop(EVENT_ART[ev.kind] || 'hall')})">
      <h2>${esc(ev.title)}</h2><p>${esc(ev.text)}</p>
      <div class="choices">${ev.options.map((o) => `<button class="btn" data-opt="${esc(o.id)}">${esc(o.label)}${o.counsel ? ' <span class="tag jade">the elders advise this</span>' : ''}${o.warn ? ` <span class="tag red">breaks “${esc(o.warn)}”</span>` : ''}</button>`).join('')}</div>
      <p class="dim small" style="margin:8px 0 0">Time waits for your answer.</p></section>` : '';
    z.querySelectorAll('[data-opt]').forEach((b) => { b.onclick = () => order('resolve', { option: b.dataset.opt }); });
    if (ev) z.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function paintScene() {
    const z = $('#z-scene'); if (!z) return;
    const building = S.builds.map((b) => b.room);
    const staff = {};
    S.pawns.forEach((p) => {
      if (p.away) return;
      const site = p.doing === 'build' ? building[0] : SITE_OF[p.doing] || 'main_hall';
      if (site) (staff[site] = staff[site] || []).push(p);
    });
    const trayText = (r) => (r.tray || []).slice(0, 2).map((t) => `+${t.n} ${t.name}`).join(' ');
    const sig = JSON.stringify([S.rooms.map((r) => r.level), building, Object.entries(staff).map(([k, v]) => k + v.map((p) => p.id).join()), S.rooms.map((r) => r.affordable), S.rooms.map(trayText), S.treasures.length]);
    if (sig === sceneSig && z.firstChild) return;
    sceneSig = sig;
    const lookL = LOOK('label');
    const pips = (r) => `<i class="pips" aria-hidden="true">${Array.from({ length: r.max }, (_, i) => `<b class="${i < r.level ? 'on' : ''}"></b>`).join('')}</i>`;
    const rooms = S.rooms.map((r) => {
      const [x, y, w, hh] = siteRect(r.id);
      const crew = (staff[r.id] || []).slice(0, 5).map((p) => face(p, 30)).join('');
      // A room you can afford to raise glows softly on its name plate (no badge, no arrow); a room whose crew made
      // something since dawn has its lanterns brightened and says what.
      const tray = trayText(r);
      const name = lookL === 'B'
        ? `<span class="pl-name">${esc(r.name)}</span>${r.open ? `<span class="pl-lv">${r.level}</span>` : building.includes(r.id) ? '<span class="pl-lv">building</span>' : ''}`
        : `<span class="pl-name">${esc(r.name)}</span>${r.open ? pips(r) : building.includes(r.id) ? '<i class="pl-note">building</i>' : ''}`;
      return `<button class="room look${lookL} ${r.open ? '' : 'closed'} ${building.includes(r.id) ? 'building' : ''} ${r.affordable ? 'can' : ''} ${tray ? 'tray' : ''}" data-room="${esc(r.id)}" style="left:${x}%;top:${y}%;width:${w}%;height:${hh}%"
        aria-label="${esc(r.name)}, ${r.open ? `level ${r.level} of ${r.max}` : 'not built'}${r.affordable ? ', you can afford the next level' : ''}${tray ? `, made ${esc(tray)} since dawn` : ''}"${r.affordable ? ' title="Ready to raise"' : ''}>
        <span class="crew" aria-hidden="true">${crew}</span>
        ${tray ? `<span class="trayn" aria-hidden="true">${esc(tray)}</span>` : ''}
        <span class="plaque">${name}</span></button>`;
    }).join('');
    const [vx, vy, vw, vh] = VAULT;
    z.innerHTML = `<div class="hq">${sectScene()}<div class="daylight" id="daylight"></div>${rooms}
      <button class="room vault" data-vault style="left:${vx}%;top:${vy}%;width:${vw}%;height:${vh}%" aria-label="Treasure vault: manuals, treasures and the world beyond">
        <span class="plaque">Treasure Vault${S.treasures.length ? `<em>${S.treasures.length}</em>` : ''}</span></button></div>`;
    z.querySelectorAll('[data-room]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.room); });
    $('[data-vault]', z).onclick = () => { tab = 'world'; sessionStorage.setItem('sect.tab', tab); paintTabs(); $('#z-tabs').scrollIntoView({ behavior: 'smooth' }); };
  }

  // The near goal, always in view: the next Main Hall level, what it opens, and the three rooms it waits on.
  function paintHall() {
    const z = $('#z-hall'); if (!z) return;
    const H = S.hall_next;
    const shortText = (o) => Object.entries(o).map(([k, v]) => `${v} more ${k === 'stones' ? 'spirit stones' : k}`).join(' and ');
    const now = H.top ? H.level : H.level - 1;
    const ladder = `<ol class="hn-ladder" aria-label="Main Hall level ${now} of 10">${Array.from({ length: 10 }, (_, i) => `<li class="${i < now ? 'on' : i === now ? 'next' : ''}">${i + 1}</li>`).join('')}</ol>`;
    const check = H.check.length ? `<div class="hn-check"><span class="small">Three other rooms at level ${H.need_lv}</span><ul>${H.check.map((x) => `<li class="${x.ok ? 'ok' : ''}">${x.name ? `${esc(x.name)} <b class="num">${x.lv}</b>` : 'another room'}</li>`).join('')}</ul></div>` : '';
    let act = '';
    if (H.top) act = '<p class="small dim" style="margin:0">The ladder is climbed.</p>';
    else if (H.queued) act = `<div class="hn-prog"><span class="small">Being raised, <b class="num">${H.pct}%</b></span>${bar(H.pct, 'azure')}<small class="dim">${esc(readyIn(H.left))}</small></div>`;
    else {
      const why = !H.ready ? `Raise three rooms to level ${H.need_lv} first` : Object.keys(H.short).length ? `Needs ${shortText(H.short)}` : !H.free ? 'Every builder is busy' : '';
      act = `<button class="btn ${H.affordable ? 'primary' : ''}" data-hall ${H.affordable ? '' : 'disabled'}>Raise it: ${esc(costText(H.cost))}</button>
        <small class="dim">${esc(why || readyIn(H.hours))}</small>`;
    }
    const html = `<div class="hallnext ${H.affordable ? 'can' : ''} ${H.top ? 'top' : ''}" style="background-image:linear-gradient(90deg,#1a130ef7 0%,#1a130eeb 62%,#1a130eb3 100%),url(${backdrop('hall')})">
      <div class="hn-head"><small>${H.top ? 'The summit' : 'The next step'}</small><b>Main Hall ${H.level}</b>${ladder}</div>
      <div class="hn-mid"><ul class="hn-opens">${H.opens.map((o) => `<li>${esc(o)}</li>`).join('')}</ul>${check}</div>
      <div class="hn-act">${act}</div></div>`;
    if (z.dataset.sig === html) return;
    z.dataset.sig = html;
    z.innerHTML = html;
    const b = $('[data-hall]', z); if (b) b.onclick = () => order('build', { room: 'main_hall' });
  }

  function paintTabs() {
    const z = $('#z-tabs'); if (!z) return;
    const ready = S.pawns.filter((p) => p.ready).length;
    const tabs = [['disciples', `Disciples ${S.pawns.length}/${S.pawn_cap}${ready ? ' ⚡' : ''}`], ['work', 'Work'], ['build', `Build${S.builds.length ? ` (${S.builds.length})` : ''}`],
      ['research', 'Research'], ['world', 'World'], ['chronicle', 'Chronicle']];
    if (!tabs.some(([id]) => id === tab)) tab = 'disciples';
    const html = `<div class="tabs" role="tablist">${tabs.map(([id, label]) => `<button role="tab" aria-selected="${tab === id}" class="${tab === id ? 'on' : ''}" data-tab="${id}">${esc(label)}</button>`).join('')}</div>
      <div class="tabbody">${{ disciples, work, build, research, world, chronicle }[tab]()}</div>`;
    if (html === tabSig && z.firstChild) return;        // nothing changed: keep scroll position and focus
    if (z.contains(document.activeElement) && document.activeElement.tagName === 'INPUT') return;   // do not repaint under someone typing
    tabSig = html;
    const sx = $('.scroll-x', z) ? $('.scroll-x', z).scrollLeft : 0;
    z.innerHTML = html;
    if ($('.scroll-x', z)) $('.scroll-x', z).scrollLeft = sx;
    z.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { tab = b.dataset.tab; sessionStorage.setItem('sect.tab', tab); paintTabs(); }; });
    z.querySelectorAll('[data-pawn]').forEach((b) => { b.onclick = () => pawnSheet(b.dataset.pawn); });
    z.querySelectorAll('[data-prio]').forEach((b) => {
      // 1 is the highest priority. Raise: off → 4 → 3 → 2 → 1. Lower: 1 → 2 → 3 → 4 → off.
      const set = (dir) => {
        const [pawn, job, cur] = b.dataset.prio.split('|'); const lv = Number(cur);
        const next = dir > 0 ? (lv === 0 ? 4 : Math.max(1, lv - 1)) : (lv === 0 || lv === 4 ? 0 : lv + 1);
        if (next === lv) return;
        b.dataset.prio = `${pawn}|${job}|${next}`;          // show it at once; the server's answer repaints the table
        b.className = `prio p${next}`; $('span', b).textContent = next ? String(next) : '';
        order('priority', { pawn, job, level: next }, true);
      };
      // A long press lowers. The table may be repainted mid-press, so the "just long-pressed" mark lives outside the button.
      let press = null;
      const justHeld = () => Date.now() - heldAt < 900;
      b.onclick = () => { if (!justHeld()) set(1); };
      b.oncontextmenu = (e) => { e.preventDefault(); if (!justHeld()) set(-1); };
      b.onpointerdown = (e) => { if (e.pointerType !== 'mouse') press = setTimeout(() => { heldAt = Date.now(); set(-1); }, 450); };
      b.onpointerup = b.onpointerleave = b.onpointercancel = () => { clearTimeout(press); };
    });
    z.querySelectorAll('[data-build]').forEach((b) => { b.onclick = () => order('build', { room: b.dataset.build }); });
    z.querySelectorAll('[data-roomtile]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.roomtile); });
    z.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => order('cancel-build', { index: Number(b.dataset.cancel) }); });
    z.querySelectorAll('[data-blueprint]').forEach((b) => { b.onclick = () => order('blueprint', { index: Number(b.dataset.blueprint) }); });
    z.querySelectorAll('[data-tech]').forEach((b) => { b.onclick = () => order('research', { tech: b.dataset.tech }); });
    z.querySelectorAll('details[data-fold]').forEach((d) => { d.ontoggle = () => {
      if (d.open) openFolds.add(d.dataset.fold); else openFolds.delete(d.dataset.fold);
      sessionStorage.setItem('sect.folds', JSON.stringify([...openFolds])); tabSig = '';
    }; });
    z.querySelectorAll('[data-pin]').forEach((b) => { b.onclick = () => { const [n, t] = b.dataset.pin.split('|'); const el = $('#pin-note'); if (el) el.textContent = `${n}: ${t}`; }; });
    z.querySelectorAll('[data-colour]').forEach((b) => { b.onclick = () => order('style', { colour: b.dataset.colour, motto: S.style.motto }, true); });
    const mt = $('[data-motto]', z); if (mt) mt.onclick = () => order('style', { colour: S.style.colour, motto: $('#motto').value }, true);
    z.querySelectorAll('[data-precept]').forEach((b) => { b.onclick = () => order('precept', { precept: b.dataset.precept, on: b.dataset.on === '1' }); });
    z.querySelectorAll('[data-recipe]').forEach((b) => { b.onclick = () => order('recipe', { recipe: b.dataset.recipe }); });
    z.querySelectorAll('[data-ally]').forEach((b) => { b.onclick = () => order('ally', { sect: b.dataset.ally }); });
    z.querySelectorAll('[data-forge]').forEach((b) => { b.onclick = () => order('forge'); });
    z.querySelectorAll('[data-trip]').forEach((b) => { b.onclick = () => tripSheet(b.dataset.trip); });
    const rp = $('[data-repeat]', z); if (rp) rp.onchange = () => order('standing', { count: S.standing.pills, on: rp.checked }, true);
    const kp = $('[data-keep]', z); if (kp) kp.onchange = () => order('standing', { count: Number(kp.value) || 0, on: S.standing.repeat }, true);
    z.querySelectorAll('[data-preset-save]').forEach((b) => { b.onclick = () => order('preset-save', { name: b.dataset.presetSave }); });
    z.querySelectorAll('[data-preset-apply]').forEach((b) => { b.onclick = () => order('preset-apply', { name: b.dataset.presetApply }); });
    z.querySelectorAll('[data-gift]').forEach((b) => { b.onclick = () => order('gift', { sect: b.dataset.gift }); });
    z.querySelectorAll('[data-burn]').forEach((b) => { b.onclick = () => { if (confirm('Burn this manual? It cannot be recovered.')) order('burn', { manual: b.dataset.burn }); }; });
  }

  function disciples() {
    return `<div class="pawns">${S.pawns.map((p) => `<button class="pawn ${p.away ? 'away' : ''}" data-pawn="${esc(p.id)}">
      ${face(p, 56)}
      <span class="grow"><b>${esc(p.name)}</b>${p.title ? ` <i class="dim">${esc(p.title)}</i>` : ''}${p.master ? ' <span class="tag gold">You</span>' : ''}
        <span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span> <span class="tag ${p.direct ? 'gold' : ''}">${esc(p.rank)}</span>${p.direct && !p.rank.startsWith('Direct') ? ' <span class="tag gold">Direct disciple</span>' : ''}
        ${p.bonds.filter((x) => x.kind).slice(0, 2).map((x) => `<span class="tag ${x.kind === 'rival' ? 'red' : 'jade'}">${x.kind === 'rival' ? '⚔' : '♥'} ${esc(x.name)}</span>`).join(' ')}
        ${p.companion ? `<span class="tag violet">☯ ${esc(p.companion)}</span>` : ''}${p.demon ? ` <span class="tag red">Heart demon${p.demon > 1 ? ` ×${p.demon}` : ''}</span>` : ''}
        <span class="doing">${p.ready ? `<span class="tag gold">⚡ Ready for ${esc(p.next_realm)}</span> ` : ''}${p.broken ? '<span class="tag red">Qi deviation</span> ' : ''}${p.inspired ? '<span class="tag jade">Inspired</span> ' : ''}${p.sick ? '<span class="tag red">Sick</span> ' : ''}${esc(p.doing)}</span>
        <span class="needs"><span title="Mood ${p.mood}">Mood ${bar(p.mood, moodCls(p.mood))}</span><span title="Food ${p.food}">Food ${bar(p.food, p.food < 25 ? 'verm' : 'azure')}</span>
          <span title="Rest ${p.rest}">Rest ${bar(p.rest, p.rest < 25 ? 'verm' : 'azure')}</span><span title="Health ${p.health}">Health ${bar(p.health, p.health < 50 ? 'verm' : 'jade')}</span></span>
      </span></button>`).join('')}</div>
      <p class="dim small" style="margin:10px 0 0">${S.beds} bed${S.beds === 1 ? '' : 's'} for ${S.pawns.length} disciple${S.pawns.length === 1 ? '' : 's'}. Wanderers sometimes ask to join; the sect can hold ${S.pawn_cap}.${S.graves ? ` ${S.graves} lie in the sect's graveyard.` : ''}</p>`;
  }

  const JOB_ICON = { build: '🔨', farm: '🌾', wood: '🪓', mine: '⛏️', forage: '🌿', craft: '⚗️', research: '📜', train: '⚔️', meditate: '🧘' };
  function work() {
    // The compact grid (one row per disciple, coloured priority numbers) with faces, job icons, skill bars and a one-line legend.
    const WORD = { 1: 'First', 2: 'High', 3: 'Normal', 4: 'Low', 0: 'Never' };
    const best = Object.fromEntries(S.jobs.map((j) => [j.id, Math.max(0, ...S.pawns.map((p) => (p.skills.find((s) => s.name === j.skill) || {}).lv || 0))]));
    const cell = (p, j) => {
      const lv = p.prio[j.id]; const sk = p.skills.find((s) => s.name === j.skill) || {}; const sl = sk.lv || 0;
      return `<td><button class="prio p${lv}" data-prio="${esc(p.id)}|${esc(j.id)}|${lv}" title="${esc(`${j.name}: ${WORD[lv]}. Skill ${sl}${sk.passion ? ', loves it' : ''}. Tap to raise, right-click or hold to lower.`)}"
        aria-label="${esc(`${p.name}, ${j.name}: ${WORD[lv]}; skill ${sl}. Activate to raise; context menu to lower.`)}"><span>${lv || ''}</span><i class="sk" style="--sk:${Math.min(1, sl / 20)}"></i>${sl && sl === best[j.id] ? '<b class="ace" aria-hidden="true">★</b>' : ''}${sk.passion ? `<em aria-hidden="true">${flames(sk.passion)}</em>` : ''}</button></td>`;
    };
    return `<div class="worklegend">${[1, 2, 3, 4, 0].map((n) => `<span><i class="prio p${n} mini"></i>${n || '–'} ${WORD[n]}</span>`).join('')}<span class="dim">Tap to raise · right-click or hold to lower · bar = skill · ★ best · 🔥 loves it</span></div>
      <div class="scroll-x workgrid"><table class="worktable mixed"><tr><th class="who"></th>${S.jobs.map((j) => `<th title="Uses ${esc(j.skill)}"><span class="jic" aria-hidden="true">${JOB_ICON[j.id] || ''}</span><span>${esc(j.name)}</span></th>`).join('')}</tr>
      ${S.pawns.map((p) => `<tr><th class="who" scope="row"><div class="wwho"><span class="wface">${face(p, 34)}</span><span class="wtxt"><b>${esc(p.name)}</b><small class="dim">${esc(p.doing || '')}</small></span></div></th>${S.jobs.map((j) => cell(p, j)).join('')}</tr>`).join('')}</table></div>
      <div class="row" style="margin-top:10px">${['peace', 'war'].map((n) => `${S.presets.includes(n) ? `<button class="btn" data-preset-apply="${n}">Use “${n}” plan</button>` : ''}<button class="btn quiet" data-preset-save="${n}">${S.presets.includes(n) ? 'Update' : 'Save as'} “${n}”</button>`).join('')}</div>`;
  }



  // Sim hours as the player will feel them: away (one sim hour per 30 real minutes) and watching at speed 1.
  const span = (secs) => (secs < 90 ? `${Math.max(1, Math.round(secs))} s` : secs < 5400 ? `${Math.round(secs / 60)} min` : `${Math.round(secs / 360) / 10} h`);
    const readyIn = (h) => `Ready in about ${span(h * S.builders.away_secs)}, or ${span(h * SECS_PER_HOUR[1])} if you watch`;

  const awayT = (h) => span(h * S.builders.away_secs);
  const watchT = (h) => span(h * SECS_PER_HOUR[1]);
  const haveRes = (k) => (S.res.find((x) => x.id === k) || {}).n || 0;
  const costChips = (cost) => Object.entries(cost).map(([k, v]) => `<span class="cchip ${haveRes(k) < v ? 'short' : ''}">${v} ${esc(k === 'stones' ? 'spirit stones' : k)}</span>`).join('');
  const lvPips = (r) => `<i class="pips" aria-hidden="true">${Array.from({ length: r.max }, (_, i) => `<b class="${i < r.level ? 'on' : i < r.level + r.queued ? 'q' : ''}"></b>`).join('')}</i>`;
  function roomState(r) {
    if (!r.cost) return 'max';
    if (r.locked) return 'locked';
    return r.affordable ? 'can' : 'short';
  }
  function benchSpeed(b, i) {
    return `<details class="fold" data-fold="speed-${i}" ${openFolds.has(`speed-${i}`) ? 'open' : ''}><summary>Speed ×${b.rate}</summary><ul class="list odds">
      ${b.rows.map((o) => `<li class="row"><span class="grow">${esc(o.label)}</span><span class="num small">${o.x === 1 ? '×1' : `+${o.x}`}</span></li>`).join('')}
      ${b.blue ? `<li class="row"><span class="grow">Master's Blueprint</span><span class="num small">−${b.blue} h</span></li>` : ''}
      <li class="row dim small">${b.done} of ${b.need} hours of work done. Disciples with Build as a priority help, two to a job.</li></ul></details>`;
  }
  function builderHead() {
    const B = S.builders;
    return `<div class="row buildhead"><span class="grow"><b class="serif">${B.busy} of ${B.n} builders at work</b>
        ${B.blueprints ? ` <span class="tag gold">${B.blueprints} blueprint${B.blueprints === 1 ? '' : 's'} in hand</span>` : ''}${B.master_hours ? ` <span class="tag jade">The Master builds for ${B.master_hours} more h</span>` : ''}</span></div>
      <details class="fold" data-fold="builders" ${openFolds.has('builders') ? 'open' : ''}><summary>Where builders come from</summary><ul class="list odds">${B.rows.map((o) => `<li class="row"><span class="grow">${esc(o.label)}</span><span class="num small">${o.n}</span></li>`).join('')}
        ${B.next_hall ? `<li class="row dim small">One more at Main Hall level ${B.next_hall}.</li>` : ''}
        <li class="row dim small">A day of study draws a Master's Blueprint (${B.blueprint_cut}% off one job, up to 3 kept); five study days in a week lend the Master as a builder for 24 sect hours.</li></ul></details>`;
  }
  function benchButtons(i) {
    return `${S.builders.blueprints ? `<button class="btn" data-blueprint="${i}" title="Takes ${S.builders.blueprint_cut}% off the time this job has left">Use a blueprint</button>` : ''}<button class="btn" data-cancel="${i}">Cancel</button>`;
  }

  // Look A, the workshop: builders as workbenches with a painted crop of the room and a big countdown; rooms as
  // painted tiles with level pips and cost chips, glowing when you can raise them, greyed while the Hall holds them.
  function buildA() {
    const B = S.builders;
    const running = S.builds.filter((b) => b.running);
    const bench = (b, i) => (b ? `<li class="bench">
        <span class="bthumb" style="${siteCrop(b.room, 1.25)}" aria-hidden="true"></span>
        <div class="bbody"><span class="bname"><b>${esc(b.name)}</b> <span class="dim small">to level ${b.level}</span></span>
          <span class="bcount"><b class="num">${esc(awayT(b.left))}</b><small class="dim">left with the app closed, ${esc(watchT(b.left))} if you watch</small></span>
          ${bar(b.pct, 'azure')}
          <div class="row bfoot">${benchSpeed(b, i)}<span class="grow"></span>${benchButtons(i)}</div></div></li>`
      : '<li class="bench empty"><span class="bthumb idle" aria-hidden="true"></span><div class="bbody"><b class="serif">A builder is free</b><span class="dim small">Choose a room below.</span></div></li>');
    const waiting = S.builds.filter((b) => !b.running);
    const tile = (r) => {
      const st = roomState(r);
      return `<li class="rtile ${st} ${r.open ? '' : 'new'}">
        <button class="rt-pic" data-roomtile="${esc(r.id)}" style="${siteCrop(r.id, 1.6)}" aria-label="${esc(r.name)}: details"><span class="rt-name">${esc(r.name)}</span></button>
        <div class="rt-body"><div class="row">${r.open ? lvPips(r) : `<span class="small dim">${r.queued ? 'Being built' : 'Not built'}</span>`}<span class="grow"></span>${r.queued ? '<span class="tag blue">building</span>' : ''}</div>
          ${st === 'max' ? '<p class="small rt-note">Highest level</p>' : st === 'locked' ? `<p class="small rt-note" title="${esc(r.locked)}">${esc(r.lock_short || r.locked)}</p>`
    : `<div class="rt-cost">${costChips(r.cost)}</div><div class="row rt-go"><small class="dim">ready in about ${esc(awayT(r.hours))}</small><span class="grow"></span>
            <button class="btn ${r.affordable ? 'primary' : ''}" data-build="${esc(r.id)}" ${r.affordable ? '' : 'disabled'}>${r.open ? 'Raise' : 'Build'}</button></div>`}</div></li>`;
    };
    return `<div class="lookA">${builderHead()}<ul class="benches">${Array.from({ length: B.n }, (_, i) => bench(running[i], i)).join('')}</ul>
      ${waiting.length ? `<p class="small dim" style="margin:8px 0 0">Waiting for a builder: ${waiting.map((b) => esc(b.name)).join(', ')}</p>` : ''}
      <ul class="rtiles">${S.rooms.map(tile).join('')}</ul></div>`;
  }

  // Look B, the ledger: builders as a strip of lantern timers; rooms sorted into what you can raise now, what waits
  // on materials (saying what is missing), and what waits on the Main Hall.
  function buildB() {
    const B = S.builders;
    const running = S.builds.filter((b) => b.running);
    const lamp = (b, i) => (b ? `<li class="lamp" style="--p:${b.pct}">
        <span class="ring"><span class="rthumb" style="${siteCrop(b.room, 1)}" aria-hidden="true"></span></span>
        <span class="ltxt"><b>${esc(b.name)} ${b.level}</b><span class="num">${esc(awayT(b.left))}</span><small class="dim">${esc(watchT(b.left))} watching · ${b.pct}%</small>
          <span class="row">${benchButtons(i)}</span>${benchSpeed(b, i)}</span></li>`
      : '<li class="lamp empty"><span class="ring"></span><span class="ltxt"><b>Free</b><small class="dim">waiting for orders</small></span></li>');
    const groups = { can: [], short: [], locked: [], max: [] };
    S.rooms.forEach((r) => groups[roomState(r)].push(r));
    const shortOf = (r) => Object.entries(r.cost).filter(([k, v]) => haveRes(k) < v).map(([k, v]) => `${v - haveRes(k)} ${k === 'stones' ? 'spirit stones' : k}`).join(', ');
    const row = (r, st) => `<li class="lrow ${st}"><button class="lthumb" data-roomtile="${esc(r.id)}" style="${siteCrop(r.id, 1)}" aria-label="${esc(r.name)}: details"></button>
        <span class="grow"><b>${esc(r.name)}</b> ${r.open ? lvPips(r) : '<span class="small dim">new</span>'}<br>
          ${st === 'locked' ? `<small class="dim">${esc(r.lock_short || r.locked)}</small>` : st === 'max' ? '<small class="dim">Highest level</small>' : `<span class="rt-cost">${costChips(r.cost)}</span>`}</span>
        ${st === 'can' ? `<span class="lgo"><button class="btn primary" data-build="${esc(r.id)}">${r.open ? 'Raise' : 'Build'}</button><small class="dim">ready in about ${esc(awayT(r.hours))}</small></span>`
    : st === 'short' ? `<small class="lneed">Needs ${esc(shortOf(r) || 'a free builder')}</small>` : ''}</li>`;
    const sect = (title, list, st) => (list.length ? `<h4 class="lhead">${esc(title)} <span class="dim small">${list.length}</span></h4><ul class="lrows">${list.map((r) => row(r, st)).join('')}</ul>` : '');
    return `<div class="lookB">${builderHead()}<ul class="lamps">${Array.from({ length: B.n }, (_, i) => lamp(running[i], i)).join('')}</ul>
      ${sect('Ready to raise', groups.can, 'can')}${sect('Gathering materials', groups.short, 'short')}${sect('Waiting on the Main Hall', groups.locked, 'locked')}${sect('Complete', groups.max, 'max')}</div>`;
  }

  function build() { return LOOK('build') === 'B' ? buildB() : buildA(); }

  function research() {
    const R = S.research;
    const head = R.has_library ? '' : '<p class="warn">With no Scripture Pavilion, only your own study moves research along (each correct answer is one point of insight). Build one and disciples will research too.</p>';
    const ledger = (R.rows || []).length ? `<details class="fold"><summary>Where research comes from</summary><ul class="list odds">${R.rows.map((o) => `<li class="row"><span class="grow">${esc(o.label)}</span><span class="num small">${esc(o.v)}</span></li>`).join('')}</ul></details>` : '';
    return `${head}${ledger}<ul class="list">${R.items.map((t) => {
      const cur = R.current === t.id;
      return `<li class="row"><span class="grow"><b>${esc(t.name)}</b> ${t.done ? '<span class="tag jade">Known</span>' : ''}<br><span class="small dim">${esc(t.effect)}</span>
        ${cur ? bar(100 * R.progress / t.cost, 'violet') : ''}</span>
        ${t.done ? '' : cur ? `<span class="dim small num">${R.progress}/${t.cost}</span>` : `<button class="btn" data-tech="${esc(t.id)}">Research (${t.cost})</button>`}</li>`;
    }).join('')}</ul><p class="dim small" style="margin:8px 0 0">Switching topic keeps what was already learned.</p>`;
  }

  // The World tab holds a great deal: every section folds, and stays as you left it.
  const openFolds = new Set(JSON.parse(sessionStorage.getItem('sect.folds') || '["Great Works"]'));
  function fold(html) {
    const parts = html.split(/<h3[^>]*>/);
    return parts[0] + parts.slice(1).map((part) => {
      const end = part.indexOf('</h3>');
      const title = part.slice(0, end); const key = title.replace(/<[^>]*>/g, '').trim();
      return `<details class="fold" data-fold="${esc(key)}" ${openFolds.has(key) ? 'open' : ''}><summary>${title}</summary>${part.slice(end + 5)}</details>`;
    }).join('');
  }

  function world() { return fold(worldRaw()); }

  // A section that does not matter yet is one line saying when it will, gathered at the end (16: hide systems until they matter).
  function worldGates() {
    const room = (id) => (S.rooms.find((r) => r.id === id) || {}).level || 0;
    return {
      precepts: S.day >= 7 || S.precepts.some((x) => x.on) || S.council ? '' : 'Precepts: what the sect swears to stand for. Offered from day 7, once the sect has found its feet.',
      works: !S.guide || S.works.some((w) => w.done) ? '' : 'Great Works: long goals with no deadline. Revealed when the elder\'s lessons are done (or skipped).',
      kingdom: S.day >= 10 || S.kingdom.favour ? '' : 'The mortal kingdom: the lowland lord takes notice of the sect from about day 10.',
      alchemy: room('alchemy') ? '' : 'Alchemy: build an Alchemy Hall to choose what is brewed and keep pills in stock.',
      artifacts: S.artifacts.length || S.has_forge ? '' : 'Artifacts: won at the gate, in the tournament and in the ruins, or forged once there is an Alchemy Hall.',
      treasures: S.treasures.length || S.beast ? '' : 'Treasures: come from auctions, secret realms and inheritances.',
    };
  }

  function worldRaw() {
    const stones = (S.res.find((r) => r.id === 'stones') || {}).n || 0;
    const relCls = (r) => (r >= 15 ? 'jade' : r > -15 ? '' : 'red');
    const gate = worldGates();
    const later = Object.values(gate).filter(Boolean);
    return `<div class="banner" style="background-image:linear-gradient(#0c1228b0,#120d0ae0),url(${backdrop('map')})"><h2>${esc(S.name)}</h2>
        <p>Fame <b class="num">${S.fame}</b>. Fame is won at the gate, in the arena and under the lightning; talented youths seek out famous sects.</p></div>
      <div class="worldmap night" style="background-image:radial-gradient(ellipse at 50% 45%,#f0a8501a,transparent 65%),linear-gradient(#0c1228a6,#120d0abf),url(${backdrop('map')});background-blend-mode:normal,multiply,normal">${S.map.map((m) => `<button class="pin ${esc(m.kind)}" style="left:${m.x}%;top:${m.y}%" title="${esc(m.text)}" data-pin="${esc(m.name)}|${esc(m.text)}"><i></i><span>${esc(m.name)}</span></button>`).join('')}</div>
      <p class="dim small" id="pin-note">Tap a place on the map.</p>
      <h3>Banner and motto</h3>
      <div class="row">${S.colours.map((k) => `<button class="swatch ${S.style.colour === k ? 'on' : ''}" data-colour="${esc(k)}" aria-label="${esc(k)}" style="background:var(--c-${esc(k)})"></button>`).join('')}
        <input class="in grow" id="motto" maxlength="60" placeholder="A motto for the sect" value="${esc(S.style.motto)}"><button class="btn" data-motto>Set</button></div>
      ${S.branches.length ? `<h3 style="margin-top:16px">Branch sects</h3><ul class="list">${S.branches.map((b) => `<li><b>${esc(b.name)}</b> <span class="dim small">led by ${esc(b.leader)}. ${b.sulking ? 'Sends nothing for now: you left them to stand alone.' : 'Sends 15 rice and 5 spirit stones every twelve days.'}</span></li>`).join('')}</ul>` : ''}
      ${S.blessings.length ? `<p>${S.blessings.map((b) => `<span class="tag gold">${esc(b)}</span>`).join(' ')}</p>` : ''}
      ${gate.precepts ? '' : `<h3>Precepts</h3>
      <p class="dim small">What the sect stands for: up to three. Each helps every day, and each makes some choices a betrayal the disciples will feel.${S.council ? ' The elders now offer counsel on great decisions; overruling them costs their goodwill.' : ''}</p>
      <ul class="list">${S.precepts.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> ${x.on ? '<span class="tag gold">Sworn</span>' : ''}<br><span class="small dim">${esc(x.text)}</span></span>
          <button class="btn ${x.on ? 'quiet' : ''}" data-precept="${esc(x.id)}" data-on="${x.on ? '0' : '1'}">${x.on ? 'Abandon' : 'Swear to it'}</button></li>`).join('')}</ul>`}
      ${gate.works ? '' : `<h3 style="margin-top:16px">Great Works</h3>
      <p class="dim small">Long goals with no deadline. Each one finished brings fame and a day the disciples never forget.</p>
      <div class="works">${S.works.map((w) => `<div class="work ${w.done ? 'done' : ''}"><b>${esc(w.name)}</b> ${w.done ? '<span class="tag gold">Achieved</span>' : ''}<br><span class="small dim">${esc(w.text)}</span>
          <ul>${w.lines.map((l) => `<li class="${l.ok ? 'ok' : ''}">${l.ok ? '✓' : '○'} ${esc(l.text)}</li>`).join('')}</ul></div>`).join('')}</div>`}
      <h3 style="margin-top:16px">Expeditions</h3>
      <p class="dim small">Send one to three disciples out. They cannot work or defend the sect while away, and the road forges bonds.</p>
      <ul class="list">${S.places.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> <span class="tag">${x.hours} hours</span><br><span class="small dim">${esc(x.text)}</span></span>
          <button class="btn" data-trip="${esc(x.id)}" ${S.trip ? 'disabled' : ''}>${S.trip ? 'A party is out' : 'Choose a party'}</button></li>`).join('')}</ul>
      <label class="row small" style="margin-top:8px"><input type="checkbox" data-repeat ${S.standing.repeat ? 'checked' : ''} style="width:20px;height:20px;accent-color:var(--gold)">
        <span class="grow">Standing order: send the same party out again whenever they are home and well${S.trip_plan ? ` (${esc(S.trip_plan.who.join(', '))} to the ${esc(S.trip_plan.place)}, ${esc(S.trip_plan.stance.toLowerCase())})` : ''}.</span></label>
      <h3 style="margin-top:16px">The sects of the region</h3>
      <ul class="list">${S.sects.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> <span class="tag">${esc(x.kind)}</span> <span class="tag ${relCls(x.rel)}">${esc(x.stance)} ${x.rel > 0 ? '+' : ''}${x.rel}</span>
          <br><span class="small">${((S.champs[x.id] || {}).list || []).map((ch) => `${esc(ch.name)} <span class="dim">(${esc(ch.role)}, ${esc(ch.realm)}, strength ${ch.power})</span>`).join(' · ')}</span>
          <br><span class="small dim">Their people advance a stage about every ${(S.champs[x.id] || {}).every || '?'} days. ${x.rel <= -15 ? 'Their raiders know the way to your gate.' : x.rel >= 15 ? 'They will not raid you.' : 'They are watching.'}</span></span>
          ${x.ally ? '<span class="tag gold">Sworn ally</span>' : x.rel >= 50 ? `<button class="btn primary" data-ally="${esc(x.id)}" ${stones >= 20 ? '' : 'disabled'}>Swear alliance (20 💎)</button>` : ''}
          <button class="btn" data-gift="${esc(x.id)}" ${stones >= 10 ? '' : 'disabled'}>Send gifts (10 💎)</button></li>`).join('')}</ul>
      ${gate.kingdom ? '' : `<h3 style="margin-top:16px">The mortal kingdom</h3>
      <p>The lowland lord is <b>${esc(S.kingdom.stance.toLowerCase())}</b> <span class="tag ${S.kingdom.favour >= 30 ? 'jade' : S.kingdom.favour <= -30 ? 'red' : ''}">${S.kingdom.favour > 0 ? '+' : ''}${S.kingdom.favour}</span>
        <span class="dim small">A grateful lord sends rice each autumn; a resentful one sends tax collectors.</span></p>`}
      ${gate.alchemy ? '' : `<h3 style="margin-top:16px">Alchemy</h3>
      <p class="dim small">What the Alchemy Hall brews. Special pills need hundred-year spirit herbs (you hold ${S.rare}) from Herb Valley or lucky foraging; a clumsy alchemist can ruin a batch.
        In the stores: ${S.elixirs.marrow} Marrow-Cleansing, ${S.elixirs.berserk} Berserk.</p>
      <label class="row small">Standing order: keep <input class="in" type="number" min="0" max="20" value="${S.standing.pills}" data-keep style="width:70px"> pills in stock <span class="dim">(0 = off). When the stock falls below this, the best alchemist brews before anything else.</span></label>
      <ul class="list">${S.recipes.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> ${x.on ? '<span class="tag gold">Brewing</span>' : ''}${x.cost ? ` <span class="tag">${esc(x.cost)}</span>` : ''}<br><span class="small dim">${esc(x.text)}</span></span>
          ${x.on ? '' : `<button class="btn" data-recipe="${esc(x.id)}">Brew this</button>`}</li>`).join('')}</ul>`}
      <h3 style="margin-top:16px">Scripture Pavilion</h3>
      <p class="dim small">Each disciple practises the best manual of each kind that their rank allows. Outer disciples read Yellow grade, Inner disciples Mystic, Core disciples Earth, Elders and the Sect Master Heaven.</p>
      <ul class="list">${S.manuals.map((m) => `<li class="row"><span class="grow"><b>${esc(m.name)}</b> <span class="tag ${m.demonic ? 'red' : 'gold'}">${m.demonic ? 'Forbidden' : `${esc(m.grade)} grade`}</span>
          <br><span class="small dim">${esc(m.kind)}, +${m.bonus}%${m.demonic ? ' and more. It darkens the heart of everyone who reads it' : ''}. ${esc(m.rank)}${m.demonic ? '' : ' and above'}.</span></span>
          ${m.demonic ? `<button class="btn quiet" data-burn="${esc(m.id)}">Burn it</button>` : ''}</li>`).join('')}</ul>
      ${gate.artifacts ? '' : `<h3 style="margin-top:16px">Artifacts</h3>
      <p class="dim small">One per disciple; give them out from a disciple's page. They come from raids won at the gate, the tournament, the Ruined Sect, and your own forge. This season favours ${ELEMENT_ICON[S.season_element] || ''} ${esc(S.season_element)} roots.</p>
      ${S.artifacts.length ? `<ul class="list">${S.artifacts.map((a) => `<li><b>${esc(a.name)}</b> ${a.owner ? `<span class="tag jade">${esc(a.owner)}</span>` : '<span class="tag">In the vault</span>'}<br><span class="small dim">${esc(a.text)} ${esc(a.origin)}</span></li>`).join('')}</ul>` : '<p class="dim">None yet.</p>'}
      <button class="btn" data-forge ${S.can_forge ? '' : 'disabled'}>${S.has_forge ? 'Forge an artifact (40 stone, 20 wood, 8 💎)' : 'Forging needs an Alchemy Hall'}</button>`}
      ${gate.treasures ? '' : `<h3 style="margin-top:16px">Treasures</h3>
      ${S.treasures.length || S.beast ? `<ul class="list">${S.treasures.map((t) => `<li><b>${esc(t.name)}</b><br><span class="small dim">${esc(t.text)}</span></li>`).join('')}
        ${S.beast ? `<li><b>${esc(S.beast.name)}</b> <span class="tag jade">Guardian beast</span><br><span class="small dim">Guards the gate with strength ${S.beast.power}, growing with age. Eats one rice a day.</span></li>` : ''}</ul>`
        : '<p class="dim">The vault is empty. Treasures come from auctions, secret realms and inheritances.</p>'}`}
      ${later.length ? `<h3 style="margin-top:16px">Still to come</h3>
        <ul class="list later">${later.map((t) => `<li class="small dim">🔒 ${esc(t)}</li>`).join('')}</ul>` : ''}`;
  }

  function chronicle() {
    const recent = S.log.length ? `<ul class="list">${S.log.map((e) => `<li class="letter ${esc(e.kind)}"><b>${esc(e.title)}</b> <span class="dim small" title="Day ${e.day} since the founding">${esc(e.when)}</span><br><span class="small">${esc(e.text)}</span></li>`).join('')}</ul>`
      : '<p class="dim">Nothing has happened yet.</p>';
    const rumours = S.rumours.length ? `<div class="rumours"><b>Heard in the tea house</b><ul>${S.rumours.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : '';
    const graves = S.tombs.length ? `<h3 style="margin-top:18px">The north slope</h3><ul class="list">${S.tombs.map((g) => `<li>🪦 <b>${esc(g.name)}</b> <span class="dim small">${esc(g.realm)}, died ${esc(g.when)}</span></li>`).join('')}</ul>` : '';
    return `${rumours}${recent}${graves}<h3 style="margin-top:18px">Annals of the ${esc(S.name)}</h3><p class="dim small">What will be remembered: who came, who rose, who fell.</p>
      <ol class="annals">${S.annals.map((a) => `<li><span class="dim small" title="Day ${a.day} since the founding">${esc(a.when)}</span> ${esc(a.text)}</li>`).join('')}</ol>`;
  }

  /* ---------------- sheets ---------------- */
  function pawnSheet(id) {
    const p = S.pawns.find((x) => x.id === id); if (!p) return;
    const pills = (S.res.find((r) => r.id === 'pills') || {}).n || 0;
    const why = [...p.thoughts, ...p.mood_why];
    const bt = p.ready ? `<section class="breakthrough" style="background-image:linear-gradient(#120d0ad9,#120d0aee),url(${backdrop('seclusion')})">
        <h3>${p.tribulation ? '⚡ Heavenly tribulation' : 'Great-realm breakthrough'}: ${esc(p.next_realm)}</h3>
        <ul class="list odds">${p.odds.map((o) => `<li class="row"><span class="grow">${esc(o.label)}</span>${signed(o.v)}</li>`).join('')}
          <li class="row"><span class="grow"><b>Chance of success</b></span><b class="num">${p.chance}%</b></li></ul>
        ${p.grade ? `<h3 style="margin-top:10px">Foundation: ${esc(p.grade.name)}${p.grade.bonus ? ` <span class="tag gold">+${p.grade.bonus}% qi for life</span>` : ''}</h3>
        <ul class="list odds">${p.grade.checks.map((x) => `<li class="${x.ok ? 'ok' : ''}">${x.ok ? '✓' : '○'} ${esc(x.label)}</li>`).join('')}</ul>
        <p class="small dim">The odds above decide whether it succeeds. This list decides how good it is: every two lines met raise the grade, and a Superior or better breakthrough opens rarer fates. Nothing here is luck.</p>` : ''}
        <p class="small dim">${p.tribulation ? 'Heaven answers with lightning. A failure wounds badly, and a disciple who is already hurt may not survive it.' : 'A failure wounds them and scatters some of their qi.'} Each failure makes the next attempt a little surer.</p>
        ${p.gate ? `<p class="${p.gate.ok ? 'small dim' : 'warn'}">${p.gate.ok ? '✓' : '✗'} ${esc(p.gate.text)}</p>` : ''}
        <button class="btn primary big" data-attempt ${p.gate && !p.gate.ok ? 'disabled' : ''}>${p.tribulation ? 'Face the tribulation' : 'Attempt the breakthrough'}</button></section>` : '';
    openSheet(`<div class="row" style="align-items:flex-start">${face(p, 84)}<div class="grow"><h2>${esc(p.name)}${p.title ? ` <i class="dim" style="font-size:.8em">${esc(p.title)}</i>` : ''}</h2>
        <p class="dim" style="margin:0">${p.age} · ${ELEMENT_ICON[p.element] || ''} ${esc(p.root)} ${esc(p.element)} root · ${esc(p.rank)}${p.master ? ' (you)' : ''}${p.direct ? ` <span class="small">(manuals up to ${esc(p.realm_rank)} grade, by realm)</span>` : ''}</p>
        ${p.origin ? `<p class="small" style="margin:4px 0 0"><i>${esc(p.origin)}</i></p>` : ''}
        <p style="margin:6px 0 0"><span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span> <span class="small dim">${p.qi} / ${p.qi_need} qi</span></p>${bar(p.qi_pct, 'violet')}</div></div>
      ${bt}
      <p style="margin-top:12px">Now: <b>${esc(p.doing)}</b></p>
      <div class="needs big"><span>Mood <b class="num">${p.mood}</b>${bar(p.mood, moodCls(p.mood))}</span><span>Food <b class="num">${p.food}</b>${bar(p.food, 'azure')}</span>
        <span>Rest <b class="num">${p.rest}</b>${bar(p.rest, 'azure')}</span><span>Joy <b class="num">${p.joy}</b>${bar(p.joy, 'azure')}</span><span>Health <b class="num">${p.health}</b>${bar(p.health, 'jade')}</span></div>
      <h3 style="margin-top:14px">Why they feel this way</h3>
      ${why.length ? `<ul class="list">${why.map((t) => `<li class="row"><span class="grow">${esc(t.label)}</span>${signed(t.v)}</li>`).join('')}</ul>
        <p class="dim small">Mood settles toward 50 plus these. Below about 20 a disciple may suffer a qi deviation.</p>` : '<p class="dim">Nothing in particular. Their mood rests at 50.</p>'}
      <h3 style="margin-top:14px">Cultivation speed <span class="tag violet num">×${p.qi_x}</span></h3>
      <ul class="list">${p.qi_why.map((t) => `<li class="row"><span class="grow">${esc(t.label)}</span><b class="num" style="color:var(--${t.x < 1 ? 'verm' : 'jade'})">×${t.x}</b></li>`).join('')}
        ${p.qi_work ? `<li class="row dim"><span class="grow">${esc(p.qi_work_label)}</span><b class="num">×${p.qi_work}</b></li>` : ''}</ul>
      <p class="dim small">Qi gathered per hour of meditation is multiplied by each of these. A manual of the root's own element is well suited (half again as strong); one of a clashing element is ill suited.</p>
      <h3 style="margin-top:14px">Artifact</h3>
      ${p.artifact ? `<p><span class="tag gold">${esc(p.artifact.name)}</span> <span class="small dim">${esc(p.artifact.text)}</span> <button class="btn quiet" data-equip="">Return to the vault</button></p>` : '<p class="dim">Carries nothing.</p>'}
      ${S.artifacts.filter((a) => !p.artifact || a.id !== p.artifact.id).length ? `<div class="row">${S.artifacts.filter((a) => !p.artifact || a.id !== p.artifact.id).map((a) => `<button class="btn" data-equip="${esc(a.id)}" title="${esc(a.text)}">Give: ${esc(a.name)}${a.owner ? ` (from ${esc(a.owner.split(' ')[0])})` : ''}</button>`).join('')}</div>
        <p class="dim small">One artifact each. Taking one from another disciple hurts them, and rivals notice who is favoured.</p>` : ''}
      ${p.master ? '' : `<h3 style="margin-top:14px">Standing</h3>
      <p class="small dim">A direct disciple stops labouring and only meditates, trains and researches, gathering qi a quarter faster, but expects a bed and some ease. The sect can spare ${S.direct_cap} (${S.direct_n} chosen).</p>
      <button class="btn" data-direct="${p.direct ? '0' : '1'}">${p.direct ? 'Return them to ordinary duties' : 'Take as a direct disciple'}</button>`}
      <h3 style="margin-top:14px">Lineage and road</h3>
      <ul class="list">
        <li class="row"><span class="grow">Master: <b>${p.mentor ? esc(p.mentor) : p.master ? 'none (you lead the sect)' : 'none'}</b>${p.student ? ` · Personal disciple: <b>${esc(p.student)}</b>` : ''}</span>
          ${p.mentors.map((m) => `<button class="btn" data-mentor="${esc(m.id)}">Kneel to ${esc(m.name)}</button>`).join('')}</li>
        ${p.mentor ? `<li><span class="small">Trust in their master: <b class="num">${p.trust}</b>/100</span>
          <div class="track"><i style="width:${p.trust}%"></i>${p.station_marks.map((m) => `<span class="${m.done ? 'done' : ''}" style="left:${m.at}%" title="At ${m.at}: their master ${esc(m.text)}">${m.done ? '◆' : '◇'}</span>`).join('')}</div>
          <span class="dim small">Grows a little each day they are both home, and a lot when the master guards a breakthrough or they fight side by side. Each mark is an evening and a gift.</span></li>` : ''}
        <li class="row"><span class="grow">Dao companion: <b>${p.companion ? esc(p.companion) : 'none'}</b></span>
          ${p.can_bind.map((m) => `<button class="btn" data-bind="${esc(m.id)}">Bind with ${esc(m.name)}</button>`).join('')}</li>
        <li class="row"><span class="grow">Path: <b>${p.path ? esc(p.path) : 'none yet'}</b>${p.can_path ? '' : p.path ? '' : ' <span class="dim small">(chosen at Foundation Establishment)</span>'}</span>
          ${p.can_path ? S.paths.map((x) => `<button class="btn" data-path="${esc(x.id)}" title="${esc(x.text)}">${esc(x.name)}</button>`).join('') : ''}</li>
        ${p.beast ? `<li><span class="tag jade">🐾 ${esc(p.beast.name)}</span> <span class="small dim">+${p.beast.bonus}% fighting strength, growing with age; +3 mood.</span></li>` : ''}
        <li class="row"><span class="grow">Merit: <b class="num">${p.merit}</b> <span class="dim small">earned by work and at the gate; spent on artifacts from the vault</span></span></li>
        ${p.fates.map((f) => `<li><span class="tag violet">Fate: ${esc(f.name)}</span> <span class="small dim">${esc(f.text)}</span></li>`).join('')}
        ${p.demon ? `<li class="row"><span class="grow"><span class="tag red">Heart demon ×${p.demon}</span> <span class="small dim">-${8 * p.demon} to every breakthrough, -${3 * p.demon} mood</span></span><button class="btn seal" data-demon>Face it</button></li>` : ''}
        ${p.toxin > 3 ? `<li><span class="tag red">Pill toxin ${p.toxin}</span> <span class="small dim">Too many pills. It fades with time.</span></li>` : ''}
      </ul>
      <div class="row">${p.can_lead_branch ? '<button class="btn" data-branch title="They leave for good with two disciples. Needs Main Hall 4, eight disciples and 100 spirit stones.">Send to found a branch sect</button>' : ''}${p.can_retreat ? '<button class="btn" data-retreat title="Twelve days sealed in: no work, a great deal of qi, a chance of an epiphany or a qi deviation.">Closed-door seclusion (10 rice)</button>' : ''}
        ${p.can_marrow ? '<button class="btn" data-marrow>Give the Marrow-Cleansing Pill</button>' : ''}</div>
      ${(() => { const open = p.meridians.filter((n) => n.open).length; const can = p.meridians.some((n) => !n.open && !n.blocked);
        return `<details class="fold meridians" ${can ? 'open' : ''}><summary>Meridians <span class="tag violet num">${p.points} point${p.points === 1 ? '' : 's'}</span>
          <span class="dim small">${open} of ${p.meridians.length} open${can ? ' · one can be opened now' : ' · nothing to open yet; a point comes with every stage reached'}</span></summary>`; })()}
      <div class="nodes">${p.meridians.map((n) => `<button class="node ${n.open ? 'open' : n.blocked ? 'blocked' : 'ready'}" data-node="${esc(n.id)}" ${n.open || n.blocked ? 'disabled' : ''} title="${esc(n.open ? 'Open' : n.blocked || 'Tap to open')}">
          <b>${esc(n.name)}</b><small>${esc(n.text)}</small><em>${n.open ? 'Open' : n.blocked ? esc(n.blocked) : `Open for ${n.cost} point${n.cost > 1 ? 's' : ''}`}</em></button>`).join('')}</div>
      <p class="dim small">One point comes with every stage reached. What is opened stays open.</p></details>
      <h3 style="margin-top:14px">Bonds</h3>
      ${p.bonds.length ? `<ul class="list">${p.bonds.map((x) => `<li class="row"><span class="grow">${esc(x.name)}${x.kind ? ` <span class="tag ${x.kind === 'rival' ? 'red' : 'jade'}">${esc(x.kind)}</span>` : ''}</span>${signed(x.v)}</li>`).join('')}</ul>
        <p class="dim small">Disciples who work side by side talk. Friends (+30) steady each other and guard a breakthrough; rivals (-30) sour the mood, and may come to blows.</p>`
        : '<p class="dim">They have not grown close to anyone yet, nor fallen out.</p>'}
      ${p.arts.length ? `<h3 style="margin-top:14px">Practising</h3><p>${p.arts.map((a) => `<span class="tag gold">${esc(a)}</span>`).join(' ')}</p>` : ''}
      <h3 style="margin-top:14px">Traits</h3>
      <ul class="list">${p.traits.map((t) => `<li><b>${esc(t.name)}</b> <span class="dim small">${esc(t.text)}</span></li>`).join('')}</ul>
      <h3 style="margin-top:14px">Skills</h3>
      <div class="skills">${p.skills.map((s) => `<span>${esc(s.name)} <b class="num">${s.lv}</b>${s.passion ? ` ${flames(s.passion)}` : ''}${bar(s.lv * 5, 'jade')}</span>`).join('')}</div>
      <hr><div class="row"><button class="btn" data-heal ${pills && (p.health < 100 || p.sick) ? '' : 'disabled'}>Give a pill (${pills})</button>
        ${p.master ? '' : '<button class="btn quiet" data-banish>Send away</button>'}</div>`);
    const s = $('#sheet');
    const heal = $('[data-heal]', s); if (heal) heal.onclick = async () => { await order('pill', { pawn: id }); pawnSheet(id); };
    const ban = $('[data-banish]', s); if (ban) ban.onclick = async () => { if (!confirm(`Send ${p.name} away from the sect for good?`)) return; closeSheet(); await order('banish', { pawn: id }); };
    s.querySelectorAll('[data-equip]').forEach((b) => { b.onclick = async () => { await order('equip', { pawn: id, artifact: b.dataset.equip }); pawnSheet(id); }; });
    const dd = $('[data-direct]', s); if (dd) dd.onclick = async () => { await order('direct', { pawn: id, on: dd.dataset.direct === '1' }); pawnSheet(id); };
    s.querySelectorAll('[data-mentor]').forEach((b) => { b.onclick = async () => { await order('apprentice', { pawn: id, other: b.dataset.mentor }); pawnSheet(id); }; });
    s.querySelectorAll('[data-bind]').forEach((b) => { b.onclick = async () => { await order('companion', { pawn: id, other: b.dataset.bind }); pawnSheet(id); }; });
    s.querySelectorAll('[data-path]').forEach((b) => { b.onclick = async () => { if (!confirm('A path is chosen once and for life. Choose this one?')) return; await order('path', { pawn: id, path: b.dataset.path }); pawnSheet(id); }; });
    const dm = $('[data-demon]', s); if (dm) dm.onclick = async () => { closeSheet(); await order('face-demon', { pawn: id }); };
    const rt = $('[data-retreat]', s); if (rt) rt.onclick = async () => { if (!confirm(`Seal ${p.name} in for twelve days?`)) return; closeSheet(); await order('retreat', { pawn: id }); };
    s.querySelectorAll('[data-node]').forEach((b) => { b.onclick = async () => { await order('meridian', { pawn: id, node: b.dataset.node }); pawnSheet(id); }; });
    const brn = $('[data-branch]', s); if (brn) brn.onclick = async () => { if (!confirm(`${p.name} and two disciples will leave the sect for good to found a branch. Send them?`)) return; const r = await order('branch', { pawn: id }); if (r.ok !== false) closeSheet(); };
    const mw = $('[data-marrow]', s); if (mw) mw.onclick = async () => { await order('marrow', { pawn: id }); pawnSheet(id); };
    const go = $('[data-attempt]', s);
    if (go) go.onclick = async () => {
      go.disabled = true;
      const res = await order('attempt', { pawn: id }, true);
      if (res.ok === false) { toast(res.error); return; }
      closeSheet();
      paintScenes();                                  // the result arrives as a scene card, success and failure framed differently
      if (shown < 0 && res.event) toast(res.event.title, res.success ? 3500 : 6000);
    };
  }

  function tripSheet(place) {
    const pl = S.places.find((x) => x.id === place); if (!pl) return;
    const picked = new Set(); let stance = 'balanced';
    const able = S.pawns.filter((p) => !p.master && !p.away && p.health >= 40);
    const draw = () => {
      openSheet(`<h2>${esc(pl.name)}</h2><p class="dim">${esc(pl.text)} ${pl.hours} hours there and back.</p>
        <h3>Who goes (one to three)</h3>
        <div class="pawns">${able.map((p) => `<button class="pawn ${picked.has(p.id) ? 'chosen' : ''}" data-pick="${esc(p.id)}">${face(p, 40)}<span class="grow"><b>${esc(p.name)}</b>
          <span class="doing">strength ${p.power} · gathering ${p.skills.find((s) => s.id === 'gather').lv} · scholarship ${p.skills.find((s) => s.id === 'scholar').lv} · alchemy ${p.skills.find((s) => s.id === 'craft').lv}</span></span></button>`).join('') || '<p class="dim">Nobody is fit to travel.</p>'}</div>
        <p class="dim small">Strength decides how much comes home and who is hurt. Halfway there the party will send word and ask what to do; what you can choose depends on who went.</p>
        <h3>How they travel</h3>
        <div class="row">${S.stances.map((x) => `<button class="btn ${stance === x.id ? 'primary' : ''}" data-stance="${esc(x.id)}" title="${esc(x.text)}">${esc(x.name)}</button>`).join('')}</div>
        <p class="dim small">${esc((S.stances.find((x) => x.id === stance) || {}).text || '')}</p>
        <button class="btn primary big" data-send ${picked.size ? '' : 'disabled'} style="margin-top:10px">Send ${picked.size || ''} ${picked.size === 1 ? 'disciple' : 'disciples'}</button>`);
      const s = $('#sheet');
      s.querySelectorAll('[data-pick]').forEach((b) => { b.onclick = () => { const k = b.dataset.pick; if (picked.has(k)) picked.delete(k); else if (picked.size < 3) picked.add(k); draw(); }; });
      s.querySelectorAll('[data-stance]').forEach((b) => { b.onclick = () => { stance = b.dataset.stance; draw(); }; });
      $('[data-send]', s).onclick = async () => { const r = await order('expedition', { place, pawns: [...picked], stance }); if (r.ok !== false) closeSheet(); };
    };
    draw();
  }

  function roomSheet(id) {
    const r = S.rooms.find((x) => x.id === id); if (!r) return;
    openSheet(`<h2>${esc(r.name)}</h2><p class="dim">${r.open ? `Level ${r.level} of ${r.max}` : 'Not built yet'}${r.queued ? ' · under construction' : ''}</p><p>${esc(r.effect)}</p>
      ${r.cost ? (r.locked ? `<p class="tag red">${esc(r.locked)}</p>`
        : `<button class="btn ${r.affordable ? 'primary' : ''}" data-go ${r.affordable ? '' : 'disabled'}>${r.open ? 'Raise' : 'Build'}: ${esc(costText(r.cost))}</button>
           <p class="dim small" style="margin-top:8px">${r.affordable ? `Materials are spent now. ${esc(readyIn(r.hours))}. Disciples with Build as a priority help.`
             : S.builders.busy >= S.builders.n ? 'Every builder is busy. One comes free when a job finishes.' : 'You do not have the materials yet.'}</p>`)
        : '<p class="tag gold">Highest level reached</p>'}`);
    const go = $('[data-go]', $('#sheet')); if (go) go.onclick = async () => { closeSheet(); await order('build', { room: id }); };
  }

  function paintStyle() {
    const root = $('#sect-root'); if (!root) return;
    const hex = /^#[0-9a-f]{6}$/i.test(S.style.hex) ? S.style.hex : '#e9b44c';      // a known colour from the server, checked anyway
    root.style.setProperty('--sect-colour', hex);
  }

  function paintLight() {
    const d = $('#daylight'); if (!d) return;
    const hh = S.hod;
    d.className = `daylight ${hh >= 21 || hh < 5 ? 'night' : hh < 8 ? 'dawn' : hh >= 18 ? 'dusk' : 'day'} ${S.season === 'Winter' ? 'winter' : ''}`;
  }

  let masterSig = '';
  function paintMaster() {
    const z = $('#z-master'); if (!z) return;
    const html = h.masterPanel();                       // drawn from the live sect view (setSect keeps it current), not the page-load copy
    if (html === masterSig) return;
    masterSig = html;
    z.innerHTML = html;
  }

  function paint() { paintStyle(); paintTop(); paintEvent(); paintScene(); paintHall(); paintLight(); paintMaster(); paintTabs(); paintScenes(); }

  /* ---------------- result scenes: a big outcome gets a framed card ---------------- */
  function sceneCard(x) {
    const mood = x.kind === 'funeral' ? 'calm' : x.ok ? 'happy' : 'oops';
    const tone = (ok) => (ok === true ? 'up' : ok === false ? 'down' : '');
    return `<section class="breakthrough result scenecard ${x.ok ? 'won' : 'lost'} k-${esc(x.kind)}" style="background-image:${x.ok
        ? 'linear-gradient(#120d0a66,#120d0ae6 62%)' : 'linear-gradient(#1a080a8c,#0d0607f0 58%)'},url(${scene(x.kind, x.painted)})">
        <p class="verdict">${esc(x.verdict)} <span class="dim">· ${esc(x.when)}</span></p>
        <h2>${esc(x.title)}</h2>
        ${x.party.length ? `<div class="party">${x.party.map((p) => `<span class="who">${portrait(p.id + p.name, { root: p.root, kind: p.master ? 'master' : '', size: 44, mood })}<small>${esc(p.name)}</small></span>`).join('')}</div>` : ''}
        ${x.text ? `<p class="story">${esc(x.text)}</p>` : ''}
        ${x.lines.length ? `<ul class="beats">${x.lines.map((l) => `<li class="${tone(l.ok)}">${l.who ? `<b>${esc(l.who)}</b> ` : ''}${esc(l.text)}</li>`).join('')}</ul>` : ''}
        ${x.changes.length ? `<div class="changes">${x.changes.map((c) => `<span class="chg ${c.good ? 'up' : 'down'}"><b class="num">${c.signed && c.v > 0 ? '+' : ''}${c.v}</b> ${esc(c.label)}</span>`).join('')}</div>` : ''}
      </section>
      <button class="btn primary big scene-ok" data-seen>${x.kind === 'funeral' ? 'Bow, and go on' : 'Continue'}</button>`;
  }
  function dismissScene(id) {
    gone.add(id);
    if (shown === id) shown = -1;
    order('scene-seen', { index: id }, true);
  }
  function paintScenes() {
    const sheet = $('#sheet');
    if (shown >= 0 && sheet.hidden) dismissScene(shown);          // closed with Escape or the backdrop: that counts as seen
    if (shown >= 0 || !sheet.hidden || !view.isConnected) return;
    const x = (S.scenes || []).find((y) => !gone.has(y.id));
    if (!x) return;
    shown = x.id;
    openSheet(sceneCard(x));
    const ok = $('[data-seen]', sheet);
    ok.onclick = () => { closeSheet(); dismissScene(x.id); };
    ok.focus({ preventScroll: true });
  }

  view.innerHTML = `<div id="sect-root"><div id="z-top"></div>
    <div id="z-event"></div><section class="panel scenewrap"><div id="z-scene"></div><div id="z-hall"></div></section>
    ${h.studyStrip()}
    <section class="panel" id="z-tabs" style="margin-top:14px"></section>
    <div class="grid2 studyrow" id="z-study">${h.todayPanel()}<div id="z-master"></div></div></div>`;
  h.bindToday(view);
  paint();
  stop();
  timer = setInterval(beat, 1000);
  return { stop, order };
}
