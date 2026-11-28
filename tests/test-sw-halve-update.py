"""Een mislukte update laat de draaiende cache ongemoeid.

Draait via een echte webserver op een kopie van de app.

Mislukt bij een update golf-score.html, dan wordt de update afgebroken. Bijbestanden
die wel binnenkwamen mogen dan niet al in de cache staan waaruit de draaiende versie
bedient: anders loopt de oude app met de bijbestanden van de nieuwe. Dat gebeurt als
CACHE_VERSION niet is verhoogd (dezelfde cache). Events en Trends schrijven pas weg
als het verplichte bestand binnen is; Golf Score doet dat nu ook.

De regels:
  1. Een update met dezelfde cachenaam waarbij golf-score.html mislukt: het icoon in
     de draaiende cache is nog het oude.
  2. De app in die cache is ook nog de oude.
  3. Lukt het daarna wel, dan staan app en icoon van de nieuwe versie er samen in.
"""
import asyncio, os, re, shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_map, zet_cachenaam
BRON = app_map()
fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

MISLUKT = set()   # paden die de server met 500 beantwoordt
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        if self.path.split('?')[0] in MISLUKT:
            self.send_response(500); self.end_headers(); return
        super().do_GET()

def schrijf(wortel, naam, tekst):
    open(os.path.join(wortel, 'golf-score', naam), 'w', encoding='utf-8').write(tekst)
def lees(wortel, naam):
    return open(os.path.join(wortel, 'golf-score', naam), encoding='utf-8').read()

# Wat er in de cache staat, zonder via het netwerk of de worker te gaan.
UIT_CACHE = """async ([cache, pad]) => { const c = await caches.open(cache);
  const r = await c.match(new URL(pad, location.href).href); return r ? await r.text() : null; }"""
STEMPEL = r'Versie [0-9A-Z]+-[0-9A-F]+'

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    sw = lees(wortel, 'sw-golf-score.js')
    schrijf(wortel, 'sw-golf-score.js', zet_cachenaam(sw, 'golf-score-proef-1'))
    schrijf(wortel, 'golf-score.html', re.sub(STEMPEL, 'Versie 13527DA-F01', lees(wortel, 'golf-score.html'), count=1))
    schrijf(wortel, 'icon.svg', '<svg xmlns="http://www.w3.org/2000/svg"><!-- icoon oud --></svg>')
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_port}/golf-score/golf-score.html'
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1200)
        check("vooraf: het oude icoon staat in de cache",
              '<!-- icoon oud -->' in (await pg.evaluate(UIT_CACHE, ['golf-score-proef-1', './icon.svg']) or ''), True)

        print("\n=== 1-2. UPDATE MET DEZELFDE CACHENAAM, golf-score.html MISLUKT ===\n")
        # De worker wijzigt (anders installeert er niets), de cachenaam niet.
        schrijf(wortel, 'sw-golf-score.js', zet_cachenaam(sw, 'golf-score-proef-1') + '\n// proef: andere bytes\n')
        schrijf(wortel, 'icon.svg', '<svg xmlns="http://www.w3.org/2000/svg"><!-- icoon nieuw --></svg>')
        MISLUKT.add('/golf-score/golf-score.html')
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})")
        await pg.wait_for_timeout(4000)
        icoon = await pg.evaluate(UIT_CACHE, ['golf-score-proef-1', './icon.svg']) or ''
        check("het icoon in de draaiende cache is nog het oude", '<!-- icoon oud -->' in icoon, True)
        app = await pg.evaluate(UIT_CACHE, ['golf-score-proef-1', './golf-score.html']) or ''
        check("de app in die cache is ook nog de oude", 'Versie 13527DA-F01' in app, True)

        print("\n=== 3. DAARNA LUKT DE UPDATE WEL ===\n")
        MISLUKT.clear()
        schrijf(wortel, 'sw-golf-score.js', zet_cachenaam(sw, 'golf-score-proef-2'))
        schrijf(wortel, 'golf-score.html', re.sub(STEMPEL, 'Versie 13527DA-F02', lees(wortel, 'golf-score.html'), count=1))
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())")
        await pg.wait_for_timeout(3000)
        app = await pg.evaluate(UIT_CACHE, ['golf-score-proef-2', './golf-score.html']) or ''
        icoon = await pg.evaluate(UIT_CACHE, ['golf-score-proef-2', './icon.svg']) or ''
        check("de nieuwe cache heeft de nieuwe app", 'Versie 13527DA-F02' in app, True)
        check("en het nieuwe icoon", '<!-- icoon nieuw -->' in icoon, True)
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
