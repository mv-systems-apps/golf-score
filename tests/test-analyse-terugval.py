"""'Analyseer mijn spel' zonder opvallende zwakke plek (1352898-026).

Springt er niets uit de cijfers, dan komt er één aanbeveling over het par-type waarop je
over al je rondes de meeste slagen verliest (topKost). Sinds 026 bestaat de analyse uit
losse onderdelen; topKost komt uit analyseParTypen en wordt pas aan het eind gelezen.
Geen andere test kwam langs deze route: de gewone testrondes geven altijd wel een
aanbeveling.

Rondes waarin niets opvalt: elke hole precies op de persoonlijke par (par + 1 slag),
hetzelfde dagresultaat elke week, één baan, geen putts, en minder dan 20 rondes (bij 20
gelijke rondes volgt een aanbeveling uit 'Stabiliteit'). Op de Airborne zijn vijf van de
negen holes par 4, dus daar zitten de meeste slagen boven par: 5 per ronde.

Deze test geeft op 025 en 026 hetzelfde; hij faalt als analyseParTypen topKost niet
teruggeeft of als buildGameAnalysis hem niet doorgeeft.
"""
import asyncio, os, sys, datetime
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
N = 12
RONDES = []
for i in range(N):
    d = (datetime.date(2026, 3, 7) + datetime.timedelta(weeks=i)).isoformat()
    r = ronde(i + 1, d, scores=[p + 1 for p in PARS], putts=False)
    r['sd'] = r['sdFinal'] = 30.0
    RONDES.append(r)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.reload(); await pg.wait_for_timeout(500)
        a = await pg.evaluate("() => { _statChartPeriod = 'alles'; return buildGameAnalysis(); }")
        koppen = [s['kop'] for s in a['secties']]
        print('  secties:', ', '.join(koppen))
        check("de analyse heeft een sectie Par-typen", 'Par-typen' in koppen, True)
        check("precies één aanbeveling", len(a['aanbev']), 1)
        tekst = a['aanbev'][0] if a['aanbev'] else ''
        check("het is de aanbeveling over het duurste par-type",
              tekst.startswith('Er springt geen duidelijke zwakke plek uit de cijfers.'), True)
        check("die noemt de par 4's met 60 slagen boven par",
              "op de par 4's (60 boven par bij elkaar)" in tekst, True)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
