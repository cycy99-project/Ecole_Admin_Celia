// Service Worker minimaliste pour l'installabilité PWA
// Stratégie : network-first pour HTML, cache-first pour les assets statiques.

const CACHE_VERSION = 'rdv-ecole-v1';
const STATIC_ASSETS = [
    '/static/style.css',
    '/static/app.js',
    '/static/icon.svg',
    '/static/manifest.webmanifest',
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_VERSION).then(function (cache) {
            return cache.addAll(STATIC_ASSETS).catch(function () { /* tolérant */ });
        }).then(function () {
            return self.skipWaiting();
        })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE_VERSION; })
                    .map(function (k) { return caches.delete(k); })
            );
        }).then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    const request = event.request;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    // Assets statiques : cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then(function (cached) {
                return cached || fetch(request).then(function (resp) {
                    if (resp.ok) {
                        const copy = resp.clone();
                        caches.open(CACHE_VERSION).then(function (cache) { cache.put(request, copy); });
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // Pages HTML : network-first, fallback cache
    if (request.headers.get('accept') && request.headers.get('accept').indexOf('text/html') !== -1) {
        event.respondWith(
            fetch(request).catch(function () {
                return caches.match(request) || caches.match('/');
            })
        );
        return;
    }
});
