let selectedProject = null;
let selectedProjectDevice = null;
let refreshPaused = false;
let refreshInterval = null;
let logsRefreshPaused = false;
let logsInterval = null;
let selectedLogLevel = 'ALL';
let viewMode = localStorage.getItem('maybot.view_mode') || 'card';
let selectedBase = null; // {device, name} of the crew member / room selected in Base View
const CONTROL_TOKEN_STORAGE_KEY = 'maybot.control_token';
// Project types that represent AI agents — surfaced in their own management area.
const AI_AGENT_TYPES = ['ai_project', 'local_ai_host'];
const TYPE_LABEL = {
  trading_bot: 'Trading Bots',
  code_project: 'Code Projects',
  game_server: 'Game Servers',
  website: 'Websites',
  school: 'School / Planning',
  ai_project: 'AI Coding Projects',
  local_ai_host: 'Local AI Hosts',
  generic: 'Generic Projects',
  github_repo: 'GitHub Repos',
};
// Flavour for the "base" room view: an activity verb + icon per project type.
const TYPE_VERB = {
  trading_bot: 'TRADING', code_project: 'BUILDING', game_server: 'HOSTING', website: 'SERVING',
  school: 'PLANNING', ai_project: 'CODING', local_ai_host: 'INFERENCE', generic: 'RUNNING',
  github_repo: 'WATCHING',
};
const TYPE_ICON = {
  trading_bot: '📈', code_project: '🛠️', game_server: '🎮', website: '🌐',
  school: '🎓', ai_project: '🤖', local_ai_host: '🧠', generic: '📦',
  github_repo: '🐙',
};
const TYPE_ORDER = ['trading_bot', 'code_project', 'game_server', 'website', 'school', 'ai_project', 'local_ai_host', 'github_repo', 'generic'];

const STONE = "<span class='stone'></span>";
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
function getControlToken() { return localStorage.getItem(CONTROL_TOKEN_STORAGE_KEY) || ''; }
function authHeaders() { const t = getControlToken(); return t ? { 'x-control-token': t } : {}; }
function healthBadge(h) { return `<span class='badge ${esc(h || 'unknown')}'>${esc(h || 'unknown')}</span>`; }
function money(v) {
  if (v === 'unknown' || v === undefined || v === null || v === '') return `<span class='money-unknown'>unknown</span>`;
  const n = Number(v);
  if (Number.isNaN(n)) return `<span class='money-unknown'>${esc(v)}</span>`;
  const cls = n > 0 ? 'money-pos' : (n < 0 ? 'money-neg' : 'money-zero');
  return `<span class='${cls}'>$${n.toFixed(2)}</span>`;
}
function metric(label, value) { return `<div class='metric'><span>${esc(label)}</span><b>${value}</b></div>`; }

function sparkSvg(history, extraClass = '') {
  const points = (history || [])
    .map(h => Number(h.pnl))
    .filter(n => Number.isFinite(n));
  if (points.length < 2) return '';
  const w = 220, h = 36, pad = 2;
  const min = Math.min(...points), max = Math.max(...points);
  const span = max - min || 1;
  const stepX = (w - pad * 2) / (points.length - 1);
  const coords = points.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + (h - pad * 2) * (1 - (v - min) / span);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const last = points[points.length - 1], first = points[0];
  const cls = last > first ? 'spark-pos' : (last < first ? 'spark-neg' : 'spark-flat');
  return `<svg viewBox='0 0 ${w} ${h}' preserveAspectRatio='none' class='spark-svg ${cls} ${extraClass}'>
      <polyline points='${coords}' fill='none' stroke-width='1.5' vector-effect='non-scaling-stroke' />
    </svg>`;
}

function sparkline(history, label) {
  const svg = sparkSvg(history);
  if (!svg) return '';
  return `<div class='sparkline'><span class='spark-label'>${esc(label)}</span>${svg}</div>`;
}

function projectCard(p) {
  const m = p.metrics || {};
  const alerts = (p.alerts || []).map(a => {
    const c = a.includes('ERROR') ? 'alert-error' : 'alert-warning';
    return `<div class='alert ${c}'>${esc(a)}</div>`;
  }).join('');
  let keyMetrics = '';
  if (p.type === 'trading_bot') {
    keyMetrics = [
      metric('Mode', esc(m.mode || 'unknown')),
      metric('Paper/Replay PnL Today', money(m.profit_today)),
      metric('Paper/Replay PnL Week', money(m.profit_this_week)),
      metric('Realized PnL', money(m.realized_pnl)),
      metric('Unrealized PnL', money(m.unrealized_pnl)),
      metric('Open Exposure', money(m.open_exposure)),
      metric('Open Positions', esc(m.open_positions)),
      metric('Trades Today', esc(m.trades_today)),
      metric('Fill Rate', esc(m.fill_rate)),
      metric('Last Trade', esc(m.last_trade_time)),
      metric('Tests', esc(m.last_test_result || 'unknown')),
    ].join('');
  } else if (p.type === 'local_ai_host') {
    keyMetrics = [
      metric('Provider', esc(m.provider)), metric('Status', esc(m.status)), metric('Default Model', esc(m.default_model)),
      metric('Model Count', esc((m.available_models || []).length)), metric('Resp ms', esc(m.response_time_ms)), metric('Process', esc(m.process_status)),
      metric('CPU', esc(m.cpu_usage)), metric('RAM MB', esc(m.ram_usage_mb)), metric('GPU/VRAM', esc(m.gpu_vram_usage)), metric('Last Error', esc(m.last_error)),
    ].join('');
  } else {
    keyMetrics = Object.entries(m).slice(0, 8).map(([k, v]) => metric(k, esc(v))).join('');
  }

  const spark = sparkline(p.history, 'PnL Today trend');

  const a = p.actions_available || {};
  const actions = `
    <div class='actions'>
      <button class='act-btn' data-log='1' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>View Logs</button>
      ${a.start ? `<button class='act-btn act-btn-start' data-action='start' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Start</button>` : ''}
      ${a.stop ? `<button class='act-btn act-btn-stop' data-action='stop' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Stop</button>` : ''}
      ${a.run_tests ? `<button class='act-btn' data-action='run-tests' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Run Tests</button>` : ''}
    </div>`;

  return `<div class='card' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
    <div class='metric'><b>${esc(p.name)}</b><span>${healthBadge(p.health)}</span></div>
    ${metric('Device', esc(p.device))}
    ${metric('Type', esc(p.type))}
    ${metric('Status', esc(p.status))}
    ${keyMetrics}
    ${spark}
    ${alerts}
    <details class='details'><summary>Raw details</summary><pre>${esc(JSON.stringify(p, null, 2))}</pre></details>
    ${actions}
  </div>`;
}

function roomBadge(p) {
  if (p.status === 'stopped') return 'FALLEN';
  if (p.status !== 'running') return 'SECLUSION';
  // Prefer the adapter-derived live activity (e.g. DayBot SCANNING / FILLING).
  const act = p.metrics && p.metrics.activity;
  if (act) return String(act).toUpperCase();
  return TYPE_VERB[p.type] || 'ACTIVE';
}

// A project rendered as a lit "room" for the base view.
function roomCard(p) {
  const health = p.health || 'unknown';
  const icon = TYPE_ICON[p.type] || '📦';
  const m = p.metrics || {};
  const isTrade = p.type === 'trading_bot';
  const a = p.actions_available || {};
  const overlay = `
    <div class='room-overlay'>
      <button class='act-btn' data-log='1' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Logs</button>
      ${a.start ? `<button class='act-btn act-btn-start' data-action='start' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Start</button>` : ''}
      ${a.stop ? `<button class='act-btn act-btn-stop' data-action='stop' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Stop</button>` : ''}
      ${a.run_tests ? `<button class='act-btn' data-action='run-tests' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Test</button>` : ''}
    </div>`;
  // Trading bots (incl. DayBot) get a live PnL micro-sparkline + PnL/positions readout on the room face.
  const spark = isTrade ? sparkSvg(p.history, 'room-spark') : '';
  const positions = (m.open_positions === undefined || m.open_positions === 'unknown') ? '—' : esc(m.open_positions);
  const stats = isTrade
    ? `<div class='room-stats'>${money(m.profit_today)}<span class='room-pos'>${positions} pos</span></div>`
    : '';
  const selected = selectedBase && selectedBase.device === p.device && selectedBase.name === p.name ? ' is-selected' : '';
  return `<div class='room room--${esc(health)}${selected}' data-select='1' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
    <div class='room-art'>
      ${spark}
      <span class='room-status'>● ${esc(roomBadge(p))}</span>
      <span class='room-char' title='${esc(p.type)}'>${icon}</span>
      ${stats}
      ${overlay}
    </div>
    <div class='room-label'>
      <div class='room-name'>${esc(p.name)}</div>
      <div class='room-sub'>${esc(p.device)} · ${esc(TYPE_LABEL[p.type] || p.type)}</div>
    </div>
    <div class='room-bar room-bar--${esc(health)}'></div>
  </div>`;
}

function summaryCards(s) {
  return [
    ['Total Devices', s.total_devices], ['Online Devices', s.online_devices], ['Offline Devices', s.offline_devices],
    ['Total Projects', s.total_projects], ['Warn / Error Projects', s.projects_with_warnings_errors], ['Bots Running', s.bots_running],
    ['Trading PnL Today', money(s.total_trading_profit_today)], ['Trading PnL Week', money(s.total_trading_profit_this_week)],
    ['Open Exposure', money(s.total_open_exposure)], ['Tests Failing', esc(s.tests_failing)], ['Local AI Online', esc(s.local_ai_hosts_online)], ['Local AI Errors', esc(s.local_ai_hosts_with_errors)],
  ].map(([k, v]) => `<div class='card'>${metric(k, String(v))}</div>`).join('');
}

function renderDevices(devices) {
  return devices.map(d => {
    const state = d.auth_error ? 'auth error' : (d.online ? 'online' : 'offline');
    const cls = d.auth_error ? 'status-auth' : (d.online ? 'status-online' : 'status-offline');
    const projectCount = (window.__lastProjects || []).filter(p => p.device === d.name).length;
    return `<div class='card'>
      <div class='metric'><b>${esc(d.name)}</b><span class='${cls}'>${esc(state)}</span></div>
      ${metric('URL', esc(d.url))}
      ${metric('Project Count', esc(projectCount))}
      ${metric('Last Update', esc(new Date().toLocaleTimeString()))}
      ${d.error ? `<div class='alert ${d.auth_error ? 'alert-warning' : 'alert-error'}'>${esc(d.error)}</div>` : ''}
    </div>`;
  }).join('');
}

async function callAction(device, project, action) {
  if (action === 'start' || action === 'stop') {
    if (!window.confirm(`${action.toUpperCase()} ${project} on ${device}? Confirm operation.`)) return;
  }
  const logsEl = document.getElementById('logs');
  document.getElementById('logs-panel').classList.remove('hidden');
  logsEl.innerText = `Running ${action} on ${project} (${device})...`;
  try {
    const url = `/api/action/${encodeURIComponent(device)}/${encodeURIComponent(project)}/${encodeURIComponent(action)}`;
    const res = await fetch(url, { method: 'POST', headers: authHeaders() });
    const body = await res.json();
    logsEl.innerText = JSON.stringify(body, null, 2);
  } catch (e) {
    logsEl.innerText = `Action failed: ${e}`;
  }
}

async function loadLogs(device, project) {
  selectedProject = project;
  selectedProjectDevice = device;
  document.getElementById('logs-title').innerText = `Logs: ${project} @ ${device}`;
  document.getElementById('logs-panel').classList.remove('hidden');
  document.getElementById('logs').innerText = 'Loading logs...';
  const level = selectedLogLevel;
  try {
    const url = `/api/logs/${encodeURIComponent(device)}/${encodeURIComponent(project)}?level=${encodeURIComponent(level)}`;
    const data = await fetch(url, { headers: authHeaders() }).then(r => r.json());
    document.getElementById('logs').innerText = (data.lines || []).join('\n') || '(no logs)';
  } catch (e) {
    document.getElementById('logs').innerText = `Error fetching logs: ${e}`;
  }
}

function startLogsAutoRefresh() {
  if (logsInterval) clearInterval(logsInterval);
  logsInterval = setInterval(() => {
    if (logsRefreshPaused || !selectedProject || !selectedProjectDevice) return;
    loadLogs(selectedProjectDevice, selectedProject);
  }, 7000);
}

async function render() {
  const summaryEl = document.getElementById('summary');
  const projectsEl = document.getElementById('projects');
  const devicesEl = document.getElementById('devices');
  const err = document.getElementById('error-banner');
  summaryEl.classList.add('loading');
  summaryEl.innerHTML = `<div class='card'>Loading overview...</div>`;
  try {
    const data = await fetch('/api/overview', { headers: authHeaders() }).then(r => r.json());
    window.__lastProjects = data.projects || [];
    err.classList.add('hidden');
    document.getElementById('refresh-status').textContent = new Date().toLocaleTimeString();
    document.getElementById('device-count-pill').textContent = `${data.summary.online_devices} online / ${data.summary.offline_devices} offline`;

    summaryEl.classList.remove('loading');
    summaryEl.innerHTML = summaryCards(data.summary);
    devicesEl.innerHTML = renderDevices(data.devices || []);

    renderAiAgents(window.__lastProjects);
    renderProjects(window.__lastProjects);
    await renderAgentCrew();
    renderGovernance();
    renderTrials();
    renderLore();
    renderSectMap();
    renderHallOfFame();
    renderProphecy();
    bindComms();
    renderComms();
    bindVault();
    renderVault();
    bindTools();
    renderTools();
    renderUsage();
    bindTreasury();
    renderTreasury();
  } catch (e) {
    err.classList.remove('hidden');
    summaryEl.classList.remove('loading');
    summaryEl.innerHTML = `<div class='card'><b>Overview unavailable</b><div class='muted'>${esc(String(e))}</div></div>`;
    devicesEl.innerHTML = '';
    projectsEl.innerHTML = '';
    document.getElementById('ai-agents').innerHTML = '';
  }
}

function projectMatches(p, query, health) {
  if (health && health !== 'ALL' && (p.health || 'unknown') !== health) return false;
  if (!query) return true;
  const hay = `${p.name} ${p.device} ${p.type} ${p.status}`.toLowerCase();
  return hay.includes(query);
}

function bindProjectButtons(root) {
  root.querySelectorAll('[data-action]').forEach(btn => btn.onclick = async (e) => {
    e.stopPropagation();
    btn.disabled = true;
    await callAction(btn.getAttribute('data-device'), btn.getAttribute('data-project'), btn.getAttribute('data-action'));
    btn.disabled = false;
    render();
  });
  root.querySelectorAll('[data-log]').forEach(btn => btn.onclick = (e) => { e.stopPropagation(); loadLogs(btn.getAttribute('data-device'), btn.getAttribute('data-project')); });
}

// ---- Base View "ship station": crew roster + manage/info panel ----

function crewStatusLine(p) {
  const m = p.metrics || {};
  if (p.status === 'stopped') return 'Fallen';
  if (p.status !== 'running') return 'In seclusion';
  let line = String(roomBadge(p)).toLowerCase();
  line = line.charAt(0).toUpperCase() + line.slice(1);
  if (p.type === 'trading_bot' && m.open_positions !== undefined && m.open_positions !== 'unknown') {
    line += ` · ${m.open_positions} pos`;
  }
  if (p.health === 'warning' || p.health === 'error') line += ' · needs attention';
  return line;
}

function crewRow(p) {
  const health = p.health || 'unknown';
  const icon = TYPE_ICON[p.type] || '📦';
  const active = selectedBase && selectedBase.device === p.device && selectedBase.name === p.name ? ' active' : '';
  return `<button class='crew-row${active}' data-select='1' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
    <span class='crew-dot ${esc(health)}'></span>
    <span class='crew-meta'>
      <span class='crew-name'>${esc(p.name)}</span>
      <span class='crew-status'>${esc(crewStatusLine(p))}</span>
    </span>
    <span class='crew-icon'>${icon}</span>
  </button>`;
}

function managePanel(p) {
  if (!p) return `<div class='manage-empty muted'>Select a crew member or room to manage.</div>`;
  const m = p.metrics || {};
  const a = p.actions_available || {};
  let stats;
  if (p.type === 'trading_bot') {
    stats = [
      metric('Activity', esc((m.activity || (p.status === 'running' ? 'trading' : p.status)).toUpperCase())),
      metric('PnL Today', money(m.profit_today)), metric('PnL Week', money(m.profit_this_week)),
      metric('Open Positions', esc(m.open_positions)), metric('Open Exposure', money(m.open_exposure)),
      metric('Fill Rate', esc(m.fill_rate)), metric('Market', esc(m.market_status)),
    ].join('');
  } else if (p.type === 'local_ai_host') {
    stats = [
      metric('Provider', esc(m.provider)), metric('Status', esc(m.status)), metric('Default Model', esc(m.default_model)),
      metric('Models', esc((m.available_models || []).length)), metric('Resp ms', esc(m.response_time_ms)), metric('Last Error', esc(m.last_error)),
    ].join('');
  } else {
    stats = Object.entries(m).filter(([k]) => k !== 'git' && k !== 'process').slice(0, 6).map(([k, v]) => metric(k, esc(v))).join('');
  }
  const alerts = (p.alerts || []).map(x => `<div class='alert ${x.includes('ERROR') ? 'alert-error' : 'alert-warning'}'>${esc(x)}</div>`).join('');
  return `
    <div class='manage-head'>
      <div><b>${esc(p.name)}</b> ${healthBadge(p.health)}</div>
      <button id='manage-close' class='btn'>×</button>
    </div>
    <div class='manage-sub muted'>${esc(p.device)} · ${esc(TYPE_LABEL[p.type] || p.type)} · status ${esc(p.status)}</div>
    <div class='manage-grid'>${stats}</div>
    ${alerts}
    <div class='manage-actions'>
      <button class='act-btn' data-log='1' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Logs</button>
      ${a.start ? `<button class='act-btn act-btn-start' data-action='start' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Start</button>` : ''}
      ${a.stop ? `<button class='act-btn act-btn-stop' data-action='stop' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Stop</button>` : ''}
      ${a.run_tests ? `<button class='act-btn' data-action='run-tests' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>Run Tests</button>` : ''}
    </div>
    <details class='details'><summary>Info / raw details</summary><pre>${esc(JSON.stringify(p, null, 2))}</pre></details>`;
}

function renderStation(projects) {
  const projectsEl = document.getElementById('projects');
  const ordered = projects.slice().sort((a, b) =>
    (TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type)) || String(a.name).localeCompare(String(b.name)));

  // keep selection only if it still exists in the current (filtered) set
  const sel = selectedBase && ordered.find(p => p.device === selectedBase.device && p.name === selectedBase.name);
  if (!sel) selectedBase = null;

  projectsEl.innerHTML = `<div class='station'>
    <aside class='crew'>
      <div class='crew-head'>DISCIPLES <span class='muted'>${ordered.length}</span></div>
      <div class='crew-list'>${ordered.map(crewRow).join('')}</div>
    </aside>
    <div class='station-main'>
      <div class='manage-panel ${sel ? '' : 'manage-panel--empty'}'>${managePanel(sel || null)}</div>
      <div class='rooms-grid'>${ordered.map(roomCard).join('')}</div>
    </div>
  </div>`;

  // selection: clicking a crew row or room (but not its action buttons) selects it
  projectsEl.querySelectorAll('[data-select]').forEach(el => el.onclick = (e) => {
    if (e.target.closest('[data-action],[data-log]')) return;
    selectedBase = { device: el.getAttribute('data-device'), name: el.getAttribute('data-project') };
    renderStation(window.__lastProjects ? window.__lastProjects.filter(p => projectMatches(p,
      (document.getElementById('project-search').value || '').trim().toLowerCase(),
      document.getElementById('health-filter').value || 'ALL')) : ordered);
  });
  const close = document.getElementById('manage-close');
  if (close) close.onclick = () => { selectedBase = null; renderStation(ordered); };
  bindProjectButtons(projectsEl);
}

// ---- Agent Crew: LLM-backed persona agents you can assign tasks to ----

function renderSectRanking(crew) {
  const el = document.getElementById('sect-ranking');
  if (!el) return;
  const ranked = (crew || []).filter(a => a.cultivation).slice().sort((x, y) => {
    const a = x.cultivation, b = y.cultivation;
    return (b.realm - a.realm) || (b.stones - a.stones);
  });
  if (!ranked.length) { el.innerHTML = ''; return; }
  const medals = ['🥇', '🥈', '🥉'];
  el.innerHTML = `<div class='rank-head'>SECT RANKING</div>` + ranked.map((a, i) => {
    const c = a.cultivation;
    return `<div class='rank-row'>
      <span class='rank-pos'>${medals[i] || (i + 1)}</span>
      <span class='rank-name'>${esc(a.name)}</span>
      <span class='rank-title'>${esc(c.rank_title || '')}</span>
      <span class='rank-realm'>${esc(c.realm_name)} · ${esc(c.layer_label || c.stage)}</span>
      <span class='rank-stones'><span class='stone'></span>${esc(c.stones)}</span>
    </div>`;
  }).join('');
}

function cultivationFlourish(c) {
  if (!c.event || (Date.now() - (c.event_ts || 0) >= 30000)) return '';
  switch (c.event) {
    case 'breakthrough': return `<div class='culti-flash culti-breakthrough'>☯ Breakthrough — ${esc(c.realm_name)}!</div>`;
    case 'tribulation_survived': return `<div class='culti-flash culti-breakthrough'>☯ Tribulation survived!</div>`;
    case 'tribulation': return `<div class='culti-flash culti-tribulation'>⚡ Heavenly Tribulation — struck down!</div>`;
    case 'facing_tribulation': return `<div class='culti-flash culti-tribulation'>⚡ Facing tribulation${c.pending_tribulation ? `: ${esc(c.pending_tribulation)}` : ''}…</div>`;
    default: return '';
  }
}

function cultivationBlock(c) {
  if (!c || !c.realm_name) return '';
  const prog = Math.round((c.progress || 0) * 100);
  const next = c.next_realm
    ? `<div class='muted culti-next'>${esc(c.stones_to_next)} stones${c.skills_to_next ? ` · ${esc(c.skills_to_next)} technique${c.skills_to_next > 1 ? 's' : ''}` : ''} → ${esc(c.next_realm)}</div>`
    : `<div class='muted culti-next'>✦ Immortal Ascension attained</div>`;
  const skills = (c.skills && c.skills.length) ? `<div class='muted culti-skills'>Techniques: ${c.skills.map(esc).join(', ')}</div>` : '';
  return `<div class='cultivation realm-${c.realm}'>
    <div class='culti-head'><span class='culti-realm'>⛰ ${esc(c.realm_name)} · ${esc(c.layer_label || c.stage)}</span><span class='culti-stones'><span class='stone'></span>${esc(c.stones)}</span></div>
    <div class='muted culti-rank'>${esc(c.rank_title || '')}</div>
    <div class='qi-bar'><span style='width:${prog}%'></span></div>
    ${next}${skills}${cultivationFlourish(c)}
  </div>`;
}

function retreatControl(a, c) {
  // Disciples decide on their own when to seclude/roam; the Ancestor can only recall.
  if (!c || !c.realm_name) return '';
  if (c.in_seclusion)
    return `<div class='retreat-row active'><span class='retreat-state'>🧘 Secluded · breakthrough in ${fmtDur(c.seclusion_remaining)}</span>
      <button class='btn culti-sec-btn' data-agent='${esc(a.name)}' data-enter=''>Recall</button></div>`;
  if (c.in_roaming)
    return `<div class='retreat-row active'><span class='retreat-state'>🌄 Roaming · returns in ${fmtDur(c.roaming_remaining)}</span>
      <button class='btn culti-roam-btn' data-agent='${esc(a.name)}' data-enter=''>Recall</button></div>`;
  return '';
}

function questControl(a) {
  const qd = window.__quests;
  if (!qd || !qd.catalog || !qd.catalog.length) return '';
  const pending = a.cultivation && a.cultivation.pending_quest;
  if (pending) return `<div class='quest-control muted'>⚑ On quest → learns ${esc(pending.skill)}</div>`;
  const opts = qd.catalog.map(q => `<option value='${esc(q.id)}'>${esc(q.name)} → ${esc(q.reward_skill)}</option>`).join('');
  return `<div class='quest-control'><select class='quest-select' data-agent='${esc(a.name)}'>${opts}</select><button class='btn quest-go' data-agent='${esc(a.name)}'>Dispatch</button></div>`;
}

function transmitControl(a, c) {
  const myRealm = (c && c.realm) || 0;
  const subs = (window.__agents || []).filter(x => x.name !== a.name && ((x.cultivation && x.cultivation.realm) || 0) < myRealm).map(x => x.name);
  const skills = (c && c.skills) || [];
  if (!subs.length || !skills.length) return '';
  return `<div class='transmit-control'><select class='transmit-skill' data-agent='${esc(a.name)}'>${skills.map(s => `<option>${esc(s)}</option>`).join('')}</select><span class='muted'>→</span><select class='transmit-to' data-agent='${esc(a.name)}'>${subs.map(n => `<option>${esc(n)}</option>`).join('')}</select><button class='btn transmit-go' data-agent='${esc(a.name)}'>Transmit</button></div>`;
}

function pillBuffs(a) {
  const pd = window.__pills || { active: {} };
  const buffs = (pd.active && pd.active[a.name]) || [];
  return buffs.length ? `<div class='pill-buffs'>${buffs.map(b => `<span class='pill-chip'>⚗ ${esc(b.name)}</span>`).join('')}</div>` : '';
}
function pillBuy(a, c) {
  const pd = window.__pills || { catalog: [] };
  if (!pd.catalog || !pd.catalog.length) return '';
  const stones = (c && c.stones) || 0;
  const opts = pd.catalog.map(p => `<option value='${esc(p.id)}'${p.cost > stones ? ' disabled' : ''}>${esc(p.name)} · <span class='stone'></span>${esc(p.cost)}</option>`).join('');
  return `<div class='pill-control'><select class='pill-select' data-agent='${esc(a.name)}'>${opts}</select><button class='btn pill-buy' data-agent='${esc(a.name)}'>Concoct</button></div>`;
}
// quest / transmit / concoct controls, tucked into one collapsible to keep the card clean
function sectActions(a, c) {
  const inner = questControl(a) + transmitControl(a, c) + pillBuy(a, c);
  if (!inner.trim()) return '';
  return `<details class='details sect-actions'><summary>Sect actions</summary>${inner}</details>`;
}

function delegateSelect(a, c) {
  const myRealm = (c && c.realm) || 0;
  const subs = (window.__agents || []).filter(x => x.name !== a.name && ((x.cultivation && x.cultivation.realm) || 0) < myRealm).map(x => x.name);
  if (!subs.length) return '';  // outranks no one → can only act for self
  return `<select class='delegate-target' data-agent='${esc(a.name)}' title='delegate to a lower-ranked disciple'><option value=''>self</option>${subs.map(n => `<option>${esc(n)}</option>`).join('')}</select>`;
}

function reputationChip(rep) {
  if (!rep) return '';
  const tier = rep.tier || 'Standard';
  const cls = tier === 'Trusted' ? 'rep-trusted' : (tier === 'Probation' ? 'rep-probation' : 'rep-standard');
  const mark = tier === 'Trusted' ? '★' : (tier === 'Probation' ? '⚠' : '◆');
  const s = rep.signals || {};
  const title = `merit ${rep.merit} · success ${s.success_pct ?? '—'}% · ${s.done || 0} tools done / ${s.failed || 0} failed / ${s.denied || 0} denied`;
  return `<span class='rep-chip ${cls}' title='${esc(title)}'>${mark} ${esc(tier)} · merit ${rep.merit}</span>`;
}

function governanceChip(g) {
  if (!g) return '';
  let badge = '';
  if (g.is_leader) badge = `<span class='gov-chip gov-leader' title='Sect Leader · standing ${g.standing}'>👑 Sect Leader</span>`;
  else if (g.is_elder) badge = `<span class='gov-chip gov-elder' title='Elder · standing ${g.standing}'>🜍 Elder</span>`;
  const spec = g.specialty ? `<span class='gov-chip gov-spec' title='mastery ${g.mastery}'>${esc(g.specialty)} · ${g.mastery}</span>` : '';
  return badge + spec;
}

function agentCard(a) {
  const st = a.status || 'idle';
  const dot = st === 'error' ? 'error' : (st === 'working' || st === 'queued' ? 'warning' : 'ok');
  const reply = a.last_reply ? esc(a.last_reply) : '';
  const c = a.cultivation || {};
  const tribCls = c.event === 'tribulation' && (Date.now() - (c.event_ts || 0) < 30000) ? ' agent-tribulation' : '';
  return `<div class='card agent-card agent-${esc(st)}${tribCls}' data-agent='${esc(a.name)}'>
    <div class='metric'><b>🧘 ${esc(a.name)}</b><span class='agent-state'><span class='crew-dot ${dot}'></span>${esc(st)}</span></div>
    ${a.reputation || a.governance ? `<div class='rep-row'>${governanceChip(a.governance)}${reputationChip(a.reputation)}${a.bond ? `<span class='gov-chip gov-spec' title='karmic-bond reviewer'>🤝 ${esc(a.bond)}</span>` : ''}</div>` : ''}
    ${(a.titles && a.titles.length) ? `<div class='rep-row'>${a.titles.map(t => `<span class='title-chip' title='${esc(t.desc)}'>🏅 ${esc(t.title)}</span>`).join('')}</div>` : ''}
    ${metric('Role', esc(a.role || '—'))}
    ${metric('Model', esc(a.model))}
    ${metric('Tasks done', esc(a.tasks_done ?? 0))}
    ${cultivationBlock(c)}
    ${pillBuffs(a)}
    ${retreatControl(a, c)}
    ${a.current_task ? `<div class='agent-task-cur'>▸ ${esc(a.current_task)}</div>` : ''}
    ${a.error ? `<div class='alert alert-error'>${esc(a.error)}</div>` : ''}
    <div class='agent-reply'>${reply || `<span class='muted'>No output yet.</span>`}</div>
    <div class='agent-assign'>
      <input class='agent-input' placeholder='Assign a task to ${esc(a.name)}…' data-agent='${esc(a.name)}'>
      <div class='agent-assign-go'>${delegateSelect(a, c)}<button class='btn btn-primary agent-send' data-agent='${esc(a.name)}'>Assign</button></div>
    </div>
    ${sectActions(a, c)}
    <details class='details agent-transcript' data-agent='${esc(a.name)}'><summary>Transcript (${esc(a.transcript_len ?? 0)})</summary><pre class='agent-tx-body'>Open to load…</pre></details>
  </div>`;
}

function bindAgentCrew(root) {
  const sel = name => root.querySelector(`.agent-send[data-agent="${CSS.escape(name)}"]`);
  const retreat = (cls, path) => root.querySelectorAll(cls).forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const enter = !!btn.getAttribute('data-enter');
    btn.disabled = true;
    try {
      await fetch(`/api/agents/${encodeURIComponent(name)}/${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ enter }),
      });
    } catch (_) {}
    btn.disabled = false;
    renderAgentCrew();
  });
  retreat('.culti-sec-btn', 'seclusion');
  retreat('.culti-roam-btn', 'roaming');
  root.querySelectorAll('.quest-go').forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const s = root.querySelector(`.quest-select[data-agent="${CSS.escape(name)}"]`);
    if (!s || !s.value) return;
    btn.disabled = true;
    try {
      const res = await fetch(`/api/agents/${encodeURIComponent(name)}/quest`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ quest: s.value }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Quest failed: ' + (b.detail || res.status)); }
    } catch (_) {}
    btn.disabled = false;
    renderAgentCrew();
  });
  root.querySelectorAll('.transmit-go').forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const sk = root.querySelector(`.transmit-skill[data-agent="${CSS.escape(name)}"]`);
    const to = root.querySelector(`.transmit-to[data-agent="${CSS.escape(name)}"]`);
    if (!sk || !to) return;
    btn.disabled = true;
    try {
      const res = await fetch(`/api/agents/${encodeURIComponent(name)}/transmit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ to: to.value, skill: sk.value }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Transmission failed: ' + (b.detail || res.status)); }
    } catch (_) {}
    btn.disabled = false;
    renderAgentCrew();
  });
  root.querySelectorAll('.pill-buy').forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const s = root.querySelector(`.pill-select[data-agent="${CSS.escape(name)}"]`);
    const pill = s && s.value;
    if (!pill) return;
    btn.disabled = true;
    try {
      const res = await fetch('/api/pills/buy', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ agent: name, pill }),
      });
      const b = await res.json().catch(() => ({}));
      if (!res.ok) { alert('Concoction failed: ' + (b.detail || res.status)); }
      else if (b.deviation) { alert('⚡ Qi deviation! The churning qi scattered every buff' + (b.struck ? ' — and struck the disciple down a realm.' : '.')); }
    } catch (e) { alert('Concoction failed: ' + e); }
    btn.disabled = false;
    renderAgentCrew();
  });
  root.querySelectorAll('.agent-send').forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const inp = root.querySelector(`.agent-input[data-agent="${CSS.escape(name)}"]`);
    const task = (inp && inp.value || '').trim();
    if (!task) return;
    const tsel = root.querySelector(`.delegate-target[data-agent="${CSS.escape(name)}"]`);
    const target = tsel ? tsel.value : '';
    btn.disabled = true;
    try {
      const url = target ? `/api/agents/${encodeURIComponent(name)}/delegate` : `/api/agents/${encodeURIComponent(name)}/task`;
      const body = target ? { to: target, task } : { task };
      const res = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Failed: ' + (b.detail || res.status)); }
      else if (inp) inp.value = '';
    } catch (_) {}
    btn.disabled = false;
    renderAgentCrew();
  });
  root.querySelectorAll('.agent-input').forEach(inp => inp.onkeydown = (e) => {
    if (e.key === 'Enter') sel(inp.getAttribute('data-agent'))?.click();
  });
  root.querySelectorAll('.agent-transcript').forEach(d => d.ontoggle = async () => {
    if (!d.open) return;
    const name = d.getAttribute('data-agent');
    const body = d.querySelector('.agent-tx-body');
    try {
      const a = await fetch(`/api/agents/${encodeURIComponent(name)}`, { headers: authHeaders() }).then(r => r.json());
      body.innerText = (a.transcript || []).map(m => `${String(m.role).toUpperCase()}: ${m.content}`).join('\n\n') || '(empty)';
    } catch (_) { body.innerText = 'Error loading transcript.'; }
  });
}

async function renderAgentCrew() {
  const section = document.getElementById('agent-crew-section');
  const el = document.getElementById('agent-crew');
  let data;
  try { data = await fetch('/api/agents', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { section.classList.add('hidden'); return; }
  const crew = (data && data.agents) || [];
  window.__agents = crew;
  try { window.__pills = await fetch('/api/pills', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { window.__pills = { catalog: [], active: {} }; }
  try { window.__quests = await fetch('/api/quests', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { window.__quests = { catalog: [] }; }
  if (!crew.length) { section.classList.add('hidden'); el.innerHTML = ''; return; }
  section.classList.remove('hidden');
  document.getElementById('agent-crew-pill').textContent = `${crew.length} disciples`;
  renderSectRanking(crew);
  // preserve whatever the user is typing across the auto-refresh re-render
  const act = document.activeElement;
  const focusName = act && act.classList && act.classList.contains('agent-input') ? act.getAttribute('data-agent') : null;
  const focusVal = focusName ? act.value : null;
  el.innerHTML = crew.map(agentCard).join('');
  bindAgentCrew(el);
  if (focusName) {
    const inp = el.querySelector(`.agent-input[data-agent="${CSS.escape(focusName)}"]`);
    if (inp) { inp.value = focusVal; inp.focus(); }
  }
}

// ---- Hall of Fame ----

function fameCard(title, a, label, value) {
  const c = a.cultivation || {};
  return `<div class='card'>
    <div class='metric'><b>${title}</b><b class='money-pos'>${value}</b></div>
    ${metric('Disciple', `🧘 ${esc(a.name)}`)}
    ${metric('Realm', `${esc(c.realm_name || '—')} · ${esc(c.layer_label || c.stage || '')}`)}
    ${metric(label, esc(value))}
  </div>`;
}

function renderHallOfFame() {
  const sec = document.getElementById('fame-section');
  const crew = (window.__agents || []).filter(a => a.cultivation);
  if (!crew.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  const top = f => crew.slice().sort(f)[0];
  const strongest = top((x, y) => (y.cultivation.realm - x.cultivation.realm) || (y.cultivation.stones - x.cultivation.stones));
  const richest = top((x, y) => y.cultivation.stones - x.cultivation.stones);
  const learned = top((x, y) => (y.cultivation.skills || []).length - (x.cultivation.skills || []).length);
  const broke = top((x, y) => y.cultivation.breakthroughs - x.cultivation.breakthroughs);
  document.getElementById('hall-of-fame').innerHTML = [
    fameCard('🏆 Strongest', strongest, 'Spirit stones', `<span class='stone'></span>${strongest.cultivation.stones}`),
    fameCard(STONE + ' Richest', richest, 'Spirit stones', `${STONE}${richest.cultivation.stones}`),
    fameCard('📚 Most Techniques', learned, 'Techniques', `${(learned.cultivation.skills || []).length}`),
    fameCard('⚡ Most Breakthroughs', broke, 'Breakthroughs', `${broke.cultivation.breakthroughs}`),
  ].join('');
}

// ---- Sect Hierarchy: governance, challenges, the Ancestor's Hall ----

async function govPost(path, body, okMsg) {
  try {
    const res = await fetch(`/api/governance/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) { alert((okMsg || 'Action') + ' failed: ' + (j.detail || res.status)); return null; }
    return j;
  } catch (e) { alert((okMsg || 'Action') + ' failed: ' + e); return null; }
}

function govRosterCard(r, leaderPinned) {
  const s = r.standing || {};
  const c = s.components || {};
  const rank = r.is_leader ? '👑 Sect Leader' : (r.is_master ? 'Sect Master' : (r.is_elder ? '🜍 Elder' : 'Disciple'));
  const specOpts = Object.keys(window.__specialties || {}).map(k =>
    `<option ${r.specialty === k ? 'selected' : ''}>${esc(k)}</option>`).join('');
  const elderControls = r.is_elder ? `
    <div class='gov-controls'>
      <select class='gov-spec-sel' data-agent='${esc(r.agent)}'>${specOpts}</select>
      <button class='btn gov-spec-go' data-agent='${esc(r.agent)}'>Set path</button>
      ${!r.is_leader && !leaderPinned ? `<button class='btn gov-challenge' data-agent='${esc(r.agent)}'>⚔ Challenge</button>` : ''}
    </div>` : '';
  return `<div class='card gov-card${r.is_leader ? ' gov-card-leader' : ''}'>
    <div class='metric'><b>${esc(r.agent)}</b><b class='money-pos'>${s.score ?? '—'}</b></div>
    ${metric('Rank', rank)}
    ${metric('Specialty', r.specialty ? `${esc(r.specialty)} · mastery ${r.mastery}` : '—')}
    <div class='gov-bars muted'>merit ${c.merit ?? '—'} · perf ${c.performance ?? '—'} · lead ${c.leadership ?? '—'} · contrib ${c.contribution ?? '—'}</div>
    ${elderControls}
  </div>`;
}

async function renderGovernance() {
  const sec = document.getElementById('governance-section');
  let data;
  try { data = await fetch('/api/governance', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { sec.classList.add('hidden'); return; }
  const roster = data.roster || [];
  if (!roster.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  window.__specialties = data.specialties || {};
  document.getElementById('leader-pill').textContent =
    data.leader ? `👑 ${data.leader}${data.leader_pinned ? ' (pinned)' : ''}` : 'no leader';

  // appoint-leader select
  const lsel = document.getElementById('leader-select');
  const cur = lsel.value;
  lsel.innerHTML = roster.map(r => `<option ${r.agent === data.leader ? 'selected' : ''}>${esc(r.agent)}</option>`).join('');
  if (cur && roster.some(r => r.agent === cur)) lsel.value = cur;

  document.getElementById('governance-roster').innerHTML =
    roster.map(r => govRosterCard(r, data.leader_pinned)).join('');

  // inbox
  let inbox = { messages: [] };
  try { inbox = await fetch('/api/governance/inbox', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) {}
  const box = document.getElementById('ancestor-inbox');
  box.innerHTML = (inbox.messages || []).length
    ? inbox.messages.map(m => `<div class='comms-msg'><div class='comms-head'><span class='comms-from'>${esc(m.from)}</span> <span class='muted'>· ${esc(m.role)}</span></div><div class='comms-body'>${esc(m.text)}</div></div>`).join('')
    : `<div class='comms-sys muted'>No word from the sect's leadership yet.</div>`;

  bindGovernance();
}

function bindGovernance() {
  const root = document.getElementById('governance-section');
  const set = document.getElementById('leader-set');
  if (set && !set.dataset.bound) {
    set.dataset.bound = '1';
    set.onclick = async () => {
      const leader = document.getElementById('leader-select').value;
      if (await govPost('leader', { leader, pinned: true }, 'Appoint')) renderGovernance();
    };
  }
  const rel = document.getElementById('leader-release');
  if (rel && !rel.dataset.bound) {
    rel.dataset.bound = '1';
    rel.onclick = async () => {
      if (await govPost('leader', { leader: null, pinned: false }, 'Release')) renderGovernance();
    };
  }
  root.querySelectorAll('.gov-spec-go').forEach(b => b.onclick = async () => {
    const agent = b.getAttribute('data-agent');
    const sel = root.querySelector(`.gov-spec-sel[data-agent="${CSS.escape(agent)}"]`);
    if (sel && await govPost('specialty', { agent, specialty: sel.value }, 'Set path')) renderGovernance();
  });
  root.querySelectorAll('.gov-challenge').forEach(b => b.onclick = async () => {
    const challenger = b.getAttribute('data-agent');
    const res = await govPost('challenge', { challenger }, 'Challenge');
    if (res) { alert(res.reason || (res.won ? 'Victory!' : 'Defeated.')); renderGovernance(); }
  });
}

// ---- Trials Hall: Night-Watch, chaos, dreamscape, spirit-root ----

async function apiJSON(path) { try { return await fetch(path, { headers: authHeaders() }).then(r => r.json()); } catch (_) { return null; } }
async function apiPost(path, body, label) {
  try {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(body) });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) { alert((label || 'Action') + ' failed: ' + (j.detail || res.status)); return null; }
    return j;
  } catch (e) { alert((label || 'Action') + ' failed: ' + e); return null; }
}

async function renderTrials() {
  const sec = document.getElementById('trials-section');
  const crew = window.__agents || [];
  if (!crew.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  // Night-Watch
  const w = await apiJSON('/api/nightwatch') || {};
  document.getElementById('watch-line').textContent = w.current
    ? `On watch: ${w.current} · next: ${w.next || '—'} · ${Math.round((w.shift_remaining || 0) / 60)}m left · ${w.open || 0} open`
    : 'No one stands the night watch.';
  const wr = document.getElementById('watch-roster');
  const onWatch = new Set(w.rotation || []);
  wr.innerHTML = crew.map(a => `<label class='comms-chip'><input type='checkbox' value='${esc(a.name)}' ${onWatch.has(a.name) ? 'checked' : ''}> ${esc(a.name)}</label>`).join('');
  document.getElementById('watch-log').innerHTML = (w.trials || w.log || []).slice ? '' : '';

  // Chaos trials
  const ch = await apiJSON('/api/chaos') || {};
  const kindSel = document.getElementById('chaos-kind');
  if (kindSel && !kindSel.dataset.ready && ch.catalog) {
    kindSel.innerHTML = Object.entries(ch.catalog).map(([k, v]) => `<option value='${esc(k)}' title='${esc(v)}'>${esc(k)}</option>`).join('');
    kindSel.dataset.ready = '1';
  }
  const discSel = document.getElementById('chaos-disciple');
  if (discSel) { const cur = discSel.value; discSel.innerHTML = `<option value=''>(no disciple)</option>` + crew.map(a => `<option>${esc(a.name)}</option>`).join(''); if (cur) discSel.value = cur; }
  document.getElementById('chaos-trials').innerHTML = (ch.trials || []).map(t => {
    const cls = t.status === 'failed' ? 'omen-ominous' : (t.status === 'weathered' ? 'omen-favorable' : '');
    const btn = t.status === 'active' ? `<div class='gov-controls'><button class='btn chaos-weather' data-id='${t.id}'>Weathered</button><button class='btn gov-challenge chaos-fail' data-id='${t.id}'>Failed</button></div>` : '';
    return `<div class='card omen-card ${cls}'>
      <div class='metric'><b>${esc(t.kind)}</b><span class='muted'>${esc(t.status)}</span></div>
      ${metric('Target', esc(t.target))}${metric('Disciple', esc(t.disciple || '—'))}${t.score != null ? metric('Score', t.score) : ''}${btn}</div>`;
  }).join('') || `<div class='comms-sys muted'>No trials summoned.</div>`;

  // Spirit-root grades
  const sr = await apiJSON('/api/spirit-root') || {};
  const profiles = (sr.profiles) || {};
  document.getElementById('spirit-grades').innerHTML = Object.keys(profiles).length
    ? Object.values(profiles).map(p => `<div class='card'><div class='metric'><b>${esc(p.agent)}</b><b class='money-pos'>${esc(p.grade)}</b></div>${metric('Overall', p.overall)}${metric('Samples', p.samples)}</div>`).join('')
    : `<div class='comms-sys muted'>No disciples assessed yet (POST results to /api/spirit-root/assess).</div>`;

  bindTrials();
}

function bindTrials() {
  const root = document.getElementById('trials-section');
  const ws = document.getElementById('watch-set');
  if (ws && !ws.dataset.bound) {
    ws.dataset.bound = '1';
    ws.onclick = async () => {
      const names = Array.from(root.querySelectorAll('#watch-roster input:checked')).map(i => i.value);
      if (await apiPost('/api/nightwatch/rotation', { names }, 'Set watch')) renderTrials();
    };
  }
  const cg = document.getElementById('chaos-go');
  if (cg && !cg.dataset.bound) {
    cg.dataset.bound = '1';
    cg.onclick = async () => {
      const target = (document.getElementById('chaos-target').value || '').trim();
      if (!target) { alert('Enter a target.'); return; }
      const kind = document.getElementById('chaos-kind').value;
      const disciple = document.getElementById('chaos-disciple').value || null;
      if (await apiPost('/api/chaos/summon', { target, kind, disciple }, 'Summon')) renderTrials();
    };
  }
  root.querySelectorAll('.chaos-weather').forEach(b => b.onclick = async () => {
    const secs = prompt('Recovery time in seconds (blank = full marks):', '');
    const body = { recovered: true }; if (secs) body.recovery_seconds = Number(secs);
    if (await apiPost(`/api/chaos/${b.getAttribute('data-id')}/resolve`, body, 'Resolve')) renderTrials();
  });
  root.querySelectorAll('.chaos-fail').forEach(b => b.onclick = async () => {
    if (await apiPost(`/api/chaos/${b.getAttribute('data-id')}/resolve`, { recovered: false }, 'Resolve')) renderTrials();
  });
  const dg = document.getElementById('dream-go');
  if (dg && !dg.dataset.bound) {
    dg.dataset.bound = '1';
    const fsel = document.getElementById('dream-formation');
    apiJSON('/api/formations').then(fd => { if (fd && fd.catalog) fsel.innerHTML = fd.catalog.map(f => `<option value='${esc(f.name)}'>${esc(f.title)}</option>`).join(''); });
    dg.onclick = async () => {
      const formation = fsel.value;
      const goal = (document.getElementById('dream-goal').value || '').trim();
      if (!goal) { alert('Enter a goal.'); return; }
      const res = await apiPost('/api/dreamscape/preview', { formation, goal }, 'Preview');
      if (res) {
        document.getElementById('dream-preview').innerHTML =
          `<div class='card'><div class='metric'><b>${esc(res.title)}</b><span class='muted'>~${res.est_tokens_total} tokens</span></div>` +
          res.stages.map(s => `<div class='metric'><span>${esc(s.stage)} · ${esc(s.assignee)}</span><span class='muted'>~${s.est_tokens}t</span></div>`).join('') + `</div>`;
      }
    };
  }
}

// ---- Sect Lore: bonds, drift, lineage, artifacts, council votes ----

async function renderLore() {
  const sec = document.getElementById('lore-section');
  const crew = window.__agents || [];
  if (crew.length < 1) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  // disciple selects (bonds + forge creator)
  ['bond-a', 'bond-b', 'forge-creator'].forEach(id => {
    const el = document.getElementById(id); if (!el) return;
    const cur = el.value;
    el.innerHTML = crew.map(a => `<option>${esc(a.name)}</option>`).join('');
    if (cur && crew.some(a => a.name === cur)) el.value = cur;
  });

  // bonds
  const b = await apiJSON('/api/bonds') || {};
  document.getElementById('bond-list').innerHTML = (b.pairs || []).length
    ? (b.pairs || []).map(p => `<div class='card'><div class='metric'><b>🤝 ${esc(p[0])} ↔ ${esc(p[1])}</b><button class='btn unbond' data-agent='${esc(p[0])}'>Unbind</button></div></div>`).join('')
    : `<div class='comms-sys muted'>No karmic bonds yet.</div>`;

  // drift
  const d = await apiJSON('/api/daoheart') || {};
  const drifts = Object.values(d.drift || {}).filter(x => x.status && x.status !== 'stable' && x.status !== 'insufficient');
  document.getElementById('drift-list').innerHTML = drifts.length
    ? drifts.map(x => `<div class='card omen-card ${x.status === 'degraded' ? 'omen-ominous' : 'omen-caution'}'>
        <div class='metric'><b>${esc(x.agent)}</b><span class='omen-badge ${x.status === 'degraded' ? 'omen-ominous' : 'omen-caution'}'>${esc(x.status)}</span></div>
        <div class='gov-bars muted'>success Δ ${x.signals.success_delta} · len ratio ${x.signals.length_ratio} · latency Δ ${x.signals.latency_delta_pct}%</div></div>`).join('')
    : `<div class='comms-sys muted'>All dao-hearts steady.</div>`;

  // lineage
  const lg = await apiJSON('/api/lineage') || {};
  const edges = lg.edges || [], origins = lg.origins || [];
  document.getElementById('lineage-list').innerHTML = (edges.length || origins.length)
    ? `<div class='card'>
        ${origins.map(o => `<div class='metric'><span>🌱 ${esc(o.skill)}</span><b>${esc(o.agent)} <span class='muted'>(${esc(o.source)})</span></b></div>`).join('')}
        ${edges.map(e => `<div class='metric'><span>📜 ${esc(e.skill)}</span><b>${esc(e.teacher)} → ${esc(e.student)}</b></div>`).join('')}
      </div>`
    : `<div class='comms-sys muted'>No techniques traced yet.</div>`;

  // artifacts
  const av = await apiJSON('/api/artifacts') || {};
  document.getElementById('artifact-list').innerHTML = (av.artifacts || []).length
    ? (av.artifacts || []).map(a => `<div class='card'><div class='metric'><b>⚱ ${esc(a.name)}</b><span class='muted'>${esc(a.kind)} v${a.version}</span></div>${metric('By', esc(a.creator))}${metric('Used', a.uses)}<div class='muted'>${esc(a.description || '')}</div></div>`).join('')
    : `<div class='comms-sys muted'>The vault is empty.</div>`;

  bindLore();
}

function bindLore() {
  const root = document.getElementById('lore-section');
  const bg = document.getElementById('bond-go');
  if (bg && !bg.dataset.bound) {
    bg.dataset.bound = '1';
    bg.onclick = async () => {
      const a = document.getElementById('bond-a').value, bb = document.getElementById('bond-b').value;
      if (a === bb) { alert('Pick two different disciples.'); return; }
      if (await apiPost('/api/bonds/bind', { a, b: bb }, 'Bind')) renderLore();
    };
  }
  root.querySelectorAll('.unbond').forEach(btn => btn.onclick = async () => {
    if (await apiPost('/api/bonds/unbind', { agent: btn.getAttribute('data-agent') }, 'Unbind')) renderLore();
  });
  const fg = document.getElementById('forge-go');
  if (fg && !fg.dataset.bound) {
    fg.dataset.bound = '1';
    fg.onclick = async () => {
      const body = {
        creator: document.getElementById('forge-creator').value,
        name: (document.getElementById('forge-name').value || '').trim(),
        kind: document.getElementById('forge-kind').value,
        description: document.getElementById('forge-desc').value,
        content: document.getElementById('forge-content').value,
      };
      if (!body.name || !body.content) { alert('Name and content required.'); return; }
      if (await apiPost('/api/artifacts/forge', body, 'Forge')) { document.getElementById('forge-name').value = ''; document.getElementById('forge-content').value = ''; renderLore(); }
    };
  }
  const vg = document.getElementById('vote-go');
  if (vg && !vg.dataset.bound) {
    vg.dataset.bound = '1';
    vg.onclick = async () => {
      const question = (document.getElementById('vote-q').value || '').trim();
      if (!question) { alert('Enter a question.'); return; }
      const votes = {};
      (document.getElementById('vote-ballots').value || '').split('\n').forEach(line => {
        const i = line.indexOf(':'); if (i > 0) votes[line.slice(0, i).trim()] = line.slice(i + 1).trim();
      });
      if (!Object.keys(votes).length) { alert('Enter ballots as "Disciple: choice" lines.'); return; }
      const res = await apiPost('/api/council/vote', { question, votes }, 'Vote');
      if (res) document.getElementById('vote-result').innerHTML =
        `<div class='card'><div class='metric'><b>Winner</b><b class='money-pos'>${esc(res.winner)}</b></div>
         ${Object.entries(res.tally).map(([k, v]) => metric(esc(k), Math.round(v * 10) / 10)).join('')}
         ${res.dissent.length ? `<div class='muted'>Dissent: ${res.dissent.map(esc).join(', ')}</div>` : ''}</div>`;
    };
  }
}

// ---- Sect Map: spatial realm view + cultivation chronicle ----

const MAP_W = 1000, MAP_H = 560, CLOUD_Y = 442;
const SVGNS = 'http://www.w3.org/2000/svg';

function mseed(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return () => { h = Math.imul(h ^ (h >>> 15), 2246822507); h ^= h >>> 13; return ((h >>> 0) % 1000) / 1000; }; }

function centerOutOrder(n) {
  const mid = (n - 1) / 2;
  return Array.from({ length: n }, (_, i) => i).sort((a, b) => Math.abs(a - mid) - Math.abs(b - mid));
}

// An organic karst spire (narrow top, bowed flanks, a couple of ledges).
function spirePath(cx, baseY, apexY, w, rnd) {
  const h = w / 2, H = baseY - apexY;
  const lean = (rnd() - 0.5) * w * 0.18;
  const ax = cx + lean;
  return `M ${cx - h} ${baseY}
    C ${cx - h * 0.92} ${baseY - H * 0.18}, ${cx - h * 0.7} ${baseY - H * 0.28}, ${cx - h * 0.55} ${baseY - H * 0.42}
    C ${cx - h * 0.46} ${baseY - H * 0.55}, ${cx - h * 0.5} ${baseY - H * 0.64}, ${cx - h * 0.34} ${baseY - H * 0.74}
    C ${cx - h * 0.24} ${baseY - H * 0.84}, ${ax - h * 0.14} ${apexY + H * 0.06}, ${ax} ${apexY}
    C ${ax + h * 0.16} ${apexY + H * 0.07}, ${cx + h * 0.3} ${baseY - H * 0.8}, ${cx + h * 0.42} ${baseY - H * 0.66}
    C ${cx + h * 0.56} ${baseY - H * 0.52}, ${cx + h * 0.62} ${baseY - H * 0.4}, ${cx + h * 0.72} ${baseY - H * 0.26}
    C ${cx + h * 0.84} ${baseY - H * 0.14}, ${cx + h * 0.94} ${baseY - H * 0.05}, ${cx + h} ${baseY} Z`;
}

function foliage(g, cx, y, r) {
  [[0, 0, r], [-r * 0.8, r * 0.3, r * 0.7], [r * 0.8, r * 0.25, r * 0.7], [0, -r * 0.5, r * 0.75]].forEach(([dx, dy, rr]) =>
    g.appendChild(svgEl('circle', { cx: cx + dx, cy: y + dy, r: rr, fill: '#5f9d54', opacity: '0.92' })));
  g.appendChild(svgEl('circle', { cx: cx - r * 0.3, cy: y - r * 0.2, r: r * 0.5, fill: '#7bbf68', opacity: '0.9' }));
}

function svgEl(tag, attrs) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }

// ===== Sect Map: role-based peaks (halls) over the pixel-art backdrop =====

function tierOf(a) {
  const r = (a.cultivation && a.cultivation.realm) || 0, g = a.governance || {};
  if (g.is_leader) return 'leader';
  if (r >= 6) return 'elder';
  if (r >= 4) return 'core';
  if (r >= 2) return 'inner';
  return 'outer';
}

// Peaks anchored to map_bg.png's painted pavilions (% of the art).
const PEAK_DEFS = [
  { id: 'leader', title: "Sect Leader's Peak", icon: '👑', kind: 'group', tiers: ['leader'], bg: 'leader_bg.png', anchor: { x: 49, y: 26 } },
  { id: 'elders', title: "Elders' Peak", icon: '🜍', kind: 'group', tiers: ['elder', 'core'], anchor: { x: 29, y: 9 } },
  { id: 'inner', title: 'Inner Court', icon: '🟦', kind: 'group', tiers: ['inner'], anchor: { x: 81, y: 13 } },
  { id: 'techniques', title: 'Technique Hall', icon: '🗡️', kind: 'utility', cat: 'tools', bg: 'technique_bg.png', anchor: { x: 66, y: 6 } },
  { id: 'outer', title: 'Outer Court', icon: '⛰️', kind: 'group', tiers: ['outer'], anchor: { x: 11, y: 41 } },
  { id: 'pill', title: 'Pill Pavilion', icon: '⚗️', kind: 'utility', cat: 'pills', bg: 'pill_bg.png', anchor: { x: 65, y: 45 } },
  { id: 'mission', title: 'Mission Hall', icon: '📜', kind: 'utility', cat: 'quests', bg: 'mission_bg.png', anchor: { x: 93, y: 43 } },
  { id: 'council', title: 'Dao Council', icon: '⚖️', kind: 'utility', cat: 'council', anchor: { x: 39, y: 58 } },
  { id: 'treasury', title: 'Treasure Pavilion', icon: '🪙', kind: 'utility', cat: 'treasury', bg: 'treasure_bg.png', anchor: { x: 6, y: 67 } },
  // Seclusion Caves: disciples sit on the central stone platform only
  { id: 'seclusion', title: 'Seclusion Caves', icon: '🕳️', kind: 'group', filter: 'seclusion', bg: 'seclusion_bg.png', floor: { cx: 50, baseY: 70, spread: 22, arc: 5 }, anchor: { x: 22, y: 71 } },
];

// state-based membership for group peaks that aren't rank tiers
const PEAK_FILTERS = { seclusion: a => !!(a.cultivation && a.cultivation.in_seclusion) };

function buildPeaks(crew) {
  const byTier = { leader: [], elder: [], core: [], inner: [], outer: [] };
  crew.forEach(a => byTier[tierOf(a)].push(a));
  return PEAK_DEFS.map(d => {
    let members = [];
    if (d.kind === 'group') {
      if (d.filter && PEAK_FILTERS[d.filter]) members = crew.filter(PEAK_FILTERS[d.filter]);
      else (d.tiers || []).forEach(t => { members = members.concat(byTier[t] || []); });
    }
    members.sort((x, y) => (y.governance?.standing || 0) - (x.governance?.standing || 0));
    return { ...d, members };
  });
}

async function renderSectMap() {
  const sec = document.getElementById('map-section');
  const crew = (window.__agents || []).slice();
  if (!crew.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  const peaks = buildPeaks(crew);
  window.__peaks = peaks;
  buildSkinMap(crew);  // lock one distinct skin per disciple
  const n = crew.length;
  const leader = crew.find(a => a.governance?.is_leader) || crew.slice().sort((a, b) => (b.governance?.standing || 0) - (a.governance?.standing || 0))[0];
  const cultivating = crew.filter(a => ['working', 'queued'].includes(a.status) || a.cultivation?.in_seclusion).length;
  const idle = crew.filter(a => (a.status || 'idle') === 'idle' && !a.cultivation?.in_seclusion && !a.cultivation?.in_roaming).length;
  const succ = Math.round(crew.reduce((s, a) => s + (a.reputation?.signals?.success_pct ?? 100), 0) / n);
  const stones = crew.reduce((s, a) => s + (a.cultivation?.stones || 0), 0);

  // day/night by local time; a storm gathers when the sect is unhealthy
  const hour = new Date().getHours();
  const phase = hour < 6 ? 'night' : hour < 9 ? 'dawn' : hour < 17 ? 'day' : hour < 20 ? 'dusk' : 'night';
  const storm = (window.__lastProjects || []).some(p => p.health === 'error')
    || crew.some(a => a.status === 'error' || a.cultivation?.pending_tribulation);

  const stat = (icon, label, val) => `<div class='po-row'><span>${icon} ${label}</span><b>${val}</b></div>`;
  const world = document.getElementById('map-world');
  world.innerHTML = `
    <img class='map-bg-img' src='/assets/map/map_bg.png' alt='' draggable='false'>
    <div class='map-weather ph-${phase}${storm ? ' storm' : ''}'>${storm ? "<div class='map-rain'></div>" : ''}</div>
    <div class='pixel-panel peak-overview'>
      <div class='pp-title'>☯ Peak Overview</div>
      ${stat('👤', 'Disciples', n)}${stat('🧘', 'Cultivating', cultivating)}${stat('🍵', 'Idle', idle)}
      ${stat('✓', 'Success', succ + '%')}${stat(STONE, 'Spirit stones', stones.toLocaleString())}
    </div>
    <div class='pixel-panel peak-lord'><span class='pl-label'>Peak Lord</span><b>👑 ${esc(leader ? leader.name : '—')}</b><span class='muted'>${esc(leader?.cultivation?.realm_name || '')}</span></div>
    <div class='map-motes'>${Array.from({ length: 14 }, (_, i) => `<span style='left:${(i * 7 + 4) % 98}%;animation-delay:${(i * 0.9).toFixed(1)}s;animation-duration:${9 + (i % 5) * 2}s'></span>`).join('')}</div>
    <div class='map-markers'></div>`;

  const markers = world.querySelector('.map-markers');
  peaks.forEach(p => {
    const sub = p.kind === 'group'
      ? `${p.members.length} disciple${p.members.length === 1 ? '' : 's'}`
      : 'utility hall';
    const active = p.kind === 'group' && p.members.some(m => ['working', 'queued'].includes(m.status));
    const b = document.createElement('button');
    b.className = 'peak-marker' + (p.id === 'leader' ? ' pm-leader' : '') + (p.kind === 'utility' ? ' pm-util' : '');
    b.style.left = p.anchor.x + '%'; b.style.top = p.anchor.y + '%';
    b.setAttribute('data-peak', p.id);
    b.innerHTML = `<span class='pm-plaque'><span class='pm-name'>${p.icon} ${esc(p.title)}</span>
      <span class='pm-realm'>${esc(sub)}</span></span>
      <span class='pm-pin crew-dot ${active ? 'warning' : 'ok'}'></span>
      <span class='pm-enter'>click to enter ▸</span>`;
    b.addEventListener('click', () => enterPeak(p.id));
    markers.appendChild(b);
  });

  // chronicle feed
  let ch = { recent: [] };
  try { ch = await fetch('/api/chronicle?limit=40', { headers: authHeaders() }).then(r => r.json()); } catch (_) {}
  const feed = document.getElementById('chronicle-feed');
  feed.innerHTML = (ch.recent || []).length
    ? (ch.recent || []).map(e => `<div class='chronicle-row'><span class='chronicle-glyph'>${esc(e.glyph)}</span><b>${esc(e.agent)}</b> <span class='muted'>${esc(e.kind)}</span> — ${esc(e.detail)}</div>`).join('')
    : `<div class='comms-sys muted'>The chronicle is yet unwritten.</div>`;
}

// ---- activity each disciple performs (label + sprite slot) ----
function hallActivity(a) {
  const c = a.cultivation || {}, st = a.status || 'idle';
  if (c.in_roaming) return { act: 'roam', label: 'Roaming', sprite: -1 };
  if (c.in_seclusion) return { act: 'seclude', label: 'In Seclusion', sprite: 1 };
  if (st === 'error') return { act: 'struggle', label: 'Wrestling a Demon', sprite: 5 };
  if (c.event === 'breakthrough' && (Date.now() - (c.event_ts || 0) < 30000)) return { act: 'breakthrough', label: 'Breaking Through', sprite: 3 };
  if (st === 'working' || st === 'queued') return { act: 'cultivate', label: 'Cultivating', sprite: 0 };
  return { act: 'sweep', label: 'Tending the Hall', sprite: 4 };
}
// sprite keys → filename suffix in /assets/map/sprites/agent_<key>.png
const SPRITE_NAMES = { cultivate: 0, meditate: 1, seclude: 1, refine: 2, breakthrough: 3, sweep: 4, struggle: 5, demon: 'demon' };
// A disciple may pin a fixed sprite (agents.yaml `sprite: demon`); else use the activity sprite.
function spriteFor(a, ax) {
  const ov = a && a.sprite;
  if (ov !== null && ov !== undefined && ov !== '') { const k = SPRITE_NAMES[ov]; return String(k !== undefined ? k : ov); }
  return String(ax.sprite >= 0 ? ax.sprite : 0);
}
// character skin sets → filename suffix (agent_<pose><suffix>.png). Per-agent via
// agents.yaml `skin:`; elders/leader default to the white-haired set.
const SKIN_SUFFIX = {
  youth: '', young: '', a: '', elder: '_b', white: '_b', b: '_b',
  empress: '_empress', lotus: '_lotus', azure: '_azure', shadow: '_shadow', vegeta: '_vegeta',
  goku: '_goku', redhood: '_redhood', brute: '_brute', sage: '_sage', asta: '_asta',
  wraith: '_wraith', warlock: '_warlock', fiend: '_fiend', lich: '_lich',
};
// pool of distinct character sets a disciple can be randomly assigned
const RANDOM_SKINS = [...new Set(Object.values(SKIN_SUFFIX))];
function _hash(s) { let h = 2166136261; s = String(s); for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

// Lock each disciple to ONE skin: explicit `skin:` wins; everyone else gets a
// DISTINCT random skin (no two agents alike until the pool runs out),
// deterministic so it never changes between renders.
let _skinMap = null, _skinKey = '';
function buildSkinMap(crew) {
  const key = crew.map(a => a.name).join('|');
  if (_skinMap && _skinKey === key) return _skinMap;
  const pool = [...RANDOM_SKINS];
  let seed = 0x9e3779b1;
  for (let i = pool.length - 1; i > 0; i--) { seed = (Math.imul(seed, 1103515245) + 12345) & 0x7fffffff; const j = seed % (i + 1); [pool[i], pool[j]] = [pool[j], pool[i]]; }
  const map = {};
  crew.filter(a => !(a.skin && SKIN_SUFFIX[a.skin] !== undefined) && !a.sprite)
      .map(a => a.name).sort()
      .forEach((nm, i) => { map[nm] = pool[i % pool.length]; });
  _skinMap = map; _skinKey = key;
  return map;
}
function skinSuffix(a) {
  const s = a && a.skin;
  if (s != null && s !== '' && SKIN_SUFFIX[s] !== undefined) return SKIN_SUFFIX[s];      // explicit skin wins
  if (_skinMap && _skinMap[a && a.name] !== undefined) return _skinMap[a.name];          // locked unique random
  return RANDOM_SKINS[_hash(a && a.name) % RANDOM_SKINS.length];                          // fallback
}
function hallUnitInner(act, key, variant) {
  const v = (variant && key !== 'demon') ? variant : '';
  return `<span class='hall-sprite act-${act}'><span class='hall-fx'><i></i><i></i><i></i></span><img src='/assets/map/sprites/agent_${key}${v}.png' alt='' draggable='false'></span>`;
}
function hallPositions(k, floor) {
  // `floor` lets a hall pin disciples to a sensible standing area (e.g. a cave's
  // central platform) instead of spreading them across scenery that can't be sat on.
  const cx = floor?.cx ?? 50;
  const baseY = floor?.baseY ?? 60;
  const spread = floor ? Math.min(floor.spread, 8 + k * 6) : Math.min(72, 16 + k * 9);
  const arc = floor?.arc ?? 11;
  const out = [];
  for (let i = 0; i < k; i++) { const t = k === 1 ? 0.5 : i / (k - 1); out.push({ x: cx - spread / 2 + spread * t, y: baseY + (floor ? 0 : 20) - Math.sin(t * Math.PI) * arc }); }
  return out;
}

function _zoomTo(peakId) {
  const scene = document.getElementById('sect-map');
  const marker = scene.querySelector(`.peak-marker[data-peak="${CSS.escape(peakId)}"]`);
  if (marker) {
    const pb = marker.getBoundingClientRect(), sb = scene.getBoundingClientRect();
    document.getElementById('map-world').style.transformOrigin =
      `${((pb.left + pb.width / 2 - sb.left) / sb.width) * 100}% ${((pb.top + pb.height / 2 - sb.top) / sb.height) * 100}%`;
  }
  scene.classList.add('zooming');
}
function _showHall(html, instant) {
  const hall = document.getElementById('map-hall');
  const wasShown = hall.classList.contains('shown') && !hall.classList.contains('hidden');
  hall.className = 'map-hall';
  hall.innerHTML = html;
  if (instant && wasShown) { hall.classList.add('shown'); }                 // live refresh, no fade/zoom
  else setTimeout(() => { hall.classList.remove('hidden'); requestAnimationFrame(() => hall.classList.add('shown')); }, 360);
  document.getElementById('hall-back').onclick = exitHall;
  return hall;
}

function enterPeak(peakId) {
  const peak = (window.__peaks || []).find(p => p.id === peakId);
  if (!peak) return;
  window.__openPeak = peakId;
  _zoomTo(peakId);
  if (peak.kind === 'group') renderGroupHall(peak, (peak.members[0] || {}).name);
  else renderUtilityHall(peak);
}

// re-render the currently open hall in place (called on live SSE updates)
function refreshOpenHall() {
  const id = window.__openPeak;
  if (!id) return;
  const peak = (window.__peaks || []).find(p => p.id === id);
  if (!peak) return;
  if (peak.kind === 'group') renderGroupHall(peak, window.__openFocus, true);
  else renderUtilityHall(peak, true);
}

async function renderGroupHall(peak, focusName, instant) {
  const all = peak.members || [];
  const present = all.filter(x => !x.cultivation?.in_roaming);
  const focus = all.find(x => x.name === focusName) || all[0];
  window.__openFocus = focus ? focus.name : undefined;
  const row = (icon, label, val) => `<div class='po-row'><span>${icon} ${label}</span><b>${val}</b></div>`;
  const cult = all.filter(x => ['working', 'queued'].includes(x.status) || x.cultivation?.in_seclusion).length;
  const stones = all.reduce((s, x) => s + (x.cultivation?.stones || 0), 0);
  const avgRealm = all.length ? Math.round(all.reduce((s, x) => s + (x.cultivation?.realm || 0), 0) / all.length) : 0;

  const agentList = all.length ? all.map(x => {
    const ax = hallActivity(x);
    return `<button class='hall-agent-row${focus && x.name === focus.name ? ' hl' : ''}' data-agent='${esc(x.name)}'>
      <span>${x.governance?.is_leader ? '👑' : '•'} ${esc(x.name)}</span><span class='muted'>${esc(ax.label)}</span></button>`;
  }).join('') : `<div class='muted' style='padding:6px'>No disciples dwell here yet.</div>`;

  const g = focus?.governance || {}, c = focus?.cultivation || {};
  const arrayFx = (peak.bg && peak.bg !== 'hall_bg.png') ? '' : `<div class='hall-array'><div class='ha-ring'></div><div class='ha-core'></div><div class='ha-beam'></div></div>`;
  const hall = _showHall(`
    <img class='hall-bg-img' src='/assets/map/${peak.bg || 'hall_bg.png'}' alt='' draggable='false'>${arrayFx}
    <button id='hall-back' class='btn hall-back'>← return to the heavens</button>
    <div class='hall-title pixel-panel'><b>${peak.icon} ${esc(peak.title)}</b><span class='muted'>${all.length} disciple${all.length === 1 ? '' : 's'}</span></div>
    <div class='pixel-panel hall-info'>
      <div class='pp-title'>⛩ Hall Info</div>
      ${row('👤', 'Present', present.length + '/' + all.length)}${row('🧘', 'Cultivating', cult)}
      ${row('⬆', 'Avg realm', avgRealm)}${row(STONE, 'Spirit stones', stones.toLocaleString())}
    </div>
    <div class='pixel-panel hall-agents'>
      <div class='pp-title'>Disciples (${all.length})</div><div class='hall-agent-list'>${agentList}</div>
    </div>
    <div class='hall-floor-units'></div>
    ${focus ? `<div class='pixel-panel hall-focus'>
      <div class='pp-title'>${esc(focus.name)}</div>
      ${row('', 'Standing', g.standing ?? '—')}${row('', 'Realm', `Lv.${c.realm ?? 0} ${esc(c.realm_name || '')}`)}
      ${row('', 'Doing', hallActivity(focus).label)}
      <div class='hall-assign'><input id='hall-task' placeholder='Assign a task to ${esc(focus.name)}…'><button id='hall-assign-go' class='btn'>Assign</button></div>
      <div class='map-detail-chron'><b class='muted'>Chronicle</b><div id='hall-timeline' class='muted'>loading…</div></div>
    </div>` : ''}`, instant);

  const units = hall.querySelector('.hall-floor-units');
  const pos = hallPositions(present.length, peak.floor);
  present.forEach((x, i) => {
    let ax = hallActivity(x);
    let p = pos[i];
    // the Sect Leader presides seated upon the throne (meditation pose)
    if (peak.id === 'leader' && x.governance?.is_leader) { ax = { act: 'cultivate', label: 'Presiding over the Sect', sprite: 0 }; p = { x: 50, y: 53.5 }; }
    const hl = focus && x.name === focus.name;
    const u = document.createElement('button');
    u.className = 'hall-unit act-' + ax.act + (hl ? ' hl' : '') + (peak.id === 'leader' && x.governance?.is_leader ? ' on-throne' : '');
    u.style.left = p.x + '%'; u.style.top = p.y + '%'; u.style.zIndex = String(10 + Math.round(p.y));
    u.setAttribute('data-agent', x.name);
    u.innerHTML = `${hallUnitInner(ax.act, spriteFor(x, ax), skinSuffix(x))}<span class='hall-tag'>${x.governance?.is_leader ? '👑 ' : ''}${esc(x.name)}<span class='ht-act'>${esc(ax.label)}</span></span>`;
    u.addEventListener('click', () => renderGroupHall(peak, x.name));
    units.appendChild(u);
  });
  hall.querySelectorAll('.hall-agent-row').forEach(b => b.onclick = () => renderGroupHall(peak, b.getAttribute('data-agent')));
  // click-to-assign: give the focused disciple a task right from the hall
  const goBtn = document.getElementById('hall-assign-go'), taskInp = document.getElementById('hall-task');
  if (goBtn && taskInp && focus) {
    const send = async () => {
      const task = (taskInp.value || '').trim();
      if (!task) return;
      goBtn.disabled = true;
      try {
        const res = await fetch(`/api/agents/${encodeURIComponent(focus.name)}/task`, {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify({ task }),
        });
        if (!res.ok) { const j = await res.json().catch(() => ({})); alert('Assign failed: ' + (j.detail || res.status)); }
        else taskInp.value = '';
      } catch (e) { alert('Assign failed: ' + e); }
      goBtn.disabled = false;
    };
    goBtn.onclick = send;
    taskInp.onkeydown = e => { if (e.key === 'Enter') send(); };
  }
  if (focus) {
    try {
      const ch = await fetch(`/api/chronicle/${encodeURIComponent(focus.name)}?limit=10`, { headers: authHeaders() }).then(r => r.json());
      const tl = (ch.timeline || []).slice().reverse();
      const el = document.getElementById('hall-timeline');
      if (el) el.innerHTML = tl.length ? tl.map(e => `<div class='chronicle-row'><span class='chronicle-glyph'>${esc(e.glyph)}</span>${esc(e.detail || e.kind)}</div>`).join('') : 'No deeds recorded yet.';
    } catch (_) {}
  }
}

async function renderUtilityHall(peak, instant) {
  const row = (a, b2) => `<div class='po-row'><span>${a}</span><b>${b2}</b></div>`;
  let body = `<div class='muted' style='padding:6px'>loading…</div>`;
  const arrayFx = (peak.bg && peak.bg !== 'hall_bg.png') ? '' : `<div class='hall-array'><div class='ha-ring'></div><div class='ha-core'></div><div class='ha-beam'></div></div>`;
  const hall = _showHall(`
    <img class='hall-bg-img' src='/assets/map/${peak.bg || 'hall_bg.png'}' alt='' draggable='false'>${arrayFx}
    <button id='hall-back' class='btn hall-back'>← return to the heavens</button>
    <div class='hall-title pixel-panel'><b>${peak.icon} ${esc(peak.title)}</b></div>
    <div class='pixel-panel hall-util'><div class='pp-title'>${peak.icon} ${esc(peak.title)}</div><div id='util-body'>${body}</div></div>`, instant);
  const set = html => { const el = document.getElementById('util-body'); if (el) el.innerHTML = html; };
  try {
    if (peak.cat === 'quests') {
      const d = await fetch('/api/quests', { headers: authHeaders() }).then(r => r.json());
      const qs = d.catalog || [];
      set(qs.length ? qs.map(q => `<div class='util-item'><b>📜 ${esc(q.name || q.id || 'Quest')}</b><div class='muted'>${esc(q.skill ? 'grants ' + q.skill : (q.description || ''))}</div></div>`).join('') : '<div class="muted">No missions posted.</div>');
    } else if (peak.cat === 'pills') {
      const d = await fetch('/api/pills', { headers: authHeaders() }).then(r => r.json());
      const ps = d.catalog || [];
      set(ps.length ? ps.map(p => `<div class='util-item'><b>⚗️ ${esc(p.name || p.id)}</b><div class='muted'>${esc(p.effect || p.description || '')}</div></div>`).join('') : '<div class="muted">The cauldron is cold.</div>');
    } else if (peak.cat === 'treasury') {
      const d = await fetch('/api/treasury', { headers: authHeaders() }).then(r => r.json());
      set(row(STONE + ' Balance', (d.balance ?? 0).toLocaleString()) + row('Spirit veins', d.veins ?? d.vein_count ?? '—') + (d.detail ? `<div class='muted' style='margin-top:6px'>${esc(d.detail)}</div>` : ''));
    } else if (peak.cat === 'tools') {
      const d = await fetch('/api/tools', { headers: authHeaders() }).then(r => r.json());
      const ts = d.tools || d.catalog || [];
      set(ts.length ? ts.map(t => `<div class='util-item'><b>🗡️ ${esc(t.name)}</b><div class='muted'>${esc(t.description || '')}</div></div>`).join('') : '<div class="muted">No sanctioned arts.</div>');
    } else if (peak.cat === 'council') {
      const [cm, votes] = await Promise.all([
        fetch('/api/comms?limit=8', { headers: authHeaders() }).then(r => r.json()).catch(() => ({})),
        fetch('/api/council/history?limit=5', { headers: authHeaders() }).then(r => r.json()).catch(() => ({})),
      ]);
      const st = (cm.status && cm.status.active) ? `<div class='util-item'><b>⚔️ In session:</b> <span class='muted'>${esc((cm.status.mission && cm.status.mission.goal) || 'a council activity')}</span></div>` : '';
      const feed = (cm.feed || []).slice(-6).map(m => `<div class='util-item'><b>${esc(m.from)}</b> <span class='muted'>${esc((m.content || '').slice(0, 80))}</span></div>`).join('');
      const vs = (votes.history || []).slice().reverse().map(v => `<div class='util-item'><b>🗳️ ${esc(v.question || 'vote')}</b> <span class='muted'>→ ${esc(v.winner || '—')}</span></div>`).join('');
      set((st || '') + (vs || '') + (feed || '') || '<div class="muted">The council chamber is quiet.</div>');
    }
  } catch (_) { set('<div class="muted">unavailable</div>'); }
}

function exitHall() {
  const scene = document.getElementById('sect-map'), hall = document.getElementById('map-hall');
  window.__openPeak = null;
  hall.classList.remove('shown');
  scene.classList.remove('zooming');
  setTimeout(() => hall.classList.add('hidden'), 360);
}

// ---- live updates + ascension cutscene (driven by SSE /api/stream) ----
async function refreshLive() {
  if (document.getElementById('map-section').classList.contains('hidden')) return;
  await renderAgentCrew();      // refresh window.__agents from /api/agents
  renderSectMap();              // peak counts + weather
  refreshOpenHall();            // re-render the open hall in place (no zoom)
}

function ascend(name) {
  const a = (window.__agents || []).find(x => x.name === name);
  const realm = a?.cultivation?.realm_name || 'a new realm';
  let cs = document.getElementById('ascension');
  if (!cs) { cs = document.createElement('div'); cs.id = 'ascension'; document.body.appendChild(cs); }
  cs.className = 'ascension show';
  cs.innerHTML = `<div class='asc-rays'></div><div class='asc-text'><div class='asc-name'>✦ ${esc(name)} ✦</div><div class='asc-sub'>breaks through to<br><b>${esc(realm)}</b></div></div>`;
  clearTimeout(window.__ascTimer);
  window.__ascTimer = setTimeout(() => cs.classList.remove('show'), 3200);
}


// ---- Heavenly Omens: prophecy / divination ----

function omenCard(o) {
  const map = { ominous: ['omen-ominous', '☄ Ominous'], caution: ['omen-caution', '☁ Caution'], favorable: ['omen-favorable', '✦ Favorable'] };
  const [cls, label] = map[o.omen] || ['omen-favorable', o.omen];
  return `<div class='card omen-card ${cls}'>
    <div class='metric'><b>${esc(o.project)}</b><span class='omen-badge ${cls}'>${label}</span></div>
    ${metric('Realm', esc(o.device))}
    <div class='omen-note'>“${esc(o.note)}”</div>
    <div class='muted omen-points'>read from ${esc(o.points)} omens</div>
  </div>`;
}

async function renderProphecy() {
  const sec = document.getElementById('prophecy-section');
  let data;
  try { data = await fetch('/api/prophecy', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { sec.classList.add('hidden'); return; }
  const omens = (data && data.omens) || [];
  if (!omens.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  const ill = omens.filter(o => o.omen !== 'favorable').length;
  document.getElementById('prophecy-pill').textContent =
    ill ? `${ill} ill omen${ill > 1 ? 's' : ''}` : 'all auspicious';
  document.getElementById('prophecy-omens').innerHTML = omens.map(omenCard).join('');
}

// ---- Ship Comms: inter-agent missions ----

function agentHue(name) {
  let h = 0;
  for (let i = 0; i < String(name).length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

function commsBubble(m) {
  if (m.kind === 'system') {
    return `<div class='comms-sys'>${esc(m.content)}</div>`;
  }
  const hue = agentHue(m.from);
  const ini = esc(String(m.from).charAt(0).toUpperCase());
  return `<div class='comms-msg' style='--hue:${hue}'>
    <div class='comms-head'><span class='comms-avatar'>${ini}</span><span class='comms-from'>${esc(m.from)}</span></div>
    <div class='comms-body'>${esc(m.content)}</div>
  </div>`;
}

async function renderComms() {
  const section = document.getElementById('comms-section');
  const crew = window.__agents || [];
  if (crew.length < 2) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');

  // participant checkboxes (preserve current selections across refresh)
  const partsEl = document.getElementById('comms-participants');
  const checked = new Set(Array.from(partsEl.querySelectorAll('input:checked')).map(i => i.value));
  const firstRender = !partsEl.dataset.ready;
  partsEl.dataset.ready = '1';
  partsEl.innerHTML = crew.map(a => {
    const on = firstRender || checked.has(a.name) ? 'checked' : '';
    return `<label class='comms-chip'><input type='checkbox' value='${esc(a.name)}' ${on}> ${esc(a.name)}</label>`;
  }).join('');

  // debate roster selects
  ['debate-a', 'debate-b', 'debate-judge'].forEach((id, idx) => {
    const elx = document.getElementById(id);
    if (!elx) return;
    const cur = elx.value;
    elx.innerHTML = crew.map(a => `<option>${esc(a.name)}</option>`).join('');
    if (cur && crew.some(a => a.name === cur)) elx.value = cur;
    else if (crew[idx]) elx.value = crew[idx].name;
  });

  // formation catalog (populate once; keep selection across refresh)
  const fsel = document.getElementById('formation-select');
  if (fsel && !fsel.dataset.ready) {
    try {
      const fd = await fetch('/api/formations', { headers: authHeaders() }).then(r => r.json());
      window.__formations = (fd && fd.catalog) || [];
      fsel.innerHTML = window.__formations.map(f =>
        `<option value='${esc(f.name)}'>${esc(f.title)} (${(f.stages || []).map(s => esc(s.name)).join(' → ')})</option>`).join('');
      fsel.dataset.ready = '1';
      const showDesc = () => {
        const f = (window.__formations || []).find(x => x.name === fsel.value);
        document.getElementById('formation-desc').textContent = f ? (f.description || '') : '';
      };
      fsel.onchange = showDesc; showDesc();
    } catch (_) {}
  }

  let data;
  try { data = await fetch('/api/comms', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { return; }
  const st = (data && data.status) || {};
  const active = st.active;
  const m = st.mission;
  document.getElementById('comms-status').textContent =
    active && m ? `cultivating · round ${m.round}/${m.rounds} · ${m.current || '…'}` : 'in seclusion';
  const launchBtn = document.getElementById('comms-launch');
  launchBtn.disabled = !!active;
  launchBtn.textContent = active ? 'Trial underway…' : 'Begin Trial';

  const feedEl = document.getElementById('comms-feed');
  const atBottom = feedEl.scrollHeight - feedEl.scrollTop - feedEl.clientHeight < 60;
  let html = (data.feed || []).map(commsBubble).join('') || `<div class='comms-sys muted'>The hall is silent.</div>`;
  if (active && m && m.current) {
    const hue = agentHue(m.current);
    const ini = esc(String(m.current).charAt(0).toUpperCase());
    html += `<div class='comms-typing'><span class='comms-avatar' style='--hue:${hue}'>${ini}</span>${esc(m.current)} is channeling qi<span class='dots'><i></i><i></i><i></i></span></div>`;
  }
  feedEl.innerHTML = html;
  if (atBottom) feedEl.scrollTop = feedEl.scrollHeight;
}

function bindComms() {
  const dgo = document.getElementById('debate-go');
  if (dgo && !dgo.dataset.bound) {
    dgo.dataset.bound = '1';
    dgo.onclick = async () => {
      const topic = (document.getElementById('debate-topic').value || '').trim();
      if (!topic) { alert('Enter a proposition.'); return; }
      const a = document.getElementById('debate-a').value;
      const b = document.getElementById('debate-b').value;
      const judge = document.getElementById('debate-judge').value;
      const rounds = Number(document.getElementById('comms-rounds').value || 2);
      dgo.disabled = true;
      try {
        const res = await fetch('/api/comms/debate', {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ topic, a, b, judge, rounds }),
        });
        if (!res.ok) { const j = await res.json().catch(() => ({})); alert('Debate failed: ' + (j.detail || res.status)); }
      } catch (e) { alert('Debate failed: ' + e); }
      dgo.disabled = false;
      renderComms();
    };
  }
  const fgo = document.getElementById('formation-go');
  if (fgo && !fgo.dataset.bound) {
    fgo.dataset.bound = '1';
    fgo.onclick = async () => {
      const formation = document.getElementById('formation-select').value;
      const goal = (document.getElementById('formation-goal').value || '').trim();
      if (!formation) { alert('Choose a formation.'); return; }
      if (!goal) { alert('Enter a goal for the array.'); return; }
      fgo.disabled = true;
      try {
        const res = await fetch('/api/formations/run', {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ formation, goal }),
        });
        if (!res.ok) { const j = await res.json().catch(() => ({})); alert('Formation failed: ' + (j.detail || res.status)); }
      } catch (e) { alert('Formation failed: ' + e); }
      fgo.disabled = false;
      renderComms();
    };
  }
  const tgo = document.getElementById('tournament-go');
  if (tgo && !tgo.dataset.bound) {
    tgo.dataset.bound = '1';
    tgo.onclick = async () => {
      const topic = (document.getElementById('debate-topic').value || '').trim();
      if (!topic) { alert('Enter a proposition for the tournament.'); return; }
      const participants = Array.from(document.querySelectorAll('#comms-participants input:checked')).map(i => i.value);
      if (participants.length < 2) { alert('Check at least 2 disciples above to enter the bracket.'); return; }
      const judge = document.getElementById('debate-judge').value;
      tgo.disabled = true;
      try {
        const res = await fetch('/api/comms/tournament', {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ topic, participants, judge, rounds: 1 }),
        });
        if (!res.ok) { const j = await res.json().catch(() => ({})); alert('Tournament failed: ' + (j.detail || res.status)); }
      } catch (e) { alert('Tournament failed: ' + e); }
      tgo.disabled = false;
      renderComms();
    };
  }
  const btn = document.getElementById('comms-launch');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.onclick = async () => {
    const goal = (document.getElementById('comms-goal').value || '').trim();
    if (!goal) return;
    const participants = Array.from(document.querySelectorAll('#comms-participants input:checked')).map(i => i.value);
    if (participants.length < 2) { alert('Select at least 2 agents.'); return; }
    const rounds = Number(document.getElementById('comms-rounds').value || 2);
    btn.disabled = true;
    try {
      const res = await fetch('/api/comms/mission', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ goal, participants, rounds }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Trial failed: ' + (b.detail || res.status)); }
    } catch (e) { alert('Trial failed: ' + e); }
    renderComms();
  };
}

// ---- Vault Memory (Obsidian) ----

function vaultCard(h) {
  return `<div class='card vault-card' data-path='${esc(h.path)}'>
    <div class='metric'><b>📝 ${esc(h.title)}</b><span class='muted'>${esc(h.path)}</span></div>
    <div class='agent-reply'>${esc(h.excerpt)}</div>
    <details class='details'><summary>Open note</summary><pre class='vault-body'>Loading…</pre></details>
  </div>`;
}

function bindVaultCards(root) {
  root.querySelectorAll('.vault-card details').forEach(d => d.ontoggle = async () => {
    if (!d.open) return;
    const path = d.closest('.vault-card').getAttribute('data-path');
    const body = d.querySelector('.vault-body');
    try {
      const n = await fetch(`/api/memory/note?path=${encodeURIComponent(path)}`, { headers: authHeaders() }).then(r => r.json());
      body.innerText = n.content || '(empty)';
    } catch (_) { body.innerText = 'Error loading note.'; }
  });
}

async function renderVault() {
  const section = document.getElementById('vault-section');
  let data;
  try { data = await fetch('/api/memory', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { section.classList.add('hidden'); return; }
  if (!data || !data.enabled) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');
}

function bindVault() {
  const btn = document.getElementById('vault-search');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  const run = async () => {
    const q = (document.getElementById('vault-q').value || '').trim();
    const out = document.getElementById('vault-results');
    if (!q) { out.innerHTML = ''; return; }
    out.innerHTML = `<div class='card muted'>Searching…</div>`;
    try {
      const data = await fetch(`/api/memory/search?q=${encodeURIComponent(q)}`, { headers: authHeaders() }).then(r => r.json());
      const res = (data && data.results) || [];
      out.innerHTML = res.length ? res.map(vaultCard).join('') : `<div class='card muted'>No matching notes.</div>`;
      bindVaultCards(out);
    } catch (_) { out.innerHTML = `<div class='card muted'>Search failed.</div>`; }
  };
  btn.onclick = run;
  document.getElementById('vault-q').onkeydown = e => { if (e.key === 'Enter') run(); };
}

// ---- Guarded Tools (Phase 4) ----

function toolBadgeClass(s) {
  if (s === 'done') return 'ok';
  if (s === 'pending' || s === 'running' || s === 'approved') return 'warning';
  if (s === 'denied') return 'unknown';
  return 'error';
}

function toolCallCard(c) {
  const cls = toolBadgeClass(c.status);
  const args = Object.keys(c.args || {}).length ? `<div class='comms-sys' style='text-align:left'>args: ${esc(JSON.stringify(c.args))}</div>` : '';
  const out = c.output ? `<div class='agent-reply'>${esc(c.output)}</div>` : '';
  const acts = c.status === 'pending'
    ? `<div class='actions'><button class='act-btn act-btn-start' data-approve='${c.id}'>Approve</button><button class='act-btn act-btn-stop' data-deny='${c.id}'>Deny</button></div>`
    : '';
  return `<div class='card'>
    <div class='metric'><b>🔧 ${esc(c.tool)}</b><span class='badge ${cls}'>${esc(c.status)}</span></div>
    ${metric('Requested by', esc(c.requester))}
    ${args}${out}${acts}
  </div>`;
}

async function renderTools() {
  const section = document.getElementById('tools-section');
  let data;
  try { data = await fetch('/api/tools', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { section.classList.add('hidden'); return; }
  if (!data || !data.enabled) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');

  // autonomy status + kill switch
  const auto = data.autonomy || {};
  const statusEl = document.getElementById('tools-status');
  const killBtn = document.getElementById('tools-kill');
  if (!auto.enabled) {
    statusEl.textContent = 'guarded · approval required';
    killBtn.classList.add('hidden');
  } else if (auto.paused) {
    statusEl.textContent = 'autonomy PAUSED';
    killBtn.classList.remove('hidden');
    killBtn.textContent = 'Resume autonomy';
  } else {
    const win = auto.hours ? (auto.in_window ? ` · window ${auto.hours}` : ` · OUTSIDE window ${auto.hours}`) : '';
    statusEl.textContent = `autonomy on · budget ${auto.max_calls}/task${win}`;
    killBtn.classList.remove('hidden');
    killBtn.textContent = 'Pause autonomy';
  }
  killBtn.dataset.paused = auto.paused ? '1' : '';

  const sel = document.getElementById('tools-select');
  const cur = sel.value;
  sel.innerHTML = (data.tools || []).map(t =>
    `<option value='${esc(t.name)}'>${esc(t.name)}${t.auto_approve ? ' (auto)' : ''} — ${esc(t.description)}</option>`).join('');
  if (cur) sel.value = cur;

  const callsEl = document.getElementById('tools-calls');
  const calls = (data.calls || []).slice().reverse();
  callsEl.innerHTML = calls.length ? calls.map(toolCallCard).join('') : `<div class='card muted'>No tool calls yet.</div>`;
  callsEl.querySelectorAll('[data-approve]').forEach(b => b.onclick = async () => {
    b.disabled = true;
    await fetch(`/api/tools/${b.getAttribute('data-approve')}/approve`, { method: 'POST', headers: authHeaders() }).catch(() => {});
    renderTools();
  });
  callsEl.querySelectorAll('[data-deny]').forEach(b => b.onclick = async () => {
    b.disabled = true;
    await fetch(`/api/tools/${b.getAttribute('data-deny')}/deny`, { method: 'POST', headers: authHeaders() }).catch(() => {});
    renderTools();
  });
}

function bindTools() {
  const audit = document.querySelector('.tools-audit');
  if (audit && !audit.dataset.bound) {
    audit.dataset.bound = '1';
    audit.ontoggle = async () => {
      if (!audit.open) return;
      const body = document.getElementById('tools-audit-body');
      body.innerHTML = `<div class='card muted'>Loading…</div>`;
      try {
        const d = await fetch('/api/tools/audit', { headers: authHeaders() }).then(r => r.json());
        const calls = (d.calls || []).slice().reverse();
        const note = d.persisted ? '' : `<div class='card muted'>In-memory only — set MAYBOT_DB to persist the audit log.</div>`;
        body.innerHTML = note + (calls.length ? calls.map(toolCallCard).join('') : `<div class='card muted'>No tool calls recorded.</div>`);
      } catch (_) { body.innerHTML = `<div class='card muted'>Failed to load audit log.</div>`; }
    };
  }
  const kill = document.getElementById('tools-kill');
  if (kill && !kill.dataset.bound) {
    kill.dataset.bound = '1';
    kill.onclick = async () => {
      const action = kill.dataset.paused ? 'resume' : 'pause';
      kill.disabled = true;
      await fetch(`/api/autonomy/${action}`, { method: 'POST', headers: authHeaders() }).catch(() => {});
      kill.disabled = false;
      renderTools();
    };
  }
  const btn = document.getElementById('tools-run');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.onclick = async () => {
    const tool = document.getElementById('tools-select').value;
    const raw = (document.getElementById('tools-args').value || '').trim();
    let args = {};
    if (raw) { try { args = JSON.parse(raw); } catch (_) { alert('Args must be valid JSON.'); return; } }
    btn.disabled = true;
    try {
      const res = await fetch('/api/tools/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ tool, args }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Run failed: ' + (b.detail || res.status)); }
    } catch (e) { alert('Run failed: ' + e); }
    btn.disabled = false;
    renderTools();
  };
}

// ---- Spirit Veins (sect treasury) ----

function fmtDur(s) {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60), ss = s % 60;
  return m ? `${m}m ${ss}s` : `${ss}s`;
}

async function renderTreasury() {
  let t;
  try { t = await fetch('/api/treasury', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { return; }
  if (!t) return;
  document.getElementById('treasury-balance').innerHTML = `<span class='stone'></span>${t.balance}`;
  document.getElementById('treasury-detail').textContent =
    `veins +${t.income_per_hour}/hr · ${t.total_income} channelled · ${t.total_spent} disbursed`;
}

function bindTreasury() {
  const btn = document.getElementById('endow-go');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.onclick = async () => {
    const amount = Number(document.getElementById('endow-amount').value || 0);
    if (!amount || amount <= 0) { alert('Enter an amount to endow.'); return; }
    btn.disabled = true;
    try {
      const res = await fetch('/api/treasury/endow', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ amount }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Endow failed: ' + (b.detail || res.status)); }
      else document.getElementById('endow-amount').value = '';
    } catch (e) { alert('Endow failed: ' + e); }
    btn.disabled = false;
    renderTreasury();
  };
}

// ---- Usage & Cost ----

function usageCard(u) {
  const succCls = u.success_pct >= 90 ? 'money-pos' : (u.success_pct >= 50 ? 'money-zero' : 'money-neg');
  const models = Object.keys(u.models || {}).join(', ') || '—';
  return `<div class='card'>
    <div class='metric'><b>🤖 ${esc(u.agent)}</b><b class='money-pos'>$${Number(u.cost).toFixed(4)}</b></div>
    ${metric('Calls', `${esc(u.calls)} <span class='${succCls}'>(${esc(u.success_pct)}% ok)</span>`)}
    ${metric('Avg latency', `${esc(u.avg_latency_ms)} ms`)}
    ${metric('Tokens in / out', `${esc(u.tokens_in)} / ${esc(u.tokens_out)}`)}
    ${metric('Models', esc(models))}
  </div>`;
}

async function renderUsage() {
  const section = document.getElementById('usage-section');
  let data;
  try { data = await fetch('/api/usage', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { section.classList.add('hidden'); return; }
  const t = (data && data.totals) || {};
  if (!t.calls) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');
  document.getElementById('usage-total').textContent =
    `$${Number(t.cost || 0).toFixed(4)} · ${t.calls} calls · ${(t.tokens_in + t.tokens_out).toLocaleString()} tok`;
  document.getElementById('usage-table').innerHTML = (data.agents || []).map(usageCard).join('');
  renderReserves();
}

async function renderReserves() {
  const el = document.getElementById('qi-reserves');
  if (!el) return;
  let b; try { b = await fetch('/api/budget', { headers: authHeaders() }).then(r => r.json()); } catch (_) { el.innerHTML = ''; return; }
  const r = b.reserves || {};
  if (!r.enabled) {                                  // no budget configured → just a hint
    el.innerHTML = `<div class='qr-card'><div class='qr-head'><b>☯ Qi Reserves</b><span class='muted'>no budget set · spent $${Number(r.spent || 0).toFixed(4)}</span></div>
      <div class='muted' style='font-size:12px'>Set <code>MAYBOT_BUDGET_USD</code> to cap sect spend and auto-throttle low-merit disciples when it runs low.</div></div>`;
    return;
  }
  const pct = r.pct_remaining;
  const lvl = r.exhausted ? 'qr-exhausted' : r.critical ? 'qr-critical' : r.low ? 'qr-low' : 'qr-ok';
  const note = r.exhausted ? 'reserves spent — autonomous runs halted'
    : r.critical ? 'critical — only Trusted disciples may act'
    : r.low ? 'low — Probation disciples throttled' : 'healthy';
  const throttled = (b.agents || []).filter(a => a.status !== 'ok');
  // per-agent spend bars (share of total spend), tinted by throttle status
  const spenders = (b.agents || []).filter(a => a.cost > 0).sort((x, y) => y.cost - x.cost).slice(0, 8);
  const maxc = Math.max(0.0001, ...spenders.map(a => a.cost));
  const bars = spenders.map(a => `<div class='qr-agent'>
    <span class='qr-aname'>${a.status === 'ok' ? '' : (a.status === 'capped' ? '⛔ ' : '⚠ ')}${esc(a.agent)}</span>
    <span class='qr-abar'><span class='qr-a-${a.status}' style='width:${Math.round(100 * a.cost / maxc)}%'></span></span>
    <span class='qr-acost'>$${a.cost.toFixed(4)}</span></div>`).join('');
  el.innerHTML = `<div class='qr-card'>
    <div class='qr-head'><b>☯ Qi Reserves</b><span>$${Number(r.remaining).toFixed(2)} / $${Number(r.budget).toFixed(2)} <span class='muted'>(${pct}%)</span></span></div>
    <div class='qr-bar'><span class='${lvl}' style='width:${Math.max(0, Math.min(100, pct))}%'></span></div>
    <div class='qr-note ${lvl}'>${note}${throttled.length ? ` · throttled: ${throttled.map(a => esc(a.agent)).join(', ')}` : ''}</div>
    ${bars ? `<div class='qr-agents'>${bars}</div>` : ''}
  </div>`;
}

// Dedicated management area for AI agents (ai_project + local_ai_host).
function renderAiAgents(projects) {
  const section = document.getElementById('ai-agents-section');
  const el = document.getElementById('ai-agents');
  const agents = (projects || []).filter(p => AI_AGENT_TYPES.includes(p.type));
  if (!agents.length) {
    section.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  section.classList.remove('hidden');
  const online = agents.filter(p => p.metrics?.status === 'online' || p.status === 'running').length;
  const issues = agents.filter(p => p.health === 'warning' || p.health === 'error').length;
  document.getElementById('ai-agents-pill').textContent =
    `${agents.length} agents · ${online} online · ${issues} need attention`;
  const render = viewMode === 'base' ? roomCard : projectCard;
  const cls = viewMode === 'base' ? 'rooms-grid' : 'grid';
  el.innerHTML = `<div class='${cls}'>${agents.map(render).join('')}</div>`;
  bindProjectButtons(el);
}

function renderProjects(projects) {
  const projectsEl = document.getElementById('projects');
  const query = (document.getElementById('project-search').value || '').trim().toLowerCase();
  const health = document.getElementById('health-filter').value || 'ALL';
  const filtered = (projects || []).filter(p => projectMatches(p, query, health));

  document.getElementById('project-count-pill').textContent =
    `${filtered.length} of ${(projects || []).length} shown`;

  if (!filtered.length) {
    projectsEl.innerHTML = `<div class='card muted'>No projects match the current filter.</div>`;
    return;
  }

  if (viewMode === 'base') {
    renderStation(filtered);
    return;
  }

  const grouped = {};
  filtered.forEach(p => {
    const type = p.type || 'generic';
    (grouped[type] = grouped[type] || []).push(p);
  });

  const sections = TYPE_ORDER.filter(t => grouped[t]?.length).map(t =>
    `<section class='project-type'><h3 class='project-type-title'>${esc(TYPE_LABEL[t] || t)}</h3><div class='grid'>${grouped[t].map(projectCard).join('')}</div></section>`
  ).join('');
  projectsEl.innerHTML = sections;
  bindProjectButtons(projectsEl);
}

document.getElementById('manual-refresh').onclick = render;
function updateViewToggleLabel() {
  document.getElementById('toggle-view').textContent = viewMode === 'base' ? 'Disciples' : 'Sect Hall';
  document.body.classList.toggle('base-mode', viewMode === 'base');
}
document.getElementById('toggle-view').onclick = () => {
  viewMode = viewMode === 'base' ? 'card' : 'base';
  localStorage.setItem('maybot.view_mode', viewMode);
  updateViewToggleLabel();
  renderAiAgents(window.__lastProjects || []);
  renderProjects(window.__lastProjects || []);
};
updateViewToggleLabel();
document.getElementById('project-search').oninput = () => renderProjects(window.__lastProjects || []);
document.getElementById('health-filter').onchange = () => renderProjects(window.__lastProjects || []);
document.getElementById('clear-filters').onclick = () => {
  document.getElementById('project-search').value = '';
  document.getElementById('health-filter').value = 'ALL';
  renderProjects(window.__lastProjects || []);
};
document.getElementById('refresh-logs').onclick = () => {
  if (!selectedProject || !selectedProjectDevice) return;
  loadLogs(selectedProjectDevice, selectedProject);
};
document.getElementById('close-logs').onclick = () => document.getElementById('logs-panel').classList.add('hidden');
document.getElementById('copy-logs').onclick = async () => {
  const text = document.getElementById('logs').innerText || '';
  try { await navigator.clipboard.writeText(text); } catch (_) {}
};
document.getElementById('clear-logs').onclick = () => { document.getElementById('logs').innerText = ''; };
document.getElementById('pause-logs-refresh').onclick = () => {
  logsRefreshPaused = !logsRefreshPaused;
  document.getElementById('pause-logs-refresh').textContent = logsRefreshPaused ? 'Resume Logs Auto' : 'Pause Logs Auto';
};
document.querySelectorAll('.level-btn').forEach(btn => btn.onclick = () => {
  document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedLogLevel = btn.getAttribute('data-level') || 'ALL';
  if (selectedProject && selectedProjectDevice) loadLogs(selectedProjectDevice, selectedProject);
});
document.getElementById('toggle-refresh').onclick = () => {
  refreshPaused = !refreshPaused;
  document.getElementById('toggle-refresh').textContent = refreshPaused ? 'Resume Auto' : 'Pause Auto';
  if (refreshPaused) clearInterval(refreshInterval);
  else refreshInterval = setInterval(render, 7000);
};

const tokenInput = document.getElementById('control-token');
tokenInput.value = getControlToken();
document.getElementById('save-control-token').onclick = () => {
  localStorage.setItem(CONTROL_TOKEN_STORAGE_KEY, tokenInput.value || '');
};

render();
refreshInterval = setInterval(render, 7000);
startLogsAutoRefresh();

// Live updates via Server-Sent Events — instant refresh on agent/comms/tool changes.
let _streamDebounce = {};
function debounced(fn, key, ms = 250) {
  clearTimeout(_streamDebounce[key]);
  _streamDebounce[key] = setTimeout(fn, ms);
}
function setupStream() {
  let es;
  try { es = new EventSource(`/api/stream?token=${encodeURIComponent(getControlToken())}`); }
  catch (_) { return; }
  es.onmessage = (e) => {
    let msg; try { msg = JSON.parse(e.data); } catch (_) { return; }
    if (msg.type === 'comms') debounced(renderComms, 'comms');
    else if (msg.type === 'tools') debounced(renderTools, 'tools');
    else if (msg.type === 'agents') {
      if (msg.data && msg.data.event === 'breakthrough' && msg.data.agent) ascend(msg.data.agent);  // ascension cutscene
      debounced(() => { renderComms(); refreshLive(); }, 'agents');
    }
  };
  es.onerror = () => {}; // EventSource auto-reconnects
}
setupStream();
