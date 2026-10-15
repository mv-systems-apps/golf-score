"""Een ACTIEVE ronde corrigeren: geen valse waarschuwing, en niets raakt kwijt.

Bij het starten waarschuwt de app als er al een ronde loopt: die wordt dan opgeslagen.
Corrigeer je juist díé ronde, dan klopt dat niet — hij wordt niet náást de nieuwe
opgeslagen maar erdoor vervangen. De melding beloofde iets wat niet gebeurt en vroeg om
een keuze die er niet is.

Loopt er een ÁNDERE ronde, dan blijft de melding staan: die wordt wél opgeslagen.

Deze test loopt alle scenario's met één en twee spelers langs en controleert bij elk:
komt de melding (wel of niet), hoeveel rondes blijven er over, en gaan de scores mee.
"""
import asyncio, json, os, sys
from datetime import date, timedelta
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, speler, dagenTerug, scores=True, tijd="09:00"):
    d = date.today() - timedelta(days=dagenTerug)
    return {
        "id": rid, "date": d.isoformat(), "time": tijd, "player": speler, "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36, "chcp": 11,
        "qualifying": True, "note": "", "total": 45, "totalStb": 18,
        "playedCount": 9 if scores else 0, "holesCount": 9, "currentHole": 0,
        "started": scores, "sd": None, "sdFinal": None, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5 if scores else None} for i in range(9)],
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

        async def scenario(rondes, actiefId, game2Id, corrigeerId, metScores=True):
            """Zet de app op, corrigeer een ronde en start hem. Geeft terug wat er
            gebeurde: de melding (of None), en de stand daarna."""
            page = await browser.new_page(viewport={"width": 390, "height": 900})
            page.on('pageerror', lambda e: paginafouten.append(str(e)))
            await page.goto(app_url())
            await page.evaluate("""([clubs, rs, a, g2]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rs));
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
                localStorage.setItem('golf_profile_name', 'Mark');
                if (a != null) localStorage.setItem('golf_active_id', String(a));
                if (g2 != null) localStorage.setItem('golf_game2_id', String(g2));
            }""", [CLUBS, rondes, actiefId, game2Id])
            await page.goto(app_url())
            await page.wait_for_timeout(1000)

            await page.evaluate("""([id, ms]) => {
                nav('archive');
                loadSaved();
                herplanRonde(id, ms);
            }""", [corrigeerId, metScores])
            await page.wait_for_timeout(300)

            eerst = await page.evaluate("""() => {
                startRound();
                const m = document.getElementById('confirmModal');
                return (m && !m.classList.contains('hidden'))
                    ? document.getElementById('confirmModalTitle').textContent : null;
            }""")
            if eerst:
                await page.evaluate("() => document.getElementById('confirmModalBtn').click()")
            await page.wait_for_timeout(500)

            stand = await page.evaluate("""() => {
                const l = loadSavedRounds();
                return {
                    aantal: l.length,
                    actief: localStorage.getItem('golf_active_id'),
                    // Speler plus het aantal ingevulde holes: zo zie je of scores meegingen.
                    spelers: l.map(x => x.player + ':' +
                        x.holes.filter(h => h.score !== null).length).sort(),
                };
            }""")
            await page.close()
            return eerst, stand

        print("=== ÉÉN SPELER ===\n")

        melding, stand = await scenario([ronde(1, 'Mark', 0)], 1, None, 1)
        check("actieve ronde corrigeren: geen melding", melding, None)
        check("er blijft één ronde over", stand["aantal"], 1)
        check("met alle scores", stand["spelers"], ['Mark:9'])
        check("en die is weer de actieve", stand["actief"] is not None, True)

        melding, stand = await scenario([ronde(1, 'Mark', 3)], None, None, 1)
        check("niet-actieve ronde corrigeren: geen melding", melding, None)
        check("er blijft één ronde over", stand["aantal"], 1)

        # Hier hoort de melding WEL: die andere ronde wordt echt opgeslagen.
        melding, stand = await scenario(
            [ronde(1, 'Mark', 3), ronde(2, 'Mark', 0, tijd='14:00')], 2, None, 1)
        check("met een ANDERE ronde actief: wel een melding",
              melding, 'Actieve ronde aanwezig')
        check("en beide rondes blijven bestaan", stand["aantal"], 2)

        melding, stand = await scenario(
            [ronde(1, 'Mark', -5, scores=False)], None, None, 1, metScores=False)
        check("geplande ronde herplannen: geen melding", melding, None)
        check("er blijft één ronde over", stand["aantal"], 1)
        check("nog zonder scores", stand["spelers"], ['Mark:0'])

        print("\n=== TWEE SPELERS ===\n")
        duo = [ronde(1, 'Mark', 0), ronde(2, 'Partner', 0)]

        melding, stand = await scenario(duo, 1, 2, 1)
        check("beide actief, via je eigen kaart: geen melding", melding, None)
        check("beide rondes blijven", stand["aantal"], 2)
        check("met beider scores", stand["spelers"], ['Mark:9', 'Partner:9'])

        # Tik je op de kaart van je medespeler, dan hoort hetzelfde te gebeuren.
        melding, stand = await scenario(duo, 1, 2, 2)
        check("beide actief, via de kaart van de maat: geen melding", melding, None)
        check("beide rondes blijven", stand["aantal"], 2)
        check("met beider scores", stand["spelers"], ['Mark:9', 'Partner:9'])

        melding, stand = await scenario(duo, 1, None, 1)
        check("alleen speler 1 actief: geen melding", melding, None)
        check("beide rondes blijven", stand["aantal"], 2)

        # Een derde ronde die er los van staat is wél iets om te melden.
        drie = [ronde(1, 'Mark', 3), ronde(2, 'Partner', 3),
                ronde(3, 'Mark', 0, tijd='15:00')]
        melding, stand = await scenario(drie, 3, None, 1)
        check("duo corrigeren met een derde ronde actief: wel een melding",
              melding, 'Actieve ronde aanwezig')
        check("alle drie de rondes blijven bestaan", stand["aantal"], 3)

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
