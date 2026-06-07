import { $, api, post, esc, money, timeAgo, mountRail, countUp, bindTilt, starfield } from '/lib.js';

mountRail('trade');
starfield('scene-canvas');

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
  const total = ((cmd && cmd.account_base) || 0) + t.realized;
  const cell = (lbl, val, cls, big) => `<div class='hero-cell'><div class='hero-lbl'>${lbl}</div>
    <div class='hero-val ${cls} ${big ? 'big' : ''}' data-num='${val}'>—</div></div>`;
  $('hero').innerHTML = `<div class='hero-grid'>` +
    cell('Today', t.today, t.today >= 0 ? 'pos' : 'neg') +
    cell('This Week', t.week, t.week >= 0 ? 'pos' : 'neg') +
    cell('This Month', t.month, t.month >= 0 ? 'pos' : 'neg') +
    cell('Total Value', total, '', true) + `</div>`;
  $('hero').querySelectorAll('.hero-val').forEach((el, i) =>
    countUp(el, Number(el.dataset.num), i === 3 ? (x) => `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : (x) => money(x)));
}

function renderMetrics(t, cmd) {
  const acct = ((cmd && cmd.account_base) || 0) + t.realized;
  const winRate = t.fillRate != null ? Math.round(t.fillRate * 100) : null;
  const pf = t.demoPF != null ? t.demoPF : (t.realized > 0 ? (1 + Math.min(3, Math.abs(t.realized) / Math.max(1, Math.abs(t.exposure) || 1000))) : null);
  const card = (lbl, val, sub, accent) => `<div class='metric-card glass ${accent || ''}' data-tilt>
    <div class='metric-lbl'>${lbl}</div><div class='metric-val'>${val}</div>${sub ? `<div class='metric-sub'>${sub}</div>` : ''}</div>`;
  $('metrics').innerHTML = [
    card('Account Value', `$${acct.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'capital deployed', 'accent-azure'),
    card('Open Exposure', money(t.exposure).replace('+', ''), `${t.botCount} bot${t.botCount === 1 ? '' : 's'} active`, 'accent-gold'),
    card('Open Positions', t.positions, 'live on the book', ''),
    card('Trades Today', t.trades, 'executed', ''),
    card('Win Rate', winRate != null ? `${winRate}%` : '—', 'fill rate', 'accent-jade'),
    card('Profit Factor', pf != null ? pf.toFixed(2) : '—', t.realized >= 0 ? 'positive' : 'drawdown', t.realized >= 0 ? 'accent-jade' : 'accent-crimson'),
  ].join('');
  bindTilt();
}

function renderPositions(cmd) {
  const ps = (cmd && cmd.positions) || [];
  $('pos-count').textContent = ps.length ? `${ps.length} on the book` : '';
  if (!ps.length) { $('positions').innerHTML = `<div class='muted' style='padding:14px'>No open positions. Wire a broker feed or set MAYBOT_DEMO=1.</div>`; return; }
  const head = `<div class='pos-row pos-head'><span>Symbol</span><span>Side</span><span>Qty</span><span>Entry</span><span>Last</span><span>P/L</span></div>`;
  $('positions').innerHTML = head + ps.map((p) => {
    const pos = Number(p.pnl) >= 0;
    return `<div class='pos-row'>
      <span class='pos-tick'>${esc(p.ticker)}</span>
      <span class='pos-side ${p.side === 'SHORT' ? 'short' : 'long'}'>${esc(p.side || 'LONG')}</span>
      <span>${esc(p.qty)}</span>
      <span>$${Number(p.entry).toFixed(2)}</span>
      <span>$${Number(p.last).toFixed(2)}</span>
      <span class='pos-pnl ${pos ? 'pos' : 'neg'}'>${money(p.pnl)} <i>${pos ? '+' : ''}${Number(p.pnl_pct).toFixed(2)}%</i></span>
    </div>`;
  }).join('');
}

function renderOpps(cmd) {
  const opps = (cmd && cmd.opportunities) || [];
  $('opp-count').textContent = opps.length ? `${opps.length} signals` : '';
  $('opps').innerHTML = opps.length ? opps.map((o) => `<div class='opp'>
    <div class='opp-tick'>${esc(o.ticker)}</div>
    <div class='opp-meta'>
      <div class='opp-row'><span>Edge <b>${Number(o.edge).toFixed(1)}%</b></span><span>Confidence <b>${o.confidence}%</b></span></div>
      <div class='signal'><span style='width:${Math.max(6, Math.min(100, o.confidence))}%'></span></div>
    </div>
    <div class='opp-status st-${esc(o.status)}'>${esc(o.status)}</div></div>`).join('')
    : `<div class='muted' style='padding:6px'>No active signals.</div>`;
}

function renderBots(cmd) {
  const bots = (cmd && cmd.bots) || [];
  const on = (s) => s === 'active' || s === 'throttled';
  $('bots').innerHTML = bots.length ? bots.map((b) => {
    const pos = Number(b.pnl_today) >= 0, st = b.status || '';
    const act = on(st)
      ? `<button class='bctl' data-bot='${esc(b.name)}' data-act='${st === 'throttled' ? 'resume' : 'throttle'}'>${st === 'throttled' ? 'Resume' : 'Throttle'}</button>
         <button class='bctl warn' data-bot='${esc(b.name)}' data-act='pause'>Pause</button>`
      : `<button class='bctl' data-bot='${esc(b.name)}' data-act='resume'>Resume</button>`;
    return `<div class='bot'>
      <div class='bot-top'><span class='bot-name'>${esc(b.name)}</span>
        <span class='bot-status ${on(st) ? 'on' : 'off'}'>${esc(st)}</span></div>
      <div class='bot-pnl ${pos ? 'pos' : 'neg'}'>${money(b.pnl_today)}<span class='muted'> today</span></div>
      <div class='bot-meta'><span>MTD <b>${money(b.pnl_month)}</b></span><span>${b.trades} trades</span><span>${b.win_rate}% win</span></div>
      <div class='bot-ctl'>${act}</div>
    </div>`;
  }).join('') : `<div class='muted'>No bots reporting.</div>`;
  $('bots').querySelectorAll('.bctl').forEach((el) => el.onclick = () => botAction(el.dataset.bot, el.dataset.act));
}

async function botAction(bot, action) {
  const r = await post('/api/bots/control', { bot, action });
  if (!r || r.error) { flash(r && r.error ? r.error : 'Operator role required for control'); return; }
  refresh();
}

/* ---- live data chip, ML signal overlay, risk + control, advisor ---- */
function renderLive(cmd) {
  const chip = $('live-chip'); const live = cmd && (cmd.live_market || cmd.broker);
  chip.hidden = !live;
  if (live) chip.innerHTML = `<i></i>${cmd.broker ? 'BROKER' : 'LIVE'}`;
}

function applySignals(cmd) {
  const sig = (cmd && cmd.signals) || []; if (!sig.length) return;
  const by = {}; sig.forEach((s) => { by[s.symbol] = s; });
  $('opps').querySelectorAll('.opp').forEach((row) => {
    const t = row.querySelector('.opp-tick'); const s = t && by[t.textContent.trim()];
    if (!s) return;
    const tag = document.createElement('div');
    tag.className = `sig-tag ${s.direction}`;
    tag.innerHTML = `ML ${s.direction} · ${(s.score * 100) | 0}%`;
    row.querySelector('.opp-meta').appendChild(tag);
  });
}

function renderRisk(cmd) {
  const r = (cmd && cmd.risk) || {};
  $('risk-note').textContent = r.halted ? 'TRADING HALTED' : 'nominal';
  const dd = Number(r.drawdown_pct || 0), exp = Number(r.exposure || 0);
  const reasons = (r.reasons || []).map((x) => esc(x)).join(' · ');
  $('risk-panel').innerHTML = `
    <div class='risk-grid'>
      <div class='risk-stat'><span>Status</span><b class='${r.halted ? 'neg' : 'pos'}'>${r.halted ? 'HALTED' : 'Live'}</b></div>
      <div class='risk-stat'><span>Exposure</span><b>$${exp.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b></div>
      <div class='risk-stat'><span>Drawdown</span><b class='${dd > 0 ? 'neg' : ''}'>${dd.toFixed(1)}%</b></div>
      <div class='risk-actions'>
        <button class='cbtn ${r.halted ? '' : 'warn'}' id='kill-btn'>${r.halted ? 'Release halt' : 'Kill-switch'}</button>
        <button class='cbtn danger' id='flatten-btn'>Flatten all</button>
      </div>
    </div>${reasons ? `<div class='muted' style='margin-top:8px;font-size:12px'>${reasons}</div>` : ''}`;
  $('kill-btn').onclick = async () => { const x = await post('/api/risk/kill', { on: !r.halted }); if (!x || x.error) flash('Operator role required'); else refresh(); };
  $('flatten-btn').onclick = async () => { if (!confirm('Flatten ALL positions across every bot?')) return; const x = await post('/api/bots/flatten'); if (!x || x.error) flash('Operator role required'); else { flash('Flatten-all requested'); refresh(); } };
}

async function loadAdvisor() {
  const a = await api('/api/advisor'); if (!a || !a.text) return;
  $('advisor-wrap').hidden = false;
  $('adv-src').textContent = a.source === 'llm' ? '· live' : '· local';
  const hi = (a.highlights || []).map((h) => `<li>${esc(h)}</li>`).join('');
  const sg = (a.suggestions || []).map((s) => `<li>${esc(s)}</li>`).join('');
  $('advisor').innerHTML = `<p class='adv-text'>${esc(a.text)}</p>
    ${hi ? `<div class='adv-cols'><div><div class='adv-h'>Highlights</div><ul>${hi}</ul></div>${sg ? `<div><div class='adv-h'>Suggestions</div><ul>${sg}</ul></div>` : ''}</div>` : ''}`;
}

let flashT;
function flash(msg) {
  let el = $('toast'); if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show'); clearTimeout(flashT); flashT = setTimeout(() => el.classList.remove('show'), 2600);
}

function renderEvents(cmd) {
  const ev = (cmd && cmd.events) || [];
  $('events').innerHTML = ev.length ? ev.map((e) => `<div class='evt'><span class='evt-ico'>${esc(e.icon || '•')}</span>
    <span class='evt-txt'>${esc(e.text)}</span><span class='evt-time'>${timeAgo(e.ts)}</span></div>`).join('')
    : `<div class='muted' style='padding:6px'>No recent activity.</div>`;
}

function jarvis(cmd, t) {
  const exe = ((cmd && cmd.opportunities) || []).filter((o) => o.status === 'EXECUTE' || o.status === 'READY').length;
  const bits = [];
  if (t.today) bits.push(`Today's PnL <b>${money(t.today)}</b>`);
  bits.push(`<b>${t.positions}</b> open · <b>${t.trades}</b> trades today`);
  if (exe) bits.push(`<b>${exe}</b> signal${exe === 1 ? '' : 's'} hot`);
  $('jarvis').innerHTML = bits.join(' · ');
}

async function refresh() {
  const [ov, cmd] = await Promise.all([api('/api/overview'), api('/api/command')]);
  if (window.__needAuth && !ov && !cmd) { $('jarvis').innerHTML = `Authentication required — <a href='/console' style='color:var(--violet)'>sign in</a>.`; return; }
  let t = tradingFromProjects((ov && ov.projects) || []);
  if (cmd && cmd.demo && cmd.pnl) {
    const d = cmd.pnl, tr = cmd.trading || {};
    t = { today: d.today, week: d.week, month: d.month, realized: d.total - (cmd.account_base || 0),
          exposure: tr.exposure || 0, positions: tr.positions || 0, trades: tr.trades_today || 0,
          fillRate: (tr.win_rate || 0) / 100, botCount: tr.bots || t.botCount, demoPF: tr.profit_factor };
  }
  renderHero(t, cmd); renderMetrics(t, cmd); renderPositions(cmd); renderOpps(cmd); renderBots(cmd); renderEvents(cmd); jarvis(cmd, t);
  renderLive(cmd); applySignals(cmd); renderRisk(cmd);
}

setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
refresh();
setInterval(refresh, 7000);
loadAdvisor();
setInterval(loadAdvisor, 30000);
