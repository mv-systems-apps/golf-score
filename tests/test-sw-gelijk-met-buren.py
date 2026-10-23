"""Service worker: wat Golf Score, Trends en Events sinds 16-10-2026 gelijk doen.

Draait de app via een echte webserver op een kopie van de appbestanden.

Tot 1352897-001 (golf):
  1. heette de cache naar een hash van de appbestanden, waar de service worker zelf niet
     in zat. Wijzigde alleen de service worker, dan installeerde de nieuwe in dezelfde
     cache waaruit de oude nog bediende;
  2. kreeg de app geen bericht als er een verse kopie van golf-score.html in de cache
     stond. De controle na 4 s was op mobiel bereik vaak te vroeg, en dan kwam de
     updatemelding pas bij het wegschakelen en terughalen;
  3. haalde de achtergrondverversing de pagina zonder no-cache op. GitHub Pages laat een
     bestand 10 minuten bewaren, dus vlak na een push schreef de verversing dezelfde
     oude app terug en bleef de melding uit;
  4. had de installatie geen tijdsgrens. Een verbinding die bleef hangen hield de
     installatie vast, en zolang die liep deed registration.update() niets.

De regels:
  1. CACHE_VERSION is een getal; de naam is 'golf-score-v' + dat getal, en
     update_cache_version.py hoogt het getal met één op.
  2. Staat er een verse kopie van de pagina in de cache, dan krijgt elk open venster
     het bericht 'kopieVernieuwd' en controleert de app meteen: de melding staat er.
  3. Binnen de 10 minuten browseropslag komt een nieuwe golf-score.html toch in de cache.
  4. Bij een verbinding die blijft hangen loopt de installatie binnen 45 s af (drie
     pogingen van hooguit 10 s), en de vorige versie blijft staan.
"""
import asyncio, os, re, shutil, subprocess, sys, tempfile, threading, time
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

M = {'cache': 'no-cache', 'hangt': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', M['cache']); super().end_headers()
    def do_GET(self):
        # Slecht bereik voor de appbestanden; de service worker zelf komt wel binnen,
        # anders begint er geen installatie.
        if M['hangt'] and not self.path.split('?')[0].endswith('.js'):
            for _ in range(900):
                if not M['hangt']: return
                time.sleep(0.1)
            return
        super().do_GET()

def zet_stempel(wortel, label):
    p = os.path.join(wortel, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))
    # Een latere wijzigingstijd, zodat een voorwaardelijk verzoek binnen dezelfde seconde
    # geen 'ongewijzigd' krijgt.
    t = time.time() + 5; os.utime(p, (t, t))

STEMPELS = """async () => { const uit = {}; for (const n of (await caches.keys()).filter(k => k.startsWith('golf-score-')).sort()) {
  const r = await (await caches.open(n)).match('./golf-score.html');
  uit[n] = r ? ((await r.text()).match(/Versie ([0-9A-F]+-[0-9A-F]+)/) || [])[1] || null : null; } return uit; }"""

async def main():
    print("\n=== 1. DE CACHENAAM IS EEN TELLER ===\n")
    sw = open(os.path.join(BRON, 'sw-golf-score.js'), encoding='utf-8').read()
    teller = re.search(r"const CACHE_VERSION = (\d+);", sw)
    check("CACHE_VERSION is een getal", bool(teller), True)
    check("de naam wordt ervan afgeleid", "const CACHE_NAME = 'golf-score-v' + CACHE_VERSION;" in sw, True)
    with tempfile.TemporaryDirectory() as d:
        for n in ('sw-golf-score.js', 'update_cache_version.py'):
            shutil.copy(os.path.join(BRON, n), d)
        subprocess.run([sys.executable, '-I', os.path.join(d, 'update_cache_version.py')], cwd=d,
                       capture_output=True, text=True)
        na = re.search(r"const CACHE_VERSION = (\d+);", open(os.path.join(d, 'sw-golf-score.js'), encoding='utf-8').read())
        check("update_cache_version.py hoogt het getal met één op",
              (int(na.group(1)) - int(teller.group(1))) if (na and teller) else None, 1)

    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    zet_stempel(wortel, '13527DA-F01')
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=wortel)); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_port}/golf-score/golf-score.html'

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 412, 'height': 915})
        pg = await ctx.new_page()
        await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready")
        await pg.wait_for_function("!!navigator.serviceWorker.controller", timeout=10000)
        await pg.wait_for_timeout(1500)
        eigen = await pg.evaluate(STEMPELS)
        check("versie 1 staat in één eigen cache", list(eigen.values()), ['13527DA-F01'])

        print("\n=== 2. EEN VERSE KOPIE WORDT METEEN GEMELD ===\n")
        # Ruim na de controle van 4 s, zodat alleen het bericht de melding kan brengen.
        await pg.wait_for_timeout(4500)
        check("vooraf geen melding", await pg.evaluate("document.getElementById('updateBanner').classList.contains('hidden')"), True)
        await pg.evaluate("window.__berichten = []; navigator.serviceWorker.addEventListener('message', e => __berichten.push(e.data && e.data.type))")
        zet_stempel(wortel, '13527DA-F02')
        pg2 = await ctx.new_page(); await pg2.goto(url)   # een opening die de pagina ververst
        await pg.wait_for_timeout(2500)
        check("het eerste venster kreeg het bericht 'kopieVernieuwd'",
              'kopieVernieuwd' in (await pg.evaluate("window.__berichten")), True)
        check("en toont meteen de melding over de nieuwe versie",
              await pg.evaluate("(() => { const b = document.getElementById('updateBanner'); return !b.classList.contains('hidden') && /Nieuwe versie \\(13527DA-F02\\)/.test(b.textContent); })()"),
              True)
        await pg2.close()

        print("\n=== 3. BINNEN DE 10 MINUTEN BROWSEROPSLAG VAN GITHUB PAGES ===\n")
        M['cache'] = 'max-age=600'
        await pg.reload(); await pg.wait_for_timeout(2000)   # de browser bewaart golf-score.html nu 10 minuten
        zet_stempel(wortel, '13527DA-F03')
        await pg.reload(); await pg.wait_for_timeout(2500)   # de achtergrondverversing van deze opening
        check("de nieuwe app staat toch in de cache", list((await pg.evaluate(STEMPELS)).values()), ['13527DA-F03'])
        M['cache'] = 'no-cache'

        print("\n=== 4. EEN INSTALLATIE DIE BLIJFT HANGEN, LOOPT AF ===\n")
        voor = await pg.evaluate(STEMPELS)
        pad = os.path.join(wortel, 'golf-score', 'sw-golf-score.js')
        tekst = open(pad, encoding='utf-8').read()
        open(pad, 'w', encoding='utf-8').write(zet_cachenaam(tekst, 'golf-score-proef-hangt'))
        M['hangt'] = True
        begin = time.time()
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => { r.update().catch(() => {}); })")
        await pg.wait_for_timeout(1500)
        check("de installatie is begonnen", await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.installing)"), True)
        duur = None
        while time.time() - begin < 50:
            if not await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.installing)"):
                duur = time.time() - begin; break
            await pg.wait_for_timeout(1000)
        print(f"       installatie liep af na {duur:.0f} s" if duur is not None else "       installatie liep na 50 s nog")
        check("de installatie loopt binnen 45 s af", duur is not None and duur <= 45, True)
        M['hangt'] = False
        await pg.wait_for_timeout(1000)
        check("er wacht geen halve nieuwe versie", await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.waiting)"), False)
        check("de vorige cache staat er nog, er is geen nieuwe bij", await pg.evaluate(STEMPELS), voor)
        await b.close()
    srv.shutdown(); srv.server_close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
