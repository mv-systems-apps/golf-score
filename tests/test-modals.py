import asyncio, os, sys
from testdata import CLUBS, RONDES, APP, app_url, SEED
from playwright.async_api import async_playwright

# rondes in verschillende staten
EXTRA = [
    dict(RONDES[0], id=900, date='2026-10-01', playedCount=9, holesCount=9),                     # af
    dict(RONDES[0], id=901, date='2026-10-02', playedCount=4, holesCount=9,
         holes=[dict(h, score=(5 if i < 4 else None)) for i, h in enumerate(RONDES[0]['holes'])]),  # half
    dict(RONDES[0], id=902, date='2026-10-03', playedCount=0, holesCount=9,
         holes=[dict(h, score=None) for h in RONDES[0]['holes']]),                                # gepland
]

async def meet(page, bestand):
    await page.goto('file://' + bestand)
    await page.evaluate("""([clubs, rondes]) => {
        localStorage.clear();
        localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes));
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_home_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_profile_name', 'Testspeler');
    }""", [CLUBS, RONDES + EXTRA])
    await page.reload(); await page.wait_for_timeout(700)
    uit = {}
    for rid, label in [(900, 'afgeronde ronde'), (901, 'halve ronde'), (902, 'geplande ronde')]:
        r = await page.evaluate("""(rid) => {
            const saved = loadSavedRounds();
            const idx = saved.findIndex(r => String(r.id) === String(rid));
            nav('archive');
            openRoundInfoModal(idx);
            const infoTitel = (document.getElementById('roundInfoTitle') || {}).textContent || '';
            const qualZichtbaar = !document.getElementById('editQualifyToggle')?.closest('.fg')?.classList.contains('hidden');
            closeRoundInfoModal();
            openRoundResultModal(idx);
            const resZichtbaar = !document.getElementById('roundResultModal').classList.contains('hidden');
            const sdWaarde = (document.getElementById('editSdCalc') || {}).value || '';
            closeRoundResultModal();
            return { infoTitel: infoTitel.trim(), qualZichtbaar, resZichtbaar, sdWaarde,
                     warn: roundHasWarning(saved[idx]) };
        }""", rid)
        uit[label] = r
    return uit

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:110]))
        voor = await meet(page, os.environ.get('APP_VOOR', APP))
        na = await meet(page, APP)
        await b.close()
    print('GEDRAG VAN DE TWEE BEWERKVENSTERS\n')
    alles = True
    for k in voor:
        gelijk = voor[k] == na[k]
        alles = alles and gelijk
        print(('  ok   ' if gelijk else ' VERSCHIL ') + k)
        print('        voor: ' + str(voor[k]))
        if not gelijk: print('        na  : ' + str(na[k]))
    print('\n' + ('gedrag ongewijzigd' if alles else 'ER IS IETS VERANDERD'))
    if fouten: print('browserfouten:', '; '.join(fouten[:3]))

asyncio.run(main())
