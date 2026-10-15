import asyncio, os, sys
from testdata import CLUBS, RONDES, APP, app_url, SEED
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.evaluate("""([clubs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_profile_hcp', '30.7');
        }""", [CLUBS])
        await page.reload(); await page.wait_for_timeout(700)

        # Een echte ronde starten en scores invoeren zoals een gebruiker
        uit = await page.evaluate("""() => {
            nav('setup');
            document.getElementById('iName').value = 'Mark';
            document.getElementById('iHcp').value = '30.7';
            sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            const meting = [];
            for (let i = 0; i < 9; i++) {
                selectHole(i);
                armScoreChange(i, 5);          // score zetten zoals een tik op een knop
                clearScoreTap(false);          // bevestigen
                const opgeslagen = JSON.parse(localStorage.getItem('golf_rounds') || '[]')
                    .find(r => String(r.id) === localStorage.getItem('golf_active_id'));
                if (opgeslagen) {
                    const echtGespeeld = (opgeslagen.holes || []).filter(h => h.score != null).length;
                    meting.push({ hole: i + 1, teller: gespeeldeHoles(opgeslagen), werkelijk: echtGespeeld });
                }
            }
            const laatste = JSON.parse(localStorage.getItem('golf_rounds') || '[]')
                .find(r => String(r.id) === localStorage.getItem('golf_active_id'));
            return { meting, eind: laatste ? { teller: gespeeldeHoles(laatste), holes: laatste.holesCount,
                     werkelijk: (laatste.holes||[]).filter(h => h.score != null).length } : null };
        }""")
        print('LIVE TELLING TEGENOVER DE SCORES TIJDENS HET INVOEREN:\n')
        afwijkingen = 0
        for m in uit['meting']:
            gelijk = m['teller'] == m['werkelijk']
            if not gelijk: afwijkingen += 1
            print(f"  na hole {m['hole']}: teller {m['teller']}, werkelijk ingevuld {m['werkelijk']}   {'gelijk' if gelijk else 'LOOPT ACHTER'}")
        print()
        print('eindstand:', uit['eind'])
        print('afwijkingen:', afwijkingen, 'van de', len(uit['meting']))
        await b.close()

asyncio.run(main())
