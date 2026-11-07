"""Eén tik op een spelerkop klapt hem in of uit (1352898-031).

Een speler zonder eerdere keuze hoort dicht te zijn (zo rekent wisselIngeklapt), maar
werd open getekend. De eerste tik zette hem dan op 'open' — er veranderde niets — en pas
de tweede tik klapte hem dicht. Dat gebeurt bijvoorbeeld na eerst
groeperen op club (die maakt de stand per speler leeg) en daarna op speler.

De test volgt die route: elke speler moet dicht getekend zijn, één tik moet de stand
zichtbaar veranderen, en een tweede tik moet hem terugzetten.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, RONDES

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

STAND = """() => [...document.querySelectorAll('#screen-archive [data-inklap="_pgCollapsed"]')]
  .map(k => k.dataset.sleutel + ':' + (k.nextElementSibling.classList.contains('hidden') ? 'dicht' : 'open'))"""
TIK = """(s) => document.querySelector(`#screen-archive [data-inklap="_pgCollapsed"][data-sleutel="${s}"]`).click()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('archive'); }")
        await pg.wait_for_timeout(300)

        await pg.evaluate("() => { openQuickClub(); openQuickLast20(); }")
        await pg.wait_for_timeout(300)
        voor = await pg.evaluate(STAND)
        print('  na club → speler:', voor)
        check("er zijn spelerkoppen", len(voor) >= 2, True)
        check("zonder eerdere keuze zijn ze dicht", all(r.endswith(':dicht') for r in voor), True)
        for regel in voor:
            sleutel = regel.split(':')[0]
            await pg.evaluate(TIK, sleutel); await pg.wait_for_timeout(100)
            na1 = [r for r in await pg.evaluate(STAND) if r.startswith(sleutel + ':')][0]
            await pg.evaluate(TIK, sleutel); await pg.wait_for_timeout(100)
            na2 = [r for r in await pg.evaluate(STAND) if r.startswith(sleutel + ':')][0]
            check(f"{sleutel}: één tik verandert de stand, een tweede zet hem terug",
                  [na1 != regel, na2], [True, regel])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
