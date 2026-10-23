"""Het startscherm bij clubs met dezelfde baannamen.

Eis van de gebruiker: clubnamen zijn uniek, baannamen en wedstrijdlussen niet — elke club moet een
baan 'Noord' of een lus 'Maan' kunnen hebben. Eerder hield de app één lijst bij van alle
banen van alle clubs, met alleen de naam als sleutel. Bij twee clubs met een baan
'Noord' bleef er één over: club A toonde geen baan, en een ronde bij club A kreeg de
holes, par en CR van club B.

Nu bevat de lijst alleen de banen van de gekozen club. Deze test loopt elke manier langs
waarop de gekozen club kan wisselen, en controleert na elke wissel het hele startscherm:
clubnaam, banen, tees, baanhandicap — en wat een gestarte ronde werkelijk meekrijgt.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]; PL = [4, 4, 4, 3, 3, 4, 5, 4, 4]
def ids(l, n=9): return [f"{l}{i}" for i in range(1, n + 1)]
CLUBS = {
  "Club A": {"club": "Club A", "shortName": "A-kort", "courses": {
    "Noord": {"holeIds": ids('A'), "tees": {"Heren": {"Geel": tee(35.0, 120, PA)}, "Dames": {"Rood": tee(36.5, 126, PA)}}},
    "Groot": {"holeIds": ids('G', 18), "tees": {"Heren": {"Geel": tee(70.4, 124, PA + PA)}}},
    "Maan":  {"holeIds": ids('MA'), "lus": True, "tees": {"Heren": {"Geel": tee(34.1, 118, PL)}}}}},
  "Club B": {"club": "Club B", "shortName": "B-kort", "courses": {
    "Noord": {"holeIds": ids('B'), "tees": {"Heren": {"Wit": tee(38.2, 139, PB), "Geel": tee(37.0, 135, PB)}}},
    "Zuid":  {"holeIds": ids('Z'), "tees": {"Heren": {"Geel": tee(36.0, 125, PA)}}},
    "Maan":  {"holeIds": ids('MB'), "lus": True, "tees": {"Heren": {"Geel": tee(36.9, 131, PB)}}}}},
}

# Wat het startscherm toont, en wat de app zelf als 'juist' zou moeten gebruiken: de
# gegevens rechtstreeks uit de club, niet via de banenlijst.
SCHERM = """() => { const club = localStorage.getItem('golf_default_club');
  const b = club && CLUBS[club] ? CLUBS[club].courses[sel.track] : null;
  const t = b ? (b.tees[sel.gender] || {})[sel.tee] : null;
  const hcp = parseFloat(document.getElementById('iHcp').value);
  return { club, kort: document.getElementById('setupClubShortName').innerText.trim(),
    banen: [...document.querySelectorAll('#trackList .track-name')].map(x => x.textContent),
    gekozen: sel.track, tees: [...document.querySelectorAll('#teeBtns button')].map(x => x.textContent.trim()), tee: sel.tee,
    chcp: document.getElementById('chcpPreview').textContent.trim(),
    hoort: t ? String(calcChcp(b.holeIds.length, t.CR, t.SR, teePar(t), hcp)) : null,
    lijst: Object.keys(COURSES).sort() }; }"""
RONDE = "() => game.started ? { club: game.club, kort: game.clubShort, baan: game.track, CR: game.CR, SR: game.SR, par: game.PAR, holes: game.holes.map(h => h.id).join(','), pars: game.holes.map(h => h.par).join('') } : null"

def ronde_hoort(club, baan, g='Heren', t='Geel'):
    c = CLUBS[club]; b = c['courses'][baan]; te = b['tees'][g][t]
    return {'club': club, 'kort': c['shortName'], 'baan': baan, 'CR': te['CR'], 'SR': te['SR'], 'par': sum(h['par'] for h in te['holes']),
            'holes': ','.join(b['holeIds']), 'pars': ''.join(str(h['par']) for h in te['holes'])}

async def schoon(pg, club='Club A', thuis='Club A', clubs=CLUBS):
    await pg.goto(app_url()); await pg.evaluate(SEED, [clubs, []])
    await pg.evaluate("""([c, t]) => { if (c) localStorage.setItem('golf_default_club', c); else localStorage.removeItem('golf_default_club');
        if (t) localStorage.setItem('golf_home_club', t); else localStorage.removeItem('golf_home_club'); localStorage.setItem('golf_lussen_open', '1'); }""", [club, thuis])
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate("() => { nav('setup'); document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '24.0'; rebuildStartScreen(); }")

async def kies_baan(pg, naam):
    await pg.locator('#trackList .track-btn', has_text=naam).first.click(); await pg.wait_for_timeout(100)

async def start(pg):
    await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
        if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"""); await pg.wait_for_timeout(300)

async def scherm_klopt(pg, wat, club, banen, kort):
    s = await pg.evaluate(SCHERM)
    check(f"{wat}: club en korte naam", (s['club'], s['kort'].startswith(kort)), (club, True))
    check(f"{wat}: de banen van deze club", s['banen'], banen)
    check(f"{wat}: de banenlijst bevat alleen deze club", s['lijst'], sorted(CLUBS[club]['courses'].keys()) if club in CLUBS else s['lijst'])
    check(f"{wat}: baanhandicap volgt de gegevens van deze club", s['chcp'], s['hoort'])
    return s

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))

        print("\n=== 1. CLUB A: STARTSCHERM EN EEN GESTARTE RONDE ===\n")
        await schoon(pg)
        s = await scherm_klopt(pg, "club A", 'Club A', ['Noord', 'Maan'], 'A-kort')
        check("tees van Noord bij club A", s['tees'], ['Geel'])
        await kies_baan(pg, 'Noord'); await start(pg)
        check("de ronde krijgt de gegevens van club A", await pg.evaluate(RONDE), ronde_hoort('Club A', 'Noord'))
        await pg.evaluate("() => finishActiveRound(null)")

        print("\n=== 2. WISSELEN VIA HET ZOEKVENSTER NAAR CLUB B ===\n")
        await pg.evaluate("() => { nav('setup'); openClubSearchModal(); selectClubSearchCandidate('Club B'); confirmClubSearchModal(); }"); await pg.wait_for_timeout(200)
        s = await scherm_klopt(pg, "club B", 'Club B', ['Noord', 'Zuid', 'Maan'], 'B-kort')
        # Andere starttijd dan de ronde van club A, anders botsen datum en tijd.
        await pg.evaluate("() => { document.getElementById('iTime').value = '06:00'; sel.time = '06:00'; sel.dateTimeEdited = true; sel.date = document.getElementById('iDate').value; }")
        await kies_baan(pg, 'Noord')
        s = await pg.evaluate(SCHERM)
        check("tees van Noord bij club B", s['tees'], ['Wit', 'Geel'])
        check("baanhandicap van Noord bij club B", s['chcp'], s['hoort'])
        gekozen_tee = s['tee']
        await start(pg)
        check("de ronde krijgt de gegevens van club B", await pg.evaluate(RONDE), ronde_hoort('Club B', 'Noord', t=gekozen_tee))
        await pg.evaluate("() => finishActiveRound(null)")

        print("\n=== 3. TERUG MET DE THUISCLUBKNOP ===\n")
        await pg.evaluate("() => { nav('setup'); useHomeClub(); }"); await pg.wait_for_timeout(200)
        await scherm_klopt(pg, "club A", 'Club A', ['Noord', 'Maan'], 'A-kort')
        await pg.evaluate("() => selectHoleCount('18')"); await pg.wait_for_timeout(100)
        check("filter 18 holes bij club A", (await pg.evaluate(SCHERM))['banen'], ['Groot'])
        await pg.evaluate("() => setDefaultClub('Club B')"); await pg.wait_for_timeout(150)
        check("na wisselen staat het filter weer goed voor club B", (await pg.evaluate(SCHERM))['banen'], ['Noord', 'Zuid', 'Maan'])

        print("\n=== 4. GEEN GEKOZEN CLUB, WEL EEN THUISCLUB (na herladen) ===\n")
        await schoon(pg, club=None, thuis='Club B')
        await scherm_klopt(pg, "thuisclub B ingevuld", 'Club B', ['Noord', 'Zuid', 'Maan'], 'B-kort')
        await pg.reload(); await pg.wait_for_timeout(400); await pg.evaluate("() => nav('setup')")
        check("na herladen nog steeds club B", (await pg.evaluate(SCHERM))['lijst'], ['Maan', 'Noord', 'Zuid'])

        print("\n=== 5. OPNIEUW PLANNEN VAN EEN RONDE VAN DE ANDERE CLUB ===\n")
        await schoon(pg, 'Club A')
        await pg.evaluate("""() => { const d = new Date(); d.setDate(d.getDate() + 4); const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            document.getElementById('iDate').value = iso; document.getElementById('iTime').value = '10:00'; sel.date = iso; sel.time = '10:00'; sel.dateTimeEdited = true; }""")
        await kies_baan(pg, 'Noord'); await start(pg); await pg.evaluate("() => finishActiveRound(null)")
        await pg.evaluate("() => setDefaultClub('Club B')"); await pg.wait_for_timeout(150)
        await pg.evaluate("() => herplanRonde(leesRondes().find(r => r.player === 'Testspeler').id)"); await pg.wait_for_timeout(300)
        s = await scherm_klopt(pg, "terug naar club A", 'Club A', ['Noord', 'Maan'], 'A-kort')
        check("de baan van de ronde is gekozen", s['gekozen'], 'Noord')
        await start(pg)
        check("de herplande ronde heeft de gegevens van club A", await pg.evaluate(RONDE), ronde_hoort('Club A', 'Noord'))
        check("en er is één ronde", await pg.evaluate("() => leesRondes().length"), 1)

        print("\n=== 6. CORRIGEREN VAN EEN RONDE VAN DE ANDERE CLUB ===\n")
        await schoon(pg, 'Club B'); await kies_baan(pg, 'Zuid'); await start(pg)
        await pg.evaluate("() => { for (let i = 0; i < 4; i++) { setCurrentHole(i); stepScore(i, +1); } finishActiveRound(null); setDefaultClub('Club A'); }")
        await pg.evaluate("() => herplanRonde(leesRondes()[0].id, true)"); await pg.wait_for_timeout(300)
        await scherm_klopt(pg, "terug naar club B", 'Club B', ['Noord', 'Zuid', 'Maan'], 'B-kort')
        await kies_baan(pg, 'Noord'); t6 = (await pg.evaluate(SCHERM))['tee']; await start(pg)
        check("gecorrigeerd naar Noord van club B", await pg.evaluate(RONDE), ronde_hoort('Club B', 'Noord', t=t6))
        check("de vier scores zijn mee", await pg.evaluate("() => game.holes.filter(h => h.score != null).length"), 4)

        print("\n=== 7. DE GEKOZEN CLUB HERNOEMEN ===\n")
        await schoon(pg, 'Club A')
        await pg.evaluate("""() => { nav('club'); openClubEditor('Club A'); document.querySelector('#clubEditorOverlay input, #clubEditorName').value;
            const naam = [...document.querySelectorAll('input')].find(i => i.value === 'Club A'); naam.value = 'Club Anders'; saveClubFromEditor(); }"""); await pg.wait_for_timeout(300)
        s = await pg.evaluate("() => { closeClubEditor?.(); nav('setup'); rebuildStartScreen(); return null; }")
        s = await pg.evaluate(SCHERM)
        check("de hernoemde club is nog gekozen", s['club'], 'Club Anders')
        check("en zijn banen staan er nog", s['banen'], ['Noord', 'Maan'])
        check("thuisclub volgt de nieuwe naam", await pg.evaluate("() => localStorage.getItem('golf_home_club')"), 'Club Anders')

        print("\n=== 8. DE GEKOZEN CLUB VERWIJDEREN ===\n")
        await schoon(pg, 'Club A', thuis='Club B')
        await pg.evaluate("""() => { delete CLUBS['Club A']; storage.removeItem('golf_default_club'); saveClubsToStorage(); rebuildCourseLookup(); rebuildAll(); nav('setup'); }"""); await pg.wait_for_timeout(200)
        s = await pg.evaluate(SCHERM)
        check("de thuisclub neemt het over, met zijn eigen banen", (s['club'], s['banen'], s['lijst']), ('Club B', ['Noord', 'Zuid', 'Maan'], ['Maan', 'Noord', 'Zuid']))
        await schoon(pg, 'Club A', thuis=None)
        await pg.evaluate("""() => { delete CLUBS['Club A']; storage.removeItem('golf_default_club'); saveClubsToStorage(); rebuildCourseLookup(); rebuildAll(); nav('setup'); }"""); await pg.wait_for_timeout(200)
        s = await pg.evaluate(SCHERM)
        check("zonder thuisclub: geen club, geen banen, geen fout", (s['club'], s['banen'], s['lijst']), (None, [], []))

        print("\n=== 9. EEN BAAN BEWERKEN BIJ DE ENE CLUB RAAKT DE ANDERE NIET ===\n")
        await schoon(pg, 'Club A'); await kies_baan(pg, 'Noord')
        voor = (await pg.evaluate(SCHERM))['chcp']
        await pg.evaluate("() => { CLUBS['Club B'].courses['Noord'].tees.Heren.Geel.CR = 45.0; rebuildCourseLookup(); saveClubsToStorage(); rebuildAll(); }")
        check("Noord van club B aangepast: club A onveranderd", (await pg.evaluate(SCHERM))['chcp'], voor)
        await pg.evaluate("() => { CLUBS['Club A'].courses['Noord'].tees.Heren.Geel.CR = 40.0; rebuildCourseLookup(); saveClubsToStorage(); rebuildAll(); }")
        s = await pg.evaluate(SCHERM)
        check("Noord van club A aangepast: baanhandicap volgt", (s['chcp'] != voor, s['chcp']), (True, s['hoort']))

        print("\n=== 10. CLUBBESTAND INLEZEN VOOR DE GEKOZEN CLUB ===\n")
        await schoon(pg, 'Club A'); await kies_baan(pg, 'Noord')
        nieuw = json.loads(json.dumps(CLUBS['Club A'])); nieuw['courses']['Noord']['tees']['Heren']['Geel']['CR'] = 39.3
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_club_a.json'); open(pad, 'w', encoding='utf-8').write(json.dumps(nieuw))
        await pg.evaluate("() => nav('settings')"); await pg.locator('#importClubFile').set_input_files(pad); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { const k = document.getElementById('confirmModalBtn'); if (k && !document.getElementById('confirmModal').classList.contains('hidden')) k.click(); }")
        await pg.wait_for_timeout(300); os.remove(pad)
        await pg.reload(); await pg.wait_for_timeout(400); await pg.evaluate("() => { nav('setup'); document.getElementById('iHcp').value = '24.0'; rebuildStartScreen(); }")
        await kies_baan(pg, 'Noord'); await start(pg)
        check("de ronde gebruikt de ingelezen CR van club A", (await pg.evaluate(RONDE))['CR'], 39.3)

        print("\n=== 11. EEN WEDSTRIJDLUS MET DEZELFDE NAAM BIJ BEIDE CLUBS ===\n")
        await schoon(pg, 'Club A'); await kies_baan(pg, 'Maan'); await start(pg)
        check("lus Maan bij club A", await pg.evaluate(RONDE), ronde_hoort('Club A', 'Maan'))
        await pg.evaluate("() => { finishActiveRound(null); nav('setup'); setDefaultClub('Club B'); }"); await pg.wait_for_timeout(150)
        # Een andere tijd dan de eerste ronde: twee rondes op dezelfde datum en tijd weigert de
        # app ('Dubbele datum & tijd'). Een vaste 06:00 ging mis als de test in die minuut
        # draaide — dan kreeg de eerste ronde zelf 06:00 (20-10-2026 voor het eerst gezien).
        await pg.evaluate("""() => { const d = document.getElementById('iDate').value;
            const bezet = new Set(loadSavedRounds().filter(r => r.date === d).map(r => r.time));
            const t = ['06:00', '06:01', '06:02'].find(x => !bezet.has(x));
            document.getElementById('iTime').value = t; sel.time = t; sel.dateTimeEdited = true; sel.date = d; }""")
        await kies_baan(pg, 'Maan'); await start(pg)
        check("lus Maan bij club B", await pg.evaluate(RONDE), ronde_hoort('Club B', 'Maan'))
        await pg.evaluate("() => { finishActiveRound(null); nav('club'); openClubEditor('Club B'); openLusMaker(); }"); await pg.wait_for_timeout(200)
        await pg.fill('#lusNaam', 'Groot'); await pg.click('[data-lus-bron="Zuid"]')
        for i in range(3): await pg.click(f'[data-lus-hole="{i}"]')
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        check("een lus 'Groot' bij club B mag, ook al heeft club A een baan 'Groot'",
              await pg.evaluate("() => [CLUBS['Club B'].courses['Groot'].holeIds.join(','), CLUBS['Club A'].courses['Groot'].holeIds.length]"), ['Z1,Z2,Z3', 18])

        print("\n=== 12. HET STARTSCHERM RAAKT EEN LOPENDE RONDE NIET ===\n")
        await schoon(pg, 'Club A'); await kies_baan(pg, 'Noord'); await start(pg)
        voor = await pg.evaluate("() => ({ chcp: game.chcp, slagen: game.holes.map(h => h.phcp).join(''), ppar: game.holes.map(h => h.ppar).join('') })")
        # Op het startscherm iets heel anders klaarzetten: andere club, andere baan, andere handicap.
        await pg.evaluate("() => { nav('setup'); setDefaultClub('Club B'); document.getElementById('iHcp').value = '4.0'; }"); await kies_baan(pg, 'Zuid')
        await pg.evaluate("""() => { const i = leesRondes().findIndex(r => String(r.id) === String(game.id)); doOpenRoundInfoModal(i);
            document.getElementById('editNoteInput').value = 'notitie'; confirmRoundInfo(); }"""); await pg.wait_for_timeout(200)
        na = await pg.evaluate("() => ({ chcp: game.chcp, slagen: game.holes.map(h => h.phcp).join(''), ppar: game.holes.map(h => h.ppar).join('') })")
        check("na Ronde bewerken: baanhandicap en slagen per hole ongewijzigd", na, voor)
        opgeslagen = await pg.evaluate("() => { const r = leesRondes().find(r => String(r.id) === String(game.id)); return { chcp: r.chcp, slagen: r.holes.map(h => h.phcp).join(''), ppar: r.holes.map(h => h.ppar).join('') }; }")
        check("ook in de opgeslagen ronde", opgeslagen, voor)

        print("\n=== 13. OUDE RONDES ZONDER CLUBNAAM ===\n")
        await schoon(pg, 'Club A')
        check("een baan die maar bij één club bestaat wordt gevonden, welke club ook gekozen is",
              await pg.evaluate("() => COURSE_CLUBS['Zuid']"), 'Club B')
        check("bij een dubbele naam wint de gekozen club", await pg.evaluate("() => COURSE_CLUBS['Noord']"), 'Club A')

        print("\n=== 14. EEN ANDER TABBLAD KIEST EEN ANDERE CLUB ===\n")
        ctx = await b.new_context(viewport={'width': 390, 'height': 844})
        t1 = await ctx.new_page(); t1.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await schoon(t1, 'Club A'); await kies_baan(t1, 'Noord'); await start(t1)
        await t1.evaluate("() => { for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, +1); } nav('setup'); }")
        lopend = await t1.evaluate("() => JSON.stringify({ ...game, holes: game.holes.map(h => ({ ...h, _initScore: undefined })) })")
        opslag = await t1.evaluate("() => localStorage.getItem('golf_rounds')")
        t2 = await ctx.new_page(); await t2.goto(app_url()); await t2.wait_for_timeout(400)
        await t2.evaluate("() => { nav('setup'); setDefaultClub('Club B'); }"); await t1.wait_for_timeout(400)
        s1 = await t1.evaluate(SCHERM)
        check("het eerste tabblad toont nu de banen van club B", (s1['club'], s1['banen'], s1['lijst']), ('Club B', ['Noord', 'Zuid', 'Maan'], ['Maan', 'Noord', 'Zuid']))
        check("en rekent met de gegevens van club B", s1['chcp'], s1['hoort'])
        check("de lopende ronde in dat tabblad is niet veranderd", await t1.evaluate("() => JSON.stringify({ ...game, holes: game.holes.map(h => ({ ...h, _initScore: undefined })) })") == lopend, True)
        check("en de opgeslagen rondes ook niet", await t1.evaluate("() => localStorage.getItem('golf_rounds')") == opslag, True)
        await ctx.close()

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
