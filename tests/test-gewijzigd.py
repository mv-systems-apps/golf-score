import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:110]))
        await page.goto(app_url())
        await page.evaluate(SEED, [CLUBS, RONDES])
        await page.reload(); await page.wait_for_timeout(700)
        res = {}

        async def naBackup():
            await page.evaluate("""() => {
                localStorage.setItem('golf_last_backup_date', todayISO());
                localStorage.setItem('golf_last_backup_ts', new Date().toISOString());
                localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
                legBackupInhoudVast();
                localStorage.removeItem('golf_rounds_changed');
            }""")

        async def proef(naam, code, verwachtStempel):
            await naBackup()
            r = await page.evaluate("""(code) => {
                try { eval(code); } catch (e) { return { fout: e.message }; }
                nav('settings'); updateLastBackupDisplay();
                return { stempel: isErIetsOnveiligs(),
                         regel: document.getElementById('newRoundsInfoTop').textContent.trim() };
            }""", code)
            goed = r.get('stempel') == verwachtStempel
            res[naam] = goed
            merk = '  ok  ' if goed else ' FOUT '
            print(f"{merk}{naam:<46} stempel: {str(r.get('stempel')):<6} (verwacht {verwachtStempel})  \"{r.get('regel','')[:26]}\"")

        print('RAAKT DE BACKUP NIET → GEEN STEMPEL\n')
        await proef('ronde plannen', """
            const s = loadSavedRounds();
            s.push({ id: 999001, date: '2026-12-01', time: '09:00', player: 'Testspeler',
                     holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score:null})),
                     qualifying: true });
            setRoundsAndMark(JSON.stringify(s));""", False)
        await proef('geplande ronde verwijderen', """
            const s = loadSavedRounds().filter(r => String(r.id) !== '999001');
            setRoundsAndMark(JSON.stringify(s));""", False)
        await proef('geplande ronde verzetten naar andere datum', """
            const s = loadSavedRounds();
            s.push({ id: 999002, date: '2026-12-02', time: '10:00', player: 'Testspeler',
                     holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score:null})), qualifying: true });
            setRoundsAndMark(JSON.stringify(s));
            const s2 = loadSavedRounds();
            const g = s2.find(r => String(r.id) === '999002');
            if (g) g.date = '2026-12-09';
            setRoundsAndMark(JSON.stringify(s2));""", False)
        await proef('halve ronde bijwerken (nog niet af)', """
            const s = loadSavedRounds();
            const half = s.find(r => !isRondeAf(r) && (r.holes||[]).some(h => h.score !== null));
            if (half) half.holes[0].score = (half.holes[0].score || 4) + 1;
            setRoundsAndMark(JSON.stringify(s));""", False)

        print('\nRAAKT DE BACKUP WÉL → STEMPEL\n')
        await proef('afgeronde ronde: notitie wijzigen', """
            const s = loadSavedRounds();
            const af = s.find(r => isRondeAf(r));
            if (af) af.note = 'test ' + Date.now();
            setRoundsAndMark(JSON.stringify(s));""", True)
        await proef('afgeronde ronde: score wijzigen', """
            const s = loadSavedRounds();
            const af = s.find(r => isRondeAf(r));
            if (af) af.holes[0].score = (af.holes[0].score || 4) + 1;
            setRoundsAndMark(JSON.stringify(s));""", True)
        await proef('afgeronde ronde verwijderen', """
            const s = loadSavedRounds();
            const af = s.find(r => isRondeAf(r));
            // Bewust verwijderen: net als in de app markeren, anders houdt de rem
            // op verlies van ingevulde rondes deze actie terecht tegen.
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(s.filter(r => r !== af))));""", True)
        await proef('nieuwe ronde afronden', """
            const s = loadSavedRounds();
            s.push({ id: 999003, date: '2026-11-01', time: '09:00', player: 'Testspeler', hcp: 30.7,
                     club: 'Golfclub Heelsum', clubShort: 'Heelsum', track: 'Airborne',
                     gender: 'Heren', tee: 'Blauw', CR: 34.5, SR: 120, PAR: 35, chcp: 11,
                     qualifying: true, holesCount: 9, sdFinal: 30.2,
                     holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score:5})) });
            setRoundsAndMark(JSON.stringify(s));""", True)

        print('\nRANDGEVAL: exporteren zet de stempel weer uit')
        await page.evaluate("""() => {
            localStorage.setItem('golf_last_backup_date', todayISO());
            localStorage.setItem('golf_last_backup_ts', new Date().toISOString());
            localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
            legBackupInhoudVast();
            localStorage.removeItem('golf_rounds_changed');
            nav('settings'); updateLastBackupDisplay();
        }""")
        r2 = await page.evaluate("""() => ({ regel: document.getElementById('newRoundsInfoTop').textContent.trim(),
                                             verborgen: document.getElementById('newRoundsInfoTop').classList.contains('hidden') })""")
        print(f"   regel na een backup: \"{r2['regel']}\" (verborgen: {r2['verborgen']})")
        res['naBackupSchoon'] = r2['verborgen'] or r2['regel'] == ''

        alles = all(res.values())
        print('\n' + ('GEEN FOUTEN' if alles and not fouten else
                      '1 FOUT(EN): ' + ', '.join(k for k, v in res.items() if not v)))
        if fouten: print('browserfouten:', fouten)
        await b.close()

asyncio.run(main())
