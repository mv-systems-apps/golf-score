"""De hele levensloop van een baan, in één doorlopende sessie.

Club aanmaken → baan met twee tees die echt van elkaar verschillen → rondes spelen
vanaf beide tees → afronden → statistieken → backup van clubs én rondes → alles wissen
→ terugzetten → controleren dat er niets is veranderd.

Dit is de test die het meest lijkt op wat er bij een echte gebruiker gebeurt, en de
enige die de clubs-kant van het herstelpad afdekt: een backup die je niet kunt
terugzetten merk je pas op het moment dat je hem nodig hebt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url

# Twee tees die op drie punten verschillen: hole 3 is vanaf rood een par 4 in plaats
# van 5, en de slagindexen lopen anders. Precies waarvoor het model is gemaakt.
HOLES_WIT  = [{"par": p, "si": s} for p, s in
              zip([4, 4, 5, 4, 3, 5, 4, 3, 4], [13, 5, 7, 11, 15, 1, 3, 17, 9])]
HOLES_ROOD = [{"par": p, "si": s} for p, s in
              zip([4, 4, 4, 4, 3, 5, 4, 3, 4], [2, 4, 6, 8, 10, 1, 3, 5, 7])]

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        toon = repr(gekregen)
        print(f"  ok   {naam}: {toon[:90]}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        page.on('console', lambda m: paginafouten.append('console: ' + m.text)
                if m.type == 'error' else None)
        await page.goto(app_url())
        await page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('golf_profile_name', 'Tester');
            localStorage.setItem('golf_profile_hcp', '24.0');
        }""")
        await page.reload()
        await page.wait_for_timeout(400)

        print("=== 1. CLUB EN BAAN AANMAKEN ===\n")
        aanmaken = await page.evaluate("""([wit, rood]) => {
            // Club aanmaken zoals de editor dat doet
            CLUBS['Proefclub'] = { club: 'Proefclub', shortName: 'PC', courses: {} };
            editorClub = 'Proefclub';
            document.getElementById('editorClubName').value = 'Proefclub';
            document.getElementById('editorShortName').value = 'PC';

            // Baan opbouwen via de editor: negen holes, twee tees
            openCourseEditor('__new__');
            document.getElementById('editorCourseName').value = 'Proefbaan';
            addTeeRow();
            for (let i = 0; i < 9; i++) addOneHoleRow();
            addTeeRow();

            // Eerste tee: Heren/Wit
            const rijen = teeRows();
            rijen[0].querySelector('.gender-cycle-btn').dataset.gender = 'Heren';
            const n0 = rijen[0].querySelector('.tee-name-field');
            n0.dataset.value = 'Wit'; n0.textContent = 'Wit';
            rijen[0].querySelector('.cr-name-field').dataset.value = '35.0';
            rijen[0].querySelector('.sr-name-field').dataset.value = '120';
            rijen[0]._holes = wit.map(h => ({ ...h }));

            // Tweede tee: Dames/Rood, met andere par en SI
            rijen[1].querySelector('.gender-cycle-btn').dataset.gender = 'Dames';
            const n1 = rijen[1].querySelector('.tee-name-field');
            n1.dataset.value = 'Rood'; n1.textContent = 'Rood';
            rijen[1].querySelector('.cr-name-field').dataset.value = '36.0';
            rijen[1].querySelector('.sr-name-field').dataset.value = '124';
            rijen[1]._holes = rood.map(h => ({ ...h }));

            // Holenamen zetten via de tabel (die zijn van de baan)
            document.querySelectorAll('.hole-id').forEach((el, i) => { el.value = 'P' + (i + 1); });
            editorHoleTeeRow = rijen[0];
            renderHoleEditor(holesVoorTabel());

            saveCourseFromEditor();
            const co = CLUBS['Proefclub'].courses['Proefbaan'];
            return {
                status: document.getElementById('editorStatus').textContent,
                holeIds: co ? co.holeIds : null,
                wit: co ? co.tees.Heren.Wit.holes : null,
                rood: co ? co.tees.Dames.Rood.holes : null,
                velden: co ? Object.keys(co).sort() : null,
            };
        }""", [HOLES_WIT, HOLES_ROOD])

        check("baan opgeslagen", aanmaken["status"], "Opgeslagen")
        check("holenamen van de baan", aanmaken["holeIds"],
              ['P%d' % (i + 1) for i in range(9)])
        check("baan bewaart alleen namen en tees", aanmaken["velden"], ["holeIds", "tees"])
        check("herentee met eigen par en SI", aanmaken["wit"], HOLES_WIT)
        check("damestee met eigen par en SI", aanmaken["rood"], HOLES_ROOD)

        print("\n=== 2. RONDES SPELEN VANAF BEIDE TEES ===\n")
        spelen = await page.evaluate("""() => {
            // Eerst de club kiezen, zoals op het startscherm: de banenlijst bevat alleen de
            // banen van de gekozen club (baannamen zijn niet uniek over clubs heen).
            setDefaultClub('Proefclub');
            const speel = (gender, tee, datum) => {
                sel.track = 'Proefbaan'; sel.gender = gender; sel.tee = tee;
                sel.chcpOverride = null; sel.qualifying = true;
                sel.date = datum; sel.time = '09:30'; sel.dateTimeEdited = true;
                document.getElementById('iName').value = 'Tester';
                document.getElementById('iHcp').value = '24.0';
                startRoundConfirmed();
                // scores invullen: telkens één boven par
                const rondes = loadSavedRounds();
                const r = rondes.find(x => x.date === datum);
                r.holes.forEach(h => { h.score = h.par + 1; h.putts = 2; });
                r.total = r.holes.reduce((s, h) => s + h.score, 0);
                r.playedCount = r.holes.length;
                setRoundsAndMark(JSON.stringify(rondes));
                // De scores zijn hierboven buiten de app om in de opslag gezet. Het geheugen
                // gelijk trekken: sinds 130 bewaart een nieuwe start eerst de lopende ronde
                // uit het geheugen (de app is daar de bron), en die had nog lege holes.
                game.holes = r.holes.map(h => ({ ...h }));
                return r;
            };
            const a = speel('Heren', 'Wit', '2026-08-01');
            const b = speel('Dames', 'Rood', '2026-08-08');
            // Sinds 10E telt een ronde pas mee als hij niet meer open staat: de laatste afsluiten.
            clearActiveRound();
            return {
                witPar: a.PAR, roodPar: b.PAR,
                witHole3: [a.holes[2].par, a.holes[2].si],
                roodHole3: [b.holes[2].par, b.holes[2].si],
                zelfdeNamen: JSON.stringify(a.holes.map(h => h.id)) ===
                             JSON.stringify(b.holes.map(h => h.id)),
                chcpVerschilt: a.chcp !== b.chcp,
                aantal: loadSavedRounds().length,
            };
        }""")

        check("par-totaal vanaf wit", spelen["witPar"], sum(h["par"] for h in HOLES_WIT))
        check("par-totaal vanaf rood", spelen["roodPar"], sum(h["par"] for h in HOLES_ROOD))
        check("hole 3 vanaf wit", spelen["witHole3"], [HOLES_WIT[2]["par"], HOLES_WIT[2]["si"]])
        check("hole 3 vanaf rood", spelen["roodHole3"], [HOLES_ROOD[2]["par"], HOLES_ROOD[2]["si"]])
        check("holenamen blijven gelijk", spelen["zelfdeNamen"], True)
        check("spelend handicap verschilt per tee", spelen["chcpVerschilt"], True)
        check("twee rondes bewaard", spelen["aantal"], 2)

        print("\n=== 3. SCHERMEN OPBOUWEN ===\n")
        schermen = await page.evaluate("""() => {
            const uit = {};
            const pr = (naam, fn) => { try { fn(); uit[naam] = 'ok'; }
                                       catch (e) { uit[naam] = 'FOUT: ' + e.message; } };
            pr('statistieken', () => renderPlayerStats());
            pr('spelanalyse', () => buildGameAnalysis());
            pr('clublijst', () => buildClubList());
            pr('startscherm', () => { buildTrackList(); buildTeeButtons(); });
            const d = courseAnalysisData('Proefclub', 'Proefbaan');
            uit.baananalyse = d ? d.holes.length : 0;
            // Hole 3 speelde je met twee verschillende pars: die hoort gemarkeerd
            uit.gemarkeerd = d ? d.holes.map(h => !!h.parWisselt) : null;
            return uit;
        }""")

        for naam in ["statistieken", "spelanalyse", "clublijst", "startscherm"]:
            check(naam + " bouwt op", schermen[naam], "ok")
        check("baananalyse kent alle holes", schermen["baananalyse"], 9)
        check("alleen hole 3 gemarkeerd", schermen["gemarkeerd"],
              [False, False, True, False, False, False, False, False, False])

        print("\n=== 4. BACKUP MAKEN ===\n")
        backup = await page.evaluate("""async () => {
            const uit = {};
            const origineel = URL.createObjectURL;
            let blob = null;
            URL.createObjectURL = (b) => { blob = b; return origineel.call(URL, b); };
            let viaHref = null;
            const maakEl = document.createElement.bind(document);
            document.createElement = (t) => {
                const el = maakEl(t);
                if (t === 'a') {
                    const d = Object.getOwnPropertyDescriptor(HTMLAnchorElement.prototype, 'href');
                    Object.defineProperty(el, 'href', {
                        set(v) { viaHref = v; d.set.call(el, v); },
                        get() { return d.get.call(el); } });
                }
                return el;
            };
            await exportAllClubs();
            document.createElement = maakEl;
            URL.createObjectURL = origineel;
            if (blob) uit.clubs = await blob.text();
            else if (viaHref && viaHref.startsWith('data:')) {
                uit.clubs = decodeURIComponent(viaHref.split(',')[1]);
            }
            uit.rondes = localStorage.getItem('golf_rounds');
            return uit;
        }""")

        clubs_backup = json.loads(backup["clubs"])
        rondes_backup = json.loads(backup["rondes"])
        check("backup bevat de club", any(c["club"] == "Proefclub" for c in clubs_backup), True)
        check("backup bevat beide rondes", len(rondes_backup), 2)

        print("\n=== 5. ALLES WISSEN EN TERUGZETTEN ===\n")
        herstel = await page.evaluate("""([clubs, rondes, voorClubs]) => {
            const uit = {};
            // Alles weg — alsof je op een nieuw toestel begint
            localStorage.clear();
            Object.keys(CLUBS).forEach(k => delete CLUBS[k]);
            rebuildCourseLookup(); saveClubsToStorage();
            uit.naWissen = Object.keys(CLUBS).length;

            // Terugzetten via dezelfde controle die de importknop gebruikt
            uit.afgekeurd = clubs.map(c => validateImportedClubData(c)).filter(Boolean);
            clubs.forEach(c => { CLUBS[c.club] = c; });
            saveClubsToStorage();
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            rebuildCourseLookup(); saveClubsToStorage();
            rebuildAll();

            const co = CLUBS['Proefclub'].courses['Proefbaan'];
            uit.gelijk = JSON.stringify(CLUBS['Proefclub']) === JSON.stringify(voorClubs);
            uit.holeIds = co.holeIds;
            uit.wit = co.tees.Heren.Wit.holes;
            uit.rood = co.tees.Dames.Rood.holes;
            uit.rondes = loadSavedRounds().length;

            // En een nieuwe ronde na herstel geeft nog steeds dezelfde waarden
            setDefaultClub('Proefclub');
            sel.track = 'Proefbaan'; sel.gender = 'Dames'; sel.tee = 'Rood';
            sel.chcpOverride = null; sel.date = '2026-08-20'; sel.dateTimeEdited = true;
            document.getElementById('iName').value = 'Tester';
            document.getElementById('iHcp').value = '24.0';
            startRoundConfirmed();
            const nieuw = loadSavedRounds().find(r => r.date === '2026-08-20');
            uit.nieuweRonde = nieuw ? [nieuw.PAR, nieuw.holes[2].par, nieuw.holes[2].si] : null;
            return uit;
        }""", [clubs_backup, rondes_backup,
               await page.evaluate("() => CLUBS['Proefclub']")])

        check("na wissen geen clubs meer", herstel["naWissen"], 0)
        check("backup komt door de controle", herstel["afgekeurd"], [])
        check("club bit-voor-bit hersteld", herstel["gelijk"], True)
        check("holenamen hersteld", herstel["holeIds"], ['P%d' % (i + 1) for i in range(9)])
        check("herentee hersteld", herstel["wit"], HOLES_WIT)
        check("damestee hersteld", herstel["rood"], HOLES_ROOD)
        check("rondes hersteld", herstel["rondes"], 2)
        check("nieuwe ronde na herstel klopt", herstel["nieuweRonde"],
              [sum(h["par"] for h in HOLES_ROOD), HOLES_ROOD[2]["par"], HOLES_ROOD[2]["si"]])

        print("\n=== 6. SCHERMEN NA HERSTEL ===\n")
        na = await page.evaluate("""() => {
            const uit = {};
            const pr = (naam, fn) => { try { fn(); uit[naam] = 'ok'; }
                                       catch (e) { uit[naam] = 'FOUT: ' + e.message; } };
            pr('statistieken', () => renderPlayerStats());
            pr('spelanalyse', () => buildGameAnalysis());
            pr('clublijst', () => buildClubList());
            return uit;
        }""")
        for naam, waarde in na.items():
            check(naam + " na herstel", waarde, "ok")

        if paginafouten:
            fouten.append('paginafouten')
            print("\nFOUTEN IN DE PAGINA:")
            for f in paginafouten[:5]:
                print('  ' + f[:150])

        await browser.close()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
