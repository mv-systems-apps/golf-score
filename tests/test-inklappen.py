"""In- en uitklappen van koppen (1352898-023).

Elke inklapbare kop (rondelijst per categorie, club, speler en agenda; Statistiek; het
clubscherm) wisselt bij een tik open/dicht en tekent het scherm opnieuw; nog een tik zet
alles terug. Tot 022 stond die logica als code in het onclick-attribuut van elke kop en
zocht 'alles openklappen' de sleutels met een zoekpatroon in die code. Nu dragen de koppen
attributen (data-inklap, data-sleutel, data-dicht, data-teken) en doet wisselIngeklapt het.

Deze test werkt op beide vormen: hij moet op 022 en op 023 hetzelfde geven. Per kop:
  1. één tik verandert het scherm (de kop klapt om);
  2. een tweede tik op dezelfde kop zet het scherm precies terug.
En lang indrukken (alles dicht, nog eens: alles open) per groepering in de rondelijst.
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, RONDES, ronde
import datetime
_d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
DATA = RONDES + [ronde(900 + i, _d(n), played=0, putts=False) for i, n in enumerate((2, 9, 40))]

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

KOPPEN = "(s) => [...document.querySelectorAll(s + ' [data-inklap], ' + s + ' [onclick*=\"Collapsed\"]')]"
STANDEN = [
    ('rondes per categorie', '#screen-archive', "nav('archive'); toggleGroupByCategory();"),
    ('rondes per club', '#screen-archive', "nav('archive'); toggleGroupByTrack();"),
    ('rondes per speler', '#screen-archive', "nav('archive'); toggleGroupByPlayer();"),
    ('agenda', '#screen-archive', "nav('archive'); toggleGroupByPlanned();"),
    ('statistiek', '#screen-stat', "nav('stat'); renderPlayerStats();"),
    ('clubscherm per categorie', '#screen-club', "nav('club'); if (!_clubGrouped) toggleClubGroupByCategory(); buildClubList();"),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, scherm, zet in STANDEN:
            ctx = await b.new_context(viewport={"width": 390, "height": 844})
            pg = await ctx.new_page()
            pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
            await pg.goto(app_url())
            await pg.evaluate(SEED, [CLUBS, DATA])
            await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
            await pg.reload(); await pg.wait_for_timeout(700)
            await pg.evaluate("(z) => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); (new Function(z))(); }", zet)
            await pg.wait_for_timeout(300)
            n = await pg.evaluate(f"(s) => ({KOPPEN})(s).length", scherm)
            print(f"\n=== {naam}: {n} koppen ===")
            check(f"{naam}: er zijn inklapbare koppen", n > 0, True)
            goed = 0
            for i in range(min(n, 10)):
                uit = await pg.evaluate("""([s, i, K]) => {
                  const koppen = () => (new Function('return ' + K))()(s);
                  const beeld = () => document.querySelector(s).innerHTML.replace(/ data-(inklap|sleutel|dicht|teken)="[^"]*"/g, '').replace(/ onclick="[^"]*"/g, '');
                  const a = beeld(); const k1 = koppen()[i]; if (!k1) return 'weg';
                  k1.click(); const b1 = beeld();
                  const k2 = koppen()[i]; if (!k2) return 'kop weg na tik';
                  k2.click(); const c = beeld();
                  return (b1 !== a ? 'om' : 'niet om') + '/' + (c === a ? 'terug' : 'niet terug');
                }""", [scherm, i, KOPPEN])
                if uit == 'om/terug': goed += 1
                else: print(f"        kop {i}: {uit}")
            check(f"{naam}: elke kop klapt om en weer terug", goed, min(n, 10))
            check(f"{naam}: geen fouten in de pagina", pf, [])
            await ctx.close()

        print("\n=== LANG INDRUKKEN: ALLES DICHT, NOG EENS: ALLES OPEN ===")
        for naam, lang in [('categorie', 'alleCategorieenDichtOfOpen'), ('speler', 'alleSpelersDichtOfOpen'), ('club', 'alleClubsDichtOfOpen')]:
            ctx = await b.new_context(viewport={"width": 390, "height": 844})
            pg = await ctx.new_page()
            await pg.goto(app_url())
            await pg.evaluate(SEED, [CLUBS, DATA])
            await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
            await pg.reload(); await pg.wait_for_timeout(700)
            await pg.evaluate(f"() => {{ nav('archive'); {lang}(); }}"); await pg.wait_for_timeout(200)
            dicht1 = await pg.evaluate("() => document.getElementById('savedList').innerHTML.length")
            await pg.evaluate(f"() => {lang}()"); await pg.wait_for_timeout(300)
            open2 = await pg.evaluate("() => document.getElementById('savedList').innerHTML.length")
            check(f"{naam}: alles dicht is korter dan alles open", dicht1 < open2, True)
            await ctx.close()
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
