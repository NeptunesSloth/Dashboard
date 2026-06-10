import { $, api, post, esc, money, timeAgo, mountRail, initAccount, liveStream, debounce, countUp, starfield } from '/lib.js';

mountRail('trade');
initAccount();
starfield('scene-canvas');

function tradingFromProjects(projects) {
  const bots = (projects || []).filter((p) => p.type === 'trading_bot');
  const num = (m, k) => { const v = Number((m || {})[k]); return Number.isFinite(v) ? v : 0; };
  // Track whether ANY bot actually reported a PnL figure, so we can show an
  // honest "not reporting" state instead of a misleading $0 (a bot that hasn't
  // wired up PnL looks identical to a genuinely break-even one otherwise).
  let today = 0, week = 0, month = 0, realized = 0, exposure = 0, positions = 0, trades = 0, fillSum = 0, fillN = 0;
  let reportedToday = false, reportedRealized = false;
  bots.forEach((p) => {
    const m = p.metrics || {};
    if (Number.isFinite(Number(m.profit_today))) reportedToday = true;
    if (Number.isFinite(Number(m.realized_pnl))) reportedRealized = true;
    today += num(m, 'profit_today'); week += num(m, 'profit_this_week'); month += num(m, 'profit_this_month');
    realized += num(m, 'realized_pnl'); exposure += num(m, 'open_exposure'); positions += num(m, 'open_positions'); trades += num(m, 'trades_today');
    const fr = Number(m.fill_rate); if (Number.isFinite(fr)) { fillSum += fr; fillN++; }
  });
  return { today, week, month, realized, exposure, positions, trades, fillRate: fillN ? fillSum / fillN : null,
           botCount: bots.length, reportedToday, reportedRealized };
}

// Hover-help for the hero metrics (plain-English, like the dossier/map/fleet).
const TR_INFO = {
  today: "Summed realized profit/loss for today across all bots. Shows “not reporting” (not $0) when no bot has written PnL yet — so a genuine break-even is distinguishable from missing data.",
  week: 'Summed PnL since the start of this week (Monday).',
  acct: 'Account base (MAYBOT_ACCOUNT_BASE) plus total realized PnL across bots.',
  trades: 'Trades counted today and the average fill/win rate where bots report it.',
};

/* P&L-forward hero: big total PnL today / this week, plus key stats at a glance. */
function renderHero(t, cmd) {
  const acct = ((cmd && cmd.account_base) || 0) + t.realized;
  const winRate = t.fillRate != null ? Math.round(t.fillRate * 100) : null;
  const cls = (v) => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
  // demo mode always has PnL; otherwise honour whether any bot actually reported.
  const liveReporting = (cmd && cmd.demo) || t.reportedToday;
  const big = liveReporting
    ? `<div class='ph-big ${cls(t.today)}' data-num='${t.today}'>—</div>`
    : `<div class='ph-big ph-noreport' title='No bot has reported PnL yet. Trade counts can still show; see the Trade-bot PnL contract.'>—<span class='ph-noreport-sub'>no PnL reported yet</span></div>`;
  $('hero').innerHTML = `
    <div class='ph-main'>
      <div class='ph-lbl' title='${esc(TR_INFO.today)}' style='cursor:help'>Profit · Today</div>
      ${big}
    </div>
    <div class='ph-cell'><div class='ph-lbl' title='${esc(TR_INFO.week)}' style='cursor:help'>This Week</div>
      <div class='ph-val ${cls(t.week)}' data-num='${t.week}'>—</div>
      <div class='metric-sub'>${t.botCount} bot${t.botCount === 1 ? '' : 's'} · ${t.positions} open</div></div>
    <div class='ph-cell'><div class='ph-lbl' title='${esc(TR_INFO.acct)}' style='cursor:help'>Account Value</div>
      <div class='ph-val'>$${acct.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
      <div class='metric-sub' title='${esc(TR_INFO.trades)}' style='cursor:help'>${t.trades} trades today${winRate != null ? ` · ${winRate}% win` : ''}</div></div>`;
  const bigEl = $('hero').querySelector('.ph-big:not(.ph-noreport)');
  if (bigEl) countUp(bigEl, Number(bigEl.dataset.num), (x) => money(x));
  if (liveReporting) $('hero').querySelectorAll('.ph-val[data-num]').forEach((el) => countUp(el, Number(el.dataset.num), (x) => money(x)));
}

/* ---- scrolling ticker tape: each bot's name + today PnL, looping ---- */
function renderTicker(cmd) {
  const bots = (cmd && cmd.bots) || [];
  const tk = $('ticker'), track = $('ticker-track');
  if (!bots.length) { tk.hidden = true; track.innerHTML = ''; return; }
  tk.hidden = false;
  const item = (b) => {
    const v = Number(b.pnl_today) || 0; const pos = v >= 0;
    return `<span class='tk-item'><span class='tk-name'>${esc(b.name)}</span>
      <span class='tk-arrow ${pos ? 'pos' : 'neg'}'>${pos ? '▲' : '▼'}</span>
      <span class='tk-pnl ${pos ? 'pos' : 'neg'}'>${money(v)}</span></span>`;
  };
  const row = bots.map(item).join('');
  // duplicate the sequence so the -50% keyframe loops seamlessly
  track.innerHTML = row + row;
}

/* ---- dependency-free SVG line chart for the equity / PnL curve ---- */
function lineChartSvg(series, opts) {
  const o = opts || {};
  const pts = (series || []).map(Number).filter(Number.isFinite);
  const W = 600, H = 200, padX = 8, padTop = 12, padBot = 18;
  if (pts.length < 2) return null;
  const min = Math.min(...pts, 0), max = Math.max(...pts, 0), rng = (max - min) || 1;
  const x = (i) => padX + (i / (pts.length - 1)) * (W - padX * 2);
  const y = (v) => padTop + (1 - (v - min) / rng) * (H - padTop - padBot);
  const line = pts.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = `${x(0).toFixed(1)},${y(min).toFixed(1)} ${line} ${x(pts.length - 1).toFixed(1)},${y(min).toFixed(1)}`;
  const up = pts[pts.length - 1] >= pts[0];
  const stroke = up ? 'var(--jade)' : 'var(--crimson)';
  const zeroY = y(0).toFixed(1);
  return `<svg class='equity-svg' viewBox='0 0 ${W} ${H}' preserveAspectRatio='none' role='img'
      aria-label='${esc(o.label || 'equity curve')}'>
    <defs><linearGradient id='eqfill' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='${up ? 'rgba(52,211,153,.28)' : 'rgba(251,94,126,.24)'}'/>
      <stop offset='100%' stop-color='rgba(52,211,153,0)'/></linearGradient></defs>
    <line x1='${padX}' y1='${zeroY}' x2='${W - padX}' y2='${zeroY}' stroke='rgba(150,160,210,.22)' stroke-width='1' stroke-dasharray='3 4'/>
    <polygon points='${area}' fill='url(#eqfill)'/>
    <polyline points='${line}' fill='none' stroke='${stroke}' stroke-width='2' vector-effect='non-scaling-stroke'/>
  </svg>`;
}

/* Build a cumulative-PnL series from a project's history (or pnl points). */
function cumulativeSeries(history) {
  const vals = (history || []).map((h) => Number(h && (h.pnl ?? h.profit_today ?? h.value))).filter(Number.isFinite);
  return vals;   // history pnl is already a running figure; plot it directly
}

let CHART_SEL = '__all__';   // '__all__' or a bot/project name
function renderEquityChart(projects) {
  const bots = (projects || []).filter((p) => p.type === 'trading_bot');
  const box = $('equity-chart'), pick = $('chart-pick');
  // picker: All + each bot with usable history
  const withHist = bots.filter((b) => (b.history || []).length >= 2);
  pick.innerHTML = [`<button data-sel='__all__' class='${CHART_SEL === '__all__' ? 'on' : ''}'>All bots</button>`]
    .concat(withHist.map((b) => `<button data-sel='${esc(b.name)}' class='${CHART_SEL === b.name ? 'on' : ''}'>${esc(b.name)}</button>`))
    .join('');
  pick.querySelectorAll('button').forEach((b) => b.onclick = () => { CHART_SEL = b.dataset.sel; renderEquityChart(projects); });

  let series = [], label = 'aggregate equity';
  if (CHART_SEL === '__all__') {
    // aggregate: sum cumulative pnl across bots at each shared index
    const seqs = withHist.map((b) => cumulativeSeries(b.history));
    const n = Math.max(0, ...seqs.map((s) => s.length));
    for (let i = 0; i < n; i++) series.push(seqs.reduce((acc, s) => acc + (s[Math.min(i, s.length - 1)] || 0), 0));
  } else {
    const b = bots.find((x) => x.name === CHART_SEL);
    series = cumulativeSeries(b && b.history); label = `${CHART_SEL} equity`;
  }
  const svg = lineChartSvg(series, { label });
  box.innerHTML = svg || `<div class='equity-empty'>Not enough history yet — the curve appears as bots report PnL over time.</div>`;
}

/* per-bot sparkline grid */
function botSpark(history) {
  const pts = (history || []).map((h) => Number(h && (h.pnl ?? h.profit_today ?? h.value))).filter(Number.isFinite);
  if (pts.length < 2) return '';
  const W = 160, H = 34, min = Math.min(...pts), max = Math.max(...pts), rng = (max - min) || 1;
  const coords = pts.map((v, i) => `${(i / (pts.length - 1) * W).toFixed(1)},${(H - 3 - ((v - min) / rng) * (H - 6)).toFixed(1)}`).join(' ');
  const up = pts[pts.length - 1] >= pts[0];
  return `<svg viewBox='0 0 ${W} ${H}' preserveAspectRatio='none'><polyline points='${coords}' fill='none'
    stroke='${up ? 'var(--jade)' : 'var(--crimson)'}' stroke-width='1.5' vector-effect='non-scaling-stroke'/></svg>`;
}
function renderSparkGrid(projects, cmd) {
  const bots = (projects || []).filter((p) => p.type === 'trading_bot');
  // demo path: command.bots carries today PnL when overview has none
  const cmdBots = {}; ((cmd && cmd.bots) || []).forEach((b) => { cmdBots[b.name] = b; });
  $('spark-note').textContent = bots.length ? `${bots.length} bot${bots.length === 1 ? '' : 's'}` : '';
  if (!bots.length) { $('spark-grid').innerHTML = `<div class='muted' style='padding:6px'>No trading bots reporting yet.</div>`; return; }
  $('spark-grid').innerHTML = bots.map((b) => {
    const m = b.metrics || {};
    let pnl = Number(m.profit_today);
    if (!Number.isFinite(pnl) && cmdBots[b.name]) pnl = Number(cmdBots[b.name].pnl_today);
    const has = Number.isFinite(pnl); const pos = has && pnl >= 0;
    const spark = botSpark(b.history);
    return `<div class='spark-card'>
      <div class='sc-top'><span class='sc-name'>${esc(b.name)}</span>
        ${has ? `<span class='sc-pnl ${pos ? 'pos' : 'neg'}'>${money(pnl)}</span>` : `<span class='muted' style='font-size:11px'>${esc(b.status || '—')}</span>`}</div>
      ${spark || `<div class='sc-empty'>history pending…</div>`}</div>`;
  }).join('');
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
  const projects = (ov && ov.projects) || [];
  let t = tradingFromProjects(projects);
  if (cmd && cmd.demo && cmd.pnl) {
    const d = cmd.pnl, tr = cmd.trading || {};
    t = { today: d.today, week: d.week, month: d.month, realized: d.total - (cmd.account_base || 0),
          exposure: tr.exposure || 0, positions: tr.positions || 0, trades: tr.trades_today || 0,
          fillRate: (tr.win_rate || 0) / 100, botCount: tr.bots || t.botCount, demoPF: tr.profit_factor };
  }
  renderHero(t, cmd); renderTicker(cmd); renderEquityChart(projects); renderSparkGrid(projects, cmd);
  renderPositions(cmd); renderOpps(cmd); renderBots(cmd); renderEvents(cmd); jarvis(cmd, t);
  renderLive(cmd); applySignals(cmd); renderRisk(cmd);
}

setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
refresh();
setInterval(refresh, 15000);
liveStream((t) => { if (['tick','tasks','agents','command','overview'].includes(t)) debounce(refresh); });
loadAdvisor();
setInterval(loadAdvisor, 30000);
