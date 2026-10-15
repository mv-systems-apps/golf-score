"""De notitie van een lopende ronde overleeft het afsluiten van de app.

De notitie werd bij het STARTEN netjes opgeslagen, maar ging verloren zodra de app uit het
geheugen was geweest. Bij het herstellen van de lopende ronde wordt die veld voor veld
opnieuw opgebouwd, en 'note' stond niet in dat rijtje. De eerstvolgende score schreef de
ronde dan opnieuw weg — zonder notitie.

Dat trof elke ronde die je niet in één sessie uitspeelde: je telefoon even wegleggen is
genoeg, want het toestel ruimt apps uit het geheugen.
"""
import asyncio, json, os, sys
from datetime import date
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, speler, note):
    return {
        "id": rid, "date": date.today().isoformat(), "time": "09:%02d" % rid,
        "player": speler, "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC",
        "track": "Airborne", "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141,
        "PAR": 36, "chcp": 11, "qualifying": True, "note": note,
        "total": 10, "totalStb": 4, "playedCount": 2, "holesCount": 9, "currentHole": 2,
        "started": True, "sd": None, "sdFinal": None, "pcc": 0,
        # Twee holes ingevuld: een halverwege onderbroken ronde.
        "holes": [{"id": i + 1, "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": (5 if i < 2 else None)} for i in range(9)],
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
        paginafouten = []

        async def opzet(rondes, tweedeSpeler=False):
            page = await browser.new_page(viewport={"width": 390, "height": 900})
            page.on('pageerror', lambda e: paginafouten.append(str(e)))
            await page.goto(app_url())
            await page.evaluate("""([clubs, rs, twee]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rs));
                localStorage.setItem('golf_active_id', '1');
                if (twee) localStorage.setItem('golf_game2_id', '2');
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            }""", [CLUBS, rondes, tweedeSpeler])
            # Opnieuw laden = de app opnieuw openen nadat hij uit het geheugen is gehaald.
            await page.goto(app_url())
            await page.wait_for_timeout(1200)
            return page

        print("=== ÉÉN SPELER ===\n")
        page = await opzet([ronde(1, 'Mark', 'Wedstrijd 85%')])
        check("de notitie komt mee in de herstelde ronde",
              await page.evaluate("() => game.note"), 'Wedstrijd 85%')

        # Een score invullen schrijft de ronde opnieuw weg. Dáár ging het mis.
        await page.evaluate("""() => {
            nav('score');
            setCurrentHole(2);
            selectHole(2);
            toggleScoreButtons(2);
            stepScore(2, +1);
            toggleScoreButtons(2);
        }""")
        await page.wait_for_timeout(500)
        check("en staat er na het invullen van een hole nog",
              await page.evaluate("() => loadSavedRounds()[0].note"), 'Wedstrijd 85%')
        check("de score is ook bewaard",
              await page.evaluate(
                  "() => loadSavedRounds()[0].holes.filter(h => h.score !== null).length"), 3)
        await page.close()

        print("\n=== TWEE SPELERS ===\n")
        page = await opzet([ronde(1, 'Mark', 'Wedstrijd 85%'),
                            ronde(2, 'Partner', 'Maat notitie')], tweedeSpeler=True)
        await page.evaluate("""() => {
            nav('score');
            setCurrentHole(2);
            selectHole(2);
            toggleScoreButtons(2);
            stepScore(2, +1);
            toggleScoreButtons(2);
        }""")
        await page.wait_for_timeout(500)
        check("beide notities staan er nog",
              await page.evaluate("""() => loadSavedRounds()
                  .map(x => x.player + ': ' + (x.note || '(weg)')).sort()"""),
              ['Mark: Wedstrijd 85%', 'Partner: Maat notitie'])

        # Ook scoren op de kaart van je medespeler mag niets wissen.
        await page.evaluate("""() => {
            if (typeof switchPlayer === 'function') switchPlayer(2);
            setCurrentHole(3);
            selectHole(3);
            toggleScoreButtons(3);
            stepScore(3, +1);
            toggleScoreButtons(3);
        }""")
        await page.wait_for_timeout(500)
        check("ook na scoren bij de maat",
              await page.evaluate("""() => loadSavedRounds()
                  .map(x => x.player + ': ' + (x.note || '(weg)')).sort()"""),
              ['Mark: Wedstrijd 85%', 'Partner: Maat notitie'])
        await page.close()

        print("\n=== EEN RONDE ZONDER NOTITIE ===\n")
        # Geen lege notitie aanmaken waar er geen was.
        page = await opzet([ronde(1, 'Mark', '')])
        await page.evaluate("""() => {
            nav('score');
            setCurrentHole(2);
            selectHole(2);
            toggleScoreButtons(2);
            stepScore(2, +1);
            toggleScoreButtons(2);
        }""")
        await page.wait_for_timeout(500)
        check("blijft zonder notitie",
              await page.evaluate("() => loadSavedRounds()[0].note ?? null"), None)
        await page.close()

        print("\n=== VASTSTELLEN WIST DE NOTITIE NIET ===\n")
        # Het venster Vaststellen leest bij opslaan het notitieveld uit, en een leeg veld
        # betekent 'geen notitie'. Het vulde dat veld alleen niet met de bestaande
        # notitie — PCC en dagresultaat wél. Elk bezoek wiste je notitie dus stilletjes.
        page = await opzet([ronde(1, 'Mark', 'Wedstrijd 85%')])
        veld = await page.evaluate("""() => {
            nav('archive');
            loadSaved();
            openRoundResultModal(0);
            return document.getElementById('resultNoteInput').value;
        }""")
        await page.wait_for_timeout(400)
        veld = await page.evaluate("() => document.getElementById('resultNoteInput').value")
        check("het venster toont de bestaande notitie", veld, 'Wedstrijd 85%')

        await page.evaluate("""() => {
            document.getElementById('editSdInput').value = '29.4';
            confirmRoundResult();
        }""")
        await page.wait_for_timeout(500)
        check("en na opslaan staat hij er nog",
              await page.evaluate("() => loadSavedRounds()[0].note"), 'Wedstrijd 85%')
        check("het dagresultaat is wel opgeslagen",
              await page.evaluate("() => loadSavedRounds()[0].sdFinal"), 29.4)

        # Wis je de notitie zelf in dat veld, dan hoort hij ook echt weg te gaan.
        await page.evaluate("""() => {
            openRoundResultModal(0);
        }""")
        await page.wait_for_timeout(400)
        await page.evaluate("""() => {
            document.getElementById('resultNoteInput').value = '';
            confirmRoundResult();
        }""")
        await page.wait_for_timeout(500)
        check("zelf leegmaken wist hem wel",
              await page.evaluate("() => loadSavedRounds()[0].note ?? null"), None)
        await page.close()

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
