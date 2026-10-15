"""Wedstrijdlus maken: een tijdelijke lus samenstellen uit holes van bestaande banen.

Aanleiding (Mark): de maanwedstrijd is een tijdelijke lus (S2, S3, S9, A1–A6). Die moest
buiten de app om in het clubbestand worden gezet, omdat CR en SR niet bekend zijn.

De lus is na het opslaan een GEWONE baan met de markering wedstrijdlus. Deze test
controleert het aanmaken met de echte knoppen, rekent par, SI, CR en SR onafhankelijk
na in Python, en kijkt of de bestaande banen onaangeroerd blijven.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED, ronde
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def holes(pars, sis): return [{"par": p, "si": s} for p, s in zip(pars, sis)]
OOST = holes([4, 3, 5, 4, 4, 3, 4, 5, 4], [7, 15, 3, 11, 1, 17, 9, 5, 13])
WEST = holes([4, 4, 3, 5, 4, 4, 3, 4, 5], [8, 2, 16, 6, 12, 4, 18, 10, 14])
P3   = holes([3] * 9, [1, 2, 3, 4, 5, 6, 7, 8, 9])
O = [f"O{i}" for i in range(1, 10)]; W = [f"W{i}" for i in range(1, 10)]
CLUBS = {"Lusclub": {"club": "Lusclub", "shortName": "Lus", "courses": {
    "Oost": {"holeIds": O, "tees": {"Heren": {"Geel": {"CR": 35.6, "SR": 128, "holes": OOST},
                                              "Rood": {"CR": 33.9, "SR": 119, "holes": OOST}},
                                    "Dames": {"Rood": {"CR": 36.4, "SR": 131, "holes": OOST}}}},
    "West": {"holeIds": W, "tees": {"Heren": {"Geel": {"CR": 36.2, "SR": 133, "holes": WEST},
                                              "Rood": {"CR": 34.4, "SR": 122, "holes": WEST}}}},
    "Oost/West": {"holeIds": O + W, "tees": {"Heren": {"Geel": {"CR": 71.8, "SR": 131, "holes": OOST + WEST},
                                                         "Rood": {"CR": 68.3, "SR": 121, "holes": OOST + WEST}}}},
    "Oost (P3)": {"holeIds": O, "tees": {"Heren": {"Paars": {"CR": 25.0, "SR": 76, "holes": P3}}}},
}},
  # Een club met alleen een wedstrijdlus: daar kiest de app de lus zelf.
  "Alleenlus": {"club": "Alleenlus", "shortName": "AL", "courses": {
    "Solo": {"holeIds": [f"X{i}" for i in range(1, 10)], "lus": True,
             "tees": {"Heren": {"Rood": {"CR": 33.9, "SR": 119, "holes": OOST}}}}}}}

def js_round(x, dec=0):
    """Math.round zoals JavaScript: halven naar boven."""
    import math
    f = 10 ** dec
    return math.floor(x * f + 0.5) / f

def verwacht(keuze, tee):
    """Onafhankelijke berekening. keuze: [(baan, index)], tee: (geslacht, naam)."""
    cs = CLUBS["Lusclub"]["courses"]; g, t = tee
    rij = []
    for volg, (b, i) in enumerate(keuze):
        th = cs[b]["tees"][g][t]["holes"]
        rang = sum(1 for x in th if x["si"] < th[i]["si"])
        rij.append({"par": th[i]["par"], "maat": (rang + 0.5) / len(th), "bron": th[i]["si"], "volg": volg})
    for nr, h in enumerate(sorted(rij, key=lambda h: (h["maat"], h["bron"], h["volg"]))): h["si"] = nr + 1
    par = sum(h["par"] for h in rij); n = len(keuze)
    cr = pr = sr = 0.0
    for b in dict.fromkeys(b for b, _ in keuze):
        k = sum(1 for bb, _ in keuze if bb == b); tot = len(cs[b]["holeIds"]); bt = cs[b]["tees"][g][t]
        cr += bt["CR"] * k / tot; pr += sum(h["par"] for h in bt["holes"]) * k / tot; sr += bt["SR"] * k / n
    return {"CR": js_round(cr + (par - pr), 1), "SR": int(js_round(sr)), "holes": [{"par": h["par"], "si": h["si"]} for h in rij]}

LUS = "(naam) => JSON.parse(localStorage.getItem('golf_clubs'))['Lusclub'].courses[naam] || null"
STATUS = "() => { const e = document.getElementById('lusStatus'); return e.classList.contains('hidden') ? '' : e.textContent; }"

async def open_maker(pg):
    await pg.evaluate("() => { sluitLusMaker(); nav('club'); openClubEditor('Lusclub'); }"); await pg.wait_for_timeout(200)
    await pg.click('#lusMaakKnop'); await pg.wait_for_timeout(150)

async def kies(pg, baan, indexen):
    await pg.click(f'[data-lus-bron="{baan}"]')
    for i in indexen: await pg.click(f'[data-lus-hole="{i}"]')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, []])
        await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Lusclub'); localStorage.setItem('golf_home_club', 'Lusclub'); }")
        await pg.reload(); await pg.wait_for_timeout(500)
        voor = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs'))")

        print("\n=== 1. WAARUIT JE KUNT KIEZEN ===\n")
        await open_maker(pg)
        check("bronbanen: de 18-holes combinatie voegt niets toe, de par-3-variant wel",
              await pg.evaluate("() => lusBronnen(lusClub)"), ['Oost', 'Oost (P3)', 'West'])

        print("\n=== 2. DE MAANWEDSTRIJD: O2, O3, O9, W1–W6 ===\n")
        await pg.fill('#lusNaam', 'Maanwedstrijd')
        await kies(pg, 'Oost', [1, 2, 8]); await kies(pg, 'West', [0, 1, 2, 3, 4, 5])
        check("telling", await pg.inner_text('#lusTelling'), '· 9 gekozen')
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        check("venster dicht", await pg.evaluate("() => document.getElementById('lusOverlay').classList.contains('hidden')"), True)
        lus = await pg.evaluate(LUS, 'Maanwedstrijd')
        keuze = [('Oost', 1), ('Oost', 2), ('Oost', 8)] + [('West', i) for i in range(6)]
        check("holes in speelvolgorde", lus['holeIds'], ['O2', 'O3', 'O9', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6'])
        check("markering wedstrijdlus", lus.get('lus'), True)
        check("alleen de tees die beide banen hebben", {g: sorted(m) for g, m in lus['tees'].items()}, {'Heren': ['Geel', 'Rood']})
        for t in ['Geel', 'Rood']:
            check(f"Heren {t}: par, SI, CR en SR kloppen met de naberekening", lus['tees']['Heren'][t], verwacht(keuze, ('Heren', t)))
        sis = [h['si'] for h in lus['tees']['Heren']['Rood']['holes']]
        check("SI is 1 t/m 9, elk één keer", sorted(sis), list(range(1, 10)))
        check("de app keurt de club goed (zelfde controle als bij inlezen)",
              await pg.evaluate("() => validateImportedClubData(CLUBS['Lusclub'])"), None)
        na = await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_clubs'))")
        del na['Lusclub']['courses']['Maanwedstrijd']
        check("de bestaande banen zijn onaangeroerd", na == voor, True)

        print("\n=== 3. EEN RONDE STARTEN OP DE LUS ===\n")
        r = await pg.evaluate("""() => { closeClubEditor?.(); nav('setup'); sel.track = 'Maanwedstrijd'; sel.gender = 'Heren'; sel.tee = 'Rood'; sel._teeUserSelected = true;
            document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8'; startRound();
            const t = COURSES['Maanwedstrijd'].tees.Heren.Rood;
            return { ids: game.holes.map(h => h.id), pars: game.holes.map(h => h.par), chcp: game.chcp,
                     hoort: calcChcp(9, t.CR, t.SR, teePar(t), 30.8), slagen: game.holes.reduce((s, h) => s + h.phcp, 0) }; }""")
        check("de ronde heeft de holes van de lus", r['ids'], ['O2', 'O3', 'O9', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6'])
        check("par per hole", r['pars'], [3, 5, 4, 4, 4, 3, 5, 4, 4])
        check("baanhandicap volgt uit de geschatte CR en SR", r['chcp'], r['hoort'])
        check("alle slagen zijn verdeeld", r['slagen'], r['chcp'])
        await pg.evaluate("() => finishActiveRound(null)")

        print("\n=== 4. WAT NIET MAG ===\n")
        await open_maker(pg); await pg.fill('#lusNaam', 'Leeg'); await pg.click('text=Opslaan als lus')
        check("zonder holes", await pg.evaluate(STATUS), 'Kies minstens één hole')
        await pg.fill('#lusNaam', '')
        await kies(pg, 'Oost', [0, 1]); await pg.click('[data-lus-hole="1"]')
        check("nog een keer tikken haalt de hole weg", await pg.evaluate("() => lusKeuze.length"), 1)
        await pg.click('text=Opslaan als lus')
        check("zonder naam", await pg.evaluate(STATUS), 'Vul een naam in')
        await pg.fill('#lusNaam', 'Oost'); await pg.click('text=Opslaan als lus')
        check("naam bestaat al", await pg.evaluate(STATUS), 'De naam "Oost" bestaat al')
        await pg.fill('#lusNaam', 'Proef')
        await pg.click('[data-lus-bron="Oost (P3)"]'); await pg.click('[data-lus-hole="0"]')
        check("dezelfde holenaam uit de par-3-variant", await pg.evaluate(STATUS), 'Hole O1 zit al in de lus')
        await open_maker(pg); await pg.fill('#lusNaam', 'Proef')
        await kies(pg, 'Oost (P3)', [0, 1, 2]); await kies(pg, 'West', [0, 1, 2, 3, 4, 5])
        await pg.click('text=Opslaan als lus')
        check("geen gezamenlijke tee", await pg.evaluate(STATUS), 'De gekozen banen hebben geen gezamenlijke tee')
        check("er is niets opgeslagen", await pg.evaluate(LUS, 'Proef'), None)
        check("een wedstrijdlus is zelf geen bron", 'Maanwedstrijd' in await pg.evaluate("() => lusBronnen(lusClub)"), False)

        print("\n=== 5. EEN LUS VAN 18 HOLES ===\n")
        await open_maker(pg); await pg.fill('#lusNaam', 'Lus 18')
        await kies(pg, 'West', range(9)); await kies(pg, 'Oost', range(9))
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        lus18 = await pg.evaluate(LUS, 'Lus 18')
        keuze18 = [('West', i) for i in range(9)] + [('Oost', i) for i in range(9)]
        check("18 holes, West eerst", lus18['holeIds'], W + O)
        check("Heren Geel klopt met de naberekening", lus18['tees']['Heren']['Geel'], verwacht(keuze18, ('Heren', 'Geel')))
        check("SI is 1 t/m 18, elk één keer", sorted(h['si'] for h in lus18['tees']['Heren']['Geel']['holes']), list(range(1, 19)))
        check("CR is de som van beide banen", lus18['tees']['Heren']['Geel']['CR'], 71.8)

        print("\n=== 5b. EEN LUS VAN 6 HOLES (net als gewone banen: elk aantal) ===\n")
        await open_maker(pg); await pg.fill('#lusNaam', 'Lus 6')
        await kies(pg, 'Oost', [0, 1, 2]); await kies(pg, 'West', [6, 7, 8])
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        lus6 = await pg.evaluate(LUS, 'Lus 6')
        keuze6 = [('Oost', 0), ('Oost', 1), ('Oost', 2), ('West', 6), ('West', 7), ('West', 8)]
        check("6 holes opgeslagen", lus6['holeIds'], ['O1', 'O2', 'O3', 'W7', 'W8', 'W9'])
        check("Heren Rood klopt met de naberekening", lus6['tees']['Heren']['Rood'], verwacht(keuze6, ('Heren', 'Rood')))

        print("\n=== 6. DE MARKERING OVERLEEFT DE BAANEDITOR ===\n")
        await pg.evaluate("() => { openCourseEditor('Maanwedstrijd'); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => saveCourseFromEditor()"); await pg.wait_for_timeout(300)
        check("na opslaan in de baaneditor nog steeds een wedstrijdlus", (await pg.evaluate(LUS, 'Maanwedstrijd')).get('lus'), True)
        await pg.evaluate("() => { openCourseEditor('Oost'); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => saveCourseFromEditor()"); await pg.wait_for_timeout(300)
        check("een gewone baan krijgt de markering niet", 'lus' in (await pg.evaluate(LUS, 'Oost')), False)

        print("\n=== 7. EIGEN KOP BIJ CLUBS ===\n")
        await pg.evaluate("() => { closeCourseEditor?.(); nav('club'); openClubEditor('Lusclub'); }"); await pg.wait_for_timeout(250)
        r = await pg.evaluate("""() => { const tekst = id => [...(document.getElementById(id)?.querySelectorAll('span') || [])].map(x => x.textContent.trim()).filter(Boolean);
            return { lus: tekst('clubCourseGrouplus').filter(t => !/^\\d+h$/.test(t)), negen: tekst('clubCourseGroup9').filter(t => !/^\\d+h$/.test(t)),
                     overig: !!document.getElementById('clubCourseGroupoverig') }; }""")
        check("Club bewerken: de lussen onder Lussen", r['lus'], ['Lus 18', 'Lus 6', 'Maanwedstrijd'])
        check("en niet meer tussen de 9-holesbanen", r['negen'], ['Oost', 'Oost (P3)', 'West'])
        check("de lus van 6 holes maakt geen groep Overig", r['overig'], False)

        print("\n=== 8. INKLAPKOP OP HET STARTSCHERM ===\n")
        LIJST = """() => ({ banen: [...document.querySelectorAll('#trackList .track-btn .track-name')].map(x => x.textContent),
            kop: document.getElementById('lusKop') ? document.getElementById('lusKop').innerText.replace(/\\s+/g, ' ').trim() : null, gekozen: sel.track })"""
        await pg.evaluate("() => { closeClubEditor?.(); localStorage.removeItem('golf_lussen_open'); nav('setup'); sel.showPar3 = false; selectHoleCount('9'); if (sel.holeCount !== '9') selectHoleCount('9'); sel.track = 'Oost'; buildTrackList(); }")
        k = await pg.evaluate(LIJST)
        check("standaard dicht: alleen de gewone banen", k['banen'], ['Oost', 'West'])
        check("de kop telt de lussen van 9 holes en die van 6", k['kop'], 'LUS 2')
        await pg.click('#lusKop'); k = await pg.evaluate(LIJST)
        check("open: de lussen eronder", k['banen'], ['Oost', 'West', 'Lus 6', 'Maanwedstrijd'])
        await pg.locator('#trackList .track-btn', has_text='Maanwedstrijd').click()
        await pg.click('#lusKop'); k = await pg.evaluate(LIJST)
        check("dicht met een gekozen lus: die blijft staan", (k['banen'], k['gekozen']), (['Oost', 'West', 'Maanwedstrijd'], 'Maanwedstrijd'))
        await pg.reload(); await pg.wait_for_timeout(400)
        check("open of dicht wordt onthouden", await pg.evaluate("() => localStorage.getItem('golf_lussen_open')"), '0')
        await pg.evaluate("() => { nav('setup'); sel.track = 'Oost'; selectHoleCount('18'); if (sel.holeCount !== '18') selectHoleCount('18'); }")
        await pg.click('#lusKop'); k = await pg.evaluate(LIJST)
        check("filter 18 holes: de lus van 18 en die van 6", k['banen'], ['Oost/West', 'Lus 18', 'Lus 6'])

        print("\n=== 9. CLUBBESTAND: UITLEZEN EN WEER INLEZEN ===\n")
        tekst = await pg.evaluate("""async () => { let uit = null; window.tryWriteToExportFolder = async (naam, json) => { uit = json; return true; };
            await exportAllClubs(); return uit; }""")
        bestand = json.loads(tekst)
        lijst = bestand if isinstance(bestand, list) else list(bestand.values())
        club = next(c for c in lijst if c['club'] == 'Lusclub')
        check("de markering staat in het clubbestand", club['courses']['Maanwedstrijd'].get('lus'), True)
        check("gewone banen hebben hem niet", 'lus' in club['courses']['Oost'], False)
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_lus_clubs.json')
        open(pad, 'w', encoding='utf-8').write(tekst)
        await pg.evaluate("() => { localStorage.setItem('golf_clubs', '{}'); }"); await pg.reload(); await pg.wait_for_timeout(400)
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importClubFile').set_input_files(pad); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { const k = document.getElementById('confirmModalBtn'); if (k && !document.getElementById('confirmModal').classList.contains('hidden')) k.click(); }")
        await pg.wait_for_timeout(300); os.remove(pad)
        terug = await pg.evaluate(LUS, 'Maanwedstrijd')
        check("na inlezen is het nog een wedstrijdlus, met dezelfde gegevens", terug, lus)
        await pg.reload(); await pg.wait_for_timeout(400)      # de melding 'Import voltooid' weg

        print("\n=== 10. EEN LUS KIEZEN ZET QUALIFYING UIT ===\n")
        await pg.evaluate("() => { nav('setup'); localStorage.setItem('golf_lussen_open', '1'); selectHoleCount('9'); if (sel.holeCount !== '9') selectHoleCount('9'); sel.qualifying = true; sel2.qualifying = true; sel.track = 'Oost'; rebuildStartScreen(); buildTrackList(); }")
        check("vooraf aan (gewone baan)", await pg.evaluate("() => [sel.qualifying, document.getElementById('qualifyToggle1').checked]"), [True, True])
        await pg.locator('#trackList .track-btn', has_text='Maanwedstrijd').click()
        check("na het kiezen van de lus: uit, ook voor speler 2", await pg.evaluate("() => [sel.qualifying, sel2.qualifying, document.getElementById('qualifyToggle1').checked]"), [False, False, False])
        await pg.evaluate("() => { sel.qualifying = true; rebuildStartScreen(); }")
        check("zelf weer aanzetten kan", await pg.evaluate("() => sel.qualifying"), True)

        print("\n=== 11. STATISTIEK: NIET IN HET OVERZICHT PER BAAN, WEL IN DE REST ===\n")
        rondes = [ronde(900 + i, f"2026-09-{10 + i:02d}", baan="Oost", club="Lusclub", kort="Lus", tee="Rood") for i in range(4)] \
               + [ronde(950 + i, f"2026-09-{20 + i:02d}", baan="Maanwedstrijd", club="Lusclub", kort="Lus", tee="Rood") for i in range(3)]
        for r in rondes:                      # de ronde bewaart de markering zelf
            if r["track"] == "Maanwedstrijd": r["lus"] = True
        await pg.evaluate("(r) => { localStorage.setItem('golf_rounds', JSON.stringify(r)); localStorage.setItem('golf_stats_grp_banen', 'open'); localStorage.setItem('golf_min_rounds_stat', '1'); }", rondes)
        await pg.reload(); await pg.wait_for_timeout(400)
        # De club staat standaard ingeklapt; dan worden de banen niet getekend.
        await pg.evaluate("() => { window._statClubCollapsed = { Lusclub: false }; nav('stat'); renderPlayerStats(); }"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("""() => { const l = leesRondes(); return {
            lus: l.filter(isLusRonde).length, gewoon: l.filter(x => !isLusRonde(x)).length,
            scherm: document.getElementById('screen-stat').textContent }; }""")
        check("drie rondes herkend als wedstrijdlus, vier als gewoon", (r['lus'], r['gewoon']), (3, 4))
        check("het overzicht noemt de gewone baan", 'Oost' in r['scherm'], True)
        check("en de wedstrijdlus niet", 'Maanwedstrijd' in r['scherm'], False)
        check("alle zeven rondes tellen mee in de statistiek", await pg.evaluate("() => (typeof analysisRounds === 'function' ? analysisRounds().length : -1)"), 7)
        await pg.evaluate("() => { const l = loadSavedRounds(); l.forEach(r => delete r.lus); setRoundsAndMark(JSON.stringify(l)); nav('archive'); nav('stat'); renderPlayerStats(); }"); await pg.wait_for_timeout(400)
        check("zonder de markering staat hij er wel (de test kijkt dus echt)", 'Maanwedstrijd' in await pg.evaluate("() => document.getElementById('screen-stat').textContent"), True)

        print("\n=== 11b. HET BEWERKVENSTER NOEMT EEN LUS EEN LUS ===\n")
        ED = """(n) => { nav('club'); openClubEditor('Lusclub'); openCourseEditor(n);
            const uit = [document.getElementById('courseEditorTitle').textContent, document.querySelector('label[for=editorCourseName]').textContent, document.getElementById('editorCourseName').placeholder];
            closeCourseEditor(); return uit; }"""
        check("een lus: titel, kop en hulptekst", await pg.evaluate(ED, 'Maanwedstrijd'), ['Lus bewerken', 'Lus', 'Naam van de lus'])
        check("een gewone baan daarna: weer baan", await pg.evaluate(ED, 'Oost'), ['Baan bewerken', 'Baan', 'Naam van de baan'])
        check("een nieuwe baan", await pg.evaluate(ED, '__new__'), ['Nieuwe baan', 'Baan', 'Naam van de baan'])
        check("tekstexport van een ronde: Lus bij een lusronde, Baan bij een gewone",
              await pg.evaluate("""() => [true, false].map(l => buildScoreText({ ...leesRondes()[0], lus: l || undefined }).split('\\n').filter(r => /^(Baan|Lus):/.test(r))[0].split(':')[0])"""), ['Lus', 'Baan'])

        print("\n=== 12. EIGEN KOP OP HET TABBLAD CLUBS ===\n")
        await pg.reload(); await pg.wait_for_timeout(400)
        await pg.evaluate("() => nav('club')"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => { const g = id => { const e = document.getElementById('courseSubGroup_Lusclub_' + id); return e ? e.innerText.replace(/\\s+/g, ' ').trim() : null; };
            return { lus: g('lus'), negen: g('9') }; }""")
        check("de lussen staan onder Lussen", all(n in (r['lus'] or '') for n in ['Maanwedstrijd', 'Lus 18', 'Lus 6']), True)
        check("en niet onder 9 holes", 'Maanwedstrijd' in (r['negen'] or ''), False)
        check("de knop heet Nieuwe lus", await pg.evaluate("() => document.getElementById('lusMaakKnop').innerText.trim()"), 'Nieuwe lus')

        print("\n=== 13. DE APP KIEST ZELF EEN LUS: OOK DAN QUALIFYING UIT ===\n")
        r = await pg.evaluate("""() => { nav('setup'); localStorage.setItem('golf_lussen_open', '0');
            sel.qualifying = true; sel2.qualifying = true; document.getElementById('qualifyToggle1').checked = true;
            localStorage.setItem('golf_default_club', 'Alleenlus'); sel.holeCount = null; sel._holeCountUserCleared = false; sel.track = null;
            rebuildCourseLookup(false); buildTrackList();
            return { gekozen: sel.track, qual: [sel.qualifying, sel2.qualifying, document.getElementById('qualifyToggle1').checked],
                     knoppen: [...document.querySelectorAll('#trackList .track-btn')].map(b => [b.querySelector('.track-name').textContent, b.classList.contains('active')]) }; }""")
        check("de enige baan is de lus, en die is gekozen", r['gekozen'], 'Solo')
        check("qualifying is uitgezet", r['qual'], [False, False, False])
        check("de lus staat er, als gekozen getekend, ook met de kop dicht", r['knoppen'], [['Solo', True]])
        await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Lusclub'); sel.track = 'Oost'; buildTrackList(); }")

        print("\n=== 14. ÉÉN CLUB EXPORTEREN (de echte knop) ===\n")
        await pg.evaluate("() => { window._uit = null; window.tryWriteToExportFolder = async (naam, json) => { window._uit = json; return true; }; nav('club'); }")
        await pg.wait_for_timeout(300)
        knop = pg.locator('button[data-club="Lusclub"][onclick^="exportClub"]').first
        await pg.evaluate("() => { const k = document.querySelector('button[data-club=\"Lusclub\"][onclick^=\"exportClub\"]'); k.closest('.card').querySelectorAll('.hidden').forEach(e => e.classList.remove('hidden')); k.scrollIntoView({block:'center'}); }")
        await knop.click(); await pg.wait_for_timeout(120); await knop.click(); await pg.wait_for_timeout(400)
        uit = json.loads(await pg.evaluate("() => window._uit") or 'null')
        club1 = (uit[0] if isinstance(uit, list) else uit) if uit else {}
        check("het clubbestand bevat de lus mét markering", (club1.get('courses', {}).get('Maanwedstrijd') or {}).get('lus'), True)

        print("\n=== 15. OPSLAAN SCHRIJFT DE CLUBGEGEVENS ÉÉN KEER WEG ===\n")
        TEL = """() => { window._n = 0; if (!window._orig) { window._orig = Storage.prototype.setItem;
            Storage.prototype.setItem = function (k, v) { if (k === 'golf_clubs') window._n++; return window._orig.call(this, k, v); }; } }"""
        await pg.evaluate(TEL); await open_maker(pg); await pg.fill('#lusNaam', 'Telproef')
        await kies(pg, 'Oost', [0, 1, 2]); await pg.evaluate("() => { window._n = 0; }")
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(250)
        check("een wedstrijdlus opslaan: één keer", await pg.evaluate("() => window._n"), 1)
        await pg.evaluate("() => { openCourseEditor('Oost'); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { window._n = 0; saveCourseFromEditor(); }"); await pg.wait_for_timeout(300)
        check("een baan opslaan in de baaneditor: één keer", await pg.evaluate("() => window._n"), 1)

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
