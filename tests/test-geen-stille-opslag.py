"""Geen verborgen bijwerkingen bij de clubs (1352898-017).

  1. Het starten schrijft de clubs niet weg. Tot 016 deed rebuildCourseLookup() dat bij elke
     start (standaard opslaan = true), en haalde zo een baan zonder holes stil en voorgoed
     uit de opslag. Nu: die baan staat niet in beeld, maar blijft in de opslag tot de
     eerstvolgende echte clubwijziging.
  2. Een ronde van een andere club herplannen kiest die club: de banenlijst wordt één keer
     opgebouwd en de clubs worden niet weggeschreven (tot 016: twee keer, plus opslaan).
  3. Een club kiezen op Start: één keer opbouwen, niets wegschrijven.
  4. Een echte clubwijziging (een club verwijderen) wordt wel opgeslagen.

De schrijfacties worden geteld vóór het script van de app draait (Storage.prototype).
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

TEL = """(() => {
  window.__schrijf = {};
  const s = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { window.__schrijf[k] = (window.__schrijf[k] || 0) + 1; return s.call(this, k, v); };
})()"""
OPBOUW = """() => { window.__opbouw = 0; window.__echtRB = window.__echtRB || rebuildCourseLookup;
  window.rebuildCourseLookup = (...a) => { window.__opbouw++; return window.__echtRB(...a); }; window.__schrijf = {}; }"""

async def main():
    clubs = json.loads(json.dumps(CLUBS))
    clubs['Golfclub Heelsum']['courses']['Leeg'] = {'tees': {}, 'holeIds': []}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        await ctx.add_init_script(TEL)
        pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        r = ronde(1, '2027-01-01', baan='Noord', club='Papendal', kort='Pap', tee='Wit', played=0, putts=False)
        await pg.evaluate(SEED, [clubs, [ronde(2, '2026-01-02'), r]])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(800)

        print("\n=== 1. STARTEN ===\n")
        check("het starten schrijft de clubs niet weg", await pg.evaluate("() => window.__schrijf.golf_clubs || 0"), 0)
        check("de baan zonder holes staat niet in beeld", await pg.evaluate("() => 'Leeg' in CLUBS['Golfclub Heelsum'].courses"), False)
        check("maar blijft in de opslag", await pg.evaluate("() => 'Leeg' in JSON.parse(localStorage.getItem('golf_clubs'))['Golfclub Heelsum'].courses"), True)

        print("\n=== 2. HERPLANNEN VAN EEN RONDE VAN EEN ANDERE CLUB ===\n")
        await pg.evaluate(OPBOUW)
        await pg.evaluate("() => herplanRonde(1)"); await pg.wait_for_timeout(300)
        uit = await pg.evaluate("() => [storage.getItem('golf_default_club'), window.__opbouw, window.__schrijf.golf_clubs || 0, Object.keys(COURSES)]")
        check("de club van de ronde is gekozen, met zijn banen", [uit[0], uit[3]], ['Papendal', ['Noord']])
        check("de banenlijst één keer opgebouwd", uit[1], 1)
        check("de clubs niet weggeschreven", uit[2], 0)
        await pg.evaluate("() => { annuleerHerplan(); document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); }")

        print("\n=== 3. EEN CLUB KIEZEN OP START ===\n")
        await pg.evaluate(OPBOUW)
        await pg.evaluate("() => setDefaultClub('Golfclub Heelsum')"); await pg.wait_for_timeout(200)
        uit = await pg.evaluate("() => [window.__opbouw, window.__schrijf.golf_clubs || 0, Object.keys(COURSES).sort()]")
        check("de banen van de gekozen club", uit[2], ['Airborne', 'Sandr'])
        check("de banenlijst één keer opgebouwd", uit[0], 1)
        check("de clubs niet weggeschreven", uit[1], 0)

        print("\n=== 4. EEN ECHTE CLUBWIJZIGING WORDT WEL OPGESLAGEN ===\n")
        await pg.evaluate("() => { window.__schrijf = {}; editorClub = 'Papendal'; const btn = document.createElement('button'); btn.dataset.confirm = '1'; }")
        await pg.evaluate("() => { CLUBS['__nieuw__1'] = { club: '', shortName: '', courses: { Proef: JSON.parse(JSON.stringify(CLUBS['Papendal'].courses.Noord)) } }; saveClubsToStorage(); editorClub = '__nieuw__1'; cleanupTempClub(); }")
        check("een tijdelijke club met een baan opruimen: weggeschreven", await pg.evaluate("() => '__nieuw__1' in JSON.parse(localStorage.getItem('golf_clubs'))"), False)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
