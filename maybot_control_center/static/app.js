let selectedProject = null;
let selectedProjectDevice = null;
let refreshPaused = false;
let refreshInterval = null;

function card(content, extra = '') { return `<div class='card${extra}'>${content}</div>`; }
function healthBadge(h) { return `<span class='badge ${h || 'unknown'}'>${h || 'unknown'}</span>`; }
function statusDot(online) { return `<span class='dot ${online ? 'dot-ok' : 'dot-err'}'></span>`; }

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
    ].map(([k, v]) => card(`<b>${k}</b><br>${v}`)).join('');

    document.getElementById('devices').innerHTML = data.devices.map(d =>
      card(`${statusDot(d.online)}<b>${d.name}</b><br><small>${d.url}</small><br>${d.online ? 'online' : 'offline'}`)
    ).join('');

    const grouped = {};
    data.projects.forEach(p => {
      const key = `${p.device} :: ${p.type}`;
      (grouped[key] = grouped[key] || []).push(p);
    });

    document.getElementById('projects').innerHTML = Object.entries(grouped).map(([k, items]) =>
      `<div class='project-type'><h3>${k}</h3><div class='grid'>${items.map(p => {
        const m = p.metrics || {};
        const trading = p.type === 'trading_bot'
          ? `<br>PnL today: ${m.profit_today}<br>PnL week: ${m.profit_this_week}<br>Exposure: ${m.open_exposure}<br>Open positions: ${m.open_positions}`
          : '';
        const localAi = p.type === 'local_ai_host'
          ? `<br>Provider: ${m.provider}<br>Base URL: ${m.base_url}<br>Status: ${m.status}<br>Model: ${m.default_model}<br>Models: ${(m.available_models || []).length}<br>Resp ms: ${m.response_time_ms}<br>CPU: ${m.cpu_usage}<br>RAM MB: ${m.ram_usage_mb}<br>GPU/VRAM: ${m.gpu_vram_usage}`
          : '';
        const isSelected = p.name === selectedProject && p.device === selectedProjectDevice;
        return `<div class='card${isSelected ? ' selected' : ''}' data-project='${p.name}' data-device='${p.device}'>
          <b>${p.name}</b><br>Device: ${p.device}<br>${healthBadge(p.health)}<br>Status: ${p.status}${trading}${localAi}
        </div>`;
      }).join('')}</div></div>`
    ).join('');

    document.querySelectorAll('[data-project]').forEach(el => el.onclick = () => {
      selectedProject = el.getAttribute('data-project');
      selectedProjectDevice = el.getAttribute('data-device');
      document.querySelectorAll('[data-project]').forEach(e => e.classList.remove('selected'));
      el.classList.add('selected');
    });

    statusEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    document.getElementById('summary').innerHTML = card(`<b>Error:</b> Failed to load — ${e}`, ' error-card');
    document.getElementById('refresh-status').textContent = 'Refresh failed';
  }
}

document.getElementById('refresh-logs').onclick = async () => {
  if (!selectedProject) { document.getElementById('logs').innerText = 'Select a project card first.'; return; }
  const level = document.getElementById('log-level').value;
  document.getElementById('logs').innerText = 'Loading…';
  try {
    const url = `/api/logs/${encodeURIComponent(selectedProjectDevice)}/${encodeURIComponent(selectedProject)}?level=${level}`;
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
