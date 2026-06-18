// Network-first for HTML navigation — always fetches fresh index.html
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener('fetch', e => {
  if(e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request.url, {cache: 'no-store'}).catch(() => caches.match(e.request))
    );
  }
});
