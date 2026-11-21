"""Beginnen bij persoonlijke par.

De schakelaar 'Beginnen bij persoonlijke par' (Instellingen, Tijdens de ronde; sleutel
golf_start_ppar, standaard uit). Uit: de eerste tik op een lege hole geeft met + bogey en
met − par, zoals altijd. Aan: + geeft de persoonlijke par (par + slagen), − één minder.
Daarna één slag per tik. Een hole zonder slagengetal valt terug op het oude gedrag. De
keuze blijft bewaard na herladen.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, kreeg, verwacht):
    if kreeg == verwacht: print(f"  ok   {naam}: {kreeg!r}")
    else: print(f"  FOUT {naam}: {kreeg!r} — verwacht {verwacht!r}"); fouten.append(naam)

# Op elke hole van een verse ronde een tik (+ of −), en per hole wat er staat en wat hoort.
TIKKEN = """(d) => { if (!(game && game.started && game.holes.length && game.holes.every(h => h.score === null))) throw new Error('geen verse ronde');
  return game.holes.map((h, i) => { setCurrentHole(i); stepScore(i, d); return [h.score, h.par, h.ppar, h.phcp]; }); }"""

UUR = [6]
async def start(pg):
    # Een verse ronde vanaf Start, elke keer op een ander uur (anders: 'Dubbele datum & tijd').
    UUR[0] += 1
    await pg.evaluate("(u) => { nav('setup'); const t = document.getElementById('iTime'); t.value = String(u).padStart(2, '0') + ':00'; onDateTimeChange(); }", UUR[0])
    await pg.click('#startRoundBtn'); await pg.wait_for_timeout(300)
    await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
    await pg.wait_for_timeout(300)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)

        print("\n=== 1. STANDAARD UIT: ZOALS ALTIJD ===\n")
        check("de schakelaar staat uit", await pg.evaluate("document.getElementById('startPparToggle').checked"), False)
        await start(pg); r = await pg.evaluate(TIKKEN, 1)
        check("er zijn holes, ook met slagen (anders test dit niets)", (len(r) > 0, any(x[3] > 0 for x in r)), (True, True))
        check("+: bogey op elke hole", all(x[0] == x[1] + 1 for x in r), True)
        await pg.evaluate("() => { finishActiveRound(); }")
        await start(pg); r = await pg.evaluate(TIKKEN, -1)
        check("−: par op elke hole", all(x[0] == x[1] for x in r), True)
        await pg.evaluate("() => { finishActiveRound(); }")

        print("\n=== 2. AAN: PERSOONLIJKE PAR ===\n")
        await pg.evaluate("nav('settings')")
        await pg.evaluate("() => { const c = document.getElementById('startPparToggle'); c.checked = true; c.dispatchEvent(new Event('change')); }")
        check("bewaard als 'on'", await pg.evaluate("localStorage.getItem('golf_start_ppar')"), 'on')
        await start(pg); r = await pg.evaluate(TIKKEN, 1)
        check("+: de persoonlijke par op elke hole", all(x[0] == x[1] + x[3] for x in r), True)
        check("en dat is het veld ppar van de hole", all(x[0] == x[2] for x in r), True)
        await pg.evaluate("() => { finishActiveRound(); }")
        await start(pg)
        nog = await pg.evaluate("() => { setCurrentHole(0); stepScore(0, 1); stepScore(0, 1); return game.holes[0].score - game.holes[0].ppar; }")
        check("de tweede tik: één slag erbij", nog, 1)
        await pg.evaluate("() => { finishActiveRound(); }")
        await start(pg); r = await pg.evaluate(TIKKEN, -1)
        check("−: één onder de persoonlijke par", all(x[0] == x[1] + x[3] - 1 for x in r), True)
        await pg.evaluate("() => { finishActiveRound(); }")

        print("\n=== 3. ZONDER SLAGENGETAL EN NA HERLADEN ===\n")
        await start(pg)
        z = await pg.evaluate("""() => { const h = game.holes[0]; delete h.phcp; setCurrentHole(0); stepScore(0, 1);
            return [h.score, h.par + 1]; }""")
        check("hole zonder slagengetal: bogey, geen NaN", z[0], z[1])
        await pg.evaluate("() => { finishActiveRound(); }")
        await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("nav('settings')")
        check("na herladen staat de schakelaar nog aan", await pg.evaluate("document.getElementById('startPparToggle').checked"), True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ", ".join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
