"""Een import overschrijft geen ronde die nog loopt.

Gevonden in de onafhankelijke review van 13527DA-13D: liep er een ronde en importeerde je
een ronde van dezelfde speler op dezelfde datum en tijd, dan bood de app aan hem te
overschrijven. Na 'Opslaan' stond alleen de geïmporteerde in de opslag, maar de oude
ronde bleef in het geheugen op het scorescherm staan. De volgende tik zette hem er weer
bij: twee rondes op hetzelfde tijdstip, en het bevestigde overschrijven was ongedaan.

De regel: een lopende ronde (of de ronde op het scorescherm) wordt niet overschreven; de
app zegt waarom en verandert niets. Is de ronde niet meer lopend, dan kan het wel.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def bestand(inhoud):
    pad = os.path.join(tempfile.mkdtemp(), 'ronde.json')
    json.dump(inhoud, open(pad, 'w', encoding='utf-8'), ensure_ascii=False); return pad
OPSLAG = "() => JSON.parse(localStorage.getItem('golf_rounds')).map(r => [r.player, r.date, r.time, r.holes.filter(h => h.score !== null).length]).sort()"
VENSTER = """() => { const m = document.getElementById('confirmModal'); return m.classList.contains('hidden') ? '' : document.getElementById('confirmModalTitle').textContent; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_profile_hcp', '30.7');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600)
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; startRound(); const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(400)
        await pg.evaluate("() => { nav('score'); for (let i = 0; i < 2; i++) { setCurrentHole(i); stepScore(i, 1); } }"); await pg.wait_for_timeout(300)
        lopend = await pg.evaluate("() => { const r = JSON.parse(localStorage.getItem('golf_rounds'))[0]; return r; }")
        imp = {k: lopend[k] for k in ('date', 'time', 'player', 'hcp', 'club', 'clubShort', 'track', 'gender', 'tee', 'CR', 'SR', 'PAR', 'chcp', 'qualifying')}
        imp['holes'] = [dict(h, score=h['par'] + 1, putts=2) for h in lopend['holes']]
        voor = await pg.evaluate(OPSLAG)

        print("\n=== 1. IMPORT TERWIJL DE RONDE LOOPT ===\n")
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importRoundFile').set_input_files(bestand(imp)); await pg.wait_for_timeout(500)
        venster = await pg.evaluate(VENSTER)
        check("de app weigert met uitleg", venster, 'Ronde loopt nog')
        # Biedt een (oudere) versie toch overschrijven aan, dan bevestigen zoals de gebruiker zou doen.
        if venster == 'Ronde bestaat al': await pg.evaluate("() => document.getElementById('confirmModalBtn').click()"); await pg.wait_for_timeout(400)
        else: await pg.evaluate("() => closeConfirmModal()")
        check("de opslag is onveranderd (de lopende ronde met 2 scores)", await pg.evaluate(OPSLAG), voor)
        await pg.evaluate("() => { nav('score'); setCurrentHole(2); stepScore(2, 1); }"); await pg.wait_for_timeout(300)
        na = await pg.evaluate(OPSLAG)
        check("na een volgende tik: één ronde, met 3 scores", na, [['Mark', lopend['date'], lopend['time'], 3]])

        print("\n=== 2. NA PAUZEREN KAN HET WEL ===\n")
        await pg.evaluate("() => { finishActiveRound(null); }"); await pg.wait_for_timeout(400)
        check("de ronde loopt niet meer", await pg.evaluate("() => [game.started, localStorage.getItem('golf_active_id')]"), [False, None])
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importRoundFile').set_input_files(bestand(imp)); await pg.wait_for_timeout(500)
        check("overschrijven wordt aangeboden", await pg.evaluate(VENSTER), 'Ronde bestaat al')
        await pg.evaluate("() => document.getElementById('confirmModalBtn').click()"); await pg.wait_for_timeout(500)
        check("één ronde: de geïmporteerde, volledig ingevuld", await pg.evaluate(OPSLAG), [['Mark', lopend['date'], lopend['time'], 9]])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
