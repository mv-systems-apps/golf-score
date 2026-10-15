"""Een update van de service worker bij slecht bereik mag de app offline niet breken.

Naspelen: de app staat geïnstalleerd en werkt offline. Er komt een nieuwe versie, maar
tijdens het ophalen faalt golf-score.html (slecht bereik op de baan). Daarna ga je offline
en open je de app. Die hoort dan gewoon te openen: met de nieuwe versie als die compleet
binnen is, anders met de vorige.
De app draait hier via een echte webserver (een service worker werkt niet vanaf een
bestand). De server kan golf-score.html op commando laten mislukken.
Draait op de map 'uit' naast tests_run2 (wat er naar GitHub gaat), in een kopie.
"""
import asyncio, os, shutil, sys, tempfile, threading, re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER); from testdata import app_map
BRON = app_map()  # werkmap: 'uit'; in de repository: de app naast tests/
fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

STORING = {'aan': False, 'geweigerd': 0}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        pad = self.path.split('?')[0]
        if (STORING['aan'] and pad.endswith('/golf-score.html')) or (STORING.get('pad') and pad == STORING['pad']):
            STORING['geweigerd'] += 1; self.send_error(503); return
        super().do_GET()

def zet_versie(map_, cache, label):
    p = os.path.join(map_, 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r"const CACHE_VERSION = '[^']*';", f"const CACHE_VERSION = '{cache}';", s))
    p = os.path.join(map_, 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

async def main():
    map_ = tempfile.mkdtemp(); shutil.copytree(BRON, map_, dirs_exist_ok=True)
    zet_versie(map_, 'golf-score-proef-1', '13527DA-F01')
    # 'Offline' = de server is weg (verbinding geweigerd). Het offline-knopje van de
    # testbrowser geldt niet voor de service worker zelf, dus dat zou niets bewijzen.
    srv = {}
    def aan(poort=0):
        ThreadingHTTPServer.allow_reuse_address = True
        srv['s'] = ThreadingHTTPServer(('127.0.0.1', poort), partial(Handler, directory=map_))
        threading.Thread(target=srv['s'].serve_forever, daemon=True).start()
        return srv['s'].server_port
    def uit():
        srv['s'].shutdown(); srv['s'].server_close()
    poort = aan()
    url = f'http://127.0.0.1:{poort}/golf-score.html'
    VERSIE = "() => (document.getElementById('appVersionStamp') || {}).textContent || ''"
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context()
        pg = await ctx.new_page()
        await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(800)
        check("vooraf: geïnstalleerd, versie 1", await pg.evaluate(VERSIE), 'Versie 13527DA-F01')
        uit(); await pg.reload(); await pg.wait_for_timeout(500)
        check("vooraf: opent offline", await pg.evaluate(VERSIE), 'Versie 13527DA-F01')
        aan(poort)

        print("\n=== NIEUWE VERSIE, MAAR golf-score.html FAALT TIJDENS HET OPHALEN ===\n")
        zet_versie(map_, 'golf-score-proef-2', '13527DA-F02'); STORING['aan'] = True
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        check("de server heeft golf-score.html geweigerd", STORING['geweigerd'] > 0, True)
        caches = await pg.evaluate("caches.keys().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => c.match('./golf-score.html')).then(m => k + (m ? ' (met app)' : ' (ZONDER app)')))))")
        uit()                     # het bereik valt helemaal weg
        STORING['aan'] = False
        pg2 = await ctx.new_page()
        try:
            await pg2.goto(url, timeout=8000); await pg2.wait_for_timeout(500); v = await pg2.evaluate(VERSIE)
        except Exception as e:
            v = 'opent niet: ' + str(e).split('\n')[0][:60]
        check("offline opent de app daarna nog, met de vorige versie", v, 'Versie 13527DA-F01')
        print(f"       (caches: {caches}; getoond: {v!r})")
        aan(poort)

        print("\n=== DAARNA GOED BEREIK: DE NIEUWE VERSIE KOMT ALSNOG ===\n")
        await pg2.close()
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(1500)
        pg3 = await ctx.new_page(); await pg3.goto(url); await pg3.wait_for_timeout(800)
        await pg3.reload(); await pg3.wait_for_timeout(800)
        check("online komt versie 2 binnen", await pg3.evaluate(VERSIE), 'Versie 13527DA-F02')
        uit(); await pg3.reload(); await pg3.wait_for_timeout(500)
        check("en die opent daarna ook offline", await pg3.evaluate(VERSIE), 'Versie 13527DA-F02')

        print("\n=== EEN PICTOGRAM DAT NIET LUKT, BREEKT DE UPDATE NIET ===\n")
        aan(poort); zet_versie(map_, 'golf-score-proef-3', '13527DA-F03'); STORING['pad'] = '/icon-512.png'
        await pg3.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg3.wait_for_timeout(2500)
        STORING['pad'] = None
        # sinds 13527DA-13B: de nieuwe versie neemt het pas over na een tik op de melding
        try: await pg3.evaluate("() => updateBannerKlik()")
        except Exception: pass
        await pg3.wait_for_timeout(2500)
        inhoud = await pg3.evaluate("caches.keys().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => Promise.all([c.match('./golf-score.html'), c.match('./icon-512.png')])).then(([a, i]) => [k, !!a, !!i]))))")
        check("de nieuwe versie is actief, met app én het pictogram uit de vorige kopie", inhoud, [['golf-score-proef-3', True, True]])
        await b.close()
    shutil.rmtree(map_, ignore_errors=True)
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
