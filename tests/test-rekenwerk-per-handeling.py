"""Hoeveel rekenwerk een handeling doet, geteld in plaats van geklokt.

Tijden schommelen per machine; aantallen niet. Deze test bewaakt twee plekken waar het
rekenwerk onnodig meegroeide met het archief:

  1. Statistiek openen zette voor elke ronde de datums van alle eerdere rondes opnieuw
     om (kwadratisch: 328.000 omzettingen bij 1000 rondes). Nu één keer per ronde.
  2. Zoeken in Rondes leidde bij elke toets de Low HI opnieuw af uit de hele historie,
     voor een veld in Instellingen dat door zoeken niet verandert.

De scoretik heeft zijn eigen test: test-scoretik-lijst.py.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

N = 300
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.add_init_script("window.__datums = 0; { const D = Date; Date = new Proxy(D, { construct(t, a) { window.__datums++; return new t(...a); } }); }")
        rondes = []
        for i in range(N):
            r = ronde(i + 1, f"{2021 + i // 60}-{1 + (i % 60) // 5:02d}-{1 + (i % 5) * 5:02d}")
            r['sdFinal'] = round(24 + (i * 7) % 13 + (i % 3) * 0.4, 1)
            if i % 9 == 0: r['club'] = 'Papendal'; r['clubShort'] = 'Papendal'
            if i % 11 == 0: r['note'] = 'wedstrijd met wind'
            rondes.append(r)
        await pg.goto(app_url())
        await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
          localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
          localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }""", [CLUBS, rondes])
        await pg.reload(); await pg.wait_for_timeout(700)

        print(f"\n=== 1. STATISTIEK OPENEN MET {N} RONDES ===\n")
        await pg.evaluate("() => { _statChartPeriod = 'alles'; nav('setup'); }")
        d = await pg.evaluate("() => { window.__datums = 0; nav('stat'); return [window.__datums, document.getElementById('screen-stat').innerHTML.length]; }")
        print(f"       {d[0]} datumomzettingen, {d[0] / N:.1f} per ronde")
        check("het scherm is opgebouwd", d[1] > 5000, True)
        check("hooguit 30 datumomzettingen per ronde (was ruim 100 en groeide mee)", d[0] <= 30 * N, True)

        print("\n=== 2. ZOEKEN IN RONDES ===\n")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { window.__lowHi = 0; window.__opslagUi = 0;
          const a = updateLowHiInput; window.updateLowHiInput = function () { window.__lowHi++; return a.apply(this, arguments); };
          const c = updateStorageSettingsUI; window.updateStorageSettingsUI = function () { window.__opslagUi++; return c.apply(this, arguments); }; }""")
        veld = pg.locator('#archiveSearch')
        if not await veld.is_visible():
            await pg.locator('#archiveSearchBtn').click(); await pg.wait_for_timeout(200)
        await veld.press_sequentially('papen', delay=60); await pg.wait_for_timeout(300)
        z = await pg.evaluate("""() => { const voor = document.getElementById('savedList').innerHTML; const n = [window.__lowHi, window.__opslagUi];
          tekenRondelijst();   // de volledige opbouw, zoals voorheen bij elke toets
          return { tellers: n, gelijk: voor === document.getElementById('savedList').innerHTML, treffers: (voor.match(/Papendal/g) || []).length, lengte: voor.length }; }""")
        check("vijf toetsen: de onderdelen van Instellingen zijn niet opnieuw berekend", z['tellers'], [0, 0])
        check("de lijst is dezelfde als bij een volledige opbouw", z['gelijk'], True)
        check("en toont de gezochte rondes", z['treffers'] > 0 and z['lengte'] > 1000, True)

        print("\n=== 3. EEN ECHTE WIJZIGING WERKT INSTELLINGEN NOG WEL BIJ ===\n")
        await pg.evaluate("() => { window.__lowHi = 0; window.__opslagUi = 0; tekenRondelijst(); }")
        check("tekenRondelijst() zonder invoer berekent beide opnieuw, zoals voorheen", await pg.evaluate("() => [window.__lowHi, window.__opslagUi]"), [1, 1])
        await pg.evaluate("() => { window.__lowHi = 0; klapAllesOpen('#screen-archive', tekenRondelijst, '_pgCollapsed'); }")
        check("ook als de functie wordt doorgegeven (uitklappen)", await pg.evaluate("() => window.__lowHi") > 0, True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
