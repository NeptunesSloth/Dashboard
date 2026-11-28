// Sect Academy service worker: keeps the app shell available offline.
// Network-first, so an updated server is picked up at once; the cache is only
// the fallback. API calls are never cached (they are your live progress).
const CACHE = 'sect-academy-v7';
const SHELL = ['/', '/academy.js', '/sect.js', '/art.js', '/reader.js', '/pictures.js', '/handwriting.js', '/academy.css', '/icon.svg', '/manifest.webmanifest', '/art/hq_grid.webp', '/art/bg_map.webp',
  '/art/p_leader.webp', '/art/p_elder.webp', '/art/p_disciple.webp', '/art/p_analyst.webp', '/art/p_architect.webp', '/art/p_engineer.webp',
  '/art/p_researcher.webp', '/art/p_trader.webp'];
const PAGES = ['/', '/study', '/read', '/library', '/trials', '/progress'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  const key = PAGES.includes(url.pathname) ? '/' : url.pathname;
  e.respondWith(fetch(e.request).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(key, copy)); }
    return res;
  }).catch(() => caches.match(key)));
});
