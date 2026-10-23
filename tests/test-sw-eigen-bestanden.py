"""Service worker: alleen eigen bestanden, zonder dubbele kopieën, nooit eindeloos wachten.

Draait de app via een echte webserver op een kopie van 'uit' (Cache-Control zoals GitHub
Pages). 'Slecht bereik' is een server die de verbinding aanneemt maar nooit antwoordt;
'geen bereik' is een server die weg is.

Tot 13527DA-139:
  * kreeg elk adres met een toevoeging achter het vraagteken (een gedeelde link,
    ?verversen) een eigen kopie van de hele app in de cache, die daarna verouderde;
  * wachtte een bestand of pagina die niet in de cache stond op een netwerk dat niet
    antwoordde, tot de browser zelf opgaf (minuten);
  * kreeg de browser niets terug als netwerk en cache allebei niets hadden.

De regels:
  1. De cache bevat alleen de appbestanden, elk één keer, onder het pad zonder toevoeging.
  2. Een verzoek dat vers wil (?verversen) gaat naar het netwerk en wordt niet bewaard;
     bij slecht bereik volgt na hooguit 10 seconden een foutcode.
  3. Een eigen pagina die niet in de cache staat: hooguit 3 seconden wachten, dan de bewaarde app.
     Is die er ook niet, dan een offlinepagina.
  4. Een appbestand dat in de cache ontbreekt: hooguit 10 seconden wachten, dan een
     foutcode; zonder bereik meteen.
  5. Op de achtergrond komt een nieuwe app in de cache terwijl de bewaarde direct opent.
"""
import asyncio, os, re, shutil, sys, tempfile, threading, time
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

M = {'hangt': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-cache'); super().end_headers()
    def do_GET(self):
        if M['hangt']:
            # blijft hangen tot de proef de storing opheft; dan valt de verbinding weg
            for _ in range(400):
                if not M['hangt']: return
                time.sleep(0.1)
            return
        super().do_GET()

SLEUTELS = """async () => { const n = (await caches.keys()).filter(k => k.startsWith('golf-score-'))[0];
  return (await (await caches.open(n)).keys()).map(r => r.url.replace(location.origin + '/golf-score/', '')).sort(); }"""
VRAAG = """async (pad) => { const t = performance.now(); const c = new AbortController(); setTimeout(() => c.abort(), 25000);
  try { const r = await fetch(pad, { signal: c.signal }); return ['status ' + r.status, Math.round((performance.now() - t) / 1000)]; }
  catch (e) { return [e.name, Math.round((performance.now() - t) / 1000)]; } }"""
VERS = VRAAG.replace("{ signal: c.signal }", "{ signal: c.signal, cache: 'reload' }")

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    basis = f'http://127.0.0.1:{srv.server_port}/golf-score/'

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(basis + 'golf-score.html'); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1500)
        await pg.reload(); await pg.wait_for_timeout(500)   # nu bestuurd door de service worker
        verwacht = sorted(await pg.evaluate(SLEUTELS))

        print("\n=== 1. GEEN DUBBELE KOPIEËN ===\n")
        for q in ('golf-score.html?fbclid=1', 'golf-score.html?fbclid=2', 'golf-score.html?opslag=hoofd', '?utm=x'):
            p2 = await ctx.new_page(); await p2.goto(basis + q); await p2.wait_for_timeout(600); await p2.close()
        await pg.evaluate(VERS, './golf-score.html?verversen'); await pg.wait_for_timeout(500)
        sl = await pg.evaluate(SLEUTELS)
        check("de cache bevat alleen de appbestanden, elk één keer", (sl, any('?' in k for k in sl)), (verwacht, False))
        check("golf-score.html staat erin", 'golf-score.html' in sl, True)

        print("\n=== 2-4. SLECHT BEREIK ===\n")
        await pg.evaluate("async () => { for (const n of await caches.keys()) if (n.startsWith('golf-score-')) { const c = await caches.open(n); await c.delete('./icon-512.png'); await c.delete('./index.html'); } }")
        M['hangt'] = True
        r = await pg.evaluate(VERS, './golf-score.html?verversen')
        check("?verversen bij slecht bereik: foutcode binnen 11 s", (r[0], r[1] <= 11), ('status 503', True))
        r = await pg.evaluate(VRAAG, './icon-512.png')
        check("ontbrekend appbestand bij slecht bereik: foutcode binnen 11 s", (r[0], r[1] <= 11), ('status 503', True))
        p3 = await ctx.new_page(); t = time.time()
        try: await p3.goto(basis + 'index.html', timeout=15000); uit = (await p3.evaluate("!!document.getElementById('appVersionStamp')"), round(time.time() - t) <= 5)
        except Exception: uit = ('opent niet', False)
        check("eigen pagina buiten de cache bij slecht bereik: binnen 5 s de bewaarde app", uit, (True, True)); await p3.close()
        p4 = await ctx.new_page(); t = time.time(); await p4.goto(basis + 'golf-score.html?x=1', timeout=8000)
        check("de app via een adres met toevoeging opent direct", (await p4.evaluate("!!document.getElementById('appVersionStamp')"), round(time.time() - t) <= 2), (True, True)); await p4.close()

        print("\n=== 3-4. GEEN BEREIK ===\n")
        M['hangt'] = False; await asyncio.sleep(0.5); srv.shutdown(); srv.server_close()
        r = await pg.evaluate(VRAAG, './icon-512.png')
        check("ontbrekend appbestand zonder bereik: meteen een foutcode", (r[0], r[1] <= 1), ('status 503', True))
        await pg.evaluate("async () => { for (const n of await caches.keys()) if (n.startsWith('golf-score-')) await (await caches.open(n)).delete('./golf-score.html'); }")
        p5 = await ctx.new_page(); await p5.goto(basis + 'index.html', timeout=8000)
        check("zonder bereik en zonder bewaarde app: een offlinepagina", (await p5.title(), 'offline' in (await p5.inner_text('body')).lower()), ('Golf Score offline', True))
        await b.close()

        print("\n=== 5. ACHTERGRONDVERVERSING ===\n")
        wortel2 = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel2, 'golf-score'))
        srv2 = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel2)); srv2.daemon_threads = True
        threading.Thread(target=srv2.serve_forever, daemon=True).start()
        basis2 = f'http://127.0.0.1:{srv2.server_port}/golf-score/'
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(basis2 + 'golf-score.html'); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1500)
        pad = os.path.join(wortel2, 'golf-score', 'golf-score.html'); s = open(pad, encoding='utf-8').read()
        open(pad, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', 'Versie 13527DA-FFF', s))
        t = time.time(); await pg.reload(); await pg.wait_for_timeout(300)
        check("de bewaarde app opent direct", (await pg.evaluate("document.getElementById('appVersionStamp').textContent") != 'Versie 13527DA-FFF', round(time.time() - t) <= 2), (True, True))
        await pg.wait_for_timeout(2000)
        v = await pg.evaluate("async () => { const r = await caches.match('./golf-score.html'); return (await r.text()).match(/Versie ([0-9A-F]+-[0-9A-F]+)/)[1]; }")
        check("op de achtergrond staat de nieuwe app in de cache", v, '13527DA-FFF')
        await b.close(); srv2.shutdown(); srv2.server_close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
