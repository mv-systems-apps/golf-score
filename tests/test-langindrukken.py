"""Lang indrukken is overal een toggle.

Op drie plekken doet lang indrukken iets met "alles tegelijk". De eis is telkens
dezelfde: nog een keer lang indrukken brengt je terug. Anders kun je met dezelfde
handeling niet terug en lijkt een tweede lange druk niets te doen — dat was het geval
bij Clubs (altijd inklappen) en bij WHS (altijd verkorten).

  * groepeer op club  -> alle clubs en banen in- of uitklappen
  * jaarkop archief   -> alle jaren in- of uitklappen
  * groepeer op WHS   -> verkorte of volledige kaarten

Het tabblad in Instellingen heeft dezelfde vorm; dat wordt in test-instellingen2 bewaakt.
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
            naam: {
                "holeIds": ["H%d" % (i + 1) for i in range(9)],
                "tees": {"Heren": {"Wit": {"CR": 35.0, "SR": 120,
                          "holes": [{"par": 4, "si": i + 1} for i in range(9)]}}},
            } for naam in ("Baan A", "Baan B")
        },
    },
    "Tweede club": {
        "club": "Tweede club", "shortName": "2C",
        "courses": {
            "Verre baan": {
                "holeIds": ["V%d" % (i + 1) for i in range(9)],
                "tees": {"Heren": {"Wit": {"CR": 34.0, "SR": 118,
                          "holes": [{"par": 4, "si": i + 1} for i in range(9)]}}},
            }
        },
    },
}


def ronde(rid, datum, club, kort, baan):
    return {
        "id": rid, "date": datum, "time": "09:00", "player": "Tester", "hcp": 30.7,
        "club": club, "clubShort": kort, "track": baan, "gender": "Heren",
        "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
        "note": "", "total": 45, "totalStb": 18, "playedCount": 9, "holesCount": 9,
        "currentHole": 0, "started": True, "sd": 30.0, "sdFinal": 30.0, "pcc": 0,
        "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }

RONDES = [
    ronde(1, '2026-08-01', 'Testclub', 'TC', 'Baan A'),
    ronde(2, '2025-06-01', 'Testclub', 'TC', 'Baan B'),
    ronde(3, '2023-05-01', 'Tweede club', '2C', 'Verre baan'),
    ronde(4, '2022-05-01', 'Tweede club', '2C', 'Verre baan'),
]

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
            localStorage.setItem('golf_profile_name', 'Tester');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(700)
        await page.evaluate("() => nav('archive')")
        await page.wait_for_timeout(400)

        # Trillingen opvangen: elke lange druk hoort er één te geven, als bevestiging
        # dat je hem lang genoeg hebt ingedrukt.
        await page.evaluate("""() => {
            window.__tril = [];
            navigator.vibrate = v => { window.__tril.push(v); return true; };
        }""")

        async def driemaal(functie, meting):
            """Drie keer lang indrukken en telkens meten; geeft de drie standen terug."""
            uit = []
            for _ in range(3):
                uit.append(await page.evaluate("""([f, m]) => {
                    window.__tril = [];
                    window[f]();
                    return { stand: eval(m), tril: window.__tril.length };
                }""", [functie, meting]))
            return uit

        KAARTEN = "document.querySelectorAll('#screen-archive .saved-item').length"

        print("=== GROEPEREN IN HET ARCHIEF ===\n")
        for functie, naam, ander in [('collapseAllPlayers', 'spelers', 'collapseAllCategories'),
                                     ('collapseAllCategories', 'categorieën', 'collapseAllPlayers'),
                                     ('collapseAllClubs', 'clubs', 'collapseAllPlayers')]:
            # Eerst een ANDERE weergave kiezen, zodat de eerste druk echt een keuze is.
            await page.evaluate("(f) => window[f]()", ander)
            r = await driemaal(functie, KAARTEN)
            standen = [x["stand"] for x in r]
            check(f"{naam}: de eerste druk klapt alles dicht", standen[0], 0)
            check(f"{naam}: de tweede klapt alles open", standen[1], len(RONDES))
            check(f"{naam}: de derde weer dicht", standen[2], 0)

        print("\n=== DE AGENDAKNOP ===\n")
        # Lang indrukken klapt de drie groepen (Deze week, Volgende week, Later) tegelijk
        # open of dicht, en zet de agendaweergave zelf aan — net als de andere
        # groepeerknoppen doen met hun eigen weergave.
        agenda = await page.evaluate("""() => {
            // Twee geplande rondes in verschillende weken.
            const nu = new Date();
            const plus = d => { const x = new Date(nu); x.setDate(x.getDate() + d);
                                return new Date(x.getTime() - x.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
            const basis = loadSavedRounds()[0];
            const leeg = (id, datum) => ({ ...basis, id, date: datum, playedCount: 0,
                started: false, total: 0, totalStb: 0, sd: null, sdFinal: null,
                holes: basis.holes.map(h => ({ ...h, score: null })) });
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(
                [leeg(9001, plus(1)), leeg(9002, plus(9)), leeg(9003, plus(40))])));

            window._groupByPlanned = false; window._planCollapsed = null;
            // Een actieve ronde uit een eerdere stap zou als vierde geplande ronde
            // meetellen; die eerst loslaten.
            localStorage.removeItem('golf_active_id');
            if (typeof game === 'object') game.started = false;
            nav('archive'); loadSaved();
            const uit = [];
            for (let i = 0; i < 3; i++) {
                collapseAllPlanned();
                // Alleen echte rondekaarten tellen: de regel 'Er zijn geen geplande
                // rondes' van een lege weekgroep draagt dezelfde opmaakklasse.
                uit.push({ kaarten: [...document.querySelectorAll('#screen-archive .saved-item')]
                               .filter(k => /\d{1,2}-\d{1,2}-\d{4}|Morgen|Vandaag/.test(k.innerText)).length,
                           inAgenda: !!window._groupByPlanned });
            }
            // Dezelfde regel als de app: niet afgerond én in de toekomst. Een
            // toekomstige ronde waarin al een hole is ingevuld telt dus ook mee.
            return { beurten: uit,
                     gepland: loadSavedRounds().filter(r => !isRondeAf(r)
                         && new Date(`${r.date || '1970-01-01'}T${r.time || '00:00'}`)
                            .getTime() > Date.now()).length };
        }""")
        gepland = agenda["gepland"]
        agenda = agenda["beurten"]
        # Overal dezelfde regel: staat alles dicht, dan opent een lange druk alles;
        # anders sluit hij alles. De uitgangsstand hier is 'Deze week' open, dus de
        # eerste druk sluit.
        check("de eerste lange druk opent de agenda", agenda[0]["inAgenda"], True)
        check("en klapt de drie groepen dicht", agenda[0]["kaarten"], 0)
        check("de tweede klapt ze open", agenda[1]["kaarten"], gepland)
        check("de derde weer dicht", agenda[2]["kaarten"], 0)

        # De oorspronkelijke rondes terugzetten: de stappen hierna rekenen daarop.
        await page.evaluate("""(rondes) => {
            window._groupByPlanned = false;
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rondes)));
            nav('archive'); loadSaved();
        }""", RONDES)

        print("\n=== GROEPEER OP WHS ===\n")
        whs = await driemaal('setWhsShort', 'window._whsShort === true')
        # De WHS-weergave heeft geen groepen; 'alles dicht' is hier de verkorte kaart.
        check("eerst verkort, dan wisselen",
              [x["stand"] for x in whs], [True, False, True])
        check("de groepering staat aan",
              await page.evaluate("() => !!window._groupByWhs"), True)

        print("\n=== CLUBSCHERM ===\n")
        await page.evaluate("() => nav('club')")
        await page.wait_for_timeout(300)
        ZICHTBAAR = "[...document.querySelectorAll('#screen-club .card')].filter(c => c.offsetParent).length"
        await page.evaluate("() => { window._clubGrouped = false; buildClubList(); }")
        clubcat = await driemaal('collapseAllClubCategories', ZICHTBAAR)
        standen = [x["stand"] for x in clubcat]
        check("clubcategorieën: eerst dicht", standen[0], 0)
        check("dan open", standen[1] > 0, True)
        check("dan weer dicht", standen[2], 0)

        print("\n=== JAARKOPPEN ===\n")
        await page.evaluate("""() => {
            nav('archive');
            window._groupByTrack = false; window._groupByPlayer = false;
            window._groupByCategory = false; window._groupByWhs = false;
            window._allesClubsDicht = false; window._clubTrkCollapsed = {};
            loadSaved();
        }""")
        await page.wait_for_timeout(300)
        jaren = await driemaal('toggleAlleArchiefJaren', KAARTEN)
        standen = [x["stand"] for x in jaren]
        check("jaren wisselen in en uit", standen[0] != standen[1] and standen[1] != standen[2], True)
        check("alles open toont alle rondes", max(standen), len(RONDES))
        check("alles dicht toont er geen", min(standen), 0)

        print("\n=== TRILLING ===\n")
        # De lange druk zelf trilt (via bindLangIndrukken en de twee eigen afhandelaars);
        # dat wordt hier via de echte gebeurtenissen gecontroleerd.
        async def echteLangeDruk(kiezer, scherm):
            await page.evaluate("(s) => nav(s)", scherm)
            await page.wait_for_timeout(250)
            # De jaarkop bestaat alleen als de vlakke lijst wordt getoond; een eerdere
            # groepering zou hem uit beeld halen.
            if kiezer == '.year-sep':
                await page.evaluate("""() => {
                    window._groupByTrack = false; window._groupByPlayer = false;
                    window._groupByCategory = false; window._groupByWhs = false;
                    loadSaved();
                }""")
                await page.wait_for_timeout(300)
            await page.evaluate("""(k) => {
                window.__tril = [];
                document.querySelector(k).dispatchEvent(
                    new PointerEvent('pointerdown', { bubbles: true }));
            }""", kiezer)
            await page.wait_for_timeout(650)
            await page.evaluate("""(k) => document.querySelector(k).dispatchEvent(
                new PointerEvent('pointerup', { bubbles: true }))""", kiezer)
            await page.wait_for_timeout(200)
            return await page.evaluate("() => window.__tril.length")

        for kiezer, scherm, naam in [
            ('#groupByPlayerBtn', 'archive', 'groepeer op speler'),
            ('#groupByCategoryBtn', 'archive', 'groepeer op categorie'),
            ('#groupByTrackBtn', 'archive', 'groepeer op club'),
            ('#groupByWhsBtn', 'archive', 'groepeer op WHS'),
            ('#clubGroupByCategoryBtn', 'club', 'clubs groeperen'),
            ('#groupByPlannedBtn', 'archive', 'geplande rondes'),
            ('.year-sep', 'archive', 'jaarkop'),
            ('#settingsTabBtnMain', 'settings', 'tabblad Instellingen'),
        ]:
            check(f"{naam} trilt", await echteLangeDruk(kiezer, scherm) > 0, True)

        print("\n=== PERIODEKNOPPEN OP STATISTIEKEN ===\n")
        # Lang indrukken op een periodeknop klapt de drie hoofdgroepen in of uit, net als
        # op een tabblad in Instellingen. Kort tikken moet gewoon de periode wisselen.
        await page.evaluate("() => nav('stat')")
        await page.wait_for_timeout(500)

        async def langOpPeriode():
            await page.evaluate("""() => {
                window.__tril = [];
                const k = document.querySelector('.stat-periode-knop');
                k.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
            }""")
            await page.wait_for_timeout(650)
            await page.evaluate("""() => {
                const k = document.querySelector('.stat-periode-knop');
                k.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                k.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            }""")
            await page.wait_for_timeout(350)
            return await page.evaluate("""() => ({
                groepen: ['handicap', 'prestaties', 'banen']
                    .map(k => localStorage.getItem('golf_stats_grp_' + k)),
                tril: window.__tril.length,
                periode: window._statChartPeriod,
            })""")

        await page.evaluate("""() => {
            window._statChartPeriod = 'l20';
            navigator.vibrate = v => { (window.__tril = window.__tril || []).push(v); return true; };
        }""")
        beurt1 = await langOpPeriode()
        beurt2 = await langOpPeriode()
        check("eerste lange druk klapt alles dicht", beurt1["groepen"],
              ['closed', 'closed', 'closed'])
        # Op Statistieken valt niets te kiezen — je bent er al — dus wisselt hij meteen.
        # De groep Clubs blijft daarbij dicht: die lijst met clubs, banen en tees vult
        # anders het hele scherm, terwijl je vrijwel altijd maar naar één club kijkt.
        check("de tweede klapt handicap en prestaties open",
              beurt2["groepen"], ['open', 'open', 'closed'])
        check("en het trilt", beurt1["tril"] > 0 and beurt2["tril"] > 0, True)
        # De tik die na de lange druk komt mag de periode niet omzetten.
        # De lange druk KIEST ook de periode: de tik erna wordt onderdrukt, dus zonder
        # dat zou de oude periode blijven staan.
        gekozen = await page.evaluate("""async () => {
            window._statChartPeriod = 'l20';
            renderPlayerStats();
            const knop = [...document.querySelectorAll('.stat-periode-knop')]
                .find(b => b.dataset.periode === 'alles' && !b.disabled);
            if (!knop) return 'geen knop';
            knop.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
            await new Promise(r => setTimeout(r, 700));
            knop.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
            knop.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            await new Promise(r => setTimeout(r, 300));
            return window._statChartPeriod;
        }""")
        check("een lange druk kiest ook de periode", gekozen, 'alles')

        # Kort tikken doet nog wel gewoon zijn werk. Knoppen met te weinig punten staan
        # uit, dus eerst een andere periode kiezen en dan terug naar 'Laatste 20'.
        kort = await page.evaluate("""() => {
            window._statChartPeriod = 'alles';
            renderPlayerStats();
            document.querySelector('.stat-periode-knop').click();
            return window._statChartPeriod;
        }""")
        check("kort tikken wisselt de periode", kort, 'l20')

        print("\n=== ÉÉN TIK OPENT EEN SPELERGROEP ===\n")
        # De spelerkoppen gebruikten een andere schakelvorm dan alle andere koppen:
        # bij een speler die nog niet in de bewaarde stand zat, deed de eerste tik niets
        # en klapte pas de tweede open. Dat treft precies een nieuwe medespeler.
        eersteTik = await page.evaluate("""() => {
            nav('archive');
            toggleGroupByPlayer();
            // een speler die nog niet in de bewaarde stand voorkomt
            delete window._pgCollapsed['pg_Tester'];
            loadSaved();
            const kop = document.querySelector("#screen-archive [onclick*='pg_Tester']");
            if (!kop) return { gevonden: false };
            kop.click();
            return { gevonden: true, open: window._pgCollapsed['pg_Tester'] === false };
        }""")
        check("de spelerkop is er", eersteTik["gevonden"], True)
        check("en één tik klapt hem open", eersteTik.get("open"), True)

        print("\n=== EEN ENKELE TIK BEWAART DE INDELING ===\n")
        # Een enkele klik is 'ga hierheen', geen 'begin opnieuw'. Twee plekken zetten dat
        # eerder terug: WHS zette de kaarten altijd op volledig, en het springen vanuit
        # de grafiek wiste de spelersindeling — dus kwam je via WHS terug bij spelers,
        # dan stond 'Laatste 12 maanden' ineens weer open.
        bewaard = await page.evaluate("""() => {
            nav('archive');
            const kaarten = () => document.querySelectorAll('#screen-archive .saved-item').length;
            const uit = {};

            // WHS onthoudt of je verkort of volledig kijkt. (Een eerdere stap in deze
            // test heeft de kaartvorm al verzet, dus hier eerst een vaste beginstand.)
            window._whsShort = false;
            toggleGroupByWhs();
            uit.whsBijStart = !!window._whsShort;
            toggleWhsShort();
            uit.whsNaWissel = !!window._whsShort;
            toggleGroupByWhs(); toggleGroupByWhs();
            uit.whsNaTerugkeer = !!window._whsShort;
            toggleGroupByWhs();

            // De spelersindeling overleeft een uitstapje naar WHS.
            toggleGroupByPlayer();
            window._pgCollapsed = { 'pg_Tester': false };
            window._pgYearCollapsed = { 'pgy_Tester_last12': false };
            loadSaved();
            uit.twaalfOpen = kaarten();
            window._pgYearCollapsed = { 'pgy_Tester_last12': true };
            loadSaved();
            uit.twaalfDicht = kaarten();
            toggleGroupByWhs();          // even naar WHS
            toggleGroupByPlayer();       // en terug
            uit.naWhsTerug = kaarten();
            return uit;
        }""")
        check("WHS begint volledig", bewaard["whsBijStart"], False)
        check("een lange druk maakt hem verkort", bewaard["whsNaWissel"], True)
        check("en dat blijft zo bij terugkeer", bewaard["whsNaTerugkeer"], True)
        check("met 12 maanden open zie je kaarten", bewaard["twaalfOpen"] > 0, True)
        check("dichtgeklapt geen", bewaard["twaalfDicht"], 0)
        check("en via WHS blijft dat dicht", bewaard["naWhsTerug"], 0)

        print("\n=== ZOEKEN ZET DE GROEPERING UIT ===\n")
        # Zoeken en groeperen zijn twee verschillende dingen. Door elkaar heen gaven ze
        # tegenstrijdige uitkomsten: in de WHS-weergave stond er "3 rondes gevonden"
        # boven een LEGE lijst, omdat die weergave alleen je laatste 20 toont en de
        # treffers er daarna weer uit filterde. Nu schakelt zoeken naar de vlakke lijst,
        # en het wissen brengt je terug waar je vandaan kwam.
        zoeken = {}
        for naam, functie in [('whs', 'toggleGroupByWhs'),
                              ('speler', 'toggleGroupByPlayer'),
                              ('categorie', 'toggleGroupByCategory')]:
            zoeken[naam] = await page.evaluate("""(f) => {
                nav('archive');
                ['_groupByPlayer', '_groupByCategory', '_groupByTrack', '_groupByWhs',
                 '_groupByPlanned'].forEach(k => window[k] = false);
                window._zoekVorigeWeergave = null;
                const veld = document.getElementById('archiveSearch');
                veld.value = '';
                window[f]();
                const actief = () => ['Player', 'Category', 'Track', 'Whs', 'Planned']
                    .filter(k => window['_groupBy' + k]).join(',') || 'vlak';
                const voor = actief();
                veld.value = 'Testclub';
                zoekInRondes();
                const tijdens = actief();
                veld.value = '';
                herstelNaZoeken();
                return { voor, tijdens, na: actief() };
            }""", functie)
        for naam in ('whs', 'speler', 'categorie'):
            check(f"{naam}: zoeken toont de vlakke lijst", zoeken[naam]["tijdens"], 'vlak')
            check(f"{naam}: en wissen brengt je terug",
                  zoeken[naam]["na"], zoeken[naam]["voor"])

        print("\n=== ZOEKEN VINDT OOK GEPLANDE RONDES ===\n")
        # Geplande rondes staan bewust NIET in de vlakke lijst: die gebruik je om terug
        # te kijken, en de planning verandert voortdurend. Maar zodra je zoekt, zoek je
        # in alles — anders stond er "2 rondes gevonden" boven een lijst met er één, en
        # was de tweede nergens te vinden (de agendaweergave gaat bij zoeken uit).
        gepland = await page.evaluate("""() => {
            const basis = loadSavedRounds()[0];
            const nu = new Date();
            const plus = d => { const x = new Date(nu); x.setDate(x.getDate() + d);
                                return new Date(x.getTime() - x.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
            metVerwijderen(() => setRoundsAndMark(JSON.stringify([
                { ...basis, id: 7101, date: '2026-08-01', note: 'Toernooi',
                  playedCount: 9, started: true },
                { ...basis, id: 7102, date: plus(3), note: 'Toernooi', playedCount: 0,
                  started: false, sd: null, sdFinal: null,
                  holes: basis.holes.map(h => ({ ...h, score: null })) },
            ])));
            window._groupByPlanned = false; window._groupByPlayer = false;
            window._groupByCategory = false; window._groupByTrack = false;
            window._groupByWhs = false;
            window._zoekVorigeWeergave = null;
            const veld = document.getElementById('archiveSearch');
            veld.value = '';
            nav('archive'); loadSaved();
            const zonderZoeken = document.querySelectorAll('#screen-archive .saved-item').length;

            veld.value = 'Toernooi';
            zoekInRondes();
            const metZoeken = document.querySelectorAll('#screen-archive .saved-item').length;
            const teller = document.getElementById('savedList').innerText.split('\\n')[0];

            veld.value = '';
            herstelNaZoeken();
            const naWissen = document.querySelectorAll('#screen-archive .saved-item').length;
            return { zonderZoeken, metZoeken, teller, naWissen };
        }""")
        check("zonder zoeken staat de geplande ronde er niet", gepland["zonderZoeken"], 1)
        check("bij zoeken wel", gepland["metZoeken"], 2)
        check("en de teller klopt met wat je ziet",
              gepland["teller"].startswith('2 rondes gevonden'), True)
        check("na wissen is hij weer weg", gepland["naWissen"], 1)

        # De oorspronkelijke rondes terugzetten: de stappen hierna rekenen daarop.
        await page.evaluate("""(rondes) => {
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rondes)));
            nav('archive'); loadSaved();
        }""", RONDES)

        print("\n=== DE TABBLADEN IN INSTELLINGEN ===\n")
        # Lang indrukken op een tabknop moet die tab ook echt KIEZEN. De tik die erop
        # volgt wordt onderdrukt, dus zonder dat gebeurt er niets; en de nieuwe tab is
        # pas na de doorloop zichtbaar, dus de secties van de vórige tab werden
        # dichtgeklapt.
        async def langOpTab(knopId):
            # Met een ECHTE muisdruk, niet met nagemaakte gebeurtenissen: die laatste
            # verhulden dat deze knoppen hun eigen langedruk-code hadden, die op een
            # toestel anders uitpakte. Ze gebruiken nu dezelfde functie als de rest.
            el = await page.query_selector('#' + knopId)
            box = await el.bounding_box()
            await page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            await page.mouse.down()
            await page.wait_for_timeout(700)
            await page.mouse.up()
            await page.wait_for_timeout(400)
            return await page.evaluate("""() => ({
                tab: ['settingsTabMain', 'settingsTabWhs', 'settingsTabData']
                    .filter(id => !document.getElementById(id).classList.contains('hidden'))[0],
                open: [...document.querySelectorAll('[data-section-key]')]
                    .filter(k => k.offsetParent && k.nextElementSibling.style.display !== 'none').length,
            })""")

        await page.evaluate("() => { nav('settings'); switchSettingsTab('main'); }")
        await page.wait_for_timeout(300)
        t1 = await langOpTab('settingsTabBtnData')
        check("de lange druk kiest de tab", t1["tab"], 'settingsTabData')
        check("en klapt alles dicht", t1["open"], 0)
        t2 = await langOpTab('settingsTabBtnData')
        check("nogmaals klapt alles open", t2["open"] > 0, True)
        t3 = await langOpTab('settingsTabBtnWhs')
        check("een andere tab kiest en sluit weer", t3["tab"], 'settingsTabWhs')
        check("met alles dicht", t3["open"], 0)

        print("\n=== WELKE CLUB KRIJGT VOORRANG ===\n")
        # Bij een enkele tik op 'groepeer op club' klapt één club open. De volgorde:
        # eerst de ronde die je nú speelt, dan de club die op Start geselecteerd staat,
        # en pas als laatste je thuisclub.
        voorrang = []
        for kv, verwacht in [
            # ronde 3 is van 'Tweede club'; met Testclub als geselecteerde club en
            # Tweede club als thuisclub is dit het enige geval dat de actieve ronde
            # onderscheidt van de rest.
            ({'golf_active_id': '3', 'golf_default_club': 'Testclub',
              'golf_home_club': 'Testclub'}, 'Tweede club'),
            ({'golf_default_club': 'Testclub', 'golf_home_club': 'Tweede club'}, 'Testclub'),
            ({'golf_home_club': 'Tweede club'}, 'Tweede club'),
            ({}, None),
        ]:
            gekregen = await page.evaluate("""(kv) => {
                ['golf_active_id', 'golf_default_club', 'golf_home_club']
                    .forEach(k => localStorage.removeItem(k));
                Object.entries(kv).forEach(([k, v]) => localStorage.setItem(k, v));
                return getPriorityGroupClub();
            }""", kv)
            voorrang.append((gekregen, verwacht))
        check("de actieve ronde gaat voor", voorrang[0][0], voorrang[0][1])
        check("daarna de geselecteerde club", voorrang[1][0], voorrang[1][1])
        check("daarna de thuisclub", voorrang[2][0], voorrang[2][1])
        check("en anders geen club", voorrang[3][0], voorrang[3][1])

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
