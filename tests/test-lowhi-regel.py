"""De Low HI-regel onder de grafiek is aanklikbaar, net als de regel van het aangewezen punt.

Beide regels wijzen een concrete ronde aan. Bij de regel van het aangewezen punt kon je
al doorklikken naar het archief, met het chevron dat de app overal gebruikt om dat aan te
geven. Bij de Low HI-regel niet, terwijl dat juist een ronde is die je wilt terugzien:
je beste van het jaar.

Uitzondering: heb je je Low HI HANDMATIG ingevuld, dan hoort er geen ronde bij. Die regel
verschijnt dan niet, dus er valt ook niets aan te klikken.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, sd):
    return {
        "id": rid, "date": "2026-%02d-%02d" % ((rid % 12) + 1, (rid % 28) + 1),
        "time": "09:%02d" % (rid % 60), "player": "Testspeler", "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36,
        "chcp": 11, "qualifying": True, "note": "", "total": 45, "totalStb": 18,
        "playedCount": 9, "holesCount": 9, "currentHole": 0, "started": True,
        "sd": sd, "sdFinal": sd, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1,
                   "ppar": 5, "score": 5} for i in range(9)],
    }


# Eén ronde springt er duidelijk uit: die levert de Low HI op.
RONDES = [ronde(i, 32.0 - (3 if i == 7 else 0) + (i % 4) * 0.4) for i in range(1, 25)]

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


LEES_REGEL = """() => {
    nav('stat');
    localStorage.setItem('golf_stats_grp_handicap', 'open');
    renderPlayerStats();
    const el = [...document.querySelectorAll('#screen-stat div')]
        .find(d => /^Low HI /.test(d.textContent.trim()) && d.children.length <= 2);
    if (!el) return null;
    return {
        tekst: el.textContent.trim(),
        chevron: el.innerHTML.includes('\\u203a'),
        aanklikbaar: !!el.getAttribute('onclick'),
        cursor: el.style.cursor,
    };
}"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 900})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(1200)

        print("=== DE REGEL WIJST EEN RONDE AAN ===\n")
        regel = await page.evaluate(LEES_REGEL)
        check("de regel staat er", regel is not None, True)
        check("met een chevron erachter", regel["chevron"], True)
        check("hij is aanklikbaar", regel["aanklikbaar"], True)
        check("en de aanwijzer verandert", regel["cursor"], 'pointer')

        print("\n=== KLIKKEN BRENGT JE NAAR DE RONDE ===\n")
        na = await page.evaluate("""() => {
            const el = [...document.querySelectorAll('#screen-stat div')]
                .find(d => /^Low HI /.test(d.textContent.trim()) && d.children.length <= 2);
            el.click();
            const actief = [...document.querySelectorAll('.screen')]
                .find(s => s.classList.contains('active'));
            return actief ? actief.id : null;
        }""")
        check("je komt in het archief uit", na, 'screen-archive')

        print("\n=== HANDMATIGE LOW HI: GEEN RONDE OM HEEN TE SPRINGEN ===\n")
        # Vul je je Low HI zelf in, dan hoort er geen ronde bij. De regel verschijnt dan
        # niet, dus er valt ook niets aan te klikken.
        await page.evaluate("() => localStorage.setItem('golf_low_hi', '29.5')")
        await page.reload()
        await page.wait_for_timeout(1000)
        handmatig = await page.evaluate(LEES_REGEL)
        check("de regel verschijnt niet", handmatig, None)

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
