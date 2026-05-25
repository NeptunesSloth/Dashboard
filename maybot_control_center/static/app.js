let selectedProject = null;
let selectedProjectDevice = null;
let refreshPaused = false;
let refreshInterval = null;
let logsRefreshPaused = false;
let logsInterval = null;
let selectedLogLevel = 'ALL';
const CONTROL_TOKEN_STORAGE_KEY = 'maybot.control_token';
const clientHistory = {};
const MAX_HISTORY = 60;
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
    ${alerts}
    <details class='details'><summary>Raw details</summary><pre>${esc(JSON.stringify(p, null, 2))}</pre></details>
    ${actions}
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

    const grouped = {};
    (data.projects || []).forEach(p => {
      const type = p.type || 'generic';
      if (!grouped[type]) grouped[type] = [];
      grouped[type].push(p);
      const key = `${p.device}:${p.name}`;
      if (!clientHistory[key]) clientHistory[key] = [];
      clientHistory[key].push({ ts: Date.now(), pnl: p.metrics?.profit_today, health: p.health });
      if (clientHistory[key].length > MAX_HISTORY) clientHistory[key].shift();
    });

    const order = ['trading_bot', 'code_project', 'game_server', 'website', 'school', 'ai_project', 'local_ai_host', 'generic'];
    projectsEl.innerHTML = order.filter(t => grouped[t]?.length).map(t =>
      `<section class='project-type'><h3 class='project-type-title'>${esc(TYPE_LABEL[t] || t)}</h3><div class='grid'>${grouped[t].map(projectCard).join('')}</div></section>`
    ).join('');

    document.querySelectorAll('[data-action]').forEach(btn => btn.onclick = async () => {
      btn.disabled = true;
      await callAction(btn.getAttribute('data-device'), btn.getAttribute('data-project'), btn.getAttribute('data-action'));
      btn.disabled = false;
      render();
    });
    document.querySelectorAll('[data-log]').forEach(btn => btn.onclick = () => loadLogs(btn.getAttribute('data-device'), btn.getAttribute('data-project')));
  } catch (e) {
    err.classList.remove('hidden');
    summaryEl.classList.remove('loading');
    summaryEl.innerHTML = `<div class='card'><b>Overview unavailable</b><div class='muted'>${esc(String(e))}</div></div>`;
    devicesEl.innerHTML = '';
    projectsEl.innerHTML = '';
  }
}

document.getElementById('manual-refresh').onclick = render;
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
document.getElementById('save-control-token').onclick = () => localStorage.setItem(CONTROL_TOKEN_STORAGE_KEY, document.getElementById('control-token').value || '');
document.getElementById('control-token').value = getControlToken();
document.getElementById('toggle-refresh').onclick = () => {
  refreshPaused = !refreshPaused;
  document.getElementById('toggle-refresh').textContent = refreshPaused ? 'Resume Auto' : 'Pause Auto';
  if (refreshPaused) clearInterval(refreshInterval);
  else refreshInterval = setInterval(render, 7000);
};

render();
refreshInterval = setInterval(render, 7000);
startLogsAutoRefresh();
