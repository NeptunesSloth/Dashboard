import { $, api, esc, money, mountRail, countUp, bindTilt, starfield } from '/lib.js';

mountRail('treasury');
starfield('scene-canvas');

const COLORS = ['#a78bfa', '#38bdf8', '#34d399', '#fbbf24', '#fb5e7e', '#7c5cff'];

function deriveCapital(ov, cmd) {
  const base = (cmd && cmd.account_base) || 0;
  let exposure = 0, realized = 0, alloc = [];
  if (cmd && cmd.demo && cmd.trading) {
    const tr = cmd.trading; const d = cmd.pnl || {};
    exposure = tr.exposure || 0; realized = (d.total || 0) - base;
    alloc = ((cmd.bots) || []).map((b) => ({ name: b.name, value: Number(b.exposure) || 0, pnl: Number(b.pnl_month) || 0 }));
    return { accountValue: tr.account_value || (base + realized), buyingPower: tr.buying_power || 0, exposure, realized, monthPnl: d.month || 0, alloc };
  }
  const bots = ((ov && ov.projects) || []).filter((p) => p.type === 'trading_bot');
  const num = (m, k) => { const v = Number((m || {})[k]); return Number.isFinite(v) ? v : 0; };
  bots.forEach((p) => {
    const m = p.metrics || {}; const ex = num(m, 'open_exposure'); exposure += ex; realized += num(m, 'realized_pnl');
    alloc.push({ name: p.name, value: ex, pnl: num(m, 'profit_this_month') });
  });
  const monthPnl = bots.reduce((s, p) => s + num(p.metrics, 'profit_this_month'), 0);
  return { accountValue: base + realized, buyingPower: Math.max(0, base + realized - exposure), exposure, realized, monthPnl, alloc };
}

function renderHero(c) {
  const cell = (lbl, val, cls, big) => `<div class='hero-cell'><div class='hero-lbl'>${lbl}</div>
    <div class='hero-val ${cls || ''} ${big ? 'big' : ''}' data-num='${val}'>—</div></div>`;
  $('hero').innerHTML = `<div class='hero-grid'>` +
    cell('Total Account Value', c.accountValue, '', true) +
    cell('Buying Power', c.buyingPower, '') +
    cell('Deployed Capital', c.exposure, '') +
    cell('Realized PnL', c.realized, c.realized >= 0 ? 'pos' : 'neg') + `</div>`;
  $('hero').querySelectorAll('.hero-val').forEach((el) =>
    countUp(el, Number(el.dataset.num), (x) => `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}`));
}

function renderAlloc(c, cmd) {
  const items = (c.alloc || []).filter((a) => a.value > 0).sort((a, b) => b.value - a.value);
  const deployed = items.reduce((s, a) => s + a.value, 0);
  const cash = Math.max(0, c.buyingPower);
  const total = deployed + cash || 1;
  $('alloc-sub').textContent = deployed ? `$${deployed.toLocaleString(undefined, { maximumFractionDigits: 0 })} deployed` : '';
  const rows = items.map((a, i) => {
    const pct = (a.value / total) * 100; const col = COLORS[i % COLORS.length];
    return `<div class='alloc-row'>
      <span class='alloc-name'><i style='background:${col}'></i>${esc(a.name)}</span>
      <div class='alloc-bar'><span style='width:${pct.toFixed(1)}%; background:${col}'></span></div>
      <span class='alloc-val'>$${a.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}<i class='${a.pnl >= 0 ? 'pos' : 'neg'}'>${money(a.pnl)}</i></span>
    </div>`;
  }).join('');
  const cashRow = `<div class='alloc-row'>
      <span class='alloc-name'><i style='background:#3a4256'></i>Cash / Buying Power</span>
      <div class='alloc-bar'><span style='width:${(cash / total * 100).toFixed(1)}%; background:#3a4256'></span></div>
      <span class='alloc-val'>$${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
    </div>`;
  $('alloc').innerHTML = (rows || '') + cashRow ||
    `<div class='muted'>No capital allocation to show.</div>`;
}

function renderMetrics(c, cmd) {
  const goal = (cmd && cmd.monthly_goal) || 10000;
  const goalPct = Math.max(0, Math.min(100, Math.round((c.monthPnl / goal) * 100)));
  const util = c.accountValue ? Math.round((c.exposure / c.accountValue) * 100) : 0;
  const card = (lbl, val, sub, accent) => `<div class='metric-card glass ${accent || ''}' data-tilt>
    <div class='metric-lbl'>${lbl}</div><div class='metric-val'>${val}</div>${sub ? `<div class='metric-sub'>${sub}</div>` : ''}</div>`;
  const ring = `<div class='metric-card glass accent-jade' data-tilt><div class='metric-lbl'>Monthly Goal</div>
    <div class='goal-card' style='margin-top:8px'><div class='ring' style='--p:${goalPct}'><b>${goalPct}%</b></div>
      <div><div class='metric-val' style='font-size:18px'>${money(c.monthPnl)}</div><div class='metric-sub'>of $${goal.toLocaleString()}</div></div></div></div>`;
  $('metrics').innerHTML = [
    card('Month-to-Date', money(c.monthPnl), 'realized + open', c.monthPnl >= 0 ? 'accent-jade' : 'accent-crimson'),
    card('Capital at Work', `${util}%`, 'of account value', 'accent-gold'),
    card('Cash Reserve', `$${Math.max(0, c.buyingPower).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'available', 'accent-azure'),
    ring,
  ].join('');
  bindTilt();
}

function renderVault(tr) {
  if (!tr) { $('vault').innerHTML = `<div class='muted'>Treasury unavailable.</div>`; return; }
  $('vault').innerHTML = `
    <div class='vault-balance'><span class='vault-coin'>◈</span>
      <div><div class='vault-num' id='vbal'>—</div><div class='metric-sub'>spirit stones</div></div></div>
    <div class='kvs' style='margin-top:14px'>
      <div class='kv'><span>Income / hour</span><b>${Number(tr.income_per_hour || 0).toLocaleString()} ◈</b></div>
      <div class='kv'><span>Spirit vein rate</span><b>${Number(tr.vein_rate || 0).toLocaleString()} ◈/h</b></div>
    </div>`;
  countUp($('vbal'), Number(tr.balance) || 0, (x) => `${Math.round(x).toLocaleString()} ◈`);
}

function renderFlow(tr) {
  if (!tr) { $('flow').innerHTML = ''; return; }
  $('flow').innerHTML = `
    <div class='flow-row'><span class='flow-ico pos'>▲</span><span>Total income</span><b class='pos'>${Number(tr.total_income || 0).toLocaleString()} ◈</b></div>
    <div class='flow-row'><span class='flow-ico neg'>▼</span><span>Total spent</span><b class='neg'>${Number(tr.total_spent || 0).toLocaleString()} ◈</b></div>`;
}

async function refresh() {
  const [ov, cmd, tr] = await Promise.all([api('/api/overview'), api('/api/command'), api('/api/treasury')]);
  if (window.__needAuth && !cmd && !ov) { $('jarvis').innerHTML = `Authentication required — <a href='/classic' style='color:var(--violet)'>sign in</a>.`; return; }
  const c = deriveCapital(ov, cmd);
  renderHero(c); renderAlloc(c, cmd); renderMetrics(c, cmd); renderVault(tr); renderFlow(tr);
  $('jarvis').innerHTML = `Account value <b>$${c.accountValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b> · <b>${tr ? Number(tr.balance).toLocaleString() : 0} ◈</b> in reserve`;
}

setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
refresh();
setInterval(refresh, 9000);
