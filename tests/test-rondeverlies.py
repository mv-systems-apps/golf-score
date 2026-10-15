"""Een ingevulde scorekaart mag nooit stilzwijgend verdwijnen.

Twee vangnetten worden hier bewaakt:

  1. Bij het wisselen naar speler 1 wordt de ronde van speler 2 alleen teruggeschreven
     als het spel in het geheugen ECHT die ronde is. Anders zou een andere geladen ronde
     eroverheen worden geschreven — inclusief het id, waardoor de kaart van de medespeler
     verdwijnt en er twee identieke rondes overblijven.
  2. Een spel zonder holes overschrijft nooit een opgeslagen ronde die ze wél heeft.
     Zo kan een half geladen of leeg spel geen volle scorekaart wissen.

Beide gaten zijn gevonden door de paden na te lopen waarlangs een ronde uit de opslag
verdwijnt; ze zijn hier vastgelegd zodat ze niet terug kunnen komen.
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


def ronde(rid, speler, gespeeld, datum="2026-08-26", tijd="09:00"):
    return {
        "id": rid, "date": datum, "time": tijd, "player": speler, "hcp": 30.7,
        "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren",
        "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
        "note": "", "total": 45, "totalStb": 18, "playedCount": gespeeld,
        "holesCount": 9, "currentHole": 0, "started": True,
        "sd": None, "sdFinal": None, "pcc": 0,
        "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": (5 if i < gespeeld else None)} for i in range(9)],
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

        async def opzetten(rondes, actief, tweede=None):
            await page.evaluate("""([clubs, rs, actief, tweede]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rs));
                localStorage.setItem('golf_active_id', String(actief));
                if (tweede) localStorage.setItem('golf_game2_id', String(tweede));
                localStorage.setItem('golf_default_club', 'Testclub');
                localStorage.setItem('golf_profile_name', 'Mark');
            }""", [CLUBS, rondes, actief, tweede])
            await page.reload()
            await page.wait_for_timeout(500)

        async def kaarten():
            return await page.evaluate("""() => loadSavedRounds().map(r =>
                [r.id, r.player, (r.holes || []).filter(h => h.score !== null).length])""")

        print("=== SPELERWISSEL MET EEN VERKEERDE STAND ===\n")
        await opzetten([ronde(201, 'Mark', 9), ronde(202, 'Partner', 9)], 201, 202)
        check("beide kaarten staan er", await kaarten(),
              [[201, 'Mark', 9], [202, 'Partner', 9]])

        # Normale route: heen en weer wisselen verandert niets
        await page.evaluate("() => switchToPlayer(2)")
        await page.wait_for_timeout(150)
        await page.evaluate("() => switchToPlayer(1)")
        await page.wait_for_timeout(150)
        check("gewoon wisselen laat beide kaarten heel", await kaarten(),
              [[201, 'Mark', 9], [202, 'Partner', 9]])

        # De gevaarlijke stand: de app denkt dat speler 2 actief is, maar in het geheugen
        # staat de ronde van speler 1. Vroeger werd die dan over speler 2 heen geschreven.
        await page.evaluate("""() => {
            activePlayer = 2;
            gameFromRound(loadSavedRounds().find(r => r.id === 201));
        }""")
        await page.evaluate("() => switchToPlayer(1)")
        await page.wait_for_timeout(200)
        check("kaart van de medespeler blijft staan", await kaarten(),
              [[201, 'Mark', 9], [202, 'Partner', 9]])

        print("\n=== LEEG SPEL OVERSCHRIJFT NIETS ===\n")
        await opzetten([ronde(301, 'Mark', 9)], 301)
        await page.evaluate("""() => {
            game = { started: true, id: 301, holes: [], track: 'Baan' };
            saveActiveRound();
        }""")
        await page.wait_for_timeout(150)
        check("volle kaart overleeft een leeg spel", await kaarten(), [[301, 'Mark', 9]])

        # En het normale geval blijft gewoon werken: scores bijwerken moet wél opslaan
        await opzetten([ronde(401, 'Mark', 4)], 401)
        await page.evaluate("""() => {
            game.holes[4].score = 5;
            saveActiveRound();
        }""")
        await page.wait_for_timeout(150)
        check("een extra score wordt wél opgeslagen", await kaarten(), [[401, 'Mark', 5]])

        # Scores wissen mag ook: dan blijven de holes bestaan, alleen zonder score
        await page.evaluate("""() => {
            game.holes.forEach(h => { h.score = null; });
            saveActiveRound();
        }""")
        await page.wait_for_timeout(150)
        check("zelf leegmaken mag wel", await kaarten(), [[401, 'Mark', 0]])

        print("\n=== SNOEIEN OP HET MAXIMUM ===\n")
        # Het maximum is een VASTE waarde (2500), geen instelling: een instelling nodigt
        # uit hem te verlagen, en dat is precies de handeling die gegevens kost.
        check("het maximum is vast", await page.evaluate("() => getRoundStorageLimit()"), 2500)

        # De opslag staat NIET op datum gesorteerd: importeren zet rondes achter de
        # actieve ronde, en een datum wijzigen verplaatst niets. Wie dan de staart van de
        # lijst afknipt, gooit soms juist de nieuwste ronde weg. Er wordt op DATUM
        # gesnoeid. Hier met een tijdelijk verlaagd maximum, anders zou de test 2500
        # rondes moeten aanmaken.
        veel = [ronde(500 + i, 'Mark', 9, '2026-%02d-%02d' % ((i % 8) + 1, (i % 9) + 1))
                for i in range(25)]
        veel[0]['date'] = '2005-01-01'      # heel oude ronde, staat vooraan
        veel[-1]['date'] = '2026-08-26'     # de nieuwste kaart, staat achteraan
        await opzetten(veel, 500)
        na = await page.evaluate("""() => {
            const echt = getRoundStorageLimit;
            getRoundStorageLimit = () => 20;
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(trimRondes(loadSavedRounds()))));
            getRoundStorageLimit = echt;
            return loadSavedRounds().map(r => r.date);
        }""")
        check("teruggesnoeid tot het maximum", len(na), 20)
        check("de nieuwste kaart blijft staan", '2026-08-26' in na, True)
        check("de oudste is weg", '2005-01-01' in na, False)

        # Onder het maximum verandert er niets.
        onder = await page.evaluate("""() => {
            const voor = loadSavedRounds().length;
            const na = trimRondes(loadSavedRounds()).length;
            return { voor, na };
        }""")
        check("onder het maximum wordt niets weggegooid", onder["na"], onder["voor"])

        print("\n=== DE REM OP ONBEDOELD VERLIES ===\n")
        # Elke schrijfactie die een INGEVULDE ronde zou laten verdwijnen zonder dat het
        # als bewuste verwijdering is gemarkeerd, hoort geweigerd te worden. Liever een
        # mislukte opslag dan een scorekaart die weg is.
        await opzetten([ronde(601, 'Mark', 9, '2026-08-26'),
                        ronde(602, 'Mark', 0, '2026-08-27', '11:00')], 601)
        geweigerd = await page.evaluate("""() => {
            const zonder601 = loadSavedRounds().filter(r => r.id !== 601);
            const uitkomst = setRoundsAndMark(JSON.stringify(zonder601));
            return { uitkomst, nog: loadSavedRounds().map(r => r.id) };
        }""")
        check("de opslag weigert", geweigerd["uitkomst"], False)
        check("de ingevulde ronde staat er nog", 601 in geweigerd["nog"], True)

        # Een LEGE ronde weghalen mag wel zonder markering: daar gaat niets verloren.
        leeg = await page.evaluate("""() => {
            const zonder602 = loadSavedRounds().filter(r => r.id !== 602);
            const uitkomst = setRoundsAndMark(JSON.stringify(zonder602));
            return { uitkomst, nog: loadSavedRounds().map(r => r.id) };
        }""")
        check("een lege ronde mag gewoon weg", leeg["uitkomst"], True)
        check("alleen de lege is verdwenen", leeg["nog"], [601])

        # En als het wél de bedoeling is, gebeurt het gewoon.
        bewust = await page.evaluate("""() => {
            const leeg = [];
            const uitkomst = metVerwijderen(() => setRoundsAndMark(JSON.stringify(leeg)));
            return { uitkomst, nog: loadSavedRounds().length };
        }""")
        check("bewust verwijderen lukt wel", bewust["uitkomst"], True)
        check("archief is leeg", bewust["nog"], 0)

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
