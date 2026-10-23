"""Wedstrijdpercentage op de baanhandicap, en de WHS-hcp met één tik overnemen.

Wedstrijden spelen vaak met een percentage van de baanhandicap: 95% bij individueel
strokeplay, 85% bij sommige stablefordwedstrijden. De officiële regels rekenen dat
percentage over de BAANHANDICAP — niet over je handicapindex, want dan kom je soms een
slag anders uit.

De uitkomst is niets bijzonders: een handmatig aangepaste baanhandicap. Daardoor werkt de
bestaande herstelknop meteen, en hoeft het percentage nergens bewaard te worden.
"""
import asyncio, json, os, sys
from datetime import date, timedelta
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, dagenTerug, sd):
    d = date.today() - timedelta(days=dagenTerug)
    return {
        "id": rid, "date": d.isoformat(), "time": "09:%02d" % (rid % 60),
        "player": "Testspeler", "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC",
        "track": "Airborne", "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141,
        "PAR": 36, "chcp": 11, "qualifying": True, "note": "", "total": 45,
        "totalStb": 18, "playedCount": 9, "holesCount": 9, "currentHole": 0,
        "started": True, "sd": sd, "sdFinal": sd, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5} for i in range(9)],
    }


RONDES = [ronde(i, i * 5, 29.0 + (i % 5) * 0.6) for i in range(1, 25)]

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
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(1100)

        await page.evaluate("""() => {
            nav('setup');
            sel.track = 'Airborne';
            sel.tee = 'Blauw';
            const i = document.getElementById('iHcp');
            i.value = '30.7';
            onHcpBlur(i);
            updateChcp();
        }""")
        await page.wait_for_timeout(300)

        LEES = """() => ({
            getoond: document.getElementById('chcpPreview').textContent,
            uitleg: document.getElementById('chcpOverrideRow').classList.contains('hidden')
                ? null : document.getElementById('chcpOverrideNote').textContent,
            override: sel.chcpOverride,
            pct: sel.chcpPct,
        })"""

        async def kiesPercentage(waarde):
            await page.evaluate("() => openChcpPercentage()")
            await page.wait_for_timeout(300)
            await page.evaluate("""(w) => {
                const knop = [...document.querySelectorAll('#choiceEditModal button')]
                    .find(b => b.textContent.trim() === w);
                if (knop) knop.click();
                const m = document.getElementById('choiceEditModal');
                if (m && !m.classList.contains('hidden')) {
                    const ok = [...m.querySelectorAll('button')]
                        .find(b => b.textContent.trim() === 'OK');
                    if (ok) ok.click();
                }
            }""", waarde)
            await page.wait_for_timeout(400)

        print("=== HET PERCENTAGE REKENT OP DE BAANHANDICAP ===\n")
        vooraf = await page.evaluate(LEES)
        vol = int(vooraf["getoond"])
        check("er is een baanhandicap om mee te rekenen", vol > 0, True)
        check("er staat vooraf geen melding", vooraf["uitleg"], None)

        await kiesPercentage('85')
        na85 = await page.evaluate(LEES)
        # Rekenkundig afronden, zoals de WHS-regels voorschrijven.
        check("85% wordt rekenkundig afgerond",
              int(na85["getoond"]), round(vol * 85 / 100))
        check("de melding vertelt waar het getal vandaan komt",
              na85["uitleg"], f"Handmatig aangepast · 85% van {vol}")

        print("\n=== HANDMATIG BIJSTELLEN WIST HET PERCENTAGE ===\n")
        # 85% van 15 is niet meer waar zodra je er zelf een slag afhaalt.
        await page.evaluate("() => adjustChcp(-1)")
        await page.wait_for_timeout(200)
        naMin = await page.evaluate(LEES)
        check("het getal gaat één omlaag",
              int(naMin["getoond"]), int(na85["getoond"]) - 1)
        check("en de melding noemt geen percentage meer",
              naMin["uitleg"], 'Handmatig aangepast')
        check("het percentage is gewist", naMin["pct"], None)

        print("\n=== DE HERSTELKNOP BRENGT JE TERUG OP 100% ===\n")
        await kiesPercentage('95')
        await page.evaluate("() => resetChcpOverride()")
        await page.wait_for_timeout(200)
        naHerstel = await page.evaluate(LEES)
        check("de volle baanhandicap is terug", int(naHerstel["getoond"]), vol)
        check("de melding is weg", naHerstel["uitleg"], None)
        check("en het percentage ook", naHerstel["pct"], None)

        print("\n=== DE WHS-HCP MET ÉÉN TIK OVERNEMEN ===\n")
        # Bestond al: de herstelknop bij het handicapveld verschijnt zodra je iets anders
        # hebt ingevuld dan de app berekent.
        await page.evaluate("""() => {
            const i = document.getElementById('iHcp');
            i.value = '25.0';
            onHcpBlur(i);
            // De regel met de knop hangt aan deze verversing; in de app gebeurt dat bij
            // het verlaten van het veld.
            updateComputedHcp();
        }""")
        await page.wait_for_timeout(400)
        hcp = await page.evaluate("""() => ({
            berekend: document.getElementById('computedHcpVal').textContent,
            veld: document.getElementById('iHcp').value,
            knop: !document.getElementById('hcpOverrideRow').classList.contains('hidden'),
        })""")
        check("bij een afwijkende waarde verschijnt de knop", hcp["knop"], True)

        na = await page.evaluate("""() => {
            resetHcpToComputed();
            return {
                veld: document.getElementById('iHcp').value,
                berekend: document.getElementById('computedHcpVal').textContent,
                knop: !document.getElementById('hcpOverrideRow').classList.contains('hidden'),
            };
        }""")
        await page.wait_for_timeout(300)
        check("één tik vult de berekende handicap in", na["veld"], na["berekend"])
        check("en de knop verdwijnt", na["knop"], False)

        print("\n=== OOK BIJ EEN LEEG VELD ===\n")
        # Een leeg veld telde niet als 'afwijkend', dus verscheen de knop niet — terwijl
        # dat juist het moment is waarop 'vul de berekende waarde in' het meest oplevert.
        leeg = await page.evaluate("""() => {
            const i = document.getElementById('iHcp');
            i.value = '';
            onHcpBlur(i);
            updateComputedHcp();
            return {
                knop: !document.getElementById('hcpOverrideRow').classList.contains('hidden'),
                melding: document.getElementById('hcpOverrideNote').textContent,
            };
        }""")
        check("bij een leeg veld verschijnt de knop", leeg["knop"], True)
        check("met een tekst die bij een leeg veld hoort",
              leeg["melding"], 'Nog geen handicap ingevuld')
        gevuld = await page.evaluate("""() => {
            resetHcpToComputed();
            updateComputedHcp();
            return {
                veld: document.getElementById('iHcp').value,
                berekend: document.getElementById('computedHcpVal').textContent,
                knop: !document.getElementById('hcpOverrideRow').classList.contains('hidden'),
            };
        }""")
        check("en één tik vult hem", gevuld["veld"], gevuld["berekend"])
        check("waarna de knop weer weg is", gevuld["knop"], False)

        print("\n=== MET HANDICAP BIJHOUDEN UIT ===\n")
        # De %-knop rekent op de BAANHANDICAP, en die bestaat ook zonder de
        # handicapberekening — dus die hoort gewoon te blijven werken. De herstelknop bij
        # het handicapveld verwijst naar je berekende WHS-hcp en hoort juist te verdwijnen.
        zonderWhs = await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'off');
            pasWhsWeergaveToe();
            nav('setup');
            updateChcp();
            updateComputedHcp();
            const zichtbaar = id => {
                const e = document.getElementById(id);
                return !!e && getComputedStyle(e).display !== 'none';
            };
            return { pctKnop: zichtbaar('chcpPctBtn'),
                     whsRegel: zichtbaar('computedHcpRow'),
                     herstelknop: zichtbaar('hcpOverrideRow') };
        }""")
        check("de %-knop blijft werken", zonderWhs["pctKnop"], True)
        check("de WHS-regel is weg", zonderWhs["whsRegel"], False)
        check("en de herstelknop bij de handicap ook", zonderWhs["herstelknop"], False)

        werkt = await page.evaluate("""() => {
            openChcpPercentage();
            const m = document.getElementById('choiceEditModal');
            const open = m && !m.classList.contains('hidden');
            if (open) {
                const k = [...m.querySelectorAll('button')]
                    .find(b => b.textContent.trim() === '85');
                if (k) k.click();
                if (!m.classList.contains('hidden')) {
                    const ok = [...m.querySelectorAll('button')]
                        .find(b => b.textContent.trim() === 'OK');
                    if (ok) ok.click();
                }
            }
            return { vensterOpende: open, pct: sel.chcpPct };
        }""")
        check("het percentagevenster gaat open", werkt["vensterOpende"], True)
        check("en het percentage wordt toegepast", werkt["pct"], 85)
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")

        print("\n=== HET PERCENTAGE REKENT ALTIJD OVER DE BEREKENDE WAARDE ===\n")
        # Ook als je de baanhandicap al handmatig had bijgesteld. Anders krijg je bij twee
        # keer kiezen 85% van 85%. Het venster zegt daarom 'van berekende chcp 15', niet
        # 'van baanhandicap' — dat laatste is wat er op dat moment staat.
        # De berekende baanhandicap opnieuw uitlezen: eerdere stappen hebben het
        # handicapveld gewijzigd, dus de waarde van bovenaan deze test is verouderd.
        await page.evaluate("""() => {
            resetChcpOverride();
            adjustChcp(-3);          // handmatig omlaag
        }""")
        await page.wait_for_timeout(200)
        berekend = await page.evaluate("() => calcChcpAuto()")
        venster = await page.evaluate("""() => {
            openChcpPercentage();
            return {
                opScherm: document.getElementById('chcpPreview').textContent,
                label: document.getElementById('choiceEditLabel').innerText
                    .split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean),
                opties: [...document.querySelectorAll('#choiceEditOptions button')]
                    .map(b => b.textContent.trim()),
            };
        }""")
        check("de baanhandicap staat handmatig lager",
              int(venster["opScherm"]), berekend - 3)
        # innerText geeft de tekst zoals hij op het scherm staat, en de kop staat in
        # hoofdletters.
        check("maar het venster rekent over de berekende waarde",
              venster["label"][-1].lower(), f"van berekende chcp {berekend}")
        check("en er staan acht percentages",
              venster["opties"], ['100', '95', '90', '85', '80', '75', '60', '50'])

        async def kiesInGeopendVenster(waarde):
            await page.evaluate("""(w) => {
                const m = document.getElementById('choiceEditModal');
                const k = [...m.querySelectorAll('button')]
                    .find(b => b.textContent.trim() === w);
                if (k) k.click();
                if (!m.classList.contains('hidden')) {
                    const ok = [...m.querySelectorAll('button')]
                        .find(b => b.textContent.trim() === 'OK');
                    if (ok) ok.click();
                }
            }""", waarde)
            await page.wait_for_timeout(300)
            return await page.evaluate(LEES)

        na = await kiesInGeopendVenster('85')
        check("85% rekent over de berekende waarde, niet over de bijgestelde",
              int(na["getoond"]), round(berekend * 85 / 100))

        print("\n=== 100% HEFT DE AANPASSING OP ===\n")
        # Niet 'handmatig aangepast naar dezelfde waarde': dan zou er een melding staan
        # over een getal dat gelijk is aan de berekende.
        await kiesPercentage('100')
        honderd = await page.evaluate(LEES)
        check("je bent terug op de berekende baanhandicap",
              int(honderd["getoond"]), berekend)
        check("zonder melding", honderd["uitleg"], None)
        check("en zonder percentage", honderd["pct"], None)

        print("\n=== SPELER 2 HEEFT ZIJN EIGEN PERCENTAGE ===\n")
        # Twee spelers, twee baanhandicapkaarten, twee percentages. Ze horen elkaar niet
        # te beïnvloeden: je medespeler kan in dezelfde wedstrijd een ander percentage
        # hebben, en bij een vierbal verschillen ze vrijwel altijd.
        await page.evaluate("""() => {
            resetChcpOverride();
            nav('setup');
            if (!player2Visible) togglePlayer2();
            document.getElementById('iName2').value = 'Partner';
            document.getElementById('iHcp2').value = '18.0';
            sel2.tee = 'Geel';
            sel2._teeUserSelected = true;
            updateChcp();
            updateChcpSpeler2();
        }""")
        await page.wait_for_timeout(300)

        BEIDE = """() => ({
            s1: {
                chcp: document.getElementById('chcpPreview').textContent,
                melding: document.getElementById('chcpOverrideRow').classList.contains('hidden')
                    ? null : document.getElementById('chcpOverrideNote').textContent,
                pct: sel.chcpPct,
            },
            s2: {
                chcp: document.getElementById('chcp2Preview').textContent,
                melding: document.getElementById('chcp2OverrideRow').classList.contains('hidden')
                    ? null : document.getElementById('chcp2OverrideNote').textContent,
                pct: sel2.chcpPct,
            },
        })"""

        async def kiesVoor(speler, waarde):
            await page.evaluate("(s) => openChcpPercentage(s)", speler)
            await page.wait_for_timeout(300)
            titel = await page.evaluate("""() =>
                document.getElementById('choiceEditLabel').innerText
                    .split(String.fromCharCode(10))[0].trim()""")
            await page.evaluate("""(w) => {
                const m = document.getElementById('choiceEditModal');
                const k = [...m.querySelectorAll('button')]
                    .find(b => b.textContent.trim() === w);
                if (k) k.click();
                if (!m.classList.contains('hidden')) {
                    const ok = [...m.querySelectorAll('button')]
                        .find(b => b.textContent.trim() === 'OK');
                    if (ok) ok.click();
                }
            }""", waarde)
            await page.wait_for_timeout(400)
            return titel

        vooraf = await page.evaluate(BEIDE)
        chcp2 = int(vooraf["s2"]["chcp"])

        titel = await kiesVoor(2, '85')
        check("de titel zegt om welke speler het gaat",
              titel.lower(), 'percentage speler 2')
        na2 = await page.evaluate(BEIDE)
        check("speler 2 krijgt zijn percentage",
              int(na2["s2"]["chcp"]), round(chcp2 * 85 / 100))
        check("en speler 1 blijft ongemoeid", na2["s1"]["pct"], None)

        await kiesVoor(1, '75')
        na1 = await page.evaluate(BEIDE)
        check("speler 1 krijgt een eigen percentage", na1["s1"]["pct"], 75)
        check("en dat van speler 2 blijft staan", na1["s2"]["pct"], 85)

        # Handmatig bijstellen en herstellen werken ook per speler.
        await page.evaluate("() => adjustChcpSpeler2(-1)")
        await page.wait_for_timeout(200)
        naBij = await page.evaluate(BEIDE)
        check("bijstellen wist alleen het percentage van speler 2",
              [naBij["s2"]["pct"], naBij["s1"]["pct"]], [None, 75])

        await page.evaluate("() => resetChcpSpeler2Override()")
        await page.wait_for_timeout(200)
        naHerstel2 = await page.evaluate(BEIDE)
        check("herstellen brengt speler 2 terug op zijn berekende waarde",
              int(naHerstel2["s2"]["chcp"]), chcp2)
        check("zonder melding", naHerstel2["s2"]["melding"], None)
        check("en speler 1 staat er nog", naHerstel2["s1"]["pct"], 75)

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
