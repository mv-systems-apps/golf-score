"""De backupherinnering voor clubs.

De bestaande herinnering keek uitsluitend naar rondes: een nieuwe club of een gewijzigde
baan leverde geen enkel signaal op, terwijl dat werk net zo goed verloren kan gaan.

Clubs krijgen daarom een eigen melding, met een andere regel dan die voor rondes: geen
dagen- of aantallendrempel, maar puur "is er sinds de laatste clubbackup iets gewijzigd".
Clubs verander je een paar keer per jaar; een tijdsdrempel zou maandenlang zeuren over
iets wat niet verandert, en een melding die zelden afgaat betekent juist iets als hij
wél afgaat.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url

CLUBS = {
    "Testclub": {
        "club": "Testclub", "shortName": "TC",
        "courses": {
            "Baan": {
                "holeIds": ["H%d" % (i + 1) for i in range(9)],
                "tees": {"Heren": {"Wit": {"CR": 35.0, "SR": 120,
                          "holes": [{"par": 4, "si": i + 1} for i in range(9)]}}},
            }
        },
    }
}


def ronde(rid, datum):
    return {
        "id": rid, "date": datum, "time": "09:00", "player": "Tester", "hcp": 30.7,
        "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren",
        "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
        "note": "", "total": 45, "totalStb": 18, "playedCount": 9, "holesCount": 9,
        "currentHole": 0, "started": True, "sd": 30.0, "sdFinal": 30.0, "pcc": 0,
        "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Testclub');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, [ronde(1, '2026-08-01'), ronde(2, '2026-08-05')]])
        await page.reload()
        await page.wait_for_timeout(700)

        async def stand():
            return await page.evaluate("""() => {
                nav('settings'); switchSettingsTab('data');
                updateLastBackupDisplay();
                const t = document.getElementById('clubBackupInfoTop');
                return {
                    achterstallig: isClubsBackupOverdue(),
                    regel: t && !t.classList.contains('hidden') ? t.textContent.trim() : null,
                    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
                };
            }""")

        async def clubsExporteren():
            await page.evaluate("() => exportAllClubs()")
            await page.wait_for_timeout(500)

        async def rondesVeiligstellen():
            await page.evaluate("""() => {
                const nu = new Date().toISOString();
                localStorage.setItem('golf_last_backup_date', nu.slice(0, 10));
                localStorage.setItem('golf_last_backup_ts', nu);
                localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
                legBackupInhoudVast();
                localStorage.setItem('golf_rounds_changed', nu);
            }""")

        print("=== NOG NOOIT EEN CLUBBACKUP ===\n")
        eerste = await stand()
        check("clubs zijn achterstallig", eerste["achterstallig"], True)
        check("met een duidelijke regel", eerste["regel"], "Backup clubs: nog nooit")

        print("\n=== NA EEN CLUBBACKUP ===\n")
        await clubsExporteren()
        await rondesVeiligstellen()
        na = await stand()
        check("clubs zijn niet meer achterstallig", na["achterstallig"], False)
        check("de regel verdwijnt", na["regel"], None)
        check("en de stip gaat uit", na["stip"], False)

        print("\n=== NA HET WIJZIGEN VAN EEN CLUB ===\n")
        await page.evaluate("""() => {
            CLUBS['Testclub'].shortName = 'Anders';
            saveClubsToStorage();
        }""")
        gewijzigd = await stand()
        check("clubs zijn weer achterstallig", gewijzigd["achterstallig"], True)
        # Eén zin, zonder tijdstip — zelfde vorm als de regel voor de rondes. Staat die
        # regel er ook, dan volstaat 'Clubs ook gewijzigd'; anders de volledige zin.
        check("de regel meldt de wijziging",
              gewijzigd["regel"] in ('Clubs: wijzigingen sinds laatste backup',
                                     'Clubs ook gewijzigd'), True)
        check("en de stip gaat aan", gewijzigd["stip"], True)

        print("\n=== EEN NIEUWE CLUB ===\n")
        await clubsExporteren()
        await page.evaluate("""() => {
            CLUBS['Tweede club'] = { club: 'Tweede club', shortName: '2C', courses: {} };
            saveClubsToStorage();
        }""")
        nieuw = await stand()
        check("een nieuwe club telt ook", nieuw["achterstallig"], True)

        print("\n=== RONDES EN CLUBS STAAN LOS VAN ELKAAR ===\n")
        await clubsExporteren()
        await rondesVeiligstellen()
        voor = await stand()
        check("alles veilig: geen melding", voor["achterstallig"], False)

        # Een nieuwe ronde mag de CLUB-melding niet aanzetten.
        await page.evaluate("""(nieuw) => {
            const lijst = loadSavedRounds();
            lijst.push(nieuw);
            setRoundsAndMark(JSON.stringify(lijst));
        }""", ronde(99, '2026-08-28'))
        naRonde = await stand()
        check("een nieuwe ronde raakt de clubmelding niet", naRonde["achterstallig"], False)

        # En andersom: een clubwijziging mag de RONDE-stand niet aanpassen.
        vooraf = await page.evaluate("() => JSON.stringify(backupVerschil())")
        await page.evaluate("""() => {
            CLUBS['Testclub'].shortName = 'Nogmaals';
            saveClubsToStorage();
        }""")
        achteraf = await page.evaluate("() => JSON.stringify(backupVerschil())")
        check("een clubwijziging raakt de rondestand niet", achteraf, vooraf)

        print("\n=== DE CONTROLE MAG NIET TRAAG ZIJN ===\n")
        # isClubsBackupOverdue draait bij ELKE verversing van de tabstippen. Werd de
        # vingerafdruk daar telkens opnieuw berekend, dan werd de hele clublijst steeds
        # doorlopen: gemeten 7 ms per keer bij 55 clubs. De waarde komt daarom uit de
        # opslag en wordt alleen bij het opslaan van clubs bijgewerkt.
        snelheid = await page.evaluate("""() => {
            // een flink aantal clubs erbij, zodat traagheid zichtbaar zou worden
            for (let i = 0; i < 50; i++) {
                CLUBS['C' + i] = JSON.parse(JSON.stringify(CLUBS['Testclub']));
            }
            saveClubsToStorage();
            localStorage.setItem('golf_clubs_backup_fingerprint', clubsVingerafdruk());
            const t0 = performance.now();
            for (let i = 0; i < 200; i++) refreshTabDot();
            return { msPerKeer: (performance.now() - t0) / 200,
                     clubs: Object.keys(CLUBS).length };
        }""")
        print(f"   {snelheid['clubs']} clubs, {snelheid['msPerKeer']:.3f} ms per verversing")
        check("de stipverversing blijft snel", snelheid["msPerKeer"] < 1.0, True)

        # De bewaarde vingerafdruk mag niet uit de pas lopen met de werkelijkheid.
        gelijk = await page.evaluate("""() => {
            CLUBS['Nog een'] = { club: 'Nog een', shortName: 'NE', courses: {} };
            saveClubsToStorage();
            return localStorage.getItem('golf_clubs_fingerprint') === clubsVingerafdruk();
        }""")
        check("de bewaarde vingerafdruk klopt met de clubs", gelijk, True)

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
