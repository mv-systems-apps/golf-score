#!/usr/bin/env python3
"""
13528A6-001: Gem. Stb en Gem. putts in de bovenste rij van Statistiek zijn per 18 holes.

Voorheen het gemiddelde per ronde: bij een mix van 9- en 18-holesrondes trok elke 18-holesronde
het gemiddelde omhoog (twee keer zoveel punten en putts), terwijl je niet beter of slechter
speelde. Nu telt een 9-holesronde dubbel: 36 is op handicap, zoals bij het dagresultaat.

Met de eigen rondes (34 van 9 holes, 2 van 18) wordt gecontroleerd:
  1. de labels blijven 'Gem. Stb' en 'Gem. putts' (per 18 holes staat in de handleiding);
  2. Gem. Stb is het gemiddelde van (Stableford × 18 / gespeelde holes), met de volle
     baanhandicap, en niet het gewone gemiddelde per ronde;
  3. Gem. putts idem met de putts (alleen rondes met putts op elke gespeelde hole);
  4. met alleen 9-holesrondes is Gem. Stb precies twee keer het gemiddelde per ronde.
Faalt op 13528A5-002.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
STAND = next(iter(json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8')).values()))
RONDES = json.loads(STAND['opslag']['golf_rounds'])

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {echt} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

KPI = """() => { const kpi = {}; document.querySelectorAll('#playerStats .kpi-grid > *').forEach(k => {
  const t = k.innerText.trim().split(/\\n+/); kpi[t[t.length - 1].trim()] = t[0].trim(); }); return kpi; }"""
REKEN = """() => {
  const rs = leesRondes().filter(meetelFilter(startPlayerName()));
  const gesp = r => (r.holes || []).filter(h => h && h.score != null);
  const stb = rs.map(r => ({ v: stbVoorStatistiek(r), n: gesp(r).length })).filter(x => x.n && isFinite(x.v));
  const pt = rs.map(r => { const g = gesp(r); return g.length && g.every(h => h.putts != null) ? { v: g.reduce((s, h) => s + h.putts, 0), n: g.length } : null; }).filter(Boolean);
  const gem = (a, f) => (a.reduce((s, x) => s + f(x), 0) / a.length).toFixed(1);
  const holes = {}; rs.forEach(r => { const n = gesp(r).length; holes[n] = (holes[n] || 0) + 1; });
  return { holes, stb18: gem(stb, x => x.v * 18 / x.n), stbRonde: gem(stb, x => x.v), stbRondeDubbel: (2 * stb.reduce((s, x) => s + x.v, 0) / stb.length).toFixed(1), putts18: gem(pt, x => x.v * 18 / x.n), puttsRonde: gem(pt, x => x.v) };
}"""

async def scherm(pg, rondes):
    await pg.goto(app_url())
    await pg.evaluate("""([clubs, rondes]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes)); localStorage.setItem('golf_profile_name', 'Testspeler');
        localStorage.setItem('golf_profile_hcp', '30.8'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
        localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_track_putts', 'on'); localStorage.setItem('golf_putts_stats', 'on'); }""", [CLUBS, rondes])
    await pg.reload(); await pg.wait_for_timeout(700)
    await pg.evaluate("() => { nav('stat'); renderPlayerStats(); }"); await pg.wait_for_timeout(300)
    return await pg.evaluate(KPI), await pg.evaluate(REKEN)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 360, 'height': 740})
        print("\n=== 1. EIGEN RONDES: MIX VAN 9 EN 18 HOLES ===\n")
        kpi, r = await scherm(pg, RONDES)
        check("er zitten 9- én 18-holesrondes in", sorted(r['holes'].keys()), ['18', '9'])
        check("labels zonder /18 (het staat in de handleiding)", ['GEM. STB' in kpi, 'GEM. PUTTS' in kpi], [True, True])
        check("Gem. Stb = gemiddelde van Stableford × 18 / gespeelde holes", kpi.get('GEM. STB'), r['stb18'])
        check("en niet het gemiddelde per ronde", kpi.get('GEM. STB') != r['stbRonde'], True)
        check("Gem. putts = gemiddelde van putts × 18 / gespeelde holes", kpi.get('GEM. PUTTS'), r['putts18'])
        check("en niet het gemiddelde per ronde", kpi.get('GEM. PUTTS') != r['puttsRonde'], True)
        print("\n=== 2. ALLEEN 9-HOLESRONDES: PRECIES TWEE KEER HET GEMIDDELDE PER RONDE ===\n")
        negen = [x for x in RONDES if len([h for h in x.get('holes', []) if h and h.get('score') is not None]) != 18]
        kpi2, r2 = await scherm(pg, negen)
        check("alleen 9 holes", list(r2['holes'].keys()), ['9'])
        check("Gem. Stb = 2 × gemiddelde per ronde", kpi2.get('GEM. STB'), r2['stbRondeDubbel'])
        await b.close()
    print(f"\n{'GEEN FOUTEN' if not fouten else f'{len(fouten)} FOUT(EN)'}")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
