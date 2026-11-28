"""De knoppenrij bovenin Rondes past op een smal scherm (review dagelijks gebruik 2,
13528FE-001): tot dan viel de eerste knop (Geplande rondes) op 320 px 8 px en op 300 px 28 px
links buiten beeld, en de rij scrolt niet. Nu gaat wat niet past (de zoekknop) naar een
volgende regel, rechts; de knoppen houden hun maat (46 px). Op 360 px een regel, als voorheen.
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

MEET = """() => { const k = [...document.querySelectorAll('#groupByPlannedBtn, #groupByPlannedBtn ~ button')].filter(b => b.offsetParent);
  const sw = document.documentElement.clientWidth;
  return { n: k.length, binnen: k.every(b => { const r = b.getBoundingClientRect(); return r.left >= 0 && r.right <= sw; }),
    breed: k.map(b => Math.round(b.getBoundingClientRect().width)),
    regels: [...new Set(k.map(b => Math.round(b.getBoundingClientRect().top)))].length,
    zoekRechts: (z => !!z && Math.abs(z.getBoundingClientRect().right - k[0].parentElement.getBoundingClientRect().right) <= 1)(document.getElementById('archiveSearchBtn')),
    midden: k.every(b => { const r = b.getBoundingClientRect(), i = b.querySelector('svg').getBoundingClientRect();
      return Math.abs((i.left + i.right) / 2 - (r.left + r.right) / 2) <= 1 && Math.abs((i.top + i.bottom) / 2 - (r.top + r.bottom) / 2) <= 1.5; }) }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 740})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        for w in (360, 320, 300):
            await pg.set_viewport_size({'width': w, 'height': 740}); await pg.wait_for_timeout(200)
            m = await pg.evaluate(MEET)
            check(f"{w} px: zes knoppen, alle binnen het scherm, icoon in het midden, niets gekrompen (46 px)", [m['n'], m['binnen'], m['midden'], m['breed']], [6, True, True, [46] * 6])
            check(f"{w} px: " + ('een regel' if w == 360 else 'twee regels, de zoekknop rechts'), [m['regels'], m['zoekRechts']], [1 if w == 360 else 2, True])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
