import asyncio, os, sys
sys.path.insert(0, '/home/claude/tests')
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

async def start(page, autoNext, putts):
    await page.goto(app_url())
    await page.evaluate("""([clubs, autoNext, putts]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_profile_name', 'Testspeler');
        localStorage.setItem('golf_auto_next', autoNext ? 'on' : 'off');
        localStorage.setItem('golf_track_putts', putts ? 'on' : 'off');
    }""", [CLUBS, autoNext, putts])
    await page.reload(); await page.wait_for_timeout(500)
    await page.evaluate("""() => {
        nav('setup');
        sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw';
        document.getElementById('iName').value='Testspeler';
        document.getElementById('iHcp').value='30.7';
        startRound();
        const cb=document.getElementById('confirmModalBtn');
        if(cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
        nav('score'); renderScore();
    }""")
    await page.wait_for_timeout(200)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:110]))

        print('1. INSTELLING UIT (standaard) — moet blijven staan')
        await start(page, False, False)
        r = await page.evaluate("""() => {
            setCurrentHole(0); armScoreChange(0, 5); clearScoreTap(false);
            return { na: currentHole };
        }""")
        print(f"   hole na invoer: {r['na']}   {'ok (blijft op 0)' if r['na']==0 else 'FOUT'}")

        print('\n2. INSTELLING AAN — moet doorgaan naar de volgende lege hole')
        await start(page, True, False)
        r2 = await page.evaluate("""() => {
            const stappen = [];
            for (let n = 0; n < 3; n++) {
                const voor = currentHole;
                armScoreChange(currentHole, 5); clearScoreTap(false);
                stappen.push(voor + '→' + currentHole);
            }
            return stappen;
        }""")
        print('   ' + ', '.join(r2) + '   ' + ('ok' if r2 == ['0→1','1→2','2→3'] else 'FOUT'))

        print('\n3. CORRIGEREN van een ingevulde hole — moet blijven staan')
        r3 = await page.evaluate("""() => {
            setCurrentHole(1);                 // hole 2 heeft al een score
            const voor = currentHole;
            armScoreChange(1, 6); clearScoreTap(false);
            return { voor, na: currentHole, score: game.holes[1].score };
        }""")
        print(f"   van {r3['voor']} naar {r3['na']}, score nu {r3['score']}   {'ok (blijft staan)' if r3['na']==1 else 'FOUT'}")

        print('\n4. GAT IN DE RIJ — kijkt vooruit, springt niet terug')
        r4 = await page.evaluate("""() => {
            // holes 0,1,2 hebben scores; geef hole 4 ook een score, dan is 3 het gat
            setCurrentHole(4); armScoreChange(4, 5); clearScoreTap(false);
            const naVier = currentHole;
            setCurrentHole(3); armScoreChange(3, 5); clearScoreTap(false);
            return { naVier, naDrie: currentHole };
        }""")
        # Bewust VOORUIT kijken: na hole 5 ga je naar 6, niet terug naar het gat op 4.
        # Terugspringen zou verwarrend zijn tijdens het spelen; het gat vul je zelf in.
        print(f"   na hole 5 → {r4['naVier']} (verwacht 5: vooruit, niet terug naar het gat)")
        print(f"   na het gat op hole 4 → {r4['naDrie']} (verwacht 5)")
        print('   ' + ('ok' if r4['naVier']==5 and r4['naDrie']==5 else 'FOUT'))

        print('\n5. LAATSTE HOLE — mag niet terugspringen')
        r5 = await page.evaluate("""() => {
            for (let i = 0; i < 9; i++) { if (game.holes[i].score === null) { setCurrentHole(i); armScoreChange(i, 5); clearScoreTap(false); } }
            setCurrentHole(8); armScoreChange(8, 4); clearScoreTap(false);
            return { na: currentHole, ingevuld: game.holes.filter(h => h.score !== null).length };
        }""")
        print(f"   hole na de laatste: {r5['na']} (verwacht 8), ingevuld: {r5['ingevuld']}/9   {'ok' if r5['na']==8 else 'FOUT'}")

        print('\n6. MET PUTTS BIJHOUDEN AAN — mag NIET doorspringen')
        await start(page, True, True)
        r6 = await page.evaluate("""() => {
            setCurrentHole(0); armScoreChange(0, 5); clearScoreTap(false);
            return { na: currentHole, putts: game.holes[0].putts };
        }""")
        print(f"   hole na invoer: {r6['na']} (verwacht 0), putts gezet op {r6['putts']}   {'ok' if r6['na']==0 else 'FOUT'}")
        goed = (r['na']==0 and r2==['0→1','1→2','2→3'] and r3['na']==1
                and r4['naVier']==5 and r5['na']==8 and r6['na']==0)
        print()
        print('GEEN FOUTEN' if goed and not fouten else '1 FOUT(EN) — zie hierboven')
        await b.close()

asyncio.run(main())
