"""De groepering van de rondelijst (1352898-022).

Tot 021 zaten er vijf vlaggen achter (_groupByPlanned/Category/Track/Player/Whs), die elke
knop met de hand moest zetten. Nu één waarde, archiefGroepering, met zetGroepering als enige
schrijver. Per handeling (tikken, lang indrukken, nog eens tikken, zoeken, springen naar een
ronde) staat er hooguit één groepering aan, en licht precies die knop op.

Twee plekken liepen tot 021 uit de pas:
  - naar een ronde springen (jumpToArchiveRound) zette de knoppen uit maar liet de agenda
    aan staan;
  - lang indrukken op 'groepeer op categorie' in het CLUBSCHERM zette de agenda in de
    rondelijst uit, terwijl de agendaknop goud bleef.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

# Welke groepering aan staat en welke knoppen goud zijn; werkt ook op versies met de vijf vlaggen.
STAND = """() => {
  let aan;
  if (typeof archiefGroepering !== 'undefined') aan = archiefGroepering ? [archiefGroepering] : [];
  else aan = [['gepland', '_groupByPlanned'], ['categorie', '_groupByCategory'], ['club', '_groupByTrack'],
              ['speler', '_groupByPlayer'], ['whs', '_groupByWhs']].filter(([, v]) => window[v]).map(([n]) => n);
  const knop = { groupByPlannedBtn: 'gepland', groupByCategoryBtn: 'categorie', groupByTrackBtn: 'club',
                 groupByPlayerBtn: 'speler', groupByWhsBtn: 'whs' };
  const goud = Object.keys(knop).filter(id => { const b = document.getElementById(id); return b && b.style.background === 'var(--gold)'; }).map(id => knop[id]);
  return [aan, goud];
}"""

# naam van de groepering, functie om aan te zetten, lange druk
KNOPPEN = [('gepland', 'toggleGroupByPlanned', 'alleGeplandeDichtOfOpen'),
           ('categorie', 'toggleGroupByCategory', 'alleCategorieenDichtOfOpen'),
           ('club', 'toggleGroupByTrack', 'alleClubsDichtOfOpen'),
           ('speler', 'toggleGroupByPlayer', 'alleSpelersDichtOfOpen'),
           ('whs', 'toggleGroupByWhs', 'setWhsShort')]

async def main():
    rs = [ronde(i, f'2026-05-{i:02d}') for i in range(1, 6)] + [ronde(9, '2027-01-02', played=0, putts=False)]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        await pg.evaluate(SEED, [CLUBS, rs])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(700)
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        st = lambda: pg.evaluate(STAND)

        print("\n=== ELKE KNOP: AAN, LANG INDRUKKEN, VAN ANDER NAAR ANDER, UIT ===\n")
        for naam, aan, lang in KNOPPEN:
            await pg.evaluate(f"() => {aan}()"); await pg.wait_for_timeout(80)
            check(f"{naam}: tikken zet alleen deze aan, en alleen deze knop is goud", await st(), [[naam], [naam]])
            await pg.evaluate(f"() => {lang}()"); await pg.wait_for_timeout(80)
            check(f"{naam}: lang indrukken houdt alleen deze aan", await st(), [[naam], [naam]])
            await pg.evaluate(f"() => {aan}()"); await pg.wait_for_timeout(80)
            check(f"{naam}: nog eens tikken zet hem uit", await st(), [[], []])
        for (n1, a1, _), (n2, a2, _) in zip(KNOPPEN, KNOPPEN[1:] + KNOPPEN[:1]):
            await pg.evaluate(f"() => {{ {a1}(); {a2}(); }}"); await pg.wait_for_timeout(80)
            check(f"van {n1} naar {n2}: alleen {n2}", await st(), [[n2], [n2]])
            await pg.evaluate(f"() => {a2}()"); await pg.wait_for_timeout(50)
        for naam, _, lang in KNOPPEN:
            await pg.evaluate(f"() => {lang}()"); await pg.wait_for_timeout(80)
            check(f"lang indrukken op {naam} vanuit een andere: alleen {naam}", await st(), [[naam], [naam]])

        print("\n=== ZOEKEN EN TERUG ===\n")
        await pg.evaluate("() => { toggleGroupByCategory(); toggleGroupByCategory(); toggleGroupByPlayer(); }"); await pg.wait_for_timeout(80)
        await pg.evaluate("() => { document.getElementById('archiveSearch').value = 'Testspeler'; zoekInRondes(); }"); await pg.wait_for_timeout(80)
        check("zoeken zet de groepering uit", await st(), [[], []])
        await pg.evaluate("() => { document.getElementById('archiveSearch').value = ''; herstelNaZoeken(); }"); await pg.wait_for_timeout(80)
        check("zoekveld leeg: terug naar speler", await st(), [['speler'], ['speler']])

        print("\n=== NAAR EEN RONDE SPRINGEN VANUIT DE AGENDA ===\n")
        await pg.evaluate("() => { toggleGroupByPlayer(); toggleGroupByPlanned(); }"); await pg.wait_for_timeout(80)
        check("vooraf: de agenda staat aan", await st(), [['gepland'], ['gepland']])
        await pg.evaluate("() => jumpToArchiveRound(3)"); await pg.wait_for_timeout(300)
        check("na springen: gewone lijst, geen knop goud", await st(), [[], []])

        print("\n=== LANG INDRUKKEN IN HET CLUBSCHERM ===\n")
        await pg.evaluate("() => { nav('archive'); toggleGroupByPlanned(); }"); await pg.wait_for_timeout(80)
        await pg.evaluate("() => { nav('club'); alleClubCategorieenDichtOfOpen(); nav('archive'); }"); await pg.wait_for_timeout(200)
        check("de groepering van de rondelijst blijft zoals hij was", await st(), [['gepland'], ['gepland']])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
