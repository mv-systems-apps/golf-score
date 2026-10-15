import asyncio, os
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

CLUBS = {"Golfclub Heelsum": {"club": "Golfclub Heelsum", "shortName": "Heelsum", "courses": {
    "Airborne": {"tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120,
                          "holes": [{"par": 4 if i % 3 else 3, "si": i+1} for i in range(9)]}}},
                 "holeIds": [i+1 for i in range(9)]}}}}

def ronde(rid, datum, played=9):
    return {"id": rid, "date": datum, "time": "09:30", "player": "Mark", "hcp": 30.7,
            "club": "Golfclub Heelsum", "clubShort": "Heelsum", "track": "Airborne",
            "gender": "Heren", "tee": "Blauw", "CR": 34.5, "SR": 120, "PAR": 35, "chcp": 11,
            "qualifying": True, "total": 45, "totalStb": 15, "playedCount": played, "holesCount": 9,
            "currentHole": 0, "started": True, "sd": 32.5, "sdFinal": 32.5,
            "holes": [{"id": i+1, "par": 4 if i % 3 else 3, "si": i+1, "phcp": 1,
                       "ppar": (4 if i % 3 else 3)+1, "score": (5 if i < played else None)} for i in range(9)]}

async def meet(page, rondes, extra=None):
    await page.evaluate("""([clubs, rondes, extra]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_player_name', 'Mark');
        Object.entries(extra || {}).forEach(([k, v]) => localStorage.setItem(k, v));
    }""", [CLUBS, rondes, extra or {}])
    await page.reload(); await page.wait_for_timeout(300)
    return await page.evaluate("""() => ({
        afgerond: afgerondeRondesCount(),
        totaal: loadSavedRounds().length,
        waarschuwing: isBackupOverdue(),
    })""")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.wait_for_timeout(300)
        vandaag = await page.evaluate("() => todayISO()")
        nu = await page.evaluate('() => new Date().toISOString()')
        afgerond3 = [ronde(1, '2026-08-01'), ronde(2, '2026-08-05'), ronde(3, '2026-08-10')]
        # Backup gemaakt bij deze 3 afgeronde rondes: de app legt de inhoud zelf vast.
        await meet(page, afgerond3, {'golf_last_backup_date': vandaag, 'golf_last_backup_ts': nu})
        inhoud = await page.evaluate("() => { legBackupInhoudVast(); return localStorage.getItem('golf_backup_inhoud'); }")
        na_backup = {'golf_last_backup_date': vandaag, 'golf_last_backup_ts': nu,
                     'golf_backup_inhoud': inhoud}

        uitkomsten = {}
        print('Uitgangspunt: backup gemaakt bij 3 afgeronde rondes\n')
        for naam, rondes in [
            ('niets veranderd', afgerond3),
            ('2 rondes GEPLAND erbij', afgerond3 + [ronde(4, '2026-09-01', played=0), ronde(5, '2026-09-05', played=0)]),
            ('1 geplande ronde half gespeeld', afgerond3 + [ronde(4, '2026-09-01', played=4)]),
            ('1 geplande ronde UITGESPEELD', afgerond3 + [ronde(4, '2026-09-01', played=9)]),
            ('2 rondes uitgespeeld', afgerond3 + [ronde(4, '2026-09-01', played=9), ronde(5, '2026-09-02', played=9)]),
        ]:
            r = await meet(page, rondes, na_backup)
            uitkomsten[naam] = r
            print(f"  {naam:34} afgerond {r['afgerond']}  (totaal {r['totaal']})  waarschuwing: {'JA' if r['waarschuwing'] else 'nee'}")
        # Slotoordeel: plannen en half spelen mogen NIET waarschuwen, een uitgespeelde
        # ronde WEL (vaste regel: iets niet in de backup = waarschuwing).
        verwacht = {
            'niets veranderd': False,
            '2 rondes GEPLAND erbij': False,
            '1 geplande ronde half gespeeld': False,
            '1 geplande ronde UITGESPEELD': True,
            '2 rondes uitgespeeld': True,
        }
        fouten = [k for k, v in verwacht.items()
                  if k in uitkomsten and uitkomsten[k]['waarschuwing'] != v]
        print()
        print('GEEN FOUTEN' if not fouten else str(len(fouten)) + ' FOUT(EN): ' + ', '.join(fouten))
        await b.close()

asyncio.run(main())
