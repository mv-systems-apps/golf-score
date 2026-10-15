"""Welke opslag is dit?

De browser houdt gegevens apart per adres én per browserprofiel. Sta je voor een lege
app, dan kan dat een eerste installatie zijn — of hetzelfde adres in een ander profiel,
met je rondes veilig op de andere plek. De app kan dat verschil niet zien, dus maakt hij
zichtbaar in wélke opslag je zit:

  * een code die bij de eerste start wordt aangemaakt en nooit meer verandert
  * een naam die je zelf kunt geven en op elk moment kunt wijzigen
  * een eenmalige vraag zodra de opslag leeg is
  * de code in de naam van elk backupbestand, met een melding bij importeren uit elders

De vergelijking gaat altijd op de CODE, nooit op de naam: hernoemen mag geen oude
backups ineens "van elders" laten lijken.
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

        print("=== LEGE OPSLAG ===\n")
        await page.evaluate("() => localStorage.clear()")
        await page.reload()
        await page.wait_for_timeout(1400)
        eerste = await page.evaluate("""() => ({
            gemeld: !document.getElementById('confirmModal').classList.contains('hidden'),
            titel: document.getElementById('confirmModalTitle').textContent,
            noemtOpslag: /Deze installatie:/.test(document.getElementById('confirmModalMessage').textContent),
            code: localStorage.getItem('golf_storage_id'),
        })""")
        check("bij een lege opslag volgt een melding", eerste["gemeld"], True)
        check("met een duidelijke titel", eerste["titel"], "Geen gegevens gevonden")
        check("en de installatie wordt genoemd", eerste["noemtOpslag"], True)
        check("er is een code aangemaakt", len(eerste["code"] or ''), 4)

        # De melding hoort maar één keer te komen; anders is hij bij elke start in de weg.
        await page.evaluate("() => closeConfirmModal()")
        await page.reload()
        await page.wait_for_timeout(1400)
        nogmaals = await page.evaluate("""() =>
            !document.getElementById('confirmModal').classList.contains('hidden')""")
        check("en komt niet nog een keer", nogmaals, False)

        # Staan er wél gegevens, dan is er niets aan de hand en komt er GEEN melding.
        # Hier stond een vraag om deze opslag een naam te geven, met een adres om op je
        # beginscherm te zetten. Dat suggereerde dat je met dat adres je opslag KOOS —
        # en dat is niet zo: welke gegevens je ziet volgt uit het browserprofiel.
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(1400)
        metClubs = await page.evaluate("""() =>
            !document.getElementById('confirmModal').classList.contains('hidden')""")
        check("met gegevens geen melding", metClubs, False)

        print("\n=== DE OPSLAGCODE ===\n")
        # Er is bewust GEEN eigen naam per opslag meer: het kenmerk uit de koppeling doet
        # dat werk al, en beter — dat gaat vanzelf af zodra je ergens anders binnenkomt.
        code = await page.evaluate("() => opslagCode()")
        regel = await page.evaluate("""() => {
            nav('settings');
            toonOpslagRegel();
            return document.getElementById('opslagRegel').textContent;
        }""")
        check("de code staat onderaan Instellingen", regel, f"Deze installatie · code {code}")

        metKenmerk = await page.evaluate("""() => {
            zetKenmerk('hoofd');
            return document.getElementById('opslagRegel').textContent;
        }""")
        check("met kenmerk staat dat erbij", metKenmerk, f"Deze installatie: hoofd · code {code}")

        # De code blijft dezelfde, wat je ook met het kenmerk doet.
        naWijziging = await page.evaluate("""() => {
            zetKenmerk('test');
            return { code: opslagCode(),
                     regel: document.getElementById('opslagRegel').textContent };
        }""")
        check("de code verandert niet mee", naWijziging["code"], code)
        check("het kenmerk wel", naWijziging["regel"], f"Deze installatie: test · code {code}")
        await page.evaluate("() => zetKenmerk('hoofd')")

        print("\n=== BACKUPBESTANDEN ===\n")
        # Kenmerk zetten en het venster leegmaken: anders staat de startvraag nog open en
        # wacht de opslagmelding daar netjes op (zie 'verdringt niets' hieronder).
        await page.evaluate("""() => { zetKenmerk('hoofd'); closeConfirmModal(); }""")
        # De code hoort achteraan de bestandsnaam, zodat je hem in de bestandkiezer ziet.
        # De herkomst is geen los venster meer: hij staat als zin in het keuzevenster en
        # in de waarschuwing bij vervangen — daar valt de beslissing.
        meldingen = await page.evaluate("""(eigenCode) => ({
            anders: andereOpslagCode('rondes_backup_20260827_(ZZ99).json'),
            eigen: andereOpslagCode('rondes_backup_20260827_(' + eigenCode + ').json'),
            zonderCode: andereOpslagCode('rondes_backup_20260825.json'),
        })""", code)
        check("bestand van elders wordt herkend", meldingen["anders"], 'ZZ99')
        check("eigen bestand geeft niets", meldingen["eigen"], None)
        check("bestand zonder code ook niet", meldingen["zonderCode"], None)

        # Een ander kenmerk mag een eigen bestand niet ineens vreemd maken: de
        # vergelijking gaat op de opslagcode, niet op het kenmerk.
        naWijzigen = await page.evaluate("""(eigenCode) => {
            zetKenmerk('heel-ander-kenmerk');
            const uit = andereOpslagCode('rondes_backup_20260827_' + eigenCode + '.json');
            zetKenmerk('hoofd');
            return uit;
        }""", code)
        check("na een ander kenmerk blijft het eigen bestand eigen", naWijzigen, None)

        print("\n=== RANDGEVALLEN BIJ HET KENMERK ===\n")
        randen = await page.evaluate("""() => {
            const uit = { code: opslagCode() };
            zetKenmerk('   ');                  // alleen spaties telt als geen kenmerk
            uit.naSpaties = localStorage.getItem('golf_opslag_kenmerk');
            zetKenmerk('x'.repeat(60));         // te lang wordt afgekapt
            uit.lengte = (localStorage.getItem('golf_opslag_kenmerk') || '').length;
            zetKenmerk('<b>stout</b>');         // geen HTML in de regel
            uit.geenHtml = !document.getElementById('opslagRegel').querySelector('b');
            zetKenmerk('hoofd');
            return uit;
        }""")
        check("alleen spaties telt als geen kenmerk", randen["naSpaties"], None)
        check("kenmerk wordt afgekapt op 16 tekens", randen["lengte"], 16)
        check("geen HTML in de regel", randen["geenHtml"], True)

        # Alles wissen mag de code NIET weggooien: die hoort bij de plek, niet bij de
        # gegevens. En de vraag "zit je in een ander profiel?" hoort dan niet te komen —
        # je hebt zojuist zelf alles gewist.
        voorReset = await page.evaluate("() => opslagCode()")
        await page.evaluate("() => { zetKenmerk('hoofd'); doResetAll(); }")
        await page.wait_for_timeout(500)
        # Openen zoals je normaal doet: via de vaste koppeling.
        await page.goto(app_url() + '?opslag=hoofd')
        await page.wait_for_timeout(1400)
        naReset = await page.evaluate("""() => ({
            code: localStorage.getItem('golf_storage_id'),

            kenmerk: localStorage.getItem('golf_opslag_kenmerk'),
            melding: !document.getElementById('confirmModal').classList.contains('hidden'),
        })""")
        check("code overleeft 'alles wissen'", naReset["code"], voorReset)

        check("kenmerk overleeft 'alles wissen'", naReset["kenmerk"], "hoofd")
        check("geen valse vraag na zelf wissen", naReset["melding"], False)

        # Het blok 'de melding verdringt niets' is vervallen: de herkomst is geen los
        # venster meer, maar een zin in het keuzevenster en in de waarschuwing bij
        # vervangen — daar waar de beslissing valt.

        print("\n=== DE NAAM IS EEN ETIKET, GEEN KEUZE ===\n")
        # Hier stond een heel stelsel rond ?opslag= in het adres, met waarschuwingen als
        # je zonder die parameter binnenkwam. Dat is eruit: het adres bepaalt NIET welke
        # gegevens je ziet — dat volgt uit het browserprofiel waarin de app draait. Een
        # geïnstalleerde app start bovendien op het start_url uit het manifest, zonder
        # parameter, dus de waarschuwing sloeg juist aan als alles goed was.
        # Wat blijft: een naam die je zelf instelt, puur als etiket.

        async def startMet(kenmerk, leeg, adres=''):
            await page.evaluate("""([clubs, k, leeg]) => {
                localStorage.clear();
                if (!leeg) {
                    localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                    localStorage.setItem('golf_default_club', 'Testclub');
                }
                if (k) localStorage.setItem('golf_opslag_kenmerk', k);
            }""", [CLUBS, kenmerk, leeg])
            await page.goto(app_url() + adres)
            await page.wait_for_timeout(1300)
            return await page.evaluate("""() => {
                const m = document.getElementById('confirmModal');
                return {
                    open: !m.classList.contains('hidden'),
                    titel: document.getElementById('confirmModalTitle').textContent,
                    kenmerk: localStorage.getItem('golf_opslag_kenmerk'),
                };
            }""")

        # Gegevens aanwezig: nooit een melding, met of zonder naam, met of zonder
        # parameter in het adres.
        check("met gegevens en een naam: geen melding",
              (await startMet('hoofd', False))["open"], False)
        check("met gegevens zonder naam: ook niet",
              (await startMet('', False))["open"], False)
        oud = await startMet('hoofd', False, '?opslag=test')
        check("een oud adres met ?opslag= wordt genegeerd", oud["open"], False)
        check("en verandert de naam niet", oud["kenmerk"], 'hoofd')

        # LEEG is het enige geval dat telt: dan lijkt het alsof je rondes weg zijn.
        leegMetNaam = await startMet('hoofd', True)
        check("leeg: wel een melding", leegMetNaam["titel"], 'Geen gegevens gevonden')
        check("de naam blijft staan", leegMetNaam["kenmerk"], 'hoofd')
        await page.evaluate("() => closeConfirmModal()")

        check("leeg zonder naam (eerste keer): dezelfde melding",
              (await startMet('', True))["titel"], 'Geen gegevens gevonden')
        await page.evaluate("() => closeConfirmModal()")

        # En die melding komt maar één keer.
        await page.reload()
        await page.wait_for_timeout(1300)
        check("en niet bij elke start opnieuw",
              await page.evaluate("""() =>
                  !document.getElementById('confirmModal').classList.contains('hidden')"""),
              False)


        print("\n=== DE SECTIE OPSLAG IN INSTELLINGEN ===\n")
        blok = await page.evaluate("""() => {
            localStorage.removeItem('golf_opslag_kenmerk');
            nav('settings');
            switchSettingsTab('data');
            openSectie('settingsTabData|Opslaglocatie', 'opslagCard');
            toonOpslagRegel();
            const zichtbaar = id => !document.getElementById(id).classList.contains('hidden');
            const uit = {
                secties: [...document.querySelectorAll('[data-section-key]')]
                    .filter(k => k.dataset.sectionKey.startsWith('settingsTabData'))
                    .map(k => k.dataset.sectionKey.split('|')[1]),
                code: document.getElementById('opslagCodeTekst').textContent,
                // Het adres met ?opslag= en de kopieerknop zijn eruit: het adres bepaalt
                // niet welke gegevens je ziet, en dat suggereerde het wel.
                adresWeg: !document.getElementById('opslagLinkRegel'),
                kopieerWeg: !document.getElementById('opslagKopieerBtn'),
                knopVoor: document.getElementById('opslagKenmerkBtn').textContent,
                uitlegVoor: document.getElementById('opslagKenmerkUitleg').textContent,
            };
            zetKenmerk('hoofd');

            uit.knopNa = document.getElementById('opslagKenmerkBtn').textContent;
            const u = document.getElementById('opslagKenmerkUitleg');
            uit.uitlegNa = u.textContent;
            uit.naamVet = u.querySelector('b') ? u.querySelector('b').textContent : null;
            zetKenmerk('test');
            uit.uitlegAndereNaam = u.textContent;
            uit.naamVetAndere = u.querySelector('b') ? u.querySelector('b').textContent : null;
            uit.aantalVet = u.querySelectorAll('b').length;
            zetKenmerk('hoofd');
            return uit;
        }""")

        check("Exporteren staat vooraan op de Gegevens-tab", blok["secties"][0], "Exporteren")
        check("de vijf secties in volgorde", blok["secties"],
              ["Exporteren", "Importeren", "Deze installatie", "Opruimen & resetten",
               "Over Golf Score"])
        check("de opslagcode staat erbij", len(blok["code"]), 4)

        check("er staat geen adres meer", blok["adresWeg"], True)
        check("en geen kopieerknop", blok["kopieerWeg"], True)
        check("de knop nodigt uit een naam te geven", blok["knopVoor"], "Naam geven")
        check("en de uitleg zegt waar de naam voor is",
              'nog geen naam' in blok["uitlegVoor"], True)

        check("de knop wordt wijzigen", blok["knopNa"], "Naam wijzigen")
        check("de uitleg noemt de naam, de code en wat het betekent",
              blok["uitlegNa"],
              f"Deze installatie heet hoofd (code {blok['code']}). "
              "Elke installatie heeft zijn eigen rondes en clubs.")
        check("de naam staat vet", blok["naamVet"], "hoofd")
        # Wijzigt de naam, dan hoort de zin mee te veranderen — en niet een tweede
        # vetgedrukte naam achter te laten.
        check("de zin volgt een naamswijziging", blok["uitlegAndereNaam"],
              f"Deze installatie heet test (code {blok['code']}). "
              "Elke installatie heeft zijn eigen rondes en clubs.")
        check("ook vet", blok["naamVetAndere"], "test")
        check("en maar één keer", blok["aantalVet"], 1)

        print("\n=== RANDGEVALLEN VAN HET ADRES EN DE BESTANDSNAAM ===\n")
        await page.evaluate("() => zetKenmerk('hoofd')")

        # Hoofdletters horen niet uit te maken: "Hoofd" is dezelfde locatie als "hoofd".
        # Anders geeft een adres met een hoofdletter een vals alarm.
        hoofdletters = {}
        for q in ['?opslag=Hoofd', '?opslag=HOOFD', '?opslag=hoofd']:
            await page.evaluate("""(k) => localStorage.setItem('golf_opslag_kenmerk', k)""", 'hoofd')
            await page.goto(app_url() + q)
            await page.wait_for_timeout(1200)
            hoofdletters[q] = await page.evaluate("""() =>
                !document.getElementById('confirmModal').classList.contains('hidden')""")
        check("hoofdletters maken niet uit", list(hoofdletters.values()), [False, False, False])

        # De bestandsnaamcontrole mag ALLEEN aanslaan op bestanden die de app zelf maakt.
        # Eerder keek hij naar de laatste vier tekens voor .json, en dan sloeg hij ook aan
        # op "mijn_data.json" — daar leek "data" een code.
        # De code wordt binnen een sessie onthouden (zie 'de code blijft dezelfde'),
        # dus na het zetten van een vaste code even opnieuw laden.
        await page.evaluate("""() => { localStorage.setItem('golf_storage_id', 'ZMVA');
                                        localStorage.setItem('golf_opslag_kenmerk', 'hoofd'); }""")
        await page.goto(app_url() + '?opslag=hoofd')
        await page.wait_for_timeout(1200)
        await page.evaluate("() => closeConfirmModal()")
        namen = {}
        for naam in ['mijn_data.json', 'backup_kopie.json',
                     'rondes_backup_20260827_(AAAA).json',
                     'rondes_backup_20260827_(AAAA) (1).json',
                     'rondes_backup_20260827_ZMVA.json',
                     'Golfclub_Heelsum_202608271530.json']:
            namen[naam] = await page.evaluate(
                "(n) => andereOpslagCode(n) !== null", naam)

        check("gewoon bestand geeft geen vals alarm", namen['mijn_data.json'], False)
        check("ander gewoon bestand ook niet", namen['backup_kopie.json'], False)
        check("clubexport geeft geen vals alarm", namen['Golfclub_Heelsum_202608271530.json'], False)
        check("backup van elders wordt gemeld", namen['rondes_backup_20260827_(AAAA).json'], True)
        check("ook een kopie van elders", namen['rondes_backup_20260827_(AAAA) (1).json'], True)
        check("eigen backup niet", namen['rondes_backup_20260827_ZMVA.json'], False)

        # De kerngegevens mogen door dit alles niet worden geraakt.
        await page.evaluate("""(clubs) => {
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_opslag_kenmerk', 'hoofd');
        }""", CLUBS)
        await page.goto(app_url())
        await page.wait_for_timeout(1200)
        heel = await page.evaluate("""() => ({
            gewaarschuwd: !document.getElementById('confirmModal').classList.contains('hidden'),
            clubs: Object.keys(CLUBS || {}).length,
            kenmerk: bekendKenmerk(),
        })""")
        # Er zijn gegevens, dus geen melding — ook zonder iets in het adres.
        check("geen melding bij aanwezige gegevens", heel["gewaarschuwd"], False)
        check("en de clubs blijven ongemoeid", heel["clubs"], 1)
        check("net als het kenmerk", heel["kenmerk"], "hoofd")

        print("\n=== VOORRANG BIJ ONLEESBARE GEGEVENS ===\n")
        # Als de rondes onleesbaar zijn, is DAT de belangrijkste melding. De vraag via
        # welk adres je binnenkwam mag daar niet overheen komen: dan zie je de ernstigste
        # melding nooit, terwijl die vertelt hoe je je gegevens terugkrijgt.
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', '{kapot');
            localStorage.setItem('golf_opslag_kenmerk', 'hoofd');
        }""", CLUBS)
        await page.goto(app_url())      # zonder kenmerk: zou anders waarschuwen
        await page.wait_for_timeout(1500)
        voorrang = await page.evaluate("""() => ({
            titel: document.getElementById('confirmModalTitle').textContent,
            zichtbaar: !document.getElementById('confirmModal').classList.contains('hidden'),
        })""")
        check("de ernstigste melding staat vooraan", voorrang["titel"], "Gegevens niet leesbaar")
        check("en is zichtbaar", voorrang["zichtbaar"], True)

        # Zodra die is weggeklikt, mag de opslagwaarschuwing alsnog komen.
        erna = await page.evaluate("""async () => {
            closeConfirmModal();
            await new Promise(r => setTimeout(r, 1200));
            return { titel: document.getElementById('confirmModalTitle').textContent,
                     zichtbaar: !document.getElementById('confirmModal').classList.contains('hidden') };
        }""")
        # Na het sluiten van de leesfoutmelding komt er niets meer overheen.
        check("daarna komt er geen tweede melding", erna["titel"] != 'Deze gegevens zijn onleesbaar', True)

        print("\n=== DE CODE BLIJFT DEZELFDE ===\n")
        # Lukt het wegschrijven niet (opslag vol of geblokkeerd), dan mag de code niet bij
        # elke aanroep opnieuw geloot worden: de code in Instellingen, die in je
        # backupbestandsnaam en die in de controle zouden dan verschillen, en je eigen
        # backups zouden als "van elders" worden gemeld.
        stabiel = await page.evaluate("""() => {
            const echt = Storage.prototype.setItem;
            Storage.prototype.setItem = function () { throw new Error('vol'); };
            localStorage.removeItem('golf_storage_id');
            const a = opslagCode(), b = opslagCode(), c = opslagCode();
            Storage.prototype.setItem = echt;
            return { a, b, c };
        }""")
        check("ook zonder werkende opslag steeds dezelfde code",
              [stabiel["a"], stabiel["b"], stabiel["c"]],
              [stabiel["a"], stabiel["a"], stabiel["a"]])

        print("\n=== HET EERSTE SCHERM VAN EEN NIEUWE GEBRUIKER ===\n")
        # Zonder clubs opent de app op het clubscherm. Alleen "Geen clubs" laat een
        # nieuwe gebruiker raden wat hij moet doen; er horen twee wegen te staan, met
        # dezelfde symbolen als op de knoppen erboven.
        await page.evaluate("() => localStorage.clear()")
        await page.goto(app_url() + '?opslag=hoofd')
        await page.wait_for_timeout(1500)
        await page.evaluate("() => closeConfirmModal()")
        eerste = await page.evaluate("""() => {
            const el = document.getElementById('clubListEmptyMsg');
            return { tekst: el.textContent.replace(/\s+/g, ' ').trim(),
                     symbolen: el.querySelectorAll('svg').length,
                     zichtbaar: !el.classList.contains('hidden') };
        }""")
        check("het lege clubscherm helpt op weg", eerste["zichtbaar"], True)
        check("met de weg naar een nieuwe club", 'Voeg een club toe' in eerste["tekst"], True)
        check("en de weg naar een backup", 'importeer een backup' in eerste["tekst"], True)
        check("met twee symbolen erbij", eerste["symbolen"], 2)

        print("\n=== HET BAANBEELD IN DE KOPBALK ===\n")
        # Zonder actieve ronde staan er twee regels leeg in de kopbalk. De hoogte vast
        # laten is bewust (inklappen liet het scherm verspringen), dus wordt die ruimte
        # gevuld met een baansilhouet. Zodra er een ronde loopt, verdwijnt het — en de
        # hoogte van de kopbalk mag er niet door veranderen.
        beeld = await page.evaluate("""() => {
            resetHeader();
            const zichtbaarZonder = !document.getElementById('hdrLeegBeeld').classList.contains('hidden');
            const hoogteZonder = Math.round(document.querySelector('header').getBoundingClientRect().height);
            toonLeegBeeld(false);
            const hoogteMet = Math.round(document.querySelector('header').getBoundingClientRect().height);
            resetHeader();
            return { zichtbaarZonder, hoogteZonder, hoogteMet };
        }""")
        check("zonder ronde is het beeld zichtbaar", beeld["zichtbaarZonder"], True)
        check("en de kopbalk blijft even hoog", beeld["hoogteZonder"], beeld["hoogteMet"])

        # De kop hoort te blijven plakken bij het scrollen. Het baanbeeld hangt erin met
        # absolute positionering; zou de kop daarvoor 'relative' krijgen, dan overschrijft
        # dat 'sticky' en scrolt de hele kop weg.
        plakt = await page.evaluate("""async () => {
            nav('settings'); switchSettingsTab('data');
            await new Promise(r => setTimeout(r, 300));
            const kop = document.querySelector('header');
            const positie = getComputedStyle(kop).position;
            window.scrollTo(0, 600);
            await new Promise(r => setTimeout(r, 300));
            const top = Math.round(kop.getBoundingClientRect().top);
            window.scrollTo(0, 0);
            return { positie, top };
        }""")
        check("de kopbalk is sticky", plakt["positie"], "sticky")
        check("en blijft bovenaan bij scrollen", plakt["top"], 0)

        print("\n=== HET ADRES DOET NIET MEER TER ZAKE ===\n")
        # Dit blok toetste of de app als geïnstalleerde app draaide, om een valse
        # waarschuwing te voorkomen. Dat is niet meer nodig: de waarschuwing zelf is weg.
        # Wat blijft is dat een adres met ?opslag= niets meer verandert.
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Testclub');
            localStorage.setItem('golf_opslag_kenmerk', 'hoofd');
        }""", CLUBS)
        await page.goto(app_url() + '?opslag=iets-anders')
        await page.wait_for_timeout(1300)
        na = await page.evaluate("""() => ({
            melding: !document.getElementById('confirmModal').classList.contains('hidden'),
            kenmerk: localStorage.getItem('golf_opslag_kenmerk'),
        })""")
        check("een vreemd adres geeft geen melding", na["melding"], False)
        check("en verandert de naam niet", na["kenmerk"], 'hoofd')


        print("\n=== DE CODE STAAT ER ALTIJD BIJ ===\n")
        # De naam typ je zelf: hij kan in twee installaties gelijk zijn, of vergeten. De
        # code is uniek en verandert nooit, en staat ook in je backupbestandsnamen. Daarom
        # hoort hij in ELKE melding en op elke plek waar de installatie wordt genoemd.
        for naam, leeg in [('hoofd', False), ('', False), ('hoofd', True), ('', True)]:
            await page.evaluate("""([clubs, k, leeg]) => {
                localStorage.clear();
                if (!leeg) {
                    localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                    localStorage.setItem('golf_rounds', '[]');
                }
                if (k) localStorage.setItem('golf_opslag_kenmerk', k);
            }""", [CLUBS, naam, leeg])
            await page.goto(app_url())
            await page.wait_for_timeout(1300)
            plekken = await page.evaluate("""() => {
                const m = document.getElementById('confirmModal');
                const melding = m && !m.classList.contains('hidden')
                    ? document.getElementById('confirmModalMessage').textContent : null;
                nav('settings');
                switchSettingsTab('data');
                return {
                    code: opslagCode(),
                    regel: document.getElementById('opslagRegel').textContent,
                    uitleg: document.getElementById('opslagKenmerkUitleg').textContent,
                    melding,
                };
            }""")
            teksten = [plekken["regel"], plekken["uitleg"]]
            if plekken["melding"]:
                teksten.append(plekken["melding"])
            omschrijving = f"naam {naam or 'geen'}, {'leeg' if leeg else 'met gegevens'}"
            check(f"{omschrijving}: de code staat overal",
                  all(plekken["code"] in t for t in teksten), True)
            if plekken["melding"]:
                await page.evaluate("() => closeConfirmModal()")

        print("\n=== DE NAAM IN DE BESTANDSNAAM ===\n")
        # De naam staat nu ook in je backupbestandsnamen: de opslagcode alleen zegt je
        # maanden later niets meer. Omdat die naam in een bestandsnaam terechtkomt, wordt
        # hij opgeschoond — tekens als / \\ : * ? " < > | breken een bestandsnaam op
        # Windows, Android of in een clouddienst.
        schoon = await page.evaluate("""() => {
            const uit = {};
            [['Edge-Mark', 'Edge-Mark'], ['Edge/Mark', 'EdgeMark'], ['a:b*c?d', 'abcd'],
             ['Telefoon Mark', 'Telefoon Mark'], ['  spaties   hier  ', 'spaties hier'],
             ['heel-erg-lange-naam-die-niet-past', null], ['....', ''],
             ['Edge(Mark)', 'EdgeMark']]
              .forEach(([invoer]) => {
                zetKenmerk(invoer);
                uit[invoer] = { naam: bekendKenmerk(), bestand: kenmerkVoorBestandsnaam() };
              });
            return uit;
        }""")
        check("een geldige naam blijft heel",
              schoon['Edge-Mark']["naam"], 'Edge-Mark')
        check("een schuine streep wordt geweigerd",
              schoon['Edge/Mark']["naam"], 'EdgeMark')
        check("net als dubbele punt, ster en vraagteken",
              schoon['a:b*c?d']["naam"], 'abcd')
        check("spaties worden opgeschoond",
              schoon['  spaties   hier  ']["naam"], 'spaties hier')
        check("en worden koppeltekens in de bestandsnaam",
              schoon['Telefoon Mark']["bestand"], 'Telefoon-Mark')
        # Haakjes bakenen in de bestandsnaam de opslagcode af, dus die mogen niet in de
        # naam staan — anders is niet meer te zien waar de code begint.
        check("haakjes worden geweigerd", schoon['Edge(Mark)']["naam"], 'EdgeMark')
        check("een te lange naam wordt afgekapt op zestien",
              len(schoon['heel-erg-lange-naam-die-niet-past']["naam"]), 16)
        check("een naam zonder bruikbare tekens levert niets op",
              schoon['....']["bestand"], '')

        # Bij het importeren moet de code nog steeds herkend worden — ook in oude
        # bestandsnamen zonder naam, en in een kopie met "(1)" erachter.
        herkenning = await page.evaluate("""() => {
            localStorage.setItem('golf_storage_id', 'QQNX');
            _opslagCode = null;
            return {
                // Het formaat van vóór de haakjes wordt bewust NIET meer herkend:
                // importeren werkt gewoon, alleen zonder de melding dat het bestand uit
                // een andere installatie komt.
                oudFormaat: andereOpslagCode('rondes_backup_20260913_AC5X.json'),
                metNaam: andereOpslagCode('rondes_backup_20260913_Edge-Mark(AC5X).json'),
                zonderNaamNieuw: andereOpslagCode('rondes_backup_20260913_(AC5X).json'),
                eigenCode: andereOpslagCode('rondes_backup_20260913_Telefoon-Mark(QQNX).json'),
                kopie: andereOpslagCode('rondes_backup_20260913_Edge-Mark(AC5X) (1).json'),
                onherkenbaar: andereOpslagCode('mijn-eigen-naam.json'),
            };
        }""")
        check("het oude formaat wordt niet meer herkend", herkenning["oudFormaat"], None)
        check("een nieuw bestand met naam ook", herkenning["metNaam"], 'AC5X')
        check("en een nieuw bestand zonder naam", herkenning["zonderNaamNieuw"], 'AC5X')
        check("een bestand uit deze installatie geeft geen waarschuwing",
              herkenning["eigenCode"], None)
        check("een kopie met (1) wordt ook herkend", herkenning["kopie"], 'AC5X')
        check("een hernoemd bestand levert niets op", herkenning["onherkenbaar"], None)

        print("\n=== BIJ ONLEESBARE GEGEVENS GEEN 'GEEN GEGEVENS GEVONDEN' ===\n")
        # Die melding klinkt als 'dit is je eerste keer', terwijl je rondes er nog wél
        # staan en een backup je redding is. De rem hiervoor keek naar een opslagsleutel
        # die nergens wordt geschreven, dus hij deed niets.
        await page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('golf_rounds', '{kapot');
        }""")
        await page.goto(app_url())
        await page.wait_for_timeout(1400)
        kapot = await page.evaluate("""() => {
            const m = document.getElementById('confirmModal');
            return {
                vlag: rondesOnleesbaar,
                titel: (m && !m.classList.contains('hidden'))
                    ? document.getElementById('confirmModalTitle').textContent : null,
            };
        }""")
        check("de app merkt dat de gegevens onleesbaar zijn", kapot["vlag"], True)
        check("en meldt dát", kapot["titel"], 'Gegevens niet leesbaar')
        # Dit was het echte gat: de rode melding kwam wél, maar zodra je hem wegtikte
        # kwam 'Geen gegevens gevonden' eroverheen — 'is dit je eerste keer, dan klopt
        # dat', terwijl je rondes er nog staan.
        await page.evaluate("() => closeConfirmModal()")
        await page.wait_for_timeout(1500)
        erna = await page.evaluate("""() => {
            const m = document.getElementById('confirmModal');
            return (m && !m.classList.contains('hidden'))
                ? document.getElementById('confirmModalTitle').textContent : null;
        }""")
        check("en er komt niets overheen na het sluiten", erna, None)

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
