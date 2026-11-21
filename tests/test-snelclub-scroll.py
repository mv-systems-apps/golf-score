"""Groeperen op club scrolt de eerste keer naar de voorrangsclub (1352898-031).

openQuickClub zet de eerste keer alles dicht behalve de voorrangsclub (de club van de
lopende ronde, anders de gekozen club bij Start, anders de thuisclub) en scrolt die kop
in beeld. Hij zocht die kop met [onclick*="club_…"], maar sinds 023 roept de kop
wisselIngeklapt(this) aan en staat de sleutel in data-sleutel. De kop werd dus niet meer
gevonden en er werd niet gescrold.

De test: thuisclub Papendal, groeperen op club voor het eerst, en scrollIntoView
afluisteren. Er moet precies één keer gescrold worden, naar de kop van Papendal, en die
kop moet open staan. Een tweede keer groeperen scrolt niet (je komt terug waar je was).
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, RONDES

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

AFLUISTER = """() => {
  window.__gescrold = [];
  const echt = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (o) {
    window.__gescrold.push({ inklap: this.dataset.inklap || null, sleutel: this.dataset.sleutel || null });
    return echt.call(this, o);
  };
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.evaluate("() => { localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_home_club', 'Papendal'); localStorage.removeItem('golf_default_club'); }")
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('archive'); }")
        await pg.wait_for_timeout(300)
        check("voorrangsclub is Papendal", await pg.evaluate("() => getPriorityGroupClub()"), 'Papendal')

        await pg.evaluate(AFLUISTER)
        await pg.evaluate("() => { delete window._clubTrkCollapsed; openQuickClub(); }")
        await pg.wait_for_timeout(400)
        gescrold = await pg.evaluate("() => window.__gescrold")
        check("eerste keer groeperen op club: één keer gescrold, naar de kop van Papendal",
              gescrold, [{'inklap': '_clubTrkCollapsed', 'sleutel': 'club_Papendal'}])
        check("en die club staat open", await pg.evaluate("() => window._clubTrkCollapsed.club_Papendal"), False)

        await pg.evaluate("() => { window.__gescrold = []; openQuickClub(); }")
        await pg.wait_for_timeout(400)
        check("tweede keer: niet gescrold", await pg.evaluate("() => window.__gescrold"), [])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
