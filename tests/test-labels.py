import asyncio, os
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto(app_url())
        await page.wait_for_timeout(500)
        await page.evaluate("() => nav('setup')")
        await page.wait_for_timeout(300)
        uit = await page.evaluate("""() => {
            const res = { gekoppeld: [], zonder: [], klikwerkt: null };
            document.querySelectorAll('input, textarea, select').forEach(el => {
                if (['hidden','file','checkbox','radio'].includes(el.type)) return;
                // de browser bepaalt zelf het toegankelijke label
                const label = el.labels && el.labels.length ? el.labels[0].textContent.trim()
                            : (el.getAttribute('aria-label') || '');
                (label ? res.gekoppeld : res.zonder).push({ id: el.id || '(geen id)', label: label.slice(0, 24), type: el.type });
            });
            // werkt tikken op een label? (zet de aandacht in het veld)
            const lab = document.querySelector('label[for="iName"]');
            if (lab) { lab.click(); res.klikwerkt = document.activeElement && document.activeElement.id === 'iName'; }
            return res;
        }""")
        print('velden met een werkend label of omschrijving:', len(uit['gekoppeld']))
        for v in uit['gekoppeld'][:16]:
            print('   ' + v['id'].ljust(24) + '"' + v['label'] + '"')
        print('\nvelden zonder:', len(uit['zonder']))
        for v in uit['zonder']:
            print('   ' + v['id'].ljust(24) + 'type ' + v['type'])
        print('\ntikken op een label zet de aandacht in het veld:', uit['klikwerkt'])
        # Slotoordeel: hooguit twee velden zonder label (verborgen hulpveld en het
        # alleen-lezen berekende dagresultaat), en tikken op een label moet werken.
        goed = uit['klikwerkt'] and len(uit['zonder']) <= 2
        print('\n' + ('GEEN FOUTEN' if goed else '1 FOUT(EN): ' +
              ('label-klik werkt niet' if not uit['klikwerkt'] else
               str(len(uit['zonder'])) + ' velden zonder label')))
        await b.close()

asyncio.run(main())
