"""De vier wegen die nog niet waren afgelegd.

  1. IMPORTEREN via de echte weg: een bestand kiezen, laten inlezen en samenvoegen.
     Dat is het vangnet als er iets misgaat, en het heeft eigen logica (dubbele rondes
     overslaan, de opslagcode vergelijken) die met direct wegschrijven niet wordt geraakt.
  2. ACHTTIEN HOLES: alle andere tests van vandaag gebruiken 9-holesrondes, terwijl de
     app 18 holes anders omrekent en een eigen verlooptabel heeft.
  3. LANG INDRUKKEN terwijl SPELER 2 aan de beurt is — die heeft een eigen actieve ronde.
  4. EEN CLUB WIJZIGEN TERWIJL ER EEN RONDE LOOPT: dan raken de clubvingerafdruk, de
     teevolgorde en de lopende ronde elkaar.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


def ronde18(rid, datum):
    """Een volledige 18-holesronde op Airborne (twee lussen van negen)."""
    return {
        "id": rid, "date": datum, "time": "09:00", "player": "Testspeler", "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "GC Heelsum", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 71.2, "SR": 135, "PAR": 72,
        "chcp": 30, "qualifying": True, "note": "", "total": 90, "totalStb": 36,
        "playedCount": 18, "holesCount": 18, "currentHole": 0, "started": True,
        "sd": 29.0, "sdFinal": 29.0, "pcc": 0,
        "holes": [{"id": "A%d" % (i % 9 + 1), "par": 4, "si": (i % 9) + 1,
                   "phcp": 2, "ppar": 6, "score": 5, "putts": 2} for i in range(18)],
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))

        await page.goto(app_url())
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
            localStorage.setItem('golf_storage_id', 'AAAA');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(700)

        print("=== 1. IMPORTEREN VIA DE ECHTE WEG ===\n")
        # Een backupbestand met vijf 18-holesrondes, met de eigen opslagcode in de naam.
        rondes = [ronde18(3000 + i, '2024-%02d-%02d' % ((i % 12) + 1, (i % 28) + 1))
                  for i in range(5)]
        map_ = tempfile.mkdtemp()
        bestand = os.path.join(map_, 'rondes_backup_20260829_AAAA.json')
        with open(bestand, 'w') as f:
            json.dump(rondes, f)

        await page.evaluate("() => { nav('settings'); switchSettingsTab('data'); }")
        await page.wait_for_timeout(300)
        invoer = await page.query_selector('#importRoundFile')
        await invoer.set_input_files(bestand)
        await page.wait_for_timeout(1200)

        na1 = await page.evaluate("""() => ({
            aantal: loadSavedRounds().length,
            venster: document.getElementById('confirmModalTitle').textContent,
            achttien: loadSavedRounds().filter(r => (r.holesCount || 0) === 18).length,
        })""")
        check("de rondes zijn ingelezen", na1["aantal"], 5)
        check("het zijn 18-holesrondes", na1["achttien"], 5)
        check("met een bevestiging", na1["venster"], "Import voltooid")
        await page.evaluate("() => closeConfirmModal()")
        await page.wait_for_timeout(300)

        # Nog eens hetzelfde bestand: dubbele rondes horen te worden overgeslagen.
        invoer = await page.query_selector('#importRoundFile')
        await invoer.set_input_files(bestand)
        await page.wait_for_timeout(1200)
        na2 = await page.evaluate("() => loadSavedRounds().length")
        check("een tweede keer importeren verdubbelt niets", na2, 5)
        await page.evaluate("() => closeConfirmModal()")

        print("\n=== 2. ACHTTIEN HOLES: BEREKENINGEN ===\n")
        achttien = await page.evaluate("""() => {
            nav('archive'); tekenRondelijst();
            const t = handicapTabellen().hcpTrendMap;
            const ids = Object.keys(t);
            const r = loadSavedRounds()[0];
            return {
                tabelregels: ids.length,
                gespeeld: gespeeldeHoles(r),
                af: isRondeAf(r),
                sd: effectiveSD(r) ? effectiveSD(r).value : null,
            };
        }""")
        check("alle 18-holesrondes zitten in de tabel", achttien["tabelregels"], 5)
        check("achttien holes worden geteld", achttien["gespeeld"], 18)
        check("de ronde geldt als afgerond", achttien["af"], True)
        check("en heeft een dagresultaat", achttien["sd"], 29.0)

        # Statistieken moeten de 18-holesregel tonen, niet die voor 9 holes.
        statregels = await page.evaluate("""() => {
            nav('stat');
            ['handicap', 'prestaties', 'banen'].forEach(k =>
                localStorage.setItem('golf_stats_grp_' + k, 'open'));
            renderPlayerStats();
            const t = document.getElementById('screen-stat').innerText;
            return { achttien: t.includes('18 holes'), negen: t.includes('9 holes') };
        }""")
        check("de statistieken tonen de 18-holesregel", statregels["achttien"], True)

        print("\n=== 3. LANG INDRUKKEN MET SPELER 2 AAN DE BEURT ===\n")
        await page.evaluate("""() => {
            nav('setup');
            sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
            sel.qualifying = true;
            document.getElementById('iName').value = 'Testspeler';
            document.getElementById('iHcp').value = '30.7';
            togglePlayer2(true);
        }""")
        await page.wait_for_timeout(300)
        await page.evaluate("""() => {
            const n2 = document.getElementById('iName2');
            const h2 = document.getElementById('iHcp2');
            if (n2) n2.value = 'Partner';
            if (h2) h2.value = '18.0';
            sel2.track = 'Airborne'; sel2.gender = 'Heren'; sel2.tee = 'Blauw';
            sel2.qualifying = true;
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
        }""")
        await page.wait_for_timeout(500)
        await page.evaluate("""() => {
            switchToPlayer(2);
            nav('score');
            for (let h = 0; h < 5; h++) {
                setCurrentHole(h); selectHole(h);
                armScoreChange(h, 4); clearScoreTap(false);
            }
        }""")
        await page.wait_for_timeout(400)
        voorToggle = await page.evaluate("""() => {
            const r = loadSavedRounds().find(x => x.player === 'Partner');
            return { speler: game.player, scores: r.holes.filter(h => h.score !== null).length };
        }""")
        check("speler 2 is aan de beurt", voorToggle["speler"], "Partner")
        check("met vijf ingevoerde holes", voorToggle["scores"], 5)

        naToggle = await page.evaluate("""() => {
            nav('archive');
            alleSpelersDichtOfOpen(); alleSpelersDichtOfOpen();
            alleClubsDichtOfOpen();   alleClubsDichtOfOpen();
            toggleAlleArchiefJaren();
            setWhsShort(); setWhsShort();
            const r = loadSavedRounds().find(x => x.player === 'Partner');
            return { speler: game.player, actief: !!game.started,
                     scores: r.holes.filter(h => h.score !== null).length };
        }""")
        check("speler 2 blijft aan de beurt", naToggle["speler"], "Partner")
        check("de ronde loopt nog", naToggle["actief"], True)
        check("en de scores staan er nog", naToggle["scores"], 5)

        print("\n=== 4. EEN CLUB WIJZIGEN TIJDENS EEN LOPENDE RONDE ===\n")
        tijdens = await page.evaluate("""() => {
            const voorScores = loadSavedRounds()
                .find(x => x.player === 'Partner').holes.filter(h => h.score !== null).length;
            const voorVolgorde = [...teeVolgordeIndex().keys()];

            // par van hole 1 wijzigen op de baan die nu gespeeld wordt
            const baan = CLUBS['Golfclub Heelsum'].courses['Airborne'];
            const tee = baan.tees['Heren']['Blauw'];
            const oudePar = tee.holes[0].par;
            tee.holes[0].par = oudePar === 5 ? 4 : 5;
            // en een nieuwe tee toevoegen
            baan.tees['Heren']['Zilver'] = { CR: 35, SR: 120,
                holes: tee.holes.map(h => ({ ...h })) };
            saveClubsToStorage();

            const naVolgorde = [...teeVolgordeIndex().keys()];
            const naScores = loadSavedRounds()
                .find(x => x.player === 'Partner').holes.filter(h => h.score !== null).length;
            return {
                scoresGelijk: voorScores === naScores,
                actief: !!game.started,
                speler: game.player,
                nieuweTeeGezien: naVolgorde.includes('Zilver') && !voorVolgorde.includes('Zilver'),
                clubsMelding: isClubsBackupOverdue(),
            };
        }""")
        check("de lopende ronde blijft ongemoeid", tijdens["scoresGelijk"], True)
        check("en loopt nog", tijdens["actief"], True)
        check("met dezelfde speler", tijdens["speler"], "Partner")
        check("de nieuwe tee zit meteen in de volgorde", tijdens["nieuweTeeGezien"], True)
        check("en de clubbackup wordt gemeld", tijdens["clubsMelding"], True)

        # Verder scoren moet gewoon werken na de clubwijziging.
        verder = await page.evaluate("""() => {
            nav('score');
            setCurrentHole(5); selectHole(5);
            armScoreChange(5, 6); clearScoreTap(false);
            const r = loadSavedRounds().find(x => x.player === 'Partner');
            return r.holes.filter(h => h.score !== null).length;
        }""")
        check("er kan gewoon verder gescoord worden", verder, 6)

        print("\n=== 5. EEN RONDE ZONDER DATUM BLIJFT ZICHTBAAR ===\n")
        # De vlakke lijst klapt jaren ouder dan vorig jaar in. Een ronde zonder datum
        # kreeg daar een leeg "jaartal", en dat telt als 0 — dus ouder dan vorig jaar en
        # ingeklapt. Er hoort bij zo'n ronde geen jaarkop, dus was hij daarna nergens
        # meer open te klappen: onzichtbaar, terwijl hij wel in de opslag stond.
        zonderDatum = await page.evaluate("""() => {
            const basis = loadSavedRounds()[0];
            const lijst = [
                { ...basis, id: 8001, date: '', holes: basis.holes.map(h => ({ ...h })) },
                { ...basis, id: 8002, date: '2026-08-02', holes: basis.holes.map(h => ({ ...h })) },
                { ...basis, id: 8003, date: '2019-05-05', holes: basis.holes.map(h => ({ ...h })) },
            ];
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
            nav('archive');
            zetGroepering(null);
            window._flatYearCollapsed = {};
            tekenRondelijst();
            return {
                kaarten: document.querySelectorAll('#screen-archive .saved-item').length,
                oudJaarDicht: isArchiveYearCollapsed('2019'),
                leegJaarDicht: isArchiveYearCollapsed(''),
                onzin: isArchiveYearCollapsed('abcd'),
            };
        }""")
        # Twee kaarten: die van dit jaar en die zonder datum. 2019 blijft ingeklapt.
        check("de ronde zonder datum is zichtbaar", zonderDatum["kaarten"], 2)
        check("een oud jaar blijft ingeklapt", zonderDatum["oudJaarDicht"], True)
        check("een leeg jaartal niet", zonderDatum["leegJaarDicht"], False)
        check("een onzinnig jaartal ook niet", zonderDatum["onzin"], False)

        print("\n=== 6. DE ACTIES BIJ EEN GEPLANDE RONDE ===\n")
        # 'Zet in agenda' zit in het deelvenster en 'Opnieuw plannen' in het
        # bewerkvenster, dus de kaart heeft geen apart planmenu meer. En 'Ronde
        # resultaat' staat uit bij een ronde zonder scores: daar een dagresultaat
        # invullen zou meetellen in de handicapberekening van een ronde die niet
        # gespeeld is.
        await page.evaluate("""(rondes) => {
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rondes)));
        }""", [
            {**{k: v for k, v in ronde18(7001, '2027-06-01').items()},
             'playedCount': 0, 'started': False, 'total': 0, 'totalStb': 0,
             'sd': None, 'sdFinal': None,
             'holes': [{'id': 'H%d' % (i + 1), 'par': 4, 'si': i + 1, 'phcp': 1,
                        'ppar': 5, 'score': None} for i in range(18)]},
            ronde18(7002, '2024-06-01'),
        ])
        await page.evaluate("() => { nav('archive'); tekenRondelijst(); }")
        await page.wait_for_timeout(300)

        acties = await page.evaluate("""() => {
            const idxGepland = loadSavedRounds().findIndex(r => r.id === 7001);
            const idxGespeeld = loadSavedRounds().findIndex(r => r.id === 7002);
            // De agenda-optie wordt niet verborgen maar UITGEZET, zoals overal in de app.
            const formaten = () => [...document.querySelectorAll('.export-opt')]
                .map(b => ({ f: b.dataset.format, uit: !!b.disabled }));
            const knop = id => {
                const e = document.getElementById(id);
                return { zichtbaar: !e.classList.contains('hidden'), uit: !!e.disabled };
            };

            openExportModal(idxGepland);
            const deelGepland = formaten();
            closeExportModal();

            openExportModal(idxGespeeld);
            const deelGespeeld = formaten();
            // Klikken op een uitgezette optie mag niets kiezen.
            document.getElementById('exportOptAgenda').click();
            const naKlik = _exportModalFormat;
            closeExportModal();

            openRoundEditChoice(idxGepland);
            const bewerkGepland = { resultaat: knop('roundEditChoiceResult'),
                                    herplan: knop('roundEditChoiceHerplan') };
            sluitRoundEditChoice();

            openRoundEditChoice(idxGespeeld);
            const bewerkGespeeld = { resultaat: knop('roundEditChoiceResult'),
                                     herplan: knop('roundEditChoiceHerplan') };
            sluitRoundEditChoice();

            return { deelGepland, deelGespeeld, naKlik, bewerkGepland, bewerkGespeeld };
        }""")
        agenda = lambda lijst: next(x for x in lijst if x["f"] == 'ics')
        check("de agenda-optie staat er altijd",
              [agenda(acties["deelGepland"])["f"], agenda(acties["deelGespeeld"])["f"]],
              ['ics', 'ics'])
        check("aan bij een geplande ronde", agenda(acties["deelGepland"])["uit"], False)
        check("uit bij een gespeelde ronde", agenda(acties["deelGespeeld"])["uit"], True)
        check("en dan levert klikken niets op", acties["naKlik"], None)
        # De drie keuzes staan er altijd, in vaste volgorde. De eerste wisselt van naam
        # in plaats van uit te gaan: zonder scores 'Herplannen', met scores 'Corrigeren'
        # (dat neemt je scores mee naar een nieuwe opzet).
        check("de eerste keuze staat altijd aan",
              [acties["bewerkGepland"]["herplan"]["uit"],
               acties["bewerkGespeeld"]["herplan"]["uit"]], [False, False])
        check("vaststellen staat uit bij een geplande ronde",
              acties["bewerkGepland"]["resultaat"]["uit"], True)
        check("en gewoon aan bij een gespeelde ronde",
              acties["bewerkGespeeld"]["resultaat"]["uit"], False)

        # De volgorde ligt vast: herplannen, bewerken, vaststellen.
        volgorde = await page.evaluate("""() => {
            const i = loadSavedRounds().findIndex(r => r.id === 7001);
            openRoundEditChoice(i);
            const uit = [...document.querySelectorAll('#roundEditChoiceModal button')]
                .filter(b => b.id).map(b => b.textContent.trim());
            sluitRoundEditChoice();
            return uit;
        }""")
        check("de volgorde klopt", volgorde, ['Herplannen', 'Bewerken', 'Vaststellen'])
        # Dezelfde ronde met scores toont dezelfde plek, maar dan als 'Corrigeren'.
        metScores = await page.evaluate("""() => {
            const i = loadSavedRounds().findIndex(r => gespeeldeHoles(r) > 0);
            if (i < 0) return 'geen gespeelde ronde';
            openRoundEditChoice(i);
            const uit = [...document.querySelectorAll('#roundEditChoiceModal button')]
                .filter(b => b.id).map(b => b.textContent.trim());
            sluitRoundEditChoice();
            return uit;
        }""")
        check("met scores heet de eerste 'Corrigeren'",
              metScores, ['Corrigeren', 'Bewerken', 'Vaststellen'])

        # De kaart heeft geen apart planmenu meer.
        knoppen = await page.evaluate("""() => {
            zetGroepering('gepland'); tekenRondelijst();
            const kaart = document.querySelector('#screen-archive .saved-item');
            const uit = [...kaart.querySelectorAll('button')].map(b => b.title);
            zetGroepering(null); tekenRondelijst();
            return uit;
        }""")
        check("er is geen apart planmenu meer op de kaart",
              any('Plannen' in (t or '') or 'Meer acties' in (t or '') for t in knoppen), False)

        print("\n=== 7. IMPORT SLAAT ONMOGELIJKE WAARDEN OVER ===\n")
        # Een importbestand is de enige weg waarlangs waarden binnenkomen die de app
        # zelf nooit zou maken. Een verzonnen dagresultaat telt gewoon mee in je
        # handicap, en dat zie je niet aan de kaart. Zulke rondes worden OVERGESLAGEN,
        # niet geweigerd: anders blokkeert één rotte ronde je hele herstel.
        keuring = await page.evaluate("""() => {
            const basis = {
                id: 1, date: '2026-01-01', time: '09:00', player: 'Tester', hcp: 30.7,
                club: 'Testclub', clubShort: 'TC', track: 'Baan', gender: 'Heren',
                tee: 'Wit', CR: 35.0, SR: 120, PAR: 36, chcp: 11, qualifying: true,
                total: 45, totalStb: 18, playedCount: 9, holesCount: 9,
                currentHole: 0, started: true, sd: 30.0, sdFinal: 30.0, pcc: 0,
                holes: Array.from({ length: 9 }, (_, i) => (
                    { id: 'H' + (i + 1), par: 4, si: i + 1, phcp: 1, ppar: 5,
                      score: 5, putts: 2 })),
            };
            const kopie = extra => JSON.parse(JSON.stringify({ ...basis, ...extra }));
            const eenHole = h => kopie({ holes: [{ id: 'H1', par: 4, si: 1, ...h }] });
            return {
                goed:        keurRonde(kopie({})),
                geenDatum:   keurRonde(kopie({ date: '' })),
                geenSpeler:  keurRonde(kopie({ player: '' })),
                geenHoles:   keurRonde(kopie({ holes: [] })),
                sdTeHoog:    keurRonde(kopie({ sdFinal: 999 })),
                hcpTeHoog:   keurRonde(kopie({ hcp: 500 })),
                srOnmogelijk:keurRonde(kopie({ SR: 5 })),
                holesCountFout: keurRonde(kopie({ holesCount: 18 })),
                parOnmogelijk: keurRonde(eenHole({ par: 99, score: 5, holesCount: 1 })),
                scoreOnmogelijk: keurRonde(eenHole({ par: 4, score: 200, holesCount: 1 })),
                // Randgevallen die WEL moeten deugen:
                geenScores:  keurRonde(kopie({ holes: basis.holes.map(h =>
                                 ({ ...h, score: null, putts: null })) })),
                geenSd:      keurRonde(kopie({ sd: null, sdFinal: null })),
                minHandicap: keurRonde(kopie({ hcp: -10 })),
            };
        }""")
        check("een gewone ronde deugt", keuring["goed"], None)
        check("een ronde zonder scores deugt ook", keuring["geenScores"], None)
        check("net als een ronde zonder dagresultaat", keuring["geenSd"], None)
        check("en een handicap van -10", keuring["minHandicap"], None)
        for sleutel in ('geenDatum', 'geenSpeler', 'geenHoles', 'sdTeHoog', 'hcpTeHoog',
                        'srOnmogelijk', 'holesCountFout', 'parOnmogelijk', 'scoreOnmogelijk'):
            check(f"afgekeurd: {sleutel}", keuring[sleutel] is not None, True)

        # En het schiften: de goede rondes komen door, de rest wordt gemeld.
        geschift = await page.evaluate("""() => {
            const goed = { date: '2026-01-01', player: 'Tester',
                           holes: [{ id: 'H1', par: 4, si: 1, phcp: 1, score: 5 }], holesCount: 1 };   // sinds 131 is de slagverdeling verplicht
            const fout = { ...goed, sdFinal: 999 };
            const uit = schiftRondes([goed, fout, goed]);
            return { goed: uit.goed.length, over: uit.over.length,
                     tekst: overgeslagenTekst(uit.over, 3) };
        }""")
        check("de goede rondes komen door", geschift["goed"], 2)
        check("de rest valt af", geschift["over"], 1)
        # 'Niet ingelezen' is voorbehouden aan rondes die niet deugen; een ronde die je
        # al had krijgt een eigen zin.
        check("met een melding erbij", 'niet ingelezen' in geschift["tekst"], True)

        print("\n=== 8. RONDE-ID\'S BLIJVEN UNIEK ===\n")
        # De app zoekt rondes op met "vind de eerste met dit id". Twee rondes met
        # hetzelfde id maakt de tweede onbereikbaar: bewerken of verwijderen raakt dan
        # altijd dezelfde. Er zijn maar twee plekken die een id uitdelen — het starten
        # van een ronde en het importeren — en beide tellen op zolang het id al bestaat.
        # Die verdediging wordt hier bewaakt.
        uniek = await page.evaluate("""() => {
            // Een ronde met een id dat straks als startpunt wordt gekozen.
            const nu = Date.now();
            const bezet = { date: '2020-01-01', time: '08:00', player: 'Tester',
                            id: nu, holes: [{ id: 'H1', par: 4, si: 1, score: 5 }],
                            holesCount: 1, playedCount: 1, started: true };
            metVerwijderen(() => setRoundsAndMark(JSON.stringify([bezet])));

            // Importeren moet een vers id kiezen, ook als het id in het bestand botst.
            const bestaande = new Set(loadSavedRounds().map(r => r.id));
            const entry = buildImportEntry(
                { ...bezet, date: '2021-02-02' }, bestaande, true);
            const naImport = entry.id;

            return { bezetId: nu, importId: naImport, verschillend: naImport !== nu };
        }""")
        check("de import kiest een vrij id", uniek["verschillend"], True)

        # Twee spelers die tegelijk starten krijgen elk een eigen id.
        # Speler 2 zichtbaar maken vraagt een tekenronde; daarna pas invullen.
        await page.evaluate("""() => {
            metVerwijderen(() => setRoundsAndMark('[]'));
            nav('setup');
            sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.qualifying = true;
            document.getElementById('iName').value = 'Testspeler';
            document.getElementById('iHcp').value = '30.7';
            // togglePlayer2 WISSELT; een eerdere stap kan speler 2 al aan hebben gezet.
            if (!player2Visible) togglePlayer2();
        }""")
        await page.wait_for_timeout(300)
        tweeSpelers = await page.evaluate("""() => {
            document.getElementById('iName2').value = 'Partner';
            document.getElementById('iHcp2').value = '18';
            sel2.track = 'Airborne'; sel2.tee = 'Blauw'; sel2.qualifying = true;
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            const ids = loadSavedRounds().map(r => r.id);
            return { aantal: ids.length, uniek: new Set(ids).size === ids.length,
            };
        }""")
        check("twee spelers geven twee rondes", tweeSpelers["aantal"], 2)
        check("met verschillende id's", tweeSpelers["uniek"], True)

        print("\n=== 9. DE VENSTERS BIJ HET IMPORTEREN ===\n")
        # De keuze en de meldingen moeten in één taal spreken. Eerder heette dezelfde
        # handeling achtereenvolgens 'volledig herstellen', 'vervangen' en 'hersteld',
        # stonden de knoppen in omgekeerde volgorde van de tekst, ontbrak Annuleren, en
        # betekende 'overgeslagen' zowel 'die had je al' als 'die deugde niet'.
        vensters = await page.evaluate("""() => {
            const lees = () => {
                for (const [id, t, m] of [['keuzeModal', 'keuzeModalTitel', 'keuzeModalTekst'],
                                          ['confirmModal', 'confirmModalTitle', 'confirmModalMessage'],
                                          ['resetAllModal', 'dangerModalTitle', 'dangerModalMessage']]) {
                    const el = document.getElementById(id);
                    if (el && !el.classList.contains('hidden')) {
                        return { venster: id,
                                 titel: document.getElementById(t).textContent,
                                 tekst: document.getElementById(m).textContent,
                                 knoppen: [...el.querySelectorAll('button')]
                                     .filter(b => b.offsetParent).map(b => b.textContent.trim()) };
                    }
                }
                return null;
            };
            const sluit = () => ['keuzeModal', 'confirmModal', 'resetAllModal']
                .forEach(id => document.getElementById(id)?.classList.add('hidden'));

            const basis = ronde => ({
                date: ronde, time: '09:00', player: 'Tester', hcp: 30.7,
                club: 'Testclub', clubShort: 'TC', track: 'Baan', gender: 'Heren',
                tee: 'Wit', CR: 35.0, SR: 120, PAR: 36, chcp: 11, qualifying: true,
                total: 45, totalStb: 18, playedCount: 1, holesCount: 1, currentHole: 0,
                started: true, sd: 30.0, sdFinal: 30.0, pcc: 0,
                holes: [{ id: 'H1', par: 4, si: 1, phcp: 1, ppar: 5, score: 5 }],
            });

            // Twee bestaande rondes, een bestand met drie waarvan één al bestaat.
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(
                [{ ...basis('2025-01-01'), id: 6001 }, { ...basis('2025-02-01'), id: 6002 }])));
            const bestand = [basis('2025-01-01'), basis('2025-03-01'), basis('2025-04-01')];

            sluit();
            // De keuze nabootsen zoals importRound die opzet.
            const n = bestand.length, bestaand = loadSavedRounds().length;
            const meervoud = a => `${a} ronde${a !== 1 ? 's' : ''}`;
            toonKeuzeModal('Rondes importeren', null,
                `Dit bestand bevat ${meervoud(n)}. Je hebt er nu ${bestaand}.`,
                [{ tekst: 'Toevoegen', hoofd: true, actie: () => doAdditiveImport(bestand) },
                 { tekst: 'Vervangen…', actie: () => {} },
                 { tekst: 'Annuleren', actie: () => {} }]);
            const keuze = lees();

            // Toevoegen kiezen en de afsluiting lezen.
            document.getElementById('keuzeModalKnop1').click();
            const slot = lees();
            sluit();
            return { keuze, slot };
        }""")
        check("het keuzevenster heet naar wat het doet",
              vensters["keuze"]["titel"], 'Rondes importeren')
        check("de knoppen lopen van veilig naar zwaar",
              vensters["keuze"]["knoppen"], ['Toevoegen', 'Vervangen…', 'Annuleren'])
        check("de tekst noemt beide aantallen",
              'bevat 3 rondes' in vensters["keuze"]["tekst"]
              and 'nu 2' in vensters["keuze"]["tekst"], True)
        check("de afsluiting meldt wat er binnenkwam",
              vensters["slot"]["tekst"].startswith('2 rondes geïmporteerd'), True)
        check("en wat je al had, in eigen woorden",
              'had je al' in vensters["slot"]["tekst"], True)
        check("zonder het woord 'overgeslagen' voor twee dingen",
              'overgeslagen' in vensters["slot"]["tekst"], False)

        print("\n=== 10. EEN BESTAND UIT EEN ANDERE OPSLAGLOCATIE ===\n")
        # De herkomst komt uit de BESTANDSNAAM; in het bestand zelf staat niets. Ze is
        # dus een extra aanwijzing, nooit de enige drempel: bij vervangen staat de
        # kernwaarschuwing er altijd, ook bij een hernoemd bestand.
        herkomst = await page.evaluate("""() => {
            const eigen = opslagCode();
            const anders = eigen === 'BBBB' ? 'CCCC' : 'BBBB';
            return {
                // De code staat tussen haakjes, met eventueel de naam van de installatie
                // ervoor: rondes_backup_20260829_EdgeTest(BBBB).json
                andereOpslag: andereOpslagCode(`rondes_backup_20260829_(${anders}).json`),
                metNaam: andereOpslagCode(`rondes_backup_20260829_EdgeTest(${anders}).json`),
                eigenOpslag: andereOpslagCode(`rondes_backup_20260829_(${eigen}).json`),
                kleineLetters: andereOpslagCode(`rondes_backup_20260829_(${anders.toLowerCase()}).json`),
                metKopieNummer: andereOpslagCode(`rondes_backup_20260829_(${anders}) (1).json`),
                clubsBestand: andereOpslagCode(`clubs_backup_20260829_(${anders}).json`),
                hernoemd: andereOpslagCode('kopie.json'),
                willekeurig: andereOpslagCode('mijn_data.json'),
                verwacht: anders,
            };
        }""")
        anders = herkomst["verwacht"]
        check("een andere opslag wordt herkend", herkomst["andereOpslag"], anders)
        check("ook met de naam van die installatie ervoor", herkomst["metNaam"], anders)
        check("de eigen opslag geeft niets", herkomst["eigenOpslag"], None)
        check("kleine letters tellen ook", herkomst["kleineLetters"], anders)
        check("en een (1) van de browser stoort niet", herkomst["metKopieNummer"], anders)
        check("clubsbestanden net zo goed", herkomst["clubsBestand"], anders)
        # Een hernoemd bestand verraadt niets meer: dat is een grens van wat te weten
        # valt, geen fout. De waarschuwing bij vervangen vangt dat op.
        check("een hernoemd bestand geeft niets", herkomst["hernoemd"], None)
        check("een willekeurig bestand ook niet", herkomst["willekeurig"], None)

        print("\n=== DE UITKLAPJES LATEN ZIEN WAAR ZE OPHOUDEN ===\n")
        # Een lijn links met inspringing maakt zichtbaar wat bij het kopje hoort. Zonder
        # die lijn liep de lijst gewoon door en was niet te zien wat er onder 'Meer' viel
        # en wat eronder stond.
        randen = await page.evaluate("""() => {
            nav('archive');
            tekenRondelijst();
            openExportModal(0);
            toggleExportMeer(true);
            const blok = document.getElementById('exportMeerBlok');
            const st = getComputedStyle(blok);
            const uit = {
                export: { kleur: st.borderLeftColor, breedte: st.borderLeftWidth,
                          inspring: st.paddingLeft },
            };
            closeExportModal();
            // En hetzelfde patroon in Instellingen, waar de opmaakklasse wordt gebruikt.
            nav('settings');
            switchSettingsTab('data');
            const sec = [...document.querySelectorAll('[data-section-key]')]
                .find(e => /exporteren/i.test(e.textContent));
            if (sec) sec.click();
            // Álle uitklapjes op dit tabblad: die horen dezelfde kleur te hebben.
            uit.instellingen = [];
            document.querySelectorAll('#settingsTabData .more-toggle').forEach(kop => {
                if (!kop.classList.contains('open')) toggleMoreInfo(kop);
                const s2 = getComputedStyle(kop.nextElementSibling);
                uit.instellingen.push({ kop: kop.textContent.trim().slice(0, 14),
                                        kleur: s2.borderLeftColor,
                                        breedte: s2.borderLeftWidth });
            });
            return uit;
        }""")
        GROEN = 'rgb(46, 125, 84)'
        check("het exportvenster heeft een lijn links",
              randen["export"]["breedte"], '2px')
        check("en die is groen, net als het kopje erboven",
              randen["export"]["kleur"], GROEN)
        check("met inspringing", randen["export"]["inspring"], '10px')
        # In Instellingen zijn de lijnen GOUD: 'Toon opties' hoort daar bij 'Meer uitleg'.
        # Groen is voorbehouden aan het Exporteer/deel-venster, waar het kopje groen is.
        GOUD = 'rgb(154, 125, 46)'
        check("in Instellingen zijn er uitklapjes",
              len(randen["instellingen"]) >= 2, True)
        check("ze hebben allemaal een gouden lijn",
              sorted({r["kleur"] for r in randen["instellingen"]}), [GOUD])
        check("en allemaal dezelfde breedte",
              sorted({r["breedte"] for r in randen["instellingen"]}), ['2px'])

        if paginafouten:
            fouten.append('paginafouten')
            print("\nFOUTEN IN DE PAGINA:")
            for f in paginafouten[:5]:
                print("   " + f[:150])

        await browser.close()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
