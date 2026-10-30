"""De handicap wordt per speeldag bijgewerkt (1352898-013).

Rules of Handicapping 2024: speel je op één dag meer rondes, dan gold bij elk de index van
het begin van die dag (regel 5.4); een uitzonderlijke score vergelijkt met de index die gold
toen je speelde (5.9); de Low HI komt uit de 365 dagen vóór de dag van je laatste ronde (5.7).

Tot 012 rekende de app per ronde: de tweede ronde van een dag vergeleek met de index van
ná de eerste. Hier: twintig rondes met dagresultaat 20,0 (index 20,0), dan op één dag
14,0 en 12,9. Tegen 20,0 is 12,9 een uitzonderlijke score (7,1 beter, −1,0); tegen de
tussenstand 19,3 niet (6,4 beter).

Het nagerekende verloop over honderden willekeurige reeksen, met rondes op dezelfde dag,
staat in test-handicapverloop.js.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        rs = []
        for i in range(20):
            r = ronde(900 + i, f'2026-01-{i + 1:02d}'); r['sdFinal'] = 20.0; rs.append(r)
        a = ronde(950, '2026-02-01'); a['time'] = '09:00'; a['sdFinal'] = 14.0
        bb = ronde(951, '2026-02-01'); bb['time'] = '14:00'; bb['sdFinal'] = 12.9
        rs += [a, bb]
        rs.reverse()
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, rs])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(600)

        print("\n=== TWEE RONDES OP ÉÉN DAG ===\n")
        uit = await pg.evaluate("""() => {
          const R = leesRondes(), t = handicapTabellen().hcpTrendMap, adj = esrMapFor('Testspeler', R);
          return { a: t[950], b: t[951], adjB: adj.get(951), adjOud: adj.get(919), nu: currentOfficialHcp('Testspeler', R) };
        }""")
        check("de eerste ronde van de dag (14,0, 6,0 beter dan 20,0): geen uitzonderlijke score", uit['a']['esrApplied'], False)
        check("de eerste ronde: index daarna 19,3 (een tussenstand)", uit['a']['newHcp'], 19.3)
        check("de tweede ronde (12,9) vergelijkt met 20,0 van het begin van de dag: −1,0", uit['adjB'], -1)
        check("de verlaging telt ook op de eerdere rondes in de laatste 20", uit['adjOud'], -1)
        check("de rondekaart van de tweede ronde meldt de verlaging", uit['b']['esrApplied'], True)
        check("handicap nu: (12,9 + 14,0 + 6 × 20,0) / 8 − 1,0 = 17,4", uit['nu'], 17.4)

        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(400)   # de lijst tekent zonder fout
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
