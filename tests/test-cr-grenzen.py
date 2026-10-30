import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

# CR-waarden zoals ze in de praktijk voorkomen
GELDIG = [
    (24.0, 'zeer korte 9-holes par-3-baan'),
    (33.2, '9 holes, kort'),
    (35.2, '9 holes, gebruikelijk'),
    (36.1, '9 holes, langer'),
    (50.0, '18 holes par-3-baan'),
    (69.1, '18 holes, gebruikelijk'),
    (72.3, '18 holes'),
    (80.0, 'zwaarste baan ter wereld'),
]
ONGELDIG = [
    (3.5,  'decimaalpunt verkeerd'),
    (7.2,  'cijfer vergeten'),
    (350,  'punt vergeten'),
    (721,  'te veel cijfers'),
    (0,    'niets ingevuld'),
    (95,   'boven elk bestaand bereik'),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 780})
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))
        await page.goto(app_url())
        await page.evaluate("""([clubs]) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
        }""", [CLUBS])
        await page.reload(); await page.wait_for_timeout(500)
        res = {}

        g = await page.evaluate("() => crGrenzen()")
        print(f"BEREIK: CR {g['min']} t/m {g['max']}  (geen onderscheid naar aantal holes)")
        res['bereik'] = g['min'] == 10 and g['max'] == 90

        print('\n1. GELDIGE WAARDEN WORDEN GEACCEPTEERD')
        for v, wat in GELDIG:
            ok = g['min'] <= v <= g['max']
            print(f"   {v:<6} {wat:<34} {'ok' if ok else 'GEWEIGERD (fout)'}")
            res[f'geldig-{v}'] = ok

        print('\n2. TYPEFOUTEN WORDEN GEWEIGERD')
        for v, wat in ONGELDIG:
            geweigerd = not (g['min'] <= v <= g['max'])
            print(f"   {v:<6} {wat:<34} {'geweigerd' if geweigerd else 'GEACCEPTEERD (fout)'}")
            res[f'ongeldig-{v}'] = geweigerd

        print('\n3. HETZELFDE BEREIK BIJ 9 EN 18 HOLES')
        r3 = await page.evaluate("""() => {
            const bak = document.getElementById('editorHoles');
            const meet = (n) => {
                if (bak) {
                    bak.innerHTML = '';
                    for (let i = 0; i < n; i++) {
                        const tr = document.createElement('tr');
                        tr.innerHTML = '<td><input class="hole-si" value="' + (i+1) + '"></td>';
                        bak.appendChild(tr);
                    }
                }
                return crGrenzen();
            };
            return { leeg: meet(0), negen: meet(9), achttien: meet(18) };
        }""")
        for naam, gg in r3.items():
            print(f"   {naam:<10} {gg['min']} t/m {gg['max']}")
        res['zelfdeBereik'] = (r3['leeg'] == r3['negen'] == r3['achttien'])

        print('\n4. FOUTMELDING ZONDER AANTAL HOLES')
        r4 = await page.evaluate("""() => {
            const g = crGrenzen();
            return g.holes
                ? `CR moet tussen ${g.min} en ${g.max} liggen (${g.holes} holes)`
                : `CR moet tussen ${g.min} en ${g.max} liggen`;
        }""")
        print('  ', r4)
        res['melding'] = 'holes' not in r4

        alles = all(res.values())
        print('\n' + ('GEEN FOUTEN' if alles and not fouten else
                      '1 FOUT(EN): ' + ', '.join(k for k, v in res.items() if not v)))
        if fouten: print('browserfouten:', fouten)
        await b.close()

asyncio.run(main())
