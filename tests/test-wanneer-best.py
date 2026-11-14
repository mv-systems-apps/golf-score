"""'Wanneer speel je het best': je rondes gegroepeerd naar het moment waarop je speelde.

Vier indelingen, allemaal cyclisch — alle dinsdagen samen, alle januari's samen:
Week/weekend, Dag, Maand en Kwartaal. Maand en kwartaal zijn erbij gekomen voor
seizoensinvloeden.

De maat is overal: dagresultaat MIN de handicap die op dat moment gold. Het kale
dagresultaat zou bij maanden liegen: je handicap verandert door het jaar heen, dus je
zomerrondes vallen in de tijd dat je beter speelde en de grafiek zou zeggen dat je 's
zomers beter speelt — terwijl je gewoon vooruit bent gegaan.

Gemeten met een echte backup van 40 rondes.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url

with open(os.path.join(HIER, 'rondes-lowhi.json'), encoding='utf-8') as f:
    RONDES = json.load(f)

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


LEES = """([periode, modus]) => {
    nav('stat');
    _statChartPeriod = periode;
    _weekdayViewMode = modus;
    renderPlayerStats();
    const kaart = [...document.querySelectorAll('#screen-stat .card')]
        .find(c => /Wanneer speel je het best/.test(c.textContent));
    if (!kaart) return null;
    const rijen = kaart.innerText.split(String.fromCharCode(10))
        .map(x => x.trim()).filter(Boolean);
    const start = rijen.findIndex(x => /t\\.o\\.v\\. hcp/i.test(x));
    const groepen = [];
    const rest = rijen.slice(start + 1).filter(x => !/^(Met |Je gegevens)/.test(x));
    for (let i = 0; i + 2 < rest.length + 1; i += 3) {
        if (!rest[i + 2]) break;
        groepen.push({ label: rest[i], waarde: rest[i + 1], n: parseInt(rest[i + 2], 10) });
    }
    const svg = kaart.querySelector('svg');
    return {
        knoppen: [...kaart.querySelectorAll('button')].map(b => b.textContent.trim()),
        groepen,
        balken: svg ? svg.querySelectorAll('line[stroke="var(--weekday-accent)"]').length : 0,
        hoogte: svg ? parseFloat(svg.getAttribute('viewBox').split(' ')[3]) : 0,
        noten: rijen.filter(x => /^(Met |Je gegevens)/.test(x)),
    };
}"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 1400})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, rs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_stats_grp_prestaties', 'open');
            localStorage.setItem('golf_profile_name', 'Testspeler');
        }""", [CLUBS, RONDES])
        await page.goto(app_url())
        await page.wait_for_timeout(1500)

        print("=== DE KAART EN ZIJN KNOPPEN ===\n")
        week = await page.evaluate(LEES, ['alles', 'weekend'])
        check("de kaart staat er", week is not None, True)
        check("vier knoppen", week["knoppen"], ['Week/weekend', 'Dag', 'Maand', 'Kwartaal'])

        print("\n=== ELKE INDELING TELT DEZELFDE RONDES ===\n")
        # Of je nu per dag of per maand kijkt: het zijn dezelfde rondes, anders verdeeld.
        uit = {}
        for modus, verwachtAantal in [('weekend', 2), ('days', 7), ('maand', 12), ('kwartaal', 4)]:
            r = await page.evaluate(LEES, ['alles', modus])
            uit[modus] = r
            check(f"{modus}: {verwachtAantal} groepen", len(r["groepen"]), verwachtAantal)
        totalen = {m: sum(g["n"] for g in r["groepen"]) for m, r in uit.items()}
        check("alle vier tellen evenveel rondes", len(set(totalen.values())), 1)

        print("\n=== DE MAAT: T.O.V. JE HANDICAP VAN TOEN ===\n")
        # Zelf narekenen voor één ronde: dagresultaat min de index die ervóór gold.
        controle = await page.evaluate("""() => {
            const rondes = loadSavedRounds()
                .filter(r => r.qualifying && isRondeAf(r))
                .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
            // Een ronde halverwege, zodat er een voorgeschiedenis is.
            const i = Math.floor(rondes.length / 2);
            const hi = indexVoorRonde(rondes, i);
            const sd = effectiveSD(rondes[i]).value;
            return { hi, sd, verschil: Math.round((sd - hi) * 10) / 10 };
        }""")
        check("de handicap van toen is bekend", controle["hi"] is not None, True)
        check("en het verschil is een klein getal, geen dagresultaat",
              abs(controle["verschil"]) < 15, True)

        # De eerste ronde heeft nog geen handicap om tegen af te zetten, en telt dus niet.
        eerste = await page.evaluate("""() => {
            const rondes = loadSavedRounds()
                .filter(r => r.qualifying && isRondeAf(r))
                .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
            return indexVoorRonde(rondes, 0);
        }""")
        check("de eerste ronde heeft geen handicap van toen", eerste, None)

        print("\n=== TE DUNNE GROEPEN KRIJGEN GEEN BALK ===\n")
        maand = uit['maand']
        dun = [g for g in maand["groepen"] if 0 < g["n"] < 3]
        check("er zijn maanden met één of twee rondes", len(dun) > 0, True)
        check("die tonen een streepje", sorted({g["waarde"] for g in dun}), ['\u2014'])
        met = [g for g in maand["groepen"] if g["n"] >= 3]
        check("één balk per maand met genoeg rondes", maand["balken"], len(met))
        check("met een uitleg eronder", any('Met minder dan' in n for n in maand["noten"]), True)

        # Altijd één decimaal, zodat de getallen netjes uitlijnen.
        getallen = [g["waarde"] for g in maand["groepen"] if g["waarde"] != '\u2014']
        check("elk getal heeft één decimaal",
              all(len(w.split('.')[-1]) == 1 for w in getallen), True)

        print("\n=== DE HOOGTE GROEIT MEE ===\n")
        # Twaalf maanden in de hoogte van twee groepen werd een streepjescode.
        check("twaalf maanden krijgen meer hoogte dan twee groepen",
              uit['maand']["hoogte"] > uit['weekend']["hoogte"], True)

        print("\n=== DE NOOT OVER DE DEKKING ===\n")
        # Bij 'Alles' niet naar 'Alles' verwijzen.
        alles = await page.evaluate(LEES, ['alles', 'maand'])
        check("bij Alles geen verwijzing naar Alles",
              any('Kies bovenaan' in n for n in alles["noten"]), False)
        jaar = await page.evaluate(LEES, ['jaar', 'maand'])
        check("bij 12 maanden wel",
              any('Kies bovenaan' in n for n in jaar["noten"]), True)

        print("\n=== ZONDER HANDICAP BIJHOUDEN ===\n")
        # De kaart rekent met dagresultaten, dus zonder handicapberekening verdwijnt hij.
        zichtbaar = await page.evaluate("""() => {
            storage.setItem('golf_whs_volgen', 'off');
            pasWhsWeergaveToe();
            renderPlayerStats();
            const k = [...document.querySelectorAll('#screen-stat .card')]
                .find(c => /Wanneer speel je het best/.test(c.textContent));
            const uit = k ? getComputedStyle(k).display !== 'none' : false;
            storage.setItem('golf_whs_volgen', 'on');
            pasWhsWeergaveToe();
            return uit;
        }""")
        check("dan is de kaart weg", zichtbaar, False)

        print("\n=== DE ANALYSE ZEGT HETZELFDE ALS DE KAART ===\n")
        # Het onderdeel 'Moment' in de analyse gebruikt dezelfde maat. De getallen horen
        # dus exact overeen te komen met de kaart.
        analyse = await page.evaluate("""() => {
            const a = buildGameAnalysis();
            const m = a.secties.find(s => s.kop === 'Moment');
            const strip = x => String(x).replace(/<[^>]*>/g, '');
            return {
                regels: m ? m.regels.map(strip) : [],
                conclusies: a.aanbev.map(strip),
            };
        }""")
        check("de analyse heeft een onderdeel Moment", len(analyse["regels"]) > 0, True)
        kaartWeek = {g["label"]: g["waarde"] for g in uit['weekend']["groepen"]}
        weekRegel = next((r for r in analyse["regels"] if r.startswith('Doordeweeks')), '')
        # De analyse schrijft '+2.6' en de kaart '+2.6': zelfde getal.
        check("doordeweeks is hetzelfde getal als op de kaart",
              kaartWeek['Ma - Vr'].replace('\u2212', '-') in weekRegel.replace('\u2212', '-'), True)
        check("en het weekend ook",
              kaartWeek['Za - Zo'].replace('\u2212', '-') in weekRegel.replace('\u2212', '-'), True)

        kwRegel = next((r for r in analyse["regels"] if r.startswith('Per kwartaal')), '')
        check("per kwartaal staat erin", bool(kwRegel), True)
        check("met de te dunne kwartalen genoemd", 'te weinig rondes' in kwRegel, True)

        # Een seizoensconclusie alleen met een heel jaar aan gegevens.
        seizoen = [c for c in analyse["conclusies"] if 'speel je' in c and 'slag beter dan in' in c]
        check("met minder dan een jaar geen seizoensconclusie", seizoen, [])

        print("\n=== DE ANALYSE VOLGT DE PERIODEKNOP ===\n")
        # De analyse staat onder de periodeknoppen, dus hoort hij ze te volgen — net als
        # de kaarten daar. Kaart en analyse moeten per periode hetzelfde zeggen.
        for periode, verwachtAantal in [('l20', 20), ('alles', None)]:
            per = await page.evaluate("""(per) => {
                nav('stat');
                _statChartPeriod = per;
                _weekdayViewMode = 'weekend';
                renderPlayerStats();
                const k = [...document.querySelectorAll('#screen-stat .card')]
                    .find(c => /Wanneer speel je het best/.test(c.textContent));
                const cel = [...k.querySelectorAll('div[style*="grid-template-columns:1fr 1fr 1fr"] > span')]
                    .map(e => e.textContent.trim()).slice(3);
                const a = buildGameAnalysis();
                const strip = x => String(x).replace(/<[^>]*>/g, '');
                return {
                    kaart: [cel[1], cel[4]],
                    overzicht: a.secties.find(s => s.kop === 'Overzicht').regels.map(strip)[0],
                    moment: ((a.secties.find(s => s.kop === 'Moment') || { regels: [] })
                        .regels.map(strip)[0]) || '',
                    alle: analysisRounds().length,
                };
            }""", periode)
            aantal = int(per["overzicht"].split(' ')[0])
            check(f"{periode}: het overzicht telt de rondes van die periode",
                  aantal, verwachtAantal if verwachtAantal else per["alle"])
            check(f"{periode}: geen verwijzing meer naar 'al je rondes'",
                  'al je opgeslagen rondes' in per["overzicht"], False)
            check(f"{periode}: doordeweeks zegt de analyse wat de kaart zegt",
                  per["kaart"][0] in per["moment"], True)
            check(f"{periode}: en het weekend ook", per["kaart"][1] in per["moment"], True)

        print("\n=== DE PROMPT VOOR AI LEGT DE MAAT UIT ===\n")
        # Anders rekent een AI seizoenen uit op het kale dagresultaat en loopt hij in
        # dezelfde valkuil.
        prompt = await page.evaluate("""async () => {
            let tekst = '';
            navigator.clipboard.writeText = async t => { tekst = t; };
            await copyAnalysisForAi();
            return tekst;
        }""")
        check("het onderdeel Moment zit in de prompt", 'MOMENT' in prompt, True)
        check("met uitleg dat het om de handicap van TOEN gaat",
              'handicapindex die op DAT moment gold' in prompt, True)

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
