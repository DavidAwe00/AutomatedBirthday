const CACHE_NAME = 'birthday-bot-v3';
const CACHE_URLS = ['/', '/static/css/style.css', '/static/js/app.js', '/static/manifest.json'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});

// ── Push notification handler ─────────────────────────────────────────────────
self.addEventListener('push', event => {
  let data = { title: '🎂 Birthday Bot', body: 'You have a new birthday notification!', url: '/' };
  if (event.data) {
    try { data = { ...data, ...JSON.parse(event.data.text()) }; } catch (_) {}
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      data: { url: data.url },
      requireInteraction: false,
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(wins => {
      const match = wins.find(w => w.url.includes(url));
      if (match) return match.focus();
      return clients.openWindow(url);
    })
  );
});
