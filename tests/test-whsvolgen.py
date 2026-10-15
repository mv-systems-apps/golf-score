"""'Handicap bijhouden' uit: de app is een scorekaart, en je gegevens blijven intact.

Zet je de schakelaar uit, dan vervalt alles wat met de handicapberekening te maken heeft:
het tabblad WHS, het handicapverloop, het dagresultaat, de qualifying-keuze en de
WHS-groepering. Wat blijft is wat een papieren scorekaart ook doet — met dit verschil dat
de app je baanhandicap uitrekent en je stableford bijhoudt.

De belangrijkste eis: het is een WEERGAVE-schakelaar. Hij raakt je rondes niet aan, dus
uit → aan → uit brengt je precies terug waar je was. Dat is wat deze test bewaakt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid):
    return {
        "id": rid, "date": "2026-08-%02d" % rid, "time": "09:00", "player": "Mark",
        "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        # Twee tees, zodat 'Gemiddelde per tee' iets te vergelijken heeft.
        "gender": "Heren", "tee": ["Blauw", "Geel"][rid % 2],
        "CR": 37.3, "SR": 141, "PAR": 36, "chcp": 11,
        "qualifying": True, "note": "", "total": 45, "totalStb": 18, "playedCount": 9,
        "holesCount": 9, "currentHole": 0, "started": True,
        "sd": 30.0, "sdFinal": 30.0, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   # Oplopende scores: anders valt er niets te vergelijken tussen
                   # holes en blijven sommige kaarten leeg.
                   "score": 4 + (i // 3)} for i in range(9)],
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
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, [ronde(i) for i in range(1, 22)]])
        await page.reload()
        await page.wait_for_timeout(1000)

        STAND = """() => {
            nav('stat');
            // Alle groepen open: anders lees je alleen de koppen.
            ['handicap', 'prestaties', 'banen']
                .forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'open'));
            renderPlayerStats();
            const tekst = document.getElementById('screen-stat').innerText;
            nav('archive');
            loadSaved();
            const kaart = document.querySelector('#screen-archive .saved-item');
            return {
                whsHcp: tekst.includes('WHS-HCP'),
                lowHi: tekst.includes('LOW HI'),
                gemSd: tekst.includes('GEM. SD'),
                handicapGroep: tekst.includes('HANDICAP'),
                prestaties: tekst.includes('PRESTATIES'),
                // Deze rusten allemaal op het DAGRESULTAAT en horen dus mee te
                // verdwijnen; ze bleven eerst staan met lege of misleidende cijfers.
                perTee: tekst.includes('GEMIDDELDE PER TEE'),
                clubsGroep: /CLUBS/i.test(tekst),
                perDag: tekst.includes('WANNEER SPEEL JE HET BEST'),   // was 'Gemiddelde per dag'
                trend: tekst.includes('Trend'),
                spreiding: tekst.includes('Consistentie (spreiding)'),
                tovHandicap: tekst.includes('T.O.V. JE HANDICAP'),
                // Deze rekenen met slagen t.o.v. de par en blijven wél:
                perPar: tekst.includes('GEMIDDELDE PER PAR'),
                perSi: tekst.includes('GEMIDDELDE PER SI'),
                // Waarschuwen voor een ontbrekend dagresultaat kan niet als je het
                // dagresultaat niet ziet en 'Vaststellen' weg is.
                driehoekjes: document.getElementById('screen-stat')
                    .querySelectorAll('svg[stroke*="orange"]').length,
                // Zichtbaarheid meten, niet de klasse: het verbergen loopt nu via één
                // regel in de opmaak (html.geen-whs .whs-only), niet meer via een
                // 'hidden'-klasse per element.
                // getComputedStyle in plaats van offsetParent: dat laatste is ook nul
                // als het element op een scherm staat dat nu niet getoond wordt, en dan
                // meet je het verkeerde.
                whsTab: getComputedStyle(document.getElementById('settingsTabBtnWhs')).display !== 'none',
                whsKnop: getComputedStyle(document.getElementById('groupByWhsBtn')).display !== 'none',
                qualRij: getComputedStyle(document.getElementById('qualRow1')).display !== 'none',
                kaart: kaart ? kaart.innerText.replace(/\\n+/g, ' | ') : '',
                // De badges en het driehoekje op de kaarten in het archief.
                analyseKnop: /Analyseer mijn spel/.test(tekst),
                whsBadges: [...document.querySelectorAll('#screen-archive .badge-whs')]
                    .some(e => getComputedStyle(e).display !== 'none'),
                lBadges: [...document.querySelectorAll('#screen-archive .badge-lowhi')]
                    .some(e => getComputedStyle(e).display !== 'none'),
                qBadges: [...document.querySelectorAll('#screen-archive .badge-q')]
                    .some(e => getComputedStyle(e).display !== 'none'),
                driehoekjesKaart: document.getElementById('screen-archive')
                    .querySelectorAll('svg[stroke*="orange"]').length,
            };
        }"""

        print("=== MET HANDICAP BIJHOUDEN AAN ===\n")
        aan = await page.evaluate(STAND)
        check("de handicapcijfers staan er", aan["whsHcp"] and aan["lowHi"] and aan["gemSd"], True)
        check("de handicapgroep ook", aan["handicapGroep"], True)
        check("het tabblad WHS is bereikbaar", aan["whsTab"], True)
        check("de WHS-groepering ook", aan["whsKnop"], True)
        check("en de qualifying-keuze staat op het startscherm", aan["qualRij"], True)
        check("de kaart toont het dagresultaat", 'Sd' in aan["kaart"], True)
        check("gemiddelde per tee staat er", aan["perTee"], True)
        check("de groep Clubs ook", aan["clubsGroep"], True)
        check("en het gemiddelde per dag", aan["perDag"], True)
        check("de knop Analyseer mijn spel staat er", aan["analyseKnop"], True)
        check("met de WHS-, Low-HI- en Q-badges op de kaarten",
              [aan["whsBadges"], aan["lBadges"], aan["qBadges"]], [True, True, True])
        check("en trend, spreiding en de handicapverdeling",
              [aan["trend"], aan["spreiding"], aan["tovHandicap"]], [True, True, True])

        print("\n=== MET HANDICAP BIJHOUDEN UIT ===\n")
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'off');
            pasWhsWeergaveToe();
        }""")
        uit = await page.evaluate(STAND)
        check("de handicapcijfers zijn weg",
              uit["whsHcp"] or uit["lowHi"] or uit["gemSd"], False)
        check("de handicapgroep ook", uit["handicapGroep"], False)
        check("het tabblad WHS is verborgen", uit["whsTab"], False)
        check("de WHS-groepering ook", uit["whsKnop"], False)
        check("en de qualifying-keuze", uit["qualRij"], False)
        check("de kaart toont geen dagresultaat", 'Sd' in uit["kaart"], False)
        # Wat een scorekaart wél doet, blijft:
        check("maar wel je baanhandicap", 'Chcp' in uit["kaart"], True)
        check("je bruto score", 'Str' in uit["kaart"], True)
        check("en je stableford", 'Stb' in uit["kaart"], True)
        check("de prestatiecijfers blijven ook", uit["prestaties"], True)
        check("per par en per SI blijven", [uit["perPar"], uit["perSi"]], [True, True])
        check("gemiddelde per tee is weg", uit["perTee"], False)
        check("de groep Clubs ook", uit["clubsGroep"], False)
        check("en het gemiddelde per dag", uit["perDag"], False)
        # De analyse leunt zwaar op dagresultaten; een halve analyse maakt het juist
        # ingewikkelder in plaats van eenvoudiger.
        check("de knop Analyseer mijn spel is weg", uit["analyseKnop"], False)
        check("net als alle WHS-badges op de kaarten",
              [uit["whsBadges"], uit["lBadges"], uit["qBadges"]], [False, False, False])
        check("en het driehoekje op de kaart", uit["driehoekjesKaart"], 0)
        check("net als trend, spreiding en de handicapverdeling",
              [uit["trend"], uit["spreiding"], uit["tovHandicap"]], [False, False, False])
        check("en er wordt niet gewaarschuwd voor een ontbrekend dagresultaat",
              uit["driehoekjes"], 0)

        print("\n=== EN WEER AAN: ALLES TERUG ===\n")
        # Dit is de kern: de schakelaar raakt geen gegevens aan.
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")
        terug = await page.evaluate(STAND)
        check("het scherm is weer als vóór het uitzetten", terug, aan)

        gegevens = await page.evaluate("""() => {
            const l = loadSavedRounds();
            return { aantal: l.length,
                     qualifying: l.filter(r => r.qualifying).length,
                     metDagresultaat: l.filter(r => r.sdFinal != null).length };
        }""")
        check("alle rondes staan er nog", gegevens["aantal"], 21)
        check("met hun qualifying-vlag", gegevens["qualifying"], 21)
        check("en hun dagresultaat", gegevens["metDagresultaat"], 21)

        print("\n=== SCHERMBREDE CONTROLE ===\n")
        # Vier plekken bleven eerst staan; ze zaten buiten het statistiekenscherm en
        # vielen daardoor niet op. De laatste was de lastigste: de qualifying-rij in het
        # bewerkvenster staat ONDERAAN het bestand, ná het script, en bestond bij de
        # eerste aanroep dus nog niet.
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'off');
            pasWhsWeergaveToe();
        }""")
        breed = await page.evaluate("""() => {
            const verborgen = id => {
                const e = document.getElementById(id);
                return e ? getComputedStyle(e).display === 'none' : 'ontbreekt';
            };
            nav('archive'); loadSaved();
            const i = loadSavedRounds().findIndex(r => (r.holes || []).some(h => h.score !== null));
            openRoundEditChoice(i);
            const vaststellen = document.getElementById('roundEditChoiceResult');
            const keuzes = ['roundEditChoiceHerplan', 'roundEditChoiceInfo', 'roundEditChoiceResult']
                .map(id => document.getElementById(id))
                .filter(b => b && getComputedStyle(b).display !== 'none')
                .map(b => b.textContent.trim());
            sluitRoundEditChoice();
            return {
                whsHcpRegel: verborgen('computedHcpRow'),      // 'WHS-hcp: —' op Start
                afwijkingsmelding: verborgen('hcpOverrideRow'),
                qualifyingStart: verborgen('qualRow1'),
                qualifyingBewerken: verborgen('editQualRow'),
                vaststellenWeg: !!vaststellen && vaststellen.classList.contains('hidden'),
                keuzes,
            };
        }""")
        check("de regel 'WHS-hcp' op Start is weg", breed["whsHcpRegel"], True)
        check("de melding dat je hcp afwijkt ook", breed["afwijkingsmelding"], True)
        check("de qualifying-keuze op Start", breed["qualifyingStart"], True)
        check("en die in het bewerkvenster", breed["qualifyingBewerken"], True)
        check("'Vaststellen' verdwijnt uit het bewerkkeuzevenster",
              breed["vaststellenWeg"], True)
        check("er blijven twee keuzes over", breed["keuzes"], ['Corrigeren', 'Bewerken'])

        # En weer aan: alles terug.
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")
        terugBreed = await page.evaluate("""() => {
            const verborgen = id => getComputedStyle(document.getElementById(id)).display === 'none';
            nav('archive'); loadSaved();
            const i = loadSavedRounds().findIndex(r => (r.holes || []).some(h => h.score !== null));
            openRoundEditChoice(i);
            const keuzes = ['roundEditChoiceHerplan', 'roundEditChoiceInfo', 'roundEditChoiceResult']
                .map(id => document.getElementById(id))
                .filter(b => b && getComputedStyle(b).display !== 'none')
                .map(b => b.textContent.trim());
            sluitRoundEditChoice();
            return { whsHcpRegel: verborgen('computedHcpRow'),
                     qualifyingStart: verborgen('qualRow1'),
                     qualifyingBewerken: verborgen('editQualRow'),
                     keuzes };
        }""")
        check("de WHS-regel is terug", terugBreed["whsHcpRegel"], False)
        check("de qualifying-keuzes ook",
              [terugBreed["qualifyingStart"], terugBreed["qualifyingBewerken"]], [False, False])
        check("en 'Vaststellen' staat er weer bij",
              terugBreed["keuzes"], ['Corrigeren', 'Bewerken', 'Vaststellen'])

        print("\n=== DE HELE CYCLUS: AAN, UIT, WEER AAN ===\n")
        # Het scenario waar het echt om gaat: je speelt een tijd met de handicap aan, zet
        # hem uit en speelt door, en zet hem later weer aan. Klopt je handicap dan nog?
        # De rondes uit de uit-periode zijn niet-qualifying en mogen je verloop niet
        # raken; de oude rondes moeten hun vlag én hun dagresultaat houden.
        async def speelRondes(aantal, dagenTerugVanaf):
            for k in range(aantal):
                await page.evaluate("""(d) => {
                    nav('setup');
                    sel.track = 'Airborne'; sel.tee = 'Blauw'; sel._teeUserSelected = true;
                    if (whsVolgen()) {
                        sel.qualifying = true;
                        const t = document.getElementById('qualifyToggle1');
                        if (t) t.checked = true;
                    }
                    document.getElementById('iName').value = 'Mark';
                    document.getElementById('iHcp').value = '30.7';
                    onHcpBlur(document.getElementById('iHcp'));
                    const dt = new Date(); dt.setDate(dt.getDate() - d);
                    document.getElementById('iDate').value = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
                    document.getElementById('iTime').value = '0' + (7 + (d % 9)) + ':00';
                    onDateTimeChange();
                    startRound();
                    const cb = document.getElementById('confirmModalBtn');
                    if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
                    if (!game || !game.holes || !game.holes.length) return 'niet gestart';
                    nav('score');
                    for (let h = 0; h < 9; h++) {
                        setCurrentHole(h); selectHole(h);
                        armScoreChange(h, 4 + ((h + d) % 3)); clearScoreTap(false);
                    }
                    localStorage.removeItem('golf_active_id');
                    game.started = false;
                    loadSaved();
                    return 'ok';
                }""", dagenTerugVanaf + k)
                await page.wait_for_timeout(200)

        METING = """() => {
            const l = loadSavedRounds();
            const w = whsHandicap(last20Qualifying('Mark', l, null, null));
            return { rondes: l.length,
                     qualifying: l.filter(x => x.qualifying).length,
                     nietQual: l.filter(x => !x.qualifying).length,
                     hcp: w ? Math.round(w.value * 10) / 10 : null };
        }"""

        await page.evaluate("""() => {
            metVerwijderen(() => setRoundsAndMark('[]'));
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")
        await speelRondes(12, 40)
        stap1 = await page.evaluate(METING)

        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'off');
            pasWhsWeergaveToe();
        }""")
        await speelRondes(6, 20)
        stap2 = await page.evaluate(METING)

        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")
        stap3 = await page.evaluate(METING)
        await speelRondes(3, 5)
        stap4 = await page.evaluate(METING)

        check("twaalf qualifying rondes om mee te beginnen", stap1["qualifying"], 12)
        check("de zes rondes met de schakelaar uit zijn niet-qualifying",
              stap2["nietQual"], 6)
        check("de oude rondes hielden hun vlag", stap3["qualifying"], 12)
        check("de handicap bleef door de hele cyclus gelijk",
              [stap2["hcp"], stap3["hcp"]], [stap1["hcp"], stap1["hcp"]])
        check("en nieuwe rondes tellen daarna weer mee", stap4["qualifying"], 15)

        print("\n=== DE KLASSE WERKT ALS GEHEEL ===\n")
        # Het verbergen loopt via één regel in de opmaak: alles met class="whs-only"
        # verdwijnt zodra de pagina de klasse 'geen-whs' krijgt. Deze controle telt ze
        # allemaal, zodat een nieuw element dat de klasse mist niet ongemerkt blijft
        # staan — dat was precies wat er drie keer misging toen elk element zijn eigen
        # voorwaarde had.
        telling = await page.evaluate("""() => {
            const tel = () => {
                nav('stat');
                ['handicap', 'prestaties', 'banen']
                  .forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'open'));
                renderPlayerStats();
                nav('archive'); loadSaved();
                const alle = [...document.querySelectorAll('.whs-only')];
                return { totaal: alle.length,
                         zichtbaar: alle.filter(e => getComputedStyle(e).display !== 'none').length };
            };
            storage.setItem('golf_whs_volgen', 'off'); pasWhsWeergaveToe();
            const uit = tel();
            storage.setItem('golf_whs_volgen', 'on'); pasWhsWeergaveToe();
            const aan = tel();
            return { uit, aan };
        }""")
        # Geen enkel whs-only element mag INLINE zijn: zo'n omhulsel om blokken heen is
        # fragiel, en bij de kerncijfers ging het daar al mis — het omhulsel werd het
        # element dat de indeling bepaalt en kreeg de kolomregel niet.
        vormen = await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
            nav('stat');
            ['handicap', 'prestaties', 'banen']
                .forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'open'));
            renderPlayerStats();
            return [...document.querySelectorAll('.whs-only')]
                .map(e => getComputedStyle(e).display)
                .filter(d => d === 'inline');
        }""")
        check("geen enkel whs-only element is inline", vormen, [])

        check("er zijn whs-only elementen om te verbergen",
              telling["uit"]["totaal"] > 20, True)
        check("met de schakelaar uit is er geen enkele zichtbaar",
              telling["uit"]["zichtbaar"], 0)
        check("en met de schakelaar aan vrijwel allemaal",
              telling["aan"]["zichtbaar"] >= telling["aan"]["totaal"] - 1, True)

        print("\n=== DE KERNCIJFERS BLIJVEN UITGELIJND ===\n")
        # De whs-only klasse hoort op het cijferblok zelf te staan. Zat hij op een
        # omhulsel eromheen, dan werd dát het flex-element en kreeg het de gelijke-
        # breedte-regel niet: elke kolom nam de breedte van zijn eigen tekst en de
        # kolommen liepen niet meer door.
        await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
        }""")
        kolommen = await page.evaluate("""() => {
            nav('stat');
            renderPlayerStats();
            const kaart = document.querySelector('#screen-stat .card');
            return [...kaart.querySelectorAll(':scope > div > div')]
                .map(e => { const b = e.getBoundingClientRect();
                            return { x: Math.round(b.x), breedte: Math.round(b.width) }; });
        }""")
        check("er staan zes kerncijfers", len(kolommen), 6)
        check("allemaal even breed",
              len({k["breedte"] for k in kolommen}), 1)
        check("en de tweede rij staat onder de eerste",
              [k["x"] for k in kolommen[3:]], [k["x"] for k in kolommen[:3]])

        # Bij elk schermformaat: gelijke kolommen, labels op één regel, geen overloop.
        # Een flexrij deed dat niet — bij 600 px stonden er vijf naast elkaar met een
        # zesde die over de volle breedte uitrekte.
        for breedte in (280, 320, 360, 390, 430, 600, 768, 1024):
            await page.set_viewport_size({"width": breedte, "height": 900})
            await page.wait_for_timeout(150)
            meting = await page.evaluate("""() => {
                nav('stat');
                renderPlayerStats();
                const items = [...document.querySelectorAll('#screen-stat .kpi-grid > div')];
                const rijen = {};
                items.forEach(e => { const b = e.getBoundingClientRect();
                    const y = Math.round(b.y); (rijen[y] = rijen[y] || []).push(Math.round(b.x)); });
                const perRij = Object.values(rijen), eerste = perRij[0];
                const labels = items.map(e => e.querySelector('.kpi-label'));
                return {
                    uitgelijnd: perRij.every(r => r.every((x, i) => x === eerste[i])),
                    eenBreedte: new Set(items.map(e => Math.round(e.getBoundingClientRect().width))).size === 1,
                    labelsOpEenRegel: labels.every(l => l.getBoundingClientRect().height <= 20),
                    nietsAfgekapt: labels.every(l => l.scrollWidth <= l.clientWidth + 1),
                    overloop: document.documentElement.scrollWidth > window.innerWidth,
                };
            }""")
            check(f"{breedte} px: kolommen gelijk en uitgelijnd",
                  [meting["uitgelijnd"], meting["eenBreedte"]], [True, True])
            check(f"{breedte} px: labels op één regel, niets afgekapt, geen overloop",
                  [meting["labelsOpEenRegel"], meting["nietsAfgekapt"], meting["overloop"]],
                  [True, True, False])
        await page.set_viewport_size({"width": 390, "height": 844})

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
