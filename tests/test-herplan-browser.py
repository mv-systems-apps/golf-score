import asyncio, os, json
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

CLUBS = {
    "Golfclub Heelsum": {
        "club": "Golfclub Heelsum", "shortName": "Heelsum",
        "courses": {
            "Airborne": {
                "tees": {"Heren": {"Blauw": {"CR": 34.5, "SR": 120, "HOLES": None},
                                    "Geel":  {"CR": 33.8, "SR": 116, "HOLES": None}},
                          "Dames": {"Rood": {"CR": 36.0, "SR": 124, "HOLES": None}}},
                "holeIds": [i + 1 for i in range(9)],
            },
            "Sandr": {
                "tees": {"Heren": {"Blauw": {"CR": 34.2, "SR": 118, "HOLES": None}},
                          "Dames": {"Rood": {"CR": 35.8, "SR": 122, "HOLES": None}}},
                "holeIds": [i + 1 for i in range(9)],
            },
        },
    }
}

# Par en SI horen bij de tee; alle tees van deze testbaan gebruiken dezelfde lijst.
TEE_HOLES = [{"par": 4 if i % 3 else 3, "si": i + 1} for i in range(9)]
for _course in CLUBS["Golfclub Heelsum"]["courses"].values():
    for _teemap in _course["tees"].values():
        for _vals in _teemap.values():
            _vals["holes"] = TEE_HOLES
            del _vals["HOLES"]


def ronde(rid, datum, tijd, speler, tee="Blauw", baan="Airborne", played=0):
    return {
        "id": rid, "date": datum, "time": tijd, "player": speler, "hcp": 30.7,
        "club": "Golfclub Heelsum", "clubShort": "Heelsum", "track": baan,
        "gender": "Heren", "tee": tee, "CR": 34.5, "SR": 120, "PAR": 35, "chcp": 11,
        "qualifying": True, "total": 0, "totalStb": 0, "playedCount": played,
        "holesCount": 9, "currentHole": 0, "started": True,
        "holes": [{"id": i + 1, "par": 4 if i % 3 else 3, "si": i + 1, "phcp": 1,
                   "ppar": (4 if i % 3 else 3) + 1, "score": (5 if i < played else None)} for i in range(9)],
    }

async def scenario(page, naam, rondes, klik_id, wijzig, verwacht):
    """Zet gegevens klaar, herplan een ronde, pas velden aan en start."""
    await page.evaluate("""([clubs, rondes]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_player_name', 'Testspeler');
        localStorage.setItem('golf_player_hcp', '30.7');
    }""", [CLUBS, rondes])
    await page.reload()
    await page.wait_for_timeout(350)

    uit = await page.evaluate("""([id, wijzig]) => {
        const log = [];
        try {
            herplanRonde(String(id));
            log.push('herplanIds=' + JSON.stringify(_herplanIds));
            log.push('speler2blok=' + player2Visible);
            log.push('banner=' + (document.getElementById('herplanBanner')?.textContent || '').slice(0, 70));
            // Net als een gebruiker: waarde zetten én de wijziging melden, zodat de
            // app zijn eigen datum/tijd-status bijwerkt.
            if (wijzig.datum) { const el = document.getElementById('iDate'); el.value = wijzig.datum;
                el.dispatchEvent(new Event('change', { bubbles: true })); }
            if (wijzig.tijd) { const el = document.getElementById('iTime'); el.value = wijzig.tijd;
                el.dispatchEvent(new Event('change', { bubbles: true })); }
            if (wijzig.tee)   { sel.tee = wijzig.tee; }
            if (wijzig.geenSpeler2 && player2Visible) togglePlayer2();
            startRound();
            // eventuele bevestigingsmodal automatisch doorzetten
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) { log.push('bevestiging getoond'); cb.click(); }
            const info = document.getElementById('infoModal');
            log.push('melding=' + (document.getElementById('confirmModalMessage')?.textContent || '').slice(0, 60));
        } catch (e) { log.push('FOUT: ' + e.message); }
        const rondesNa = JSON.parse(localStorage.getItem('golf_rounds') || '[]');
        return {
            log,
            aantal: rondesNa.length,
            rondes: rondesNa.map(r => r.player + ' ' + r.date + ' ' + (r.time || '-') + ' ' + r.tee + ' ' + r.track),
            duplicaten: (() => {
                const zien = {}, dup = [];
                rondesNa.forEach(r => { const k = r.date + '|' + (r.time || '') + '|' + r.player;
                    if (zien[k]) dup.push(k); zien[k] = 1; });
                return dup;
            })(),
        };
    }""", [klik_id, wijzig])

    goed = uit['aantal'] == verwacht['aantal'] and not uit['duplicaten']
    print(('  ok   ' if goed else ' FOUT  ') + naam)
    print('        rondes na afloop (' + str(uit['aantal']) + '): ' + ' | '.join(uit['rondes']))
    if uit['duplicaten']:
        print('        DUPLICATEN: ' + ', '.join(uit['duplicaten']))
    if not goed:
        print('        verwacht ' + str(verwacht['aantal']) + ' rondes')
        print('        log: ' + ' ; '.join(uit['log']))
    return goed

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on('pageerror', lambda e: print('        [browserfout] ' + str(e)[:120]))
        await page.goto(app_url())
        await page.wait_for_timeout(400)

        goed = []
        print('=== HERPLANNEN: END-TO-END IN DE BROWSER ===\n')

        goed.append(await scenario(page, 'alleen de tee wijzigen, zelfde tijdstip, één speler',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler')], 1, {'tee': 'Geel'}, {'aantal': 1}))

        goed.append(await scenario(page, 'twee spelers, zelfde tijdstip, tee gewijzigd',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '09:30', 'Speler 2')],
            1, {'tee': 'Geel'}, {'aantal': 2}))

        goed.append(await scenario(page, 'twee spelers, verzetten naar een andere dag',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '09:30', 'Speler 2')],
            1, {'datum': '2026-09-05', 'tijd': '10:00'}, {'aantal': 2}))

        goed.append(await scenario(page, 'twee spelers, speler 2 eruit gehaald',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '09:30', 'Speler 2')],
            1, {'geenSpeler2': True, 'tijd': '11:00'}, {'aantal': 1}))

        goed.append(await scenario(page, 'herplannen vanaf de kaart van speler 2',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '09:30', 'Speler 2')],
            2, {'tee': 'Geel'}, {'aantal': 2}))

        goed.append(await scenario(page, 'oude ongespeelde ronde uit het verleden verzetten',
            [ronde(1, '2026-07-01', '09:30', 'Testspeler')], 1, {'datum': '2026-09-10', 'tijd': '08:00'}, {'aantal': 1}))

        goed.append(await scenario(page, 'naast een gespeelde ronde van dezelfde dag',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(9, '2026-09-01', '14:00', 'Testspeler', played=9)],
            1, {'tee': 'Geel'}, {'aantal': 2}))


        goed.append(await scenario(page, 'verzetten naar een tijdstip waar je al een ronde hebt (moet blokkeren)',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(7, '2026-09-08', '09:00', 'Testspeler')],
            1, {'datum': '2026-09-08', 'tijd': '09:00'}, {'aantal': 2}))

        goed.append(await scenario(page, 'baan van de oude ronde bestaat niet meer',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler', baan='Verdwenen')], 1, {'tijd': '10:15'}, {'aantal': 1}))

        goed.append(await scenario(page, 'ronde zonder tijd verzetten',
            [ronde(1, '2026-09-01', '', 'Testspeler')], 1, {'datum': '2026-09-12', 'tijd': '07:45'}, {'aantal': 1}))

        goed.append(await scenario(page, 'drie rondes op dezelfde dag, verschillende tijden',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '12:00', 'Testspeler'),
             ronde(3, '2026-09-01', '15:00', 'Testspeler')], 2, {'tijd': '13:00'}, {'aantal': 3}))

        goed.append(await scenario(page, 'twee spelers, medespeler heeft al scores',
            [ronde(1, '2026-09-01', '09:30', 'Testspeler'), ronde(2, '2026-09-01', '09:30', 'Speler 2', played=5)],
            1, {'tijd': '16:00'}, {'aantal': 2}))
        print('\n' + ('ALLE SCENARIO\'S GOED' if all(goed) else str(goed.count(False)) + ' SCENARIO(S) MET EEN PROBLEEM'))
        await browser.close()

asyncio.run(main())
