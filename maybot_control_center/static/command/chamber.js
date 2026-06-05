import { $, api, esc, mountRail, starfield } from '/lib.js';

mountRail('disciples');
starfield('scene-canvas');

let ROWS = [];
let active = null;

const STATUS_DOT = { working: 'dot-working', idle: 'dot-idle', queued: 'dot-working', error: 'dot-error' };
const STATUS_LABEL = { working: 'Cultivating a task', idle: 'In repose', queued: 'Awaiting orders', error: 'Tribulation' };

function initial(name) { return (name || '?').trim().charAt(0).toUpperCase(); }

/* confidence ~ blend of merit tier success and aptitude, clamped 12..99 */
function confidence(r) {
  const rep = r.reputation || {}; const sig = rep.signals || {};
  const succ = Number(sig.success_pct);
  const apt = Number((r.governance || {}).aptitude);
  const base = Number.isFinite(succ) ? succ : 70;
  const v = 0.6 * base + 0.4 * (Number.isFinite(apt) ? apt : 50) - (sig.fail_streak || 0) * 6;
  return Math.max(12, Math.min(99, Math.round(v)));
}

function renderRoster() {
  $('roster-sub').textContent = `${ROWS.length} disciples in the sect`;
  $('roster').innerHTML = ROWS.map((r) => {
    const cult = r.cultivation || {};
    const now = r.status === 'working' && r.current_task ? r.current_task : (STATUS_LABEL[r.status] || r.status);
    return `<div class='disc-card ${r.name === active ? 'active' : ''}' data-name='${esc(r.name)}'>
      <div class='dav'>${esc(initial(r.name))}<span class='dav-dot ${STATUS_DOT[r.status] || 'dot-idle'}'></span></div>
      <div class='disc-meta'>
        <div class='disc-name'>${esc(r.name)}</div>
        <div class='disc-rank'>${esc(cult.rank_title || r.role || 'Disciple')}</div>
        <div class='disc-now ${r.status === 'working' ? 'working' : ''}'>${esc(now)}</div>
      </div>
    </div>`;
  }).join('');
  $('roster').querySelectorAll('.disc-card').forEach((c) => c.onclick = () => select(c.dataset.name));
}

function metric(lbl, val, sub, accent) {
  return `<div class='metric-card glass ${accent ? 'accent-' + accent : ''}'>
    <div class='metric-lbl'>${lbl}</div><div class='metric-val'>${val}</div>${sub ? `<div class='metric-sub'>${sub}</div>` : ''}</div>`;
}

function recommend(r) {
  const recs = []; const cult = r.cultivation || {}; const rep = r.reputation || {}; const sig = rep.signals || {};
  if (cult.stones_to_next > 0 && cult.next_realm)
    recs.push(['💎', `${cult.stones_to_next} spirit stones from breakthrough to <b>${esc(cult.next_realm)}</b> — assign focused work to push the realm.`]);
  if ((sig.fail_streak || 0) >= 2) recs.push(['⚠', `On a ${sig.fail_streak}-task failure streak — pair with a senior or lighten the load.`]);
  if (r.status === 'idle') recs.push(['💤', 'Idle right now — a fitting moment to delegate a mission.']);
  if ((r.governance || {}).is_leader) recs.push(['👑', 'Sect Leader — best reserved for oversight and critical missions.']);
  if (cult.in_seclusion) recs.push(['🚪', 'In closed-door seclusion — a breakthrough is brewing; do not disturb.']);
  const apt = (r.governance || {}).aptitude_parts || {};
  if (Number(apt.knowledge) < 30) recs.push(['📚', 'Low knowledge score — feed it documentation tasks to grow its skills.']);
  if (!recs.length) recs.push(['✓', 'Performing well across the board — keep the missions flowing.']);
  return recs.slice(0, 4).map(([i, t]) => `<div class='rec'><span class='rec-ico'>${i}</span><span class='rec-txt'>${t}</span></div>`).join('');
}

function reasoning(transcript) {
  const msgs = (transcript || []).filter((m) => m.role === 'assistant').slice(-6).reverse();
  if (!msgs.length) return `<div class='muted' style='padding:10px 0'>No reasoning recorded yet.</div>`;
  return msgs.map((m) => `<div class='reason'>${esc(String(m.content || '').slice(0, 320))}</div>`).join('');
}

function timelineHTML(entries) {
  const list = (entries || []).slice().reverse();
  if (!list.length) return `<div class='muted' style='padding:10px 0'>No chronicle yet.</div>`;
  return `<div class='tline'>` + list.slice(0, 40).map((e) =>
    `<div class='evt'><span class='evt-ico'>${esc(e.glyph || '•')}</span><span class='evt-txt'>${esc(e.detail || e.kind)}</span><span class='evt-time'>${esc(e.kind || '')}</span></div>`).join('') + `</div>`;
}

async function select(name) {
  active = name; renderRoster();
  const r = ROWS.find((x) => x.name === name) || { name };
  const cult = r.cultivation || {}; const rep = r.reputation || {}; const sig = rep.signals || {}; const gov = r.governance || {};
  const conf = confidence(r);
  const now = r.status === 'working' && r.current_task ? r.current_task : (STATUS_LABEL[r.status] || r.status);
  const skills = (cult.skills || []).map((s) => `<span class='tag skill'>${esc(s)}</span>`).join('');
  const titles = (r.titles || []).map((t) => `<span class='tag title'>${esc(typeof t === 'string' ? t : (t.name || t.title || ''))}</span>`).join('');
  const specialty = gov.specialty ? `<span class='tag'>${esc(gov.specialty)}</span>` : '';

  $('main').innerHTML = `
    <section class='dossier glass rise'>
      <div class='dossier-head'>
        <div class='portrait'>${esc(initial(name))}<span class='portrait-dot ${STATUS_DOT[r.status] || 'dot-idle'}'></span></div>
        <div class='dossier-id'>
          <div class='dossier-name'>${esc(name)}</div>
          <div class='dossier-rank'>${esc(cult.rank_title || 'Disciple')} · ${esc(cult.realm_name || 'Mortal')} ${esc(cult.stage || '')} · ${esc(r.model || '')}</div>
          <div class='dossier-now'>Current mission — <b>${esc(now)}</b></div>
        </div>
      </div>
      <div class='confidence'>
        <span class='metric-lbl'>Confidence</span>
        <div class='conf-bar'><span style='width:${conf}%'></span></div>
        <span class='conf-val'>${conf}%</span>
      </div>
    </section>

    <div class='dgrid'>
      ${metric('Tasks Done', r.tasks_done || 0, 'lifetime', 'jade')}
      ${metric('Merit', rep.merit ?? '—', esc(rep.tier || ''), 'gold')}
      ${metric('Success', Number.isFinite(sig.success_pct) ? sig.success_pct + '%' : '—', `${sig.done || 0} done · ${sig.failed || 0} failed`, 'azure')}
      ${metric('Realm', esc(cult.realm_name || 'Mortal'), esc(cult.layer_label || ''))}
      ${metric('Breakthroughs', cult.breakthroughs || 0, cult.next_realm ? `${cult.stones_to_next} stones to ${esc(cult.next_realm)}` : 'peak realm')}
      ${metric('Aptitude', Math.round(gov.aptitude || 0), esc(gov.is_leader ? 'Sect Leader' : gov.is_elder ? 'Elder' : 'Disciple'), gov.is_leader ? 'gold' : '')}
    </div>

    ${(skills || titles || specialty) ? `<div class='glass' style='padding:18px'>
      <div class='panel-title'>Mastery &amp; Honors</div>
      <div class='tag-row'>${specialty}${skills}${titles || `<span class='muted' style='font-size:12px'>No titles earned yet.</span>`}</div>
    </div>` : ''}

    <div class='cols-2'>
      <section class='glass rise d2' style='padding:20px'>
        <div class='panel-title'>Recent Work</div>
        <div id='c-timeline' style='margin-top:12px'><div class='muted'>Loading chronicle…</div></div>
      </section>
      <section class='glass rise d3' style='padding:20px'>
        <div class='panel-title'>Recommendations</div>
        <div class='recs' style='margin-top:12px'>${recommend(r)}</div>
      </section>
    </div>

    <section class='glass rise d4' style='padding:20px'>
      <div class='panel-title'>Reasoning &amp; Decisions</div>
      <div id='c-reason' style='margin-top:8px'><div class='muted'>Loading transcript…</div></div>
    </section>`;

  const [detail, chron] = await Promise.all([
    api('/api/agents/' + encodeURIComponent(name)),
    api('/api/chronicle/' + encodeURIComponent(name)),
  ]);
  const tl = $('c-timeline'); if (tl) tl.innerHTML = timelineHTML(chron && chron.timeline);
  const rs = $('c-reason'); if (rs) rs.innerHTML = reasoning(detail && detail.transcript);
}

async function load() {
  const data = await api('/api/agents');
  if (window.__needAuth && !data) {
    $('roster-sub').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`;
    return;
  }
  ROWS = (data && data.agents) || [];
  renderRoster();
  if (!active && ROWS.length) select(ROWS[0].name);
  else renderRoster();
}
load();
setInterval(load, 12000);
