// Service worker voor Golf Score: stale-while-revalidate. Meteen uit de eigen
// cache bedienen en op de achtergrond verversen; of er een nieuwe versie is,
// beslist de app zelf (checkAppUpdate, met het versiestempel).
//
// De drie service workers doen hetzelfde, elk in de schrijfstijl van de eigen
// app; de gedeelde regels staan in apps-basis/conventies.md, paragraaf 3.
// Wijzig je hier iets wezenlijks, doe het dan ook daar en in de andere twee.
// Bewust verschil (conventies, paragraaf 4): Golf Score probeert elk bestand bij
// de installatie tot drie keer, omdat een update op de baan bij wisselend bereik
// anders pas bij de volgende opening een nieuwe kans krijgt.
//
// CACHE_VERSION is de teller in de naam van de cache. update_cache_version.py verhoogt hem,
// en dat hoort zodra dit bestand of de lijst met appbestanden wijzigt: anders
// installeert de nieuwe worker in dezelfde cache waaruit de oude nog bedient.
// Het versiestempel in golf-score.html is een eigen teller en gaat met de hand
// omhoog.
//
// Bewuste keuze: de app zelf komt via de achtergrondverversing bij de volgende
// opening binnen, ook zonder tik op de updatemelding; 'jij bepaalt wanneer' geldt
// alleen voor de service worker. Dat kan omdat de scores in de opslag staan en
// elke versie die van de vorige leest (test-backup-overstap.py), de app nooit
// midden in gebruik herlaadt, alle logica in golf-score.html zit en een
// afgebroken download niet in de cache komt.
const CACHE_VERSION = 4;
const CACHE_NAME = 'golf-score-v' + CACHE_VERSION;

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
  // Maskeerbare varianten: randvullend, zonder eigen afronding; Android legt daar zijn
  // eigen vorm overheen. Zonder deze twee toont het opstartscherm het gewone pictogram
  // met witte hoekjes eromheen.
  './icon-maskable-192.png',
  './icon-maskable-512.png',
];

// Zonder dit bestand is er niets om offline te openen, dus dit moet slagen. Lukt het
// niet, dan wordt de update afgebroken: de vorige versie en haar kopie blijven staan,
// en de browser probeert het later vanzelf opnieuw.
const VERPLICHT = ['./golf-score.html'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    // Eerst alles ophalen (per bestand, elk met tot drie pogingen; niet met addAll, dat
    // faalt als één bestand ontbreekt), en pas wegschrijven als het verplichte bestand
    // binnen is. Anders staan bij een afgebroken update de bijbestanden van de nieuwe
    // versie al in de cache, en is CACHE_VERSION niet verhoogd, dan is dat de cache
    // waaruit de draaiende versie bedient. Zo doen Events en Trends het ook.
    const opgehaald = await Promise.all(APP_FILES.map(url => haalMetPogingen(url)));
    const mist = APP_FILES.filter((url, i) => !opgehaald[i]);
    if (mist.some(url => VERPLICHT.includes(url))) {
      throw new Error('Update afgebroken: ' + mist.join(', ') + ' niet opgehaald');
    }
    // Bestond deze cache al, dan is CACHE_VERSION niet verhoogd en bedient de draaiende
    // worker er nog uit: een mislukte installatie wist hem dan niet.
    const bestond = await caches.has(CACHE_NAME);
    const c = await caches.open(CACHE_NAME);
    const zet = (url, res) => c.put(new URL(url, self.location.href).href, res);
    try {
      // Een bijbestand mag ook bij het wegschrijven mislukken (volle opslag); het
      // verplichte bestand niet.
      await Promise.all(APP_FILES.map((url, i) => !opgehaald[i] ? null
        : VERPLICHT.includes(url) ? zet(url, opgehaald[i]) : zet(url, opgehaald[i]).catch(() => null)));
    } catch (fout) {
      // Een cache die hier zelf is aangemaakt, opruimen: anders gaat hij door voor een
      // kopie van de nieuwe versie.
      if (!bestond) await caches.delete(CACHE_NAME).catch(() => {});
      throw fout;
    }
    // Een bijbestand dat niet binnenkwam, overnemen uit de nieuwste vorige eigen cache,
    // zodat het niet ontbreekt. Alleen eigen caches: caches.match() zou ook in die van
    // Events en Trends zoeken.
    if (mist.length) {
      const vorige = (await caches.keys()).filter(k => k.startsWith('golf-score-') && k !== CACHE_NAME).reverse();
      for (const url of mist) {
        const adres = new URL(url, self.location.href).href;
        for (const naam of vorige) {
          const oud = await (await caches.open(naam)).match(adres);
          if (oud) { await c.put(adres, oud); break; }
        }
      }
    }
    // Geen skipWaiting: een nieuwe versie neemt een open app niet vanzelf over. De app
    // meldt de wachtende versie en vraagt pas om de overname als je op die melding tikt;
    // zie de message-handler. Is de app helemaal gesloten, dan neemt de browser de
    // nieuwe versie bij de volgende start zelf in gebruik.
  })());
});

self.addEventListener('message', e => {
  if (e.data && e.data.type === 'nuOverstappen') self.skipWaiting();
  // De app vraagt welke cache bij deze (actieve) service worker hoort, zodat de
  // updatecontrole precies die kopie bekijkt en niet een achtergebleven andere.
  if (e.data && e.data.type === 'welkeCache' && e.ports && e.ports[0]) e.ports[0].postMessage({ cache: CACHE_NAME });
});

async function haalMetPogingen(url, attempts = 3) {
  const adres = new URL(url, self.location.href).href;
  for (let i = 0; i < attempts; i++) {
    // cache: 'reload' zodat de installatie geen verouderde kopie uit de browsercache
    // overneemt: GitHub Pages laat een bestand 10 minuten bewaren. Elke poging heeft de
    // grens van 10 s, zodat een hangende verbinding de installatie niet eindeloos ophoudt;
    // zolang die loopt, doet registration.update() niets. Drie pogingen zijn hooguit
    // zo'n 30 s.
    try {
      const h = haalMetStop(adres, { cache: 'reload' });
      // De inhoud meteen helemaal lezen, binnen dezelfde grens: er wordt pas
      // weggeschreven als alles binnen is, en een antwoord waarvan de inhoud nog niet
      // gelezen is houdt een verbinding bezet. De browser opent er maar een paar per
      // server, dus de laatste bestanden zouden dan op de grens wachten.
      const res = await metGrens(h.belofte.then(async r => (!r || !r.ok) ? r
        : new Response(await r.blob(), { status: r.status, statusText: r.statusText, headers: r.headers })),
        GRENS, h.stop);
      if (!res || !res.ok) throw new Error('status ' + (res && res.status));
      return res;
    }
    catch (e) { /* opnieuw proberen; na de laatste poging beslist de installatie */ }
  }
  return null;
}

// ── Welke verzoeken zijn van deze app ──────────────────────────────────────
// Alleen de bestanden uit APP_FILES worden uit de cache beantwoord en bewaard, altijd onder
// hun pad zonder zoekstring: anders krijgt elk adres met een zoekstring (een gedeelde link,
// ?verversen) een eigen kopie van de hele app, die daarna veroudert.
const EIGEN_PADEN = new Set(APP_FILES.map(u => new URL(u, self.location.href).pathname));
const APP_SLEUTEL = new URL('./golf-score.html', self.location.href).href;
function sleutel(url) { return url.origin + url.pathname; }
// Alleen uit de eigen cache van deze versie lezen. caches.match() zoekt in alle caches
// van de origin (ook die van Events en Trends), en terwijl een nieuwe versie wacht ook
// in de hare: dan zouden twee versies door elkaar lopen.
function uitEigenCache(adres) {
  return caches.open(CACHE_NAME).then(c => c.match(adres)).catch(() => undefined);
}

// Drie uiterste wachttijden, naar de rol van het verzoek; bij de grens wordt het verzoek
// echt afgebroken (zie metGrens).
// - GRENS: een cachemisser; dan is dit verzoek het antwoord. Ook elke ophaalpoging van de
//   installatie.
// - GRENS_MET_APP: een paginaverzoek mist de cache terwijl de app wel bewaard is. Lang
//   wachten koopt dan niets: liever na 3 s de bewaarde app.
const GRENS = 10000;
const GRENS_MET_APP = 3000;
// - GRENS_ACHTERGROND: een cachetreffer. Het antwoord is al gegeven en dit verzoek ververst
//   alleen de kopie, dus die mag ruim, maar niet eindeloos: een hangende verbinding houdt
//   anders een van de weinige verbindingen per server bezet, en dan wachten ook latere
//   verzoeken.
const GRENS_ACHTERGROND = 60000;

// Het netwerk met een uiterste grens. Bij de grens wordt het verzoek echt afgebroken en
// niet alleen losgelaten; anders houdt het een verbinding bezet terwijl niemand meer op
// het antwoord wacht.
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
// uitleg, voor de rest een lege foutcode. Anders toont de browser een netwerkfout zonder
// uitleg.
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

// Zeggen dat er een verse kopie van de pagina in de cache staat. De app kijkt ook zelf
// (4 s na de start), maar dan is de verversing op mobiel bereik vaak nog onderweg; zonder
// dit bericht komt de melding pas bij het wegschakelen en terughalen van de app.
function meldVerversing() {
  if (!self.clients || typeof self.clients.matchAll !== 'function') return;
  self.clients.matchAll({ type: 'window' }).then(lijst => {
    for (const c of lijst) { try { c.postMessage({ type: 'kopieVernieuwd' }); } catch (f) { /* weg is weg */ } }
  }).catch(() => { /* niets aan te doen */ });
}

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    // Alle apps op deze origin (mv-systems-apps.github.io/<app>/) delen dezelfde
    // cacheopslag: alleen eigen oude caches opruimen. Pas bij activeren, zodat de vorige
    // cache blijft staan tot de nieuwe versie het werkelijk overneemt.
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('golf-score-') && k !== CACHE_NAME).map(k => caches.delete(k)));
    // Kopieën onder een adres met zoekstring opruimen; die kunnen van oudere versies zijn.
    try {
      const c = await caches.open(CACHE_NAME);
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
  // (een andere pagina, een andere app): laten gaan alsof er geen service worker is.
  if (!EIGEN_PADEN.has(url.pathname)) return;

  // Een verzoek dat uitdrukkelijk vers wil (de app haalt zo een actuele kopie op met
  // ?verversen): altijd het netwerk, nooit de cache, niets bewaren. Wel met een grens,
  // zodat de app bij slecht bereik na 10 s 'Geen verbinding' kan melden, en zonder
  // netwerk een foutcode in plaats van de oude kopie.
  if (!navigatie && (req.cache === 'reload' || req.cache === 'no-store')) {
    const v = haalMetStop(req);
    e.respondWith(metGrens(v.belofte, GRENS, v.stop).catch(() => offlineAntwoord(false)));
    return;
  }
  // Eerst de eigen cache, dan het netwerk: zo weet het verzoek welke rol het heeft. Bij een
  // treffer is het alleen de achtergrondverversing (ruime grens, de pagina met no-cache);
  // bij een misser het antwoord zelf (10 s, of 3 s als de bewaarde app klaarstaat).
  //
  // Deze waitUntil moet nu al, tijdens het afhandelen van het event, worden aangemeld; de
  // belofte wordt later ingevuld. Hij omvat het ophalen en het wegschrijven, zodat de
  // browser de worker niet stopt voordat de nieuwe kopie in de cache staat.
  let achtergrondKlaar;
  e.waitUntil(new Promise(r => { achtergrondKlaar = r; }));

  e.respondWith((async () => {
    try {
      const cached = await uitEigenCache(sleutel(url));
      const app = (!cached && navigatie) ? await uitEigenCache(APP_SLEUTEL) : undefined;
      const grens = cached ? GRENS_ACHTERGROND : (app ? GRENS_MET_APP : GRENS);
      // Altijd het adres zonder zoekstring, zodat er geen tweede kopie onder een ander adres
      // komt. Bij een cachetreffer op de pagina met no-cache: GitHub Pages laat een bestand
      // 10 minuten bewaren, en een gewoon verzoek kan dan dezelfde oude bytes terugschrijven,
      // waardoor de melding van een nieuwe versie vlak na een push uitblijft. Alleen de
      // pagina: daar staat het stempel.
      const h = haalMetStop(sleutel(url), (cached && navigatie) ? { cache: 'no-cache' } : {});
      let kopie = null;
      const netwerk = metGrens(h.belofte, grens, h.stop).then(res => {
        if (res && res.ok && res.type === 'basic') kopie = res.clone();
        return res;
      });
      achtergrondKlaar(netwerk.then(() => kopie && caches.open(CACHE_NAME)
        .then(c => c.put(sleutel(url), kopie))
        .then(() => { if (navigatie) meldVerversing(); }), () => {}).catch(() => {}));

      if (cached) return cached;                      // direct, zonder op het netwerk te wachten
      try {
        const res = await netwerk;
        if (res && res.ok) return res;
        if (!app && res) return res;                  // bijv. een echte 404 van de server
      } catch (f) { /* geen of te traag netwerk */ }
      return app || offlineAntwoord(navigatie);
    } catch (f) {
      return offlineAntwoord(navigatie);              // cacheopslag stuk of geweigerd
    } finally {
      achtergrondKlaar();                             // een ingevulde belofte blijft staan
    }
  })());
});
