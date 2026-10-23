"""Bij slecht bereik opent de geïnstalleerde app direct, via elk adres.

Draait de app via een echte webserver op een kopie van 'uit'. Slecht bereik is hier: de
server neemt de verbinding aan maar antwoordt nooit (zoals op de baan met één streepje).
Geen bereik is: de server is weg.

Tot 13527DA-137 opende een adres met een toevoeging achter het vraagteken (zoals een
gedeelde link die WhatsApp verlengt) bij slecht bereik niet: de service worker vond die
pagina niet in zijn opslag en wachtte op het netwerk. 'Verversen' laadt hetzelfde adres
opnieuw en bleef dan ook hangen.

De regel: het openen van een pagina komt uit de opslag zodra die er is, met of zonder
toevoeging, met of zonder bereik. Het ophalen van een nieuwe versie (?verversen) blijft
via het netwerk gaan en wordt niet uit de opslag beantwoord.
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

MODUS = {'hangt': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        if MODUS['hangt']: time.sleep(30); return
        super().do_GET()

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    basis = f'http://127.0.0.1:{srv.server_port}/golf-score/'
    VERSIE = "() => (document.getElementById('appVersionStamp') || {}).textContent || ''"

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); await pg.goto(basis + 'golf-score.html')
        await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1200)
        versie = await pg.evaluate(VERSIE); await pg.close()
        check("online geïnstalleerd", bool(re.fullmatch(r'Versie [0-9A-F]+-[0-9A-F]+', versie)), True)

        async def open_(pad):
            pg = await ctx.new_page(); t = time.time()
            try:
                await pg.goto(basis + pad, timeout=6000); await pg.wait_for_function("document.getElementById('appVersionStamp')", timeout=6000)
                v = await pg.evaluate(VERSIE)
            except Exception: v = 'opent niet'
            return pg, v, time.time() - t

        print("\n=== 1. SLECHT BEREIK: DE SERVER ANTWOORDT NIET ===\n")
        MODUS['hangt'] = True
        for pad in ('golf-score.html', 'golf-score.html?fbclid=abc123', './?utm_source=whatsapp', 'index.html'):
            pg, v, t = await open_(pad)
            check(f"'{pad}' opent direct uit de opslag", (v, t < 3), (versie, True))
            await pg.close()
        pg, v, t = await open_('golf-score.html?fbclid=abc123')
        t0 = time.time()
        try: await pg.reload(timeout=6000); await pg.wait_for_function("document.getElementById('appVersionStamp')", timeout=6000); v = await pg.evaluate(VERSIE)
        except Exception: v = 'opent niet'
        check("verversen op zo'n adres opent ook direct", (v, time.time() - t0 < 3), (versie, True))
        r = await pg.evaluate("""async () => { const c = new AbortController(); setTimeout(() => c.abort(), 2000);
          try { await fetch('./golf-score.html?verversen', { cache: 'reload', signal: c.signal }); return 'antwoord'; } catch (e) { return 'wacht op het netwerk'; } }""")
        check("een nieuwe versie ophalen (?verversen) gaat via het netwerk, niet uit de opslag", r, 'wacht op het netwerk')
        await pg.close()

        print("\n=== 2. GEEN BEREIK: DE SERVER IS WEG ===\n")
        MODUS['hangt'] = False; srv.shutdown(); srv.server_close()
        for pad in ('golf-score.html', 'golf-score.html?fbclid=abc123'):
            pg, v, t = await open_(pad)
            check(f"'{pad}' opent", v, versie); await pg.close()
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
