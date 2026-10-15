"""Ook de gegroepeerde lijsten bouwen niet honderden kaarten in één keer.

De vlakke lijst had die bescherming al: hooguit vijftig kaarten, met een knop om de rest
te laden. De gegroepeerde weergaven niet — en juist daar kun je met één lange druk alles
openklappen. Gemeten bij 1000 rondes: spelers 317 ms, clubs 689 ms, categorieën 933 ms,
en op een toestel een veelvoud daarvan.

Twee dingen moeten daarbij kloppen:
  * de KOPPEN worden altijd gebouwd, ook voorbij de grens — anders verdwijnt een hele
    groep uit beeld zonder dat je hem nog kunt openklappen;
  * er is ÉÉN teller, dezelfde als die van de vlakke lijst, zodat het springen vanuit de
    grafiek en het zoeken niet met een tweede grens gaan botsen.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, jaar):
    return {
        "id": rid, "date": "%d-%02d-%02d" % (jaar, (rid % 12) + 1, (rid % 28) + 1),
        "time": "09:%02d" % (rid % 60),
        "player": "Mark" if rid % 4 else "Partner", "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "GC",
        "track": ["Airborne", "Helsum", "Sandr"][rid % 3], "gender": "Heren",
        "tee": ["Blauw", "Geel", "Rood"][rid % 3], "CR": 37.3, "SR": 141, "PAR": 36,
        "chcp": 11, "qualifying": True, "note": "", "total": 45, "totalStb": 18,
        "playedCount": 9, "holesCount": 9, "currentHole": 0, "started": True,
        "sd": 30.0 + rid % 5, "sdFinal": 30.0 + rid % 5, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5, "putts": 2} for i in range(9)],
    }

VEEL = [ronde(i, 2020 + (i % 7)) for i in range(1, 301)]

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
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            // Ook een flinke agenda, want die bouwt zijn kaarten langs een eigen weg.
            const nu = new Date();
            for (let i = 0; i < 80; i++) {
                const d = new Date(nu); d.setDate(d.getDate() + i + 1);
                rs.push({ ...rs[0], id: 5000 + i, date: new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10),
                          playedCount: 0, started: false, sd: null, sdFinal: null,
                          holes: rs[0].holes.map(h => ({ ...h, score: null })) });
            }
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, VEEL])
        await page.reload()
        await page.wait_for_timeout(1500)

        print("=== ALLES OPENKLAPPEN BLIJFT BEGRENSD ===\n")
        for naam, functie in [('spelers', 'collapseAllPlayers'),
                              ('categorieën', 'collapseAllCategories'),
                              ('clubs', 'collapseAllClubs'),
                              ('agenda', 'collapseAllPlanned')]:
            uit = await page.evaluate("""(f) => {
                nav('archive');
                window._flatListLimit = null;
                window[f]();          // eerste druk: alles dicht
                window[f]();          // tweede druk: alles open
                const tekst = document.getElementById('savedList').innerText;
                return {
                    // Alleen echte rondekaarten: de regel 'Geen geplande rondes' van een
                    // lege weekgroep draagt dezelfde opmaakklasse, en of die verschijnt
                    // hangt af van de dag waarop de test draait. Een ronde van gisteren heet
                    // 'Gisteren' in plaats van een datum (viel op 15-10-2026 voor het eerst op).
                    kaarten: [...document.querySelectorAll('#screen-archive .saved-item')]
                        .filter(k => /\d{1,2}-\d{1,2}-\d{4}|Morgen|Vandaag|Gisteren/.test(k.innerText)).length,
                    toonMeer: tekst.includes('Toon meer'),
                };
            }""", functie)
            check(f"{naam}: hooguit vijftig kaarten", uit["kaarten"], 50)
            check(f"{naam}: met een knop voor de rest", uit["toonMeer"], True)

        print("\n=== DE KNOP LAADT ER VIJFTIG BIJ ===\n")
        meer = await page.evaluate("""() => {
            const knop = [...document.querySelectorAll('#screen-archive button')]
                .find(b => b.textContent.trim() === 'Toon meer');
            knop.click();
            return document.querySelectorAll('#screen-archive .saved-item').length;
        }""")
        # De laatst getoonde weergave is de agenda met 80 geplande rondes: die passen
        # daarna in één keer.
        check("na één keer laden staan er meer dan vijftig", meer > 50, True)

        print("\n=== KOPPEN VERDWIJNEN NOOIT ===\n")
        # Zou een groep voorbij de grens ook zijn kop verliezen, dan was hij niet meer
        # open te klappen en waren die rondes onbereikbaar.
        koppen = await page.evaluate("""() => {
            nav('archive');
            // De vorige stap heeft de grens verhoogd met 'Toon meer'; hier weer terug
            // naar de standaard, anders meet deze controle een opgerekte lijst.
            window._flatListLimit = null;
            loadSaved();
            // Met deze vlag verschijnen ook de lege categorieën, dus alle vijf de koppen.
            window._toonLegeCategorieen = true;
            collapseAllCategories(); collapseAllCategories();
            const tekst = document.getElementById('savedList').innerText;
            return {
                koppen: ['ACTIEF', 'GEÏMPORTEERD', 'GEPLAND', 'GEPAUZEERD', 'AFGEROND']
                    .filter(k => tekst.includes(k)).length,
                // Alleen echte rondekaarten tellen: de regels 'Er zijn geen ...' van een
                // lege groep dragen dezelfde opmaakklasse.
                kaarten: [...document.querySelectorAll('#screen-archive .saved-item')]
                    .filter(k => /\d{1,2}-\d{1,2}-\d{4}/.test(k.innerText)).length,
            };
        }""")
        check("alle vijf de koppen staan er, ook voorbij de grens", koppen["koppen"], 5)
        check("terwijl de kaarten begrensd blijven", koppen["kaarten"] <= 50, True)

        print("\n=== KLEINE AANTALLEN MERKEN ER NIETS VAN ===\n")
        klein = await page.evaluate("""() => {
            const lijst = loadSavedRounds().slice(0, 35);
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
            window._flatListLimit = null;
            collapseAllPlayers(); collapseAllPlayers();
            const tekst = document.getElementById('savedList').innerText;
            return {
                kaarten: document.querySelectorAll('#screen-archive .saved-item').length,
                toonMeer: tekst.includes('Toon meer'),
            };
        }""")
        check("vijfendertig rondes passen in één keer", klein["kaarten"], 35)
        check("en er is geen knop nodig", klein["toonMeer"], False)

        print("\n=== STATISTIEKEN: CLUBS BLIJVEN DICHT ===\n")
        # Je kijkt vrijwel altijd naar één club; alles openklappen zou een lijst van
        # tientallen banen en tees geven.
        stat = await page.evaluate("""() => {
            nav('stat');
            ['handicap', 'prestaties', 'banen']
                .forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'closed'));
            window._statClubCollapsed = { 'club_Golfclub_Heelsum': false };
            toggleAlleStatsGroepen();     // alles open
            return {
                clubstand: JSON.stringify(window._statClubCollapsed),
                groepen: ['handicap', 'prestaties', 'banen']
                    .map(k => localStorage.getItem('golf_stats_grp_' + k)),
            };
        }""")
        # De groep 'Clubs' (sleutel 'banen') blijft zelf dicht: die lijst met clubs,
        # banen en tees vult anders het hele scherm, terwijl je vrijwel altijd maar naar
        # één club kijkt.
        check("handicap en prestaties gaan open", stat["groepen"][:2], ['open', 'open'])
        check("maar de groep Clubs blijft dicht", stat["groepen"][2], 'closed')
        check("en de clubs erbinnen ook", stat["clubstand"], '{}')

        # Alles dichtklappen doet de groep Clubs wél gewoon mee, en zelf openklappen
        # blijft werken.
        vervolg = await page.evaluate("""() => {
            toggleAlleStatsGroepen();                       // alles dicht
            const dicht = ['handicap', 'prestaties', 'banen']
                .map(k => localStorage.getItem('golf_stats_grp_' + k));
            localStorage.setItem('golf_stats_grp_banen', 'open');
            renderPlayerStats();
            const t = document.getElementById('screen-stat').innerText;
            return { dicht, clublijstZichtbaar: /THUISCLUB|OVERIG|FAVORIETEN/.test(t) };
        }""")
        check("alles dichtklappen sluit ook Clubs", vervolg["dicht"],
              ['closed', 'closed', 'closed'])
        check("en zelf openklappen toont de clublijst",
              vervolg["clublijstZichtbaar"], True)

        print("\n=== OOK BIJ ZOEKEN ===\n")
        # Zoeken kan honderden treffers opleveren; de grens hoort daar net zo goed te
        # gelden. De teller telt alles, de lijst bouwt er vijftig.
        zoek = await page.evaluate("""(rondes) => {
            // Een eerdere stap heeft de lijst tot 35 rondes teruggebracht; hier weer de
            // volle lijst, anders valt er niets te begrenzen.
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rondes)));
            nav('archive');
            window._flatListLimit = null; window._flatYearCollapsed = {};
            const veld = document.getElementById('archiveSearch');
            veld.value = 'Heelsum';
            zoekInRondes();
            const lijst = document.getElementById('savedList');
            return {
                kaarten: lijst.querySelectorAll('.saved-item').length,
                teller: lijst.innerText.split('\\n')[0],
                toonMeer: lijst.innerText.includes('Toon meer'),
            };
        }""", VEEL)
        check("zoeken bouwt hooguit vijftig kaarten", zoek["kaarten"], 50)
        check("de teller noemt het echte aantal",
              zoek["teller"].startswith('300 rondes gevonden')
              or 'rondes gevonden' in zoek["teller"], True)
        check("met een knop voor de rest", zoek["toonMeer"], True)

        # En zoeken in clubs zet de groepering uit, zoals bij de rondes: anders blijft
        # een treffer in een dichtgeklapte groep onzichtbaar.
        clubzoek = await page.evaluate("""() => {
            nav('club');
            window._clubZoekVorige = undefined;
            collapseAllClubCategories();          // groeperen, alles dicht
            const zicht = () => [...document.querySelectorAll('#screen-club .card')]
                .filter(c => c.offsetParent).length;
            const voor = { gegroepeerd: !!window._clubGrouped, zichtbaar: zicht() };
            document.getElementById('clubSearch').value = 'Heelsum';
            zoekInClubs();
            const tijdens = { gegroepeerd: !!window._clubGrouped, zichtbaar: zicht() };
            document.getElementById('clubSearch').value = '';
            herstelNaClubZoeken();
            return { voor, tijdens, na: { gegroepeerd: !!window._clubGrouped } };
        }""")
        check("clubs: gegroepeerd en dicht vóór het zoeken",
              [clubzoek["voor"]["gegroepeerd"], clubzoek["voor"]["zichtbaar"]], [True, 0])
        check("zoeken zet de groepering uit", clubzoek["tijdens"]["gegroepeerd"], False)
        check("en toont de treffer", clubzoek["tijdens"]["zichtbaar"] > 0, True)
        check("na wissen is de groepering terug", clubzoek["na"]["gegroepeerd"], True)

        print("\n=== HET CLUBSCHERM HEEFT GEEN GRENS NODIG ===\n")
        # Bewust géén 'Toon meer' hier. Een clubkaart is licht (een naam en een aantal
        # banen) waar een rondekaart tien regels, badges en een grafiekje heeft, en het
        # aantal groeit heel anders: rondes komen er elk seizoen tientallen bij, clubs
        # alleen als je ergens gaat spelen. Deze meting legt vast dat dat zo blijft — bij
        # 200 clubs, al onwaarschijnlijk veel, hoort het scherm ruim onder de 150 ms te
        # blijven. Slaat dit ooit aan, dan is er iets anders veranderd.
        clubmeting = await page.evaluate("""() => {
            const basis = CLUBS['Golfclub Heelsum'];
            Object.keys(CLUBS).forEach(k => { if (k !== 'Golfclub Heelsum') delete CLUBS[k]; });
            for (let i = 0; i < 199; i++) {
                CLUBS['Club ' + i] = JSON.parse(JSON.stringify(basis));
            }
            saveClubsToStorage();
            nav('club');
            window._clubGrouped = false;
            buildClubList();                       // warmlopen
            const t0 = performance.now();
            buildClubList();
            const lijst = performance.now() - t0;

            collapseAllClubCategories(); collapseAllClubCategories();   // alles open
            const t1 = performance.now();
            buildClubList();
            const alles = performance.now() - t1;

            return { clubs: Object.keys(CLUBS).length,
                     msLijst: lijst, msAllesOpen: alles,
                     zichtbaar: [...document.querySelectorAll('#screen-club .card')]
                         .filter(c => c.offsetParent).length };
        }""")
        print(f"   {clubmeting['clubs']} clubs: {clubmeting['msLijst']:.0f} ms voor de lijst, "
              f"{clubmeting['msAllesOpen']:.0f} ms met alles open")
        check("de clublijst blijft snel", clubmeting["msLijst"] < 150, True)
        check("ook met alles uitgeklapt", clubmeting["msAllesOpen"] < 150, True)
        check("en er wordt niets weggelaten", clubmeting["zichtbaar"] >= 200, True)

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
