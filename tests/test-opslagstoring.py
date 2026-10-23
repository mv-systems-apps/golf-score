"""Wat gebeurt er als de opslag halverwege een ronde weigert.

De browser geeft een app ongeveer 5 MB, en die ruimte wordt gedeeld met alles wat je in
diezelfde browser bezoekt. Een andere site kan hem opvullen, en dan kan deze app ineens
niets meer wegschrijven — zonder dat jij iets deed.

Wat er dan moet gebeuren:
  * je scores blijven in beeld en gaan niet verloren;
  * al opgeslagen holes blijven staan;
  * er staat een waarschuwing IN BEELD zolang de storing duurt — niet een paar seconden,
    want dan speel je verder in de veronderstelling dat alles bewaard wordt;
  * en zodra het weer lukt, wordt alsnog alles weggeschreven.

Die waarschuwing hangt aan de sleutel die faalde. De app schrijft voortdurend andere
sleutels weg en die slagen wél; zouden die de melding wissen, dan was hij meteen weer weg
terwijl je rondes nog steeds niet worden opgeslagen.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url

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
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(800)

        # Ronde starten en twee holes invullen terwijl alles nog werkt.
        await page.evaluate("""() => {
            nav('setup');
            sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.qualifying = true;
            document.getElementById('iName').value = 'Testspeler';
            document.getElementById('iHcp').value = '30.7';
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            nav('score');
            for (let h = 0; h < 2; h++) {
                setCurrentHole(h); selectHole(h);
                armScoreChange(h, 5); clearScoreTap(false);
            }
        }""")
        await page.wait_for_timeout(400)

        melding = lambda: page.evaluate(
            "() => !!document.getElementById('opslagStoringMelding')")

        print("=== NORMAAL ===\n")
        check("geen waarschuwing als alles werkt", await melding(), False)
        check("twee holes opgeslagen", await page.evaluate(
            "() => loadSavedRounds()[0].holes.filter(h => h.score !== null).length"), 2)

        print("\n=== TIJDENS EEN STORING ===\n")
        # Alleen het wegschrijven van de RONDES weigeren; al het andere blijft werken.
        await page.evaluate("""() => {
            window.__echteSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function (k, v) {
                if (k === 'golf_rounds') {
                    const e = new Error('QuotaExceededError');
                    e.name = 'QuotaExceededError';
                    throw e;
                }
                return window.__echteSetItem.call(this, k, v);
            };
            setCurrentHole(2); selectHole(2);
            armScoreChange(2, 5); clearScoreTap(false);
        }""")
        await page.wait_for_timeout(250)
        check("de waarschuwing staat in beeld", await melding(), True)

        # Doorspelen en van scherm wisselen: dat schrijft andere sleutels weg, die wél
        # slagen. De waarschuwing hoort te blijven staan.
        await page.evaluate("""() => {
            for (let h = 3; h < 6; h++) {
                setCurrentHole(h); selectHole(h);
                armScoreChange(h, 5); clearScoreTap(false);
            }
            nav('archive'); nav('score');
        }""")
        await page.wait_for_timeout(2500)
        check("en blijft staan zolang de storing duurt", await melding(), True)

        tijdens = await page.evaluate("""() => ({
            inBeeld: game.holes.filter(h => h.score !== null).length,
            opgeslagen: loadSavedRounds()[0].holes.filter(h => h.score !== null).length,
        })""")
        check("de scores staan gewoon in beeld", tijdens["inBeeld"], 6)
        check("maar zijn niet opgeslagen", tijdens["opgeslagen"], 2)

        print("\n=== NA HERSTEL ===\n")
        await page.evaluate("""() => {
            Storage.prototype.setItem = window.__echteSetItem;
            setCurrentHole(6); selectHole(6);
            armScoreChange(6, 5); clearScoreTap(false);
        }""")
        await page.wait_for_timeout(400)
        check("de waarschuwing verdwijnt", await melding(), False)
        check("en alles is alsnog opgeslagen", await page.evaluate(
            "() => loadSavedRounds()[0].holes.filter(h => h.score !== null).length"), 7)

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
