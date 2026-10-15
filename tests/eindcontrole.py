import asyncio, os, hashlib, sys
from testdata import CLUBS, RONDES, APP, app_url, SEED
from playwright.async_api import async_playwright

VOOR = os.environ.get('APP_VOOR', APP)
NA = APP

async def meet(page, bestand):
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
        ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open'));
    }""", [CLUBS, RONDES])
    await page.reload(); await page.wait_for_timeout(800)

    uit = {}
    for periode in ['l20', 'jaar', 'alles']:
        for clubOpen in [True, False]:
            for dagStand in ['weekend', 'days']:
                h = await page.evaluate("""([periode, clubOpen, dagStand]) => {
                    window._statChartPeriod = periode;
                    window._weekdayViewMode = dagStand;
                    window._statClubCollapsed = clubOpen ? { Golfclub_Heelsum: false, Papendal: false } : {};
                    nav('stat'); renderPlayerStats();
                    return document.getElementById('playerStats').innerHTML;
                }""", [periode, clubOpen, dagStand])
                uit[f'stat {periode} {"clubs-open" if clubOpen else "clubs-dicht"} {dagStand}'] = h
    for scherm in ['archive', 'club', 'settings', 'setup']:
        uit['scherm ' + scherm] = await page.evaluate("""(s) => {
            nav(s); const el = document.getElementById('screen-' + s);
            return el ? el.innerHTML : '(ontbreekt)';
        }""", scherm)
    uit['analyse'] = await page.evaluate("() => JSON.stringify(buildGameAnalysis())")
    uit['rondes in opslag'] = await page.evaluate("() => localStorage.getItem('golf_rounds')")
    return {k: (hashlib.sha256(v.encode()).hexdigest()[:16], len(v)) for k, v in uit.items()}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:110]))
        voor = await meet(page, VOOR)
        na = await meet(page, NA)
        await b.close()

    print('VERGELIJKING MET DE VERSIE VÓÓR ALLE OPSPLITSINGEN\n')
    afw = []
    for k in sorted(voor):
        a, c = voor[k], na.get(k, ('?', 0))
        if a[0] == c[0]:
            print('  ok   ' + k.ljust(36) + str(a[1]).rjust(7) + ' tekens')
        else:
            afw.append(k)
            print(' LET OP ' + k.ljust(36) + f'was {a[1]}, nu {c[1]} tekens')
    print('\n' + (f'{len(voor)} vergelijkingen, allemaal identiek' if not afw
                  else f'{len(afw)} afwijking(en) van de {len(voor)}'))
    if fouten: print('browserfouten: ' + '; '.join(fouten[:4]))

asyncio.run(main())
