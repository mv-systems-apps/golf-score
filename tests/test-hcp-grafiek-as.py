"""De handicapgrafiek op Statistiek (eindcontrole 13528FF-001): valt een gekleurd label op de
as (Low HI, softcap, hardcap of je huidige handicap) over een grijs asgetal, dan vervalt dat
asgetal. Tot dan stak het half onder het label uit ('34' achter '33.5').
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

MEET = """() => { const svg = document.querySelector('#sdChart svg'); if (!svg) return null;
  const grijs = [...svg.querySelectorAll('text')].filter(t => t.getAttribute('x') === '2' && t.getAttribute('font-size') === '10').map(t => ({ v: t.textContent, y: parseFloat(t.getAttribute('y')) - 4 }));
  const labels = [...svg.querySelectorAll('rect')].filter(r => r.getAttribute('x') === '0' && r.getAttribute('height') === '12').map(r => parseFloat(r.getAttribute('y')) + 6);
  return { grijs: grijs.map(g => g.v), overlap: grijs.filter(g => labels.some(y => Math.abs(g.y - y) < 10)).map(g => g.v), labels: labels.length }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 900})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("() => nav('stat')"); await pg.wait_for_timeout(600)
        m0 = await pg.evaluate(MEET)
        check("de grafiek staat er, met asgetallen", bool(m0) and len(m0['grijs']) >= 2, True)
        # zet de Low HI zo dat de softcap (Low HI + 3) vlak bij het middelste asgetal valt
        # het middelste asgetal is round((min + max) / 2); de huidige-hcp-label kan hem al verbergen
        waarden = sorted(float(v) for v in (m0['grijs'] if m0 else []))
        midden = round((waarden[0] + waarden[-1]) / 2) if len(waarden) >= 2 else None
        if midden is not None:
            await pg.evaluate("(v) => { storage.setItem('golf_low_hi', String(v)); storage.setItem('golf_lowhi_graph', 'on'); nav('setup'); nav('stat'); }", round(midden - 3 - 0.4, 1))
            await pg.wait_for_timeout(600)
            m1 = await pg.evaluate(MEET)
            check("met Low HI: er staan gekleurde labels op de as", bool(m1) and m1['labels'] >= 3, True)
            check("geen grijs asgetal half onder een gekleurd label", m1 and m1['overlap'], [])
            check("de andere asgetallen blijven staan", bool(m1) and len(m1['grijs']) >= 1, True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
