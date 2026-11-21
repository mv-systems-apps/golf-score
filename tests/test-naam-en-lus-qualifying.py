"""Twee koppelingen tussen scherm en gegevens (bevinding 15a en 15b).

a. Je wijzigt je naam terwijl er een ronde loopt en kiest 'Alles aanpassen'. De lopende
   ronde hoort mee te gaan: anders schrijft de volgende score de oude naam terug en telt
   die ronde niet meer mee.
b. Je hebt qualifying aangezet. Kiest de app zelf een lus (bij een club met alleen een
   lus), dan gaat qualifying uit. Ga je daarna terug naar een gewone baan, dan hoort
   jouw keuze er weer te staan.
Alles met echte tikken, behalve het klaarzetten van de gegevens.
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

clubs = json.loads(json.dumps(CLUBS))
clubs['Golfclub Heelsum']['courses']['Maan'] = dict(json.loads(json.dumps(CLUBS['Golfclub Heelsum']['courses']['Sandr'])), lus=True)
clubs['Alleenlus'] = {"club": "Alleenlus", "shortName": "AL", "courses": {"Solo": dict(json.loads(json.dumps(CLUBS['Golfclub Heelsum']['courses']['Airborne'])), lus=True)}}

async def klaar(pg, rondes):
    await pg.goto(app_url())
    await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
      localStorage.setItem('golf_last_backup_date', new Date().toISOString()); localStorage.setItem('golf_track_putts', 'on'); localStorage.setItem('golf_lussen_open', '1'); }""", [clubs, rondes])
    await pg.reload(); await pg.wait_for_timeout(600)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))

        print("\n=== a. NAAM WIJZIGEN TIJDENS EEN LOPENDE RONDE ===\n")
        await klaar(pg, [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(6)])
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw';
          document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.7'; onHcpBlur(document.getElementById('iHcp'));
          startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); }""")
        await pg.wait_for_timeout(400)
        plus = pg.locator('#screen-score .current-row .plus-cell')
        await plus.first.click(); await pg.wait_for_timeout(250); await plus.first.click(); await pg.wait_for_timeout(2500)
        NAMEN = "() => ({ game: game.player, opslag: JSON.parse(localStorage.getItem('golf_rounds')).map(r => r.player).sort().join(','), lopend: JSON.parse(localStorage.getItem('golf_rounds')).find(r => String(r.id) === String(game.id)).player })"
        check("uitgangspunt: de lopende ronde staat op Testspeler", (await pg.evaluate(NAMEN))['lopend'], 'Testspeler')
        await pg.evaluate("nav('setup')"); await pg.wait_for_timeout(300)
        await pg.click('#iName'); await pg.fill('#iName', 'Testspeler V'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(400)
        check("de vraag verschijnt", 'meenemen' in await pg.evaluate("document.getElementById('keuzeModalTekst').textContent"), True)
        await pg.locator('#keuzeModal button:visible', has_text='Alles aanpassen').click(); await pg.wait_for_timeout(400)
        n = await pg.evaluate(NAMEN)
        check("direct daarna staan alle rondes in de opslag op de nieuwe naam", n['opslag'], ','.join(['Testspeler V'] * 7))
        check("de lopende ronde in het geheugen ook", n['game'], 'Testspeler V')
        await pg.evaluate("nav('score')"); await pg.wait_for_timeout(300)
        voor = await pg.evaluate("JSON.parse(localStorage.getItem('golf_rounds')).find(r => String(r.id) === String(game.id)).holes[0].score")
        await plus.first.click(); await pg.wait_for_timeout(250); await plus.first.click(); await pg.wait_for_timeout(2500)
        na = await pg.evaluate("JSON.parse(localStorage.getItem('golf_rounds')).find(r => String(r.id) === String(game.id)).holes[0].score")
        check("de volgende score is echt weggeschreven", (voor is not None, na != voor), (True, True))
        n = await pg.evaluate(NAMEN)
        check("na de volgende score staat de lopende ronde nog op de nieuwe naam", n['lopend'], 'Testspeler V')
        check("en alle zeven rondes samen", n['opslag'], ','.join(['Testspeler V'] * 7))

        print("\n=== b. QUALIFYING NA EEN LUS DIE DE APP ZELF KOOS ===\n")
        await klaar(pg, [])
        await pg.evaluate("nav('setup')"); await pg.wait_for_timeout(300)
        Q = "() => [sel.track, sel.qualifying, document.getElementById('qualifyToggle1').checked]"
        if not (await pg.evaluate(Q))[1]:
            await pg.evaluate("document.getElementById('qualifyToggle1').click()"); await pg.wait_for_timeout(200)
        voor = await pg.evaluate(Q)
        check("vooraf: gewone baan, qualifying aan", (voor[1], voor[2]), (True, True))
        WISSEL = "(c) => { localStorage.setItem('golf_default_club', c); rebuildCourseLookup(false); rebuildAll(); }"
        await pg.evaluate(WISSEL, 'Alleenlus'); await pg.wait_for_timeout(300)
        check("club met alleen een lus: de app kiest de lus en zet qualifying uit", await pg.evaluate(Q), ['Solo', False, False])
        await pg.evaluate(WISSEL, 'Golfclub Heelsum'); await pg.wait_for_timeout(300)
        na = await pg.evaluate(Q)
        check("terug op een gewone baan staat qualifying weer aan", (na[0] in ('Airborne', 'Sandr'), na[1], na[2]), (True, True, True))
        async def baan(naam): await pg.locator('.track-btn', has_text=naam).first.click(); await pg.wait_for_timeout(250)
        await baan('Maan')
        check("zelf de lus aantikken zet qualifying uit", await pg.evaluate(Q), ['Maan', False, False])
        await baan('Sandr')
        check("daarna een gewone baan aantikken zet het weer aan", await pg.evaluate(Q), ['Sandr', True, True])
        await baan('Maan'); await pg.evaluate("document.getElementById('qualifyToggle1').click()"); await pg.wait_for_timeout(150)
        await pg.evaluate("document.getElementById('qualifyToggle1').click()"); await pg.wait_for_timeout(150)
        check("op de lus zelf aan- en weer uitgezet: staat uit", (await pg.evaluate(Q))[1:], [False, False])
        await baan('Airborne')
        check("dan geldt jouw laatste keuze: op de gewone baan blijft het uit", await pg.evaluate(Q), ['Airborne', False, False])
        await baan('Maan'); await baan('Sandr')
        check("stond het vóór de lus uit, dan blijft het daarna uit", await pg.evaluate(Q), ['Sandr', False, False])
        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
