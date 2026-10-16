"""Een update is beschikbaar zonder actief te worden: pas een tik op de melding activeert.

Draait de app via een echte webserver op een kopie van 'uit'. Offline is: de server is weg.

Tot 13527DA-13A nam een nieuwe service worker het direct over (skipWaiting). De pagina
herlaadde daarbij niet, maar 'beschikbaar' en 'actief' waren niet te onderscheiden.

De regels:
  1. Een nieuwe versie die binnenkomt tijdens een lopende ronde, op het invoerscherm en
     met een tik die nog op bevestiging wacht, wacht: de app herlaadt niet, de oude
     service worker blijft de baas, de scores blijven, de melding verschijnt.
  2. Bewaart de browser niets, dan weigert de melding te verversen (herladen zou alles wissen).
  3. Offline tikken op de melding activeert de wachtende versie; de app herlaadt één keer,
     de ronde loopt door; een tik die nog op bevestiging wachtte, is teruggedraaid
     (sinds 13527DA-140, net als na 2 seconden zonder bevestiging).
  4. Een update waarbij de app niet binnenkomt (verbinding valt weg) levert niets wachtends
     op; de app werkt door.
  5. Zonder tik neemt de browser de nieuwe versie pas in gebruik als de app helemaal dicht
     is geweest; de ronde loopt daarna door.
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

STORING = {'html': False}
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_GET(self):
        if STORING['html'] and self.path.split('?')[0].endswith('/golf-score.html'): self.send_error(503); return
        super().do_GET()

def zet_versie(wortel, cache, label):
    p = os.path.join(wortel, 'golf-score', 'sw-golf-score.js'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(zet_cachenaam(s, cache))
    p = os.path.join(wortel, 'golf-score', 'golf-score.html'); s = open(p, encoding='utf-8').read()
    open(p, 'w', encoding='utf-8').write(re.sub(r'Versie [0-9A-Z]+-[0-9A-F]+', f'Versie {label}', s))

STAND = """async () => { const reg = await navigator.serviceWorker.getRegistration();
  const ctrl = navigator.serviceWorker.controller ? new URL(navigator.serviceWorker.controller.scriptURL).pathname : null;
  const r = JSON.parse(localStorage.getItem('golf_rounds') || '[]').find(x => String(x.id) === localStorage.getItem('golf_active_id'));
  const b = document.getElementById('updateBanner');
  return { wacht: !!(reg && reg.waiting), herladen: !window.__zelfdePagina, versie: document.getElementById('appVersionStamp').textContent,
    ronde: game.started, scores: r ? r.holes.filter(h => h.score !== null).length : null,
    melding: b && !b.classList.contains('hidden') ? b.textContent : '' }; }"""
CACHE_HTML = """async () => { const uit = {}; for (const n of (await caches.keys()).sort()) { const r = await (await caches.open(n)).match('./golf-score.html');
  uit[n] = r ? (await r.text()).match(/Versie ([0-9A-F]+-[0-9A-F]+)/)[1] : null; } return uit; }"""

async def main():
    wortel = tempfile.mkdtemp(); shutil.copytree(BRON, os.path.join(wortel, 'golf-score'))
    zet_versie(wortel, 'golf-score-proef-1', '13527DA-F01')
    srv = {}
    def aan(poort=0):
        ThreadingHTTPServer.allow_reuse_address = True
        srv['s'] = ThreadingHTTPServer(('127.0.0.1', poort), partial(Handler, directory=wortel)); srv['s'].daemon_threads = True
        threading.Thread(target=srv['s'].serve_forever, daemon=True).start(); return srv['s'].server_port
    def uit(): srv['s'].shutdown(); srv['s'].server_close()
    poort = aan(); url = f'http://127.0.0.1:{poort}/golf-score/golf-score.html'

    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); await pg.goto(url); await pg.evaluate("navigator.serviceWorker.ready"); await pg.wait_for_timeout(1200)
        await pg.evaluate("""(c) => { localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_profile_hcp', '30.7'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(800)
        await pg.evaluate("() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }")
        await pg.wait_for_timeout(400)
        await pg.evaluate("() => { nav('score'); for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, 1); } setCurrentHole(3); window.__zelfdePagina = 1; }")

        print("\n=== 1. NIEUWE VERSIE TIJDENS EEN RONDE, MET EEN WACHTENDE TIK ===\n")
        zet_versie(wortel, 'golf-score-proef-2', '13527DA-F02')
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())"); await pg.wait_for_timeout(2500)
        st = await pg.evaluate(STAND)
        check("de nieuwe versie wacht", st['wacht'], True)
        check("de app is niet herladen en draait nog versie 1", (st['herladen'], st['versie']), (False, 'Versie 13527DA-F01'))
        check("de ronde loopt met de scores", (st['ronde'], st['scores']), (True, 3))
        check("de melding staat er", 'Nieuwe versie' in st['melding'], True)
        check("het invoerscherm staat nog open", await pg.evaluate("() => document.querySelector('.screen.active').id"), 'screen-score')

        print("\n=== 2. BROWSER BEWAART NIETS: NIET VERVERSEN ===\n")
        await pg.evaluate("() => { storageIsPersistent = false; updateBannerKlik(); }"); await pg.wait_for_timeout(3500)
        st = await pg.evaluate(STAND)
        check("niet herladen en nog steeds wachtend", (st['herladen'], st['wacht']), (False, True))
        check("met uitleg", await pg.evaluate("() => document.getElementById('confirmModalTitle').textContent"), 'Niet verversen')
        await pg.evaluate("() => { storageIsPersistent = true; document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); }")

        print("\n=== 3. OFFLINE OP DE MELDING TIKKEN ===\n")
        uit()
        # een score die nog op bevestiging wacht (de tik vervalt anders na 2 seconden)
        await pg.evaluate("() => { setCurrentHole(3); armScoreChange(3, 5); }")
        await pg.click('#updateBanner'); await pg.wait_for_timeout(3500)
        st = await pg.evaluate(STAND)
        check("de app is herladen en draait versie 2", (st['herladen'], st['versie']), (True, 'Versie 13527DA-F02'))
        check("niets wacht meer; alleen de cache van versie 2", (st['wacht'], await pg.evaluate(CACHE_HTML)), (False, {'golf-score-proef-2': '13527DA-F02'}))
        # Sinds 13527DA-140: een tik die nog op bevestiging wacht, geldt als niet bevestigd en
        # wordt bij het verversen teruggedraaid (net als na 2 seconden zonder bevestiging).
        check("de ronde loopt door met de bevestigde scores; de onbevestigde tik is teruggedraaid", (st['ronde'], st['scores']), (True, 3))
        await pg.evaluate("() => { window.__zelfdePagina = 1; }"); await pg.wait_for_timeout(2000)
        check("daarna herlaadt hij niet vanzelf nog eens", (await pg.evaluate(STAND))['herladen'], False)

        print("\n=== 4. UPDATE WAARBIJ DE VERBINDING WEGVALT ===\n")
        aan(poort); zet_versie(wortel, 'golf-score-proef-3', '13527DA-F03'); STORING['html'] = True
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update()).catch(() => {})"); await pg.wait_for_timeout(2500)
        STORING['html'] = False
        st = await pg.evaluate(STAND)
        check("niets wachtends, geen herladen, de app werkt door op versie 2", (st['wacht'], st['herladen'], st['versie'], st['scores']), (False, False, 'Versie 13527DA-F02', 3))

        print("\n=== 5. ZONDER TIK: PAS NA HELEMAAL SLUITEN ===\n")
        zet_versie(wortel, 'golf-score-proef-4', '13527DA-F04')
        await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())"); await pg.wait_for_timeout(2500)
        check("versie 4 wacht, de app draait versie 2", ((await pg.evaluate(STAND))['wacht'], (await pg.evaluate(STAND))['versie']), (True, 'Versie 13527DA-F02'))
        await pg.close(); await asyncio.sleep(1.5)
        uit()
        pg = await ctx.new_page(); await pg.goto(url); await pg.wait_for_timeout(1500)
        st = await pg.evaluate(STAND)
        check("na helemaal sluiten opent offline versie 4, de ronde loopt door", (st['wacht'], st['ronde'], st['scores'], list(await pg.evaluate(CACHE_HTML))), (False, True, 3, ['golf-score-proef-4']))
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
