"""Het venster 'Club bestaat al' (1352898-019).

Een club inlezen die je al hebt, vraagt of hij overschreven mag worden. Tot 018 bouwde
importCourseData dat venster met de hand na, en zette het niet alles terug wat
showConfirmModal wel terugzet. Na een eerdere melding bleef er iets van hangen:
  - de titel bleef rood (van een foutmelding ervoor);
  - de tweede knop heette 'Sluiten' in plaats van 'Annuleren'.
Nu loopt het via showConfirmModal: 'Overschrijven' en 'Annuleren'. Dat Annuleren geen
actie van een eerder venster uitvoert, ging al goed (closeConfirmModal ruimt die op); de
test bewaakt het wel.
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import SEED, app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

ECHT = json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))
CLUBS = {c['club']: c for c in ECHT}
EEN = ECHT[0]
INLEZEN = """(c) => { const f = new File([JSON.stringify(c)], 'club.json', {type: 'application/json'});
  const inp = document.createElement('input'); inp.type = 'file'; Object.defineProperty(inp, 'files', {value: [f]}); importCourseData(inp); }"""
VENSTER = """() => { const b = document.getElementById('confirmModalBtn'), c = document.getElementById('confirmModalCancelBtn'), t = document.getElementById('confirmModalTitle');
  return { open: !document.getElementById('confirmModal').classList.contains('hidden'), titel: t.textContent, rood: t.style.color !== '',
           knop: b.textContent, knopZichtbaar: getComputedStyle(b).display !== 'none', tweede: c.textContent }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, []])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)

        print("\n=== NA EEN EERDER VENSTER EN EEN RODE MELDING ===\n")
        await pg.evaluate("""() => { window.__oud = 0;
          showConfirmModal('Eerder', 'een vraag', () => {}, 'Annuleren', () => { window.__oud++; }); closeConfirmModal();
          showInfoModal('Fout', 'een rode melding', 'red'); closeConfirmModal(); }""")
        await pg.evaluate(INLEZEN, EEN); await pg.wait_for_timeout(500)
        v = await pg.evaluate(VENSTER)
        check("het venster staat open", [v['open'], v['titel']], [True, 'Club bestaat al'])
        check("de titel is niet rood", v['rood'], False)
        check("de knoppen: Overschrijven en Annuleren", [v['knop'], v['knopZichtbaar'], v['tweede']], ['Overschrijven', True, 'Annuleren'])
        await pg.evaluate("() => document.getElementById('confirmModalCancelBtn').click()"); await pg.wait_for_timeout(200)
        check("Annuleren voert niets van een eerder venster uit", await pg.evaluate("() => window.__oud"), 0)
        check("en sluit het venster", await pg.evaluate("() => document.getElementById('confirmModal').classList.contains('hidden')"), True)

        print("\n=== DIRECT NA EEN ANDER BEVESTIGVENSTER ===\n")
        await pg.evaluate("() => { window.__oud = 0; showConfirmModal('Eerder', 'een vraag', () => {}, 'Annuleren', () => { window.__oud++; }); closeConfirmModal(); }")
        await pg.evaluate(INLEZEN, EEN); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.getElementById('confirmModalCancelBtn').click()"); await pg.wait_for_timeout(200)
        check("Annuleren voert de actie van het vorige venster niet uit", await pg.evaluate("() => window.__oud"), 0)

        print("\n=== OVERSCHRIJVEN ===\n")
        gewijzigd = json.loads(json.dumps(EEN)); gewijzigd['shortName'] = 'Proef'
        await pg.evaluate(INLEZEN, gewijzigd); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.getElementById('confirmModalBtn').click()"); await pg.wait_for_timeout(500)
        check("na Overschrijven staat de nieuwe versie in de opslag",
              json.loads(await pg.evaluate("() => localStorage.getItem('golf_clubs')"))[EEN['club']]['shortName'], 'Proef')
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
