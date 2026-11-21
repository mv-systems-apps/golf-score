"""Baan bewerken (poetsronde 13528FF-001): op 320 px past een CR als '34.5' in zijn vakje (raakte
de rechterrand), en er zit 16 px tussen de regel Holes en de knoppen (stond er tegenaan).
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 320, 'height': 740})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { nav('club'); openClubEditor('Golfclub Heelsum'); openCourseEditor('Airborne'); toggleEditorSection('tees'); }"); await pg.wait_for_timeout(300)
        m = await pg.evaluate("""() => {
          const velden = [...document.querySelectorAll('.cr-name-field, .sr-name-field')].filter(e => e.offsetParent);
          const past = velden.every(e => { const r = document.createRange(); r.selectNodeContents(e); const t = r.getBoundingClientRect(), k = e.getBoundingClientRect(), c = getComputedStyle(e);
            return t.left >= k.left + parseFloat(c.borderLeftWidth) + 1 && t.right <= k.right - parseFloat(c.borderRightWidth) - 1; });
          const holes = [...document.querySelectorAll('span')].find(e => e.offsetParent && e.textContent.trim() === 'Holes');
          const rij = document.getElementById('editorStatus').parentElement, knop = rij.querySelector('button');
          return [velden.length > 0, past, Math.round(knop.getBoundingClientRect().top - holes.parentElement.getBoundingClientRect().bottom)]; }""")
        check("320 px: elke CR en SR binnen zijn vakje, met wat ruimte", m[:2], [True, True])
        check("320 px: 16 px tussen de regel Holes en de knoppen", m[2] >= 16, True)
        print('    ruimte boven de knoppen:', m[2], 'px')
        # met Tees en Holes open op 360 × 640 is het venster langer dan het scherm: de knoppen
        # blijven onderin te zien (vaste knoppenrij, 13528FF-002)
        await pg.set_viewport_size({'width': 360, 'height': 640})
        await pg.evaluate("() => { toggleEditorSection('holes'); }"); await pg.wait_for_timeout(300)
        k = await pg.evaluate("""() => { const o = document.getElementById('courseEditorOverlay'), k = [...o.querySelectorAll('button')].find(b => /Opslaan/.test(b.textContent));
            const zie = () => { const r = k.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; };
            const uit = [o.scrollHeight > o.clientHeight, zie()]; o.scrollTop = 300; uit.push(zie()); return uit; }""")
        check("360 × 640, Tees en Holes open: het venster scrolt, Opslaan blijft in beeld", k, [True, True, True])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
