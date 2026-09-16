const CACHE_NAME = 'guardain-pwa-v2';
const OFFLINE_FALLBACK = {
  status: 'offline',
  message: 'Offline mode active. Connection restored when the network is available.'
};

const APP_ASSETS = ['./', './index.html', './manifest.json', './sw.js'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_ASSETS)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && (response.status === 200 || response.type === 'opaque')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(async () => {
        const cacheResponse = await caches.match(request);
        if (cacheResponse) {
          return cacheResponse;
        }

        if (request.mode === 'navigate') {
          return caches.match('./index.html');
        }

        return new Response(JSON.stringify(OFFLINE_FALLBACK), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      })
  );
});
