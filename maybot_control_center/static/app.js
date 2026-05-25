async function main(){
  const data = await fetch('/api/overview').then(r=>r.json());
  document.getElementById('summary').innerHTML = `<pre>${JSON.stringify(data.summary,null,2)}</pre>`;
  document.getElementById('devices').innerHTML = `<div class='grid'>${data.devices.map(d=>`<div class='card'><b>${d.name}</b><br>${d.online?'online':'offline'}<br>${d.url}</div>`).join('')}</div>`;
  document.getElementById('projects').innerHTML = `<div class='grid'>${data.projects.map(p=>`<div class='card'><b>${p.name}</b><br>${p.device}<br>${p.type}<br>${p.status}<pre>${JSON.stringify(p.metrics,null,2)}</pre></div>`).join('')}</div>`;
}
main();
