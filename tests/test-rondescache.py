"""De bewaarde rondelijst: sneller, maar zonder besmettingsrisico.

loadSavedRounds werd heel vaak aangeroepen — bij het openen van Instellingen 65 keer —
en ontleedde elke keer de volledige JSON opnieuw. Samen 3,6 MB werk voor één scherm.

De uitkomst wordt daarom bewaard zolang de opgeslagen tekst niet verandert. Twee dingen
moeten daarbij kloppen, en die worden hier bewaakt:

  * WIJZIGEN: wie de teruggegeven lijst of een ronde daarin aanpast, mag daarmee niet
    de bewaarde stand aantasten. Er wordt op vijf plekken in de uitkomst geschoven.
  * BIJBLIJVEN: schrijft de app (of een ander tabblad) nieuwe rondes weg, dan moet de
    volgende aanroep die meteen zien.
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
        context = await browser.new_context(viewport={"width": 390, "height": 844})
        page = await context.new_page()
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Testclub');
            // Zonder spelersnaam blijven de handicaptabellen leeg en meet de test niets.
            localStorage.setItem('golf_profile_name', 'Tester');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, [ronde(i, '2026-08-%02d' % i) for i in range(1, 6)]])
        await page.reload()
        await page.wait_for_timeout(700)

        print("=== DE BEWAARDE LIJST RAAKT NIET BESMET ===\n")
        lijst = await page.evaluate("""() => {
            const a = loadSavedRounds();
            a.splice(0, 2);          // in de lijst schuiven
            a.push({ id: 999 });
            return loadSavedRounds().length;
        }""")
        check("schuiven in de lijst laat de stand ongemoeid", lijst, 5)

        obj = await page.evaluate("""() => {
            const a = loadSavedRounds();
            a[0].note = 'besmet';
            a[0].holes[0].score = 99;
            const b = loadSavedRounds();
            return { note: b[0].note, score: b[0].holes[0].score };
        }""")
        check("een ronde aanpassen raakt de stand niet", obj["note"], "")
        check("ook niet via de holes", obj["score"], 5)

        print("\n=== DE LIJST BLIJFT BIJ ===\n")
        na = await page.evaluate("""(nieuw) => {
            const lijst = loadSavedRounds();
            lijst.push(nieuw);
            setRoundsAndMark(JSON.stringify(lijst));
            return loadSavedRounds().length;
        }""", ronde(99, '2026-08-28'))
        check("na opslaan is de nieuwe ronde er", na, 6)

        # Een tweede tabblad schrijft: de opgeslagen tekst is dan anders, dus de
        # bewaarde stand moet vervallen.
        tweede = await context.new_page()
        await tweede.goto(app_url())
        await tweede.wait_for_timeout(700)
        await tweede.evaluate("""(nieuw) => {
            const lijst = loadSavedRounds();
            lijst.push(nieuw);
            setRoundsAndMark(JSON.stringify(lijst));
        }""", ronde(77, '2026-08-27'))
        await page.wait_for_timeout(300)
        check("een ander tabblad wordt gezien",
              await page.evaluate("() => loadSavedRounds().length"), 7)
        await tweede.close()

        print("\n=== DE ALLEEN-LEZEN VARIANT WIJZIGT NIETS ===\n")
        # Drie functies gebruiken leesRondes(): die krijgt de bewaarde lijst zonder
        # kopie, omdat ze uitsluitend tellen en filteren. Als daar ooit toch iets
        # gewijzigd wordt, moet dat hier opvallen.
        onaangetast = await page.evaluate("""() => {
            const voor = JSON.stringify(loadSavedRounds());
            afgerondeRondesCount();
            openStaandeMeldingen();
            huidigeBackupInhoud();
            backupVerschil();
            return JSON.stringify(loadSavedRounds()) === voor;
        }""")
        check("tellen en filteren laat de rondes ongemoeid", onaangetast, True)

        print("\n=== BEWAARDE BEREKENINGEN BLIJVEN KLOPPEN ===\n")
        # De handicaptabellen en de historie-functies worden bewaard tot de rondes
        # wijzigen. Als dat misgaat, zie je oude handicapstanden op je kaarten — en dat
        # valt niet op. Daarom: wijzig een score en controleer dat alles meebeweegt.
        meebewegen = await page.evaluate("""() => {
            // Genoeg rondes voor een echte handicapberekening (de WHS-staffel en de
            // Low HI hebben er tientallen nodig, anders blijft alles leeg).
            const basis = loadSavedRounds()[0];
            const veel = [];
            for (let i = 0; i < 30; i++) {
                const maand = String((i % 12) + 1).padStart(2, '0');
                const dag = String((i % 28) + 1).padStart(2, '0');
                veel.push({ ...basis, id: 2000 + i, date: '2025-' + maand + '-' + dag,
                            holes: basis.holes.map(h => ({ ...h })) });
            }
            // De bestaande rondes verdwijnen hierbij; dat mag alleen via metVerwijderen(),
            // anders weigert de app de schrijfactie (de rem op onbedoeld rondeverlies).
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(veel)));
            nav('archive'); loadSaved();
            const eersteId = loadSavedRounds()[0].id;
            const voor = handicapTabellen(loadSavedRounds()).hcpTrendMap[eersteId];
            const lowHiVoor = effectiveLowHi('Tester', loadSavedRounds());

            const lijst = loadSavedRounds();
            lijst.forEach(r => { r.sdFinal = 12.0; r.sd = 12.0; });
            setRoundsAndMark(JSON.stringify(lijst));

            loadSaved();
            const na = handicapTabellen(loadSavedRounds()).hcpTrendMap[eersteId];
            const lowHiNa = effectiveLowHi('Tester', loadSavedRounds());
            return {
                trendVeranderd: JSON.stringify(voor) !== JSON.stringify(na),
                lowHiVeranderd: lowHiVoor !== lowHiNa,
            };
        }""")
        check("het verloop per ronde beweegt mee", meebewegen["trendVeranderd"], True)
        check("de Low HI ook", meebewegen["lowHiVeranderd"], True)

        # Een doorrekening met een eigen lijst mag NIET uit de bewaarde stand komen.
        eigenLijst = await page.evaluate("""() => {
            const echt = loadSavedRounds();
            const verzonnen = echt.map(r => ({ ...r, sdFinal: 40.0, sd: 40.0 }));
            const metEcht = effectiveLowHi('Tester', echt);
            const metVerzonnen = effectiveLowHi('Tester', verzonnen);
            return metEcht !== metVerzonnen;
        }""")
        check("een eigen lijst wordt apart doorgerekend", eigenLijst, True)

        # Alles wat de uitkomst beïnvloedt hoort in de sleutel. De handmatige Low HI zat
        # er eerst niet in: die wijzigen liet de bewaarde tabellen staan, en dan zag je
        # op je kaarten nog het verloop van vóór de wijziging.
        lowHiInSleutel = await page.evaluate("""() => {
            nav('archive'); loadSaved();
            const eerste = () => {
                const t = handicapTabellen().hcpTrendMap;
                const ids = Object.keys(t);
                return ids.length ? t[ids[ids.length - 1]].newHcp : null;
            };
            const voor = eerste();
            localStorage.setItem('golf_low_hi', '5.0');
            const na = eerste();
            localStorage.removeItem('golf_low_hi');
            return { voor, na, anders: voor !== na };
        }""")
        check("een handmatige Low HI werkt door", lowHiInSleutel["anders"], True)

        # En de speler: onder een andere naam horen er geen tabellen te zijn.
        anderSpeler = await page.evaluate("""() => {
            nav('setup');
            document.getElementById('iName').value = 'Iemand anders';
            nav('archive'); loadSaved();
            const leeg = Object.keys(handicapTabellen().hcpTrendMap).length;
            nav('setup');
            document.getElementById('iName').value = 'Tester';
            nav('archive'); loadSaved();
            const terug = Object.keys(handicapTabellen().hcpTrendMap).length;
            return { leeg, terug };
        }""")
        check("een andere speler geeft lege tabellen", anderSpeler["leeg"], 0)
        check("en de eigen speler weer gevulde", anderSpeler["terug"] > 0, True)

        print("\n=== EN HET IS SNELLER ===\n")
        snelheid = await page.evaluate("""() => {
            // een flinke lijst, zodat het verschil meetbaar is
            const veel = [];
            for (let i = 0; i < 200; i++) {
                const r = JSON.parse(JSON.stringify(loadSavedRounds()[0]));
                r.id = 1000 + i;
                veel.push(r);
            }
            setRoundsAndMark(JSON.stringify(veel));
            const ruw = localStorage.getItem('golf_rounds');
            loadSavedRounds();                       // eerste keer: ontleden
            const t0 = performance.now();
            for (let i = 0; i < 200; i++) loadSavedRounds();
            const metCache = (performance.now() - t0) / 200;
            const t1 = performance.now();
            for (let i = 0; i < 200; i++) JSON.parse(ruw);
            const ontleden = (performance.now() - t1) / 200;
            return { metCache, ontleden, rondes: veel.length };
        }""")
        print(f"   {snelheid['rondes']} rondes: {snelheid['metCache']:.3f} ms uit de cache, "
              f"{snelheid['ontleden']:.3f} ms bij opnieuw ontleden")
        check("uit de cache is sneller dan opnieuw ontleden",
              snelheid["metCache"] < snelheid["ontleden"], True)

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
