"""Twee vensters tegelijk open (de geïnstalleerde app en een tabblad in Chrome).

Gevonden in de onafhankelijke review van 13527DA-13D:
  a. Beide vensters hebben dezelfde lopende ronde. In A vul je hole 3 in; venster B meldt
     'Bijgewerkt in ander tabblad', maar houdt de oude stand in het geheugen. Een tik in B
     schreef de hele ronde terug, zonder hole 3.
  b. Rondt A de ronde af, dan zette de volgende tik in B hem weer terug als lopende ronde.
  c. In A staat het bewerkvenster van ronde Y open (een plaats in de lijst). B voegt een
     ronde toe, de plaatsen schuiven op, en Verwijderen in A wiste ronde X.

De regels: een venster neemt na een wijziging elders de stand van de opslag over; een
ronde die elders niet meer loopt, staat hier niet meer op het scorescherm; open vensters
houden vast aan de ronde, niet aan de plaats in de lijst.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

SCORES = "() => { const r = JSON.parse(localStorage.getItem('golf_rounds')).find(r => String(r.id) === localStorage.getItem('golf_active_id')); return r ? r.holes.map(h => h.score) : null; }"
def ronde(id_, dag, speler='Testspeler'):
    return {"id": id_, "date": f"2026-05-{dag:02d}", "time": "10:00", "player": speler, "hcp": 30.7, "club": "Golfclub Heelsum", "track": "Airborne", "tee": "Blauw",
            "gender": "Heren", "CR": 34.5, "SR": 120, "PAR": 36, "chcp": 15, "qualifying": True,
            "holes": [{"id": str(i + 1), "par": p, "si": i + 1, "phcp": 2 if i < 6 else 1, "score": p + 1} for i, p in enumerate([4, 3, 5, 4, 4, 3, 4, 5, 4])]}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844})
        A = await ctx.new_page(); pf = []; A.on('pageerror', lambda e: pf.append('A ' + str(e)[:120]))
        await A.goto(app_url())
        await A.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", CLUBS)
        await A.reload(); await A.wait_for_timeout(600)
        await A.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; startRound(); const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); for (let i = 0; i < 2; i++) { setCurrentHole(i); stepScore(i, 1); } }""")
        await A.wait_for_timeout(300)
        B = await ctx.new_page(); B.on('pageerror', lambda e: pf.append('B ' + str(e)[:120]))
        await B.goto(app_url()); await B.wait_for_timeout(700)
        await B.evaluate("() => nav('score')")
        check("B heeft dezelfde lopende ronde", await B.evaluate("() => [game.started, game.holes.filter(h => h.score !== null).length]"), [True, 2])

        print("\n=== a. A VULT HOLE 3 IN, DAARNA TIKT B OP HOLE 4 ===\n")
        await A.evaluate("() => { setCurrentHole(2); stepScore(2, 1); }"); await A.wait_for_timeout(400)
        await B.evaluate("() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
        await B.evaluate("() => { setCurrentHole(3); stepScore(3, 1); }"); await B.wait_for_timeout(400)
        s = await A.evaluate(SCORES)
        check("hole 3 (uit A) en hole 4 (uit B) staan er allebei", [x is not None for x in s[:4]], [True, True, True, True])

        print("\n=== b. A RONDT AF, DAARNA TIKT B ===\n")
        await A.evaluate("() => { for (let i = 4; i < 9; i++) { setCurrentHole(i); stepScore(i, 1); } finishActiveRound(null); }"); await A.wait_for_timeout(500)
        check("in B staat de ronde niet meer op het scorescherm", await B.evaluate("() => game.started"), False)
        await B.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); try { setCurrentHole(0); stepScore(0, 1); } catch (e) {} }"); await B.wait_for_timeout(400)
        check("een tik in B zet hem niet terug als lopende ronde", await A.evaluate("() => localStorage.getItem('golf_active_id')"), None)
        check("er is precies één ronde, afgerond", await A.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds')).map(r => r.holes.every(h => h.score !== null))"), [True])

        print("\n=== c. A HEEFT HET BEWERKVENSTER VAN Y OPEN, B VOEGT EEN RONDE TOE, A VERWIJDERT ===\n")
        await A.evaluate("(r) => { localStorage.setItem('golf_rounds', JSON.stringify(r)); _rondesCache = null; tekenRondelijst(); }", [ronde(1, 1), ronde(2, 2), ronde(3, 3)])
        await B.reload(); await B.wait_for_timeout(500)
        y = await A.evaluate("() => { const lijst = loadSavedRounds(); return lijst.findIndex(r => r.id === 2); }")
        await A.evaluate("(i) => { nav('archive'); doOpenRoundInfoModal(i); }", y); await A.wait_for_timeout(300)
        # B voegt vooraan een ronde toe (zoals een import of een nieuwe ronde doet)
        await B.evaluate("(r) => { const lijst = loadSavedRounds(); lijst.unshift(r); localStorage.setItem('golf_rounds', JSON.stringify(lijst)); }", ronde(9, 20))
        await A.wait_for_timeout(400)
        await A.evaluate("() => document.getElementById('confirmModal').classList.add('hidden')")
        # Verwijderen met de echte knop: twee tikken, dan bevestigen in het rode venster
        knop = A.locator('#roundInfoModal button[onclick="deleteRoundFromInfoModal(this)"]')
        await knop.click(); await knop.click(); await A.wait_for_timeout(200)
        await A.click('#dangerModalConfirmBtn'); await A.wait_for_timeout(400)
        check("ronde Y (id 2) is verwijderd, de rest staat er nog", sorted(await A.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds')).map(r => r.id)")), [1, 3, 9])
        check("geen fouten in de pagina's", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
