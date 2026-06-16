import { $, api, post, esc, authHeaders, mountRail, initAccount, starfield } from '/lib.js';

mountRail('comics');
initAccount();
starfield('scene-canvas');

// live clock
const clock = $('clock');
if (clock) setInterval(() => { clock.textContent = new Date().toLocaleTimeString(); }, 1000);

let STATE = { exportEnabled: false, feeds: [] };

function msg(text, ok = true) {
  const m = $('cx-msg'); if (!m) return;
  m.textContent = text || '';
  m.style.color = ok ? 'var(--jade)' : 'var(--crimson)';
}

/* ---------------- library ---------------- */
async function loadLibrary() {
  const d = await api('/api/comics');
  if (!d) { $('library').innerHTML = `<div class="muted">Sign in to view the library.</div>`; return; }
  STATE.exportEnabled = !!d.export_enabled;
  STATE.feeds = d.feeds || [];
  renderLibActions();
  renderFeeds();
  const grid = $('library');
  const series = d.series || [];
  if (!series.length) {
    grid.innerHTML = `<div class="muted">No comics yet. ${window.__isOperator ? 'Add one above.' : ''}</div>`;
    return;
  }
  grid.innerHTML = series.map((s) => `
    <div class="cx-card" data-series="${esc(s.id)}">
      <div class="cx-cover" id="cover-${esc(s.id)}"><span class="ph">📖</span></div>
      <div class="cx-card-t">${esc(s.title)}</div>
      <div class="cx-card-n">${s.issue_count} issue${s.issue_count === 1 ? '' : 's'}</div>
    </div>`).join('');
  grid.querySelectorAll('.cx-card').forEach((c) => {
    c.onclick = () => openSeries(c.dataset.series);
    // best-effort cover: try the series' first issue cover endpoint
    probeCover(c.dataset.series);
  });
}

async function probeCover(seriesId) {
  // Ask the series detail for its first issue, then point an <img> at the cover.
  const d = await api('/api/comics/' + encodeURIComponent(seriesId));
  if (!d || !d.issues || !d.issues.length) return;
  const withCover = d.issues.find((i) => i.cover) || d.issues[0];
  if (!withCover || !withCover.cover) return;
  const box = $('cover-' + seriesId);
  if (!box) return;
  const url = `/api/comics/${encodeURIComponent(seriesId)}/${encodeURIComponent(withCover.id)}/cover`;
  const img = new Image();
  img.onload = () => { box.innerHTML = ''; box.appendChild(img); };
  img.alt = d.title || seriesId;
  img.src = url;
}

function renderLibActions() {
  const el = $('cx-libactions'); if (!el) return;
  let html = `<a class="cx-btn" href="/api/comics/bundle" download>⬇ Download all</a>`;
  if (window.__isOperator && STATE.exportEnabled) {
    html += `<button class="cx-btn" id="export-all">💽 Export to SSD</button>`;
  }
  el.innerHTML = html;
  const ex = $('export-all');
  if (ex) ex.onclick = () => exportTo(null);
}

/* ---------------- series detail ---------------- */
async function openSeries(seriesId) {
  const d = await api('/api/comics/' + encodeURIComponent(seriesId));
  const box = $('series-detail');
  if (!d) { box.style.display = 'none'; return; }
  const op = window.__isOperator;
  const rows = (d.issues || []).map((i) => `
    <div class="cx-issue" data-issue="${esc(i.id)}">
      <input type="checkbox" class="cx-sel" data-issue="${esc(i.id)}">
      <span class="cx-issue-t">${esc(i.title)}${i.read ? ' <span class="cx-badge">read</span>' : ''}</span>
      ${i.readable ? `<button class="cx-btn" data-read="${esc(i.id)}">Read</button>` : ''}
      <a class="cx-btn" href="/api/comics/${encodeURIComponent(seriesId)}/${encodeURIComponent(i.id)}/download" download>⬇</a>
      ${op ? `<button class="cx-btn" data-del="${esc(i.id)}">✕</button>` : ''}
    </div>`).join('');
  box.style.display = 'block';
  box.innerHTML = `
    <div class="section-h" style="margin-top:0">
      <div class="panel-title">${esc(d.title)}</div>
      <button class="cx-btn" id="cx-back">← Library</button>
    </div>
    <div class="cx-libactions" style="margin:10px 0">
      <a class="cx-btn" href="/api/comics/${encodeURIComponent(seriesId)}/bundle" download>⬇ Download series</a>
      <button class="cx-btn" id="dl-selected">⬇ Download selected</button>
      ${op && STATE.exportEnabled ? `<button class="cx-btn" id="export-series">💽 Export series to SSD</button>` : ''}
    </div>
    <div>${rows || '<div class="muted">No issues.</div>'}</div>`;
  $('cx-back').onclick = () => { box.style.display = 'none'; };
  box.querySelectorAll('[data-read]').forEach((b) => b.onclick = () => openReader(seriesId, b.dataset.read, d.title));
  box.querySelectorAll('[data-del]').forEach((b) => b.onclick = async () => {
    if (!confirm('Delete this issue?')) return;
    await api(`/api/comics/${encodeURIComponent(seriesId)}/${encodeURIComponent(b.dataset.del)}`, { method: 'DELETE' });
    openSeries(seriesId); loadLibrary();
  });
  $('dl-selected').onclick = () => {
    const ids = [...box.querySelectorAll('.cx-sel:checked')].map((c) => c.dataset.issue);
    if (!ids.length) { msg('Select issues first.', false); return; }
    const q = ids.map(encodeURIComponent).join(',');
    window.location.href = `/api/comics/${encodeURIComponent(seriesId)}/bundle?issues=${q}`;
  };
  const exs = $('export-series');
  if (exs) exs.onclick = () => exportTo(seriesId);
  box.scrollIntoView({ behavior: 'smooth' });
}

/* ---------------- reader overlay ---------------- */
let READER = { series: null, issue: null, page: 0, pages: 0 };
async function openReader(seriesId, issueId, title) {
  const meta = await api(`/api/comics/${encodeURIComponent(seriesId)}/${encodeURIComponent(issueId)}/pages`);
  if (!meta || !meta.readable || !meta.pages) {
    // Not a page-readable archive (e.g. PDF): open the file in a new tab.
    window.open(`/api/comics/${encodeURIComponent(seriesId)}/${encodeURIComponent(issueId)}/download`, '_blank');
    return;
  }
  READER = { series: seriesId, issue: issueId, page: 0, pages: meta.pages };
  $('r-title').textContent = title || issueId;
  $('reader').classList.add('open');
  $('reader').setAttribute('aria-hidden', 'false');
  setPage(0);
}
function setPage(n) {
  n = Math.max(0, Math.min(n, READER.pages - 1));
  READER.page = n;
  $('reader-img').src = `/api/comics/${encodeURIComponent(READER.series)}/${encodeURIComponent(READER.issue)}/page/${n}`;
  $('r-count').textContent = `${n + 1} / ${READER.pages}`;
  if (window.__isOperator) post(`/api/comics/${encodeURIComponent(READER.series)}/${encodeURIComponent(READER.issue)}/progress`, { page: n });
}
function closeReader() {
  $('reader').classList.remove('open');
  $('reader').setAttribute('aria-hidden', 'true');
  loadLibrary();
}
$('r-close').onclick = closeReader;
$('r-prev').onclick = () => setPage(READER.page - 1);
$('r-next').onclick = () => setPage(READER.page + 1);
document.addEventListener('keydown', (e) => {
  if (!$('reader').classList.contains('open')) return;
  if (e.key === 'ArrowLeft') setPage(READER.page - 1);
  else if (e.key === 'ArrowRight') setPage(READER.page + 1);
  else if (e.key === 'Escape') closeReader();
});

/* ---------------- feeds (right rail) ---------------- */
function renderFeeds() {
  const el = $('feeds'); if (!el) return;
  const op = window.__isOperator;
  if (!STATE.feeds.length) { el.innerHTML = `<div class="muted">No subscriptions.</div>`; return; }
  el.innerHTML = STATE.feeds.map((f) => `
    <div class="cx-feed">
      <div class="cx-feed-url">${esc(f.url)}</div>
      <div class="cx-feed-meta">
        <span>→ ${esc(f.series_id)}</span>
        <span>${f.last_status ? esc(f.last_status) : 'not polled'}</span>
        ${op ? `<button class="cx-btn" data-poll="${esc(f.id)}" style="padding:3px 8px;font-size:11px">Poll</button>
        <button class="cx-btn" data-unfeed="${esc(f.id)}" style="padding:3px 8px;font-size:11px">✕</button>` : ''}
      </div>
    </div>`).join('');
  el.querySelectorAll('[data-poll]').forEach((b) => b.onclick = async () => {
    msg('Polling feed…');
    const r = await post(`/api/comics/feeds/${encodeURIComponent(b.dataset.poll)}/poll`, {});
    msg(r ? `Feed polled: ${r.new} new issue(s).` : 'Poll failed.', !!r);
    loadLibrary();
  });
  el.querySelectorAll('[data-unfeed]').forEach((b) => b.onclick = async () => {
    await api(`/api/comics/feeds/${encodeURIComponent(b.dataset.unfeed)}`, { method: 'DELETE' });
    loadLibrary();
  });
}

/* ---------------- operator controls ---------------- */
function renderOps() {
  if (!window.__isOperator) return;
  $('ops').style.display = 'block';
  $('cx-ops').innerHTML = `
    <div class="cx-form">
      <h4>Upload a file</h4>
      <input class="cx-input" id="up-series" placeholder="Series title">
      <input class="cx-input" id="up-file" type="file" accept=".cbz,.zip,.cbr,.rar,.pdf,image/*">
      <button class="cx-btn" id="up-go">Upload</button>
    </div>
    <div class="cx-form">
      <h4>Add by URL</h4>
      <input class="cx-input" id="url-series" placeholder="Series title">
      <input class="cx-input" id="url-url" placeholder="https://…/issue.cbz">
      <button class="cx-btn" id="url-go">Download &amp; add</button>
    </div>
    <div class="cx-form">
      <h4>Subscribe to a feed</h4>
      <input class="cx-input" id="feed-series" placeholder="Series title">
      <input class="cx-input" id="feed-url" placeholder="https://…/feed.xml (RSS/Atom)">
      <button class="cx-btn" id="feed-go">Subscribe</button>
    </div>`;
  $('up-go').onclick = doUpload;
  $('url-go').onclick = doUrl;
  $('feed-go').onclick = doFeed;
}

async function doUpload() {
  const series = $('up-series').value.trim();
  const file = $('up-file').files[0];
  if (!series || !file) { msg('Series title and a file are required.', false); return; }
  msg('Uploading…');
  const q = `series_title=${encodeURIComponent(series)}&filename=${encodeURIComponent(file.name)}`;
  try {
    // The file bytes are the raw request body (no multipart dependency server-side).
    const r = await fetch('/api/comics/upload?' + q, { method: 'POST', headers: authHeaders(), body: file });
    const d = await r.json().catch(() => null);
    if (!r.ok) { msg((d && d.detail) || 'Upload failed.', false); return; }
    msg(`Added "${d.title}".`);
    loadLibrary();
  } catch (_) { msg('Upload failed.', false); }
}

async function doUrl() {
  const series = $('url-series').value.trim();
  const url = $('url-url').value.trim();
  if (!series || !url) { msg('Series title and URL are required.', false); return; }
  msg('Downloading…');
  const r = await post('/api/comics/ingest-url', { series_title: series, url });
  if (!r || r.detail) { msg((r && r.detail) || 'Download failed.', false); return; }
  msg(`Added "${r.title}".`);
  loadLibrary();
}

async function doFeed() {
  const series = $('feed-series').value.trim();
  const url = $('feed-url').value.trim();
  if (!series || !url) { msg('Series title and feed URL are required.', false); return; }
  const r = await post('/api/comics/feeds', { series_title: series, url });
  if (!r || r.detail) { msg((r && r.detail) || 'Could not subscribe.', false); return; }
  msg('Subscribed. New issues arrive automatically.');
  loadLibrary();
}

async function exportTo(seriesId) {
  const dest = prompt('Export destination path (must be an allow-listed mount, e.g. an SSD):');
  if (!dest) return;
  msg('Exporting…');
  const r = await post('/api/comics/export', { dest, series: seriesId || undefined });
  if (!r || r.detail) { msg((r && r.detail) || 'Export failed (destination not allowed?).', false); return; }
  msg(`Exported to ${r.dest}: ${r.copied} copied, ${r.skipped} already current.`);
}

// boot
(async function () {
  // initAccount sets window.__isOperator asynchronously; give it a tick.
  setTimeout(renderOps, 400);
  await loadLibrary();
})();
