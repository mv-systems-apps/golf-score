"""
13528A7-002: de snelkoppelingen in manifest.json (lang drukken op het icoon, of Niagara).
golf-score.html?snel=start|score|statistiek opent het juiste tabblad, na het herstel van een
lopende ronde; 'snel' gaat daarna uit het adres, de rest blijft.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(testdata.APP))

async def main():
    fouten = []
    def eis(naam, kreeg, verwacht):
        ok = kreeg == verwacht
        print(('  OK   ' if ok else '  FOUT ') + naam + ('' if ok else f'  — kreeg {kreeg!r}, verwacht {verwacht!r}'))
        if not ok: fouten.append(naam)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        async def open_met(zoek, lopend=False):
            await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [CLUBS, testdata.RONDES])
            if lopend: await pg.evaluate("() => localStorage.setItem('golf_active_id', '80')")
            await pg.goto(app_url() + zoek); await pg.wait_for_timeout(600)
            return await pg.evaluate("() => [(document.querySelector('.tabs .tab.active') || {}).id, location.search, (typeof game !== 'undefined' && !!game.started)]")
        eis('gewoon opstarten zonder lopende ronde: het startscherm', (await open_met(''))[0], 'tab-setup')
        eis('snel=statistiek: het tabblad Statistiek, en snel uit het adres', await open_met('?snel=statistiek'), ['tab-stat', '', False])
        eis('snel=score zonder lopende ronde: het startscherm', (await open_met('?snel=score'))[0], 'tab-setup')
        eis('snel=score met een lopende ronde: de score', (await open_met('?snel=score', True))[:1], ['tab-score'])
        eis('snel=start met een lopende ronde: het startscherm, de ronde blijft lopen', await open_met('?snel=start', True), ['tab-setup', '', True])
        eis('snel=statistiek met een lopende ronde: het tabblad zoals het is (de rondestatistiek)', (await open_met('?snel=statistiek', True))[0], 'tab-stat')
        # de hele opslag van de lopende ronde: na snel=start precies gelijk aan gewoon openen
        opslag = "() => JSON.stringify(Object.keys(localStorage).filter(k => /^golf_(rounds|active_id|game)/.test(k)).sort().map(k => [k, localStorage.getItem(k)]))"
        # vergelijken met de stand direct na het klaarzetten, niet met een tweede keer openen
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [CLUBS, testdata.RONDES])
        await pg.evaluate("() => localStorage.setItem('golf_active_id', '80')"); klaar = await pg.evaluate(opslag)
        await pg.goto(app_url()); await pg.wait_for_timeout(1500); gewoon = await pg.evaluate(opslag)
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [CLUBS, testdata.RONDES])
        await pg.evaluate("() => localStorage.setItem('golf_active_id', '80')")
        await pg.goto(app_url() + '?snel=start'); await pg.wait_for_timeout(1500); na_start = await pg.evaluate(opslag)
        eis('snel=start met een lopende ronde: de opslag van de rondes verandert niet meer dan bij gewoon openen', [na_start == gewoon, 'golf_active_id' in na_start], [True, True])
        eis('en de lopende ronde zelf (golf_rounds, golf_active_id) is precies als na het klaarzetten', [x for x in json.loads(na_start) if x[0] in ('golf_rounds', 'golf_active_id')] == [x for x in json.loads(klaar) if x[0] in ('golf_rounds', 'golf_active_id')], True)
        eis('een onbekende opdracht: gaat uit het adres, het scherm blijft het gewone', await open_met('?snel=onzin'), ['tab-setup', '', False])
        eis('alleen snel gaat uit het adres; de rest blijft', (await open_met('?x=1&snel=start'))[1], '?x=1')
        await open_met('?snel=statistiek'); await pg.reload(); await pg.wait_for_timeout(600)
        eis('herladen herhaalt de opdracht niet', await pg.evaluate("() => (document.querySelector('.tabs .tab.active') || {}).id"), 'tab-setup')
        m = json.load(open(os.path.join(HIER, 'manifest.json'), encoding='utf-8'))
        s = m.get('shortcuts', [])
        eis('het manifest: drie snelkoppelingen', [(x['name'], x['url']) for x in s],
            [('Nieuwe ronde', './golf-score.html?snel=start'), ('Score', './golf-score.html?snel=score'), ('Statistiek', './golf-score.html?snel=statistiek')])
        eis('elk met een PNG van 192 die bestaat', all(i['type'] == 'image/png' and i['sizes'] == '192x192' and os.path.exists(os.path.join(HIER, i['src'])) for x in s for i in x['icons']) and len(s) == 3, True)
        eis('elk icoon twee keer: als any en als maskable (13528A7-004)', all([i.get('purpose') for i in x['icons']] == ['any', 'maskable'] for x in s), True)
        eis('geen paginafouten', pf, [])
        await b.close()
    print('\nGEEN FOUTEN' if not fouten else f'\n{len(fouten)} FOUT(EN)')
    sys.exit(1 if fouten else 0)

asyncio.run(main())
