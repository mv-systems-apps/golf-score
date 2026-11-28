"""Statistiek, groep Clubs: een club zonder één baan met genoeg rondes staat er niet (037).

De drempel is 'Minimum aantal rondes voor statistieken' uit Instellingen (standaard 3).
Een club waar bij elke baan een streepje zou staan, zegt niets en verdwijnt. Een club met
minstens één baan boven de drempel blijft helemaal staan, ook met de banen eronder die
een streepje hebben. De aantallen (groep Clubs, Thuisclub/Favorieten/Overig) tellen alleen
de getoonde clubs; een lege categorie en een lege groep verdwijnen.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

# De Hoeve: Akkerweg 3×, Spoor 1×. Heidezicht (favoriet): Noord 2×.
RONDES = ([ronde(i, f'2026-09-{i:02d}') for i in (1, 2, 3)]
          + [ronde(4, '2026-09-04', baan='Spoor')]
          + [ronde(i, f'2026-09-{i:02d}', baan='Noord', club='Heidezicht', kort='Heidezicht') for i in (5, 6)])
# Een Heidezicht-ronde zonder dagresultaat: die geeft een waarschuwingsdriehoekje
RONDES[-1] = dict(RONDES[-1], sd=None, sdFinal=None)

ZET = """([c, r, m]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub De Hoeve'); localStorage.setItem('golf_home_club', 'Golfclub De Hoeve');
  localStorage.setItem('golf_fav_clubs', JSON.stringify(['Heidezicht'])); localStorage.setItem('golf_profile_name', 'Testspeler');
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString());
  localStorage.setItem('golf_min_rounds_stat', String(m));
  ['handicap', 'prestaties', 'banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open')); }"""
SCHERM = """() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'));
  _statChartPeriod = 'alles'; window._statClubCollapsed = new Proxy({}, { get: () => false, set: () => true });
  nav('stat'); renderPlayerStats();
  const t = document.getElementById('playerStats').innerText.replace(/[ \\t]+/g, ' ');
  const groep = (t.match(/\\nCLUBS\\s*(\\d+)/i) || [])[1] || null;
  const kop = [...document.querySelectorAll('#playerStats [onclick]')].find(e => e.getAttribute('onclick').includes('toggleStatsGroup') && e.getAttribute('onclick').includes('banen'));
  const driehoek = kop ? !!kop.querySelector('svg[stroke="var(--orange)"]') : null;
  const spoor = (t.split('Spoor')[1] || '').slice(0, 40);
  return { tekst: t, groep, driehoek, spoor: spoor.includes('—') && spoor.includes('1×') }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        async def scherm(rondes, minimum):
            await pg.evaluate(ZET, [CLUBS, rondes, minimum]); await pg.reload(); await pg.wait_for_timeout(600)
            return await pg.evaluate(SCHERM)

        print("\n=== 1. MINIMUM 3: HEIDEZICHT (2×) WEG, DE HOEVE HELEMAAL ===\n")
        s = await scherm(RONDES, 3)
        check("Heidezicht staat er niet", 'Heidezicht' in s['tekst'], False)
        check("de categorie Favorieten valt weg (leeg)", 'FAVORIETEN' in s['tekst'].upper(), False)
        check("De Hoeve staat er, met Akkerweg én Spoor (dat een streepje heeft)", ['Golfclub De Hoeve' in s['tekst'], 'Akkerweg' in s['tekst'], 'Spoor' in s['tekst']], [True, True, True])
        check("de groep Clubs telt 1", s['groep'], '1')
        check("Spoor met een streepje en 1×", s['spoor'], True)
        check("geen driehoekje bij Clubs: de ronde zonder dagresultaat hoort bij het verborgen Heidezicht", s['driehoek'], False)

        print("\n=== 2. MINIMUM 2: HEIDEZICHT TERUG ===\n")
        s = await scherm(RONDES, 2)
        check("Heidezicht en Favorieten staan er", ['Heidezicht' in s['tekst'], 'FAVORIETEN' in s['tekst'].upper()], [True, True])
        check("de groep Clubs telt 2", s['groep'], '2')
        check("nu Heidezicht er staat, wel het driehoekje bij Clubs", s['driehoek'], True)

        print("\n=== 3. MINIMUM 1: ALLES ===\n")
        s = await scherm(RONDES, 1)
        check("beide clubs", ['Heidezicht' in s['tekst'], 'Golfclub De Hoeve' in s['tekst']], [True, True])

        print("\n=== 4. GEEN ENKELE CLUB BOVEN DE DREMPEL: GEEN GROEP CLUBS ===\n")
        s = await scherm(RONDES[3:], 3)
        check("geen groep Clubs, geen lege kop", s['groep'], None)
        check("en geen clubnamen", ['Heidezicht' in s['tekst'], 'Golfclub De Hoeve' in s['tekst']], [False, False])

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)"); sys.exit(1)
    print("Alles in orde.")

asyncio.run(main())
