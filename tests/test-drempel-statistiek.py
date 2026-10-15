"""Het minimum aantal rondes voor statistieken geldt voor alle gemiddelden op Statistiek.

Instellingen → Algemeen → 'Minimum aantal rondes voor statistieken' (standaard 3): een getal
dat op minder rondes rust, wordt verborgen of toont een streepje. Tot 13527DA-145 hield niet
elk onderdeel zich daaraan (Marks melding: per par 2× en bij de clubs zelfs 1×):
  - per tee en bij de clubs (gem. dagresultaat) stond een gemiddelde bij 1 of 2 rondes;
  - per par en per SI telde de drempel holes in plaats van rondes;
  - de bovenste rij (Gem. Sd, Gem. Stb, Gem. putts) had geen drempel;
  - het verloop per drie holes (9 holes) en per negen (18 holes) telde holes;
  - de trend vergeleek de laatste 5 al met één losse ronde ervoor;
  - de spreiding had een vaste grens van 3 en negeerde een hogere instelling.
De baananalyse op het clubtabblad heeft bewust geen minimum (Marks keuze) en valt hier buiten.

Steeds ook met een lagere instelling, zodat vaststaat dat het de drempel is die het getal
verbergt en niet iets anders.
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

def reeks(n):
    return [ronde(i + 1, f'2026-09-{i + 1:02d}') for i in range(n)]

ZET = """([c, r, m]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark');
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString());
  localStorage.setItem('golf_min_rounds_stat', String(m));
  ['handicap', 'prestaties', 'banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open')); }"""
SCHERM = """() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'));
  window._statChartPeriod = 'alles'; window._statClubCollapsed = new Proxy({}, { get: () => false, set: () => true });
  nav('stat'); renderPlayerStats();
  const kaarten = [...document.querySelectorAll('#playerStats .card')].map(c => c.innerText.replace(/\\s+/g, ' ').trim());
  const kpi = {}; document.querySelectorAll('#playerStats .kpi-grid > *').forEach(k => { const t = k.innerText.trim().split(/\\n+/); kpi[t[t.length - 1].trim().toUpperCase()] = t[0].trim(); });
  return { kaarten, kpi }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        async def scherm(rondes, minimum):
            await pg.evaluate(ZET, [CLUBS, rondes, minimum]); await pg.reload(); await pg.wait_for_timeout(600)
            return await pg.evaluate(SCHERM)
        kaart = lambda s, kop: next((k for k in s['kaarten'] if k.upper().startswith(kop.upper())), None)
        heeft = lambda s, tekst: any(tekst in k for k in s['kaarten'])

        print("\n=== 1. TWEE RONDES, MINIMUM 3: OVERAL EEN STREEPJE OF NIETS ===\n")
        s = await scherm(reeks(2), 3)
        check("bovenste rij: Gem. Sd, Gem. Stb, Gem. putts", [s['kpi'].get('GEM. SD'), s['kpi'].get('GEM. STB'), s['kpi'].get('GEM. PUTTS')], ['—', '—', '—'])
        check("aantal rondes staat er wel", s['kpi'].get('RONDES'), '2')
        check("per tee: streepje, aantal blijft", 'Blauw — 2×' in (kaart(s, 'Gemiddelde per tee') or ''), True)
        check("per par: geen kaart (2 rondes, ook al zijn het 4 par-3-holes)", kaart(s, 'Gemiddelde per par'), None)
        check("per SI: geen kaart", kaart(s, 'Gemiddelde per SI'), None)
        check("verloop per drie holes: weg", heeft(s, 'VERLOOP'), False)
        clubs = next((k for k in s['kaarten'] if 'Airborne' in k), '')
        check("clubs: Airborne zonder gemiddelde, wel 2×", 'Airborne — ' in clubs and '2×' in clubs, True)

        print("\n=== 2. ZELFDE TWEE RONDES, MINIMUM 2: ALLES TERUG ===\n")
        s = await scherm(reeks(2), 2)
        check("bovenste rij heeft getallen", all(s['kpi'].get(k, '—') != '—' for k in ('GEM. SD', 'GEM. STB', 'GEM. PUTTS')), True)
        check("per tee: gemiddelde", 'Blauw — 2×' in (kaart(s, 'Gemiddelde per tee') or 'x'), False)
        check("per par en per SI: kaarten terug", [kaart(s, 'Gemiddelde per par') is not None, kaart(s, 'Gemiddelde per SI') is not None], [True, True])
        check("verloop per drie holes: terug", heeft(s, 'VERLOOP · 9 HOLES'), True)

        print("\n=== 3. TREND: BEIDE BLOKKEN MINSTENS HET MINIMUM (MAX. 5) ===\n")
        check("7 rondes, minimum 3: geen trend (de 5 ervoor zijn er maar 2)", heeft(await scherm(reeks(7), 3), 'Trend (laatste 5)'), False)
        check("8 rondes, minimum 3: trend", heeft(await scherm(reeks(8), 3), 'Trend (laatste 5)'), True)
        check("9 rondes, minimum 10: geen trend (blok van 5 is het maximum: 10 nodig)", heeft(await scherm(reeks(9), 10), 'Trend (laatste 5)'), False)
        check("10 rondes, minimum 10: trend", heeft(await scherm(reeks(10), 10), 'Trend (laatste 5)'), True)

        print("\n=== 4. SPREIDING: MINSTENS 3, EN MINSTENS HET MINIMUM ===\n")
        check("4 rondes, minimum 5: geen spreiding", heeft(await scherm(reeks(4), 5), 'Consistentie (spreiding)'), False)
        check("5 rondes, minimum 5: spreiding", heeft(await scherm(reeks(5), 5), 'Consistentie (spreiding)'), True)
        check("2 rondes, minimum 1: geen spreiding (over 2 punten zegt het niets)", heeft(await scherm(reeks(2), 1), 'Consistentie (spreiding)'), False)
        check("3 rondes, minimum 1: spreiding", heeft(await scherm(reeks(3), 1), 'Consistentie (spreiding)'), True)

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
