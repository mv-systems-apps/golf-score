"""Datum en tijd passen naast elkaar in hun kaart, ook op een smalle telefoon (035).

Tot 034 stak het tijdveld op het startscherm rechts buiten de kaart: een datum- of
tijdveld wordt niet smaller dan zijn eigen inhoud, inclusief het kalender- of klokicoon.
Sinds 035 zijn die iconen onzichtbaar, mogen de velden krimpen en krijgt de datum iets
meer ruimte. Sinds 036 ligt het onzichtbare icoon over het hele veld: in 035 was het weg,
en dan opende een tik in Edge op Android niets.
Hetzelfde paar staat in het venster om een opgeslagen ronde te wijzigen (ronde-info).
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


RONDE = {
    "id": 1, "date": "2026-08-01", "time": "08:34", "player": "Testspeler",
    "hcp": 30.7, "club": "Golfclub Heelsum", "clubShort": "GC", "track": "Airborne",
    "gender": "Heren", "tee": "Blauw", "CR": 37.3, "SR": 141, "PAR": 36, "chcp": 11,
    "qualifying": True, "note": "", "total": 0, "totalStb": 0, "playedCount": 0, "holesCount": 9,
    "currentHole": 0, "started": False, "sd": None, "sdFinal": None, "pcc": 0,
    "holes": [{"id": "A%d" % (i + 1), "par": 4, "si": i + 1, "phcp": 1, "ppar": 5, "score": None} for i in range(9)],
}

PAST = """([datum, tijd]) => {
    const d = document.getElementById(datum), t = document.getElementById(tijd);
    const kaart = d.closest('.card') || d.closest('.modal-box') || d.closest('.modal') || d.parentElement.parentElement;
    const k = kaart.getBoundingClientRect(), rd = d.getBoundingClientRect(), rt = t.getBoundingClientRect();
    /* het icoon zelf is niet te meten (getComputedStyle kent dat pseudo-element niet):
       kijk of de regel die het verbergt bestaat en op dit veld van toepassing is */
    const regel = [...document.styleSheets].flatMap(sh => { try { return [...sh.cssRules]; } catch (e) { return []; } })
      .find(r => r.selectorText && /::-webkit-calendar-picker-indicator/.test(r.selectorText));
    /* onzichtbaar, maar over het hele veld: zo opent een tik overal de kiezer (036) */
    const overVeld = regel && regel.style.opacity === '0' && regel.style.position === 'absolute' &&
      ['top', 'right', 'bottom', 'left'].every(k => regel.style[k] === '0px') && regel.style.display !== 'none';
    const stijl = el => overVeld && el.matches(regel.selectorText.replace(/::-webkit-calendar-picker-indicator/g, '')) ? 'onzichtbaar over het veld' : 'anders';
    return { binnen: rt.right <= k.right + 0.5 && rd.left >= k.left - 0.5, naastElkaar: rd.right <= rt.left,
             datumBreder: rd.width > rt.width, iconen: [stijl(d), stijl(t)] };
}"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--lang=nl-NL'])
        for breed in (360, 320):
            page = await browser.new_page(viewport={"width": breed, "height": 740}, locale='nl-NL')
            paginafouten = []
            page.on('pageerror', lambda e: paginafouten.append(str(e)))
            await page.goto(app_url())
            await page.evaluate("""([clubs, r]) => {
                localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify([r]));
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
                localStorage.setItem('golf_profile_name', 'Testspeler');
                localStorage.setItem('golf_kenmerk_gevraagd', '1');
            }""", [CLUBS, RONDE])
            await page.reload()
            await page.wait_for_timeout(800)
            await page.evaluate("() => { nav('setup'); document.getElementById('iDate').value = '2026-10-23'; document.getElementById('iTime').value = '08:34'; }")
            print(f"\n=== STARTSCHERM, {breed} PX ===\n")
            m = await page.evaluate(PAST, ['iDate', 'iTime'])
            check("het tijdveld blijft binnen de kaart", m["binnen"], True)
            check("datum en tijd naast elkaar, zonder overlap", m["naastElkaar"], True)
            check("de datum krijgt meer ruimte dan de tijd", m["datumBreder"], True)
            check("kalender- en klokicoon onzichtbaar, maar over het hele veld (tikbaar)", m["iconen"], ['onzichtbaar over het veld'] * 2)

            print(f"\n=== RONDE-INFO, {breed} PX ===\n")
            await page.evaluate("() => { nav('archive'); doOpenRoundInfoModal(0); }")
            await page.wait_for_timeout(200)
            m = await page.evaluate(PAST, ['editDateInput', 'editTimeInput'])
            check("ook in het venster binnen de rand", m["binnen"], True)
            check("naast elkaar, zonder overlap", m["naastElkaar"], True)
            check("ook in het venster: icoon onzichtbaar over het hele veld", m["iconen"], ['onzichtbaar over het veld'] * 2)
            await page.evaluate("() => closeRoundInfoModal()")
            await page.wait_for_timeout(200)

            check("het veld zelf is relatief geplaatst (het icoon vult het veld)", await page.evaluate("() => ['iDate','iTime'].map(id => getComputedStyle(document.getElementById(id)).position)"), ['relative', 'relative'])
            check(f"geen fouten in de pagina ({breed} px)", paginafouten, [])
            await page.close()
        await browser.close()
    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("Alles in orde.")


asyncio.run(main())
