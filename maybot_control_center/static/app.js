let selectedProject = null;

function card(content){ return `<div class='card'>${content}</div>`; }

function healthBadge(h){ return `<span class='badge ${h||'unknown'}'>${h||'unknown'}</span>`; }

async function render(){
  const data = await fetch('/api/overview').then(r=>r.json());
  const s = data.summary;
  document.getElementById('summary').innerHTML = [
    ['Total Devices', s.total_devices], ['Online', s.online_devices], ['Offline', s.offline_devices],
    ['Projects', s.total_projects], ['Warn/Error', s.projects_with_warnings_errors], ['Bots Running', s.bots_running],
    ['PnL Today', s.total_trading_profit_today], ['PnL Week', s.total_trading_profit_this_week], ['Open Exposure', s.total_open_exposure],
    ['Tests Failing', s.tests_failing],
  ].map(([k,v])=>card(`<b>${k}</b><br>${v}`)).join('');

  document.getElementById('devices').innerHTML = data.devices.map(d=>card(`<b>${d.name}</b><br>${d.url}<br>${d.online?'online':'offline'}`)).join('');

  const grouped = {};
  data.projects.forEach(p=>{ const key=`${p.device} :: ${p.type}`; (grouped[key]=grouped[key]||[]).push(p); });
  const html = Object.entries(grouped).map(([k,items])=>`<div class='project-type'><h3>${k}</h3><div class='grid'>${items.map(p=>{
    const m=p.metrics||{};
    const trading = p.type==='trading_bot' ? `<br>PnL today: ${m.profit_today}<br>PnL week: ${m.profit_this_week}<br>Exposure: ${m.open_exposure}<br>Open positions: ${m.open_positions}` : '';
    return `<div class='card' data-project='${p.name}'><b>${p.name}</b><br>${healthBadge(p.health)}<br>Status: ${p.status}${trading}</div>`;
  }).join('')}</div></div>`).join('');
  document.getElementById('projects').innerHTML = html;

  document.querySelectorAll('[data-project]').forEach(el=>el.onclick=()=>{ selectedProject = el.getAttribute('data-project'); });
}

document.getElementById('refresh-logs').onclick = async ()=>{
  if(!selectedProject){ document.getElementById('logs').innerText='Select a project card first.'; return; }
  const level = document.getElementById('log-level').value;
  const res = await fetch(`/api/overview`).then(r=>r.json());
  const project = res.projects.find(p=>p.name===selectedProject);
  document.getElementById('logs').innerText = `Log viewing is agent-scoped. Selected: ${selectedProject} (${project?.device||'unknown device'}) Level: ${level}`;
};

render();
setInterval(render, 7000);
