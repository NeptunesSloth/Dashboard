let selectedProject = null;
let selectedProjectDevice = null;
let refreshPaused = false;
let refreshInterval = null;
let prevHealthMap = {};
const clientHistory = {};
const MAX_HISTORY = 60; // ~7 min at 7s intervals

if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission();
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function card(content, extra = '') { return `<div class='card${extra}'>${content}</div>`; }

function healthBadge(h) { return `<span class='badge ${esc(h || 'unknown')}'>${esc(h || 'unknown')}</span>`; }

function statusDot(online) { return `<span class='dot ${online ? 'dot-ok' : 'dot-err'}'></span>`; }

function sparkline(values, color, width = 110, height = 28) {
  const nums = values.map(Number).filter(v => !isNaN(v));
  if (nums.length < 2) return '';
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const range = max - min || 1;
  const step = width / (nums.length - 1);
  const pts = nums.map((v, i) =>
    `${(i * step).toFixed(1)},${(height - ((v - min) / range) * (height - 2) - 1).toFixed(1)}`
  ).join(' ');
  return `<svg class='sparkline' width='${width}' height='${height}'><polyline points='${pts}' fill='none' stroke='${color}' stroke-width='1.5' stroke-linejoin='round'/></svg>`;
}

const HEALTH_VAL = { ok: 2, warning: 1, unknown: 1.5, error: 0 };
const HEALTH_COLOR = { ok: '#2d8f4e', warning: '#d08a00', error: '#c53c3c', unknown: '#888' };

function projectSparkline(key, type, metrics) {
  const hist = clientHistory[key] || [];
  if (hist.length < 2) return '';
  if (type === 'trading_bot') {
    const vals = hist.map(h => h.pnl).filter(v => v != null && v !== 'unknown');
    return vals.length > 1 ? sparkline(vals, '#3b7dd8') : '';
  }
  if (type === 'local_ai_host') {
    const vals = hist.map(h => h.responseMs).filter(v => v != null && v !== 'unknown');
    return vals.length > 1 ? sparkline(vals, '#a855f7') : '';
  }
  const vals = hist.map(h => HEALTH_VAL[h.health] ?? 1.5);
  const lastHealth = hist[hist.length - 1]?.health || 'unknown';
  return sparkline(vals, HEALTH_COLOR[lastHealth] || '#888');
}

function actionButtons(p) {
  const a = p.actions_available || {};
  const btns = [
    a.start ? `<button class='act-btn' data-action='start' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>&#9654; Start</button>` : '',
    a.stop ? `<button class='act-btn' data-action='stop' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>&#9632; Stop</button>` : '',
    a.run_tests ? `<button class='act-btn' data-action='run-tests' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>&#9881; Tests</button>` : '',
  ].join('');
  return btns ? `<div class='actions'>${btns}</div>` : '';
}

async function render() {
  const statusEl = document.getElementById('refresh-status');
  statusEl.textContent = 'Refreshing…';
  try {
    const data = await fetch('/api/overview').then(r => r.json());
    const s = data.summary;

    document.getElementById('summary').innerHTML = [
      ['Total Devices', s.total_devices], ['Online', s.online_devices], ['Offline', s.offline_devices],
      ['Projects', s.total_projects], ['Warn/Error', s.projects_with_warnings_errors], ['Bots Running', s.bots_running],
      ['PnL Today', s.total_trading_profit_today], ['PnL Week', s.total_trading_profit_this_week],
      ['Open Exposure', s.total_open_exposure], ['Tests Failing', s.tests_failing],
      ['Local AI Total', s.local_ai_hosts_total], ['Local AI Online', s.local_ai_hosts_online],
      ['Local AI Offline', s.local_ai_hosts_offline], ['Local AI Errors', s.local_ai_hosts_with_errors],
    ].map(([k, v]) => card(`<b>${esc(k)}</b><br>${esc(v)}`)).join('');

    document.getElementById('devices').innerHTML = data.devices.map(d =>
      card(`${statusDot(d.online)}<b>${esc(d.name)}</b><br><small>${esc(d.url)}</small><br>${d.online ? 'online' : 'offline'}`)
    ).join('');

    // accumulate client-side history and fire browser notifications
    data.projects.forEach(p => {
      const key = `${p.device}:${p.name}`;
      if (!clientHistory[key]) clientHistory[key] = [];
      const m = p.metrics || {};
      clientHistory[key].push({
        ts: Date.now(),
        health: p.health,
        pnl: m.profit_today,
        responseMs: m.response_time_ms,
      });
      if (clientHistory[key].length > MAX_HISTORY) clientHistory[key].shift();

      const prev = prevHealthMap[key];
      const curr = p.health;
      if (prev !== undefined && prev !== curr && (curr === 'error' || curr === 'warning')) {
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification(`MayBot: ${p.name}`, {
            body: `Health ${prev} → ${curr} on ${p.device} (${p.status})`,
          });
        }
      }
      prevHealthMap[key] = curr;
    });

    const grouped = {};
    data.projects.forEach(p => {
      const key = `${p.device} :: ${p.type}`;
      (grouped[key] = grouped[key] || []).push(p);
    });

    document.getElementById('projects').innerHTML = Object.entries(grouped).map(([k, items]) =>
      `<div class='project-type'><h3>${esc(k)}</h3><div class='grid'>${items.map(p => {
        const m = p.metrics || {};
        const histKey = `${p.device}:${p.name}`;
        const trading = p.type === 'trading_bot'
          ? `<br>PnL today: ${esc(m.profit_today)}<br>PnL week: ${esc(m.profit_this_week)}<br>Exposure: ${esc(m.open_exposure)}<br>Open positions: ${esc(m.open_positions)}`
          : '';
        const localAi = p.type === 'local_ai_host'
          ? `<br>Provider: ${esc(m.provider)}<br>Base URL: ${esc(m.base_url)}<br>Status: ${esc(m.status)}<br>Model: ${esc(m.default_model)}<br>Models: ${esc((m.available_models || []).length)}<br>Resp ms: ${esc(m.response_time_ms)}<br>CPU: ${esc(m.cpu_usage)}<br>RAM MB: ${esc(m.ram_usage_mb)}<br>GPU/VRAM: ${esc(m.gpu_vram_usage)}`
          : '';
        const isSelected = p.name === selectedProject && p.device === selectedProjectDevice;
        return `<div class='card${isSelected ? ' selected' : ''}' data-project='${esc(p.name)}' data-device='${esc(p.device)}'>
          <b>${esc(p.name)}</b><br>Device: ${esc(p.device)}<br>${healthBadge(p.health)}<br>Status: ${esc(p.status)}${trading}${localAi}
          ${projectSparkline(histKey, p.type, m)}
          ${actionButtons(p)}
        </div>`;
      }).join('')}</div></div>`
    ).join('');

    document.querySelectorAll('[data-project]').forEach(el => el.onclick = (e) => {
      if (e.target.classList.contains('act-btn')) return;
      selectedProject = el.getAttribute('data-project');
      selectedProjectDevice = el.getAttribute('data-device');
      document.querySelectorAll('[data-project]').forEach(e => e.classList.remove('selected'));
      el.classList.add('selected');
    });

    document.querySelectorAll('.act-btn').forEach(btn => btn.onclick = async (e) => {
      e.stopPropagation();
      const action = btn.getAttribute('data-action');
      const project = btn.getAttribute('data-project');
      const device = btn.getAttribute('data-device');
      const origText = btn.textContent;
      btn.disabled = true;
      btn.textContent = '…';
      const logsEl = document.getElementById('logs');
      logsEl.innerText = `Running ${action} on ${project} (${device})…`;
      try {
        const url = `/api/action/${encodeURIComponent(device)}/${encodeURIComponent(project)}/${encodeURIComponent(action)}`;
        const res = await fetch(url, { method: 'POST' });
        const result = await res.json();
        logsEl.innerText = JSON.stringify(result, null, 2);
      } catch (err) {
        logsEl.innerText = `Error: ${err}`;
      }
      btn.disabled = false;
      btn.textContent = origText;
      render();
    });

    statusEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    document.getElementById('summary').innerHTML = card(`<b>Error:</b> Failed to load — ${esc(String(e))}`, ' error-card');
    document.getElementById('refresh-status').textContent = 'Refresh failed';
  }
}

document.getElementById('refresh-logs').onclick = async () => {
  if (!selectedProject) { document.getElementById('logs').innerText = 'Select a project card first.'; return; }
  const level = document.getElementById('log-level').value;
  document.getElementById('logs').innerText = 'Loading…';
  try {
    const url = `/api/logs/${encodeURIComponent(selectedProjectDevice)}/${encodeURIComponent(selectedProject)}?level=${encodeURIComponent(level)}`;
    const data = await fetch(url).then(r => r.json());
    document.getElementById('logs').innerText = (data.lines || []).join('\n') || '(no logs)';
  } catch (e) {
    document.getElementById('logs').innerText = `Error fetching logs: ${e}`;
  }
};

document.getElementById('toggle-refresh').onclick = () => {
  refreshPaused = !refreshPaused;
  if (refreshPaused) {
    clearInterval(refreshInterval);
    document.getElementById('toggle-refresh').textContent = 'Resume Refresh';
  } else {
    render();
    refreshInterval = setInterval(render, 7000);
    document.getElementById('toggle-refresh').textContent = 'Pause Refresh';
  }
};

render();
refreshInterval = setInterval(render, 7000);
