import asyncio, os
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

CLUBS = {"Golfclub Heelsum": {"club": "Golfclub Heelsum", "shortName": "Heelsum", "courses": {
    "Airborne": {"tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120,
                          "holes": [{"par": 4 if i % 3 else 3, "si": i+1} for i in range(9)]}}},
                 "holeIds": [i+1 for i in range(9)]}}}}

def ronde(rid, datum):
    return {"id": rid, "date": datum, "time": "09:30", "player": "Mark", "hcp": 30.7,
            "club": "Golfclub Heelsum", "clubShort": "Heelsum", "track": "Airborne",
            "gender": "Heren", "tee": "Blauw", "CR": 34.5, "SR": 120, "PAR": 35, "chcp": 11,
            "qualifying": True, "total": 45, "totalStb": 15, "playedCount": 9, "holesCount": 9,
            "currentHole": 0, "started": True, "sd": 32.5, "sdFinal": 32.5, "pcc": 0,
            "holes": [{"id": i+1, "par": 4 if i % 3 else 3, "si": i+1, "phcp": 1,
                       "ppar": (4 if i % 3 else 3)+1, "score": 5, "putts": 2} for i in range(9)]}

rondes = [ronde(i, f'2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}') for i in range(1, 61)]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_player_name', 'Mark');
        }""", [CLUBS, rondes])
        await page.reload(); await page.wait_for_timeout(600)

        print('Met 60 afgeronde rondes in de app:\n')
        for naam, code in [('Rondes openen', "nav('archive')"),
                           ('Statistieken openen', "nav('stat')"),
                           ('Startscherm openen', "nav('setup')"),
                           ('Analyse opbouwen', "buildGameAnalysis()")]:
            uit = await page.evaluate("""(code) => {
                let leesActies = 0, geparsteBytes = 0;
                const orig = Storage.prototype.getItem;
                Storage.prototype.getItem = function (k) {
                    leesActies++;
                    const v = orig.call(this, k);
                    if (k === 'golf_rounds' && v) geparsteBytes += v.length;
                    return v;
                };
                const t0 = performance.now();
                eval(code);
                const ms = performance.now() - t0;
                Storage.prototype.getItem = orig;
                return { ms: Math.round(ms), leesActies, mb: Math.round(geparsteBytes / 1024) };
            }""", code)
            print(f"  {naam:24} {uit['ms']:>4} ms   {uit['leesActies']:>4} leesacties   {uit['mb']:>5} kB aan rondes ingelezen")
        await b.close()

asyncio.run(main())
