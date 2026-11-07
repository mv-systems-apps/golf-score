"""Op een rode knop hoort alles wit te zijn — tekst én pictogram.

In de lichte modus is de variabele --white juist donker. Een knop die rood wordt bij
het bevestigen kreeg daardoor zwarte tekst op rood, en een pictogram met een eigen
kleur (zoals het prullenbakje) bleef zelfs zwart als de knoptekst al wit was.

Deze test meet de WERKELIJK berekende kleuren in de browser, in beide modi, en zoekt
zelf alle knoppen op die op dat moment een rode achtergrond hebben — dus ook knoppen
die later worden toegevoegd, zonder dat deze test daarvoor hoeft te worden aangepast.
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
                "tees": {
                    "Heren": {"Wit": {"CR": 35.0, "SR": 120,
                                      "holes": [{"par": 4, "si": i + 1} for i in range(9)]},
                              "Geel": {"CR": 34.0, "SR": 116,
                                       "holes": [{"par": 4, "si": i + 1} for i in range(9)]}},
                },
            }
        },
    }
}

RONDE = {
    "id": 1, "date": "2026-09-20", "time": "10:00", "player": "Tester", "hcp": 30.7,
    "club": "Testclub", "clubShort": "TC", "track": "Baan", "gender": "Heren",
    "tee": "Wit", "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 11, "qualifying": True,
    "note": "", "total": 45, "totalStb": 18, "playedCount": 9, "holesCount": 9,
    "currentHole": 0, "started": True, "sd": 30.0, "sdFinal": 30.0, "pcc": 0,
    "holes": [{"id": "H%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5,
               "score": 5, "putts": 2} for i in range(9)],
}

# Zoekt ELKE knop in de pagina op die rood is of rood kan worden, en meet de werkelijk
# berekende kleuren van de knop, van alles wat erin staat, en van de lijnen en vlakken
# van een eventueel pictogram. Knoppen die pas bij een bevestiging rood worden, krijgen
# die toestand hier tijdelijk opgelegd — zo wordt de afspraak zelf getoetst, zonder dat
# de test elk scherm hoeft na te bootsen.
METEN = """
(zetOpScherp) => {
  const naarRgb = t => {
    const m = (t || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
    return m ? [+m[1], +m[2], +m[3]] : null;
  };
  const isRood = c => c && c[0] > 120 && c[1] < 90 && c[2] < 90;
  const isWit  = c => c && c[0] > 200 && c[1] > 200 && c[2] > 200;
  const resultaat = [];
  document.querySelectorAll('button').forEach(knop => {
    const eigenStijl = knop.getAttribute('style') || '';
    const wasArmed = knop.classList.contains('confirm-armed');
    if (zetOpScherp) {
      knop.classList.add('confirm-armed');
      knop.style.background = 'var(--red)';
    }
    const st = getComputedStyle(knop);
    const rood = isRood(naarRgb(st.backgroundColor));
    const problemen = [];
    if (rood) {
      if ((knop.textContent || '').trim() && !isWit(naarRgb(st.color))) {
        problemen.push('tekst ' + st.color);
      }
      knop.querySelectorAll('*').forEach(kind => {
        const ks = getComputedStyle(kind);
        if ((kind.textContent || '').trim() && !isWit(naarRgb(ks.color))) {
          problemen.push('binnen-tekst ' + ks.color);
        }
      });
      knop.querySelectorAll('svg path, svg polyline, svg line, svg rect, svg circle, svg polygon')
          .forEach(vorm => {
        const vs = getComputedStyle(vorm);
        if (vs.stroke && vs.stroke !== 'none' && !isWit(naarRgb(vs.stroke))) {
          problemen.push('lijn ' + vs.stroke);
        }
        if (vs.fill && vs.fill !== 'none' && !isWit(naarRgb(vs.fill))) {
          problemen.push('vlak ' + vs.fill);
        }
      });
      resultaat.push({
        naam: knop.id || (knop.textContent || '').trim().slice(0, 30) || '(pictogramknop)',
        problemen,
      });
    }
    if (zetOpScherp) {
      if (!wasArmed) knop.classList.remove('confirm-armed');
      knop.setAttribute('style', eigenStijl);
    }
  });
  return resultaat;
}
"""


fouten = []


async def meet(page, naam, modus, opScherp):
    knoppen = await page.evaluate(METEN, opScherp)
    if not knoppen:
        fouten.append(f"{naam} ({modus}): geen enkele rode knop gevonden — meet de test nog wel iets?")
        print(f" FOUT  {naam} ({modus}): geen rode knoppen gevonden")
        return
    slecht = [k for k in knoppen if k["problemen"]]
    for k in slecht:
        fouten.append(f"{naam} ({modus}) — {k['naam']}: {', '.join(k['problemen'])}")
        print(f" FOUT  {naam} ({modus}) — {k['naam']}: {', '.join(k['problemen'])}")
    if not slecht:
        namen = ', '.join(k["naam"] for k in knoppen[:4])
        print(f"  ok   {naam} ({modus}): {len(knoppen)} knoppen wit — {namen}"
              + (' …' if len(knoppen) > 4 else ''))


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""([clubs, ronde]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify([ronde]));
            localStorage.setItem('golf_default_club', 'Testclub');
            localStorage.setItem('golf_profile_name', 'Tester');
        }""", [CLUBS, RONDE])
        await page.reload()
        await page.wait_for_timeout(400)

        # De baaneditor erbij openen: die bevat de knoppen die deze sprint zijn bijgekomen.
        await page.evaluate("""() => {
            editorClub = 'Testclub';
            document.getElementById('editorClubName').value = 'Testclub';
            document.getElementById('editorShortName').value = 'TC';
            openCourseEditor('Baan');
            teeRows()[1]._holes[0] = { par: 6, si: teeRows()[1]._holes[0].si };
            renderHoleTeeChooser();
            _roundInfoIdx = 0;
            document.getElementById('roundInfoModal')?.classList.remove('hidden');
        }""")
        await page.wait_for_timeout(300)

        print("\n=== PAGINA, TABBALK EN SYSTEEMBALK ZIJN ÉÉN KLEUR ===\n")
        # Het html-element had zelf geen achtergrond; de kleur kwam alleen van body. Haalt
        # Android de kleur van de navigatiebalk op terwijl dat vlak onbeschilderd is — bij
        # scrollen, wisselen van scherm of doorveren — dan valt het systeem terug op zijn
        # eigen standaard en wordt de balk zwart.
        for donker in (True, False):
            await page.evaluate("""(donker) => {
                const cb = document.getElementById('themeToggle');
                nav('settings');
                switchSettingsTab('main');
                if (cb) { cb.checked = donker; toggleTheme(); }
            }""", donker)
            # De kleurovergang duurt .2s; eerder meten geeft de kleur van halverwege.
            await page.wait_for_timeout(400)
            kleuren = await page.evaluate("""() => {
                const per = {};
                ['setup', 'score', 'stat', 'archive', 'club', 'settings'].forEach(t => {
                    nav(t);
                    per[t] = getComputedStyle(document.documentElement).backgroundColor;
                });
                return {
                    perTab: per,
                    body: getComputedStyle(document.body).backgroundColor,
                    tabbalk: getComputedStyle(document.querySelector('.tabs')).backgroundColor,
                    theme: document.querySelector('meta[name=theme-color]').content,
                };
            }""")
            naam = 'donkere' if donker else 'lichte'
            uniek = sorted(set(kleuren["perTab"].values()))
            if len(uniek) != 1:
                fouten.append(f"{naam} modus: de pagina heeft per tabblad een andere kleur")
            elif uniek[0] != kleuren["body"] or uniek[0] != kleuren["tabbalk"]:
                fouten.append(f"{naam} modus: pagina {uniek[0]}, body {kleuren['body']}, "
                              f"tabbalk {kleuren['tabbalk']}")
            else:
                r, g, bl = [int(x) for x in uniek[0].replace('rgb(', '').replace(')', '').split(',')]
                hex_ = '#%02x%02x%02x' % (r, g, bl)
                if kleuren["theme"].lower() != hex_:
                    fouten.append(f"{naam} modus: systeembalk {kleuren['theme']}, pagina {hex_}")
                else:
                    print(f"  ok   {naam} modus: pagina, tabbalk en systeembalk zijn {hex_}")

        for modus in ("licht", "donker"):
            print(f"\n=== {modus.upper()}E MODUS ===\n")
            await page.evaluate("(licht) => document.documentElement.classList.toggle('light-mode', licht)",
                                modus == "licht")
            # Knoppen die altijd rood zijn (Instellingen, bevestigingsmodals)
            await meet(page, "altijd rood", modus, False)
            # En elke knop alsof hij op scherp staat
            await meet(page, "op scherp", modus, True)

        print("\n=== DE SYSTEEMBALKEN VOLGEN HET THEMA ===\n")
        # Android en iOS tinten de status- en navigatiebalk met de theme-color uit de kop
        # van de pagina. Die stond vast op het donkergroen: in donkere modus klopte dat,
        # in lichte modus niet — en dan koos Android zelf, wat de balk onderaan soms zwart
        # en soms groen maakte. De kleur volgt nu de tabbalk.
        for donker in (True, False):
            kleuren = await page.evaluate("""(donker) => {
                const cb = document.getElementById('themeToggle');
                nav('settings');
                switchSettingsTab('main');
                if (cb) { cb.checked = donker; toggleTheme(); }
                const balk = [...document.querySelectorAll('div,nav')].find(e =>
                    getComputedStyle(e).position === 'fixed' && e.querySelector('#tab-settings'));
                return {
                    themeColor: document.querySelector('meta[name=theme-color]').content,
                    tabbalk: balk ? getComputedStyle(balk).backgroundColor
                                  : getComputedStyle(document.body).backgroundColor,
                    licht: document.documentElement.classList.contains('light-mode'),
                };
            }""", donker)
            naam = 'donkere' if donker else 'lichte'
            if kleuren["licht"] is donker:
                fouten.append(f"{naam} modus: de klasse staat verkeerd")
            # De theme-color moet exact de tabbalk zijn; die grenst aan de navigatiebalk.
            r, g, bl = [int(x) for x in kleuren["tabbalk"]
                        .replace('rgb(', '').replace(')', '').split(',')]
            verwacht = '#%02x%02x%02x' % (r, g, bl)
            gekregen = kleuren["themeColor"].lower()
            if gekregen != verwacht:
                fouten.append(f"{naam} modus: systeembalk {gekregen}, tabbalk {verwacht}")
            else:
                print(f"  ok   {naam} modus: systeembalk en tabbalk zijn {verwacht}")

        if paginafouten:
            fouten.append('paginafouten')
            print("\nFOUTEN IN DE PAGINA:")
            for f in paginafouten[:5]:
                print("   " + f[:150])

        await browser.close()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        for f in fouten: print('   -', f)
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
