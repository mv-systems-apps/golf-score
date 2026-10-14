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
//
// BEWUSTE KEUZE (12-10-2026, versie 13527DA-13C): stale-while-revalidate blijft.
// Gevolg, geaccepteerd: de app zelf (golf-score.html) komt via de achtergrondverversing
// bij de volgende opening binnen, ook zonder tik op de updatemelding. 'Jij bepaalt
// wanneer' geldt alleen voor de service worker. Afgewogen:
//   - scores staan in de opslag, niet in de app; elke versie leest die van de vorige
//     (test-backup-overstap.py), dus een nieuwe app tijdens een ronde kost niets;
//   - de app herlaadt nooit midden in gebruik, alleen bij het openen;
//   - een nieuwe pagina met de oude service worker of oude pictogrammen botst in de
//     praktijk niet: alle logica zit in golf-score.html;
//   - een afgebroken download komt niet in de cache;
//   - kosten: zo'n 280 KB per opening met bereik.
// Het alternatief (geen achtergrondverversing; de app alleen via de wachtende update)
// is besproken en bewust niet gekozen.
const CACHE_VERSION = 'golf-score-a7473fd37b1f';

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
    // Bestond deze cache al (zelfde versie opnieuw geïnstalleerd), dan wordt hij bij een
    // mislukking niet weggegooid: dan is het de kopie waar de app op draait.
    const bestond = await caches.has(CACHE_VERSION);
    const c = await caches.open(CACHE_VERSION);
    // Per bestand toevoegen is robuuster dan addAll (dat faalt als één bestand ontbreekt).
    // Bij falen een paar keer opnieuw proberen.
    const gelukt = await Promise.all(APP_FILES.map(url => addWithRetry(c, url)));
    const mist = APP_FILES.filter((url, i) => !gelukt[i]);
    if (mist.some(url => VERPLICHT.includes(url))) {
      // Geen half gevulde cache achterlaten: die gaat anders tot de volgende geslaagde
      // update door voor een kopie van de nieuwe versie.
      if (!bestond) await caches.delete(CACHE_VERSION).catch(() => {});
      throw new Error('Update afgebroken: ' + mist.join(', ') + ' niet opgehaald');
    }
    // Een pictogram of ander bijbestand dat niet lukte: overnemen uit een vorige kopie van
    // Golf Score (de nieuwste eerst), zodat het niet ontbreekt. Uitdrukkelijk alleen uit
    // eigen caches: caches.match() zou ook in die van Events en Trends zoeken.
    if (mist.length) {
      const vorige = (await caches.keys()).filter(k => k.startsWith('golf-score-') && k !== CACHE_VERSION).reverse();
      for (const url of mist) {
        const adres = new URL(url, self.location.href).href;
        for (const naam of vorige) {
          const oud = await (await caches.open(naam)).match(adres);
          if (oud) { await c.put(adres, oud); break; }
        }
      }
    }
    // Geen skipWaiting: een nieuwe versie neemt een open app niet vanzelf over. De app
    // meldt dat er een nieuwe versie klaarstaat en vraagt pas om de overname als je op
    // die melding tikt (zie de message-handler hieronder). Is de app helemaal gesloten,
    // dan neemt de browser de nieuwe versie bij de volgende start zelf in gebruik.
  })());
});

self.addEventListener('message', e => {
  if (e.data && e.data.type === 'nuOverstappen') self.skipWaiting();
  // De app vraagt welke cache bij deze (actieve) service worker hoort, zodat de
  // updatecontrole precies die kopie bekijkt en niet een achtergebleven andere.
  if (e.data && e.data.type === 'welkeCache' && e.ports && e.ports[0]) e.ports[0].postMessage({ cache: CACHE_VERSION });
});

async function addWithRetry(cache, url, attempts = 3) {
  for (let i = 0; i < attempts; i++) {
    // cache: 'reload' slaat de browsercache over. GitHub Pages laat een bestand 10 minuten
    // bewaren; zonder dit kreeg een update binnen die tijd de vorige golf-score.html mee.
    try { await cache.add(new Request(url, { cache: 'reload' })); return true; }
    catch (e) { /* opnieuw proberen; na de laatste poging beslist de installatie */ }
  }
  return false;
}

// ── Welke verzoeken zijn van deze app ──────────────────────────────────────
// Alleen de bestanden uit APP_FILES worden uit de cache beantwoord en bewaard, en altijd
// onder hun pad ZONDER toevoeging achter het vraagteken. Voorheen kreeg elk adres met een
// toevoeging (een gedeelde link, ?verversen) een eigen kopie van de hele app in de cache,
// telkens zo'n 1 MB, die daarna verouderde.
const EIGEN_PADEN = new Set(APP_FILES.map(u => new URL(u, self.location.href).pathname));
const APP_SLEUTEL = new URL('./golf-score.html', self.location.href).href;
function sleutel(url) { return url.origin + url.pathname; }
// Alleen uit de eigen cache van deze versie lezen. caches.match() zoekt in alle caches
// van de origin (ook die van Events en Trends), en terwijl een nieuwe versie wacht ook
// in de hare: dan zouden twee versies door elkaar lopen.
function uitEigenCache(adres) {
  return caches.open(CACHE_VERSION).then(c => c.match(adres)).catch(() => undefined);
}

// Hoe lang er op het netwerk gewacht wordt als de cache een bestand niet heeft. Bij een
// treffer wordt nooit gewacht. Een pagina wacht korter als de bewaarde app klaarstaat.
const GRENS = 10000;
const GRENS_MET_APP = 3000;
// Een verversing op de achtergrond mag langer duren (een trage maar werkende verbinding),
// maar niet eindeloos: een verbinding die blijft hangen houdt anders een van de weinige
// verbindingen per server bezet, en dan wachten ook latere verzoeken.
const GRENS_ACHTERGROND = 60000;

// Ophalen met een stopknop: bij het verstrijken van een grens wordt het verzoek echt
// afgebroken, zodat de verbinding vrijkomt.
function haalMetStop(invoer, opties = {}) {
  const stop = new AbortController();
  return { stop, belofte: fetch(invoer, Object.assign({}, opties, { signal: stop.signal })) };
}
function metGrens(belofte, ms, stop) {
  return new Promise((klaar, mis) => {
    const klok = setTimeout(() => { if (stop) stop.abort(); mis(new Error('netwerk duurde langer dan ' + ms + ' ms')); }, ms);
    belofte.then(r => { clearTimeout(klok); klaar(r); }, f => { clearTimeout(klok); mis(f); });
  });
}

// Een geldig antwoord als netwerk en cache allebei niets hebben: voor een pagina een korte
// uitleg, voor de rest een lege foutcode. Voorheen kreeg de browser niets terug en toonde
// hij een netwerkfout zonder uitleg.
function offlineAntwoord(navigatie) {
  if (!navigatie) return new Response('', { status: 503, statusText: 'offline' });
  return new Response('<!doctype html><html lang="nl"><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Golf Score offline</title>'
    + '<body style="font:18px system-ui;margin:2rem;background:#1a3a2a;color:#e8e8e8">'
    + '<h1 style="font-size:1.3rem;color:#c9a84c">Golf Score is offline</h1>'
    + '<p>Deze pagina staat niet in de offline-kopie en er is geen verbinding. '
    + 'Open de app via het pictogram op je beginscherm, of probeer het opnieuw met bereik.</p>',
    { status: 503, statusText: 'offline', headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    // Alleen eigen oude caches: andere apps op dezelfde origin (GitHub Pages:
    // mv-systems-apps.github.io/<app>/) delen dezelfde cacheopslag.
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('golf-score-') && k !== CACHE_VERSION).map(k => caches.delete(k)));
    // Kopieën onder een adres met toevoeging (uit eerdere versies) opruimen.
    try {
      const c = await caches.open(CACHE_VERSION);
      for (const req of await c.keys()) if (new URL(req.url).search) await c.delete(req);
    } catch (f) { /* opruimen is gemak; de app werkt ook zonder */ }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch (f) { return; }
  if (url.origin !== self.location.origin) return;
  const navigatie = req.mode === 'navigate';
  // Alleen de eigen bestanden van Golf Score, ook bij een navigatie. Al het andere
  // (een andere pagina, een andere app) gaat ongemoeid naar het netwerk.
  if (!EIGEN_PADEN.has(url.pathname)) return;

  // Een verzoek dat uitdrukkelijk vers wil (de app haalt zo een actuele kopie op met
  // ?verversen): altijd het netwerk, nooit de cache, niets bewaren. Wel met een grens,
  // zodat de app bij slecht bereik na 10 seconden 'Geen verbinding' kan melden.
  if (!navigatie && (req.cache === 'reload' || req.cache === 'no-store')) {
    const v = haalMetStop(req);
    e.respondWith(metGrens(v.belofte, GRENS, v.stop).catch(() => offlineAntwoord(false)));
    return;
  }
  // De achtergrondverversing loopt via waitUntil, zodat de browser de service worker niet
  // stopt voordat de nieuwe kopie in de cache staat.
  let ververst = Promise.resolve();
  // (Altijd het adres zonder toevoeging: een paginaverzoek zelf kan niet met een stopknop
  // worden nagemaakt, en zo komt er geen tweede kopie onder een ander adres.)
  const h = haalMetStop(sleutel(url));
  const achtergrondKlok = setTimeout(() => h.stop.abort(), GRENS_ACHTERGROND);
  const netwerk = h.belofte.then(res => {
    clearTimeout(achtergrondKlok);
    if (res && res.ok && res.type === 'basic') {
      const kopie = res.clone();
      ververst = caches.open(CACHE_VERSION).then(c => c.put(sleutel(url), kopie)).catch(() => {});
    }
    return res;
  });
  e.waitUntil(netwerk.then(() => ververst, () => {}));

  e.respondWith((async () => {
    const cached = await uitEigenCache(sleutel(url));
    if (cached) return cached;                      // direct, zonder op het netwerk te wachten
    const app = navigatie ? await uitEigenCache(APP_SLEUTEL) : undefined;
    try {
      const res = await metGrens(netwerk, app ? GRENS_MET_APP : GRENS, h.stop);
      if (res && res.ok) return res;
      if (!app && res) return res;                  // bijv. een echte 404 van de server
    } catch (f) { /* geen of te traag netwerk */ }
    return app || offlineAntwoord(navigatie);
  })());
});
