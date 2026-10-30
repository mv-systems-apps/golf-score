import asyncio, os
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

CLUBS = {"Golfclub Heelsum": {"club": "Golfclub Heelsum", "shortName": "Heelsum", "courses": {
    "Airborne": {"tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120,
                          "holes": [{"par": 4 if i % 3 else 3, "si": i+1} for i in range(9)]}}},
                 "holeIds": [i+1 for i in range(9)]}}}}

def ronde(rid, datum, speler='Testspeler'):
    return {"id": rid, "date": datum, "time": "09:30", "player": speler, "hcp": 30.7,
            "club": "Golfclub Heelsum", "clubShort": "Heelsum", "track": "Airborne",
            "gender": "Heren", "tee": "Blauw", "CR": 34.5, "SR": 120, "PAR": 35, "chcp": 11,
            "qualifying": True, "total": 45, "totalStb": 15, "playedCount": 9, "holesCount": 9,
            "currentHole": 0, "started": True, "sd": 32.5, "sdFinal": 32.5,
            "holes": [{"id": i+1, "par": 4 if i % 3 else 3, "si": i+1, "phcp": 1,
                       "ppar": (4 if i % 3 else 3)+1, "score": 5} for i in range(9)]}

rondes = ([ronde(i, f'2026-0{(i % 8)+1}-1{i % 9}') for i in range(1, 7)] +
          [ronde(10+i, f'2025-0{(i % 8)+1}-1{i % 9}') for i in range(1, 7)] +
          [ronde(20+i, f'2026-0{(i % 8)+1}-2{i % 8}', 'Speler 2') for i in range(1, 4)])

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_player_name', 'Testspeler');
        }""", [CLUBS, rondes])
        await page.reload(); await page.wait_for_timeout(500)

        for naam, fn in [('geen indeling', ''), ('op categorie', 'toggleGroupByCategory()'),
                         ('op baan', 'toggleGroupByTrack()'), ('op speler', 'toggleGroupByPlayer()'),
                         ('op WHS', 'toggleGroupByWhs()')]:
            await page.evaluate("""(fn) => {
                zetGroepering(null);
                nav('archive');
                if (fn) eval(fn);
            }""", fn)
            await page.wait_for_timeout(250)
            uit = await page.evaluate("""() => {
                const res = [];
                document.querySelectorAll('#screen-archive > div, #savedList > div').forEach(el => {
                    const s = getComputedStyle(el);
                    const isKop = (el.classList.contains('year-sep')) ||
                                  (s.fontWeight === '800' && parseFloat(s.fontSize) >= 15 && el.querySelector('span'));
                    if (!isKop) return;
                    res.push({ soort: el.classList.contains('year-sep') ? 'jaar' : 'groepskop',
                               tekst: el.textContent.trim().slice(0, 16).replace(/\\s+/g, ' '),
                               grootte: s.fontSize, positie: s.position, padding: s.paddingTop + '/' + s.paddingBottom, marge: s.marginBottom,
                               totaalOnder: (parseFloat(s.paddingBottom) + parseFloat(s.marginBottom)) + 'px' });
                });
                return res;
            }""")
            print('\n=== ' + naam + ' ===')
            gezien = set()
            for r in uit:
                k = (r['soort'], r['grootte'], r['padding'])
                if k in gezien: continue
                gezien.add(k)
                print(f"  {r['soort']:10} {r['tekst']:18} {r['grootte']:>6}  positie {r['positie']:8} padding {r['padding']}  marge-onder {r['marge']}  TOTAAL ONDER {r['totaalOnder']}")
            if not uit: print('  (geen koppen)')
        await b.close()

asyncio.run(main())
