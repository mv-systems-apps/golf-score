"""Na de eerste tik op Gereed staat 'Tik nogmaals om te bevestigen' in de knop. Op 320 px
wordt die twee regels hoog en viel de onderste regel achter de tabbalk (review dagelijks
gebruik 2, 13528FE-001). Nu schuift het scherm net zo ver op dat de hele knop te zien is;
op 360 px (één regel) verschuift er niets. Met echte tikken; de scores via de app zelf
ingevuld (het tikken van negen holes test test-wedstrijd en de reviewer al).
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

STAND = """() => { const k = document.getElementById('finishRoundBtn').getBoundingClientRect(), t = document.querySelector('.tabs').getBoundingClientRect();
  return { boven: k.bottom <= t.top + 0.5, label: document.getElementById('finishRoundLabel').textContent, y: Math.round(scrollY) }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in (320, 360):
            print(f"\n=== {w} px ===\n")
            ctx = await b.new_context(viewport={'width': w, 'height': 680}, has_touch=True, is_mobile=True)
            pg = await ctx.new_page(); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
            await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(600)
            try:
                await pg.click('#startRoundBtn'); await pg.wait_for_timeout(800)
                await pg.evaluate("() => { game.holes.forEach(h => { h.score = (h.par || 4) + 1; }); saveActiveRound(); renderScore(); }"); await pg.wait_for_timeout(300)
                await pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(200)
                voor = await pg.evaluate(STAND)
                await pg.locator('#finishRoundBtn').click(); await pg.wait_for_timeout(300)
                na = await pg.evaluate(STAND)
                check(f"{w} px: voor de tik Gereed, helemaal boven de tabbalk", [voor['label'], voor['boven']], ['Gereed', True])
                check(f"{w} px: na de eerste tik de hele knop boven de tabbalk", [na['label'], na['boven']], ['Tik nogmaals om te bevestigen', True])
                if w == 360:
                    hoog = await pg.evaluate("() => document.getElementById('finishRoundLabel').getClientRects().length")
                    if hoog == 1: check("360 px, de tekst op één regel: het scherm verschuift niet", na['y'], voor['y'])
            except Exception as e:
                check(f"{w} px: de ronde", 'FOUT: ' + str(e).split('\n')[0][:120], 'gelukt')
            check(f"{w} px: geen paginafouten", pf, [])
            await ctx.close()
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
