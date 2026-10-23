"""Namen met een '|' erin (1352898-015).

De app gebruikte op een paar plekken 'naam|naam' als sleutel en knipte die later weer op '|'.
Een baan- of teenaam met een '|' gaf dan:
  1. bij een wedstrijdlus een fout: de tee werd onder de verkeerde naam gezocht;
  2. in de spelanalyse een verkeerde naam ('Noord (Oost)' in plaats van 'Noord|Oost (club)').
Nu zijn die sleutels een JSON-lijst, die heel blijft wat de namen ook bevatten. Hetzelfde
voor de sleutel per hole (club, baan, holenummer) en die van whsStand.
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

async def main():
    clubs = json.loads(json.dumps(CLUBS))
    club = clubs['Golfclub Heelsum']
    for baan in ('Airborne', 'Sandr'):
        h = club['courses'][baan]['tees']['Heren']
        h['Geel|kort'] = json.loads(json.dumps(h['Blauw']))
    rs = []
    for i in range(6):
        r = ronde(300 + i, f'2026-03-{i + 1:02d}', baan='Airborne'); r['track'] = 'Noord|Oost'; r['tee'] = 'Geel|kort'; r['sdFinal'] = 20.0; rs.append(r)
        r = ronde(400 + i, f'2026-04-{i + 1:02d}', baan='Sandr'); r['sdFinal'] = 30.0; r['tee'] = 'Blauw'; rs.append(r)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [clubs, rs])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)

        print("\n=== 1. WEDSTRIJDLUS MET EEN TEE 'Geel|kort' ===\n")
        uit = await pg.evaluate("""() => { try {
            const l = berekenLus('Golfclub Heelsum', [{ baan: 'Airborne', idx: 0 }, { baan: 'Sandr', idx: 1 }]);
            return { tees: Object.keys(l.tees.Heren || {}).sort(), cr: l.tees.Heren['Geel|kort'] ? l.tees.Heren['Geel|kort'].CR : null };
          } catch (e) { return { fout: e.message }; } }""")
        check("de lus is te berekenen", uit.get('fout'), None)
        check("de lus kent de tee 'Geel|kort' naast Blauw", uit.get('tees'), ['Blauw', 'Geel|kort'])
        check("en die heeft een course rating", uit.get('cr') is not None, True)

        print("\n=== 2. SPELANALYSE: BEST EN LASTIGST ===\n")
        tekst = await pg.evaluate("() => { const a = buildGameAnalysis(); return typeof a === 'string' ? a : JSON.stringify(a); }")
        check("beste baan: 'Noord|Oost (Golfclub Heelsum)'", 'Noord|Oost (Golfclub Heelsum)' in tekst, True)
        check("beste tee: 'Geel|kort op Noord|Oost (Golfclub Heelsum)'", 'Geel|kort op Noord|Oost (Golfclub Heelsum)' in tekst, True)

        print("\n=== 3. SLEUTEL PER HOLE ===\n")
        uit = await pg.evaluate("""() => [holeSleutel({ club: 'A|B', track: 'C' }, 0) !== holeSleutel({ club: 'A', track: 'B|C' }, 0),
                                       holeSleutel({ club: 'A', track: 'B' }, 0) === holeSleutel({ club: 'A', track: 'B' }, 0)]""")
        check("club 'A|B' baan 'C' en club 'A' baan 'B|C' vallen niet samen; gelijke namen wel", uit, [True, True])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
