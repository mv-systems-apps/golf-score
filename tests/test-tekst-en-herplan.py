"""Twee restpunten uit de onafhankelijke review.

a. Een datum of SI uit de opslag mag nooit als HTML in beeld komen. Via import kan dat
   niet meer (de keuring houdt het tegen), maar wel via opslag die buiten de app om is
   gewijzigd of via rondes uit oudere, ongekeurde imports.
b. De onthouden qualifying-keuze van vóór een lus (versie 126) hoort niet te blijven
   hangen als je daarna een ronde herplant: dan geldt de keuze van die ronde.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

X = '<img src=x onerror="window.__x=(window.__x||[]).concat(\'%s\')">'
ZET = """([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_player_name', 'Mark');
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); localStorage.setItem('golf_lussen_open', '1'); }"""
DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        print("\n=== a. DATUM EN SI UIT DE OPSLAG ZIJN TEKST ===\n")
        pg = await b.new_page(viewport={"width": 390, "height": 844}); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
        rs = [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(4)]
        rs[1]['date'] = X % 'datum'; rs[3]['holes'][0]['si'] = X % 'si'
        await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, rs]); await pg.reload(); await pg.wait_for_timeout(700); await pg.evaluate(DICHT)
        for t in ['setup', 'archive', 'stat', 'settings']:
            await pg.evaluate(f"nav('{t}')"); await pg.wait_for_timeout(400)
        for i in range(len(rs)):
            await pg.evaluate(f"() => {{ try {{ const l = loadSavedRounds(); if (l[{i}]) {{ loadRoundSingle({i}); nav('score'); renderScore(); }} }} catch (e) {{}} }}"); await pg.wait_for_timeout(250)
            await pg.evaluate(DICHT)
        check("nergens is iets uit een datum of SI als HTML uitgevoerd", sorted(set(await pg.evaluate("window.__x || []"))), [])
        check("de goede rondes zijn er nog", await pg.evaluate("leesRondes().filter(r => [1, 3].includes(r.id)).length"), 2)
        await pg.close()

        print("\n=== b. HERPLANNEN NA EEN LUS ===\n")
        clubs = json.loads(json.dumps(CLUBS))
        clubs['Golfclub Heelsum']['courses']['Maan'] = dict(json.loads(json.dumps(CLUBS['Golfclub Heelsum']['courses']['Sandr'])), lus=True)
        oud = ronde(50, '2026-05-10', baan='Airborne', qual=False)
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        await pg.goto(app_url()); await pg.evaluate(ZET, [clubs, [oud]]); await pg.reload(); await pg.wait_for_timeout(700); await pg.evaluate(DICHT)
        await pg.evaluate("nav('setup')"); await pg.wait_for_timeout(200)
        Q = "() => [sel.track, sel.qualifying]"
        if not (await pg.evaluate(Q))[1]: await pg.evaluate("document.getElementById('qualifyToggle1').click()")
        await pg.locator('.track-btn', has_text='Maan').first.click(); await pg.wait_for_timeout(200)
        check("op de lus: qualifying uit", await pg.evaluate(Q), ['Maan', False])
        await pg.evaluate("() => herplanRonde('50')"); await pg.wait_for_timeout(300); await pg.evaluate(DICHT)
        check("herplannen van een niet-qualifying ronde: qualifying uit", (await pg.evaluate(Q))[1], False)
        await pg.evaluate("nav('setup')"); await pg.wait_for_timeout(200)
        await pg.locator('.track-btn', has_text='Sandr').first.click(); await pg.wait_for_timeout(200)
        check("daarna een gewone baan kiezen zet de keuze van vóór de lus niet terug", await pg.evaluate(Q), ['Sandr', False])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
