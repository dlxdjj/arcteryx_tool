const V = 'v1';
const STATIC = ['index.html', 'manifest.json', 'icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(STATIC).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== V).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = e.request.url;
  // results.json 和汇率 API 始终走网络，离线时回退缓存
  if (url.includes('results.json') || url.includes('frankfurter') || url.includes('fonts.')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
