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
    bindComms();
    renderComms();
    bindVault();
    renderVault();
    bindTools();
    renderTools();
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
  if (p.status === 'stopped') return 'Offline';
  if (p.status !== 'running') return 'Standby';
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
      <div class='crew-head'>SHIP CREW <span class='muted'>${ordered.length}</span></div>
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

function agentCard(a) {
  const st = a.status || 'idle';
  const dot = st === 'error' ? 'error' : (st === 'working' || st === 'queued' ? 'warning' : 'ok');
  const reply = a.last_reply ? esc(a.last_reply) : '';
  return `<div class='card agent-card agent-${esc(st)}' data-agent='${esc(a.name)}'>
    <div class='metric'><b>🤖 ${esc(a.name)}</b><span class='agent-state'><span class='crew-dot ${dot}'></span>${esc(st)}</span></div>
    ${metric('Role', esc(a.role || '—'))}
    ${metric('Model', esc(a.model))}
    ${metric('Tasks done', esc(a.tasks_done ?? 0))}
    ${a.current_task ? `<div class='agent-task-cur'>▸ ${esc(a.current_task)}</div>` : ''}
    ${a.error ? `<div class='alert alert-error'>${esc(a.error)}</div>` : ''}
    <div class='agent-reply'>${reply || `<span class='muted'>No output yet.</span>`}</div>
    <div class='agent-assign'>
      <input class='agent-input' placeholder='Assign a task…' data-agent='${esc(a.name)}'>
      <button class='btn agent-send' data-agent='${esc(a.name)}'>Assign</button>
    </div>
    <details class='details agent-transcript' data-agent='${esc(a.name)}'><summary>Transcript (${esc(a.transcript_len ?? 0)})</summary><pre class='agent-tx-body'>Open to load…</pre></details>
  </div>`;
}

function bindAgentCrew(root) {
  const sel = name => root.querySelector(`.agent-send[data-agent="${CSS.escape(name)}"]`);
  root.querySelectorAll('.agent-send').forEach(btn => btn.onclick = async () => {
    const name = btn.getAttribute('data-agent');
    const inp = root.querySelector(`.agent-input[data-agent="${CSS.escape(name)}"]`);
    const task = (inp && inp.value || '').trim();
    if (!task) return;
    btn.disabled = true;
    try {
      await fetch(`/api/agents/${encodeURIComponent(name)}/task`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ task }),
      });
      if (inp) inp.value = '';
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
  if (!crew.length) { section.classList.add('hidden'); el.innerHTML = ''; return; }
  section.classList.remove('hidden');
  document.getElementById('agent-crew-pill').textContent = `${crew.length} agents`;
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
  return `<div class='comms-msg' style='--hue:${hue}'>
    <div class='comms-from'>${esc(m.from)}</div>
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

  let data;
  try { data = await fetch('/api/comms', { headers: authHeaders() }).then(r => r.json()); }
  catch (_) { return; }
  const st = (data && data.status) || {};
  const active = st.active;
  const m = st.mission;
  document.getElementById('comms-status').textContent =
    active && m ? `running · round ${m.round}/${m.rounds} · ${m.current || '…'}` : 'idle';
  const launchBtn = document.getElementById('comms-launch');
  launchBtn.disabled = !!active;
  launchBtn.textContent = active ? 'Mission running…' : 'Launch Mission';

  const feedEl = document.getElementById('comms-feed');
  const atBottom = feedEl.scrollHeight - feedEl.scrollTop - feedEl.clientHeight < 60;
  feedEl.innerHTML = (data.feed || []).map(commsBubble).join('') || `<div class='comms-sys muted'>No missions yet.</div>`;
  if (atBottom) feedEl.scrollTop = feedEl.scrollHeight;
}

function bindComms() {
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
      if (!res.ok) { const b = await res.json().catch(() => ({})); alert('Mission failed: ' + (b.detail || res.status)); }
    } catch (e) { alert('Mission failed: ' + e); }
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
    statusEl.textContent = `autonomy on · budget ${auto.max_calls}/task`;
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
    else if (msg.type === 'agents') debounced(() => { renderAgentCrew(); renderComms(); }, 'agents');
  };
  es.onerror = () => {}; // EventSource auto-reconnects
}
setupStream();
