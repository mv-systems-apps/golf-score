"""Een wedstrijdlus is een kopie van zijn bronbanen — en de app laat zien wanneer die
kopie verouderd is.

Past de club later de par, SI, CR of SR van een bronbaan aan, dan verandert de lus niet
vanzelf mee. De lus onthoudt daarom uit welke holes hij is samengesteld. Bij Clubs en op
het startscherm staat een melding zodra een bronbaan is gewijzigd, en bij Clubs kun je
hem bijwerken.

Eis van de gebruiker: dit mag een ronde NOOIT aantasten. Een ronde bewaart zijn eigen par, SI, CR
en SR. Deze test legt daarom een afgeronde, een lopende en een geplande ronde op de lus
klaar en vergelijkt ze na elke stap met hoe ze waren.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {str(echt)[:260]} — verwacht {str(verwacht)[:260]}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PO = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PW = [4, 4, 3, 5, 4, 4, 3, 4, 5]
CLUBS = {"Lusclub": {"club": "Lusclub", "shortName": "Lus", "courses": {
    "Oost": {"holeIds": [f"O{i}" for i in range(1, 10)], "tees": {"Heren": {"Geel": tee(35.6, 128, PO)}}},
    "West": {"holeIds": [f"W{i}" for i in range(1, 10)], "tees": {"Heren": {"Geel": tee(36.2, 133, PW)}}}}}}

RONDES = "() => leesRondes().map(r => JSON.stringify(r, (k, v) => (k === '_initScore' ? undefined : v))).sort()"
GEHEUGEN = "() => JSON.stringify({ ...game, holes: game.holes.map(h => ({ ...h, _initScore: undefined })) })"
LUS = "() => JSON.parse(JSON.stringify(CLUBS['Lusclub'].courses['Maan'] || null))"
STATUS = "() => lusStatus('Lusclub', 'Maan')"
RIJ = """() => { nav('club'); openClubEditor('Lusclub'); const g = document.getElementById('clubCourseGrouplus'); if (g && g.classList.contains('hidden')) toggleClubCourseGroup('lus');
    const m = document.querySelector('#clubCourseGrouplus [data-lus-status]'); return m ? [m.dataset.lusStatus, m.innerText.replace(/\\s+/g, ' ').trim()] : null; }"""
HINT = """() => { closeClubEditor?.(); nav('setup'); localStorage.setItem('golf_lussen_open', '1'); sel.track = 'Maan'; buildTrackList();
    const h = document.getElementById('lusVerouderd'); return h ? h.textContent : null; }"""

async def baan_cr(pg, baan, cr):
    await pg.evaluate("""([baan, cr]) => { nav('club'); openClubEditor('Lusclub'); openCourseEditor(baan);
        const v = document.querySelector('.cr-name-field'); v.dataset.value = cr; v.textContent = cr; saveCourseFromEditor(); closeCourseEditor?.(); }""", [baan, cr])
    await pg.wait_for_timeout(300)

async def start(pg, tijd, dagen=0, vullen=0):
    await pg.evaluate("""([tijd, dagen]) => { closeClubEditor?.(); nav('setup'); sel.track = 'Maan'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true; rebuildStartScreen();
        document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '24.0';
        const d = new Date(); d.setDate(d.getDate() + dagen); const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
        document.getElementById('iDate').value = iso; document.getElementById('iTime').value = tijd; sel.date = iso; sel.time = tijd; sel.dateTimeEdited = true;
        startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""", [tijd, dagen])
    await pg.wait_for_timeout(300)
    if vullen: await pg.evaluate("(n) => { for (let i = 0; i < n; i++) { setCurrentHole(i); stepScore(i, +1); } }", vullen)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, []])
        await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Lusclub'); localStorage.setItem('golf_home_club', 'Lusclub'); }")
        await pg.reload(); await pg.wait_for_timeout(400)

        print("\n=== 1. EEN NIEUWE LUS ONTHOUDT ZIJN HERKOMST ===\n")
        await pg.evaluate("() => { nav('club'); openClubEditor('Lusclub'); }"); await pg.click('#lusMaakKnop'); await pg.wait_for_timeout(150)
        await pg.fill('#lusNaam', 'Maan'); await pg.click('[data-lus-bron="Oost"]')
        for i in [1, 2, 8]: await pg.click(f'[data-lus-hole="{i}"]')
        await pg.click('[data-lus-bron="West"]')
        for i in range(6): await pg.click(f'[data-lus-hole="{i}"]')
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        lus0 = await pg.evaluate(LUS)
        check("de herkomst is bewaard", lus0.get('bron'), [{'baan': 'Oost', 'idx': 1}, {'baan': 'Oost', 'idx': 2}, {'baan': 'Oost', 'idx': 8}] + [{'baan': 'West', 'idx': i} for i in range(6)])
        check("status", await pg.evaluate(STATUS), 'actueel')
        check("geen melding bij Clubs", await pg.evaluate(RIJ), None)
        check("geen aanwijzing op het startscherm", await pg.evaluate(HINT), None)

        print("\n=== 2. DRIE RONDES OP DE LUS: AFGEROND, GEPLAND, LOPEND ===\n")
        await start(pg, '08:00', vullen=9); await pg.evaluate("() => finishActiveRound(null)")
        await start(pg, '10:00', dagen=6); await pg.evaluate("() => finishActiveRound(null)")
        await start(pg, '12:00', vullen=4)
        rondes0 = await pg.evaluate(RONDES); geheugen0 = await pg.evaluate(GEHEUGEN)
        check("drie rondes, de lopende met vier scores", (len(rondes0), await pg.evaluate("() => game.holes.filter(h => h.score != null).length")), (3, 4))
        async def rondes_gelijk(wat):
            check(f"{wat}: afgeronde, geplande en lopende ronde ongewijzigd (opslag en geheugen)",
                  (await pg.evaluate(RONDES) == rondes0, await pg.evaluate(GEHEUGEN) == geheugen0), (True, True))

        print("\n=== 3. ZELF DE CR VAN DE LUS AANPASSEN MAAKT HEM NIET 'VEROUDERD' ===\n")
        await baan_cr(pg, 'Maan', '33.3')
        check("status blijft actueel", await pg.evaluate(STATUS), 'actueel')
        check("de eigen CR staat erin, de herkomst is bewaard", ((await pg.evaluate(LUS))['tees']['Heren']['Geel']['CR'], (await pg.evaluate(LUS)).get('bronStempel')), (33.3, lus0['bronStempel']))
        await rondes_gelijk("eigen CR op de lus")

        print("\n=== 4. EEN BRONBAAN WIJZIGT ===\n")
        await baan_cr(pg, 'West', '39.0')
        check("status", await pg.evaluate(STATUS), 'verouderd')
        check("de lus zelf is niet veranderd", (await pg.evaluate(LUS))['tees']['Heren']['Geel']['CR'], 33.3)
        check("melding bij Clubs, met Bijwerken", await pg.evaluate(RIJ), ['verouderd', 'Een bronbaan is gewijzigd. Bijwerken'])
        check("aanwijzing op het startscherm", await pg.evaluate(HINT), 'Een bronbaan van deze lus is gewijzigd. Bijwerken kan bij Clubs.')
        await rondes_gelijk("bronbaan gewijzigd")

        print("\n=== 5. BIJWERKEN ===\n")
        await pg.evaluate(RIJ)
        await pg.locator('#clubCourseGrouplus [data-lus-status] span', has_text='Bijwerken').click(); await pg.wait_for_timeout(200)
        check("er wordt eerst gevraagd", await pg.evaluate("() => [...document.querySelectorAll('#keuzeModal button')].filter(b => !b.classList.contains('hidden')).map(b => b.textContent.trim())"), ['Annuleren', 'Bijwerken'])
        await pg.locator('#keuzeModal button', has_text='Annuleren').click(); await pg.wait_for_timeout(150)
        check("Annuleren: niets veranderd", ((await pg.evaluate(LUS))['tees']['Heren']['Geel']['CR'], await pg.evaluate(STATUS)), (33.3, 'verouderd'))
        await pg.locator('#clubCourseGrouplus [data-lus-status] span', has_text='Bijwerken').click(); await pg.wait_for_timeout(200)
        await pg.locator('#keuzeModal button', has_text='Bijwerken').click(); await pg.wait_for_timeout(300)
        lus1 = await pg.evaluate(LUS)
        hoort = await pg.evaluate("() => berekenLus('Lusclub', CLUBS['Lusclub'].courses['Maan'].bron).tees")
        check("de lus is opnieuw berekend uit de bronbanen", lus1['tees'], hoort)
        check("de CR volgt de nieuwe bronbaan (en de eigen aanpassing is vervallen)", lus1['tees']['Heren']['Geel']['CR'] not in (33.3, lus0['tees']['Heren']['Geel']['CR']), True)
        check("nog steeds een wedstrijdlus, met dezelfde holes", (lus1.get('lus'), lus1['holeIds']), (True, lus0['holeIds']))
        check("status weer actueel, melding weg", (await pg.evaluate(STATUS), await pg.evaluate(RIJ)), ('actueel', None))
        check("bewaard in de opslag", await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs'))['Lusclub'].courses['Maan'].tees.Heren.Geel.CR"), lus1['tees']['Heren']['Geel']['CR'])
        await rondes_gelijk("na het bijwerken")
        await pg.reload(); await pg.wait_for_timeout(400)
        check("na herladen: rondes in de opslag nog steeds gelijk", await pg.evaluate(RONDES) == rondes0, True)
        check("de lopende ronde speelt verder met zijn EIGEN CR", await pg.evaluate("() => game.CR"), lus0['tees']['Heren']['Geel']['CR'])
        await pg.evaluate("() => finishActiveRound(null)")
        await start(pg, '16:00')
        check("een NIEUWE ronde krijgt de bijgewerkte CR", await pg.evaluate("() => game.CR"), lus1['tees']['Heren']['Geel']['CR'])
        await pg.evaluate("() => finishActiveRound(null)")

        print("\n=== 6. EEN BRONBAAN HERNOEMEN, DAARNA VERWIJDEREN ===\n")
        await pg.evaluate("""() => { nav('club'); openClubEditor('Lusclub'); openCourseEditor('West'); document.getElementById('editorCourseName').value = 'Westbaan'; saveCourseFromEditor();
            document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden')); closeCourseEditor?.(); }"""); await pg.wait_for_timeout(300)
        check("de herkomst volgt de nieuwe naam", sorted({k['baan'] for k in (await pg.evaluate(LUS))['bron']}), ['Oost', 'Westbaan'])
        check("status blijft actueel", await pg.evaluate(STATUS), 'actueel')
        await pg.evaluate("() => { delete CLUBS['Lusclub'].courses['Westbaan']; rebuildCourseLookup(); saveClubsToStorage(); rebuildAll(); }")
        check("bronbaan weg: status", await pg.evaluate(STATUS), 'bronweg')
        check("melding zonder knop", await pg.evaluate(RIJ), ['bronweg', 'Een bronbaan bestaat niet meer; deze lus staat op zichzelf.'])
        check("de lus zelf blijft bruikbaar", (await pg.evaluate(LUS))['holeIds'], lus0['holeIds'])

        print("\n=== 7. EEN LUS ZONDER HERKOMST ===\n")
        await pg.evaluate("() => { const l = CLUBS['Lusclub'].courses['Maan']; delete l.bron; delete l.bronStempel; }")
        check("status onbekend, geen melding", (await pg.evaluate(STATUS), await pg.evaluate(RIJ)), ('onbekend', None))

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
