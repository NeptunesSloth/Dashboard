let selectedProject = null;
let selectedProjectDevice = null;
let refreshPaused = false;
let refreshInterval = null;
let logsRefreshPaused = false;
let logsInterval = null;
let selectedLogLevel = 'ALL';
let viewMode = localStorage.getItem('maybot.view_mode') || 'card';
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
};
// Flavour for the "base" room view: an activity verb + icon per project type.
const TYPE_VERB = {
  trading_bot: 'TRADING', code_project: 'BUILDING', game_server: 'HOSTING', website: 'SERVING',
  school: 'PLANNING', ai_project: 'CODING', local_ai_host: 'INFERENCE', generic: 'RUNNING',
};
const TYPE_ICON = {
  trading_bot: '📈', code_project: '🛠️', game_server: '🎮', website: '🌐',
  school: '🎓', ai_project: '🤖', local_ai_host: '🧠', generic: '📦',
};
const TYPE_ORDER = ['trading_bot', 'code_project', 'game_server', 'website', 'school', 'ai_project', 'local_ai_host', 'generic'];

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
  if (p.status === 'stopped') return 'OFFLINE';
  if (p.status !== 'running') return 'STANDBY';
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
  return `<div class='room room--${esc(health)}' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
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
  root.querySelectorAll('[data-action]').forEach(btn => btn.onclick = async () => {
    btn.disabled = true;
    await callAction(btn.getAttribute('data-device'), btn.getAttribute('data-project'), btn.getAttribute('data-action'));
    btn.disabled = false;
    render();
  });
  root.querySelectorAll('[data-log]').forEach(btn => btn.onclick = () => loadLogs(btn.getAttribute('data-device'), btn.getAttribute('data-project')));
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
    // One uniform grid of rooms, ordered by type then name — like the base layout.
    const rooms = filtered
      .slice()
      .sort((a, b) => (TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type)) || String(a.name).localeCompare(String(b.name)))
      .map(roomCard).join('');
    projectsEl.innerHTML = `<div class='rooms-grid'>${rooms}</div>`;
    bindProjectButtons(projectsEl);
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
  document.getElementById('toggle-view').textContent = viewMode === 'base' ? 'Card View' : 'Base View';
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
