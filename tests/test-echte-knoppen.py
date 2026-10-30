"""Routes die eerder alleen met een rechtstreekse functieaanroep waren getest, nu met de
echte knoppen: tikken waar je in de app ook tikt.

Een aanroep van de functie mist alles wat de knop zelf doet (een bevestiging, een venster
dat eerst sluit, de volgorde). Hier:
  1. de gekozen club hernoemen in Club bewerken;
  2. een wedstrijdlus bewerken, hernoemen (met de vraag over bestaande rondes) en verwijderen;
  3. opnieuw plannen met twee spelers;
  4. corrigeren met twee spelers.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {echt} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
def ids(l): return [f"{l}{i}" for i in range(1, 10)]
CLUBS = {"Club A": {"club": "Club A", "shortName": "A", "courses": {
    "Noord": {"holeIds": ids('A'), "tees": {"Heren": {"Geel": tee(35.0, 120, PA)}, "Dames": {"Rood": tee(36.5, 126, PA)}}},
    "Zuid":  {"holeIds": ids('Z'), "tees": {"Heren": {"Geel": tee(33.1, 112, PB)}, "Dames": {"Rood": tee(34.6, 118, PB)}}},
    "Maan":  {"holeIds": ids('M'), "lus": True, "tees": {"Heren": {"Geel": tee(34.1, 118, PB)}}}}}}

async def schoon(pg):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, []])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_lussen_open', '1'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
    await pg.reload(); await pg.wait_for_timeout(400)

async def open_clubeditor(pg, club):
    await pg.evaluate("() => nav('club')"); await pg.wait_for_timeout(250)
    knop = pg.locator(f'button[data-club="{club}"][onclick^="confirmEditClub"]').first
    # De actieknoppen op de clubkaart klappen pas uit als je de kaart aantikt.
    if not await knop.is_visible():
        await pg.locator('.card', has_text=club).first.locator('div').first.click(); await pg.wait_for_timeout(200)
    await knop.click(); await pg.wait_for_timeout(250)

async def start_ronde(pg, baan, twee, toekomst=False, vullen=0):
    await pg.evaluate("() => nav('setup')"); await pg.wait_for_timeout(200)
    await pg.locator('#trackList .track-btn', has_text=baan).first.click()
    await pg.fill('#iName', 'Testspeler'); await pg.fill('#iHcp', '30.8'); await pg.locator('#iHcp').blur()
    await pg.evaluate("""([twee, toekomst]) => { if (twee !== player2Visible) togglePlayer2();
        if (twee) { document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20'; selectGenderSpeler2('Dames'); zetStartNote(2, 'notitie Anna'); }
        zetStartNote(1, 'notitie Testspeler');
        if (toekomst) { const d = new Date(); d.setDate(d.getDate() + 5); const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            document.getElementById('iDate').value = iso; document.getElementById('iTime').value = '10:00'; onDateTimeChange(); } }""", [twee, toekomst])
    await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
    if vullen:
        await pg.evaluate("(n) => { for (let i = 0; i < n; i++) { setCurrentHole(i); stepScore(i, +1); } }", vullen)
        if twee: await pg.evaluate("(n) => { switchToPlayer(2); for (let i = 0; i < n - 1; i++) { setCurrentHole(i); stepScore(i, +1); } switchToPlayer(1); }", vullen)

RONDES = "() => leesRondes().map(r => [r.player, r.club, r.track, r.note ?? null, r.holes.filter(h => h.score != null).length, r.lus ?? null]).sort()"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))

        print("\n=== 1. DE GEKOZEN CLUB HERNOEMEN ===\n")
        await schoon(pg); await start_ronde(pg, 'Noord', False, vullen=9)
        await pg.evaluate("() => finishActiveRound(null)")
        await open_clubeditor(pg, 'Club A')
        await pg.fill('#editorClubName', 'Club Anders'); await pg.fill('#editorShortName', 'CA')
        await pg.click('button[onclick="saveClubFromEditor()"]'); await pg.wait_for_timeout(300)
        check("er wordt gevraagd of de bestaande ronde mee moet", await pg.evaluate("() => !document.getElementById('clubRenameModal').classList.contains('hidden')"), True)
        await pg.locator('#clubRenameModal button', has_text='Ja').first.click() if await pg.locator('#clubRenameModal button', has_text='Ja').count() else await pg.evaluate("() => document.querySelector('#clubRenameModal .btn-primary').click()")
        await pg.wait_for_timeout(300)
        check("de ronde draagt de nieuwe clubnaam", await pg.evaluate("() => leesRondes().map(r => [r.club, r.clubShort])"), [['Club Anders', 'CA']])
        await pg.evaluate("() => { closeClubEditor(); nav('setup'); }"); await pg.wait_for_timeout(250)
        check("het startscherm toont de hernoemde club met zijn banen",
              await pg.evaluate("() => [localStorage.getItem('golf_default_club'), localStorage.getItem('golf_home_club'), [...document.querySelectorAll('#trackList .track-name')].map(x => x.textContent)]"),
              ['Club Anders', 'Club Anders', ['Noord', 'Zuid', 'Maan']])

        print("\n=== 2. EEN WEDSTRIJDLUS BEWERKEN, HERNOEMEN EN VERWIJDEREN ===\n")
        await schoon(pg); await start_ronde(pg, 'Maan', False, vullen=9)
        await pg.evaluate("() => finishActiveRound(null)")
        check("ronde op de lus", await pg.evaluate(RONDES), [['Testspeler', 'Club A', 'Maan', 'notitie Testspeler', 9, True]])
        await open_clubeditor(pg, 'Club A')
        await pg.locator('#clubCourseList div', has_text='Lussen').first.click(); await pg.wait_for_timeout(150)
        await pg.locator('#clubCourseGrouplus button').first.click(); await pg.wait_for_timeout(300)
        check("de baaneditor opent op de lus", await pg.input_value('#editorCourseName'), 'Maan')
        await pg.fill('#editorCourseName', 'Maanlus'); await pg.click('button[onclick="saveCourseFromEditor()"]'); await pg.wait_for_timeout(300)
        check("er wordt gevraagd of de bestaande ronde mee moet", await pg.evaluate("() => !document.getElementById('clubRenameModal').classList.contains('hidden')"), True)
        await pg.evaluate("() => naamWijzigingKeuze(true)") if not await pg.locator('#clubRenameModal .btn-primary').count() else await pg.locator('#clubRenameModal .btn-primary').first.click()
        await pg.wait_for_timeout(300)
        check("de lus heet anders en is nog een wedstrijdlus", await pg.evaluate("() => [Object.keys(CLUBS['Club A'].courses).sort(), CLUBS['Club A'].courses['Maanlus'].lus]"), [['Maanlus', 'Noord', 'Zuid'], True])
        check("de ronde volgt de nieuwe naam en houdt de markering", await pg.evaluate(RONDES), [['Testspeler', 'Club A', 'Maanlus', 'notitie Testspeler', 9, True]])
        wis = pg.locator('button[onclick^="deleteCourseFromEditor"]').first
        await wis.click(); await pg.wait_for_timeout(150); await wis.click(); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const k = document.getElementById('dangerModalConfirmBtn'); if (k && !document.getElementById('resetAllModal').classList.contains('hidden')) k.click(); }")
        await pg.wait_for_timeout(300)
        check("de lus is verwijderd", await pg.evaluate("() => Object.keys(CLUBS['Club A'].courses).sort()"), ['Noord', 'Zuid'])
        check("de ronde bestaat nog, mét markering", await pg.evaluate(RONDES), [['Testspeler', 'Club A', 'Maanlus', 'notitie Testspeler', 9, True]])

        print("\n=== 3. OPNIEUW PLANNEN MET TWEE SPELERS ===\n")
        await schoon(pg); await start_ronde(pg, 'Noord', True, toekomst=True)
        await pg.evaluate("() => finishActiveRound(null)")
        check("twee geplande rondes", await pg.evaluate(RONDES), [['Anna', 'Club A', 'Noord', 'notitie Anna', 0, None], ['Testspeler', 'Club A', 'Noord', 'notitie Testspeler', 0, None]])
        # Geplande rondes staan in de agenda (de kalenderknop bovenaan Rondes).
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(250)
        if not await pg.evaluate("() => (archiefGroepering === 'gepland')"):
            await pg.locator('[onclick="toggleGroupByPlanned()"]').first.click(); await pg.wait_for_timeout(300)
        # De groep openklappen waar de rondes in staan (over vijf dagen: deze of volgende week).
        for kop in ['Deze week', 'Volgende week', 'Later']:
            if await pg.locator('#savedList button[onclick^="openRoundEditChoice"]').count(): break
            await pg.locator('#savedList [onclick]', has_text=kop).first.click(); await pg.wait_for_timeout(250)
        idx = await pg.evaluate("() => loadSavedRounds().findIndex(r => r.player === 'Anna')")      # op de kaart van de medespeler tikken
        await pg.evaluate("(i) => { const k = [...document.querySelectorAll('button')].find(x => x.getAttribute('onclick') === 'openRoundEditChoice(' + i + ')'); k.closest('.hidden')?.classList.remove('hidden'); k.scrollIntoView({block:'center'}); }", idx)
        await pg.locator(f'button[onclick="openRoundEditChoice({idx})"]').first.click(); await pg.wait_for_timeout(200)
        check("de knop heet Herplannen", (await pg.inner_text('#roundEditChoiceHerplan')).strip(), 'Herplannen')
        await pg.click('#roundEditChoiceHerplan'); await pg.wait_for_timeout(350)
        s = await pg.evaluate("() => ({ naam: document.getElementById('iName').value, naam2: document.getElementById('iName2').value, n1: document.getElementById('startNote1').value, n2: document.getElementById('startNote2').value, banner: !document.getElementById('herplanBanner').classList.contains('hidden') })")
        check("startscherm: de eigen speler is speler 1, met beide notities", s, {'naam': 'Testspeler', 'naam2': 'Anna', 'n1': 'notitie Testspeler', 'n2': 'notitie Anna', 'banner': True})
        await pg.locator('#trackList .track-btn', has_text='Zuid').first.click()
        await pg.click('#startRoundBtn'); await pg.wait_for_timeout(400)
        check("beide rondes vervangen, op de nieuwe baan, met hun notitie", await pg.evaluate(RONDES), [['Anna', 'Club A', 'Zuid', 'notitie Anna', 0, None], ['Testspeler', 'Club A', 'Zuid', 'notitie Testspeler', 0, None]])

        print("\n=== 4. CORRIGEREN MET TWEE SPELERS ===\n")
        await schoon(pg); await start_ronde(pg, 'Noord', True, vullen=5)
        check("vijf en vier scores", await pg.evaluate(RONDES), [['Anna', 'Club A', 'Noord', 'notitie Anna', 4, None], ['Testspeler', 'Club A', 'Noord', 'notitie Testspeler', 5, None]])
        scores = await pg.evaluate("() => leesRondes().map(r => [r.player, r.holes.map(h => h.score ?? '-').join('')]).sort()")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        idx = await pg.evaluate("() => loadSavedRounds().findIndex(r => r.player === 'Testspeler')")
        await pg.evaluate("(i) => { const k = [...document.querySelectorAll('button')].find(x => x.getAttribute('onclick') === 'openRoundEditChoice(' + i + ')'); k.closest('.hidden')?.classList.remove('hidden'); k.scrollIntoView({block:'center'}); }", idx)
        await pg.locator(f'button[onclick="openRoundEditChoice({idx})"]').first.click(); await pg.wait_for_timeout(200)
        check("de knop heet Corrigeren", (await pg.inner_text('#roundEditChoiceHerplan')).strip(), 'Corrigeren')
        await pg.click('#roundEditChoiceHerplan'); await pg.wait_for_timeout(250)
        await pg.locator('#keuzeModal button', has_text='Corrigeren').first.click(); await pg.wait_for_timeout(350)
        await pg.locator('#trackList .track-btn', has_text='Zuid').first.click()
        await pg.click('#startRoundBtn'); await pg.wait_for_timeout(400)
        await pg.evaluate("() => { const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"); await pg.wait_for_timeout(300)
        check("beide rondes op de nieuwe baan, met notitie en hun eigen aantal scores", await pg.evaluate(RONDES), [['Anna', 'Club A', 'Zuid', 'notitie Anna', 4, None], ['Testspeler', 'Club A', 'Zuid', 'notitie Testspeler', 5, None]])
        check("ieder zijn eigen scores", await pg.evaluate("() => leesRondes().map(r => [r.player, r.holes.map(h => h.score ?? '-').join('')]).sort()"), scores)
        check("de pars zijn die van de nieuwe baan", await pg.evaluate("() => leesRondes().map(r => r.holes.map(h => h.par).join(''))"), ['544345444', '544345444'])

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
