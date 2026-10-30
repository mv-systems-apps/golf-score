"""De Low HI geldt PER RONDE, niet één keer voor je hele geschiedenis.

Op elke rondekaart staat wat je handicap deed: 'Whs 31.7 → 35.6'. Die berekening kreeg
steeds dezelfde Low HI mee — die van VANDAAG. Bij een eerste ronde van jaren terug
leverde dat een hardcap op tegen een getal dat toen nog niet bestond: de app remde een
ronde uit het verleden af met je laagste handicap van nu.

De grafiek deed het al goed (Low HI per punt, uit de rondes tot dat moment binnen 365
dagen); deze lijst niet. Daardoor spraken de twee elkaar tegen.

Gemeten met een echte backup: de eerste ronde kreeg 35.6 met hardcap, terwijl 38.3 klopt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url

with open(os.path.join(HIER, 'rondes-lowhi.json'), encoding='utf-8') as f:
    RONDES = json.load(f)

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
        page = await browser.new_page(viewport={"width": 390, "height": 1200})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_profile_name', 'Testspeler');
        }""", [CLUBS, RONDES])
        await page.goto(app_url())
        await page.wait_for_timeout(1500)

        verloop = await page.evaluate("""() => {
            const t = handicapTabellen();
            const l = loadSavedRounds().filter(r => r.qualifying)
                .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
            return l.slice(0, 4).map(r => {
                const x = t.hcpTrendMap[r.id] || {};
                return { datum: r.date, oud: x.oldHcp, nieuw: x.newHcp, cap: x.capType };
            });
        }""")

        eerste = verloop[0]
        check("de eerste ronde is die van 20-9-2025", eerste["datum"], '2025-09-20')
        # Bij je eerste ronde bestaat er nog geen Low HI om tegen af te remmen.
        check("er staat geen cap op", eerste["cap"], None)
        check("en de handicap is de onafgeremde waarde", eerste["nieuw"], 38.3)

        check("de rondes erna zijn ongemoeid",
              [(r["datum"], r["nieuw"], r["cap"]) for r in verloop[1:]],
              [('2025-11-30', 31.1, None), ('2025-12-02', 30.9, None),
               ('2025-12-08', 31.9, None)])

        # Het gaat om de weergave van het verleden; de stand van nu mag niet schuiven.
        huidig = await page.evaluate("""() => {
            nav('setup');
            updateComputedHcp();
            return document.getElementById('computedHcpVal').textContent.trim();
        }""")
        check("de huidige handicap verandert niet", huidig, '30.8')

        # De grafiek rekende al per ronde; beide horen nu hetzelfde te zeggen.
        grafiek = await page.evaluate("""() => {
            nav('stat');
            storage.setItem('golf_sd_period', 'alles');
            renderPlayerStats();
            const t = document.getElementById('screen-stat').innerText;
            return t.includes('Hardcap');
        }""")
        check("de grafiek toont wel de legenda", grafiek, True)

        print("\n=== EEN HANDMATIGE LOW HI BLIJFT VAST ===\n")
        # Die stel je zelf in; dan geldt hij voor alles, ook met terugwerkende kracht.
        metHand = await page.evaluate("""() => {
            storage.setItem('golf_low_hi', '30.0');
            const t = handicapTabellen();
            const l = loadSavedRounds().filter(r => r.qualifying)
                .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
            const x = t.hcpTrendMap[l[0].id] || {};
            storage.removeItem('golf_low_hi');
            return { nieuw: x.newHcp, cap: x.capType };
        }""")
        check("dan wordt de eerste ronde wél afgeremd", metHand["cap"], 'hard')
        check("op Low HI plus vijf", metHand["nieuw"], 35.0)

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
