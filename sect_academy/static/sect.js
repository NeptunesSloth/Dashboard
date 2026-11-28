// The sect screen: a colony sim you watch and steer. The server owns the simulation;
// this module draws it, sends orders, and asks for sim hours as real time passes.
// All text from the server goes through esc(); every number arrives already cast.

import { ICON, backdrop, cellRect, floorRect, gridCut, place, portrait, roomThumb, roomTile, scene, sectScene, setFaces } from '/art.js';

const SPEED_KEY = 'sect.speed';
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

  // Posting by hand: drag a disciple from the roster onto a room (or tap one, then a room). While a disciple is in
  // hand every room says how well they suit it and how many places it has.
  let selPawn = '';                                 // the disciple picked up (tap) or being dragged
  let dragging = false;
  function postTo(room) {
    const pid = selPawn; selPawn = ''; dragging = false; sceneSig = '';
    const r = S.rooms.find((x) => x.id === room);
    if (pid && r && r.slots) order('post', { pawn: pid, room });
    else { paintScene(); if (pid && r) toast(`No one is posted to the ${r.name}.`); }
  }
  function cancelPick() { if (!selPawn) return; selPawn = ''; dragging = false; sceneSig = ''; paintScene(); }
  // The room under the pointer: on the painting, or its row in the rail (look B).
  const dropId = (el) => { const n = el && el.closest('[data-room], [data-railroom]'); return n ? n.dataset.room || (n.dataset.railroom === 'vault' ? '' : n.dataset.railroom) : ''; };
  function startDrag(e, pid, btn) {
    if (e.button !== undefined && e.button !== 0) return;
    const x0 = e.clientX; const y0 = e.clientY; let ghost = null;
    const move = (ev) => {
      if (!ghost && Math.hypot(ev.clientX - x0, ev.clientY - y0) < 8) return;
      if (!ghost) {
        selPawn = pid; dragging = false; sceneSig = ''; paintScene(); dragging = true;
        ghost = document.createElement('div'); ghost.className = 'dragghost'; ghost.innerHTML = btn.querySelector('.face') ? btn.querySelector('.face').outerHTML : '';
        document.body.appendChild(ghost);
      }
      ghost.style.left = `${ev.clientX}px`; ghost.style.top = `${ev.clientY}px`;
      const over = document.elementFromPoint(ev.clientX, ev.clientY);
      const id = dropId(over);
      document.querySelectorAll('[data-hot].over').forEach((n) => { if (n.dataset.hot !== id) n.classList.remove('over'); });
      if (id) document.querySelectorAll('#z-scene [data-hot]').forEach((n) => { if (n.dataset.hot === id) n.classList.add('over'); });
    };
    const up = (ev) => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up);
      if (!ghost) return;                           // a tap: the click handler picks the disciple up
      ghost.remove();
      heldAt = Date.now();
      const over = ev.type === 'pointerup' ? document.elementFromPoint(ev.clientX, ev.clientY) : null;
      const id = dropId(over);
      if (id) postTo(id); else cancelPick();
    };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up);
  }

  // Placing on the grid: a new room (from the Build ledger) or a room being moved waits here for an empty alcove.
  let placing = null;                               // { mode: 'build' | 'move', room }
  let hotId = '';                                   // the room (or alcove) pointed at or focused: its words and rail row light up
  // TEMPORARY, for the owner to pick one: the look of the home map's words.
  //   'A' quiet until asked: a name carved on the beam under each room, the rest on hover, focus or while dragging.
  //   'B' ledger rail: no words on the painting at rest; the rooms are listed floor by floor beside it.
  // Change the letter here (or, to compare without editing: localStorage.setItem('sect.maplook', 'B') and reload).
  const MAP_LOOK = (() => { try { const v = localStorage.getItem('sect.maplook'); if (v === 'A' || v === 'B') return v; } catch (e) { /* no storage */ } return 'A'; })();
  const roomOf = (id) => S.rooms.find((x) => x.id === id);
  const box = (r) => `left:${r[0].toFixed(3)}%;top:${r[1].toFixed(3)}%;width:${r[2].toFixed(3)}%;height:${r[3].toFixed(3)}%`;
  const ORD = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth'];
  const FLOOR = ['ground floor', 'second floor', 'third floor', 'fourth floor', 'top floor'];
  function startPlacing(mode, room) {
    placing = { mode, room }; selPawn = ''; sceneSig = ''; paintScene();
    const m = $('#z-scene'); if (m) m.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
  function cancelPlacing() { if (!placing) return; placing = null; sceneSig = ''; paintScene(); }
  function pickCell(f, s) {
    if (!placing) { alcoveSheet(f, s); return; }
    const { mode, room } = placing; placing = null; sceneSig = '';
    order(mode === 'move' ? 'move-room' : 'build', { room, cell: [f, s] });
  }
  // A room's painted tiles, side by side (the Main Hall's own tile is two alcoves wide).
  function tilesHtml(id, w) {
    const t = roomTile(id); if (!t) return '';
    const n = id === 'main_hall' ? 1 : w;
    return `<span class="tiles" aria-hidden="true">${Array.from({ length: n }, () => `<i style="background-image:url(${t})"></i>`).join('')}</span>`;
  }
  // The half lantern and pillar at each outer edge of a room are finished by a sliver of the tile's other edge,
  // so a room beside an empty alcove still ends on a whole lantern.
  function capsHtml(id, p) {
    const t = roomTile(id); if (!t) return '';
    const [x, y, w, hh] = cellRect(p.f, p.s, p.w); const cw = 1.55; const k = id === 'main_hall' ? 2000 : 1000;
    const cap = (left, side, pos) => `<i class="cap ${side}" style="${box([left, y, cw + 0.15, hh])};background-image:url(${t});background-size:${k}% 100%;background-position:${pos}% 0" aria-hidden="true"></i>`;
    return cap(x - cw, 'l', 100) + cap(x + w - 0.15, 'r', 0);        // the right one tucks under the tile: no hairline between them
  }

  function paintScene() {
    const z = $('#z-scene'); if (!z) return;
    if (dragging && z.firstChild) return;          // never repaint under a drag
    const building = S.builds.map((b) => b.room);
    const staff = {};
    S.pawns.forEach((p) => {
      if (p.away) return;
      const site = p.doing === 'build' ? building[0] : SITE_OF[p.doing] || 'main_hall';
      if (site) (staff[site] = staff[site] || []).push(p);
    });
    const G = S.grid;
    if (placing && !(placing.mode === 'move' ? placing.room === 'vault' || (roomOf(placing.room) || {}).plot : roomOf(placing.room) && !roomOf(placing.room).plot)) placing = null;
    const trayText = (r) => (r.tray || []).slice(0, 2).map((t) => `+${t.n} ${t.name}`).join(' ');
    const held = selPawn ? S.pawns.find((p) => p.id === selPawn) : null;
    const sig = JSON.stringify([S.rooms.map((r) => [r.level, r.affordable, trayText(r), r.tray_full, r.posted.length, r.slots, r.plot, r.wing, r.wide && r.wide.affordable]), building, G, placing,
      Object.entries(staff).map(([k, v]) => k + v.map((p) => p.id).join()), S.treasures.length, selPawn, dragging, S.pawns.map((p) => p.id + p.post)]);
    if (sig === sceneSig && z.firstChild) return;
    sceneSig = sig;
    const placed = S.rooms.filter((r) => r.plot);
    const caps = placed.filter((r) => r.open).map((r) => capsHtml(r.id, r.plot)).join('') + (G.vault ? capsHtml('vault', G.vault) : '');
    // Nothing is boxed on the painting. A room's name is carved on the floor beam under it (`.nm`, with its level as a
    // small numeral); a line of plain words under the lintel (`.nt`) says the rest, and only when asked: on hover or
    // focus, or while a disciple is in hand. Both live in a layer over the rooms, so a beam is never painted over.
    const fitOf = (r) => (held ? (r.slots ? (r.posted.length >= r.slots && held.post !== r.id ? 'full' : held.fit[r.id] || 'poor') : 'none') : '');
    const FIT_WORD = { good: 'suits them well', fair: 'suits them', poor: 'suits them poorly', full: 'is full', none: 'takes no post' };
    const freeText = (r) => { const n = Math.max(0, r.slots - r.posted.length); return `${n} place${n === 1 ? '' : 's'} free`; };
    const fitNote = (r) => { const f = fitOf(r); return f === 'none' ? 'no post here' : f === 'full' ? `full, ${r.posted.length} of ${r.slots}` : `${FIT_WORD[f]} · ${freeText(r)}`; };
    const restNote = (r) => [r.open && r.slots ? `${r.posted.length} of ${r.slots} posted` : '', r.affordable ? 'ready to raise' : '', r.wide && r.wide.affordable ? 'a wing can be built' : ''].filter(Boolean).join(' · ');
    const roomAria = (r) => `${esc(r.name)}, ${r.open ? `level ${r.level} of ${r.max}` : 'being built'}${r.wide && r.wide.w > 1 ? `, ${esc(r.wide.word)}` : ''}${r.affordable ? ', you can afford the next level' : ''}${held ? `: post ${esc(held.name)} here, ${FIT_WORD[fitOf(r)] || ''}${r.slots ? `, ${r.posted.length} of ${r.slots} places taken` : ''}` : ''}`;
    const trayHtml = (r) => r.tray.slice(0, 2).map((t) => `<b class="num">+${t.n}</b> ${esc(t.name)}`).join(' ');
    const trayAria = (r) => `${esc(r.name)} made ${esc(trayText(r))} since the last look. Inspect the work`;
    const beam = ([x, y, w, hh], f, id, cls, html) => `<span class="nm ${cls}" data-hot="${esc(id)}" aria-hidden="true" style="left:${(x + w / 2).toFixed(3)}%;top:${(y + hh + (f === 0 ? -0.9 : 0.5)).toFixed(3)}%">${html}</span>`;
    // (at the painting's two edges the line is set flush with the room, so a long one is never cut off)
    const lintel = ([x, y, w, hh], id, cls, text, s0) => { const side = s0 === 0 ? 'al-l' : s0 + w >= 6 ? 'al-r' : ''; const at = side === 'al-l' ? x + 3.4 : side === 'al-r' ? x + w - 3.4 : x + w / 2;
      return text ? `<span class="nt ${cls} ${side}" data-hot="${esc(id)}" aria-hidden="true" style="left:${at.toFixed(3)}%;top:${(y + hh * 0.17).toFixed(3)}%">${esc(text)}</span>` : ''; };
    let words = '';
    const rooms = placed.map((r) => {
      const w = r.plot.w; const all = staff[r.id] || []; const show = Math.min(all.length, 3 * w + 1);
      const crew = all.slice(0, show).map((p) => face(p, 24)).join('') + (all.length > show ? `<b class="more">+${all.length - show}</b>` : '');
      const fit = fitOf(r); const rect = cellRect(r.plot.f, r.plot.s, w);
      words += beam(rect, r.plot.f, r.id, `${r.affordable ? 'can' : ''} ${fit ? `fit-${fit}` : ''}`, `<b>${esc(r.name)}</b>${r.open ? `<i>${r.level}</i>` : '<em>being built</em>'}`)
        + lintel(rect, r.id, fit ? `fit-${fit}` : '', held ? fitNote(r) : restNote(r), r.plot.s);
      return `<button class="room w${w} ${r.open ? '' : 'closed'} ${building.includes(r.id) && !r.wing ? 'building' : ''} ${r.affordable ? 'can' : ''} ${r.tray.length ? 'tray' : ''} ${r.tray_full ? 'trayfull' : ''} ${fit ? `fit-${fit}` : ''}" data-room="${esc(r.id)}" data-hot="${esc(r.id)}" style="${box(rect)};--w:${w}"
        aria-label="${roomAria(r)}">
        ${tilesHtml(r.id, w)}<span class="lit" aria-hidden="true"></span>
        <span class="crew" aria-hidden="true">${crew}</span></button>`;
    }).join('');
    // A wing being built: the room's tile in the next alcove, still dark, until the wall comes down.
    const wings = placed.filter((r) => r.wing).map((r) => {
      const rect = cellRect(r.wing.f, r.wing.s, 1);
      words += beam(rect, r.wing.f, `wing-${r.id}`, 'site', '<em>a wing, being built</em>');
      return `<button class="room wingsite building" data-wingsite="${esc(r.id)}" data-hot="wing-${esc(r.id)}" style="${box(rect)}" aria-label="A wing of the ${esc(r.name)}, being built">
        ${tilesHtml(r.id === 'main_hall' ? '' : r.id, 1)}<span class="lit" aria-hidden="true"></span></button>`;
    }).join('');
    if (G.vault) words += beam(cellRect(G.vault.f, G.vault.s, 1), G.vault.f, 'vault', held ? 'fit-none' : '', `<b>Treasure Vault</b>${S.treasures.length ? `<i>${S.treasures.length}</i>` : ''}`);
    // What a room's crew made: look A writes it over the room, softly, and only once a morning's work waits (a fresh
    // tray shows when you point at the room); look B keeps it in the rail. Either way the room itself glows.
    const trays = held || placing || MAP_LOOK !== 'A' ? '' : placed.filter((r) => r.tray.length).map((r) => {
      const [x, y, w, hh] = cellRect(r.plot.f, r.plot.s, r.plot.w);
      return `<button class="traybtn ${r.tray_full ? 'full' : ''}" data-tray="${esc(r.id)}" data-hot="${esc(r.id)}" style="left:${x + w / 2}%;top:${y + hh * 0.33}%"
        aria-label="${trayAria(r)}">${trayHtml(r)}</button>`;
    }).join('');
    // Empty alcoves are where you build: nothing is written on one until you point at it. With a room in hand
    // (placing) every one of them is lit.
    const pr = placing ? (placing.room === 'vault' ? { name: 'Treasure Vault' } : roomOf(placing.room)) : null;
    const alcoves = held ? '' : G.free.map(([f, s]) => {
      const rect = cellRect(f, s, 1);
      words += beam(rect, f, `cell-${f}-${s}`, `empty ${placing ? 'ok' : ''}`, `<em>${placing ? 'place here' : 'build here'}</em>`);
      return `<button class="alcove ${placing ? 'ok' : ''}" data-cell="${f},${s}" data-hot="cell-${f}-${s}" style="${box(rect)}"
        aria-label="Empty alcove, ${FLOOR[f]}, ${ORD[s]} from the left. ${pr ? `Put the ${esc(pr.name)} here` : 'Build here'}"></button>`;
    }).join('');
    // Only the floors in use are shown: the painting is cut under the roof, so the building grows as the Hall rises.
    const top = Math.max(0, ...placed.map((r) => r.plot.f), ...placed.filter((r) => r.wing).map((r) => r.wing.f), G.vault ? G.vault.f : 0);
    const show = Math.max(G.open, top + 1);
    const [cut, roofH] = gridCut(show); const keep = 100 - cut;
    const lockText = (f) => (f === G.open ? `This floor opens at Main Hall ${G.next_floor}` : 'Not yet opened');
    const locks = Array.from({ length: show - G.open }, (_, i) => G.open + i).map((f) => `<div class="floorlock" style="${box(floorRect(f))}">${MAP_LOOK === 'A' ? `<span>${lockText(f)}</span>` : ''}</div>`).join('');
    // Look B, the ledger rail: the painting carries no words at rest; beside it each floor lists its rooms in plain
    // serif (name, level, places taken, what was made), level with that floor. A row and its room light together.
    let rail = '';
    if (MAP_LOOK === 'B') {
      const yOf = (v) => 100 - (100 - v) * 100 / keep;
      const row = (r) => {
        const all = staff[r.id] || []; const fit = fitOf(r);
        const crew = held ? fitNote(r).replace(/places? free/, 'free') : !r.open ? 'being built' : r.wing ? 'a wing being built' : r.slots ? `${r.posted.length} of ${r.slots}` : all.length ? `${all.length} here` : '';
        const made = !held && !placing && r.tray.length ? `<button class="rmade ${r.tray_full ? 'full' : ''}" data-tray="${esc(r.id)}" aria-label="${trayAria(r)}">${trayHtml(r)}</button>` : '';
        return `<div class="rrow ${r.affordable ? 'can' : ''} ${r.tray_full ? 'trayfull' : ''} ${fit ? `fit-${fit}` : ''}" data-hot="${esc(r.id)}"><button class="rname" data-railroom="${esc(r.id)}" aria-label="${roomAria(r)}">${esc(r.name)}${r.open ? `<i>${r.level}</i>` : ''}</button><span class="rcrew">${esc(crew)}</span>${made}</div>`;
      };
      const floors = Array.from({ length: show }, (_, f) => f).reverse().map((f) => {
        const here = placed.filter((r) => r.plot.f === f).map((r) => [r.plot.s, row(r)]);
        if (G.vault && G.vault.f === f) here.push([G.vault.s, `<div class="rrow ${held ? 'fit-none' : ''}" data-hot="vault"><button class="rname" data-railroom="vault" aria-label="Treasure vault: manuals, treasures and the world beyond">Treasure Vault</button><span class="rcrew">${S.treasures.length ? `${S.treasures.length} kept` : ''}</span></div>`]);
        here.sort((p, q) => p[0] - q[0]);
        const [, fy, , fh] = floorRect(f);
        return `<div class="rfloor" style="top:${yOf(fy).toFixed(3)}%;height:${(fh * 100 / keep).toFixed(3)}%">${f >= G.open ? `<p class="rnone">${lockText(f)}</p>` : here.length ? here.map((x) => x[1]).join('') : '<p class="rnone">Empty</p>'}</div>`;
      }).join('');
      rail = `<div class="rail" role="group" aria-label="The rooms, floor by floor"><p class="rcap" style="height:${(100 * roofH / keep).toFixed(3)}%">${held ? `where ${esc(held.name.split(' ').slice(-1)[0])} would fit` : 'room and level · posted · made since dawn'}</p>${floors}</div>`;
    }
    const roster = S.pawns.filter((p) => !p.away).map((p) => `<button class="token ${selPawn === p.id ? 'on' : ''}" data-token="${esc(p.id)}" aria-pressed="${selPawn === p.id}"
        aria-label="${esc(p.name)}${p.post ? `, posted to the ${esc((S.rooms.find((r) => r.id === p.post) || {}).name || '')}` : ''}. Pick up to post">${face(p, 34)}<span><b>${esc(p.name.split(' ').slice(-1)[0])}</b><small>${esc(p.post ? (S.rooms.find((r) => r.id === p.post) || {}).name || '' : p.doing || '')}</small></span></button>`).join('');
    const hint = held ? `Now choose a room for ${esc(held.name)}. <button class="btn" data-unpick>Cancel</button>`
      : pr ? `Choose an empty alcove for the ${esc(pr.name)}. <button class="btn" data-unplace>Cancel</button>`
        : 'Drag a disciple onto a room to post them there, or tap one and then a room. Tap an empty alcove to build in it.';
    z.innerHTML = `<div class="mapwrap look${MAP_LOOK}"><div class="hq ${held ? 'holding' : ''} ${placing ? 'placing' : ''}" style="aspect-ratio:1620 / ${(9.71 * keep).toFixed(2)}"><div class="hqin" style="height:${(10000 / keep).toFixed(3)}%">${sectScene()}${locks}${caps}${rooms}${wings}
      ${G.vault ? `<button class="room vault ${held ? 'fit-none' : ''}" data-vault data-hot="vault" style="${box(cellRect(G.vault.f, G.vault.s, 1))}" aria-label="Treasure vault: manuals, treasures and the world beyond">
        ${tilesHtml('vault', 1)}<span class="lit" aria-hidden="true"></span></button>` : ''}
      ${alcoves}<div class="daylight" id="daylight"></div><div class="words">${words}</div>${trays}</div>
      ${cut > 0 ? `<div class="roof" style="height:${(100 * roofH / keep).toFixed(3)}%" aria-hidden="true"></div>` : ''}</div>${rail}</div>
      <div class="roster" role="group" aria-label="Post disciples to rooms"><span class="rhint">${hint}</span><div class="tokens">${roster}</div></div>`;
    // Pointing at a room (or its rail row, its tray, or tabbing to any of them) lights everything that belongs to it.
    const wrap = z.firstElementChild;
    const hot = (id) => { if (id === hotId) return; hotId = id; z.querySelectorAll('[data-hot]').forEach((n) => n.classList.toggle('hot', !!id && n.dataset.hot === id)); };
    const hotOf = (t) => { const n = t && t.closest ? t.closest('[data-hot]') : null; return n ? n.dataset.hot : ''; };
    wrap.onmouseover = (e) => { if (!dragging) hot(hotOf(e.target)); };
    wrap.onmouseleave = () => { if (!dragging) hot(hotOf(document.activeElement)); };
    wrap.addEventListener('focusin', (e) => hot(hotOf(e.target)));
    wrap.addEventListener('focusout', () => hot(''));
    const was = hotId; hotId = ''; hot(was);
    // a disciple picked up by tap: focus stays on their token, so Escape (handled on this zone) puts them down
    if (held && !z.contains(document.activeElement)) { const t = $('.token.on', z); if (t) t.focus({ preventScroll: true }); }
    z.querySelectorAll('[data-railroom]').forEach((b) => { b.onclick = () => {
      if (Date.now() - heldAt < 400) return;
      const id = b.dataset.railroom;
      if (id === 'vault') { const v = $('[data-vault]', z); if (v) v.click(); } else if (selPawn) postTo(id); else roomSheet(id);
    }; });
    z.querySelectorAll('[data-room]').forEach((b) => { b.onclick = () => { if (Date.now() - heldAt < 400) return; if (selPawn) postTo(b.dataset.room); else roomSheet(b.dataset.room); }; });
    z.querySelectorAll('[data-wingsite]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.wingsite); });
    z.querySelectorAll('[data-cell]').forEach((b) => { b.onclick = () => { const [f, s] = b.dataset.cell.split(',').map(Number); pickCell(f, s); }; });
    z.querySelectorAll('[data-token]').forEach((b) => {
      b.onpointerdown = (e) => startDrag(e, b.dataset.token, b);
      b.onclick = () => { if (Date.now() - heldAt < 400) return; placing = null; selPawn = selPawn === b.dataset.token ? '' : b.dataset.token; sceneSig = ''; paintScene(); };
    });
    z.querySelectorAll('[data-tray]').forEach((b) => { b.onclick = () => collect(b); });
    const un = $('[data-unpick]', z); if (un) un.onclick = cancelPick;
    const up = $('[data-unplace]', z); if (up) up.onclick = cancelPlacing;
    z.onkeydown = (e) => { if (e.key === 'Escape' && (selPawn || placing)) { e.stopPropagation(); cancelPick(); cancelPlacing(); } };
    const vb = $('[data-vault]', z);
    if (vb) vb.onclick = () => { if (selPawn) { cancelPick(); return; } tab = 'world'; sessionStorage.setItem('sect.tab', tab); paintTabs(); $('#z-tabs').scrollIntoView({ behavior: 'smooth' }); };
    paintLight();
  }

  // Tapping a tray: the numbers count up and lift away, then the server's answer (the crew's thought) is toasted.
  function collect(b) {
    if (b.classList.contains('taken')) return;
    b.classList.add('taken');
    const nums = [...b.querySelectorAll('.num')].map((n) => [n, Number(n.textContent.replace(/\D/g, '')) || 0]);
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 450);
      nums.forEach(([n, v]) => { n.textContent = `+${Math.round(v * k)}`; });
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    setTimeout(() => { sceneSig = ''; order('inspect', { room: b.dataset.tray }); }, 700);
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
    z.querySelectorAll('[data-place]').forEach((b) => { b.onclick = () => startPlacing('build', b.dataset.place); });
    z.querySelectorAll('[data-roomtile]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.roomtile); });
    z.querySelectorAll('[data-rushbuild]').forEach((b) => { b.onclick = () => rushSheet(Number(b.dataset.rushbuild)); });
    z.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => order('cancel-build', { index: Number(b.dataset.cancel) }); });
    z.querySelectorAll('[data-blueprint]').forEach((b) => { b.onclick = () => order('blueprint', { index: Number(b.dataset.blueprint) }); });
    z.querySelectorAll('[data-tech]').forEach((b) => { b.onclick = () => order('research', { tech: b.dataset.tech }); });
    z.querySelectorAll('details[data-fold]').forEach((d) => { d.ontoggle = () => {
      if (d.open) openFolds.add(d.dataset.fold); else openFolds.delete(d.dataset.fold);
      sessionStorage.setItem('sect.folds', JSON.stringify([...openFolds])); tabSig = '';
    }; });
    bindMap(z);
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
    return `<button class="btn" data-rushbuild="${i}" title="Finish it now, at a risk">Rush</button>${S.builders.blueprints ? `<button class="btn" data-blueprint="${i}" title="Takes ${S.builders.blueprint_cut}% off the time this job has left">Use a blueprint</button>` : ''}<button class="btn" data-cancel="${i}">Cancel</button>`;
  }

  // The Build tab, a ledger: builders as a strip of lantern timers; rooms sorted into what you can raise now, what waits
  // on materials (saying what is missing), and what waits on the Main Hall.
  function build() {
    const B = S.builders;
    const running = S.builds.filter((b) => b.running);
    const lamp = (b, i) => (b ? `<li class="lamp" style="--p:${b.pct}">
        <span class="ring"><span class="rthumb" style="${roomThumb(b.room)}" aria-hidden="true"></span></span>
        <span class="ltxt"><b>${esc(b.name)} ${b.wing ? 'wing' : b.level}</b><span class="num">${esc(awayT(b.left))} left</span><small class="dim">with the app closed, or ${esc(watchT(b.left))} if you watch · ${b.pct}% done</small>
          <span class="row">${benchButtons(i)}</span>${benchSpeed(b, i)}</span></li>`
      : '<li class="lamp empty"><span class="ring"></span><span class="ltxt"><b>Free</b><small class="dim">waiting for orders</small></span></li>');
    const groups = { can: [], short: [], locked: [], max: [] };
    S.rooms.forEach((r) => groups[roomState(r)].push(r));
    const merge = S.rooms.filter((r) => r.wide && r.wide.affordable);
    const shortOf = (r) => Object.entries(r.cost).filter(([k, v]) => haveRes(k) < v).map(([k, v]) => `${v - haveRes(k)} ${k === 'stones' ? 'spirit stones' : k}`).join(', ');
    const row = (r, st) => `<li class="lrow ${st}"><button class="lthumb" data-roomtile="${esc(r.id)}" style="${roomThumb(r.id)}" aria-label="${esc(r.name)}: details"></button>
        <span class="grow"><b>${esc(r.name)}</b> ${r.open ? lvPips(r) : '<span class="small dim">new</span>'}${r.wide && r.wide.w > 1 ? ` <span class="small dim">${esc(r.wide.word)}</span>` : ''}<br>
          ${st === 'locked' ? `<small class="dim">${esc(r.lock_short || r.locked)}</small>` : st === 'max' ? '<small class="dim">Highest level</small>' : `<span class="rt-cost">${costChips(r.cost)}</span>`}</span>
        ${st === 'can' ? `<span class="lgo">${r.plot ? `<button class="btn primary" data-build="${esc(r.id)}">Raise</button>` : `<button class="btn primary" data-place="${esc(r.id)}">Choose an alcove</button>`}<small class="dim">ready in about ${esc(awayT(r.hours))}</small></span>`
    : st === 'short' ? `<small class="lneed">Needs ${esc(shortOf(r) || 'a free builder')}</small>` : ''}</li>`;
    const sect = (title, list, st) => (list.length ? `<h4 class="lhead">${esc(title)} <span class="dim small">${list.length}</span></h4><ul class="lrows">${list.map((r) => row(r, st)).join('')}</ul>` : '');
    const mrow = (r) => `<li class="lrow can"><button class="lthumb" data-roomtile="${esc(r.id)}" style="${roomThumb(r.id)}" aria-label="${esc(r.name)}: details"></button>
        <span class="grow"><b>${esc(r.name)}</b> <span class="small dim">${esc(r.wide.word)} now</span><br><span class="rt-cost">${costChips(r.wide.cost)}</span></span>
        <span class="lgo"><button class="btn" data-roomtile="${esc(r.id)}">See the merge</button><small class="dim">a wing, ready in about ${esc(awayT(r.wide.hours))}</small></span></li>`;
    return `<div class="ledger">${builderHead()}<ul class="lamps">${Array.from({ length: B.n }, (_, i) => lamp(running[i], i)).join('')}</ul>
      ${sect('Ready to raise', groups.can, 'can')}${merge.length ? `<h4 class="lhead">Ready to merge <span class="dim small">${merge.length}</span></h4><ul class="lrows">${merge.map(mrow).join('')}</ul>` : ''}${sect('Gathering materials', groups.short, 'short')}${sect('Waiting on the Main Hall', groups.locked, 'locked')}${sect('Complete', groups.max, 'max')}</div>`;
  }

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

  // ---- the World map ----------------------------------------------------------------------------------------------
  // A list of places beside the map (hovering one lights the other), hanging banners for labels, and the chosen
  // place's card opened under its row in the list, so it never hides a marker or a label on the painting (the map is
  // too full for a card on it to find a clear spot).
  // A place's marker is a painted emblem (art.place: static/art/place_<kind>.webp) when that file exists. Until it
  // does there is no icon at all: on the map the banner hangs from a small point of lantern light, in the list the
  // row is the name and its standing. What a place is always stands in words (the row's second line, the tooltip).
  let mapSel = sessionStorage.getItem('sect.mapsel') || '';
  const MAP_KIND = { home: 'Your sect', sect: 'Sect', ally: 'Sworn ally', foe: 'Rival sect', village: 'Village', wilds: 'Wilds',
    ruin: 'Ruins', realm: 'Secret realm', kingdom: 'Mortal kingdom', branch: 'Branch sect' };
  const mapSect = (m) => (m.type === 'sect' ? S.sects.find((x) => x.id === m.id) : null);
  // what a marker is, in words as well as colour: the second line never relies on colour alone
  function mapMark(m) {
    const em = place(m.emblem, S.place_art);
    const s = mapSect(m);
    if (s) {
      const cls = s.ally ? 'ally' : s.rel <= -15 ? 'foe' : 'sect';
      return { cls, em, known: true, sub: s.ally ? 'Sworn ally' : `${s.stance} ${s.rel > 0 ? '+' : ''}${s.rel}`, kind: `${MAP_KIND[cls]}, ${s.kind}` };
    }
    if (m.type === 'kingdom' && worldGates().kingdom) return { cls: 'kingdom', em, known: false, sub: 'Not yet known', kind: MAP_KIND.kingdom };
    if (m.type === 'home') return { cls: 'home', em, known: true, sub: 'Home', kind: MAP_KIND.home };
    const b = m.type === 'branch' ? S.branches[Number(m.id.slice(6))] : null;
    if (b) return { cls: 'branch', em, known: true, sub: `Led by ${b.leader}`, kind: MAP_KIND.branch };
    const cls = MAP_KIND[m.type] ? m.type : 'wilds';
    return { cls, em, known: true, sub: m.far || '', kind: MAP_KIND[m.type] || 'Place' };
  }
  // the painted emblem, or nothing (em is a fixed /art/ path from art.place, never user text)
  const emblem = (k) => (k.em ? `<img class="wm-em" src="${k.em}" alt="" draggable="false">` : '');
  const mapTip = (m, k) => `${m.name}: ${k.kind}${k.sub && k.sub !== k.kind ? ` (${k.sub})` : ''}`;
  const mapAt = (m) => `left:${Number(m.x)}%;top:${Number(m.y)}%`;
  // where a label sits so it stays on the painting: beside the marker at the edges, below it elsewhere
  const mapSide = (m) => (m.y > 88 || m.x < 7 ? 'lab-r' : m.x > 86 ? 'lab-ul' : m.x > 93 ? 'lab-l' : '');

  // the body of a place's card: what it is, how things stand, what can be done there (the same orders as below the map)
  function mapBody(m) {
    const k = mapMark(m);
    const stones = (S.res.find((r) => r.id === 'stones') || {}).n || 0;
    const s = mapSect(m);
    const more = (key, label) => `<button class="btn quiet" data-mopen="${esc(key)}">${esc(label)}</button>`;
    let stand = ''; let acts = '';
    if (m.type === 'home') {
      stand = `Fame <b class="num">${S.fame}</b>. ${S.pawns.length} disciple${S.pawns.length === 1 ? '' : 's'}${S.trip ? '; a party is on the road' : ''}.`;
      acts = more('Banner and motto', 'Banner and motto');
    } else if (s) {
      const ch = S.champs[s.id] || {};
      stand = `<b>${esc(s.stance)}</b> <span class="num">${s.rel > 0 ? '+' : ''}${s.rel}</span>. ${s.rel <= -15 ? 'Their raiders know the way to your gate.' : s.rel >= 15 ? 'They will not raid you.' : 'They are watching.'}
        ${(ch.list || []).slice(0, 2).map((c) => `<br><span class="small">${esc(c.name)} <span class="dim">(${esc(c.role)}, ${esc(c.realm)}, strength ${c.power})</span></span>`).join('')}`;
      acts = `${s.ally ? '<span class="tag gold">Sworn ally</span>' : s.rel >= 50 ? `<button class="btn primary" data-ally="${esc(s.id)}" ${stones >= 20 ? '' : 'disabled'}>Swear alliance (20 spirit stones)</button>` : ''}
        <button class="btn" data-gift="${esc(s.id)}" ${stones >= 10 ? '' : 'disabled'}>Send gifts (10 spirit stones)</button>`;
    } else if (m.trip) {
      const pl = S.places.find((x) => x.id === m.trip);
      if (pl) {
        stand = `${esc(pl.text)} <b class="num">${pl.hours}</b> hours there and back.${S.trip_plan && S.trip_plan.place === pl.name ? ' A standing order sends the same party again.' : ''}`;
        acts = `<button class="btn primary" data-trip="${esc(pl.id)}" ${S.trip ? 'disabled' : ''}>${S.trip ? 'A party is out' : 'Choose a party'}</button>`;
      }
    } else if (m.type === 'kingdom') {
      stand = k.known ? `The lord is <b>${esc(S.kingdom.stance.toLowerCase())}</b> <span class="num">${S.kingdom.favour > 0 ? '+' : ''}${S.kingdom.favour}</span>. A grateful lord sends rice each autumn; a resentful one sends tax collectors.`
        : esc(worldGates().kingdom);
      if (k.known) acts = more('The mortal kingdom', 'The mortal kingdom');
    } else if (m.type === 'realm') {
      stand = 'Once in sixty years a tear opens in the sky above the marsh. When it does, word comes and you choose who goes in.';
    } else if (m.type === 'village') {
      stand = 'When they need help they send word, and the choice comes to you.';
    } else if (m.type === 'branch') {
      const b = S.branches[Number(m.id.slice(6))];
      if (b) stand = b.sulking ? 'Sends nothing for now: you left them to stand alone.' : 'Sends 15 rice and 5 spirit stones every twelve days.';
    }
    return `<p class="wm-kind${k.known ? '' : ' unknown'}">${emblem(k)}${esc(k.kind)}${m.far ? ` · ${esc(m.far)}` : ''}</p>
      ${m.type === 'home' || m.trip || s ? '' : `<p class="wm-text">${esc(m.text)}</p>`}
      ${stand ? `<p class="wm-stand">${stand}</p>` : ''}
      ${acts ? `<div class="wm-acts">${acts}</div>` : ''}`;
  }

  function mapMarker(m, sel) {
    const k = mapMark(m);
    return `<button class="wm-mk t-${k.cls} ${mapSide(m)}${k.em ? ' em' : ''}${sel ? ' sel' : ''}${k.known ? '' : ' unknown'}" style="${mapAt(m)}" data-mk="${esc(m.id)}"
      aria-pressed="${sel}" aria-label="${esc(m.name)}: ${esc(k.kind)}${k.sub ? `, ${esc(k.sub)}` : ''}" title="${esc(mapTip(m, k))}">${k.em ? emblem(k) : '<i class="wm-glow" aria-hidden="true"></i>'}
      <span class="wm-lab" aria-hidden="true"><b>${esc(m.name)}</b>${k.sub && (k.cls === 'foe' || !k.known) ? `<small>${esc(k.sub)}</small>` : ''}</span></button>`;
  }

  const mapBg = `background-image:radial-gradient(ellipse at 55% 40%,#f0a85022,transparent 60%),linear-gradient(#0c122855,#120d0a77),url(${backdrop('map')})`;

  function worldMap() {
    const sel = S.map.find((m) => m.id === mapSel);
    const groups = [['Your sect', (m) => m.type === 'home' || m.type === 'branch'], ['Sects of the region', (m) => m.type === 'sect'], ['The country', (m) => !['home', 'branch', 'sect'].includes(m.type)]];
    const card = (m) => `<div class="wm-card" role="region" aria-label="${esc(m.name)}" aria-live="polite">
      <button class="wm-x" data-mk="" aria-label="Close ${esc(m.name)}">×</button>${mapBody(m)}</div>`;
    const row = (m) => { const k = mapMark(m); const on = !!sel && sel.id === m.id; return `<li><button class="wm-row t-${k.cls}${on ? ' sel' : ''}${k.known ? '' : ' unknown'}" data-mk="${esc(m.id)}" aria-pressed="${on}" aria-expanded="${on}" title="${esc(mapTip(m, k))}">
      ${emblem(k)}<span><b>${esc(m.name)}</b><small>${esc(k.sub || k.kind)}</small></span></button>${on ? card(m) : ''}</li>`; };
    return `<div class="wm">
      <nav class="wm-list" aria-label="Places on the map">${groups.map(([t, f]) => { const ms = S.map.filter(f); return ms.length ? `<p class="wm-group">${esc(t)}</p><ul>${ms.map(row).join('')}</ul>` : ''; }).join('')}</nav>
      <div class="worldmap wm-paint" style="${mapBg}">${S.map.map((m) => mapMarker(m, !!sel && m.id === sel.id)).join('')}</div></div>`;
  }

  function bindMap(z) {
    // focus stays where the choice was made (the marker or the row); closing the card returns it to that place's row
    const pick = (id, from) => {
      const was = mapSel;
      mapSel = id; sessionStorage.setItem('sect.mapsel', id); tabSig = ''; paintTabs();
      const el = $(`${from === 'map' ? '.worldmap' : '.wm-list'} [data-mk="${CSS.escape(id || was)}"]`, z); if (el) el.focus({ preventScroll: true });
    };
    z.querySelectorAll('[data-mk]').forEach((b) => {
      b.onclick = () => pick(b.dataset.mk === mapSel ? '' : b.dataset.mk, b.closest('.worldmap') ? 'map' : 'list');
      const lit = (on) => { if (b.dataset.mk) z.querySelectorAll(`[data-mk="${CSS.escape(b.dataset.mk)}"]`).forEach((x) => x.classList.toggle('hl', on)); };
      b.onmouseenter = b.onfocus = () => lit(true); b.onmouseleave = b.onblur = () => lit(false);
    });
    const card = $('.wm-card', z);
    if (card) card.onkeydown = (e) => { if (e.key === 'Escape') { e.stopPropagation(); pick('', 'list'); } };
    z.querySelectorAll('[data-mopen]').forEach((b) => { b.onclick = () => {
      const key = b.dataset.mopen; openFolds.add(key); sessionStorage.setItem('sect.folds', JSON.stringify([...openFolds])); tabSig = ''; paintTabs();
      const d = $(`details[data-fold="${CSS.escape(key)}"]`, z); if (d) d.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }; });
  }

  function worldRaw() {
    const stones = (S.res.find((r) => r.id === 'stones') || {}).n || 0;
    const relCls = (r) => (r >= 15 ? 'jade' : r > -15 ? '' : 'red');
    const gate = worldGates();
    const later = Object.values(gate).filter(Boolean);
    return `<div class="banner" style="background-image:linear-gradient(#0c1228b0,#120d0ae0),url(${backdrop('map')})"><h2>${esc(S.name)}</h2>
        <p>Fame <b class="num">${S.fame}</b>. Fame is won at the gate, in the arena and under the lightning; talented youths seek out famous sects.</p></div>
      ${worldMap()}
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

  // The odds of a rush, as two ledgers: the chance of an incident, and the chance the crew contain one.
  function rushHtml(R, what) {
    const rows = (list) => list.map((o) => `<li class="row"><span class="grow">${esc(o.label)}</span><span class="num small">${o.v > 0 ? '+' : ''}${o.v}%</span></li>`).join('');
    return `<div class="rushbox"><h3>Rush ${esc(what)}</h3>
      <p class="small">${R.out && R.out.length ? `Delivers ${esc(R.out.map((x) => `${x.n} ${x.name}`).join(' and '))} now, six hours of the crew's work.` : 'Finishes the job now.'}</p>
      <div class="rushodds"><div><b class="num">${R.chance}%</b><small>chance of an incident (${esc(R.incident.toLowerCase())})</small></div>
        <div><b class="num">${R.contain}%</b><small>the crew contain it if it comes</small></div></div>
      <details class="fold"><summary>Why ${R.chance}%</summary><ul class="list odds">${rows(R.rows)}</ul></details>
      <details class="fold"><summary>Why ${R.contain}% to contain it</summary><ul class="list odds">${rows(R.contain_rows)}</ul>
        <p class="dim small">${R.crew.length ? `The crew: ${esc(R.crew.join(', '))}.` : 'No crew to lean on.'}</p></details>
      <p class="dim small">If it is not contained: ${R.out && R.out.length ? 'the rushed work is lost, the room stands idle six hours and the crew are hurt' : 'two more hours of work and a tenth of the materials spoiled'}. No one dies of a rush. Each rush makes the next one riskier for two days.</p></div>`;
  }
  function rushSheet(index) {
    const b = S.builds.filter((x) => x.running)[index]; if (!b || !b.rush) return;
    openSheet(`<h2>${esc(b.name)} ${b.wing ? "wing" : `to level ${b.level}`}</h2>${rushHtml(b.rush, 'the build')}
      <button class="btn primary" data-dorush>Rush it (${b.rush.chance}% risk)</button>`);
    const go = $('[data-dorush]', $('#sheet')); if (go) go.onclick = async () => { closeSheet(); await order('rush-build', { index }); };
  }

  // What a wing gives, as a ledger: now against merged, then the price.
  function mergeHtml(r) {
    const W = r.wide; const next = ['', 'two alcoves wide', 'three alcoves wide'][W.w] || '';
    return `<div class="rushbox mergebox"><h3>Merge: the ${esc(r.name)}, ${esc(next)}</h3>
      <p class="small">A wing is built in the alcove beside it, at level ${r.level}. When it is done the wall comes down and the halls are one room.</p>
      <table class="mergeled"><tr><th scope="col"></th><th scope="col">Now</th><th scope="col">Merged</th></tr>
        ${W.rows.map((o) => `<tr><th scope="row">${esc(o.label)}</th><td class="num">${esc(o.now)}</td><td class="num then">${esc(o.then)}</td></tr>`).join('')}</table>
      <p class="small" style="margin:8px 0 0">The wing: <span class="rt-cost">${costChips(W.cost)}</span></p>
      <p class="dim small" style="margin:4px 0 0">${esc(readyIn(W.hours))}. It takes a builder, like any job.</p></div>`;
  }
  const sideWord = (r, c) => (c[1] < r.plot.s ? 'on the left' : 'on the right');
  function wingButtons(r, only) {
    const W = r.wide; const cells = only ? W.cells.filter((c) => c[0] === only[0] && c[1] === only[1]) : W.cells;
    if (W.why) return `<p class="tag red">${esc(W.why)}</p>`;
    const short = Object.entries(W.cost).filter(([k, v]) => haveRes(k) < v).map(([k, v]) => `${v - haveRes(k)} more ${k === 'stones' ? 'spirit stones' : k}`).join(' and ');
    return `<div class="row">${cells.map((c) => `<button class="btn ${W.affordable ? 'primary' : ''}" data-wing="${esc(r.id)}|${c[0]}|${c[1]}" ${W.affordable ? '' : 'disabled'}>Build the wing${cells.length > 1 ? ` ${sideWord(r, c)}` : ''}</button>`).join('')}</div>
      ${W.affordable ? '' : `<p class="dim small" style="margin-top:6px">${short ? `Needs ${esc(short)}.` : 'Every builder is busy. One comes free when a job finishes.'}</p>`}`;
  }
  function bindWings(root) {
    root.querySelectorAll('[data-wing]').forEach((b) => { b.onclick = async () => { const [room, f, s] = b.dataset.wing.split('|'); closeSheet(); await order('widen', { room, cell: [Number(f), Number(s)] }); }; });
  }

  // An empty alcove: merge the room beside it into it, or build a room that has no place yet.
  function alcoveSheet(f, s) {
    const beside = S.rooms.filter((r) => r.open && r.plot && r.wide && r.plot.f === f && (r.plot.s + r.plot.w === s || r.plot.s - 1 === s) && r.wide.w < 3);
    const fresh = S.rooms.filter((r) => !r.plot);
    const state = (r) => (r.locked ? `<small class="dim">${esc(r.lock_short || r.locked)}</small>`
      : r.affordable ? `<span class="lgo"><button class="btn primary" data-new="${esc(r.id)}">Build here</button><small class="dim">ready in about ${esc(awayT(r.hours))}</small></span>`
        : `<small class="lneed">Needs ${esc(Object.entries(r.cost).filter(([k, v]) => haveRes(k) < v).map(([k, v]) => `${v - haveRes(k)} ${k === 'stones' ? 'spirit stones' : k}`).join(', ') || 'a free builder')}</small>`);
    const row = (r) => `<li class="lrow ${r.locked ? 'locked' : r.affordable ? 'can' : 'short'}"><span class="lthumb" style="${roomThumb(r.id)}" aria-hidden="true"></span>
        <span class="grow"><b>${esc(r.name)}</b><br>${r.locked ? '' : `<small class="dim">${esc(r.effect)}</small><br><span class="rt-cost">${costChips(r.cost)}</span>`}</span>${state(r)}</li>`;
    fresh.sort((a, b) => (a.locked ? 1 : 0) - (b.locked ? 1 : 0));
    openSheet(`<h2>An empty alcove</h2><p class="dim">The ${FLOOR[f]}, ${ORD[s]} from the left.</p>
      ${beside.map((r) => `${mergeHtml(r)}${wingButtons(r, [f, s])}`).join('')}
      ${fresh.length ? `<h3 style="margin-top:16px">Build a room here</h3><ul class="lrows">${fresh.map(row).join('')}</ul>`
    : `<p class="small" style="margin-top:14px">Every room is built. ${beside.length ? '' : 'A room standing beside an empty alcove can grow into it; a room can also be moved here from its own sheet.'}</p>`}
      ${S.grid.wide_max < 3 ? `<p class="dim small" style="margin-top:10px">Rooms merge ${S.grid.wide_max < 2 ? `two alcoves wide from Main Hall ${S.grid.wide_halls['2']}, ` : ''}three wide from Main Hall ${S.grid.wide_halls['3']}.</p>` : ''}`);
    const sh = $('#sheet');
    sh.querySelectorAll('[data-new]').forEach((b) => { b.onclick = async () => { closeSheet(); await order('build', { room: b.dataset.new, cell: [f, s] }); }; });
    bindWings(sh);
  }

  function roomSheet(id) {
    const r = S.rooms.find((x) => x.id === id); if (!r) return;
    const crew = r.posted.map((pid) => (S.pawns.find((p) => p.id === pid) || {}).name).filter(Boolean);
    const R = r.rush; const W = r.wide;
    const wide = W && r.open ? `${W.w > 1 ? `<p class="small">Merged, ${esc(W.word)}${W.yield ? `: ${esc(W.yield.toLowerCase())} ×${W.x}` : ''}. Each level costs and takes more than a single room's, and less than ${W.w} rooms would.</p>` : ''}
      ${r.wing ? '<p class="small">A wing is being built beside it.</p>' : W.rows.length ? `${mergeHtml(r)}${wingButtons(r)}` : ''}` : '';
    openSheet(`<h2>${esc(r.name)}</h2><p class="dim">${r.open ? `Level ${r.level} of ${r.max}` : 'Not built yet'}${r.queued ? ' · under construction' : ''}</p><p>${esc(r.effect)}</p>
      ${r.slots ? `<p class="small">Posted here (${esc(r.post_jobs.join(', '))} first): ${r.posted.length} of ${r.slots}${crew.length ? `, ${esc(crew.join(', '))}` : ''}. Drag a disciple from the roster under the map onto the room to post them.</p>` : ''}
      ${r.tray.length ? `<p class="small">Made since the last look: ${esc(r.tray.map((t) => `${t.n} ${t.name}`).join(', '))}. It is in the stores already; tapping the tray on the map is the Master's inspection, which pleases the crew (+3 mood for 12 hours, once a day).</p>` : ''}
      ${r.cost ? (r.locked ? `<p class="tag red">${esc(r.locked)}</p>`
    : r.plot ? `<button class="btn ${r.affordable ? 'primary' : ''}" data-go ${r.affordable ? '' : 'disabled'}>${r.open ? 'Raise' : 'Build'}: ${esc(costText(r.cost))}</button>
           <p class="dim small" style="margin-top:8px">${r.affordable ? `Materials are spent now. ${esc(readyIn(r.hours))}. Disciples with Build as a priority help.`
    : S.builders.busy >= S.builders.n ? 'Every builder is busy. One comes free when a job finishes.' : 'You do not have the materials yet.'}</p>`
      : `<button class="btn ${r.affordable ? 'primary' : ''}" data-placeit ${r.affordable ? '' : 'disabled'}>Choose an alcove: ${esc(costText(r.cost))}</button>
           <p class="dim small" style="margin-top:8px">${r.affordable ? `Pick an empty alcove on the map. ${esc(readyIn(r.hours))}.` : S.builders.busy >= S.builders.n ? 'Every builder is busy. One comes free when a job finishes.' : 'You do not have the materials yet.'}</p>`)
    : '<p class="tag gold">Highest level reached</p>'}
      ${wide}
      ${R ? (R.idle ? `<p class="warn">Putting things right after an incident: idle ${R.idle} more hours.</p>` : R.out.length ? `${rushHtml(R, 'the work')}<button class="btn" data-dorush>Rush it (${R.chance}% risk)</button>` : '<p class="dim small">Nobody has worked here today, so there is nothing to rush.</p>') : ''}
      ${r.plot && !r.queued && !r.wing && id !== 'main_hall' ? '<p style="margin:14px 0 2px"><button class="btn quiet" data-move>Move this room to another alcove</button></p><p class="dim small" style="margin:0">Free, and at once. Where a room stands decides what it can merge into.</p>' : ''}`);
    const sh = $('#sheet');
    const go = $('[data-go]', sh); if (go) go.onclick = async () => { closeSheet(); await order('build', { room: id }); };
    const pl = $('[data-placeit]', sh); if (pl) pl.onclick = () => { closeSheet(); startPlacing('build', id); };
    const mv = $('[data-move]', sh); if (mv) mv.onclick = () => { closeSheet(); startPlacing('move', id); };
    const ru = $('[data-dorush]', sh); if (ru) ru.onclick = async () => { closeSheet(); await order('rush', { room: id }); };
    bindWings(sh);
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
