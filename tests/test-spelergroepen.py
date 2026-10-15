"""Groeperen op speler: rondes in de toekomst horen niet bij 'Laatste 12 maanden'.

De indeling keek alleen naar de ONDERGRENS — datum later dan een jaar geleden. Alles wat
in de toekomst ligt voldoet daaraan, dus een ronde van volgende maand stond tussen je
gespeelde rondes van dit jaar.

Nu zijn er drie groepen:
  * Gepland            — datum na nu, ONGEACHT de status
  * Laatste 12 maanden — datum binnen het afgelopen jaar
  * Overig             — ouder dan een jaar

Eén regel zonder uitzonderingen: of een ronde nog niet begonnen is, gepauzeerd, actief of
zelfs afgerond maakt niet uit. Een afgeronde ronde met een datum in de toekomst is
vrijwel altijd een typefout, en zo zie je hem meteen.

De volgorde binnen Gepland is die van de vlakke lijst: nieuw naar oud.
"""
import asyncio, json, os, sys
from datetime import date, timedelta
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, dagenTerug, gepland=False, actief=False):
    d = date.today() - timedelta(days=dagenTerug)
    x = {
        "id": rid, "date": d.isoformat(), "time": "09:%02d" % (rid % 60),
        "player": "Mark", "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC",
        "track": "Airborne", "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141,
        "PAR": 36, "chcp": 11, "qualifying": True, "note": "", "total": 45,
        "totalStb": 18, "playedCount": 9, "holesCount": 9, "currentHole": 0,
        "started": True, "sd": 30.0, "sdFinal": 30.0, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }
    if gepland:
        x.update(playedCount=0, started=False, sd=None, sdFinal=None,
                 holes=[{**h, "score": None} for h in x["holes"]])
    if actief:
        x.update(playedCount=4, sd=None, sdFinal=None,
                 holes=[{**h, "score": 5 if i < 4 else None}
                        for i, h in enumerate(x["holes"])])
    return x


RONDES = [
    ronde(1, 10),                       # gespeeld, binnen het jaar
    ronde(2, 100),                      # gespeeld, binnen het jaar
    ronde(3, 500),                      # ouder dan een jaar
    ronde(10, -30, gepland=True),       # over een maand
    ronde(11, -5, gepland=True),        # over vijf dagen
    ronde(12, -60),                     # AFGEROND, maar datum in de toekomst
    ronde(20, -10, actief=True),        # actief, maar datum in de toekomst
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
        page = await browser.new_page(viewport={"width": 390, "height": 1000})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_active_id', '20');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(900)

        print("=== DRIE GROEPEN PER SPELER ===\n")
        stand = await page.evaluate("""() => {
            nav('archive');
            if (!window._groupByPlayer) toggleGroupByPlayer();
            window._pgCollapsed = {};
            window._pgYearCollapsed = {};
            loadSaved();
            const regels = document.getElementById('screen-archive').innerText
                .split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean);
            const uit = {};
            regels.forEach((t, i) => {
                if (/^(GEPLAND|LAATSTE 12 MAANDEN|OVERIG)$/.test(t)) {
                    uit[t] = parseInt(regels[i + 1], 10);
                }
            });
            return { koppen: Object.keys(uit), aantallen: uit };
        }""")
        check("de groepen staan in volgorde", stand["koppen"],
              ['GEPLAND', 'LAATSTE 12 MAANDEN', 'OVERIG'])
        # Gepland: twee plannen, de afgeronde ronde met een toekomstige datum, en de
        # actieve ronde waarvan de datum in de toekomst is gezet.
        check("vier rondes onder Gepland", stand["aantallen"].get('GEPLAND'), 4)
        check("twee onder Laatste 12 maanden",
              stand["aantallen"].get('LAATSTE 12 MAANDEN'), 2)
        check("één onder Overig", stand["aantallen"].get('OVERIG'), 1)

        print("\n=== DE STATUS DOET NIET TER ZAKE ===\n")
        # Alleen de datum telt. De actieve ronde in deze proef heeft een datum in de
        # toekomst en staat daarom óók onder Gepland — geen uitzondering voor 'waar je
        # nu mee bezig bent'.
        volgorde = await page.evaluate("""() => {
            window._pgCollapsed = {};
            window._pgYearCollapsed = {};
            loadSaved();
            // Alle subgroepen openklappen via de sleutels uit hun eigen onclick.
            const keys = [...document.querySelectorAll('#screen-archive [onclick*="_pgYearCollapsed"]')]
                .map(e => {
                    const m = e.getAttribute('onclick').match(/_pgYearCollapsed'\]\['([^']+)'\]/);
                    return m ? m[1] : null;
                })
                .filter(Boolean);
            keys.forEach(k => { window._pgYearCollapsed[k] = false; });
            loadSaved();
            return [...document.querySelectorAll('#screen-archive .saved-item')]
                .map(k => k.innerText.split(String.fromCharCode(10))[0].trim());
        }""")
        # Nieuw naar oud, net als in de vlakke lijst.
        datums = [t.split('\u00b7')[0].strip() for t in volgorde]
        check("de kaarten staan er (alle groepen open)", len(volgorde) >= 5, True)
        check("gesorteerd nieuw naar oud",
              volgorde == sorted(volgorde, key=lambda t: tuple(
                  int(x) for x in reversed(t.split('\u00b7')[0].strip().split(' ')[1].split('-'))),
                  reverse=True), True)

        print("\n=== ZONDER GEPLANDE RONDES GEEN LEGE GROEP ===\n")
        zonder = await page.evaluate("""(rs) => {
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rs)));
            localStorage.removeItem('golf_active_id');
            loadSaved();
            const regels = document.getElementById('screen-archive').innerText
                .split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean);
            return regels.filter(t => /^(GEPLAND|LAATSTE 12 MAANDEN|OVERIG)$/.test(t));
        }""", [RONDES[0], RONDES[2]])
        check("alleen de groepen die iets bevatten", zonder,
              ['LAATSTE 12 MAANDEN', 'OVERIG'])

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
