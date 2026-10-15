"""Het oranje driehoekje bij afgeleide waarden.

De regel in de app: een gemiddelde dat op dagresultaten (Sd) is gebaseerd krijgt het
driehoekje zodra één van de meegetelde rondes er zelf een heeft — dat wil zeggen: een
afgeronde qualifying-ronde zonder vastgesteld dagresultaat. Zo zie je dat het getal op
onvolledige gegevens rust.

Die controle stond op het gemiddelde per tee, per baan, per club en per dagdeel, maar
ontbrak op 'Gem. dagresultaat 9 holes' en '18 holes' — terwijl die over dezelfde rondes
rekenen.

Waar het driehoekje NIET hoort: bij waarden in rauwe slagen ten opzichte van par
(Verloop, per SI, per par-type). Die gebruiken geen dagresultaat, dus een ontbrekende Sd
zegt daar niets.
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


def ronde(rid, datum, sd=30.0):
    return {
        "id": rid, "date": datum, "time": "09:00", "player": "Tester", "hcp": 30.7,
        "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren",
        "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
        "note": "", "total": 45, "totalStb": 18, "playedCount": 9, "holesCount": 9,
        "currentHole": 0, "started": True, "sd": sd, "sdFinal": sd, "pcc": 0,
        "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
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

        async def meet(zonderDagresultaat):
            rondes = [ronde(i, '2026-%02d-01' % ((i % 8) + 1)) for i in range(1, 9)]
            # Eén ronde uit een ander jaar, zodat er meerdere jaarkoppen zijn en de
            # controle op "alleen het juiste jaar krijgt het driehoekje" iets bewijst.
            rondes.append(ronde(50, '2025-06-01'))
            if zonderDagresultaat:
                rondes[0]['sd'] = None
                rondes[0]['sdFinal'] = None
            await page.evaluate("""([clubs, rs]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rs));
                localStorage.setItem('golf_default_club', 'Testclub');
                localStorage.setItem('golf_profile_name', 'Tester');
                localStorage.setItem('golf_kenmerk_gevraagd', '1');
            }""", [CLUBS, rondes])
            await page.reload()
            await page.wait_for_timeout(800)
            return await page.evaluate("""() => {
                nav('stat');
                ['handicap', 'prestaties', 'banen'].forEach(k =>
                    localStorage.setItem('golf_stats_grp_' + k, 'open'));
                renderPlayerStats();
                const rij = tekst => [...document.querySelectorAll('#screen-stat div')]
                    .find(d => d.textContent.trim().startsWith(tekst));
                const heeft = tekst => { const r = rij(tekst); return r ? !!r.querySelector('svg') : null; };
                // Alleen het LABEL bekijken bij de hoofdgroepen: het pijltje ernaast is
                // ook een svg en zou elke controle waar maken.
                const groep = naam => {
                    const kop = [...document.querySelectorAll('[onclick^="toggleStatsGroup"]')]
                        .find(el => el.textContent.trim().startsWith(naam));
                    if (!kop) return null;
                    const label = kop.querySelector('span');
                    return !!label.querySelector('svg');
                };
                return {
                    groepHandicap: groep('Handicap'),
                    groepPrestaties: groep('Prestaties'),
                    groepClubs: groep('Clubs'),
                    dagresultaat9: heeft('Gem. dagresultaat 9 holes'),
                    verloop1_3: heeft('Hole 1\\u20133'),
                    gemiddeldeSd: [...document.querySelectorAll('#screen-stat div')]
                        .some(d => /GEM\\. SD/i.test(d.textContent) && d.querySelector('svg')),
                };
            }""")

        print("=== ALLE RONDES COMPLEET ===\n")
        heel = await meet(False)
        check("geen driehoekje bij het gemiddelde dagresultaat", heel["dagresultaat9"], False)
        check("en ook niet bij het verloop", heel["verloop1_3"], False)

        print("\n=== ÉÉN RONDE ZONDER DAGRESULTAAT ===\n")
        kaal = await meet(True)
        check("het gemiddelde dagresultaat krijgt het driehoekje",
              kaal["dagresultaat9"], True)
        # Het verloop rekent in slagen t.o.v. par en gebruikt dus geen dagresultaat;
        # daar hoort het driehoekje niet, ook niet als er een Sd ontbreekt.
        check("het verloop blijft zonder driehoekje", kaal["verloop1_3"], False)

        print("\n=== DE DRIE HOOFDGROEPEN ===\n")
        # Op een dichtgeklapte groep moet je kunnen zien dat er iets onzeker is. Eerder
        # had alleen Clubs dat; Handicap en Prestaties kregen de vlag niet doorgegeven.
        check("Handicap zonder probleem: geen driehoekje", heel["groepHandicap"], False)
        check("Prestaties zonder probleem: geen driehoekje", heel["groepPrestaties"], False)
        check("Clubs zonder probleem: geen driehoekje", heel["groepClubs"], False)
        check("Handicap krijgt het driehoekje", kaal["groepHandicap"], True)
        check("Prestaties ook", kaal["groepPrestaties"], True)
        check("Clubs ook", kaal["groepClubs"], True)

        print("\n=== JAARKOPPEN IN HET ARCHIEF ===\n")
        # Alleen het jaar met de onvolledige ronde krijgt het driehoekje.
        jaren = await page.evaluate("""() => {
            nav('archive');
            window._flatYearCollapsed = {};
            window._groupByTrack = false; window._groupByPlayer = false;
            window._groupByCategory = false; window._groupByWhs = false;
            loadSaved();
            return [...document.querySelectorAll('#screen-archive .year-sep')].map(k => {
                const label = k.querySelector('span');
                return { jaar: label.textContent.trim(), driehoek: !!label.querySelector('svg') };
            });
        }""")
        metVlag = [j["jaar"] for j in jaren if j["driehoek"]]
        zonder = [j["jaar"] for j in jaren if not j["driehoek"]]
        check("er is een jaarkop met een driehoekje", len(metVlag), 1)
        check("en de andere jaren hebben er geen", len(zonder) >= 1, True)

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
