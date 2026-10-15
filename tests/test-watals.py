"""'Wat als...?' en de vooruitblik moeten hetzelfde zeggen.

'Wat als' rekent door wat er met je handicap gebeurt als je een ronde met een bepaald
dagresultaat speelt. Dat deed het NIET: de tijdelijke ronde werd aangemaakt zonder holes,
en een ronde telt pas mee in je laatste twintig als hij AF is — alle holes ingevuld. De
tijdelijke viel dus buiten het venster en er kwam altijd je huidige handicap uit, welk
getal je ook invulde.

Op het scherm sprak dat de vooruitblik eronder tegen: die zei dat je handicap zou stijgen
terwijl 'Wat als' beweerde dat er niets veranderde. Deze test bewaakt dat ze het eens
zijn.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, sd, dag):
    return {
        "id": rid, "date": "2026-%02d-%02d" % (1 + (dag // 28), 1 + (dag % 28)),
        "time": "09:%02d" % (rid % 60), "player": "Mark", "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36,
        "chcp": 11, "qualifying": True, "note": "", "total": 45, "totalStb": 18,
        "playedCount": 9, "holesCount": 9, "currentHole": 0, "started": True,
        "sd": sd, "sdFinal": sd, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1,
                   "ppar": 5, "score": 5} for i in range(9)],
    }


# Twintig rondes, waarvan de OUDSTE de beste is: die valt er straks uit, dus de
# vooruitblik heeft iets te melden.
RONDES = [ronde(1, 28.0, 0)] + [ronde(i, 31.0 + (i % 5) * 0.5, i) for i in range(2, 21)]

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
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, RONDES])
        await page.reload()
        await page.wait_for_timeout(1100)

        print("=== WAT ALS REAGEERT OP WAT JE INVULT ===\n")
        uitkomsten = await page.evaluate("""() => {
            const uit = {};
            [20, 25, 30, 33, 40].forEach(v => {
                const w = computeWhatIf('Mark', v);
                uit[v] = w && w.hypo ? Math.round(w.hypo.value * 10) / 10 : null;
            });
            return uit;
        }""")
        print("   ", uitkomsten)
        check("elke invoer geeft een uitkomst",
              all(v is not None for v in uitkomsten.values()), True)
        check("en niet overal dezelfde", len(set(uitkomsten.values())) > 1, True)
        # Een beter (lager) dagresultaat mag je handicap nooit omhoog duwen.
        waarden = [uitkomsten[k] for k in sorted(uitkomsten, key=lambda x: float(x))]
        check("een lager dagresultaat geeft nooit een hogere handicap",
              waarden == sorted(waarden), True)

        print("\n=== DE TIJDELIJKE RONDE TELT ECHT MEE ===\n")
        venster = await page.evaluate("""() => {
            const all = loadSavedRounds();
            const temp = { id: '__T__', player: 'Mark', qualifying: true,
                           date: todayISO(), time: '12:00', sdFinal: 20, holesCount: 18,
                           holes: Array.from({ length: 18 }, (_, i) => ({
                               id: 'W' + i, par: 4, si: i + 1, phcp: 1, ppar: 5, score: 5 })) };
            const l20 = last20Qualifying('Mark', [...all, temp], null, null);
            return { aantal: l20.length, bevatTemp: l20.some(r => r.id === '__T__') };
        }""")
        check("het venster blijft twintig rondes", venster["aantal"], 20)
        check("met de tijdelijke ronde erin", venster["bevatTemp"], True)

        print("\n=== DE VOORUITBLIK KLOPT MET WAT ALS ===\n")
        # 'Speel je geen dagresultaat onder X, dan gaat je hcp naar Y.' Op X en erboven
        # moet Wat als precies Y geven.
        samen = await page.evaluate("""() => {
            const all = loadSavedRounds();
            const last20 = last20Qualifying('Mark', all, null, null);
            const lowHi = effectiveLowHi('Mark', all);
            const esr = esrMapFor('Mark', all);
            const whs = whsHandicap(last20, lowHi, esr);
            const tekst = bouwVooruitblik({ last20, whs, lowHiEff: lowHi, esrMapStats: esr })
                .replace(/<[^>]+>/g, '');
            const g = tekst.match(/van ([\\d.-]+) of beter/);
            const y = tekst.match(/naar ([\\d.]+)/);
            const grens = g ? parseFloat(g[1]) : null;
            const w = x => { const c = computeWhatIf('Mark', x);
                             return c && c.hypo ? Math.round(c.hypo.value * 10) / 10 : null; };
            return { grens, voorspeld: y ? parseFloat(y[1]) : null,
                     huidig: Math.round(whs.value * 10) / 10,
                     opDeGrens: grens != null ? w(grens) : null,
                     netErboven: grens != null ? w(grens + 0.1) : null,
                     erboven: grens != null ? w(grens + 5) : null };
        }""")
        check("de vooruitblik noemt een grens", samen["grens"] is not None, True)
        # De grens is de waarde die je handicap VASTHOUDT. Eerder stond hier de waarde
        # waarmee je in je beste acht komt, en dat is iets anders: met een dagresultaat
        # net onder die grens steeg de handicap alsnog, terwijl de zin het tegendeel
        # beloofde.
        check("op de grens blijft je handicap gelijk",
              samen["opDeGrens"], samen["huidig"])
        check("één tiende erboven stijgt hij",
              samen["netErboven"] > samen["huidig"], True)
        check("en ruim erboven kom je op de voorspelde waarde uit",
              samen["erboven"], samen["voorspeld"])

        print("\n=== IN ELKE SITUATIE ===\n")
        # De vooruitblik heeft drie teksten: venster nog niet vol, de vertrekkende ronde
        # telt niet mee, en de vertrekkende ronde telt wél mee. In alle drie moet de
        # doorrekening kloppen — en waar een grens genoemd wordt, moet Wat als daar
        # precies op uitkomen.
        SITUATIES = {
            'venster nog niet vol': [ronde(i, 30.0 + (i % 5) * 0.4, i) for i in range(1, 20)],
            'oudste telt mee': ([ronde(1, 25.0, 0)]
                                + [ronde(i, 31.0 + (i % 5) * 0.5, i) for i in range(2, 21)]),
            'oudste telt niet mee': ([ronde(1, 40.0, 0)]
                                     + [ronde(i, 31.0 + (i % 5) * 0.5, i) for i in range(2, 21)]),
            'meer dan twintig': [ronde(i, 29.0 + (i % 7) * 0.6, i) for i in range(1, 31)],
            'niet-qualifying ertussen': [ronde(i, 31.0 + (i % 5) * 0.5, i)
                                         for i in range(1, 26)],
            'niet-vastgestelde dagresultaten': [ronde(i, 31.0 + (i % 5) * 0.5, i)
                                                for i in range(1, 21)],
        }
        # De laatste twee situaties aanpassen zodat ze doen wat hun naam zegt.
        for i, r in enumerate(SITUATIES['niet-qualifying ertussen']):
            if (i + 1) % 3 == 0:
                r["qualifying"] = False
        for i, r in enumerate(SITUATIES['niet-vastgestelde dagresultaten']):
            if (i + 1) % 4 == 0:
                r["sdFinal"] = None

        for naam, rondes in SITUATIES.items():
            await page.evaluate("""(rs) => {
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(rs)));
            }""", rondes)
            await page.wait_for_timeout(150)
            meting = await page.evaluate("""() => {
                const all = loadSavedRounds();
                const last20 = last20Qualifying('Mark', all, null, null);
                const lowHi = effectiveLowHi('Mark', all);
                const esr = esrMapFor('Mark', all);
                const whs = whsHandicap(last20, lowHi, esr);
                const tekst = bouwVooruitblik({ last20, whs, lowHiEff: lowHi, esrMapStats: esr })
                    .replace(/<[^>]+>/g, '').trim();
                const w = x => { const c = computeWhatIf('Mark', x);
                                 return c && c.hypo ? Math.round(c.hypo.value * 10) / 10 : null; };
                const g = tekst.match(/van ([\d.-]+) of beter/);
                const y = tekst.match(/naar ([\d.]+)/);
                const grens = g ? parseFloat(g[1]) : null;
                const reeks = [20, 25, 30, 35, 40].map(w);
                return {
                    reeks,
                    // Een slechter dagresultaat mag de handicap nooit verlagen.
                    monotoon: reeks.every((v, i, a) => i === 0 || v == null || a[i - 1] == null
                                                       || v >= a[i - 1]),
                    voorspeld: y ? parseFloat(y[1]) : null,
                    opGrens: grens != null ? w(grens) : null,
                    erboven: grens != null ? w(grens + 5) : null,
                };
            }""")
            check(f"{naam}: elke invoer geeft een uitkomst",
                  all(v is not None for v in meting["reeks"]), True)
            check(f"{naam}: slechter is nooit beter", meting["monotoon"], True)
            if meting["voorspeld"] is not None and meting["opGrens"] is not None:
                check(f"{naam}: Wat als komt uit op de voorspelde waarde",
                      [meting["opGrens"], meting["erboven"]],
                      [meting["voorspeld"], meting["voorspeld"]])

        print("\n=== ELKE ZIN, ELKE SITUATIE ===\n")
        # De vooruitblik kent vier zinnen. Voor elke geldt een eigen belofte, en die
        # moet nagerekend kunnen worden met Wat als:
        #   'venster nog niet vol'  — geen belofte
        #   'telt niet mee'         — geen belofte
        #   'je hcp blijft dan Y'   — zelfs het slechtst mogelijke resultaat geeft Y
        #   'gaat naar Y, tenzij X' — op X blijft je hcp gelijk, erboven stijgt hij,
        #                             en het slechtst mogelijke resultaat geeft Y
        PROFIELEN = {
            'hcp stijgt': ([ronde(1, 28.0, 0)]
                           + [ronde(i, 31.0 + (i % 5) * 0.5, i) for i in range(2, 21)]),
            'hcp blijft gelijk': [ronde(i, 31.0 + (i % 3) * 0.2, i) for i in range(1, 21)],
            'grote spreiding': ([ronde(1, 20.0, 0)]
                                + [ronde(i, 28.0 + (i % 9) * 1.2, i) for i in range(2, 21)]),
            'zeer lage handicap': [ronde(i, 2.0 + (i % 4) * 0.3, i) for i in range(1, 21)],
            'zeer hoge handicap': [ronde(i, 48.0 + (i % 4) * 0.5, i) for i in range(1, 21)],
            'alle rondes gelijk': [ronde(i, 30.0, i) for i in range(1, 21)],
            'meer dan twintig rondes': [ronde(i, 29.0 + (i % 7) * 0.6, i) for i in range(1, 36)],
        }
        for naam, rondes in PROFIELEN.items():
            await page.evaluate("""(rs) => {
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(rs)));
            }""", rondes)
            await page.wait_for_timeout(150)
            m = await page.evaluate("""() => {
                const all = loadSavedRounds();
                const last20 = last20Qualifying('Mark', all, null, null);
                const lowHi = effectiveLowHi('Mark', all);
                const esr = esrMapFor('Mark', all);
                const whs = whsHandicap(last20, lowHi, esr);
                const tekst = bouwVooruitblik({ last20, whs, lowHiEff: lowHi, esrMapStats: esr })
                    .replace(/<[^>]+>/g, '').trim();
                const w = x => { const c = computeWhatIf('Mark', x);
                                 return c && c.hypo ? Math.round(c.hypo.value * 10) / 10 : null; };
                const mG = tekst.match(/van ([\d.-]+) of beter/);
                const mN = tekst.match(/naar ([\d.-]+) \(/);
                const mB = tekst.match(/blijft dan ([\d.-]+)/);
                const grens = mG ? parseFloat(mG[1]) : null;
                return {
                    stijgt: !!mN, blijft: mB ? parseFloat(mB[1]) : null,
                    naar: mN ? parseFloat(mN[1]) : null,
                    huidig: whs ? Math.round(whs.value * 10) / 10 : null,
                    grens,
                    opGrens: grens != null ? w(grens) : null,
                    netErboven: grens != null ? w(Math.round((grens + 0.1) * 10) / 10) : null,
                    // 54 is het slechtst mogelijke dagresultaat dat je kunt invullen.
                    slechtst: w(54),
                };
            }""")
            if m["stijgt"]:
                check(f"{naam}: het slechtste resultaat geeft de voorspelde waarde",
                      m["slechtst"], m["naar"])
                if m["grens"] is not None:
                    check(f"{naam}: op de grens blijft je handicap gelijk",
                          m["opGrens"], m["huidig"])
                    check(f"{naam}: één tiende erboven stijgt hij",
                          m["netErboven"] > m["huidig"], True)
            elif m["blijft"] is not None:
                check(f"{naam}: zelfs het slechtste resultaat houdt je handicap gelijk",
                      m["slechtst"], m["blijft"])

        print("\n=== DE UITKOMST OP ÉÉN REGEL ===\n")
        # Zelfde vorm als op de rondekaart ('Whs 30.7 ↗ 30.8 (+0.1)'), met alleen de
        # nieuwe waarde vet. Eerder stond dit op twee regels met een eigen formulering.
        await page.evaluate("""(rs) => {
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rs)));
            nav('stat');
            window._watIfCollapsed = false;
            localStorage.setItem('golf_stats_grp_handicap', 'open');
            renderPlayerStats();
        }""", [ronde(1, 28.0, 0)] + [ronde(i, 31.0 + (i % 5) * 0.5, i) for i in range(2, 21)])
        await page.wait_for_timeout(300)
        regel = await page.evaluate("""() => {
            const inp = document.getElementById('watIfInput');
            inp.value = '31.9';
            onWatIfInput(inp);
            const el = document.getElementById('watIfResult');
            return { tekst: el.innerText.trim(),
                     regels: el.innerText.trim().split(String.fromCharCode(10)).length,
                     vet: [...el.querySelectorAll('b')].map(b => b.textContent),
                     pijl: el.querySelectorAll('svg').length };
        }""")
        check("het staat op één regel", regel["regels"], 1)
        check("in de vorm van de rondekaart",
              regel["tekst"].startswith('Whs '), True)
        check("met een pijl ertussen", regel["pijl"] >= 1, True)
        check("en alleen de nieuwe waarde vet", len(regel["vet"]), 1)

        volgorde = await page.evaluate("""() => [...document.querySelectorAll('#watIfCard div')]
            .map(d => d.textContent.trim())
            .filter(t => t === 'Vooruitblik' || t === 'Volgend dagresultaat')""")
        check("de vooruitblik staat boven het invoerveld",
              volgorde, ['Vooruitblik', 'Volgend dagresultaat'])

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
