import asyncio, hashlib, json, os, sys
from playwright.async_api import async_playwright

DATA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'echte-data.json')))

async def meet(page, bestand):
    await page.goto('file://' + bestand)
    await page.evaluate("""([clubs, rondes]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_profile_name', 'Testspeler');
        localStorage.setItem('golf_profile_hcp', '30.7');
        localStorage.setItem('golf_track_putts', 'on');
        localStorage.setItem('golf_putts_stats', 'on');
        ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open'));
    }""", [DATA['clubs'], DATA['rondes']])
    await page.reload(); await page.wait_for_timeout(900)

    uit = {}
    for periode in ['l20', 'jaar', 'alles']:
        uit['statistieken ' + periode] = await page.evaluate("""(p) => {
            _statChartPeriod = p;
            window._statClubCollapsed = { };
            nav('stat'); renderPlayerStats();
            return document.getElementById('playerStats').innerHTML;
        }""", periode)
    uit['archief'] = await page.evaluate("() => { nav('archive'); return document.getElementById('savedList').innerHTML; }")
    uit['analyse'] = await page.evaluate("() => JSON.stringify(buildGameAnalysis())")
    # de kerncijfers apart, want daar gaat het echt om
    uit['handicap en tellingen'] = await page.evaluate("""() => {
        const alle = loadSavedRounds();
        const speler = startPlayerName();
        const laatste20 = last20Qualifying(speler, alle);
        const whs = whsHandicap(laatste20, effectiveLowHi(speler, alle), esrMapFor(speler, alle));
        return JSON.stringify({
            rondes: alle.length,
            afgerond: alle.filter(isRondeAf).length,
            qualifying: laatste20.length,
            handicap: whs ? whs.value : null,
        });
    }""")
    return {k: (hashlib.sha256(v.encode()).hexdigest()[:16], len(v), v if k == 'handicap en tellingen' else '')
            for k, v in uit.items()}

async def main():
    doel = sys.argv[1] if len(sys.argv) > 1 else APP
    ijk = sys.argv[2] if len(sys.argv) > 2 else None
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:110]))
        h = await meet(page, doel)
        await b.close()
    if ijk:
        oud = json.load(open(ijk))
        gelijk = True
        for k in h:
            a, c = h[k], tuple(oud.get(k, ('?', 0, '')))
            ok = a[0] == c[0]
            gelijk = gelijk and ok
            print(('  ok   ' if ok else ' AFWIJKING ') + k.ljust(24) + str(a[1]).rjust(7) + ' tekens' + (('   ' + a[2]) if a[2] else ''))
        print('\n' + ('IDENTIEK met jouw echte gegevens' if gelijk else 'VERSCHIL GEVONDEN'))
        if fouten: print('browserfouten:', '; '.join(fouten[:3]))
        sys.exit(0 if gelijk else 1)
    else:
        json.dump({k: list(v) for k, v in h.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ijk-echt.json'), 'w'), indent=1)
        print('IJKMETING MET JOUW ECHTE GEGEVENS:')
        for k, v in h.items():
            print('  ' + k.ljust(24) + v[0] + '  ' + str(v[1]).rjust(7) + ' tekens' + (('   ' + v[2]) if v[2] else ''))
        if fouten: print('browserfouten:', '; '.join(fouten[:3]))

asyncio.run(main())
