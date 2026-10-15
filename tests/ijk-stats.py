import asyncio, hashlib, json, os, sys
from playwright.async_api import async_playwright

from testdata import CLUBS, RONDES, APP, app_url

async def hashes(page, bestand):
    await page.goto('file://' + bestand)
    await page.evaluate("""([clubs, rondes]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_profile_name', 'Mark');
        localStorage.setItem('golf_profile_hcp', '30.7');
        localStorage.setItem('golf_track_putts', 'on');
        localStorage.setItem('golf_putts_stats', 'on');
        window._statClubCollapsed = { Golfclub_Heelsum: false, Papendal: false };
        ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open'));
    }""", [CLUBS, RONDES])
    await page.reload(); await page.wait_for_timeout(700)

    uit = {}
    # elke periode-instelling apart, plus de analyse en de scorekaart-tekst
    for periode in ['l20', 'jaar', 'alles']:
        h = await page.evaluate("""(periode) => {
            window._statChartPeriod = periode;
            nav('stat');
            renderPlayerStats();
            return document.getElementById('playerStats').innerHTML;
        }""", periode)
        uit['statistieken-' + periode] = h
    uit['analyse'] = await page.evaluate("() => JSON.stringify(buildGameAnalysis())")
    return {k: (hashlib.sha256(v.encode()).hexdigest()[:16], len(v)) for k, v in uit.items()}

async def main():
    doel = sys.argv[1] if len(sys.argv) > 1 else APP
    ijk = sys.argv[2] if len(sys.argv) > 2 else None
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:100]))
        h = await hashes(page, doel)
        await b.close()
    if ijk:
        oud = json.load(open(ijk))
        print('VERGELIJKING MET DE IJKMETING\n')
        gelijk = True
        for k in h:
            a, b2 = h[k], tuple(oud.get(k, ('?', 0)))
            ok = a[0] == b2[0]
            gelijk = gelijk and ok
            print(('  ok   ' if ok else ' AFWIJKING ') + k.ljust(24) +
                  f'{a[1]} tekens' + ('' if ok else f'   (was {b2[1]} tekens)'))
        print('\n' + ('IDENTIEK — de opgebouwde pagina is byte-voor-byte gelijk' if gelijk else 'VERSCHIL GEVONDEN'))
        if fouten: print('browserfouten: ' + '; '.join(fouten))
        sys.exit(0 if gelijk else 1)
    else:
        json.dump({k: list(v) for k, v in h.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ijkmeting.json'), 'w'), indent=1)
        print('IJKMETING VASTGELEGD:')
        for k, v in h.items():
            print('  ' + k.ljust(24) + v[0] + '   ' + str(v[1]) + ' tekens')
        if fouten: print('browserfouten: ' + '; '.join(fouten))

asyncio.run(main())
