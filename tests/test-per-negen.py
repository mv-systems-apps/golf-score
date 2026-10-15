"""Per negen in de ronde-informatie: hoe speelde je op de eerste en de tweede lus?

Bij een ronde van 18 holes staan de twee negens op twee verschillende banen. Het paneel
toonde alleen de totalen, dus je kon niet zien waar je de slagen verloor.

Het blok verschijnt ALLEEN bij 18 holes: bij negen zou het een lege doos zijn. En de
netto-afwijking wordt tegen de PAR afgezet, net als in de regels erboven — tegen de
persoonlijke par zou je de handicapslagen dubbel tellen.
"""
import asyncio, json, os, sys
from datetime import date
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def maakRonde(aantalIngevuld, holes=18):
    """Een ronde met wisselende pars en handicapslagen, zodat de optelsom echt iets zegt."""
    hs = []
    for i in range(holes):
        par = 4 if i % 3 else (3 if i % 2 else 5)
        hs.append({
            "id": i + 1, "par": par, "si": i + 1,
            "phcp": 2 if i < 12 else 1,
            "ppar": par + (2 if i < 12 else 1),
            "score": (par + 1 + (i % 3)) if i < aantalIngevuld else None,
        })
    return {
        "id": 1, "date": date.today().isoformat(), "time": "09:00", "player": "Mark",
        "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC",
        "track": "Sandr/Airborne", "gender": "Heren", "tee": "Blauw",
        "CR": 70.0, "SR": 130, "PAR": sum(h["par"] for h in hs), "chcp": 31,
        "qualifying": True, "note": "", "total": 0, "totalStb": 0,
        "playedCount": aantalIngevuld, "holesCount": holes, "currentHole": 0,
        "started": True, "sd": None, "sdFinal": None, "pcc": 0, "holes": hs,
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

        async def paneel(ronde):
            page = await browser.new_page(viewport={"width": 390, "height": 1000})
            page.on('pageerror', lambda e: paginafouten.append(str(e)))
            await page.goto(app_url())
            await page.evaluate("""([clubs, r]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify([r]));
                localStorage.setItem('golf_active_id', '1');
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            }""", [CLUBS, ronde])
            await page.goto(app_url())
            await page.wait_for_timeout(1200)
            regels = await page.evaluate("""() => {
                nav('stat');
                // Het blok staat standaard dicht; voor de inhoudscontrole klappen we het
                // open. Dat de stand standaard DICHT is, wordt hieronder apart getoetst.
                const kop = [...document.querySelectorAll('#sumInfo .more-toggle')]
                    .find(e => /per negen/i.test(e.textContent));
                if (kop && !kop.classList.contains('open')) toggleMoreInfo(kop);
                return document.getElementById('sumInfo').innerText
                    .split(String.fromCharCode(10))
                    .map(s => s.trim())
                    .filter(Boolean);
            }""")
            await page.close()
            # innerText geeft de tekst zoals hij op het scherm staat: de sectiekop staat
            # daar in hoofdletters. De twee regels eronder dragen het label van de
            # subtabs op het scorescherm — dus de hole-id's, niet '1...9' vast.
            # Elk cijfer staat op een eigen regel, met een kopregel per negen die het
            # label van de subtab draagt (opgebouwd uit de hole-id's). We lezen per kop
            # de labels en waarden eronder uit, tot de volgende kop.
            uit = {}
            koppen = [k for k, r in enumerate(regels) if '...' in r and 'Sd' not in r]
            for nr, k in enumerate(koppen[:2], start=1):
                eind = koppen[nr] if nr < len(koppen) else len(regels)
                velden = {}
                m = k + 1
                while m + 1 < eind:
                    velden[regels[m]] = regels[m + 1]
                    m += 2
                uit['eerste' if nr == 1 else 'tweede'] = (regels[k], velden)
            uit['Per negen'] = len(koppen) >= 2
            return uit, regels

        print("=== 18 HOLES, ALLES INGEVULD ===\n")
        ronde = maakRonde(18)
        uit, regels = await paneel(ronde)
        check("het blok staat er", uit.get('Per negen'), True)

        def stbVoor(h):
            """Stablefordpunten voor één hole: 2 bij je persoonlijke par, en per slag
            eromheen één meer of minder, met nul als bodem."""
            if h["score"] is None:
                return 0
            return max(0, 2 - (h["score"] - (h["par"] + h["phcp"])))

        # Zelf narekenen: de app moet hetzelfde uitkomen.
        def reken(van, tot):
            deel = ronde["holes"][van:tot]
            bruto = sum(h["score"] for h in deel)
            par = sum(h["par"] for h in deel)
            phcp = sum(h["phcp"] for h in deel)
            netto = bruto - phcp
            return bruto, bruto - par, netto, netto - par

        # De labels komen uit de hole-id's, net als de subtabs op het scorescherm.
        check("het eerste label is dat van de subtab",
              uit['eerste'][0], f"{ronde['holes'][0]['id']}...{ronde['holes'][8]['id']}")
        check("en het tweede ook",
              uit['tweede'][0], f"{ronde['holes'][9]['id']}...{ronde['holes'][17]['id']}")

        for sleutel, (van, tot) in [('eerste', (0, 9)), ('tweede', (9, 18))]:
            bruto, dBruto, netto, dNetto = reken(van, tot)
            label, velden = uit[sleutel]
            verwachtBruto = f"{bruto} ({'E' if dBruto == 0 else format(dBruto, '+d')} vs par)"
            verwachtNetto = f"{netto} ({'E' if dNetto == 0 else format(dNetto, '+d')} vs par)"
            check(f"{label}: bruto", velden.get('Bruto (STR)'), verwachtBruto)
            check(f"{label}: netto", velden.get('Netto'), verwachtNetto)
            stb = sum(stbVoor(h) for h in ronde["holes"][van:tot])
            check(f"{label}: stableford", velden.get('Stableford (STB)'), str(stb))

        # De twee negens samen horen het totaal te zijn dat erboven staat.
        b1, _, _, _ = reken(0, 9)
        b2, _, _, _ = reken(9, 18)
        totaalRegel = next((regels[i + 1] for i, r in enumerate(regels)
                            if r == 'Bruto (STR)'), '')
        check("samen zijn ze het brutototaal",
              totaalRegel.startswith(str(b1 + b2)), True)

        print("\n=== HALVE RONDE ===\n")
        # Tot en met hole 12: de tweede negen is onvolledig en moet dat zeggen, anders
        # vergelijk je een halve negen met een hele.
        uit, _ = await paneel(maakRonde(12))
        check("de eerste negen meldt geen aantal", 'Holes' in uit['eerste'][1], False)
        check("de tweede negen meldt hoeveel holes er zijn",
              uit['tweede'][1].get('Holes'), '3 / 9 gespeeld')

        print("\n=== NOG NIETS INGEVULD ===\n")
        uit, _ = await paneel(maakRonde(0))
        check("beide negens tonen een streepje",
              [uit['eerste'][1].get('Bruto (STR)'), uit['tweede'][1].get('Bruto (STR)')],
              ['\u2014', '\u2014'])

        print("\n=== NEGEN HOLES ===\n")
        uit, _ = await paneel(maakRonde(9, holes=9))
        check("dan staat het blok er niet", uit.get('Per negen'), False)

        print("\n=== EIGEN HOLENUMMERING ===\n")
        # Sommige banen nummeren hun holes niet 1 t/m 18. Het label volgt dan de hole-id's,
        # precies zoals de subtab op het scorescherm dat doet — daar staat het ook niet
        # hardgecodeerd.
        eigen = maakRonde(18)
        for k, h in enumerate(eigen["holes"]):
            h["id"] = ('A' if k < 9 else 'B') + str((k % 9) + 1)
        uit, _ = await paneel(eigen)
        check("het label volgt de hole-id's",
              [uit['eerste'][0], uit['tweede'][0]], ['A1...A9', 'B1...B9'])

        print("\n=== HET BLOK STAAT STANDAARD DICHT ===\n")
        # Je kijkt er maar af en toe naar, dus het hoort niet elke keer het paneel op te
        # rekken. Zelfde patroon als 'Meer uitleg' elders in de app.
        page = await browser.new_page(viewport={"width": 390, "height": 1200})
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, r]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify([r]));
            localStorage.setItem('golf_active_id', '1');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        }""", [CLUBS, maakRonde(18)])
        await page.goto(app_url())
        await page.wait_for_timeout(1200)

        LEES = """() => {
            const kop = [...document.querySelectorAll('#sumInfo .more-toggle')]
                .find(e => /per negen/i.test(e.textContent));
            const wrap = kop && kop.nextElementSibling;
            return {
                kop: kop ? kop.textContent.trim() : null,
                open: wrap ? wrap.classList.contains('open') : null,
                zichtbaar: !!(wrap && wrap.getBoundingClientRect().height > 10),
                grootte: kop ? getComputedStyle(kop).fontSize : null,
                gewicht: kop ? getComputedStyle(kop).fontWeight : null,
            };
        }"""
        await page.evaluate("() => nav('stat')")
        await page.wait_for_timeout(600)
        dicht = await page.evaluate(LEES)
        # textContent geeft de tekst uit de code; de hoofdletters komen uit de opmaak.
        check("er staat een kopje", dicht["kop"], 'Per negen')
        check("standaard dicht", dicht["open"], False)
        check("dus de cijfers zijn niet zichtbaar", dicht["zichtbaar"], False)
        # Zelfde maat als de andere sectiekopjes in dit paneel.
        check("zelfde grootte als de andere kopjes", dicht["grootte"], '17px')
        check("en zelfde gewicht", dicht["gewicht"], '800')

        await page.evaluate("""() => {
            const kop = [...document.querySelectorAll('#sumInfo .more-toggle')]
                .find(e => /per negen/i.test(e.textContent));
            kop.click();
        }""")
        await page.wait_for_timeout(500)
        open_ = await page.evaluate(LEES)
        check("na een tik gaat het open", open_["open"], True)
        check("en zijn de cijfers zichtbaar", open_["zichtbaar"], True)

        # Het inklapbare deel mag ALLEEN de twee negens bevatten. Eerder liep het door tot
        # het einde van de kaart en klapte PCC & Dagresultaat mee weg — juist de regels
        # die je tijdens een ronde wilt zien. Daarom is dit nu een eigen kaart.
        inhoud = await page.evaluate("""() => {
            const kop = [...document.querySelectorAll('#sumInfo .more-toggle')]
                .find(e => /per negen/i.test(e.textContent));
            return kop.nextElementSibling.innerText
                .split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean);
        }""")
        check("er zit niets anders in dan de twee negens",
              [r for r in inhoud if 'PCC' in r or 'Sd' in r or 'Spelcondities' in r], [])
        check("en PCC & Dagresultaat blijft gewoon staan",
              await page.evaluate("""() => {
                  const t = document.getElementById('sumInfo').innerText;
                  return t.includes('Spelcondities') && t.includes('Voorlopig');
              }"""), True)

        # Een lijn links maakt zichtbaar tot waar het uitgeklapte deel loopt.
        rand = await page.evaluate("""() => {
            const kop = [...document.querySelectorAll('#sumInfo .more-toggle')]
                .find(e => /per negen/i.test(e.textContent));
            const st = getComputedStyle(kop.nextElementSibling);
            return { breedte: st.borderLeftWidth, inspring: st.paddingLeft };
        }""")
        check("het uitgeklapte deel heeft een lijn links", rand["breedte"], '2px')
        check("en springt in", rand["inspring"], '10px')
        await page.close()

        print("\n=== AGS EN PUTTS ===\n")
        # AGS staat er altijd (Marks keuze, 13527DA-145; eerder alleen als hij afweek van
        # bruto). Wijkt hij af, dan is het verschil precies wat de netto-dubbelbogey-
        # begrenzing wegnam — dus dat je op die lus holes hebt opgeblazen.
        # Putts alleen als je ze bijhoudt, net als in de sectie erboven.
        def metExtras(opgeblazen, putts):
            r = maakRonde(18)
            for k, h in enumerate(r["holes"]):
                if opgeblazen and k in (3, 4):
                    h["score"] = h["par"] + h["phcp"] + 5
                if putts:
                    h["putts"] = 2 if k % 3 else 3
            return r

        uit, _ = await paneel(metExtras(opgeblazen=True, putts=True))
        eerste, tweede = uit['eerste'][1], uit['tweede'][1]
        check("op de opgeblazen lus staat AGS erbij", 'Aangepast (AGS)' in eerste, True)
        check("en die is lager dan bruto",
              int(eerste['Aangepast (AGS)']) < int(eerste['Bruto (STR)'].split(' ')[0]), True)
        check("op de andere lus staat hij ook, gelijk aan bruto", tweede.get('Aangepast (AGS)'), tweede['Bruto (STR)'].split(' ')[0])
        check("putts staan er bij beide", ['Putts' in eerste, 'Putts' in tweede], [True, True])
        # Ook het gemiddelde per hole: bij een onvolledige lus zegt het totaal weinig,
        # want dan vergelijk je drie holes met negen.
        check("met het gemiddelde per hole erbij",
              ['Putts per hole' in eerste, 'Putts per hole' in tweede], [True, True])

        uit, _ = await paneel(metExtras(opgeblazen=False, putts=False))
        check("zonder uitschieters staat AGS er ook, gelijk aan bruto",
              uit['eerste'][1].get('Aangepast (AGS)'), uit['eerste'][1]['Bruto (STR)'].split(' ')[0])
        check("zonder putts geen puttregel", 'Putts' in uit['eerste'][1], False)
        check("en ook geen gemiddelde", 'Putts per hole' in uit['eerste'][1], False)

        # Een halve lus: het totaal loopt achter, het gemiddelde blijft vergelijkbaar.
        half = maakRonde(12)
        for k, h in enumerate(half["holes"]):
            if h["score"] is not None:
                h["putts"] = 2 if k % 3 else 3
        uit, _ = await paneel(half)
        putts = [h["putts"] for h in half["holes"][9:12]]
        check("de halve lus telt alleen zijn eigen putts",
              uit['tweede'][1].get('Putts'), str(sum(putts)))
        check("en het gemiddelde is over die holes",
              uit['tweede'][1].get('Putts per hole'),
              f"{sum(putts) / len(putts):.1f}".replace('.', '.'))

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
