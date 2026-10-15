"""Een lopende ronde verandert niet door wat je op de ANDERE schermen doet.

Vervolg op test-startscherm-lopende-ronde.py. Dezelfde regel, nu voor Rondes, Clubs,
Instellingen en Statistiek: je bewerkt een andere ronde, past een baan aan, zet een
schakelaar om, maakt een backup of leest iets in — en de ronde die loopt blijft precies
zoals hij was, in het geheugen en in de opslag.

Er loopt een ronde van twee spelers met scores, putts en notities. Daarnaast staan er
andere rondes (afgerond, gepland). Na elke handeling wordt de lopende ronde vergeleken
met hoe hij ervoor was; met speler 1 en met speler 2 op het scherm.

Niet in deze lijst: handelingen die bedoeld zijn om de lopende ronde te raken (hem zelf
bewerken, een andere ronde laden, alles wissen).
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {echt} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
def ids(l, n=9): return [f"{l}{i}" for i in range(1, n + 1)]
CLUBS = {
  "Club A": {"club": "Club A", "shortName": "A", "courses": {
    "Noord": {"holeIds": ids('A'), "tees": {"Heren": {"Geel": tee(35.0, 120, PA)}, "Dames": {"Rood": tee(36.5, 126, PA)}}},
    "Zuid":  {"holeIds": ids('Z'), "tees": {"Heren": {"Geel": tee(33.1, 112, PB)}}}}},
  "Club B": {"club": "Club B", "shortName": "B", "courses": {
    "West": {"holeIds": ids('W'), "tees": {"Heren": {"Geel": tee(38.0, 139, PB)}}}}},
}
def ronde(rid, datum, speler, baan='Zuid', gespeeld=9, qual=True):
    pars = PB if baan == 'Zuid' else PA
    return {"id": rid, "date": datum, "time": "09:00", "player": speler, "hcp": 24.0, "gender": "Heren", "track": baan, "tee": "Geel",
            "club": "Club A", "clubShort": "A", "CR": 33.1, "SR": 112, "PAR": sum(pars), "chcp": 10, "qualifying": qual, "started": True,
            "holesCount": 9, "currentHole": 0, "total": 0, "totalStb": 0,
            "holes": [{"id": f"Z{i+1}", "par": p, "si": i + 1, "phcp": 1, "ppar": p + 1, "score": (p + 1 if i < gespeeld else None), **({"putts": 2} if i < gespeeld else {})} for i, p in enumerate(pars)]}
ANDERE = [ronde(101, "2026-08-01", "Mark"), ronde(102, "2026-08-08", "Mark"), ronde(103, "2026-08-15", "Anna"),
          ronde(104, "2026-08-22", "Mark", qual=False), ronde(105, "2027-05-01", "Mark", gespeeld=0)]

FOTO = """() => { const eigen = new Set([String(localStorage.getItem('golf_active_id')), String(localStorage.getItem('golf_game2_id'))]);
  return { opslag: leesRondes().filter(r => eigen.has(String(r.id))).map(x => JSON.stringify(x, (k, v) => (k === '_initScore' ? undefined : v))).sort(),
    geheugen: JSON.stringify({ ...game, holes: game.holes.map(h => ({ ...h, _initScore: undefined })) }),
    actief: localStorage.getItem('golf_active_id'), g2: localStorage.getItem('golf_game2_id'), speler: activePlayer, hole: currentHole }; }"""
SLUIT = """() => { document.querySelectorAll('[id$=Modal], [id$=Overlay]').forEach(m => { if (!m.classList.contains('hidden')) m.classList.add('hidden'); });
    if (typeof annuleerHerplan === 'function') annuleerHerplan(); }"""
IDX = "(id) => leesRondes().findIndex(r => r.id === id)"

async def inlezen(pg, veld, inhoud, bevestig=True):
    pad = os.path.join(HIER, '_inlees.json'); open(pad, 'w', encoding='utf-8').write(json.dumps(inhoud))
    await pg.evaluate("() => nav('settings')"); await pg.locator(veld).set_input_files(pad); await pg.wait_for_timeout(500)
    if bevestig:
        await pg.evaluate("() => { const k = document.getElementById('confirmModalBtn'); if (k && !document.getElementById('confirmModal').classList.contains('hidden')) k.click(); }")
        await pg.wait_for_timeout(300)
    os.remove(pad)

async def baan_cr(pg, club, baan, cr):
    # De baaneditor zelf: openen, CR van de eerste tee wijzigen, opslaan.
    await pg.evaluate("""([club, baan, cr]) => { nav('club'); openClubEditor(club); openCourseEditor(baan);
        const v = document.querySelector('#editorTeesBody .cr-name-field, .cr-name-field'); v.dataset.value = cr; v.textContent = cr; saveCourseFromEditor(); }""", [club, baan, cr])
    await pg.wait_for_timeout(300)

async def klik_alles(pg, scherm):
    # Elke bedienbare kop en knop op dit scherm één keer aantikken.
    n = await pg.evaluate("(s) => document.querySelectorAll('#screen-' + s + ' [onclick]').length", scherm)
    for i in range(min(n, 60)):
        await pg.evaluate("""([s, i]) => { const e = document.querySelectorAll('#screen-' + s + ' [onclick]')[i]; if (e && e.offsetParent) e.click(); }""", [scherm, i])
    await pg.wait_for_timeout(200)

TWEE = lambda f: f"() => {{ {f}(); {f}(); }}"
HANDELINGEN = [
    # ── Rondes
    ("Rondes: alle groeperingen omzetten",      "() => { nav('archive'); toggleGroupByCategory(); toggleGroupByPlanned(); toggleGroupByPlayer(); toggleGroupByTrack(); toggleGroupByWhs(); toggleGroupByWhs(); }"),
    ("Rondes: zoeken",                          "() => { const z = document.getElementById('archiveSearch'); z.value = 'Zuid'; zoekInRondes(); z.value = ''; zoekInRondes(); }"),
    ("Rondes: notitie van een ANDERE ronde",    "() => { doOpenRoundInfoModal(leesRondes().findIndex(r => r.id === 101)); document.getElementById('editNoteInput').value = 'andere ronde'; confirmRoundInfo(); }"),
    ("Rondes: datum van een andere ronde",      "() => { doOpenRoundInfoModal(leesRondes().findIndex(r => r.id === 102)); document.getElementById('editDateInput').value = '2026-07-30'; confirmRoundInfo(); }"),
    ("Rondes: speler van een andere ronde",     "() => { doOpenRoundInfoModal(leesRondes().findIndex(r => r.id === 102)); document.getElementById('editPlayerInput').value = 'Kees'; confirmRoundInfo(); }"),
    ("Rondes: andere ronde vaststellen",        "() => { doOpenRoundResultModal(leesRondes().findIndex(r => r.id === 101)); document.getElementById('editSdInput').value = '31.5'; confirmRoundResult(); }"),
    ("Rondes: ronde van speler 2's naamgenoot", "() => { doOpenRoundInfoModal(leesRondes().findIndex(r => r.id === 103)); document.getElementById('editNoteInput').value = 'oude ronde Anna'; confirmRoundInfo(); }"),
    ("Rondes: andere ronde verwijderen",        "() => { metVerwijderen(() => setRoundsAndMark(JSON.stringify(loadSavedRounds().filter(r => r.id !== 104)))); loadSaved(); }"),
    ("Rondes: geplande ronde opnieuw plannen, dan afbreken", "() => { herplanRonde(105); annuleerHerplan(); nav('archive'); }"),
    ("Rondes: andere ronde corrigeren, dan afbreken",        "() => { herplanRonde(101, true); annuleerHerplan(); nav('archive'); }"),
    ("Rondes: ronde inlezen uit een bestand",   lambda pg: inlezen(pg, '#importRoundFile', [{k: v for k, v in ronde(0, "2026-06-01", "Mark").items() if k != 'id'}])),
    # ── Clubs
    ("Clubs: de baan van de lopende ronde aanpassen (CR)", lambda pg: baan_cr(pg, 'Club A', 'Noord', '41.2')),
    ("Clubs: een andere baan aanpassen",        lambda pg: baan_cr(pg, 'Club A', 'Zuid', '30.3')),
    ("Clubs: een baan van een andere club",     lambda pg: baan_cr(pg, 'Club B', 'West', '39.9')),
    ("Clubs: thuisclub en favoriet omzetten",   "() => { openClubEditor('Club B'); toggleHomeClubInEditor(); toggleFavClubInEditor(); toggleHomeClubInEditor(); }"),
    ("Clubs: een wedstrijdlus maken",           "() => { openClubEditor('Club A'); openLusMaker(); document.getElementById('lusNaam').value = 'Lusje'; kiesLusBron('Noord'); [0,1,2].forEach(tikLusHole); bewaarLus(); }"),
    ("Clubs: clubbestand inlezen (overschrijven)", lambda pg: inlezen(pg, '#importClubFile', {**CLUBS['Club A'], "shortName": "A"})),
    ("Clubs: andere club kiezen op het clubtabblad", "() => { nav('club'); setDefaultClub('Club B'); setDefaultClub('Club A'); }"),
    ("Clubs: zoeken en groeperen",              "() => { nav('club'); toggleClubGroupByCategory(); toggleClubGroupByCategory(); }"),
    # ── Instellingen
    ("Instellingen: putts bijhouden uit en aan",        TWEE('toggleTrackPutts')),
    ("Instellingen: puttstatistiek uit en aan",         TWEE('togglePuttsStats')),
    ("Instellingen: handicap bijhouden uit en aan",     TWEE('toggleWhsVolgen')),
    ("Instellingen: automatisch doorspringen",          TWEE('toggleAutoNext')),
    ("Instellingen: thema",                             TWEE('toggleTheme')),
    ("Instellingen: symbolen op de scorekaart",         TWEE('toggleScorecardSymbols')),
    ("Instellingen: voortgangsbalk",                    TWEE('toggleProgressIndicator')),
    ("Instellingen: slecht weer",                       TWEE('toggleBadWeather')),
    ("Instellingen: acties altijd zichtbaar",           TWEE('toggleActionsAlwaysVisible')),
    ("Instellingen: minimum aantal rondes",             "() => { adjustMinRoundsStat(1); adjustMinRoundsStat(-1); }"),
    ("Instellingen: tabbladen wisselen",                "() => { nav('settings'); switchSettingsTab('whs'); switchSettingsTab('data'); switchSettingsTab('main'); }"),
    ("Instellingen: backup van de rondes maken",        "async () => { window.tryWriteToExportFolder = async () => true; await exportAllRounds(); }"),
    ("Instellingen: backup van de clubs maken",         "async () => { window.tryWriteToExportFolder = async () => true; await exportAllClubs(); }"),
    ("Instellingen: dagresultaten exporteren",          "async () => { window.tryWriteToExportFolder = async () => true; try { await exportDagresultaten(); } catch (e) {} }"),
    ("Instellingen: niet-qualifying rondes verwijderen", "() => { nav('settings'); const k = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').startsWith('confirmPurgeNonQ')); confirmPurgeNonQ(k); confirmPurgeNonQ(k); document.getElementById('dangerModalConfirmBtn').click(); }"),
    ("Instellingen: rondes van andere spelers verwijderen", "() => { nav('settings'); const k = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').startsWith('confirmDeleteOtherPlayers')); confirmDeleteOtherPlayers(k); confirmDeleteOtherPlayers(k); document.getElementById('dangerModalConfirmBtn').click(); }"),
    # ── Statistiek
    ("Statistiek: elke kop en knop aantikken",          lambda pg: klik_alles(pg, 'stat')),
    ("Statistiek: nog een keer (alles weer terug)",     lambda pg: klik_alles(pg, 'stat')),
    # ── Algemeen
    ("alle tabbladen langs",                            "() => ['archive', 'stat', 'club', 'settings', 'setup', 'score'].forEach(nav)"),
    ("pagina herladen",                                 lambda pg: pg.reload()),
]

async def opzet(pg, speler2):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, ANDERE])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Noord'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true; sel.qualifying = true; sel2.qualifying = true;
        document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8';
        player2Visible = true; sel2.gender = 'Dames'; sel2.tee = 'Rood'; sel2._teeUserSelected = true;
        document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
        zetStartNote(1, 'notitie Mark'); zetStartNote(2, 'notitie Anna'); startRound(); }"""); await pg.wait_for_timeout(300)
    await pg.evaluate("""() => { for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, +1); stepPutts(i, +1); }
        switchToPlayer(2); for (let i = 0; i < 2; i++) { setCurrentHole(i); stepScore(i, +1); stepPutts(i, -1); } }""")
    if not speler2: await pg.evaluate("() => switchToPlayer(1)")
    await pg.wait_for_timeout(150)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        for speler2 in (False, True):
            print(f"\n=== LOPENDE RONDE VAN TWEE SPELERS, SPELER {2 if speler2 else 1} OP HET SCHERM ===\n")
            await opzet(pg, speler2)
            foto = await pg.evaluate(FOTO)
            check("de ronde loopt, met scores en putts van beide spelers", (len(foto['opslag']), foto['speler'], '"putts"' in foto['geheugen']), (2, 2 if speler2 else 1, True))
            for naam, doe in HANDELINGEN:
                herladen = naam == "pagina herladen"
                if isinstance(doe, str): await pg.evaluate(doe)
                else: await doe(pg)
                await pg.wait_for_timeout(350 if herladen else 150)
                if not herladen: await pg.evaluate(SLUIT)
                na = await pg.evaluate(FOTO)
                # Na herladen staat speler 1 op het scherm: het geheugen is dan per definitie
                # anders. Wat telt is dat de opgeslagen rondes en de koppeling gelijk zijn.
                sleutels = ['opslag', 'actief', 'g2'] if herladen else list(foto)
                verschil = [k for k in sleutels if foto[k] != na[k]]
                check(naam, verschil, [])
                if verschil and not herladen:
                    await opzet(pg, speler2); foto = await pg.evaluate(FOTO)
        print("\n=== DE WISKNOPPEN DOEN NOG WEL HUN WERK, EN SLAAN ALLEEN DE LOPENDE RONDE OVER ===\n")
        for q in (False, True):
            await opzet(pg, False)
            if not q: await pg.evaluate("() => { const l = loadSavedRounds(); l.forEach(r => { if (r.id > 5000) r.qualifying = false; }); setRoundsAndMark(JSON.stringify(l)); game.qualifying = false; }")
            await pg.evaluate("() => { nav('settings'); const k = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').startsWith('confirmPurgeNonQ')); confirmPurgeNonQ(k); confirmPurgeNonQ(k); document.getElementById('dangerModalConfirmBtn').click(); }")
            await pg.wait_for_timeout(200)
            r = await pg.evaluate("() => ({ lopend: leesRondes().filter(r => r.id > 5000).length, losseNietQ: leesRondes().filter(r => r.id < 5000 && !r.qualifying).length, losseQ: leesRondes().filter(r => r.id < 5000 && r.qualifying).length })")
            check(f"niet-qualifying wissen (lopende ronde {'wel' if q else 'niet'} qualifying): lopende blijven, losse niet-qualifying weg", r, {'lopend': 2, 'losseNietQ': 0, 'losseQ': 4})
        await opzet(pg, False)
        await pg.evaluate("() => { nav('settings'); const k = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').startsWith('confirmDeleteOtherPlayers')); confirmDeleteOtherPlayers(k); confirmDeleteOtherPlayers(k); document.getElementById('dangerModalConfirmBtn').click(); }")
        await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => leesRondes().map(r => [r.player, r.id > 5000]).sort()")
        check("andere spelers wissen: de oude ronde van Anna weg, haar lopende ronde blijft", r, [['Anna', True], ['Mark', False], ['Mark', False], ['Mark', False], ['Mark', False], ['Mark', True]])
        await pg.evaluate("() => { nav('score'); switchToPlayer(2); stepScore(currentHole, +1); }")
        check("en speler 2 speelt gewoon verder", await pg.evaluate("() => [game.player, activePlayer]"), ['Anna', 2])

        print("\n=== DE DATUM VAN EEN LOPENDE RONDE WIJZIGEN ONTKOPPELT NOG WEL ===\n")
        await opzet(pg, False)
        await pg.evaluate("() => { doOpenRoundInfoModal(leesRondes().findIndex(r => String(r.id) === localStorage.getItem('golf_game2_id'))); document.getElementById('editDateInput').value = '2026-01-02'; confirmRoundInfo(); }")
        await pg.wait_for_timeout(200)
        check("koppeling weg, zoals bedoeld", await pg.evaluate("() => localStorage.getItem('golf_game2_id')"), None)

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
