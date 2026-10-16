"""Een update installeert altijd de nieuwe app, en laat bij mislukken niets half achter.

Draait de app via een echte webserver op een kopie van 'uit', met dezelfde kopregel als
GitHub Pages: de browser mag een bestand 10 minuten bewaren (Cache-Control: max-age=600).

Tot 13527DA-138:
  1. haalde de installatie van een nieuwe versie golf-score.html op via die browseropslag.
     Een update binnen 10 minuten na het openen kreeg zo de VORIGE app in de cache van de
     nieuwe versie, en na herladen draaide nog steeds de oude;
  2. bleef bij een mislukte update (golf-score.html komt niet binnen) een half gevulde
     cache van de nieuwe versie staan.

De regel: een nieuwe versie bevat altijd haar eigen app, en een mislukte update laat de
opslag precies zoals hij was. De vorige kopie blijft in beide gevallen werken.
"""
import asyncio, os, re, shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)

sys.path.insert(0, HIER); from testdata import app_map, zet_cachenaam
BRON = app_map()  # werkmap: 'uit'; in de repository: de app naast tests/
fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

STORING = {'html': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'max-age=600'); super().end_headers()
    def do_GET(self):
        if STORING['html'] and self.path.split('?')[0].endswith('/golf-score.html'): self.send_error(503); return
        super().do_GET()

def zet_versie(wortel, cache, label):
    p = os.path.join(wortel, 'golf-score', 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(zet_cachenaam(s, cache))
    p = os.path.join(wortel, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

INHOUD = """async () => { const uit = {}; for (const n of (await caches.keys()).sort()) { const r = await (await caches.open(n)).match('./golf-score.html');
  uit[n] = r ? (await r.text()).match(/Versie ([0-9A-F]+-[0-9A-F]+)/)[1] : null; } return uit; }"""
VERSIE = "() => document.getElementById('appVersionStamp').textContent"
# Sinds 13527DA-13B neemt een nieuwe versie het pas over na een tik op de updatemelding.
async def tik_op_melding(pg):
    try: await pg.evaluate("() => updateBannerKlik()")
    except Exception: pass   # de pagina herlaadt tijdens de aanroep
    await pg.wait_for_timeout(2500)

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    zet_versie(wortel, 'golf-score-proef-1', '13527DA-F01')
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_port}/golf-score/golf-score.html'

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page()
        await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1500)
        check("versie 1 geïnstalleerd", await pg.evaluate(INHOUD), {'golf-score-proef-1': '13527DA-F01'})

        print("\n=== 1. UPDATE BINNEN 10 MINUTEN NA HET OPENEN ===\n")
        zet_versie(wortel, 'golf-score-proef-2', '13527DA-F02')
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())"); await pg.wait_for_timeout(3000)
        check("de cache van versie 2 bevat de app van versie 2", (await pg.evaluate(INHOUD)).get('golf-score-proef-2'), '13527DA-F02')
        await tik_op_melding(pg)
        check("na de tik op de melding draait versie 2, alleen haar cache staat er", (await pg.evaluate(VERSIE), await pg.evaluate(INHOUD)), ('Versie 13527DA-F02', {'golf-score-proef-2': '13527DA-F02'}))

        print("\n=== 2. MISLUKTE UPDATE: DE APP KOMT NIET BINNEN ===\n")
        zet_versie(wortel, 'golf-score-proef-3', '13527DA-F03'); STORING['html'] = True
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(3000)
        check("geen halve cache van versie 3; versie 2 staat er nog", await pg.evaluate(INHOUD), {'golf-score-proef-2': '13527DA-F02'})
        check("er wacht geen nieuwe versie", await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.waiting)"), False)
        await pg.reload(); await pg.wait_for_timeout(800)
        check("de app werkt door op versie 2", await pg.evaluate(VERSIE), 'Versie 13527DA-F02')
        srv.shutdown(); srv.server_close()
        pg2 = await ctx.new_page(); await pg2.goto(url); await pg2.wait_for_timeout(800)
        check("daarna offline: versie 2 opent", await pg2.evaluate(VERSIE), 'Versie 13527DA-F02')
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
