"""De holesknoppen op Start (eindcontrole 13528FF-001): '9 holes' en '18 holes' staan op één
regel als ze allebei passen; moet er één afbreken, dan allebei, als getal met 'holes' eronder.
Tot dan brak op 360 px alleen '18 holes' af. Gemeten op 412, 360 en 320 px, ook na een
andere breedte terwijl Start open is.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

REGELS = """() => ['cat-9', 'cat-18'].map(id => { const k = document.getElementById(id), r = document.createRange(); r.selectNodeContents(k);
  return new Set([...r.getClientRects()].filter(x => x.width > 1).map(x => Math.round(x.top))).size; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 412, 'height': 900})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        for w, verwacht in ((412, [1, 1]), (360, [2, 2]), (320, [2, 2]), (412, [1, 1])):
            await pg.set_viewport_size({'width': w, 'height': 900}); await pg.wait_for_timeout(250)
            check(f"{w} px: 9 holes en 18 holes allebei op " + ('één regel' if verwacht == [1, 1] else 'twee regels'), await pg.evaluate(REGELS), verwacht)
        check("de knoppen even breed", await pg.evaluate("() => new Set([...document.getElementById('catBtns').children].map(k => Math.round(k.getBoundingClientRect().width))).size"), 1)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
