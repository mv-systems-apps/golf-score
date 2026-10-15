"""Par en SI horen bij de TEE, niet bij de baan.

Deze test legt vast wat dat concreet betekent: twee tees op dezelfde baan met een
verschillende par en slagindex moeten twee verschillende rondes opleveren — andere
hole-pars, een andere persoonlijke par en een ander par-totaal. Ook wordt gecontroleerd
dat een baan die niet aan het model voldoet netjes wordt geweigerd bij het importeren.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import APP, app_url

# Eén baan, twee tees die ECHT verschillen: hole 3 is vanaf Rood een par 4 in plaats
# van een par 5, en de slagindex loopt anders. Precies het geval waarvoor dit model er is.
HOLES_HEREN = [{"par": p, "si": i + 1} for i, p in enumerate([4, 4, 5, 4, 3, 5, 4, 3, 4])]
HOLES_DAMES = [{"par": p, "si": s} for p, s in zip([4, 4, 4, 4, 3, 5, 4, 3, 4],
                                                   [2, 4, 6, 8, 10, 1, 3, 5, 7])]

CLUBS = {
    "Testclub": {
        "club": "Testclub", "shortName": "TC",
        "courses": {
            "Baan": {
                "holeIds": [f"H{i+1}" for i in range(9)],
                "tees": {
                    "Heren": {"Wit": {"CR": 35.0, "SR": 120, "holes": HOLES_HEREN}},
                    "Dames": {"Rood": {"CR": 36.0, "SR": 124, "holes": HOLES_DAMES}},
                },
            }
        },
    }
}


async def start_ronde(page, gender, tee):
    """Start een ronde vanaf de gekozen tee en geef de opgeslagen ronde terug."""
    return await page.evaluate("""([gender, tee]) => {
        sel.gender = gender;
        sel.tee = tee;
        sel.track = 'Baan';
        sel.chcpOverride = null;
        document.getElementById('iName').value = 'Tester';
        document.getElementById('iHcp').value = '18';
        startRoundConfirmed();
        return JSON.parse(localStorage.getItem('golf_rounds') || '[]')[0];
    }""", [gender, tee])


async def main():
    fouten = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(app_url())
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Testclub');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(350)

        heren = await start_ronde(page, 'Heren', 'Wit')
        await page.evaluate("() => localStorage.setItem('golf_rounds', '[]')")
        dames = await start_ronde(page, 'Dames', 'Rood')

        def check(naam, gekregen, verwacht):
            if gekregen != verwacht:
                fouten.append(f"{naam}: {gekregen!r} — verwacht {verwacht!r}")
                print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
            else:
                print(f"  ok   {naam}: {gekregen!r}")

        print("=== PAR EN SI PER TEE ===\n")
        check("par-totaal heren", heren["PAR"], sum(h["par"] for h in HOLES_HEREN))
        check("par-totaal dames", dames["PAR"], sum(h["par"] for h in HOLES_DAMES))
        check("hole-pars heren", [h["par"] for h in heren["holes"]],
              [h["par"] for h in HOLES_HEREN])
        check("hole-pars dames", [h["par"] for h in dames["holes"]],
              [h["par"] for h in HOLES_DAMES])
        check("slagindexen heren", [h["si"] for h in heren["holes"]],
              [h["si"] for h in HOLES_HEREN])
        check("slagindexen dames", [h["si"] for h in dames["holes"]],
              [h["si"] for h in HOLES_DAMES])
        check("holenamen komen van de baan", [h["id"] for h in dames["holes"]],
              CLUBS["Testclub"]["courses"]["Baan"]["holeIds"])
        # Persoonlijke par moet de par van DEZE tee volgen, niet die van de andere.
        check("persoonlijke par volgt de eigen hole-par",
              [h["ppar"] - h["phcp"] for h in dames["holes"]],
              [h["par"] for h in HOLES_DAMES])
        # De slagenverdeling hangt aan de SI van DEZE tee. Bij deze handicap vallen er
        # een paar extra slagen; die horen op de laagste slagindexen te landen — bij de
        # dames dus op andere holes dan bij de heren, want de SI loopt daar anders.
        def extra_slagen_op(ronde, tee_holes):
            phcps = [h["phcp"] for h in ronde["holes"]]
            top = max(phcps)
            gekregen = sorted(i for i, v in enumerate(phcps) if v == top)
            aantal = len(gekregen)
            laagste_si = sorted(range(len(tee_holes)), key=lambda i: tee_holes[i]["si"])[:aantal]
            return gekregen, sorted(laagste_si)

        check("extra slagen op de laagste SI (heren)", *extra_slagen_op(heren, HOLES_HEREN))
        check("extra slagen op de laagste SI (dames)", *extra_slagen_op(dames, HOLES_DAMES))

        print("\n=== BAANEDITOR: PER TEE BEWERKEN ===\n")
        await page.evaluate("""() => {
            editorClub = 'Testclub';
            document.getElementById('editorClubName').value = 'Testclub';
            document.getElementById('editorShortName').value = 'TC';
            openCourseEditor('Baan');
        }""")

        ed = await page.evaluate("""() => {
            const uit = {};
            uit.kiezer = Array.from(document.querySelectorAll('.hole-tee-btn')).map(b => b.textContent);
            uit.tabelHeren = readHolesFromEditor().map(h => [h.par, h.si]);
            kiesHoleTee(1);
            uit.tabelDames = readHolesFromEditor().map(h => [h.par, h.si]);
            // hole 1 vanaf de damestee een par 5 maken
            const rij = document.querySelectorAll('.hole-editor-row')[0];
            rij.querySelector('.par-cycle-btn').dataset.par = '5';
            updateAllTeeParDisplays();
            uit.parKolom = Array.from(document.querySelectorAll('.par-name-field')).map(e => e.dataset.value);
            kiesHoleTee(0);
            uit.herenNaWijzigingDames = readHolesFromEditor().map(h => [h.par, h.si]);
            uit.onopgeslagen = hasUnsavedCourseChanges();
            saveCourseFromEditor();
            uit.status = document.getElementById('editorStatus').textContent;
            const co = CLUBS['Testclub'].courses['Baan'];
            uit.opgeslagenHeren = co.tees.Heren.Wit.holes.map(h => [h.par, h.si]);
            uit.opgeslagenDames = co.tees.Dames.Rood.holes.map(h => [h.par, h.si]);
            uit.holeIds = co.holeIds;
            return uit;
        }""")

        check("teekiezer toont beide tees", ed["kiezer"], ["H · Wit", "D · Rood"])
        check("tabel toont de herentee", ed["tabelHeren"],
              [[h["par"], h["si"]] for h in HOLES_HEREN])
        check("wisselen toont de damestee", ed["tabelDames"],
              [[h["par"], h["si"]] for h in HOLES_DAMES])
        check("PAR-kolom per tee", ed["parKolom"],
              [str(sum(h["par"] for h in HOLES_HEREN)),
               str(sum(h["par"] for h in HOLES_DAMES) + 1)])
        check("herentee blijft ongemoeid", ed["herenNaWijzigingDames"],
              [[h["par"], h["si"]] for h in HOLES_HEREN])
        check("wijziging telt als niet opgeslagen", ed["onopgeslagen"], True)
        check("opslaan lukt", ed["status"], "Opgeslagen")
        check("opgeslagen herentee ongewijzigd", ed["opgeslagenHeren"],
              [[h["par"], h["si"]] for h in HOLES_HEREN])
        verwacht_dames = [[h["par"], h["si"]] for h in HOLES_DAMES]
        verwacht_dames[0] = [5, verwacht_dames[0][1]]
        check("opgeslagen damestee met de wijziging", ed["opgeslagenDames"], verwacht_dames)
        check("holenamen blijven van de baan", ed["holeIds"],
              CLUBS["Testclub"]["courses"]["Baan"]["holeIds"])

        # Een hole toevoegen hoort bij ALLE tees te gebeuren: anders lopen de lijsten
        # uit de pas en klopt de baan niet meer.
        lengtes = await page.evaluate("""() => {
            addOneHoleRow();
            const na = teeRows().map(r => r._holes.length);
            removeHoleRow({dataset:{confirm:'1'}, style:{}, classList:{add(){},remove(){}}});
            return { naToevoegen: na, naVerwijderen: teeRows().map(r => r._holes.length),
                     rijen: document.querySelectorAll('.hole-editor-row').length };
        }""")
        check("hole toevoegen geldt voor alle tees", lengtes["naToevoegen"], [10, 10])
        check("hole verwijderen geldt voor alle tees", lengtes["naVerwijderen"], [9, 9])
        check("tabel telt weer negen rijen", lengtes["rijen"], 9)

        print("\n=== STATUSREGEL EN GELIJKTREKKEN ===\n")
        st = await page.evaluate("""() => {
            const uit = {};
            const tekst = () => document.getElementById('holeTeeStatusText')?.textContent;
            const knoppen = () => Array.from(document.querySelectorAll('#holeTeeStatus button')).map(b => b.textContent);
            const stippen = () => document.querySelectorAll('.tee-afwijkend-stip').length;
            const gelijk = () => {
                const eerste = JSON.stringify(teeRows()[0]._holes);
                return teeRows().every(r => JSON.stringify(r._holes) === eerste);
            };

            // Begin: heren en dames verschillen (zo staat de testbaan erin)
            uit.begin = [tekst(), knoppen(), stippen()];

            // De rest aanpassen aan de getoonde tee, in twee tikken
            const b = document.getElementById('teeGelijkAllesBtn');
            trekAlleTeesGelijk(b);
            uit.naEersteTik = [tekst(), document.getElementById('teeGelijkMsg')?.className];
            trekAlleTeesGelijk(document.getElementById('teeGelijkAllesBtn'));
            uit.naTweedeTik = [tekst(), knoppen(), stippen(), gelijk()];

            // Tikfout in de SI op de tee die je bekijkt: die is dan de uitzondering.
            // Werkt ook bij precies twee tees — de getoonde tee is altijd het ijkpunt.
            kiesHoleTee(1);
            document.querySelectorAll('.hole-editor-row')[0].querySelector('.hole-si').value = '18';
            syncHoleTableNaarTee(); renderHoleTeeChooser();
            uit.uitzondering = [tekst(), knoppen()];

            // Herstellen haalt de waarden uit de rest, niet andersom
            const h = document.getElementById('teeHerstelBtn');
            herstelGetoondeTee(h);
            herstelGetoondeTee(document.getElementById('teeHerstelBtn'));
            uit.naHerstel = [tekst(), knoppen(), stippen(), gelijk()];

            // Verschil in par wordt apart benoemd
            document.querySelectorAll('.hole-editor-row')[0].querySelector('.par-cycle-btn').dataset.par = '6';
            updateAllTeeParDisplays();
            uit.parVerschil = tekst();
            return uit;
        }""")

        # Bij twee tees die verschillen is de getoonde tee het ijkpunt, dus staat de
        # andere er als afwijkend bij — herstellen van déze tee gaat dan voor.
        check("status bij verschil", st["begin"][0], "Par en SI van deze tee wijken af")
        check("herstel eerst, dan de rest", st["begin"][1],
              ["Deze tee herstellen", "De overige aanpassen"])
        check("stip bij de afwijkende tee", st["begin"][2], 1)
        check("eerste tik vraagt bevestiging", st["naEersteTik"][0],
              "Par en SI van deze tee wijken af")
        check("bevestigingsmelding zichtbaar", "hidden" in (st["naEersteTik"][1] or ""), False)
        check("na bevestigen alles gelijk", st["naTweedeTik"][0], "Alle 2 tees zijn gelijk")
        check("geen knoppen meer nodig", st["naTweedeTik"][1], [])
        check("geen stippen meer", st["naTweedeTik"][2], 0)
        check("hole-lijsten echt gelijk", st["naTweedeTik"][3], True)
        check("getoonde tee als enige afwijkend", st["uitzondering"][0],
              "De SI van deze tee wijkt af")
        check("herstel staat vooraan", st["uitzondering"][1],
              ["Deze tee herstellen", "De overige aanpassen"])
        check("herstel maakt alles weer gelijk", st["naHerstel"][3], True)
        check("par apart benoemd", st["parVerschil"], "De par van deze tee wijkt af")

        # Het restgeval: meerdere tees verschillen zonder duidelijk patroon. Enkelvoud
        # en meervoud worden apart geformuleerd.
        telling = await page.evaluate("""() => {
            const tekst = () => document.getElementById('holeTeeStatusText')?.textContent;
            const uit = {};
            addTeeRow(); addTeeRow();               // drie tees, alle gelijk aan de getoonde
            teeRows()[1]._holes = teeRows()[1]._holes.map((h, i) => i === 0 ? {par: 6, si: h.si} : h);
            renderHoleTeeChooser();
            uit.een = tekst();
            teeRows()[2]._holes = teeRows()[2]._holes.map((h, i) => i === 1 ? {par: 6, si: h.si} : h);
            renderHoleTeeChooser();
            uit.meer = tekst();
            return uit;
        }""")
        check("enkelvoud", telling["een"], "De par van 1 tee wijkt af")
        check("meervoud met totaal", telling["meer"], "De par van 2 van 4 tees wijkt af")

        print("\n=== RANDGEVALLEN ===\n")
        rand = await page.evaluate("""() => {
            const uit = {};
            const open = (n) => {
                editorClub = 'Testclub';
                document.getElementById('editorClubName').value = 'Testclub';
                document.getElementById('editorShortName').value = 'TC';
                openCourseEditor(n);
            };

            // Een tweede baan met een ANDER aantal holes en andere namen. Bij het openen
            // daarvan mogen de holenamen van de vorige baan niet blijven staan.
            CLUBS['Testclub'].courses['Kort'] = {
                holeIds: ['K1', 'K2', 'K3'],
                tees: { Heren: { Wit: { CR: 27, SR: 90,
                        holes: [{par:3,si:1},{par:3,si:2},{par:3,si:3}] } } }
            };
            rebuildCourseLookup();
            open('Baan');
            open('Kort');
            uit.tweedeBaan = readHolesFromEditor().map(h => h.id);

            // En terug: de namen van de eerste baan horen weer te verschijnen
            open('Baan');
            uit.terug = readHolesFromEditor().map(h => h.id);

            // Verwijder je de tee die in de tabel staat, dan moet de tabel de tee tonen
            // waar de kiezer op terugvalt — niet de waarden van de verdwenen tee.
            open('Baan');
            const laatste = teeRows().length - 1;
            kiesHoleTee(laatste);
            const vanVerwijderde = readHolesFromEditor().map(h => h.par);
            removeLastTeeRow({dataset:{confirm:'1'}, style:{}, classList:{add(){}, remove(){}}});
            uit.naVerwijderen = {
                tabel: readHolesFromEditor().map(h => h.par),
                hoortBij: (editorHoleTeeRow?._holes || []).map(h => h.par),
                wasVanVerwijderde: vanVerwijderde,
            };
            return uit;
        }""")

        check("tweede baan toont eigen holenamen", rand["tweedeBaan"], ["K1", "K2", "K3"])
        check("terug naar de eerste baan", rand["terug"],
              CLUBS["Testclub"]["courses"]["Baan"]["holeIds"])
        check("tabel volgt de kiezer na verwijderen",
              rand["naVerwijderen"]["tabel"], rand["naVerwijderen"]["hoortBij"])

        print("\n=== BAANANALYSE BIJ WISSELENDE PAR ===\n")
        ca = await page.evaluate("""() => {
            // Twee rondes op dezelfde baan: één vanaf een tee waar hole 1 een par 4 is,
            // één vanaf een tee waar diezelfde hole een par 5 is.
            const maakRonde = (id, datum, pars) => ({
                id, date: datum, time: '09:30', player: 'Tester', hcp: 18,
                club: 'Testclub', clubShort: 'TC', track: 'Baan', gender: 'Heren',
                tee: 'Wit', CR: 35, SR: 120, PAR: pars.reduce((s, p) => s + p, 0),
                chcp: 18, qualifying: true, total: 50, totalStb: 18, playedCount: 9,
                holesCount: 9, currentHole: 0, started: true, sd: 30, sdFinal: 30, pcc: 0,
                holes: pars.map((par, i) => ({ id: 'H' + (i + 1), par, si: i + 1,
                    phcp: 1, ppar: par + 1, score: par + 1 })),
            });
            const basis = [4, 4, 5, 4, 3, 5, 4, 3, 4];
            const anders = [5, 4, 5, 4, 3, 5, 4, 3, 4];
            localStorage.setItem('golf_rounds', JSON.stringify([
                maakRonde(101, '2026-08-10', basis),
                maakRonde(102, '2026-08-01', anders),
            ]));
            localStorage.setItem('golf_profile_name', 'Tester');

            const data = courseAnalysisData('Testclub', 'Baan');
            window._caBlocks = { proef: data };
            if (!document.getElementById('caDetail_proef')) {
                document.body.insertAdjacentHTML('beforeend', '<div id="caDetail_proef"></div>');
            }
            caShowHole('proef', 0);
            const eerste = document.getElementById('caDetail_proef').textContent;
            caShowHole('proef', 1);
            const tweede = document.getElementById('caDetail_proef').textContent;
            const legenda = Array.from(document.querySelectorAll('span'))
                .some(e => (e.textContent || '').startsWith('Baananalyse: op deze hole'));
            return {
                markeringen: data.holes.map(h => !!h.parWisselt),
                getoondePar: data.holes[0].par,
                eersteRegel: eerste,
                tweedeRegel: tweede,
                legenda,
            };
        }""")

        check("alleen de wisselende hole gemarkeerd", ca["markeringen"],
              [True, False, False, False, False, False, False, False, False])
        # De rondes staan nieuwste eerst, dus het getoonde getal komt van de laatste ronde.
        check("par van de meest recente ronde", ca["getoondePar"], 4)
        check("sterretje bij wisselende par", "(par 4*)" in ca["eersteRegel"], True)
        check("geen sterretje bij vaste par", "*" in ca["tweedeRegel"], False)
        check("uitleg staat in de symbolenlijst", ca["legenda"], True)

        print("\n=== BESCHADIGDE GEGEVENS EN EXPORT ===\n")
        robuust = await page.evaluate("""async () => {
            const uit = {};
            // Een tee waarvan de hole-lijst korter is dan de baan. Kan niet ontstaan via
            // de editor of import, maar wel door geknoei in de opslag — dan hoort de app
            // een nette melding te geven in plaats van halverwege om te vallen.
            CLUBS['Testclub'].courses['Scheef'] = {
                holeIds: ['S1', 'S2', 'S3'],
                tees: { Heren: { Wit: { CR: 30, SR: 100, holes: [{par:4, si:1}] } } }
            };
            rebuildCourseLookup();
            localStorage.setItem('golf_rounds', '[]');
            sel.track = 'Scheef'; sel.gender = 'Heren'; sel.tee = 'Wit';
            document.getElementById('iName').value = 'Tester';
            document.getElementById('iHcp').value = '18';
            let fout = null;
            try { startRoundConfirmed(); } catch (e) { fout = e.message; }
            uit.crash = fout;
            uit.rondeGemaakt = JSON.parse(localStorage.getItem('golf_rounds') || '[]').length;
            delete CLUBS['Testclub'].courses['Scheef'];
            rebuildCourseLookup();

            // Export van één club moet het nieuwe model wegschrijven en weer inleesbaar zijn
            const origCreate = URL.createObjectURL;
            let blob = null;
            URL.createObjectURL = (b) => { blob = b; return origCreate.call(URL, b); };
            const houder = document.createElement('div');
            document.body.appendChild(houder);
            const knop = document.createElement('button');
            knop.dataset.confirm = '1';
            houder.appendChild(knop);
            await exportClub('Testclub', knop);
            URL.createObjectURL = origCreate;
            if (blob) {
                const data = JSON.parse(await blob.text());
                const baan = data.courses['Baan'];
                uit.exportVelden = Object.keys(baan).sort();
                uit.exportTeeVelden = Object.keys(baan.tees.Heren.Wit).sort();
                uit.exportOpnieuwGeldig = validateImportedClubData(data) === null;
            }
            return uit;
        }""")

        check("geen crash bij onvolledige tee", robuust["crash"], None)
        check("en ook geen halve ronde", robuust["rondeGemaakt"], 0)
        check("export van één club: baanvelden", robuust.get("exportVelden"),
              ["holeIds", "tees"])
        check("export van één club: teevelden", robuust.get("exportTeeVelden"),
              ["CR", "SR", "holes"])
        check("export is weer inleesbaar", robuust.get("exportOpnieuwGeldig"), True)

        print("\n=== SLAGINDEX: LEEG OF BUITEN BEREIK ===\n")
        si = await page.evaluate("""() => {
            const uit = {};
            editorClub = 'Testclub';
            document.getElementById('editorClubName').value = 'Testclub';
            document.getElementById('editorShortName').value = 'TC';
            openCourseEditor('Baan');
            const veld = () => document.querySelectorAll('.hole-si')[0];
            const keur = () => { try { validateCourseInput(); return null; } catch (e) { return e.message; } };

            veld().value = '';
            uit.leeg = keur();
            veld().value = '0';
            uit.nul = keur();
            veld().value = '19';
            uit.negentien = keur();
            veld().value = '13';
            uit.geldig = keur();

            // Een leeg veld blijft leeg — ook na wisselen van tee. Vroeger werd hier
            // stilzwijgend het holenummer ingevuld, waarna de fout verderop als
            // 'dubbele SI' opdook zonder dat je de oorzaak zag.
            veld().value = '';
            syncHoleTableNaarTee();
            kiesHoleTee(1);
            kiesHoleTee(0);
            uit.blijftLeeg = veld().value;
            uit.geenNullInBeeld = !document.getElementById('editorHoles').innerHTML.includes('"null"');
            return uit;
        }""")

        check("leeg veld vraagt om invullen", si["leeg"],
              'Vul SI in voor Tee "Wit", hole "H1"')
        check("SI 0 meldt het bereik", si["nul"],
              'SI 0 buiten bereik (1–18) voor Tee "Wit", hole "H1"')
        check("SI 19 meldt het bereik", si["negentien"],
              'SI 19 buiten bereik (1–18) voor Tee "Wit", hole "H1"')
        check("geldige SI komt erdoor", si["geldig"], None)
        check("leeg blijft leeg na wisselen", si["blijftLeeg"], "")
        check("geen 'null' in beeld", si["geenNullInBeeld"], True)

        print("\n=== OPSLAAN MISLUKT ===\n")
        vol = await page.evaluate("""() => {
            // Bij een volle opslag mag de editor geen "Opgeslagen" melden: de wijziging
            // staat dan alleen in het geheugen en is bij de volgende start weg.
            const origineel = Storage.prototype.setItem;
            Storage.prototype.setItem = function (k, v) {
                if (k === 'golf_clubs') {
                    const e = new Error('QuotaExceededError');
                    e.name = 'QuotaExceededError';
                    throw e;
                }
                return origineel.call(this, k, v);
            };
            let melding;
            try {
                editorClub = 'Testclub';
                document.getElementById('editorClubName').value = 'Testclub';
                document.getElementById('editorShortName').value = 'TC';
                openCourseEditor('Baan');
                document.querySelectorAll('.hole-editor-row')[0]
                    .querySelector('.par-cycle-btn').dataset.par = '3';
                updateAllTeeParDisplays();
                saveCourseFromEditor();
                melding = document.getElementById('editorStatus').textContent;
            } finally {
                Storage.prototype.setItem = origineel;
            }
            return melding;
        }""")
        check("volle opslag wordt gemeld", vol,
              "Opslaan mislukt — geheugen vol of geblokkeerd")

        print("\n=== WIJZIGING IN EEN ANDER TABBLAD ===\n")
        ander = await page.evaluate("""() => {
            const uit = {};
            openCourseEditor('Baan');
            // Doen alsof een ander tabblad de clubgegevens heeft weggeschreven
            clubsGewijzigdElders = true;
            document.querySelectorAll('.hole-editor-row')[0]
                .querySelector('.par-cycle-btn').dataset.par = '6';
            updateAllTeeParDisplays();
            const parVoor = CLUBS['Testclub'].courses['Baan'].tees.Heren.Wit.holes[0].par;
            saveCourseFromEditor();
            uit.vraagt = !document.getElementById('confirmModal').classList.contains('hidden');
            uit.titel = document.getElementById('confirmModalTitle').textContent;
            uit.knop = document.getElementById('confirmModalBtn').textContent;
            uit.nogNietOpgeslagen =
                CLUBS['Testclub'].courses['Baan'].tees.Heren.Wit.holes[0].par === parVoor;
            document.getElementById('confirmModalBtn').click();   // Toch opslaan
            uit.naBevestigen = CLUBS['Testclub'].courses['Baan'].tees.Heren.Wit.holes[0].par;
            uit.vlagGewist = clubsGewijzigdElders === false;
            return uit;
        }""")

        check("opslaan vraagt eerst om bevestiging", ander["vraagt"], True)
        check("met een duidelijke titel", ander["titel"], "Bijgewerkt in ander tabblad")
        check("en een knop die zegt wat hij doet", ander["knop"], "Toch opslaan")
        check("nog niets overschreven", ander["nogNietOpgeslagen"], True)
        check("na bevestigen wel opgeslagen", ander["naBevestigen"], 6)
        check("de waarschuwing komt niet nog eens", ander["vlagGewist"], True)

        print("\n=== IMPORT WEIGERT WAT NIET AAN HET MODEL VOLDOET ===\n")
        gevallen = [
            ("tee zonder holes",
             {"club": "X", "courses": {"B": {"holeIds": ["H1"],
              "tees": {"Heren": {"Wit": {"CR": 35, "SR": 120}}}}}}),
            ("holes tellen niet op met holeIds",
             {"club": "X", "courses": {"B": {"holeIds": ["H1", "H2"],
              "tees": {"Heren": {"Wit": {"CR": 35, "SR": 120,
                                          "holes": [{"par": 4, "si": 1}]}}}}}}),
            ("dubbele SI binnen een tee",
             {"club": "X", "courses": {"B": {"holeIds": ["H1", "H2"],
              "tees": {"Heren": {"Wit": {"CR": 35, "SR": 120,
                                          "holes": [{"par": 4, "si": 1},
                                                    {"par": 4, "si": 1}]}}}}}}),
            ("baan zonder holeIds",
             {"club": "X", "courses": {"B": {
              "tees": {"Heren": {"Wit": {"CR": 35, "SR": 120,
                                          "holes": [{"par": 4, "si": 1}]}}}}}}),
        ]
        for naam, data in gevallen:
            melding = await page.evaluate("(d) => validateImportedClubData(d)", data)
            if melding:
                print(f"  ok   {naam} — geweigerd: {melding}")
            else:
                fouten.append(f"{naam}: werd geaccepteerd")
                print(f" FOUT  {naam}: werd geaccepteerd")

        goed = await page.evaluate("(d) => validateImportedClubData(d)",
                                    CLUBS["Testclub"])
        if goed:
            fouten.append(f"geldige club geweigerd: {goed}")
            print(f" FOUT  geldige club werd geweigerd: {goed}")
        else:
            print("  ok   geldige club wordt geaccepteerd")

        await browser.close()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
