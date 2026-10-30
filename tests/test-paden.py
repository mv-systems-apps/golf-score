import asyncio, os, sys
from testdata import CLUBS, RONDES, APP, app_url, SEED
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))
        page.on('console', lambda m: fouten.append('console: ' + m.text[:90]) if m.type == 'error' else None)

        # 1. Verse installatie: geen enkele instelling, geen rondes
        await page.goto(app_url())
        await page.evaluate("() => localStorage.clear()")
        await page.reload(); await page.wait_for_timeout(800)
        print('1. VERSE INSTALLATIE (lege opslag)')
        print('   fouten bij het opstarten:', fouten or 'geen')

        # 2. Alle schermen langs, meerdere keren
        fouten.clear()
        for ronde in range(2):
            for s in ['setup', 'score', 'archive', 'stat', 'club', 'settings']:
                await page.evaluate("(s) => nav(s)", s)
                await page.wait_for_timeout(120)
        print('\n2. ALLE SCHERMEN TWEE KEER DOORLOPEN')
        print('   fouten:', fouten or 'geen')

        # 3. Met gegevens: de paden die de verwijderde controles raakten
        fouten.clear()
        await page.evaluate("""([clubs, rondes]) => {
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes));
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
        }""", [CLUBS, RONDES])
        await page.reload(); await page.wait_for_timeout(700)
        stappen = [
            ("de statustip verversen", "refreshTabDot()"),
            ("de meldingen in Rondes", "refreshStatusReminder()"),
            ("de backupregel", "updateLastBackupDisplay()"),
            ("na een backup", "naBackupBijwerken()"),
            ("de analyse opbouwen", "buildGameAnalysis()"),
            ("de analyse kopiëren", "copyAnalysisForAi && 1"),
            ("puttstatistieken aanzetten", "togglePuttsStats()"),
            ("naar Instellingen met oude backup", "nav('settings')"),
            ("naar het startscherm", "nav('setup')"),
            ("statistieken opbouwen", "renderPlayerStats()"),
            ("archief opbouwen", "tekenRondelijst()"),
            ("favoriete clubs ophalen", "getFavClubs().length"),
        ]
        print('\n3. DE PADEN DIE DE VERWIJDERDE CONTROLES RAAKTEN')
        for naam, code in stappen:
            r = await page.evaluate("""(code) => {
                try { eval(code); return 'ok'; } catch (e) { return 'FOUT: ' + e.message; }
            }""", code)
            print(f'   {naam:<36} {r}')
        print('\n   fouten onderweg:', fouten or 'geen')
        await b.close()

asyncio.run(main())
