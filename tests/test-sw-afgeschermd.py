"""De service worker van Golf Score blijft van alles af wat niet van Golf Score is.

Draait via een echte webserver met drie apps naast elkaar, zoals op GitHub Pages:
/golf-score/, /events/ en /trends/ op dezelfde origin, dus met één gedeelde cacheopslag.

Tot 13527DA-13B:
  * kreeg een pagina binnen /golf-score/ die geen appbestand is, de app als terugval;
  * zocht de service worker met caches.match() in ALLE caches van de origin. Ontbrak een
    bestand in de eigen cache, dan kon het antwoord uit de cache van een andere app komen,
    en terwijl een nieuwe versie wachtte uit de cache van die nieuwe versie;
  * nam de installatie een ontbrekend pictogram over uit welke cache dan ook.

De regels:
  1. Navigaties naar Events en Trends komen niet bij Golf Score langs.
  2. Een pagina binnen /golf-score/ die geen appbestand is, wordt niet onderschept.
  3. De service worker antwoordt alleen uit zijn eigen cache, nooit uit die van een
     andere app en nooit uit die van een wachtende nieuwe versie.
  4. Bij het installeren komen ontbrekende bijbestanden alleen uit eerdere caches van
     Golf Score.
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

STORING = {'pad': None}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        if STORING['pad'] and self.path.split('?')[0].endswith(STORING['pad']): self.send_error(503); return
        super().do_GET()

def zet_versie(wortel, cache, label):
    p = os.path.join(wortel, 'golf-score', 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(zet_cachenaam(s, cache))
    p = os.path.join(wortel, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

VRAAG = """async (pad) => { try { const r = await fetch(pad); return [r.status, (await r.text()).slice(0, 12)]; } catch (e) { return [e.name, '']; } }"""
WIS_ICOON = """async () => { for (const n of await caches.keys()) if (n.startsWith('golf-score-')) await (await caches.open(n)).delete('./icon-512.png'); }"""

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    zet_versie(wortel, 'golf-score-proef-1', '13527DA-F01')
    for app in ('events', 'trends'):
        os.makedirs(os.path.join(wortel, app))
        open(os.path.join(wortel, app, f'{app}.html'), 'w').write(f'<!doctype html><title>{app}</title><p>{app}')
    open(os.path.join(wortel, 'golf-score', 'andere.html'), 'w').write('<!doctype html><title>andere</title><p>andere')
    srv = {}
    def aan(poort=0):
        ThreadingHTTPServer.allow_reuse_address = True
        srv['s'] = ThreadingHTTPServer(('127.0.0.1', poort), partial(Handler, directory=wortel)); srv['s'].daemon_threads = True
        threading.Thread(target=srv['s'].serve_forever, daemon=True).start(); return srv['s'].server_port
    def uit(): srv['s'].shutdown(); srv['s'].server_close()
    poort = aan(); basis = f'http://127.0.0.1:{poort}/'

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context()
        pg = await ctx.new_page(); await pg.goto(basis + 'golf-score/golf-score.html')
        await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1200); await pg.reload(); await pg.wait_for_timeout(500)

        print("\n=== 1. EVENTS EN TRENDS ===\n")
        for app in ('events', 'trends'):
            q = await ctx.new_page(); await q.goto(basis + f'{app}/{app}.html')
            check(f"{app}: eigen inhoud, niet bestuurd door Golf Score", (await q.title(), await q.evaluate("!!navigator.serviceWorker.controller")), (app, False)); await q.close()

        print("\n=== 2. EEN ANDERE PAGINA BINNEN /golf-score/ ===\n")
        q = await ctx.new_page(); await q.goto(basis + 'golf-score/andere.html')
        check("online: de pagina zelf", await q.title(), 'andere'); await q.close()
        uit()
        q = await ctx.new_page()
        try: await q.goto(basis + 'golf-score/andere.html', timeout=6000); t = await q.title()
        except Exception: t = 'niet geladen (geen terugval)'
        check("offline: geen terugval op de app", t != 'Golf Score', True); await q.close()

        print("\n=== 3. ALLEEN UIT DE EIGEN CACHE ===\n")
        await pg.evaluate("() => caches.open('trends-9').then(c => c.put(location.origin + '/golf-score/icon-512.png', new Response('VREEMD-TRENDS')))")
        await pg.evaluate(WIS_ICOON)
        check("offline: een ontbrekend pictogram komt niet uit de cache van Trends", await pg.evaluate(VRAAG, './icon-512.png'), [503, ''])
        await pg.evaluate("() => caches.delete('trends-9')")

        print("\n=== 4. INSTALLEREN: ALLEEN UIT EIGEN EERDERE CACHES ===\n")
        aan(poort)
        await pg.evaluate("() => caches.open('events-v9').then(c => c.put(location.origin + '/golf-score/icon-512.png', new Response('VREEMD-EVENTS')))")
        zet_versie(wortel, 'golf-score-proef-2', '13527DA-F02'); STORING['pad'] = '/icon-512.png'
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        STORING['pad'] = None
        inhoud = await pg.evaluate("""async () => { const c = await caches.open('golf-score-proef-2'); const r = await c.match('./icon-512.png');
            return [!!(await c.match('./golf-score.html')), r ? (await r.text()).slice(0, 13) : null]; }""")
        check("de nieuwe versie is compleet, zonder pictogram uit de cache van Events", inhoud, [True, None])
        check("de cache van Events is niet aangeraakt", await pg.evaluate("() => caches.has('events-v9')"), True)

        print("\n=== 3b. WACHTENDE VERSIE: NIET MENGEN ===\n")
        check("versie 2 wacht", await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => !!r.waiting)"), True)
        await pg.evaluate("() => caches.open('golf-score-proef-2').then(c => c.put('./icon-512.png', new Response('NIEUWE-VERSIE')))")
        uit()
        r = await pg.evaluate(VRAAG, './icon-512.png')
        check("de huidige versie haalt een ontbrekend bestand niet uit de wachtende versie", r, [503, ''])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
