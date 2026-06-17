// v200 — force-bust mlb-v152 stale cache
const CACHE = "mlb-v200";
const SHELL = ["./", "./index.html", "./manifest.json", "./icon.svg"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  // JSON data files: network first, graceful cache fallback
  if (url.pathname.endsWith(".json")) {
    e.respondWith(
      fetch(e.request, {cache: "no-store"})
        .then(res => {
          if (res.ok) {
            caches.open(CACHE).then(c => c.put(e.request, res.clone()));
          }
          return res;
        })
        .catch(() =>
          caches.match(e.request).then(cached =>
            cached || new Response(
              '{"picks":[],"stats":{},"recent_history":[],"live_games":[]}',
              {status: 200, headers: {"Content-Type": "application/json"}}
            )
          )
        )
    );
    return;
  }

  // App shell: network first (so HTML updates are always received)
  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (res.ok) caches.open(CACHE).then(c => c.put(e.request, res.clone()));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
