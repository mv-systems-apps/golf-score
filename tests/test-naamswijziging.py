"""Een naamswijziging raakt je handicap — en dat gebeurde stil.

De app groepeert alles op de naam in het startveld: je laatste 20, je gemiddelden en je
Low HI. Twee dingen gingen daar ongemerkt mis:

  * HERNOEMEN ("Testspeler" -> "Testspeler V"): je oude rondes bleven op de oude naam staan en
    telden ineens niet meer mee. Gemeten: van 20 meetellende rondes naar nul, Low HI weg,
    en het statistiekenscherm meldde "Geen afgeronde qualifying rondes".
  * BOTSEN: nam je een naam die al bij iemand anders in je archief stond, dan gingen
    diens rondes meetellen in JOUW handicap. Gemeten: Low HI 9 in plaats van 28.

Nu volgt bij allebei een venster met een keuze. De botsing gaat vóór: dat is het
ernstigste geval, ook als er tegelijk rondes op de oude naam staan.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, datum, speler, sd=30.0):
    return {
        "id": rid, "date": datum, "time": "09:%02d" % (rid % 60), "player": speler,
        "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36, "chcp": 11,
        "qualifying": True, "note": "", "total": 45, "totalStb": 18, "playedCount": 9,
        "holesCount": 9, "currentHole": 0, "started": True, "sd": sd, "sdFinal": sd,
        "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }

EIGEN = [ronde(i, '2026-%02d-%02d' % ((i % 12) + 1, (i % 28) + 1), 'Testspeler')
         for i in range(1, 26)]

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

        async def opzetten(rondes):
            await page.goto(app_url())
            await page.evaluate("""([clubs, rs]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rs));
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
                localStorage.setItem('golf_profile_name', 'Testspeler');
                localStorage.setItem('golf_kenmerk_gevraagd', '1');
            }""", [CLUBS, rondes])
            await page.reload()
            await page.wait_for_timeout(700)

        async def wijzigNaam(naar):
            return await page.evaluate("""(naar) => {
                nav('setup');
                const el = document.getElementById('iName');
                el.dataset.vorigeNaam = el.value.trim();
                el.value = naar;
                controleerNaamswijziging(el);
                const m = document.getElementById('keuzeModal');
                return {
                    open: !m.classList.contains('hidden'),
                    titel: document.getElementById('keuzeModalTitel').textContent,
                    tekst: document.getElementById('keuzeModalTekst').textContent,
                    knoppen: ['keuzeModalKnop1', 'keuzeModalKnop2', 'keuzeModalKnop3']
                        .map(i => document.getElementById(i))
                        .filter(b => !b.classList.contains('hidden'))
                        .map(b => b.textContent),
                };
            }""", naar)

        print("=== HERNOEMEN ===\n")
        await opzetten(EIGEN)
        v = await wijzigNaam('Testspeler V')
        check("er komt een venster", v["open"], True)
        check("met de juiste titel", v["titel"], 'Naam gewijzigd')
        check("en drie keuzes", v["knoppen"],
              ['Alles aanpassen', 'Alleen nieuwe rondes', 'Annuleren'])
        check("de tekst noemt het aantal en beide namen",
              'Er staan 25 rondes op "Testspeler"' in v["tekst"] and 'Testspeler V' in v["tekst"], True)

        na = await page.evaluate("""() => {
            document.getElementById('keuzeModalKnop1').click();   // Alles aanpassen
            const l = loadSavedRounds();
            return { opNieuw: l.filter(r => r.player === 'Testspeler V').length,
                     opOud: l.filter(r => r.player === 'Testspeler').length,
                     meetellend: last20Qualifying('Testspeler V', l).length };
        }""")
        check("alle rondes zijn meegenomen", na["opNieuw"], 25)
        check("er staat niets meer op de oude naam", na["opOud"], 0)
        check("en ze tellen weer mee", na["meetellend"], 20)

        print("\n=== ALLEEN NIEUWE RONDES ===\n")
        await opzetten(EIGEN)
        await wijzigNaam('Testspeler V')
        na2 = await page.evaluate("""() => {
            document.getElementById('keuzeModalKnop2').click();
            const l = loadSavedRounds();
            return { opOud: l.filter(r => r.player === 'Testspeler').length,
                     naam: document.getElementById('iName').value };
        }""")
        check("de oude rondes blijven op de oude naam", na2["opOud"], 25)
        check("en je speelt verder onder de nieuwe", na2["naam"], 'Testspeler V')

        print("\n=== ANNULEREN ===\n")
        await opzetten(EIGEN)
        await wijzigNaam('Testspeler V')
        na3 = await page.evaluate("""() => {
            document.getElementById('keuzeModalKnop3').click();
            return { naam: document.getElementById('iName').value,
                     opslag: localStorage.getItem('golf_profile_name') };
        }""")
        check("de oude naam staat terug in het veld", na3["naam"], 'Testspeler')
        check("en ook in de opslag", na3["opslag"], 'Testspeler')

        print("\n=== BOTSING ===\n")
        gemengd = EIGEN[:20] + [
            ronde(100 + i, '2025-%02d-%02d' % ((i % 12) + 1, (i % 28) + 1), 'Partner', 10.0)
            for i in range(5)]
        await opzetten(gemengd)
        b = await wijzigNaam('Partner')
        check("de botsing wordt gemeld", b["titel"], 'Naam bestaat al')
        check("met de veilige keuze bovenaan", b["knoppen"], ['Annuleren', 'Toch gebruiken'])
        check("en het gevolg staat erbij",
              'meetellen in je handicap' in b["tekst"], True)
        check("annuleren zet de naam terug", await page.evaluate("""() => {
            document.getElementById('keuzeModalKnop1').click();
            return document.getElementById('iName').value;
        }"""), 'Testspeler')

        print("\n=== GEEN VENSTER ZONDER REDEN ===\n")
        await opzetten(EIGEN)
        zelfde = await wijzigNaam('Testspeler')
        check("dezelfde naam geeft geen venster", zelfde["open"], False)
        # Een naam die nergens voorkomt en waar niets op staat: ook geen venster.
        await opzetten([])
        leeg = await wijzigNaam('Iemand anders')
        check("zonder rondes ook niet", leeg["open"], False)

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
