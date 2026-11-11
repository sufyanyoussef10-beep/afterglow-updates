// Afterglow for iPhone: keeps the app's own files on the phone, so it opens with no internet.
// (The songs are not here: they are kept by the page itself, in the phone's storage.)
const CACHE = 'afterglow-shell-3';
const FILES = ['./', 'manifest.webmanifest', 'icon-180.png', 'icon-512.png'];
const OWN = FILES.map(f => new URL(f, self.registration.scope).href).concat(new URL('index.html', self.registration.scope).href);

self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Only the app's own few files: the newest from the internet when it answers within 3 seconds, else what was kept.
self.addEventListener('fetch', e => {
  const url = e.request.url.split('?')[0].split('#')[0];
  if (e.request.method !== 'GET' || OWN.indexOf(url) < 0) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const key = url.endsWith('index.html') ? new URL('./', self.registration.scope).href : url;
    const kept = await cache.match(key);
    const fresh = fetch(e.request).then(r => { if (r && r.ok) cache.put(key, r.clone()); return r; });
    if (!kept) return fresh;
    const late = new Promise(res => setTimeout(() => res(kept), 3000));
    return Promise.race([fresh.catch(() => kept), late]);
  })());
});
