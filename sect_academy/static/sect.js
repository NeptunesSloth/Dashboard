// The sect screen: a colony sim you watch and steer. The server owns the simulation;
// this module draws it, sends orders, and asks for sim hours as real time passes.
// All text from the server goes through esc(); every number arrives already cast.

import { ICON, VAULT, backdrop, portrait, sectScene, siteRect } from '/art.js';

const SPEED_KEY = 'sect.speed';
const SECS_PER_HOUR = { 1: 4, 2: 2, 3: 1 };          // real seconds per sim hour
const RES_ICON = { rice: '🌾', wood: '🪵', stone: '🪨', herbs: '🌿', pills: '💊', stones: '💎' };
const SITE_OF = { farm: 'fields', quarry: 'spirit_vein', 'cut wood': 'storehouse', 'forage herbs': 'fields', 'brew pills': 'alchemy',
  research: 'library', train: 'training', meditate: 'meditation', sleeping: 'dormitory', recovering: 'dormitory', relaxing: 'main_hall', idle: 'main_hall' };
const EVENT_ART = { omen: 'mission', young_master: 'leader', auction: 'treasure', secret_realm: 'seclusion', cave: 'seclusion', tournament: 'technique',
  demonic_offer: 'seclusion', merchant: 'treasure', wanderer: 'hall', recruit: 'hall', engagement: 'leader', spy: 'leader', village: 'map', beast_cub: 'map' };
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
    if (res.ok === false && !quiet) toast(res.error || 'That did not work.');
    else if (res.event && !quiet) toast(res.event.title, res.event.kind === 'bad' ? 6000 : 3500);
    paint();
    return res;
  }

  /* ---------------- the clock ---------------- */
  function setSpeed(n) { speed = n; store.set(SPEED_KEY, String(n)); owed = 0; paintTop(); }
  async function beat() {
    if (!view.isConnected || !$('#sect-root')) { stop(); return; }
    if (document.hidden || busy) return;
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
      if (top && top.hour + top.title !== before && top.hour > 0) toast(top.title, top.kind === 'bad' ? 6000 : 3500);
      paint();
    }
  }
  function stop() { if (timer) clearInterval(timer); timer = null; }

  /* ---------------- zones ---------------- */
  function paintTop() {
    const z = $('#z-top'); if (!z) return;
    z.innerHTML = `<header class="status">
        <h1>${esc(S.name)}<small>${esc(S.renown)} · Day ${S.season_day} of ${esc(S.season)}, year ${S.year} · ${clock()}${S.seclusion ? ' · gates sealed' : ''}</small></h1>
        <span class="pill flame ${S.streak ? '' : 'off'}" title="Study streak. Best: ${S.best_streak}">${ICON.flame}${S.streak}</span>
        <span class="speed" role="group" aria-label="Game speed">
          <button class="${speed === 0 ? 'on' : ''}" data-speed="0" aria-label="Pause">${ICON.pause}</button>
          ${[1, 2, 3].map((n) => `<button class="${speed === n ? 'on' : ''}" data-speed="${n}" aria-label="Speed ${n}">${'▸'.repeat(n)}</button>`).join('')}
        </span>
      </header>
      <div class="resbar">${S.res.map((r) => `<span class="res ${r.id === 'rice' && S.food_days < 3 ? 'low' : ''}" title="${esc(r.name)}${r.cap ? ` (store holds ${r.cap})` : ''}">
          <span aria-hidden="true">${RES_ICON[r.id] || ''}</span><b class="num">${r.n}</b><small>${esc(r.name)}</small></span>`).join('')}
        <span class="res" title="Insight from your own study. It is spent on research automatically."><span aria-hidden="true">📜</span><b class="num">${S.insight}</b><small>Insight</small></span>
        <span class="res" title="How strong the sect's defence is"><span aria-hidden="true">🛡</span><b class="num">${S.defense}</b><small>Defence</small></span>
        <span class="res" title="Fame: won in fights, tournaments and breakthroughs. Draws better recruits."><span aria-hidden="true">🏮</span><b class="num">${S.fame}</b><small>Fame</small></span>
      </div>
      ${S.guide ? `<div class="guide tutor">${portrait('guide', { kind: 'elder', size: 52 })}<div class="speech"><small class="dim">The elder's counsel · ${S.guide.n} of ${S.guide.total}</small><br>${esc(S.guide.text)}
          <button class="linkish dim small" data-skipguide style="margin-left:8px">I know colony sims, skip</button></div></div>` : ''}
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
    const sig = ev ? ev.title + ev.text + ev.options.length : '';
    if (z.dataset.sig === sig) return;
    z.dataset.sig = sig;
    z.innerHTML = ev ? `<section class="panel event" style="background-image:linear-gradient(90deg,#120d0af2 0%,#120d0ad9 55%,#120d0a66 100%),url(${backdrop(EVENT_ART[ev.kind] || 'hall')})">
      <h2>${esc(ev.title)}</h2><p>${esc(ev.text)}</p>
      <div class="choices">${ev.options.map((o, i) => `<button class="btn ${i === 0 ? 'primary' : ''}" data-opt="${esc(o.id)}">${esc(o.label)}</button>`).join('')}</div>
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
    tabSig = html;
    const sx = $('.scroll-x', z) ? $('.scroll-x', z).scrollLeft : 0;
    z.innerHTML = html;
    if ($('.scroll-x', z)) $('.scroll-x', z).scrollLeft = sx;
    z.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { tab = b.dataset.tab; sessionStorage.setItem('sect.tab', tab); paintTabs(); }; });
    z.querySelectorAll('[data-pawn]').forEach((b) => { b.onclick = () => pawnSheet(b.dataset.pawn); });
    z.querySelectorAll('[data-prio]').forEach((b) => {
      b.onclick = () => { const [pawn, job, cur] = b.dataset.prio.split('|'); const next = cur === '0' ? 1 : (Number(cur) + 1) % 5; order('priority', { pawn, job, level: next }, true); };
    });
    z.querySelectorAll('[data-build]').forEach((b) => { b.onclick = () => order('build', { room: b.dataset.build }); });
    z.querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = () => order('cancel-build', { index: Number(b.dataset.cancel) }); });
    z.querySelectorAll('[data-tech]').forEach((b) => { b.onclick = () => order('research', { tech: b.dataset.tech }); });
    z.querySelectorAll('[data-forge]').forEach((b) => { b.onclick = () => order('forge'); });
    z.querySelectorAll('[data-trip]').forEach((b) => { b.onclick = () => order('expedition', { place: b.dataset.trip }); });
    z.querySelectorAll('[data-gift]').forEach((b) => { b.onclick = () => order('gift', { sect: b.dataset.gift }); });
    z.querySelectorAll('[data-burn]').forEach((b) => { b.onclick = () => { if (confirm('Burn this manual? It cannot be recovered.')) order('burn', { manual: b.dataset.burn }); }; });
  }

  function disciples() {
    return `<div class="pawns">${S.pawns.map((p) => `<button class="pawn ${p.away ? 'away' : ''}" data-pawn="${esc(p.id)}">
      ${face(p, 56)}
      <span class="grow"><b>${esc(p.name)}</b>${p.title ? ` <i class="dim">${esc(p.title)}</i>` : ''}${p.master ? ' <span class="tag gold">You</span>' : ''}
        <span class="tag blue">${esc(p.realm)} · ${esc(p.stage)}</span> <span class="tag">${esc(p.rank)}</span>${p.direct ? ' <span class="tag gold">Direct disciple</span>' : ''}
        ${p.bonds.filter((x) => x.kind).slice(0, 2).map((x) => `<span class="tag ${x.kind === 'rival' ? 'red' : 'jade'}">${x.kind === 'rival' ? '⚔' : '♥'} ${esc(x.name.split(' ')[0])}</span>`).join(' ')}
        <span class="doing">${p.ready ? `<span class="tag gold">⚡ Ready for ${esc(p.next_realm)}</span> ` : ''}${p.broken ? '<span class="tag red">Qi deviation</span> ' : ''}${p.inspired ? '<span class="tag jade">Inspired</span> ' : ''}${p.sick ? '<span class="tag red">Sick</span> ' : ''}${esc(p.doing)}</span>
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
          ${lv || ''}<small>${sk ? sk.lv : 0}${sk ? flames(sk.passion) : ''}</small></button></td>`;
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
    }).join('')}</ul><p class="dim small" style="margin:8px 0 0">Switching topic keeps what was already learned.</p>`;
  }

  function world() {
    const stones = (S.res.find((r) => r.id === 'stones') || {}).n || 0;
    const relCls = (r) => (r >= 15 ? 'jade' : r > -15 ? '' : 'red');
    return `<div class="banner" style="background-image:linear-gradient(#120d0a55,#120d0acc),url(${backdrop('map')})"><h2>${esc(S.name)}</h2>
        <p>Fame <b class="num">${S.fame}</b>. Fame is won at the gate, in the arena and under the lightning; talented youths seek out famous sects.</p></div>
      <h3>Great Works</h3>
      <p class="dim small">Long goals with no deadline. Each one finished brings fame and a day the disciples never forget.</p>
      <div class="works">${S.works.map((w) => `<div class="work ${w.done ? 'done' : ''}"><b>${esc(w.name)}</b> ${w.done ? '<span class="tag gold">Achieved</span>' : ''}<br><span class="small dim">${esc(w.text)}</span>
          <ul>${w.lines.map((l) => `<li class="${l.ok ? 'ok' : ''}">${l.ok ? '✓' : '○'} ${esc(l.text)}</li>`).join('')}</ul></div>`).join('')}</div>
      <h3 style="margin-top:16px">Expeditions</h3>
      <p class="dim small">Send your two strongest disciples out. They cannot work or defend the sect while away, and the road forges bonds.</p>
      <ul class="list">${S.places.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> <span class="tag">${x.hours} hours</span><br><span class="small dim">${esc(x.text)}</span></span>
          <button class="btn" data-trip="${esc(x.id)}" ${S.trip ? 'disabled' : ''}>${S.trip ? 'A party is out' : 'Send a party'}</button></li>`).join('')}</ul>
      <h3 style="margin-top:16px">The sects of the region</h3>
      <ul class="list">${S.sects.map((x) => `<li class="row"><span class="grow"><b>${esc(x.name)}</b> <span class="tag">${esc(x.kind)}</span> <span class="tag ${relCls(x.rel)}">${esc(x.stance)} ${x.rel > 0 ? '+' : ''}${x.rel}</span>
          <br><span class="small dim">Young master: ${esc(x.young)}. ${x.rel <= -15 ? 'Their raiders know the way to your gate.' : x.rel >= 15 ? 'They will not raid you.' : 'They are watching.'}</span></span>
          <button class="btn" data-gift="${esc(x.id)}" ${stones >= 10 ? '' : 'disabled'}>Send gifts (10 💎)</button></li>`).join('')}</ul>
      <h3 style="margin-top:16px">Scripture Pavilion</h3>
      <p class="dim small">Each disciple practises the best manual of each kind that their rank allows. Outer disciples read Yellow grade, Inner disciples Mystic, Core disciples Earth, Elders and the Sect Master Heaven.</p>
      <ul class="list">${S.manuals.map((m) => `<li class="row"><span class="grow"><b>${esc(m.name)}</b> <span class="tag ${m.demonic ? 'red' : 'gold'}">${m.demonic ? 'Forbidden' : `${esc(m.grade)} grade`}</span>
          <br><span class="small dim">${esc(m.kind)}, +${m.bonus}%${m.demonic ? ' and more. It darkens the heart of everyone who reads it' : ''}. ${esc(m.rank)}${m.demonic ? '' : ' and above'}.</span></span>
          ${m.demonic ? `<button class="btn quiet" data-burn="${esc(m.id)}">Burn it</button>` : ''}</li>`).join('')}</ul>
      <h3 style="margin-top:16px">Artifacts</h3>
      <p class="dim small">One per disciple; give them out from a disciple's page. They come from raids won at the gate, the tournament, the Ruined Sect, and your own forge. This season favours ${ELEMENT_ICON[S.season_element] || ''} ${esc(S.season_element)} roots.</p>
      ${S.artifacts.length ? `<ul class="list">${S.artifacts.map((a) => `<li><b>${esc(a.name)}</b> ${a.owner ? `<span class="tag jade">${esc(a.owner)}</span>` : '<span class="tag">In the vault</span>'}<br><span class="small dim">${esc(a.text)} ${esc(a.origin)}</span></li>`).join('')}</ul>` : '<p class="dim">None yet.</p>'}
      <button class="btn" data-forge ${S.can_forge ? '' : 'disabled'}>${S.has_forge ? 'Forge an artifact (40 stone, 20 wood, 8 💎)' : 'Forging needs an Alchemy Hall'}</button>
      <h3 style="margin-top:16px">Treasures</h3>
      ${S.treasures.length || S.beast ? `<ul class="list">${S.treasures.map((t) => `<li><b>${esc(t.name)}</b><br><span class="small dim">${esc(t.text)}</span></li>`).join('')}
        ${S.beast ? `<li><b>${esc(S.beast.name)}</b> <span class="tag jade">Guardian beast</span><br><span class="small dim">Guards the gate with strength ${S.beast.power}, growing with age. Eats one rice a day.</span></li>` : ''}</ul>`
        : '<p class="dim">The vault is empty. Treasures come from auctions, secret realms and inheritances.</p>'}`;
  }

  function chronicle() {
    const recent = S.log.length ? `<ul class="list">${S.log.map((e) => `<li class="letter ${esc(e.kind)}"><b>${esc(e.title)}</b> <span class="dim small">day ${e.day}</span><br><span class="small">${esc(e.text)}</span></li>`).join('')}</ul>`
      : '<p class="dim">Nothing has happened yet.</p>';
    return `${recent}<h3 style="margin-top:18px">Annals of the ${esc(S.name)}</h3><p class="dim small">What will be remembered: who came, who rose, who fell.</p>
      <ol class="annals">${S.annals.map((a) => `<li><span class="dim small">Year ${a.year}, day ${a.day}</span> ${esc(a.text)}</li>`).join('')}</ol>`;
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
        <p class="small dim">${p.tribulation ? 'Heaven answers with lightning. A failure wounds badly, and a disciple who is already hurt may not survive it.' : 'A failure wounds them and scatters some of their qi.'} Each failure makes the next attempt a little surer.</p>
        <button class="btn primary big" data-attempt>${p.tribulation ? 'Face the tribulation' : 'Attempt the breakthrough'}</button></section>` : '';
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
    const go = $('[data-attempt]', s);
    if (go) go.onclick = async () => {
      go.disabled = true;
      const res = await order('attempt', { pawn: id }, true);
      if (res.ok === false) { toast(res.error); return; }
      const ev = res.event || {};
      openSheet(`<section class="breakthrough result ${res.success ? 'won' : 'lost'}" style="background-image:linear-gradient(#120d0a99,#120d0aee),url(${backdrop('seclusion')})">
          <h2>${esc(ev.title || '')}</h2><p>${esc(ev.text || '')}</p></section>
        <button class="btn primary big" data-close style="margin-top:12px">Continue</button>`);
      $('[data-close]', $('#sheet')).onclick = closeSheet;
    };
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

  function paintLight() {
    const d = $('#daylight'); if (!d) return;
    const hh = S.hod;
    d.className = `daylight ${hh >= 21 || hh < 5 ? 'night' : hh < 8 ? 'dawn' : hh >= 18 ? 'dusk' : 'day'} ${S.season === 'Winter' ? 'winter' : ''}`;
  }

  function paint() { paintTop(); paintEvent(); paintScene(); paintLight(); paintTabs(); }

  view.innerHTML = `<div id="sect-root"><div id="z-top"></div><div class="grid2">${h.todayPanel()}${h.masterPanel()}</div>
    <div id="z-event"></div><section class="panel scenewrap" id="z-scene"></section><section class="panel" id="z-tabs" style="margin-top:14px"></section></div>`;
  h.bindToday(view);
  paint();
  stop();
  timer = setInterval(beat, 1000);
  return { stop, order };
}
