"""Alle groepskoppen in het archief zijn precies even hoog en even ver ingesprongen.

Bij het wisselen tussen weergaven verspringt de lijst dan niet. Twee koppen weken af, elk
op een eigen manier:

  * de jaarkop in de vlakke lijst had 2 pixels opvulling links, dus stond zijn tekst niet
    op één lijn met de kaarten eronder;
  * de agendakop miste de regelhoogte die de andere koppen via archiefInklapKop krijgen
    en was daardoor vier pixels hoger.

Allebei nauwelijks te zien op één scherm, maar hinderlijk zodra je heen en weer schakelt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url


def ronde(rid, datum, gespeeld=9):
    return {
        "id": rid, "date": datum, "time": "09:%02d" % (rid % 60), "player": "Testspeler",
        "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
        "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36, "chcp": 11,
        "qualifying": True, "note": "", "total": 45 if gespeeld else 0,
        "totalStb": 18 if gespeeld else 0, "playedCount": gespeeld, "holesCount": 9,
        "currentHole": 0, "started": gespeeld > 0,
        "sd": 30.0 if gespeeld else None, "sdFinal": 30.0 if gespeeld else None, "pcc": 0,
        "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
                   "score": 5 if i < gespeeld else None} for i in range(9)],
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
            // Eén geplande ronde erbij, zodat de agendaweergave iets te tonen heeft.
            const nu = new Date();
            const plus = d => { const x = new Date(nu); x.setDate(x.getDate() + d);
                                return new Date(x.getTime() - x.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
            rs.push({ ...rs[0], id: 900, date: plus(2), playedCount: 0, started: false,
                      sd: null, sdFinal: null,
                      holes: rs[0].holes.map(h => ({ ...h, score: null })) });
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", [CLUBS, [ronde(1, '2026-08-01'), ronde(2, '2026-07-01')]])
        await page.reload()
        await page.wait_for_timeout(800)

        METEN = """(patroon) => {
            const kop = [...document.querySelectorAll('#screen-archive div')].find(d => {
                const st = getComputedStyle(d);
                return st.fontSize === '20px' && st.fontWeight === '800'
                    && new RegExp(patroon, 'i').test(d.textContent.trim().slice(0, 12));
            });
            if (!kop) return null;
            const st = getComputedStyle(kop);
            const span = kop.querySelector('span');
            return {
                hoogte: Math.round(kop.getBoundingClientRect().height),
                tekstX: Math.round((span || kop).getBoundingClientRect().x),
                regelhoogte: st.lineHeight,
            };
        }"""

        await page.evaluate("() => nav('archive')")
        jaar = await page.evaluate(METEN, '^20')
        # De kaartrand meten in de vlakke lijst: bij categorie staat alles dicht.
        kaartX = await page.evaluate(
            "() => Math.round(document.querySelector('#screen-archive .saved-item')"
            ".getBoundingClientRect().x)")
        await page.evaluate("() => toggleGroupByPlanned()")
        agenda = await page.evaluate(METEN, '^deze week')
        await page.evaluate("() => { toggleGroupByPlanned(); toggleGroupByCategory(); }")
        categorie = await page.evaluate(METEN, '^afgerond')
        await page.evaluate("() => toggleGroupByCategory()")

        print("=== ALLE KOPPEN GELIJK ===\n")
        for naam, kop in (('jaarkop', jaar), ('agendakop', agenda), ('categoriekop', categorie)):
            check(f"{naam} gevonden", kop is not None, True)
        if all((jaar, agenda, categorie)):
            check("even hoog",
                  [jaar["hoogte"], agenda["hoogte"], categorie["hoogte"]],
                  [categorie["hoogte"]] * 3)
            check("even ver ingesprongen",
                  [jaar["tekstX"], agenda["tekstX"], categorie["tekstX"]],
                  [categorie["tekstX"]] * 3)
            check("en op één lijn met de kaarten", jaar["tekstX"], kaartX)
            check("met dezelfde regelhoogte",
                  [jaar["regelhoogte"], agenda["regelhoogte"], categorie["regelhoogte"]],
                  [categorie["regelhoogte"]] * 3)

        print("\n=== ÉÉN STIJL VOOR ALLE KOPPEN ===\n")
        # De afspraak, overgenomen van het statistiekenscherm: de TITEL is 20px en vet,
        # het AANTAL erachter 15px en niet vet. Het aantal is bijzaak en hoort zich ook
        # zo te gedragen.
        # Eerder liep dit uiteen: in de vlakke lijst 15px/400, in de andere weergaven
        # 20px/400, en in Instellingen 15px maar wél vet.
        groottes = await page.evaluate("""() => {
            const meet = (aanroep) => {
                nav('archive');
                zetGroepering(null);
                tekenRondelijst();
                eval(aanroep);
                const kop = document.querySelector('#screen-archive .year-sep')
                         || document.querySelector('#screen-archive [data-inklap]')
                         // Terugval: elke kop met hoofdletters, een eigen onclick en een
                         // titel plus een aantal erin.
                         || [...document.querySelectorAll('#screen-archive *')].find(e =>
                                e.getAttribute('onclick')
                                && e.children.length >= 2 && e.children.length <= 3
                                && getComputedStyle(e).textTransform === 'uppercase');
                if (!kop) return null;
                const delen = [...kop.children]
                    .filter(c => c.textContent.trim())
                    .map(c => ({ grootte: getComputedStyle(c).fontSize,
                                 gewicht: getComputedStyle(c).fontWeight }));
                return { kop: getComputedStyle(kop).fontSize, delen };
            };
            const instellingen = () => {
                nav('settings');
                switchSettingsTab('data');
                const kop = document.querySelector('#settingsTabData [data-section-key]');
                if (!kop) return null;
                return {
                    kop: getComputedStyle(kop).fontSize,
                    delen: [...kop.children].filter(c => c.textContent.trim())
                        .map(c => ({ grootte: getComputedStyle(c).fontSize,
                                     gewicht: getComputedStyle(c).fontWeight })),
                };
            };
            return {
                vlak: meet('0'),
                categorie: meet('toggleGroupByCategory()'),
                club: meet('toggleGroupByTrack()'),
                speler: meet('toggleGroupByPlayer()'),
                agenda: meet('toggleGroupByPlanned()'),
                whs: meet('toggleGroupByWhs()'),
                instellingen: instellingen(),
                // De regel 'Banen 2 ▸' op het clubtabblad. Die staat BINNEN een kaart en
                // is dus niveau 2, maar hij is wel de kop van een eigen lijst — dus
                // dezelfde verhouding tussen titel en aantal.
                clubs: (() => {
                    nav('club');
                    const rij = [...document.querySelectorAll('#screen-club div')]
                        .find(d => /^Banen/.test(d.textContent.trim()) && d.children.length === 3);
                    if (!rij) return null;
                    return {
                        kop: getComputedStyle(rij.children[0]).fontSize,
                        delen: [...rij.children].filter(c => c.textContent.trim())
                            .map(c => ({ grootte: getComputedStyle(c).fontSize,
                                         gewicht: getComputedStyle(c).fontWeight })),
                    };
                })(),
            };
        }""")
        for naam, m in groottes.items():
            check(f"{naam}: de kop is 20px", m["kop"] if m else None, '20px')
            # Eerste deel is de naam of het jaartal, tweede het aantal.
            titel, aantal = (m["delen"] + [None, None])[:2] if m else (None, None)
            # Op het clubtabblad staat de titel op gewicht 700 in plaats van 800: die
            # regel staat binnen een kaart en mag niet met de clubnaam erboven
            # concurreren. De maatverhouding met het aantal is wat telt.
            verwachtGewicht = '700' if naam == 'clubs' else '800'
            check(f"{naam}: de titel is 20px en vet",
                  [titel["grootte"], titel["gewicht"]] if titel else None,
                  ['20px', verwachtGewicht])
            check(f"{naam}: het aantal is 15px en niet vet",
                  [aantal["grootte"], aantal["gewicht"]] if aantal else None, ['15px', '400'])

        # Instellingen: het backupblok staat boven alle drie de tabbladen. De eerste kop
        # eronder hoort op elk tabblad even ver weg te staan. Exporteren (Gegevens) had
        # nog 16px extra bovenaan, uit de tijd dat de backupstand daar binnen het tabblad
        # stond — op Gegevens stond de kop daardoor 28px lager in plaats van 12px.
        print("\n=== INSTELLINGEN: EERSTE KOP ONDER HET BACKUPBLOK ===\n")
        gaten = await page.evaluate("""() => {
            nav('settings');
            const uit = {};
            for (const [tab, id] of [['main','settingsTabMain'],['whs','settingsTabWhs'],['data','settingsTabData']]) {
                switchSettingsTab(tab);
                const blok = document.getElementById('backupStatusTop').getBoundingClientRect();
                // De TEKST van de kop, niet zijn kader: opvulling zit binnen het kader.
                const el = document.getElementById(id).firstElementChild;
                const r = document.createRange(); r.selectNodeContents(el);
                uit[tab] = Math.round(r.getBoundingClientRect().top - blok.bottom);
            }
            return uit;
        }""")
        print(f"   ruimte per tabblad: {gaten}")
        check("de eerste kop staat op alle drie de tabbladen even ver onder het blok",
              len(set(gaten.values())), 1)

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
