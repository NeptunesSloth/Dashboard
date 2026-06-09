// MayBot PWA service worker — offline app shell, never caches the API.
// Network-first for the UI so a redeploy is picked up immediately; the cache is
// only a fallback when offline. (A cache-first worker would pin a stale app.js /
// style.css forever — which made the console look "old" after updates.)
const CACHE = 'maybot-v3';
const SHELL = [
  '/', '/app.js', '/style.css', '/icon.svg', '/manifest.webmanifest', '/pwa.js',
  '/command.css', '/lib.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Web Push: show a notification even when the app is closed.
self.addEventListener('push', (e) => {
  let d = { title: 'MayBot', body: 'Alert', url: '/' };
  try { d = Object.assign(d, e.data.json()); } catch (_) { if (e.data) d.body = e.data.text(); }
  e.waitUntil(self.registration.showNotification(d.title, { body: d.body, icon: '/icon.svg', badge: '/icon.svg', tag: d.tag, data: { url: d.url } }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
    for (const w of wins) { if ('focus' in w) return w.focus(); }
    return clients.openWindow(url);
  }));
});

// Network-first for GET (except the live API): always try the network and refresh
// the cache; fall back to cache only when offline.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;   // live data: always network
  e.respondWith(
    fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match(e.request).then((hit) => hit || caches.match('/')))
  );
});
