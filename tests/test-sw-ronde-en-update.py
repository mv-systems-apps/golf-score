"""Service worker: andere apps ongemoeid, en een update tijdens een lopende ronde.

Draait de app via een echte webserver op een kopie van 'uit'. 'Offline' is: de server is
weg (het offline-knopje van de testbrowser geldt niet voor de service worker zelf).

1. Cache-isolatie: Golf Score staat op dezelfde origin als andere apps (GitHub Pages:
   mv-systems-apps.github.io/<app>/). Een update van Golf Score mag hun caches niet weggooien,
   en ruimt alleen eigen oude caches op.
2. Een lopende ronde en een update:
   a. ronde starten, dan offline;
   b. offline scores invoeren en de app opnieuw openen;
   c. een nieuwe versie beschikbaar terwijl de ronde loopt;
   d. van offline naar online met een lopende ronde;
   e. na de update opnieuw offline starten;
   f. een gedeeltelijk mislukte update (golf-score.html komt niet binnen);
   g. 'Verouderde kopie — tik om op te ruimen': zonder bereik, met een verbinding die
      halverwege wegvalt, en geslaagd; steeds daarna direct offline starten.
   Steeds: geen score kwijt, de app opent, en de ronde loopt door.
"""
import asyncio, json, os, re, shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS

sys.path.insert(0, HIER); from testdata import app_map, zet_cachenaam
BRON = app_map()  # werkmap: 'uit'; in de repository: de app naast tests/
fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

STORING = {'aan': False, 'half': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        pad = self.path.split('?')[0]
        if STORING['aan'] and pad.endswith('/golf-score.html'): self.send_error(503); return
        if STORING['half'] and pad.endswith('/golf-score.html'):
            # de verbinding valt weg halverwege de download
            data = open(os.path.join(self.directory, pad.lstrip('/')), 'rb').read()
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data[:len(data) // 2]); self.wfile.flush()
            self.close_connection = True; self.connection.shutdown(2); return
        super().do_GET()

def zet_versie(map_, cache, label):
    p = os.path.join(map_, 'golf-score', 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(zet_cachenaam(s, cache))
    p = os.path.join(map_, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

async def main():
    wortel = tempfile.mkdtemp(); map_ = os.path.join(wortel, 'golf-score'); shutil.copytree(BRON, map_)
    zet_versie(wortel, 'golf-score-proef-1', '13527DA-F01')
    srv = {}
    def aan(poort=0):
        if srv.get('draait'): return srv['s'].server_port
        srv['draait'] = True
        ThreadingHTTPServer.allow_reuse_address = True
        srv['s'] = ThreadingHTTPServer(('127.0.0.1', poort), partial(Handler, directory=wortel))
        threading.Thread(target=srv['s'].serve_forever, daemon=True).start(); return srv['s'].server_port
    def uit():
        if not srv.get('draait'): return
        srv['draait'] = False; srv['s'].shutdown(); srv['s'].server_close()
    poort = aan(); url = f'http://127.0.0.1:{poort}/golf-score/golf-score.html'
    VERSIE = "() => (document.getElementById('appVersionStamp') || {}).textContent || ''"
    SCORES = "() => { const r = JSON.parse(localStorage.getItem('golf_rounds') || '[]').find(r => String(r.id) === localStorage.getItem('golf_active_id')); return r ? r.holes.map(h => h.score) : null; }"
    async def open_(ctx):
        pg = await ctx.new_page()
        try: await pg.goto(url, timeout=8000); await pg.wait_for_timeout(700); return pg, await pg.evaluate(VERSIE)
        except Exception as e: return pg, 'opent niet'
    async def tik(pg, n):
        await pg.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
        await pg.evaluate(f"() => {{ nav('score'); for (let k = 0; k < {n}; k++) {{ const i = game.holes.findIndex(h => h.score === null); if (i < 0) return; setCurrentHole(i); stepScore(i, 1); }} }}")
        await pg.wait_for_timeout(300)

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg, v = await open_(ctx)
        await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(800)
        await pg.evaluate("""(c) => { localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_profile_hcp', '30.7'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", CLUBS)
        # een andere app op dezelfde origin met een eigen cache
        await pg.evaluate("() => caches.open('trends-7').then(c => c.put('/trends/trends.html', new Response('trends')))")
        await pg.evaluate("() => caches.open('events-3').then(c => c.put('/events/events.html', new Response('events')))")
        await pg.reload(); await pg.wait_for_timeout(700)

        print("\n=== a. RONDE STARTEN, DAN OFFLINE ===\n")
        await pg.evaluate("() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }")
        await pg.wait_for_timeout(400); await tik(pg, 3)
        voor = await pg.evaluate(SCORES)
        check("ronde loopt met 3 scores", sum(1 for s in voor if s is not None), 3)
        uit()
        await pg.close(); pg, v = await open_(ctx)
        check("offline: de app opent", v, 'Versie 13527DA-F01')

        print("\n=== b. OFFLINE SCORES INVOEREN EN OPNIEUW OPENEN ===\n")
        await pg.wait_for_timeout(300); await tik(pg, 2)
        await pg.wait_for_timeout(2300)
        await pg.close(); pg, v = await open_(ctx)
        check("offline opnieuw geopend: de ronde loopt door met 5 scores", (v, await pg.evaluate("game.started"), sum(1 for s in await pg.evaluate(SCORES) if s is not None)), ('Versie 13527DA-F01', True, 5))

        print("\n=== c. NIEUWE VERSIE TERWIJL DE RONDE LOOPT ===\n")
        zet_versie(wortel, 'golf-score-proef-2', '13527DA-F02'); aan(poort)
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        check("de lopende pagina werkt door: nog een score invoeren", (await tik(pg, 1)) or sum(1 for s in await pg.evaluate(SCORES) if s is not None), 6)

        print("\n=== d. VAN OFFLINE NAAR ONLINE MET EEN LOPENDE RONDE ===\n")
        await pg.close(); pg, v = await open_(ctx)
        await pg.reload(); await pg.wait_for_timeout(700); v = await pg.evaluate(VERSIE)
        check("online: de nieuwe versie is er, de ronde loopt door met 6 scores", (v, await pg.evaluate("game.started"), sum(1 for s in await pg.evaluate(SCORES) if s is not None)), ('Versie 13527DA-F02', True, 6))
        caches = sorted(await pg.evaluate("caches.keys()"))
        check("alleen de eigen oude cache is opgeruimd; trends en events staan er nog", caches, ['events-3', 'golf-score-proef-2', 'trends-7'])

        print("\n=== e. NA DE UPDATE OPNIEUW OFFLINE STARTEN ===\n")
        uit(); await pg.close(); pg, v = await open_(ctx)
        check("offline: de nieuwe versie opent, de ronde loopt door", (v, await pg.evaluate("game.started"), sum(1 for s in await pg.evaluate(SCORES) if s is not None)), ('Versie 13527DA-F02', True, 6))
        await tik(pg, 1); await pg.wait_for_timeout(2300)

        print("\n=== f. GEDEELTELIJK MISLUKTE UPDATE TIJDENS DE RONDE ===\n")
        zet_versie(wortel, 'golf-score-proef-3', '13527DA-F03'); aan(poort); STORING['aan'] = True
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        uit(); STORING['aan'] = False
        await pg.close(); pg, v = await open_(ctx)
        check("offline: de vorige versie opent, de ronde loopt door met 7 scores", (v, await pg.evaluate("game.started"), sum(1 for s in await pg.evaluate(SCORES) if s is not None)), ('Versie 13527DA-F02', True, 7))

        print("\n=== g. 'VEROUDERDE KOPIE OPRUIMEN' ===\n")
        # De melding 'Verouderde kopie in het geheugen — tik om op te ruimen' verschijnt als
        # de cache een oudere versie heeft dan wat er draait. Hier: de cache krijgt een oude
        # kopie (F01) terwijl F02 draait. Drie gevallen: geen bereik, verbinding valt weg
        # tijdens het ophalen, en een geslaagde opruimactie. Na elk geval: offline starten.
        ANDERE = "() => caches.keys().then(k => k.filter(n => !n.startsWith('golf-score-')).sort())"
        INHOUD = """() => caches.keys().then(ks => Promise.all(ks.filter(n => n.startsWith('golf-score-')).map(n => caches.open(n).then(c =>
            Promise.all([c.match('./golf-score.html').then(r => r ? r.text() : ''), c.match('./icon-192.png'), c.match('./manifest.json')])
            .then(([t, i, m]) => [n, (t.match(/Versie (13527DA-[0-9A-F]+)/) || [])[1] || null, !!i, !!m]))))).then(l => l.sort())"""
        OUD = open(os.path.join(BRON, 'golf-score.html'), encoding='utf-8').read().replace(re.search(r'Versie [0-9A-Z]+-[0-9A-F]+', open(os.path.join(BRON, 'golf-score.html'), encoding='utf-8').read()).group(0), 'Versie 13527DA-F01')
        async def verouderd(pg):
            await pg.evaluate("(t) => caches.keys().then(ks => Promise.all(ks.filter(n => n.startsWith('golf-score-')).map(n => caches.open(n).then(c => c.put('./golf-score.html', new Response(t, { headers: { 'Content-Type': 'text/html' } }))))))", OUD)
            await pg.evaluate("() => { const b = document.getElementById('updateBanner'); b.dataset.ouder = '1'; }")
        # Uitgangspunt: online, de laatst geplaatste versie (F03) volledig geïnstalleerd.
        aan(poort); await pg.close(); pg, v = await open_(ctx)
        await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        for geval, voorbereiden in [('geen bereik', lambda: uit()), ('verbinding valt weg tijdens het ophalen', lambda: STORING.update(half=True))]:
            aan(poort); await pg.close(); pg, v = await open_(ctx); await pg.wait_for_timeout(1500)
            await verouderd(pg); voor = await pg.evaluate(INHOUD)
            voorbereiden()
            await pg.evaluate("() => updateBannerKlik()"); await pg.wait_for_timeout(800)
            melding = await pg.evaluate("document.getElementById('confirmModal').classList.contains('hidden') ? '' : document.getElementById('confirmModalTitle').textContent")
            check(f"{geval}: melding, en de cache is ongewijzigd (compleet: app, pictogram, manifest)", (melding, await pg.evaluate(INHOUD)), ('Geen verbinding', voor))
            STORING['half'] = False
            uit()
            await pg.close(); pg, v = await open_(ctx)
            check(f"{geval}: direct daarna offline starten lukt, de ronde loopt door", (v != 'opent niet', (await pg.evaluate("game.started")) if v != 'opent niet' else None), (True, True))
        aan(poort); await pg.close(); pg, v = await open_(ctx); await pg.wait_for_timeout(500)
        await verouderd(pg)
        await pg.evaluate("() => updateBannerKlik()"); await pg.wait_for_timeout(1500)
        na = await pg.evaluate(INHOUD)
        check("geslaagd: de oude kopie is vervangen door de actuele, de rest van de cache staat er nog", [x[1:] for x in na], [['13527DA-F03', True, True]])
        uit(); await pg.close(); pg, v = await open_(ctx)
        check("en offline start de actuele versie, met de ronde", (v, await pg.evaluate("game.started") if v != 'opent niet' else None), ('Versie 13527DA-F03', True))
        aan(poort); await pg.close(); pg, v = await open_(ctx)
        check("de caches van andere apps staan er na alles nog", await pg.evaluate(ANDERE), ['events-3', 'trends-7'])
        await b.close()
    shutil.rmtree(wortel, ignore_errors=True)
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
