"""Opnieuw plannen moet ELKE keuze van de ronde terugzetten.

De bestaande herplantest kijkt naar wat er daarna in de opslag staat. Deze kijkt naar
het startscherm zelf: staat de juiste baan, tee, geslacht, datum en het juiste
9/18-filter er echt, en overleven die het opnieuw opbouwen van het scherm?

Dat laatste is precies waar het misging: het startscherm heeft eigen regels (val terug
op de eerste zichtbare baan, kies de NGF-aanbevolen tee) die na het herplannen overheen
schreven wat er net was ingevuld.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url

NEGEN = [{"par": p, "si": i + 1} for i, p in enumerate([4, 4, 5, 4, 3, 5, 4, 3, 4])]
ACHTTIEN = [{"par": p, "si": i + 1} for i, p in
            enumerate([4, 4, 5, 4, 3, 5, 4, 3, 4, 4, 4, 5, 4, 3, 5, 4, 3, 4])]

CLUBS = {
    "Testclub": {
        "club": "Testclub", "shortName": "TC",
        "courses": {
            # Twee 9-holesbanen en één 18-holesbaan, met meerdere tees per geslacht.
            "Kleine baan": {
                "holeIds": ["K%d" % (i + 1) for i in range(9)],
                "tees": {
                    "Heren": {"Wit": {"CR": 35.0, "SR": 130, "holes": NEGEN},
                              "Geel": {"CR": 34.0, "SR": 118, "holes": NEGEN},
                              "Blauw": {"CR": 33.0, "SR": 110, "holes": NEGEN}},
                    "Dames": {"Rood": {"CR": 36.0, "SR": 124, "holes": NEGEN},
                              "Oranje": {"CR": 35.0, "SR": 115, "holes": NEGEN}},
                },
            },
            "Andere baan": {
                "holeIds": ["A%d" % (i + 1) for i in range(9)],
                "tees": {"Heren": {"Wit": {"CR": 35.5, "SR": 128, "holes": NEGEN}}},
            },
            "Grote baan": {
                "holeIds": ["G%d" % (i + 1) for i in range(18)],
                "tees": {
                    "Heren": {"Wit": {"CR": 71.0, "SR": 132, "holes": ACHTTIEN},
                              "Geel": {"CR": 69.0, "SR": 124, "holes": ACHTTIEN},
                              "Blauw": {"CR": 67.0, "SR": 116, "holes": ACHTTIEN}},
                    "Dames": {"Rood": {"CR": 73.0, "SR": 128, "holes": ACHTTIEN}},
                },
            },
        },
    }
}


def ronde(rid, track, gender, tee, datum, holes, speler="Tester", hcp=30.7, notitie=""):
    return {
        "id": rid, "date": datum, "time": "09:30", "player": speler, "hcp": hcp,
        "club": "Testclub", "clubShort": "TC", "track": track, "gender": gender,
        "tee": tee, "CR": 35.0, "SR": 130, "PAR": 36, "chcp": 15, "qualifying": False,
        "note": notitie, "total": 0, "totalStb": 0, "playedCount": 0,
        "holesCount": holes, "currentHole": 0, "started": False,
        "sd": None, "sdFinal": None, "pcc": 0,
        "holes": [{"id": "X%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1,
                   "ppar": 5, "score": None} for i in range(holes)],
    }

RONDES = [
    # Een 18-holesronde: die valt buiten het 9-filter dat standaard aanstaat.
    ronde(1, "Grote baan", "Heren", "Wit", "2026-09-20", 18),
    # Een damesronde vanaf een tee die niet de NGF-aanbeveling is.
    ronde(2, "Kleine baan", "Dames", "Oranje", "2026-09-12", 9),
    # Een herenronde vanaf de langste tee — ook niet wat het advies zou kiezen.
    ronde(3, "Kleine baan", "Heren", "Wit", "2026-09-14", 9, notitie="niet vergeten"),
    # Twee gekoppelde rondes op hetzelfde tijdstip: speler 1 en speler 2.
    ronde(4, "Kleine baan", "Dames", "Rood", "2026-09-18", 9),
    ronde(5, "Kleine baan", "Heren", "Blauw", "2026-09-18", 9, speler="Partner", hcp=12.0),
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
        page = await browser.new_page()
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Testclub');
            localStorage.setItem('golf_profile_name', 'Tester');
            localStorage.setItem('golf_profile_hcp', '30.7');
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(500)

        async def herplan(rid):
            return await page.evaluate("""(rid) => {
                annuleerHerplan();
                herplanRonde(rid);
                const actief = id => !!document.getElementById(id)?.classList.contains('active');
                return {
                    track: sel.track, gender: sel.gender, tee: sel.tee,
                    date: sel.date, holeCount: sel.holeCount,
                    baanKnop: Array.from(document.querySelectorAll('.track-btn'))
                        .filter(b => b.classList.contains('active'))
                        .map(b => b.querySelector('.track-name').textContent)[0] || null,
                    teeKnop: Array.from(document.querySelectorAll('#teeBtns button'))
                        .filter(b => b.classList.contains('active'))
                        .map(b => b.textContent.trim())[0] || null,
                    herenKnop: actief('gb-Heren'), damesKnop: actief('gb-Dames'),
                    filter9: actief('cat-9'), filter18: actief('cat-18'),
                    naam: document.getElementById('iName').value,
                    hcp: document.getElementById('iHcp').value,
                };
            }""", rid)

        print("=== 18-HOLESRONDE (valt buiten het 9-filter) ===\n")
        a = await herplan('1')
        check("baan", a["track"], "Grote baan")
        check("baanknop gemarkeerd", a["baanKnop"], "Grote baan")
        check("filter staat op 18", [a["filter9"], a["filter18"]], [False, True])
        check("tee", a["tee"], "Wit")
        check("teeknop gemarkeerd", a["teeKnop"], "Wit")
        check("datum", a["date"], "2026-09-20")

        print("\n=== DAMESRONDE VANAF EEN NIET-AANBEVOLEN TEE ===\n")
        b = await herplan('2')
        check("baan", b["track"], "Kleine baan")
        check("geslacht", b["gender"], "Dames")
        check("damesknop gemarkeerd", [b["herenKnop"], b["damesKnop"]], [False, True])
        check("tee blijft staan", b["tee"], "Oranje")
        check("teeknop gemarkeerd", b["teeKnop"], "Oranje")

        print("\n=== HERENRONDE VANAF DE LANGSTE TEE ===\n")
        c = await herplan('3')
        check("tee blijft staan", c["tee"], "Wit")
        check("teeknop gemarkeerd", c["teeKnop"], "Wit")
        check("herenknop gemarkeerd", [c["herenKnop"], c["damesKnop"]], [True, False])
        check("naam en handicap", [c["naam"], c["hcp"]], ["Tester", "30.7"])

        print("\n=== TWEE GEKOPPELDE RONDES ===\n")
        d = await page.evaluate("""() => {
            annuleerHerplan();
            herplanRonde('4');
            return {
                speler1: { gender: sel.gender, tee: sel.tee, naam: document.getElementById('iName').value },
                zichtbaar: player2Visible,
                speler2: { gender: sel2.gender, tee: sel2.tee,
                           naam: document.getElementById('iName2').value,
                           hcp: document.getElementById('iHcp2').value },
            };
        }""")
        check("speler 1 tee", d["speler1"]["tee"], "Rood")
        check("speler 2 verschijnt", d["zichtbaar"], True)
        check("speler 2 tee blijft staan", d["speler2"]["tee"], "Blauw")
        check("speler 2 geslacht", d["speler2"]["gender"], "Heren")
        check("speler 2 naam en handicap",
              [d["speler2"]["naam"], d["speler2"]["hcp"]], ["Partner", "12"])

        print("\n=== EN DAN ECHT STARTEN ===\n")
        e = await page.evaluate("""() => {
            startRound();
            if (!document.getElementById('confirmModal').classList.contains('hidden')) {
                document.getElementById('confirmModalBtn').click();
            }
            return loadSavedRounds()
                .filter(r => r.date === '2026-09-18')
                .map(r => [r.player, r.track, r.gender, r.tee, r.holes.length])
                .sort();
        }""")
        check("beide rondes met hun eigen tee", e,
              [["Partner", "Kleine baan", "Heren", "Blauw", 9],
               ["Tester", "Kleine baan", "Dames", "Rood", 9]])

        # De herplande rondes horen vervangen te zijn, niet verdubbeld.
        aantal = await page.evaluate("""() => loadSavedRounds().length""")
        check("geen dubbele rondes", aantal, len(RONDES))

        print("\n=== RONDE VAN EEN ANDERE CLUB ===\n")
        # Het startscherm toont alleen de banen van de geselecteerde club. Herplan je een
        # ronde van een andere club, dan moet de app naar díé club omschakelen — anders
        # staat de baan niet in de lijst en krijg je stilzwijgend een andere.
        anders = await page.evaluate("""() => {
            CLUBS['Tweede club'] = {
                club: 'Tweede club', shortName: '2C',
                courses: { 'Verre baan': {
                    holeIds: ['V1','V2','V3','V4','V5','V6','V7','V8','V9'],
                    tees: { Heren: { Geel: { CR: 34.0, SR: 118,
                        holes: Array.from({length: 9}, (_, i) => ({ par: 4, si: i + 1 })) } } } } }
            };
            const rondes = loadSavedRounds();
            rondes.push({
                id: 99, date: '2026-10-01', time: '11:00', player: 'Tester', hcp: 30.7,
                club: 'Tweede club', clubShort: '2C', track: 'Verre baan', gender: 'Heren',
                tee: 'Geel', CR: 34.0, SR: 118, PAR: 36, chcp: 15, qualifying: false,
                note: '', total: 0, totalStb: 0, playedCount: 0, holesCount: 9,
                currentHole: 0, started: false, sd: null, sdFinal: null, pcc: 0,
                holes: Array.from({length: 9}, (_, i) => ({ id: 'V' + (i + 1), par: 4,
                    si: i + 1, phcp: 1, ppar: 5, score: null })),
            });
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Testclub');
            saveClubsToStorage();
            rebuildCourseLookup(); saveClubsToStorage();
            rebuildAll();

            annuleerHerplan();
            herplanRonde('99');
            return {
                club: localStorage.getItem('golf_default_club'),
                track: sel.track, tee: sel.tee,
                baanKnop: Array.from(document.querySelectorAll('.track-btn'))
                    .filter(b => b.classList.contains('active'))
                    .map(b => b.querySelector('.track-name').textContent)[0] || null,
                zichtbaar: Array.from(document.querySelectorAll('.track-btn'))
                    .map(b => b.querySelector('.track-name').textContent),
            };
        }""")

        check("club schakelt mee", anders["club"], "Tweede club")
        check("baan van die club", anders["track"], "Verre baan")
        check("baanknop gemarkeerd", anders["baanKnop"], "Verre baan")
        check("alleen banen van die club in de lijst", anders["zichtbaar"], ["Verre baan"])
        check("tee blijft staan", anders["tee"], "Geel")

        gestart = await page.evaluate("""() => {
            startRound();
            if (!document.getElementById('confirmModal').classList.contains('hidden')) {
                document.getElementById('confirmModalBtn').click();
            }
            return loadSavedRounds()
                .filter(r => r.date === '2026-10-01')
                .map(r => [r.club, r.track, r.tee]);
        }""")
        check("gestart op de juiste baan", gestart, [["Tweede club", "Verre baan", "Geel"]])

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
