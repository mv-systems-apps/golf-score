"""Doorspringen naar de eerstvolgende lege hole.

De regel: zodra je het invoerpaneel van een hole sluit en die hole een score heeft
gekregen, springt de app naar de eerstvolgende hole zonder score. Dat werkt hetzelfde
of je nu putts bijhoudt of niet — met putts aan hoort de puttregel bij dezelfde hole,
en meteen na de score wegspringen zou die onbereikbaar maken.

Twee dingen die bewust NIET gebeuren: springen bij een correctie op een al ingevulde
hole (dan wordt corrigeren onwerkbaar), en springen als er geen lege hole meer volgt.
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

RONDE = {
    "id": 1, "date": "2026-09-01", "time": "09:00", "player": "Tester", "hcp": 30.7,
    "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren",
    "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
    "note": "", "total": 0, "totalStb": 0, "playedCount": 0, "holesCount": 9,
    "currentHole": 0, "started": True, "sd": None, "sdFinal": None, "pcc": 0,
    "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
               "score": None} for i in range(9)],
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
        page.on('console', lambda m: paginafouten.append('console: ' + m.text)
                if m.type == 'error' else None)
        await page.goto(app_url())
        await page.evaluate("""([clubs, ronde]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify([ronde]));
            localStorage.setItem('golf_active_id', '1');
            localStorage.setItem('golf_default_club', 'Testclub');
            localStorage.setItem('golf_profile_name', 'Tester');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, RONDE])
        await page.reload()
        await page.wait_for_timeout(500)

        async def speel(putts_aan, autonext_aan, hole):
            """Vult hole in zoals op de kaart: paneel open, score met +, paneel dicht."""
            return await page.evaluate("""([puttsAan, autoNextAan, hole]) => {
                localStorage.setItem('golf_track_putts', puttsAan ? 'on' : 'off');
                localStorage.setItem('golf_auto_next', autoNextAan ? 'on' : 'off');
                setCurrentHole(hole); selectHole(hole); renderScore();
                toggleScoreButtons(hole);
                stepScore(hole, +1);
                const tussen = { hole: currentHole, paneel: scoreButtonsRow };
                toggleScoreButtons(hole);
                return { tussen, na: { hole: currentHole, paneel: scoreButtonsRow },
                         score: game.holes[hole].score,
                         putts: game.holes[hole].putts ?? null };
            }""", [putts_aan, autonext_aan, hole])

        print("=== PUTTS UIT ===\n")
        a = await speel(False, True, 0)
        check("blijft staan zolang het paneel open is", a["tussen"]["hole"], 0)
        check("springt door bij het sluiten", a["na"]["hole"], 1)
        check("paneel is dicht", a["na"]["paneel"], None)
        check("score bewaard", a["score"], 5)

        print("\n=== PUTTS AAN ===\n")
        b = await speel(True, True, 1)
        check("blijft staan na de score", b["tussen"]["hole"], 1)
        check("putts staan klaar op 2", b["putts"], 2)
        check("springt door bij het sluiten", b["na"]["hole"], 2)

        # De puttregel moet bereikbaar blijven zolang het paneel open is: dat is precies
        # waarvoor de sprong wordt uitgesteld.
        putts = await page.evaluate("""() => {
            localStorage.setItem('golf_track_putts', 'on');
            localStorage.setItem('golf_auto_next', 'on');
            setCurrentHole(2); selectHole(2); renderScore();
            toggleScoreButtons(2);
            stepScore(2, +1);
            const bereikbaar = puttRowActief();
            stepPutts(2, +1);
            const naPutt = game.holes[2].putts;
            toggleScoreButtons(2);
            return { bereikbaar, naPutt, hole: currentHole };
        }""")
        check("puttregel is bereikbaar", putts["bereikbaar"], True)
        check("putts aanpasbaar vóór de sprong", putts["naPutt"], 3)
        check("daarna alsnog doorgesprongen", putts["hole"], 3)

        print("\n=== WAT NIET MAG GEBEUREN ===\n")
        # Correctie op een al ingevulde hole: blijven staan
        correctie = await page.evaluate("""() => {
            setCurrentHole(0); selectHole(0); renderScore();
            toggleScoreButtons(0);
            stepScore(0, +1);
            toggleScoreButtons(0);
            return { hole: currentHole, score: game.holes[0].score };
        }""")
        check("correctie laat je staan", correctie["hole"], 0)
        check("de correctie is wel doorgevoerd", correctie["score"], 6)

        # Instelling uit: nooit springen
        uit = await speel(True, False, 4)
        check("uitgeschakeld: blijft staan", uit["na"]["hole"], 4)

        # Geen lege hole meer: blijven staan
        vol = await page.evaluate("""() => {
            localStorage.setItem('golf_auto_next', 'on');
            game.holes.forEach(h => { if (h.score === null) { h.score = 5; h.putts = 2; } });
            game.holes[5].score = null; delete game.holes[5].putts;
            setCurrentHole(7); selectHole(7); renderScore();
            toggleScoreButtons(7);
            const alHad = game.holes[7].score;
            toggleScoreButtons(7);
            return { hole: currentHole, alHad };
        }""")
        check("geen lege hole ná deze: blijft staan", vol["hole"], 7)

        # Een lege hole VÓÓR de huidige wordt niet gepakt: de app kijkt vooruit
        vooruit = await page.evaluate("""() => {
            game.holes[8].score = null; delete game.holes[8].putts;
            setCurrentHole(6); selectHole(6);
            game.holes[6].score = null; renderScore();
            toggleScoreButtons(6);
            stepScore(6, +1);
            toggleScoreButtons(6);
            return currentHole;
        }""")
        check("kijkt vooruit, niet terug", vooruit, 8)

        print("\n=== ALLE MANIEREN OM HET PANEEL TE SLUITEN ===\n")
        # Dit gaat via ECHTE tikken op het scherm. De losse functies aanroepen dekt niet
        # alles af: het sluiten loopt onder meer via een klikafhandelaar op het document,
        # en juist daar zat een tik te verdwijnen.
        async def via_tikken(manier, putts_aan):
            await page.evaluate("""([ronde, puttsAan]) => {
                localStorage.setItem('golf_rounds', JSON.stringify([ronde]));
                localStorage.setItem('golf_track_putts', puttsAan ? 'on' : 'off');
                localStorage.setItem('golf_auto_next', 'on');
                localStorage.setItem('golf_kenmerk_gevraagd', '1');
            }""", [RONDE, putts_aan])
            await page.reload()
            await page.wait_for_timeout(500)
            await page.evaluate("() => nav('score')")
            await page.wait_for_timeout(300)
            # hole 1 openen en een score zetten met de +knop
            rij = (await page.query_selector_all('.sum-tr'))[0]
            await (await rij.query_selector('.score-val')).click()
            await page.wait_for_timeout(150)
            await page.evaluate("""() => {
                const c = document.querySelectorAll('.sum-tr')[0].querySelector('.plus-cell');
                c.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                c.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
            }""")
            await page.wait_for_timeout(250)
            if manier == 'nogmaals op de score':
                r = (await page.query_selector_all('.sum-tr'))[0]
                await (await r.query_selector('.score-val')).click()
            elif manier == 'op de rij zelf':
                await page.evaluate("() => document.querySelectorAll('.sum-tr')[0].click()")
            elif manier == 'buiten de rijen':
                await page.evaluate("""() => {
                    const doel = document.getElementById('sumRows').parentElement;
                    doel.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                }""")
            elif manier == 'op de puttregel':
                await page.evaluate("() => document.getElementById('puttOverlay')?.click()")
            elif manier == 'de volgende hole aantikken':
                await page.evaluate("() => document.querySelectorAll('.sum-tr')[1].click()")
            await page.wait_for_timeout(300)
            return await page.evaluate("() => currentHole")

        for manier in ['nogmaals op de score', 'op de rij zelf', 'buiten de rijen',
                       'op de puttregel', 'de volgende hole aantikken']:
            check(f"putts aan · {manier}", await via_tikken(manier, True), 1)
        for manier in ['nogmaals op de score', 'op de rij zelf', 'buiten de rijen',
                       'de volgende hole aantikken']:
            check(f"putts uit · {manier}", await via_tikken(manier, False), 1)

        print("\n=== HET SCOREVAK: ÉÉN TIK, ÉÉN BETEKENIS ===\n")
        # Op het scorevak zat een lange druk (score wissen) met een venster van twee
        # seconden om die terug te nemen. Dat mechanisme leverde vier fouten op: een tik
        # die bevestigde in plaats van te sluiten, een wissing die terugdraaide bij
        # doortikken, een lange druk op een lege hole die de tik opsnoepte, en een
        # losdruk die op een telefoon werd afgebroken. Het is eruit: aantikken opent of
        # sluit het paneel, en verder niets. Wissen gaat via de min-knop.
        async def tikOpScoreVak(ms=60, afgebroken=False):
            await page.evaluate("""() => {
                const el = document.querySelector('.sum-tr.current-row .score-val');
                el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                window.__scoreEl = el;
            }""")
            await page.wait_for_timeout(ms)
            await page.evaluate("""(afgebroken) => {
                const el = window.__scoreEl;
                el.dispatchEvent(new PointerEvent(
                    afgebroken ? 'pointercancel' : 'pointerup', { bubbles: true }));
                el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            }""", afgebroken)
            await page.wait_for_timeout(250)

        async def legeHole():
            await page.evaluate("""() => {
                game.holes.forEach(h => { h.score = null; h.putts = null; });
                clearScoreTap(true); scoreButtonsRow = null;
                setCurrentHole(0); renderScore();
            }""")

        for ms, afgebroken, wat in [(60, False, 'korte tik'),
                                    (700, False, 'lang ingedrukt'),
                                    (60, True, 'tik met een afgebroken losdruk')]:
            await legeHole()
            await tikOpScoreVak(ms, afgebroken)
            check(f"lege hole, {wat}: het paneel gaat open",
                  await page.evaluate("() => scoreButtonsRow"), 0)

        # Ook op een ingevulde score verandert een lange druk niets meer.
        await page.evaluate("""() => {
            game.holes.forEach(h => { h.score = null; h.putts = null; });
            clearScoreTap(true); scoreButtonsRow = null;
            setCurrentHole(0); game.holes[0].score = 5; renderScore();
        }""")
        await tikOpScoreVak(700)
        check("ingevulde score blijft staan bij een lange druk",
              await page.evaluate("() => game.holes[0].score"), 5)
        check("en het paneel gaat gewoon open",
              await page.evaluate("() => scoreButtonsRow"), 0)

        # Nog een tik sluit het weer.
        await tikOpScoreVak()
        check("nog een tik sluit het paneel",
              await page.evaluate("() => scoreButtonsRow"), None)

        # Wissen kan met de min-knop: op nul wordt de score leeg.
        wissen = await page.evaluate("""() => {
            game.holes[0].score = 1;
            scoreButtonsRow = 0;
            renderScore();
            const min = [...document.querySelectorAll('.sum-tr.current-row button')]
                .find(b => b.textContent.trim() === '\u2212');
            min.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
            min.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
            return game.holes[0].score;
        }""")
        check("de min-knop wist de score", wissen, None)

        print("\n=== BIJ 18 HOLES WISSELT HET TABBLAD MEE ===\n")
        # De twee negens staan op een eigen tabblad. Sprong de app van hole 9 naar 10,
        # dan bleef het tabblad op '1...9' staan: je stond op een hole die je niet zag,
        # met negen ingevulde rijen voor je neus.
        # Het meewisselen zit bij het wisselen van HOLE, dus het geldt voor elke weg
        # daarheen: automatisch doorspringen, zelf een hole aantikken, of hervatten.
        await page.evaluate("""() => {
            // Een ronde van 18 holes opzetten in de lopende partij.
            const basis = game.holes[0];
            game.holes = Array.from({ length: 18 }, (_, i) => ({
                ...basis, id: i + 1, si: i + 1, score: null, putts: null,
            }));
            clearScoreTap(true);
            scoreButtonsRow = null;
            selectNine(0);
            setCurrentHole(0);
            renderScore();
        }""")
        await page.wait_for_timeout(200)

        async def vulHole(h):
            await page.evaluate("""(h) => {
                setCurrentHole(h);
                selectHole(h);
                toggleScoreButtons(h);
                stepScore(h, +1);
                toggleScoreButtons(h);
            }""", h)
            await page.wait_for_timeout(120)

        STAND = """() => ({
            hole: currentHole + 1,
            tab: currentNine,
            rijZichtbaar: !!document.querySelector('.sum-tr.current-row'),
        })"""

        for h in range(8):
            await vulHole(h)
        voor = await page.evaluate(STAND)
        check("na hole 8 sta je op hole 9, eerste tabblad",
              [voor["hole"], voor["tab"]], [9, 0])

        await vulHole(8)
        na = await page.evaluate(STAND)
        check("na hole 9 spring je naar hole 10", na["hole"], 10)
        check("en het tabblad gaat mee", na["tab"], 1)
        check("dus je ziet waar je staat", na["rijZichtbaar"], True)

        # Zelf een hole op de andere negen aantikken doet hetzelfde — ook als het
        # automatisch doorspringen uitstaat.
        await page.evaluate("""() => {
            storage.setItem('golf_auto_next', 'off');
            selectNine(0);
            selectHole(13);
        }""")
        await page.wait_for_timeout(200)
        aangetikt = await page.evaluate(STAND)
        check("zelf hole 14 aantikken brengt je naar het tweede tabblad",
              [aangetikt["hole"], aangetikt["tab"]], [14, 1])
        check("en je ziet die hole", aangetikt["rijZichtbaar"], True)
        await page.evaluate("() => storage.setItem('golf_auto_next', 'on')")

        # Blader je zelf terug om iets na te kijken, dan hoort de app je met rust te laten.
        await page.evaluate("() => selectNine(0)")
        await page.wait_for_timeout(200)
        gebladerd = await page.evaluate(STAND)
        check("zelf bladeren wordt niet teruggedraaid", gebladerd["tab"], 0)
        check("en je huidige hole verandert niet", gebladerd["hole"], 14)

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
