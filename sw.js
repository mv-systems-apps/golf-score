// Service worker voor de Golf Score PWA.
// Plaats dit bestand naast golf-score.html in de GitHub Pages-repo.
// CACHE_VERSION wordt afgeleid uit een hash van de app-bestanden door
// update_cache_version.py. Niet handmatig aanpassen.
//
// Let op: dit hóéft NIET bij elke wijziging opnieuw te draaien. De fetch-
// handler hieronder ververst de cache toch al op de achtergrond bij elk
// bezoek (stale-while-revalidate), ongeacht of CACHE_VERSION verandert —
// gebruikers krijgen dus sowieso vanzelf de nieuwste versie, uiterlijk één
// bezoek later. Draai update_cache_version.py alleen wanneer:
//   - er een bestand is toegevoegd/verwijderd uit APP_FILES hieronder, of
//   - je een directe, volledige refresh wilt forceren i.p.v. de geleidelijke
//     achtergrond-verversing.
const CACHE_VERSION = 'golf-score-299628c3c3db';

// Bestanden die offline beschikbaar moeten zijn.
const APP_FILES = [
  './',
  './index.html',
  './golf-score.html',
  './manifest.json',
  './icon.svg',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_VERSION)
      // Per bestand toevoegen is robuuster dan addAll (dat faalt als één bestand ontbreekt).
      .then(c => Promise.all(APP_FILES.map(url => c.add(url).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;

  e.respondWith(
    caches.match(req).then(cached => {
      const network = fetch(req).then(res => {
        // Vernieuw de cache op de achtergrond (alleen geldige, same-origin responses).
        if (res && res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then(c => c.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() => {
        // Offline: val voor paginanavigatie terug op de gecachte app.
        if (req.mode === 'navigate') return caches.match('./golf-score.html');
        return cached;
      });
      return cached || network;
    })
  );
});
