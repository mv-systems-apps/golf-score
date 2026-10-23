"""Zestig bewerkingen door elkaar in de baaneditor, met vaste uitkomst.

Wisselen van tee, holes toevoegen en verwijderen, pars aanpassen, tees toevoegen en
verwijderen, gelijktrekken — in een vaste volgorde, zodat een fout altijd op dezelfde
stap valt en te herhalen is. Na élke stap worden dezelfde afspraken gecontroleerd:

  * elke tee heeft een even lange hole-lijst
  * die lengte is gelijk aan het aantal rijen in de tabel
  * de holenamen zijn uniek
  * de PAR-kolom van elke tee is de som van zijn eigen holes
  * de tee die in de tabel staat, staat ook in de kiezer

Losse tests dekken één handeling; hier gaat het om wat er misgaat als handelingen
elkaar afwisselen — precies waar de hole-lijsten uit de pas kunnen raken.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url

CLUBS = {
    "Stressclub": {
        "club": "Stressclub", "shortName": "SC",
        "courses": {
            "Baan": {
                "holeIds": ["H%d" % (i + 1) for i in range(9)],
                "tees": {
                    "Heren": {
                        "Wit":  {"CR": 35.0, "SR": 120,
                                 "holes": [{"par": p, "si": i + 1} for i, p in
                                           enumerate([4, 4, 5, 4, 3, 5, 4, 3, 4])]},
                        "Geel": {"CR": 34.0, "SR": 116,
                                 "holes": [{"par": p, "si": i + 1} for i, p in
                                           enumerate([4, 4, 5, 4, 3, 5, 4, 3, 4])]},
                    },
                    "Dames": {
                        "Rood": {"CR": 36.0, "SR": 124,
                                 "holes": [{"par": p, "si": i + 1} for i, p in
                                           enumerate([4, 4, 4, 4, 3, 5, 4, 3, 4])]},
                    },
                },
            }
        },
    }
}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        page.on('console', lambda m: paginafouten.append('console: ' + m.text)
                if m.type == 'error' else None)
        await page.goto(app_url())
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Stressclub');
            localStorage.setItem('golf_profile_name', 'Tester');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(400)

        uit = await page.evaluate("""() => {
            const fouten = [];
            const stappen = [];

            const knop = () => {
                const h = document.createElement('div');
                document.body.appendChild(h);
                const b = document.createElement('button');
                b.dataset.confirm = '1';
                h.appendChild(b);
                return b;
            };

            // Na elke stap: kloppen de afspraken nog?
            const controleer = (stap) => {
                const rijen = teeRows();
                const lengtes = new Set(rijen.map(r => (r._holes || []).length));
                const tabelRijen = document.querySelectorAll('.hole-editor-row').length;
                if (lengtes.size > 1) {
                    fouten.push(stap + ': tee-lijsten ongelijk (' + [...lengtes].join(',') + ')');
                }
                if (rijen.length && [...lengtes][0] !== tabelRijen) {
                    fouten.push(stap + ': tabel ' + tabelRijen + ' rijen, lijst ' + [...lengtes][0]);
                }
                const ids = readHolesFromEditor().map(h => h.id);
                if (new Set(ids).size !== ids.length) fouten.push(stap + ': dubbele holenaam');
                // PAR-kolom moet de som van de eigen holes zijn
                rijen.forEach((r, i) => {
                    const getoond = r.querySelector('.par-name-field')?.dataset.value;
                    const som = (r._holes || []).reduce((s, h) => s + (h.par || 0), 0);
                    if (String(som) !== String(getoond)) {
                        fouten.push(stap + ': tee ' + i + ' toont par ' + getoond + ', som is ' + som);
                    }
                });
                // De getoonde tee moet bestaan en in de kiezer staan
                if (rijen.length && !rijen.includes(editorHoleTeeRow)) {
                    fouten.push(stap + ': getoonde tee hoort niet meer bij de baan');
                }
                stappen.push(stap + ' → ' + rijen.length + ' tees, ' + tabelRijen + ' holes');
            };

            editorClub = 'Stressclub';
            document.getElementById('editorClubName').value = 'Stressclub';
            document.getElementById('editorShortName').value = 'SC';
            openCourseEditor('Baan');
            controleer('start');

            // Vaste reeks van 60 handelingen: het patroon herhaalt zich, maar de
            // volgorde is elke keer dezelfde — dus een fout is altijd te herhalen.
            let toegevoegd = 0;
            for (let i = 0; i < 60; i++) {
                const rijen = teeRows();
                switch (i % 6) {
                    case 0:
                        if (rijen.length) kiesHoleTee(i % rijen.length);
                        break;
                    case 1:
                        addOneHoleRow(); toegevoegd++;
                        break;
                    case 2:
                        if (toegevoegd > 0) { removeHoleRow(knop()); toegevoegd--; }
                        break;
                    case 3: {
                        const rij = document.querySelectorAll('.hole-editor-row')[i % 9];
                        if (rij) {
                            rij.querySelector('.par-cycle-btn').dataset.par = String(3 + (i % 4));
                            updateAllTeeParDisplays();
                        }
                        break;
                    }
                    case 4: {
                        const b = document.getElementById('teeGelijkAllesBtn')
                               || document.getElementById('teeHerstelBtn')
                               || document.getElementById('teeGelijkGeslachtBtn');
                        if (b) { b.dataset.confirm = '1'; b.click(); }
                        break;
                    }
                    case 5:
                        // Om en om een tee erbij en eraf, zodat het aantal niet oploopt
                        if (rijen.length > 3) removeLastTeeRow(knop());
                        else addTeeRow();
                        break;
                }
                controleer('stap ' + i);
            }

            // Tot slot moet wat er staat ook op te slaan zijn (of met een duidelijke
            // reden geweigerd worden — niet stilzwijgend half doorgevoerd).
            let opslaan;
            try {
                const v = validateCourseInput();
                opslaan = 'geldig: ' + v.holeIds.length + ' holes, ' +
                    Object.values(v.tees).reduce((s, m) => s + Object.keys(m).length, 0) + ' tees';
            } catch (e) {
                opslaan = 'geweigerd: ' + e.message;
            }

            return { fouten, aantalStappen: stappen.length, laatste: stappen.slice(-3), opslaan };
        }""")

        print("=== BAANEDITOR ONDER DRUK ===\n")
        print(f"  stappen gecontroleerd: {uit['aantalStappen']}")
        for regel in uit["laatste"]:
            print("  " + regel)
        print(f"  opslaan aan het eind: {uit['opslaan']}")

        alles_goed = True
        if uit["fouten"]:
            alles_goed = False
            print(f"\n {len(uit['fouten'])} SCHENDING(EN) VAN DE AFSPRAKEN:")
            for f in uit["fouten"][:10]:
                print("   " + f)
        else:
            print("\n  ok   alle afspraken bleven gelden bij elke stap")

        # Aan het eind moet er iets zinnigs staan: geldig, of geweigerd met uitleg.
        if not (uit["opslaan"].startswith("geldig") or uit["opslaan"].startswith("geweigerd")):
            alles_goed = False
            print(" FOUT  opslaan gaf geen duidelijke uitkomst")

        if paginafouten:
            alles_goed = False
            print("\nFOUTEN IN DE PAGINA:")
            for f in paginafouten[:5]:
                print("   " + f[:150])

        await browser.close()

    print()
    print("GEEN FOUTEN" if alles_goed else "FOUTEN GEVONDEN")
    sys.exit(0 if alles_goed else 1)


asyncio.run(main())
