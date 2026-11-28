"""De kaart van een geplande ronde op het scorescherm op 300 px (review dagelijks gebruik 2,
13528FE-001): tot dan schoof 'Par 36' onder de ▶-knop (de teeregel brak niet af) en bleef er
een punt aan het eind van een regel staan ('Vr 20-11-2026 ·' en '10:30' eronder, net zo bij
club · baan). Nu gaat '9h · Par 36' als geheel naar een volgende regel, en de tijd en de baan
met hun punt ervoor. Op 360 px ziet de kaart er uit als voorheen.
"""
import asyncio, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

MEET = r"""() => { const k = document.querySelector('#scoreEmptyMsg .lege-open .lege-knop'); if (!k) return 'geen kaart';
  const acties = k.querySelector('.lege-knop-acties').getBoundingClientRect();
  const tee = [...k.querySelectorAll('.lege-knop-tee > *')], onder = tee.filter(e => e.getBoundingClientRect().right > acties.left + 0.5).map(e => e.textContent.trim());
  /* een punt aan het eind van een regel: het teken na '· ' staat lager dan de punt */
  const losse = [];
  for (const el of k.querySelectorAll('.lege-knop-wanneer, .lege-knop-waar')) {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) for (let i = 0; i < n.data.length; i++) if (n.data[i] === '·') {
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const p = r.getBoundingClientRect().top;
      let m = n, j = i + 1; while (m && j >= m.data.length) { m = w.nextNode(); j = 0; } if (!m) { losse.push(el.textContent.trim()); break; }
      while (m && /\s/.test(m.data[j])) { j++; if (j >= m.data.length) { m = w.nextNode(); j = 0; } }
      if (!m) break; const r2 = document.createRange(); r2.setStart(m, j); r2.setEnd(m, j + 1);
      if (r2.getBoundingClientRect().top > p + 4) losse.push(el.textContent.trim()); n = m; i = j; }
  }
  return { onder, losse, tekst: k.querySelector('.lege-knop-tekst').innerText.replace(/\s+/g, ' ').trim() }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 740})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        hoofd = await pg.evaluate("() => startPlayerName()")
        await pg.evaluate(PLAN % dag(2), [990901, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await pg.evaluate(PLAN % dag(2), [990902, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await pg.evaluate("() => { _legeOpen.gepland = undefined; nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(300)
        tekst = {}
        for w in (360, 320, 300):
            await pg.set_viewport_size({'width': w, 'height': 740}); await pg.wait_for_timeout(150)
            await pg.evaluate("() => verversLegeScoreKnoppen()"); await pg.wait_for_timeout(150)
            m = await pg.evaluate(MEET)
            if not isinstance(m, dict): check(f"{w} px: kaart gevonden", m, 'kaart'); continue
            tekst[w] = m['tekst']
            check(f"{w} px: niets van de teeregel onder de knoppen rechts", m['onder'], [])
            check(f"{w} px: geen punt aan het eind van een regel", m['losse'], [])
        check("dezelfde tekst op elke breedte (alleen anders afgebroken)", len(set(tekst.values())) == 1 and '9h · Par' in tekst.get(360, ''), True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
