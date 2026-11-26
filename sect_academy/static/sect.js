// The sect screen: a colony sim you watch and steer. The server owns the simulation;
// this module draws it, sends orders, and asks for sim hours as real time passes.
// All text from the server goes through esc(); every number arrives already cast.

import { ICON, VAULT, backdrop, portrait, scene, sectScene, siteRect } from '/art.js';

const SPEED_KEY = 'sect.speed';
const SECS_PER_HOUR = { 1: 4, 2: 2, 3: 1 };          // real seconds per sim hour
const RES_ICON = { rice: '🌾', wood: '🪵', stone: '🪨', herbs: '🌿', pills: '💊', stones: '💎' };
const SITE_OF = { farm: 'fields', quarry: 'spirit_vein', 'cut wood': 'storehouse', 'forage herbs': 'fields', 'brew pills': 'alchemy',
  research: 'library', train: 'training', meditate: 'meditation', sleeping: 'dormitory', recovering: 'dormitory', relaxing: 'main_hall', idle: 'main_hall' };
const EVENT_ART = { omen: 'mission', young_master: 'leader', auction: 'treasure', secret_realm: 'seclusion', cave: 'seclusion', tournament: 'technique',
  demonic_offer: 'seclusion', trip_choice: 'map', fate: 'seclusion', succession: 'leader', qingming: 'map', lord: 'leader', taxes: 'leader', embrace: 'seclusion', discipline: 'hall', demon: 'seclusion', festival: 'hall', merchant: 'treasure', wanderer: 'hall', recruit: 'hall', engagement: 'leader', spy: 'leader', village: 'map', beast_cub: 'map' };
const RES_SHORT = { stones: 'Spirit st.' };          // phone chips keep a label; only the long one is cut
const ELEMENT_ICON = { wood: '🌿', fire: '🔥', earth: '⛰', metal: '⚔', water: '💧' };
const store = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } } };

export function mountSect(h) {
  const { view, $, esc, api, toast, openSheet, closeSheet } = h;
  let S = h.sect();
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

  function take(res, mine) { if (res.sect && mine >= seq) { seq = mine; S = res.sect; h.setSect(S); return true; } return false; }

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
  function paintTop() {
    const z = $('#z-top'); if (!z) return;
    z.innerHTML = `<header class="status">
        <h1 style="border-left:6px solid ${S.colours.includes(S.style.colour) ? `var(--sect-colour)` : 'var(--gold)'};padding-left:10px">${esc(S.name)}${S.style.motto ? `<em class="motto">“${esc(S.style.motto)}”</em>` : ''}<small>${esc(S.renown)}${S.demonic ? ' · demonic path' : ''} · <span title="Day ${S.day} since the founding">${esc(S.when)}</span> · ${clock()}${S.seclusion ? ' · gates sealed' : ''}</small></h1>
        <span class="pill flame ${S.streak ? '' : 'off'}" title="Study streak. Best: ${S.best_streak}">${ICON.flame}${S.streak}</span>
        <span class="speed" role="group" aria-label="Game speed">
          <button class="${speed === 0 ? 'on' : ''}" data-speed="0" aria-label="Pause">${ICON.pause}</button>
          ${[1, 2, 3].map((n) => `<button class="${speed === n ? 'on' : ''}" data-speed="${n}" aria-label="Speed ${n}">${'▸'.repeat(n)}</button>`).join('')}
        </span>
      </header>
      <div class="resbar">${S.res.map((r) => `<span class="res ${r.id === 'rice' && S.food_days < 3 ? 'low' : ''}" title="${esc(r.name)}${r.cap ? ` (store holds ${r.cap})` : ''}">
          <span aria-hidden="true">${RES_ICON[r.id] || ''}</span><b class="num">${r.n}</b><small class="lbl">${esc(r.name)}</small><small class="lbl-s">${esc(RES_SHORT[r.id] || r.name)}</small></span>`).join('')}
        <span class="res" title="Insight from your own study. It is spent on research automatically."><span aria-hidden="true">📜</span><b class="num">${S.insight}</b><small class="lbl">Insight</small><small class="lbl-s">Insight</small></span>
        <span class="res" title="How strong the sect's defence is"><span aria-hidden="true">🛡</span><b class="num">${S.defense}</b><small class="lbl">Defence</small><small class="lbl-s">Defence</small></span>
        <span class="res" title="Fame: won in fights, tournaments and breakthroughs. Draws better recruits."><span aria-hidden="true">🏮</span><b class="num">${S.fame}</b><small class="lbl">Fame</small><small class="lbl-s">Fame</small></span>
      </div>
      ${S.guide ? `<div class="guide tutor">${portrait('guide', { kind: 'elder', size: 52 })}<div class="speech"><small class="dim">The elder's counsel · ${S.guide.n} of ${S.guide.total}</small><br>${esc(S.guide.text)}
          <button class="linkish dim small" data-skipguide style="margin-left:8px">I know colony sims, skip</button></div></div>` : ''}
      ${S.siege ? `<p class="warn">⚔ Under siege by the ${esc(S.siege.sect)}: battle ${S.siege.stage} of three is coming. Train, brew, and mend the wounded.</p>` : ''}
      ${S.quest ? `<p class="questline ${S.quest.ready ? 'ready' : ''}">📜 <b>${esc(S.quest.title)}</b>: ${S.quest.have}/${S.quest.n} ${esc(S.quest.res)}, ${S.quest.days_left} day${S.quest.days_left === 1 ? '' : 's'} left.
          ${S.quest.ready ? '<button class="btn primary" data-deliver>Deliver</button>' : ''}</p>` : ''}
      ${S.alerts.length ? `<ul class="alerts">${S.alerts.map((a) => `<li class="${esc(a.kind)}">${a.pawn ? `<button class="linkish" data-pawn="${esc(a.pawn)}">${esc(a.text)}</button>` : esc(a.text)}</li>`).join('')}</ul>` : ''}`;
    z.querySelectorAll('[data-speed]').forEach((b) => { b.onclick = () => setSpeed(Number(b.dataset.speed)); });
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
    const sig = JSON.stringify([S.rooms.map((r) => r.level), building, Object.entries(staff).map(([k, v]) => k + v.map((p) => p.id).join()), S.rooms.map((r) => r.affordable), S.treasures.length]);
    if (sig === sceneSig && z.firstChild) return;
    sceneSig = sig;
    const rooms = S.rooms.map((r) => {
      const [x, y, w, hh] = siteRect(r.id);
      const crew = (staff[r.id] || []).slice(0, 5).map((p) => face(p, 30)).join('');
      return `<button class="room ${r.open ? '' : 'closed'} ${building.includes(r.id) ? 'building' : ''}" data-room="${esc(r.id)}" style="left:${x}%;top:${y}%;width:${w}%;height:${hh}%"
        aria-label="${esc(r.name)}, ${r.open ? `level ${r.level}` : 'not built'}${r.affordable ? ', you can afford the next level' : ''}">
        ${r.affordable ? '<span class="can" aria-hidden="true">↑</span>' : ''}
        <span class="crew" aria-hidden="true">${crew}</span>
        <span class="plaque">${esc(r.name)}${r.open ? `<em>${r.level}</em>` : building.includes(r.id) ? '<em>building</em>' : ''}</span></button>`;
    }).join('');
    const [vx, vy, vw, vh] = VAULT;
    z.innerHTML = `<div class="hq">${sectScene()}<div class="daylight" id="daylight"></div>${rooms}
      <button class="room vault" data-vault style="left:${vx}%;top:${vy}%;width:${vw}%;height:${vh}%" aria-label="Treasure vault: manuals, treasures and the world beyond">
        <span class="plaque">Treasure Vault${S.treasures.length ? `<em>${S.treasures.length}</em>` : ''}</span></button></div>`;
    z.querySelectorAll('[data-room]').forEach((b) => { b.onclick = () => roomSheet(b.dataset.room); });
    $('[data-vault]', z).onclick = () => { tab = 'world'; sessionStorage.setItem('sect.tab', tab); paintTabs(); $('#z-tabs').scrollIntoView({ behavior: 'smooth' }); };
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
    z.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => order('cancel-build', { index: Number(b.dataset.cancel) }); });
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
        <span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span> <span class="tag">${esc(p.rank)}</span>${p.direct ? ' <span class="tag gold">Direct disciple</span>' : ''}
        ${p.bonds.filter((x) => x.kind).slice(0, 2).map((x) => `<span class="tag ${x.kind === 'rival' ? 'red' : 'jade'}">${x.kind === 'rival' ? '⚔' : '♥'} ${esc(x.name.split(' ')[0])}</span>`).join(' ')}
        ${p.companion ? `<span class="tag violet">☯ ${esc(p.companion.split(' ')[0])}</span>` : ''}${p.demon ? ` <span class="tag red">Heart demon${p.demon > 1 ? ` ×${p.demon}` : ''}</span>` : ''}
        <span class="doing">${p.ready ? `<span class="tag gold">⚡ Ready for ${esc(p.next_realm)}</span> ` : ''}${p.broken ? '<span class="tag red">Qi deviation</span> ' : ''}${p.inspired ? '<span class="tag jade">Inspired</span> ' : ''}${p.sick ? '<span class="tag red">Sick</span> ' : ''}${esc(p.doing)}</span>
        <span class="needs"><span title="Mood ${p.mood}">Mood ${bar(p.mood, moodCls(p.mood))}</span><span title="Food ${p.food}">Food ${bar(p.food, p.food < 25 ? 'verm' : 'azure')}</span>
          <span title="Rest ${p.rest}">Rest ${bar(p.rest, p.rest < 25 ? 'verm' : 'azure')}</span><span title="Health ${p.health}">Health ${bar(p.health, p.health < 50 ? 'verm' : 'jade')}</span></span>
      </span></button>`).join('')}</div>
      <p class="dim small" style="margin:10px 0 0">${S.beds} bed${S.beds === 1 ? '' : 's'} for ${S.pawns.length} disciple${S.pawns.length === 1 ? '' : 's'}. Wanderers sometimes ask to join; the sect can hold ${S.pawn_cap}.${S.graves ? ` ${S.graves} lie in the sect's graveyard.` : ''}</p>`;
  }

  function work() {
    return `<p class="dim small"><b>1</b> is done first, <b>4</b> last, blank never. Click or tap a cell to raise it (blank → 4 → … → 1); right-click or press and hold to lower it. When two jobs tie, a disciple does what the sect is shortest of.</p>
      <p class="dim small phone-only">Swipe the grid sideways for more jobs; the names stay put.</p>
      <div class="scroll-x workgrid"><table class="worktable"><tr><th class="who"></th>${S.jobs.map((j) => `<th title="Uses ${esc(j.skill)}"><span>${esc(j.name)}</span></th>`).join('')}</tr>
      ${S.pawns.map((p) => `<tr><th class="who" scope="row">${esc(p.name.split(' ')[0])}</th>${S.jobs.map((j) => {
        const lv = p.prio[j.id]; const sk = p.skills.find((s) => s.name === j.skill);
        return `<td><button class="prio p${lv}" data-prio="${esc(p.id)}|${esc(j.id)}|${lv}" title="${esc(j.name)}: priority ${lv || 'off'}, skill ${sk ? sk.lv : 0}. Click to raise, right-click or hold to lower."
          aria-label="${esc(p.name)}: ${esc(j.name)}, priority ${lv || 'off'}; skill ${sk ? sk.lv : 0}. Activate to raise; context menu to lower.">
<span>${lv || ''}</span><small>${sk ? sk.lv : 0}${sk ? flames(sk.passion) : ''}</small></button></td>`;
      }).join('')}</tr>`).join('')}</table></div>
      <p class="dim small" style="margin:8px 0 0">The small number is their skill; a flame means they love it and learn it fast.</p>
      <div class="row" style="margin-top:10px">${['peace', 'war'].map((n) => `<button class="btn quiet" data-preset-save="${n}">Save as “${n}”</button>${S.presets.includes(n) ? `<button class="btn" data-preset-apply="${n}">Switch to “${n}”</button>` : ''}`).join('')}</div>
      <p class="dim small">Two saved sets of priorities, so preparing for a siege is one tap.</p>`;
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
    return `<div class="banner" style="background-image:linear-gradient(#120d0a55,#120d0acc),url(${backdrop('map')})"><h2>${esc(S.name)}</h2>
        <p>Fame <b class="num">${S.fame}</b>. Fame is won at the gate, in the arena and under the lightning; talented youths seek out famous sects.</p></div>
      <div class="worldmap" style="background-image:url(${backdrop('map')})">${S.map.map((m) => `<button class="pin ${esc(m.kind)}" style="left:${m.x}%;top:${m.y}%" title="${esc(m.text)}" data-pin="${esc(m.name)}|${esc(m.text)}"><i></i><span>${esc(m.name)}</span></button>`).join('')}</div>
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
        <p class="dim" style="margin:0">${p.age} · ${ELEMENT_ICON[p.element] || ''} ${esc(p.root)} ${esc(p.element)} root · ${esc(p.rank)}${p.master ? ' (you)' : ''}</p>
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
      <ul class="list">${p.qi_why.map((t) => `<li class="row"><span class="grow">${esc(t.label)}</span><b class="num" style="color:var(--${t.x < 1 ? 'verm' : 'jade'})">×${t.x}</b></li>`).join('')}</ul>
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
          ${p.mentors.map((m) => `<button class="btn" data-mentor="${esc(m.id)}">Kneel to ${esc(m.name.split(' ')[0])}</button>`).join('')}</li>
        ${p.mentor ? `<li><span class="small">Trust in their master: <b class="num">${p.trust}</b>/100</span>
          <div class="track"><i style="width:${p.trust}%"></i>${p.station_marks.map((m) => `<span class="${m.done ? 'done' : ''}" style="left:${m.at}%" title="At ${m.at}: their master ${esc(m.text)}">${m.done ? '◆' : '◇'}</span>`).join('')}</div>
          <span class="dim small">Grows a little each day they are both home, and a lot when the master guards a breakthrough or they fight side by side. Each mark is an evening and a gift.</span></li>` : ''}
        <li class="row"><span class="grow">Dao companion: <b>${p.companion ? esc(p.companion) : 'none'}</b></span>
          ${p.can_bind.map((m) => `<button class="btn" data-bind="${esc(m.id)}">Bind with ${esc(m.name.split(' ')[0])}</button>`).join('')}</li>
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
           ${r.affordable ? '<p class="dim small" style="margin-top:8px">Materials are spent now; disciples with Build as a priority do the work.</p>' : '<p class="dim small" style="margin-top:8px">You do not have the materials yet.</p>'}`)
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

  function paint() { paintStyle(); paintTop(); paintEvent(); paintScene(); paintLight(); paintMaster(); paintTabs(); paintScenes(); }

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
    <div id="z-event"></div><section class="panel scenewrap" id="z-scene"></section>
    <div class="grid2 studyrow">${h.todayPanel()}<div id="z-master"></div></div>
    <section class="panel" id="z-tabs" style="margin-top:14px"></section></div>`;
  h.bindToday(view);
  paint();
  stop();
  timer = setInterval(beat, 1000);
  return { stop, order };
}
