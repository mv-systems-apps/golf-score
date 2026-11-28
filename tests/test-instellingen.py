import asyncio, os, sys
sys.path.insert(0, '/home/claude/tests')
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 780})
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))
        await page.goto(app_url())
        await page.evaluate(SEED, [CLUBS, RONDES])
        await page.reload(); await page.wait_for_timeout(700)

        print('1. BEGINSTAND: staan de secties dicht?')
        r = await page.evaluate("""() => {
            nav('settings');
            const koppen = [...document.querySelectorAll('[data-section-key]')];
            const open = koppen.filter(k => {
                const body = k.nextElementSibling;
                return body && body.style.display !== 'none';
            }).map(k => k.dataset.sectionKey.split('|')[1]);
            return { totaal: koppen.length, open, paginahoogte: document.getElementById('screen-settings').scrollHeight };
        }""")
        print(f"   {r['totaal']} secties, open: {r['open'] or '(geen)'}")
        print(f"   paginahoogte: {r['paginahoogte']}px")

        print('\n2. BACKUPREGEL: zichtbaar op alle drie de tabbladen?')
        for tab in ['main', 'whs', 'data']:
            r2 = await page.evaluate("""(tab) => {
                switchSettingsTab(tab);
                const el = document.getElementById('lastBackupInfoTop');
                const zichtbaar = el && el.offsetParent !== null;
                return { zichtbaar, tekst: el ? el.textContent.trim().slice(0, 40) : '(ontbreekt)' };
            }""", tab)
            print(f"   tab {tab:<6} zichtbaar: {str(r2['zichtbaar']):<6} \"{r2['tekst']}\"")

        print('\n3. TIK OP DE BACKUPREGEL: opent de Backup-sectie?')
        r3 = await page.evaluate("""() => {
            switchSettingsTab('main');
            document.getElementById('backupStatusTop').click();
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            const body = kop ? kop.nextElementSibling : null;
            return { tabNu: [...document.querySelectorAll('[id^=settingsTab]')].filter(t => t.id.startsWith('settingsTab') && !t.id.includes('Btn') && !t.classList.contains('hidden')).map(t => t.id),
                     backupOpen: body ? body.style.display !== 'none' : null };
        }""")
        print(f"   zichtbare tab: {r3['tabNu']}, Backup-sectie open: {r3['backupOpen']}")

        print('\n4. STAND BLIJFT NA HERSTART?')
        await page.reload(); await page.wait_for_timeout(600)
        r4 = await page.evaluate("""() => {
            nav('settings'); switchSettingsTab('data');
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            const body = kop ? kop.nextElementSibling : null;
            return { backupOpen: body ? body.style.display !== 'none' : null,
                     opgeslagen: localStorage.getItem('golf_set_sections') };
        }""")
        print(f"   Backup-sectie nog open: {r4['backupOpen']}")
        print(f"   opgeslagen stand: {(r4['opgeslagen'] or '')[:70]}")

        print('\n5. LANG INDRUKKEN: klapt alles open?')
        r5 = await page.evaluate("""() => {
            if (typeof settingsTabDown === 'function') { settingsTabDown(); }
            return { functieBestaat: typeof settingsTabDown === 'function' };
        }""")
        print('   lang-indrukken beschikbaar:', r5['functieBestaat'])
        # Alle secties starten dicht, ook bij een verlopen backup: de stip stuurt niet
        # meer naar Gegevens, want de backupstand staat al bovenaan elk tabblad.
        goed = (r['open'] == [] and r3['backupOpen'] and r4['backupOpen'])
        print()
        print('GEEN FOUTEN' if goed and not fouten else '1 FOUT(EN) — zie hierboven')
        await b.close()

asyncio.run(main())
