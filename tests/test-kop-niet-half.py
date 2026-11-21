"""De gouden kop Geplande rondes staat na Sluiten en na Opslaan in Ronde bewerken niet half
onder de vaste kop van het scherm (review dagelijks gebruik 2, 13528FE-001). Tot dan gold dat
alleen na een tik in de agendastrook. Met echte tikken: een ronde met twee spelers plannen,
op het scorescherm Sluiten, en daarna Ronde bewerken en Opslaan; op 360, 320 en 300 px.
"""
import asyncio, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
HALF = """() => { const kop = document.querySelector('#scoreEmptyMsg .lege-kop[data-kop="gepland"]'), hdr = document.querySelector('header');
  if (!kop || !hdr) return 'niet gevonden'; const k = kop.getBoundingClientRect(), h = hdr.getBoundingClientRect().bottom;
  return k.bottom <= h + 0.5 ? 'weg' : k.top >= h - 0.5 ? 'heel' : 'half'; }"""

async def stap(pg, naam, fn):
    try: await fn()
    except Exception as e: check(naam, 'FOUT: ' + str(e).split('\n')[0][:100], 'gelukt')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in (360, 320, 300):
            print(f"\n=== {w} px ===\n")
            ctx = await b.new_context(viewport={'width': w, 'height': 680}, has_touch=True, is_mobile=True)
            pg = await ctx.new_page(); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
            await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(600)
            async def plan():
                await pg.click('#addPlayer2Btn'); await pg.wait_for_timeout(200)
                await pg.fill('#iName2', 'Medespeler'); await pg.fill('#iHcp2', '20.4'); await pg.locator('#iHcp2').blur()
                await pg.fill('#iDate', dag(2)); await pg.dispatch_event('#iDate', 'change')
                await pg.fill('input[type=time]', '10:30')
                await pg.click('#startRoundBtn'); await pg.wait_for_timeout(700)
                await pg.locator('#finishRoundLabel').click(); await pg.wait_for_timeout(800)
            await stap(pg, 'plannen en Sluiten', plan)
            check(f"{w} px, na Sluiten: de gouden kop niet half", await pg.evaluate(HALF) in ('heel', 'weg'), True)
            async def bewerk():
                await pg.locator('#scoreEmptyMsg .lege-open .lege-knop-bewerk').first.click(); await pg.wait_for_timeout(400)
                await pg.get_by_role('button', name='Ronde bewerken').click(); await pg.wait_for_timeout(500)
                await pg.get_by_role('button', name='Opslaan').filter(visible=True).first.click(); await pg.wait_for_timeout(800)
            await stap(pg, 'Ronde bewerken en Opslaan', bewerk)
            check(f"{w} px, na Opslaan: de gouden kop niet half", await pg.evaluate(HALF) in ('heel', 'weg'), True)
            check(f"{w} px: geen paginafouten", pf, [])
            await ctx.close()
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
