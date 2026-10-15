"""Tees staan overal in dezelfde volgorde.

De lijsten met tees werden gesorteerd op het aantal rondes. Daardoor stond de volgorde
per baan anders (op de ene baan Blauw-Rood-Geel, op de andere Geel-Blauw-Rood) en kon je
banen niet naast elkaar vergelijken. Bij een gelijk aantal besliste bovendien puur
toeval: welke ronde de app het eerst tegenkwam.

Nu geldt de volgorde van de club zelf, zoals die in de baaneditor staat — doorgaans van
achteren naar voren. Tees die nergens meer in een club voorkomen (uit oude rondes) komen
achteraan op alfabet, zodat ook die volgorde vastligt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url


def baan(tees):
    return {
        "holeIds": ["H%d" % (i + 1) for i in range(9)],
        "tees": {"Heren": {t: {"CR": 35.0, "SR": 120,
                               "holes": [{"par": 4, "si": i + 1} for i in range(9)]}
                           for t in tees}},
    }

# De club noemt de tees in deze volgorde: Wit, Geel, Blauw, Rood.
CLUBS = {
    "Testclub": {
        "club": "Testclub", "shortName": "TC",
        "courses": {
            "Baan A": baan(["Wit", "Geel", "Blauw", "Rood"]),
            "Baan B": baan(["Wit", "Geel", "Blauw", "Rood"]),
        },
    }
}


def ronde(rid, datum, track, tee):
    return {
        "id": rid, "date": datum, "time": "09:00", "player": "Tester", "hcp": 30.7,
        "club": "Testclub", "clubShort": "TC", "track": track, "gender": "Heren",
        "tee": tee, "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
        "note": "", "total": 45, "totalStb": 18, "playedCount": 9, "holesCount": 9,
        "currentHole": 0, "started": True, "sd": 30.0 + rid % 5,
        "sdFinal": 30.0 + rid % 5, "pcc": 0,
        "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }

# Baan A: veel Blauw, één Rood, één Geel. Baan B: veel Geel, één Blauw.
# Op aantal gesorteerd zou dat twee verschillende volgordes geven.
RONDES = ([ronde(i, '2026-08-%02d' % (i + 1), 'Baan A', 'Blauw') for i in range(1, 9)]
          + [ronde(20, '2026-07-01', 'Baan A', 'Rood'),
             ronde(21, '2026-07-02', 'Baan A', 'Geel')]
          + [ronde(30 + i, '2026-06-%02d' % (i + 1), 'Baan B', 'Geel') for i in range(3)]
          + [ronde(40, '2026-05-01', 'Baan B', 'Blauw')])

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
        await page.wait_for_timeout(900)

        print("=== DE VOLGORDE VAN DE CLUB ===\n")
        volgorde = await page.evaluate("() => [...teeVolgordeIndex().keys()]")
        check("de club bepaalt de volgorde", volgorde, ["Wit", "Geel", "Blauw", "Rood"])

        gesorteerd = await page.evaluate("""() =>
            ['Rood', 'Blauw', 'Geel', 'Wit'].sort(teeSorteerder())""")
        check("een losse lijst volgt die volgorde", gesorteerd,
              ["Wit", "Geel", "Blauw", "Rood"])

        # Een tee die nergens meer in een club voorkomt, hoort achteraan.
        metOnbekend = await page.evaluate("""() =>
            ['Zilver', 'Rood', 'Geel', 'Onbekend'].sort(teeSorteerder())""")
        check("onbekende tees komen achteraan, op alfabet", metOnbekend,
              ["Geel", "Rood", "Onbekend", "Zilver"])

        print("\n=== DEZELFDE VOLGORDE OP ELKE BAAN ===\n")
        perBaan = await page.evaluate("""() => {
            nav('stat');
            ['handicap', 'prestaties', 'banen'].forEach(k =>
                localStorage.setItem('golf_stats_grp_' + k, 'open'));
            // Clubs staan standaard ingeklapt; eerst openzetten, anders zijn er geen
            // tee-regels om te bekijken.
            window._statClubCollapsed = window._statClubCollapsed || {};
            window._statTrackCollapsed = window._statTrackCollapsed || {};
            renderPlayerStats();
            document.querySelectorAll('[onclick*="_statClubCollapsed"]').forEach(el => {
                const m = /_statClubCollapsed\['([^']+)'\]/.exec(el.getAttribute('onclick'));
                if (m) window._statClubCollapsed[m[1]] = false;
            });
            renderPlayerStats();
            // De tee-regels staan ingesprongen onder hun baan; per baan verzamelen op
            // volgorde van verschijnen in het scherm.
            const uit = {};
            let huidige = null;
            document.querySelectorAll('#screen-stat div').forEach(d => {
                const eerste = d.children[0];
                if (!eerste) return;
                const naam = (eerste.textContent || '').trim();
                if (/^Baan [AB]$/.test(naam)) { huidige = naam; return; }
                if (d.querySelector('.tee-badge') && huidige && naam) {
                    (uit[huidige] = uit[huidige] || []).push(naam);
                }
            });
            return uit;
        }""")
        banen = sorted(perBaan.keys())
        check("beide banen tonen tees", len(banen), 2)
        if len(banen) == 2:
            a, b = perBaan[banen[0]], perBaan[banen[1]]
            # Baan A heeft er drie, baan B twee — de gedeelde tees moeten in dezelfde
            # onderlinge volgorde staan.
            gedeeld_a = [t for t in a if t in b]
            gedeeld_b = [t for t in b if t in a]
            check("de gedeelde tees staan in dezelfde volgorde", gedeeld_a, gedeeld_b)
            check("baan A volgt de clubvolgorde", a, ["Geel", "Blauw", "Rood"])

        print("\n=== DE KAART 'GEMIDDELDE PER TEE' ===\n")
        kaart = await page.evaluate("""() => {
            const k = [...document.querySelectorAll('#screen-stat .card')]
                .find(c => c.textContent.toUpperCase().includes('GEMIDDELDE PER TEE'));
            if (!k) return null;
            return [...k.querySelectorAll('.tee-badge')]
                .map(b => b.parentElement.textContent.trim())
                .filter(Boolean);
        }""")
        check("ook daar de clubvolgorde", kaart, ["Geel", "Blauw", "Rood"])

        print("\n=== DE VOLGORDE WORDT NIET STEEDS OPNIEUW BEREKEND ===\n")
        # teeVolgordeIndex wordt per BAAN aangeroepen bij het opbouwen van de clubboom.
        # Zonder cache liep hij dan telkens de hele clublijst door. De uitkomst hangt
        # alleen van de clubs af, dus hij wordt bewaard tot die wijzigen.
        # Gecontroleerd op gedrag, niet op tijd: een tijdsgrens (eerst < 0,01 ms) faalde soms
        # alleen door de drukte van de volledige testrun (13527DA-146: 0,0100 ms). Bewaard
        # betekent: dezelfde Map terug zolang de clubs gelijk blijven, en een nieuwe zodra ze
        # wijzigen. De tijd wordt alleen nog gemeld.
        snelheid = await page.evaluate("""() => {
            for (let i = 0; i < 50; i++) {
                CLUBS['C' + i] = JSON.parse(JSON.stringify(CLUBS['Testclub']));
            }
            saveClubsToStorage();
            const eerste = teeVolgordeIndex();         // eerste keer opbouwen
            const t0 = performance.now();
            let steedsDezelfde = true;
            for (let i = 0; i < 500; i++) if (teeVolgordeIndex() !== eerste) steedsDezelfde = false;
            const ms = (performance.now() - t0) / 500;
            CLUBS['Extra'] = JSON.parse(JSON.stringify(CLUBS['Testclub']));
            saveClubsToStorage();
            const naWijziging = teeVolgordeIndex();
            return { ms, clubs: Object.keys(CLUBS).length - 1, steedsDezelfde,
                     nieuwNaWijziging: naWijziging !== eerste, nieuwBewaard: teeVolgordeIndex() === naWijziging };
        }""")
        print(f"   {snelheid['clubs']} clubs, {snelheid['ms']:.4f} ms per aanroep (alleen ter informatie)")
        check("zolang de clubs gelijk blijven: de bewaarde volgorde, niet opnieuw berekend", snelheid["steedsDezelfde"], True)
        check("na een wijziging van de clubs: opnieuw opgebouwd", snelheid["nieuwNaWijziging"], True)
        check("en daarna weer bewaard", snelheid["nieuwBewaard"], True)

        # Wijzigen de clubs, dan moet de volgorde wél meebewegen.
        vernieuwd = await page.evaluate("""() => {
            const voor = [...teeVolgordeIndex().keys()];
            CLUBS['Testclub'].courses['Baan A'].tees['Heren']['Zilver'] =
                { CR: 35, SR: 120, holes: [] };
            saveClubsToStorage();
            const na = [...teeVolgordeIndex().keys()];
            return { voor: voor.includes('Zilver'), na: na.includes('Zilver') };
        }""")
        check("een nieuwe tee stond er nog niet in", vernieuwd["voor"], False)
        check("en verschijnt na de wijziging", vernieuwd["na"], True)

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
