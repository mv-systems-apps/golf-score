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
        resultaten = {}

        print('1. STAAT ER NOG BACKUPINFO BOVEN DE EXPORTMAP-REGEL?')
        r1 = await page.evaluate("""() => {
            nav('settings'); switchSettingsTab('data');
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            if (kop) { window._setSectionCollapsed[kop.dataset.sectionKey] = false; applySettingsSections(); }
            updateLastBackupDisplay();
            const kaart = document.getElementById('exportCard');
            const zichtbaar = [...kaart.children].filter(el => el.offsetParent !== null)
                .map(el => el.textContent.trim().slice(0, 30)).filter(Boolean);
            return { eersteZichtbaar: zichtbaar[0] || '(niets)', aantal: zichtbaar.length };
        }""")
        print(f"   eerste zichtbare regel in de kaart: {r1['eersteZichtbaar']!r}")
        # De eerste zichtbare regel in de kaart hoort de exportmap te zijn; staat er
        # backupinfo boven, dan is die naar boven verhuisd en hoort hij hier weg.
        resultaten['geenInfoBovenExport'] = r1['eersteZichtbaar'].startswith('Exportmap')

        print('\n2. BOVENSTE BLOKJE — beide uitgangen van de vulfunctie')
        for datum, label in [(None, 'nog nooit'), ('2026-08-01', 'met datum')]:
            r2 = await page.evaluate("""(datum) => {
                if (datum) localStorage.setItem('golf_last_backup_date', datum);
                else localStorage.removeItem('golf_last_backup_date');
                nav('settings'); updateLastBackupDisplay();
                const top = document.getElementById('lastBackupInfoTop');
                const topN = document.getElementById('newRoundsInfoTop');
                return { tekst: top.textContent.trim(), tweedeRegel: topN.textContent.trim(),
                         zichtbaar: top.offsetParent !== null };
            }""", datum)
            print(f"   {label:<12} \"{r2['tekst']}\" | \"{r2['tweedeRegel']}\" | zichtbaar: {r2['zichtbaar']}")
            resultaten['blokje-' + label] = bool(r2['tekst']) and r2['zichtbaar']

        print('\n3. TIK OP HET BLOKJE — welke kaart licht op, waar staat de kop?')
        r3 = await page.evaluate("""async () => {
            // Alle secties op de Gegevens-tab openklappen: anders past alles op één
            // scherm en valt er niets te scrollen, waardoor de test niets zou meten.
            // Alle secties op ALLE tabbladen openklappen: het tabblad waar je vandaan
            // komt moet lang genoeg zijn om te kunnen scrollen, anders meet de controle
            // op "springt naar boven" niets.
            document.querySelectorAll('[data-section-key]').forEach(k => {
                window._setSectionCollapsed[k.dataset.sectionKey] = false;
            });
            applySettingsSections();
            // Eerst een eind naar beneden scrollen, anders staat de pagina al bovenaan
            // en bewijst de controle daarop niets.
            switchSettingsTab('main');
            window.scrollTo(0, 900);
            await new Promise(r => setTimeout(r, 150));
            const scrollVoor = Math.round(document.scrollingElement.scrollTop);
            document.getElementById('backupStatusTop').click();
            await new Promise(r => setTimeout(r, 500));
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            const kaart = document.getElementById('exportCard');
            const header = document.querySelector('.app-header') || document.querySelector('header');
            return {
                kaartLichtOp: kaart ? kaart.classList.contains('round-flash') : null,
                kopLichtOp: kop ? kop.classList.contains('round-flash') : null,
                kopTop: kop ? Math.round(kop.getBoundingClientRect().top) : null,
                headerHoogte: header ? Math.round(header.getBoundingClientRect().height) : null,
                // Onderaan de pagina kan er niet verder gescrold worden; dan staat de kop
                // verder naar beneden en is dat geen fout.
                scrollVoor,
                scrollTop: Math.round(document.scrollingElement.scrollTop),
                kaartTop: kaart ? Math.round(kaart.getBoundingClientRect().top) : null,
                sectieOpen: kop && kop.nextElementSibling ? kop.nextElementSibling.style.display !== 'none' : null,
            };
        }""")
        for k, v in r3.items(): print(f'   {k:<16} {v}')
        # De juiste kaart licht op, de sectie klapt open, en de pagina springt naar
        # BOVEN — daar staat de backupstand, en juist die wil je zien als je erop tikt.
        resultaten['juisteKaartGemarkeerd'] = r3['kaartLichtOp'] and not r3['kopLichtOp']
        resultaten['sectieOpen'] = r3['sectieOpen']
        # De pagina hoort bovenaan te staan, zodat de backupstand zichtbaar is.
        resultaten['bovenaanNaTik'] = (r3['scrollVoor'] > 100 and r3['scrollTop'] == 0)

        print('\n4. ORANJE STIP — blijft op Algemeen, backupstand zichtbaar')
        r4 = await page.evaluate("""async () => {
            localStorage.setItem('golf_last_backup_date', '2020-01-01');
            localStorage.setItem('golf_rounds_changed', new Date().toISOString());
            switchSettingsTab('main');      // eerst netjes op Algemeen zetten
            nav('archive');
            await new Promise(r => setTimeout(r, 200));
            nav('settings');
            await new Promise(r => setTimeout(r, 600));
            const kop = document.querySelector('[data-section-key*="|Exporteren"]');
            const kaart = document.getElementById('exportCard');
            return { verouderd: isBackupOverdue(),
                     gegevensTabOpen: !document.getElementById('settingsTabData').classList.contains('hidden'),
                     algemeenTabOpen: !document.getElementById('settingsTabMain').classList.contains('hidden'),
                     backupInfoZichtbaar: (() => { const t = document.getElementById('lastBackupInfoTop');
                                                   return !!t && t.offsetParent !== null; })() };
        }""")
        for k, v in r4.items(): print(f'   {k:<16} {v}')
        # De stip stuurt nu NIET meer naar Gegevens: Instellingen opent gewoon op
        # Algemeen, en de backupstand is daar toch al zichtbaar.
        resultaten['stipBlijftOpAlgemeen'] = r4['algemeenTabOpen'] and not r4['gegevensTabOpen']
        resultaten['backupInfoZichtbaar'] = r4['backupInfoZichtbaar']

        print('\n5. EXPORTEREN WERKT NOG (de verborgen regels breken niets)')
        r5 = await page.evaluate("""() => {
            try { updateLastBackupDisplay(); toonNieuweRondesRegel(false); return { ok: true }; }
            catch (e) { return { ok: false, fout: e.message }; }
        }""")
        print('   vulfuncties draaien:', r5)
        resultaten['vulfuncties'] = r5['ok']

        alles = all(resultaten.values())
        print('\n' + ('GEEN FOUTEN' if alles and not fouten else '1 FOUT(EN): ' +
              ', '.join(k for k, v in resultaten.items() if not v)))
        if fouten: print('browserfouten:', fouten)
        await b.close()

asyncio.run(main())
