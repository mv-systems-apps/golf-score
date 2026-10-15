"""De updatecontrole bekijkt precies de cache van de actieve service worker.

Draait via een echte webserver op een kopie van 'uit'.

Tot 13527DA-13C nam de updatecontrole de eerste Golf Score-cache met golf-score.html,
in de volgorde waarin de caches zijn aangemaakt. In gewone standen is dat de actieve.
Blijft er na een afgebroken opruimactie een oudere cache staan die vóór de actieve komt,
dan meldde de balk ten onrechte 'Verouderde kopie'.

De regels:
  1. Eén cache, geen update: geen balk.
  2. Een achtergebleven oudere cache vóór de actieve: geen balk.
  3. Een nieuwe versie die wacht: de balk meldt een nieuwe versie.
  4. Een nieuwe app in de actieve cache (achtergrondverversing): de balk meldt hem.
"""
import asyncio, os, re, shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)

sys.path.insert(0, HIER); from testdata import app_map
BRON = app_map()  # werkmap: 'uit'; in de repository: de app naast tests/
fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()

def zet_versie(wortel, cache, label):
    p = os.path.join(wortel, 'golf-score', 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r"const CACHE_VERSION = '[^']*';", f"const CACHE_VERSION = '{cache}';", s))
    p = os.path.join(wortel, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

BALK = """async () => { const b = document.getElementById('updateBanner'); b.classList.add('hidden'); b.textContent = ''; delete b.dataset.ouder;
  const reg = await navigator.serviceWorker.getRegistration(); if (reg.waiting && navigator.serviceWorker.controller) toonWachtendeUpdate();
  await checkAppUpdate(); return b.classList.contains('hidden') ? '' : b.textContent; }"""
# Een achtergebleven oudere cache die VÓÓR de actieve staat: de actieve wordt opnieuw
# aangemaakt met dezelfde inhoud, zodat de restcache in de volgorde eerst komt.
REST_VOOR_ACTIEF = """async () => { const actief = (await caches.keys()).find(n => n.startsWith('golf-score-'));
  await (await caches.open('golf-score-rest')).put('./golf-score.html', new Response('<b>Versie 13527DA-F00</b>'));
  const c = await caches.open(actief); const inhoud = [];
  for (const req of await c.keys()) inhoud.push([req, await c.match(req)]);
  await caches.delete(actief); const nieuw = await caches.open(actief);
  for (const [req, res] of inhoud) await nieuw.put(req, res);
  return (await caches.keys()).filter(n => n.startsWith('golf-score-')); }"""

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    zet_versie(wortel, 'golf-score-proef-1', '13527DA-F01')
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_port}/golf-score/golf-score.html'
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1200); await pg.reload(); await pg.wait_for_timeout(600)

        print("\n=== 1. EÉN CACHE ===\n")
        check("geen balk", await pg.evaluate(BALK), '')

        print("\n=== 2. ACHTERGEBLEVEN OUDERE CACHE VÓÓR DE ACTIEVE ===\n")
        check("de restcache staat vooraan", await pg.evaluate(REST_VOOR_ACTIEF), ['golf-score-rest', 'golf-score-proef-1'])
        check("toch geen balk", await pg.evaluate(BALK), '')
        await pg.evaluate("() => caches.delete('golf-score-rest')")

        print("\n=== 3. EEN NIEUWE VERSIE WACHT ===\n")
        zet_versie(wortel, 'golf-score-proef-2', '13527DA-F02')
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())"); await pg.wait_for_timeout(2500)
        check("de balk meldt een nieuwe versie", (await pg.evaluate(BALK)).startswith('Nieuwe versie'), True)

        print("\n=== 4. NIEUWE APP IN DE ACTIEVE CACHE (ACHTERGRONDVERVERSING) ===\n")
        await pg.reload(); await pg.wait_for_timeout(1500)
        check("de balk noemt de nieuwe versie", await pg.evaluate(BALK), 'Nieuwe versie (13527DA-F02) beschikbaar — tik om te verversen')
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
