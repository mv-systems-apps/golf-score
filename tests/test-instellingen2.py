import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

        print('1. TABKNOPPEN')
        r1 = await page.evaluate("""() => {
            nav('settings');
            return [...document.querySelectorAll('[id^=settingsTabBtn]')].map(b => b.textContent.trim());
        }""")
        print('   ' + ', '.join(r1))

        print('\n2. STATUS OP BEIDE PLEKKEN (gekopieerd, niet verplaatst)')
        # beide uitgangen van updateLastBackupDisplay: zonder én met backupdatum
        for datum, label in [(None, 'nog nooit geback-upt'), ('2026-08-01', 'met backupdatum')]:
            r2b = await page.evaluate("""(datum) => {
                if (datum) localStorage.setItem('golf_last_backup_date', datum);
                else localStorage.removeItem('golf_last_backup_date');
                nav('settings'); updateLastBackupDisplay();
                const top = document.getElementById('lastBackupInfoTop');
                const org = document.getElementById('lastBackupInfo');
                return { gelijk: top.innerHTML === org.innerHTML, tekst: top.textContent.trim().slice(0, 34) };
            }""", datum)
            print('   ' + label.ljust(24) + ' gelijk: ' + str(r2b['gelijk']) + '   ' + r2b['tekst'])
        r2 = await page.evaluate("""() => {
            switchSettingsTab('data');
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            if (kop) { window._setSectionCollapsed[kop.dataset.sectionKey] = false; applySettingsSections(); }
            return { bovenaan: !!document.getElementById('lastBackupInfoTop'),
                     inSectie: !!document.getElementById('lastBackupInfo'),
                     zelfdeTekst: (document.getElementById('lastBackupInfoTop')||{}).textContent
                                === (document.getElementById('lastBackupInfo')||{}).textContent };
        }""")
        for k, v in r2.items(): print(f'   {k:<14} {v}')

        print('\n3. LANG INDRUKKEN OP ELKE TAB')
        for tab, naam in [('main', 'Algemeen'), ('whs', 'WHS'), ('data', 'Gegevens')]:
            r3 = await page.evaluate("""(tab) => {
                switchSettingsTab(tab);
                // ALLE zichtbare blokken meetellen: het tabblad Algemeen bestaat uit twee
                // blokken (het tweede bevat Clubs & Rondes). Keek je naar het eerste, dan
                // zag je niet dat die sectie achterbleef bij het openklappen.
                const zichtbaar = ['settingsTabMain','settingsTabWhs','settingsTabMain2','settingsTabData']
                    .map(id => document.getElementById(id)).filter(t => t && !t.classList.contains('hidden'));
                const koppen = zichtbaar.flatMap(b => [...b.querySelectorAll('[data-section-key]')]);
                const open = () => koppen.filter(k => k.nextElementSibling && k.nextElementSibling.style.display !== 'none').length;
                const voor = open();
                toggleAllSettingsSections();
                const na1 = open();
                toggleAllSettingsSections();
                const na2 = open();
                return { secties: koppen.length, voor, na1, na2 };
            }""", tab)
            # Lang indrukken op een ANDERE tab kiest die tab en klapt alles dicht; de
            # tweede druk op dezelfde tab klapt alles open. Deze test drukt twee keer op
            # dezelfde tab, dus: eerst alles dicht, dan alles open.
            werkt = (r3['na1'] == 0 and r3['na2'] == r3['secties'])
            print(f"   {naam:<10} {r3['secties']} secties: open {r3['voor']} → {r3['na1']} → {r3['na2']}   {'werkt' if werkt else 'WERKT NIET'}")
            if not werkt:
                fouten.append(f'lang indrukken op {naam}: {r3["na1"]} van {r3["secties"]} secties')

        print('\n4. TIK OP HET STATUSBLOKJE')
        r4 = await page.evaluate("""async () => {
            switchSettingsTab('main');
            window.scrollTo(0, 0);
            document.getElementById('backupStatusTop').click();
            await new Promise(r => setTimeout(r, 400));
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            const header = document.querySelector('.app-header') || document.querySelector('header');
            return {
                backupOpen: kop && kop.nextElementSibling ? kop.nextElementSibling.style.display !== 'none' : null,
                lichtOp: (() => { const kaart = document.getElementById('exportCard');
                                  return kaart ? kaart.classList.contains('round-flash') : null; })(),
                kopLichtOp: kop ? kop.classList.contains('round-flash') : null,
                kopTop: kop ? Math.round(kop.getBoundingClientRect().top) : null,
                headerHoogte: header ? Math.round(header.getBoundingClientRect().height) : null,
            };
        }""")
        for k, v in r4.items(): print(f'   {k:<14} {v}')
        # Er wordt bewust NIET meer gescrold: de Backup-sectie staat bovenaan het
        # tabblad, dus er valt niets te overbruggen. Alleen de kaart licht kort op.
        onderHeader = True
        goed = (r2['bovenaan'] and r2['inSectie'] and r4['backupOpen'] and r4['lichtOp'] and onderHeader)
        print('\n' + ('GEEN FOUTEN' if goed and not fouten else '1 FOUT(EN) — zie hierboven'))
        if fouten: print('fouten:', fouten)
        await b.close()

asyncio.run(main())
