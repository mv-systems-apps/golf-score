import asyncio, os
from playwright.async_api import async_playwright
from testdata import CLUBS, RONDES, APP, app_url, SEED

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        meldingen = []
        page.on('console', lambda m: meldingen.append(m.text[:80]) if m.type in ('warning', 'error') else None)
        await page.goto(app_url())

        print('=== CORRUPTE RONDES ===')
        await page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('golf_rounds', '{kapot json[[[');
            localStorage.setItem('golf_player_name', 'Testspeler');
        }""")
        await page.reload(); await page.wait_for_timeout(900)
        uit = await page.evaluate("""() => {
            const voor = localStorage.getItem('golf_rounds');
            const gelukt = setRoundsAndMark(JSON.stringify([{id: 1}]));   // poging tot overschrijven
            return { vlag: rondesOnleesbaar, schrijfLukte: gelukt,
                     ongewijzigd: localStorage.getItem('golf_rounds') === voor,
                     modalZichtbaar: !document.getElementById('confirmModal').classList.contains('hidden'),
                     modalTekst: (document.getElementById('confirmModalMessage').textContent || '').slice(0, 80) };
        }""")
        print('  vlag gezet            :', uit['vlag'])
        print('  overschrijven geweigerd:', uit['schrijfLukte'] is False)
        print('  gegevens ongewijzigd  :', uit['ongewijzigd'])
        print('  melding in beeld      :', uit['modalZichtbaar'], '|', uit['modalTekst'][:70])

        print('\n=== CORRUPTE CLUBGEGEVENS ===')
        await page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', 'geen json');
            localStorage.setItem('golf_rounds', '[]');
        }""")
        await page.reload(); await page.wait_for_timeout(900)
        uit2 = await page.evaluate("""() => {
            const voor = localStorage.getItem('golf_clubs');
            saveClubsToStorage();
            return { vlag: clubsOnleesbaar, ongewijzigd: localStorage.getItem('golf_clubs') === voor,
                     modalZichtbaar: !document.getElementById('confirmModal').classList.contains('hidden'),
                     modalTekst: (document.getElementById('confirmModalMessage').textContent || '').slice(0, 80) };
        }""")
        print('  vlag gezet            :', uit2['vlag'])
        print('  gegevens ongewijzigd  :', uit2['ongewijzigd'])
        print('  melding in beeld      :', uit2['modalZichtbaar'], '|', uit2['modalTekst'][:70])

        print('\n=== NORMALE GEGEVENS (mag niets veranderen) ===')
        await page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('golf_rounds', '[]');
        }""")
        await page.reload(); await page.wait_for_timeout(700)
        uit3 = await page.evaluate("""() => {
            const gelukt = setRoundsAndMark(JSON.stringify([{id: 1, date: '2026-01-01'}]));
            return { vlag: rondesOnleesbaar, schrijfLukte: gelukt,
                     opgeslagen: JSON.parse(localStorage.getItem('golf_rounds')).length,
                     modalZichtbaar: !document.getElementById('confirmModal').classList.contains('hidden') };
        }""")
        print('  vlag uit              :', uit3['vlag'] is False)
        print('  schrijven lukte       :', uit3['schrijfLukte'])
        print('  aantal opgeslagen     :', uit3['opgeslagen'])
        print('  geen melding          :', uit3['modalZichtbaar'] is False)
        await b.close()

asyncio.run(main())
