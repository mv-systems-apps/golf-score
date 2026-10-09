// Service worker voor de Golf Score PWA.
// Plaats dit bestand als sw-golf-score.js naast golf-score.html in de GitHub
// Pages-repo. De bestandsnaam bevat de app, zodat meerdere apps in dezelfde repo
// elkaars service worker niet overschrijven.
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
const CACHE_VERSION = 'golf-score-e021887739c0';

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
  // Maskeerbare varianten: randvullend, zonder eigen afronding. Android legt daar zijn
  // eigen vorm overheen. Zonder deze twee toonde het opstartscherm het gewone pictogram
  // ongemaskeerd, met witte hoekjes eromheen.
  './icon-maskable-192.png',
  './icon-maskable-512.png',
];

// Zonder deze bestanden opent de app niet. Lukt het ophalen daarvan niet, dan wordt de
// update afgebroken: de vorige versie en haar kopie blijven staan, en de browser probeert
// het later vanzelf opnieuw. Voorheen ging de update toch door en verdween de oude
// kopie; bij slecht bereik op de baan opende de app daarna offline niet meer.
const VERPLICHT = ['./golf-score.html'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE_VERSION);
    // Per bestand toevoegen is robuuster dan addAll (dat faalt als één bestand ontbreekt).
    // Bij falen een paar keer opnieuw proberen.
    const gelukt = await Promise.all(APP_FILES.map(url => addWithRetry(c, url)));
    const mist = APP_FILES.filter((url, i) => !gelukt[i]);
    if (mist.some(url => VERPLICHT.includes(url))) {
      throw new Error('Update afgebroken: ' + mist.join(', ') + ' niet opgehaald');
    }
    // Een pictogram of ander bijbestand dat niet lukte: overnemen uit de vorige kopie,
    // zodat het niet ontbreekt. De achtergrondverversing haalt later de nieuwe op.
    for (const url of mist) {
      const oud = await caches.match(url);
      if (oud) await c.put(url, oud);
    }
    await self.skipWaiting();
  })());
});

async function addWithRetry(cache, url, attempts = 3) {
  for (let i = 0; i < attempts; i++) {
    try { await cache.add(url); return true; }
    catch (e) { /* opnieuw proberen; na de laatste poging beslist de installatie */ }
  }
  return false;
}

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      // Alleen eigen oude caches: andere apps op dezelfde origin (GitHub Pages:
      // mv-systems-apps.github.io/<app>/) delen dezelfde cacheopslag.
      .then(keys => Promise.all(keys.filter(k => k.startsWith('golf-score-') && k !== CACHE_VERSION).map(k => caches.delete(k))))
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
