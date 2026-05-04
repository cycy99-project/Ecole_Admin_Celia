// Service Worker minimaliste & robuste pour l'installabilité PWA.
//
// Stratégie volontairement minimale pour éviter tout écran noir / page blanche
// (notamment sur iOS Safari, plus strict que Chrome) :
// - On NE TOUCHE PAS aux requêtes HTML : le navigateur s'en charge nativement
//   (réseau direct + cache navigateur natif). Aucun risque que le SW renvoie
//   une réponse undefined.
// - On cache uniquement les assets statiques (style.css, app.js, icônes…) en
//   stratégie stale-while-revalidate.
//
// Un SW présent + manifest valide suffit pour rendre l'app installable.

const CACHE_VERSION = 'rdv-ecole-v3';
const STATIC_ASSETS = [
    '/static/style.css',
    '/static/app.js',
    '/static/icon.svg',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/manifest.webmanifest',
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_VERSION)
            .then(function (cache) { return cache.addAll(STATIC_ASSETS).catch(function () {}); })
            .then(function () { return self.skipWaiting(); })
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

    let url;
    try { url = new URL(request.url); } catch (e) { return; }

    // On n'intercepte QUE les assets sous /static/ (origine same-origin).
    if (url.origin !== self.location.origin) return;
    if (!url.pathname.startsWith('/static/')) return;

    event.respondWith(
        caches.match(request).then(function (cached) {
            const fetchPromise = fetch(request).then(function (resp) {
                if (resp && resp.ok) {
                    const copy = resp.clone();
                    caches.open(CACHE_VERSION).then(function (cache) { cache.put(request, copy); });
                }
                return resp;
            }).catch(function () {
                // Si offline et pas en cache : laisser le navigateur gérer (sera une erreur réseau classique, pas écran noir).
                return cached || Response.error();
            });
            return cached || fetchPromise;
        })
    );
});
