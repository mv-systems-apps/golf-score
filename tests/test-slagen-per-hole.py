"""De slagen per hole tellen altijd op tot de baanhandicap.

Vaste regel (Mark, 4-10-2026). Drie lagen:

  1. REKENKUNDIG — de verdeling voor elke baanhandicap van -10 t/m 60, met de SI-reeks
     van elke tee van elke baan uit Marks eigen clubbestand en uit de testclubs, en met
     een paar lastige reeksen (dubbele SI, ontbrekende SI). Gecontroleerd: de som is de
     baanhandicap; geen hole krijgt meer dan één slag meer dan een andere; en de extra
     slagen gaan naar de moeilijkste holes (bij een negatieve baanhandicap gaan de
     slagen eraf bij de makkelijkste).
  2. IN DE APP — op elke baan en elke tee een ronde starten met twee spelers, met de
     berekende baanhandicap en met een aangepaste (-10, -3, 0, 7, 54 en een
     wedstrijdpercentage), bij uiteenlopende handicaps. Bij beide spelers: de som van
     de slagen per hole is de baanhandicap van die ronde, in het geheugen en in de
     opslag, en de persoonlijke par is par plus slagen.
  3. BESTAANDE RONDES — Marks eigen rondes (echte-rondes.json, zijn backup van
     4-10-2026): bij elke ronde dezelfde som. De test verandert geen ronde.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-slagen-per-hole.py
draait op een app waarin de verdeling de restslagen laat vallen. Dan moet hij falen.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
KAPOT = os.environ.get('KAPOT') == '1'
ECHTE_CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
ECHTE_RONDES = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))   # Marks backup van 4-10-2026

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

KAPOT_JS = """() => { const f = window.distributeChcp;
  window.distributeChcp = function (chcp, n, holes) { const b = Math.trunc(chcp / n) || 0; return new Array(n).fill(b); }; }"""

# ── laag 1 ────────────────────────────────────────────────────────────────────────
RASTER = """(reeksen) => {
  const fout = []; let n = 0;
  const zeg = t => { if (fout.length < 8) fout.push(t); };
  for (const [naam, holes] of reeksen) {
    const aantal = holes.length;
    const uniek = new Set(holes.map(h => h.si)).size === aantal && holes.every(h => Number.isFinite(h.si));
    for (let chcp = -10; chcp <= 60; chcp++) {
      n++;
      const p = distributeChcp(chcp, aantal, holes);
      const som = p.reduce((s, x) => s + x, 0);
      if (p.length !== aantal) { zeg(`${naam}, chcp ${chcp}: ${p.length} waarden voor ${aantal} holes`); continue; }
      if (som !== chcp) zeg(`${naam}, chcp ${chcp}: som ${som}`);
      const min = Math.min(...p), max = Math.max(...p);
      if (max - min > 1) zeg(`${naam}, chcp ${chcp}: verschil tussen holes is ${max - min}`);
      if (uniek && max !== min) {
        // de holes met de meeste slagen zijn de moeilijkste (laagste SI)
        const meer = holes.filter((h, i) => p[i] === max).map(h => h.si), minder = holes.filter((h, i) => p[i] === min).map(h => h.si);
        if (Math.max(...meer) > Math.min(...minder)) zeg(`${naam}, chcp ${chcp}: slagen niet naar de moeilijkste holes (SI ${meer} tegen ${minder})`);
      }
    }
  }
  return { n, fout };
}"""

def si_reeksen():
    uit = []
    for bron, clubs in (('eigen', ECHTE_CLUBS), ('test', testdata.CLUBS)):
        for club, c in clubs.items():
            for baan, b in c['courses'].items():
                for g, tees in b['tees'].items():
                    for t, te in tees.items():
                        uit.append((f"{club} · {baan} · {g} {t}", [{'si': h.get('si')} for h in te.get('holes', [])]))
    uit.append(('dubbele SI (9)', [{'si': x} for x in [1, 1, 3, 3, 5, 5, 7, 7, 9]]))
    uit.append(('alle SI gelijk (18)', [{'si': 1} for _ in range(18)]))
    uit.append(('SI ontbreekt (9)', [{} for _ in range(9)]))
    uit.append(('SI 1-18 op 9 holes (oneven)', [{'si': x} for x in range(1, 18, 2)]))
    return uit

# ── laag 2 ────────────────────────────────────────────────────────────────────────
STARTEN = """([club, baan, g, t, hcp1, hcp2, over1, over2, pct, tijd]) => {
  metVerwijderen(() => setRoundsAndMark('[]')); clearActiveRound();
  nav('setup'); setDefaultClub(club); sel.holeCount = null; sel._holeCountUserCleared = true; sel.showPar3 = trackCategories(baan).has('par3');
  sel.track = baan; sel.gender = g; sel.tee = t; sel._teeUserSelected = true; sel.chcpOverride = null; sel.chcpPct = null; rebuildStartScreen();
  document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = String(hcp1);
  document.getElementById('iTime').value = tijd; sel.time = tijd; sel.date = document.getElementById('iDate').value; sel.dateTimeEdited = true;
  togglePlayer2(true);
  document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = String(hcp2);
  sel2.track = baan; sel2.gender = g; sel2.tee = t; sel2.chcpOverride = null; sel2.chcpPct = null;
  if (pct != null) {                                  // zoals openChcpPercentage het zet
    const a1 = calcChcpAuto(), a2 = calcChcpAuto2(hcp2);
    sel.chcpPct = pct; sel.chcpOverride = Math.max(-10, Math.min(54, Math.round(a1 * pct / 100)));
    sel2.chcpPct = pct; sel2.chcpOverride = Math.max(-10, Math.min(54, Math.round(a2 * pct / 100)));
  } else { sel.chcpOverride = over1; sel2.chcpOverride = over2; }
  const fout0 = document.getElementById('startError') ? document.getElementById('startError').innerText : '';
  startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
  if (!game.started) return { gestart: false, melding: (document.querySelector('#screen-setup .start-error, #startError') || {}).innerText || fout0 };
  const kort = r => r ? { chcp: r.chcp, n: (r.holes || []).length, phcp: (r.holes || []).map(h => h.phcp),
                          ppar: (r.holes || []).every(h => h.ppar === h.par + h.phcp) } : null;
  const opslag = loadSavedRounds();
  const uit = { gestart: true, spel: kort(game), opslag1: kort(opslag.find(r => String(r.id) === localStorage.getItem('golf_active_id'))),
                opslag2: kort(opslag.find(r => r.id === game2Id)), verwacht1: pct != null ? sel.chcpOverride : over1, verwacht2: pct != null ? sel2.chcpOverride : over2 };
  togglePlayer2(false);
  return uit;
}"""

VARIANTEN = [   # hcp1, hcp2, aangepast1, aangepast2, percentage
    (30.8, 18.0, None, None, None),
    (4.2, 54.0, None, None, None),
    (-2.5, 0.0, None, None, None),
    (30.8, 18.0, -10, 54, None),
    (30.8, 18.0, 54, -10, None),
    (30.8, 18.0, -3, 7, None),
    (30.8, 18.0, 0, 37, None),
    (30.8, 18.0, None, None, 75),
    (41.5, 9.9, None, None, 85),
]

def som_ok(r):
    return (r is not None and all(isinstance(x, int) for x in r['phcp']) and len(r['phcp']) == r['n']
            and sum(r['phcp']) == r['chcp'])

async def laag2(b, bron, clubs):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url())
    await pg.evaluate("""([clubs]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', '[]'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_profile_hcp', '30.8');
        localStorage.setItem('golf_kenmerk_gevraagd', '1'); const c = Object.keys(clubs)[0];
        localStorage.setItem('golf_home_club', c); localStorage.setItem('golf_default_club', c); }""", [clubs])
    await pg.reload(); await pg.wait_for_timeout(400)
    if KAPOT: await pg.evaluate(KAPOT_JS)
    tees = starts = 0; niet = []
    for club, c in clubs.items():
        for baan, bd in c['courses'].items():
            for g, tt in bd['tees'].items():
                for t in tt:
                    tees += 1
                    for nr, (h1, h2, o1, o2, pct) in enumerate(VARIANTEN):
                        waar = f"{bron} · {club} · {baan} · {g} {t} · variant {nr + 1}"
                        try:
                            r = await pg.evaluate(STARTEN, [club, baan, g, t, h1, h2, o1, o2, pct, f"{6 + nr:02d}:1{nr}"])
                        except Exception as e:
                            check(f"{waar}: de ronde is gestart", False, str(e)[:160]); continue
                        if not r['gestart']:
                            niet.append(waar + (': ' + r['melding'] if r.get('melding') else '')); continue
                        starts += 1
                        for wie, k in (('speler 1 (geheugen)', 'spel'), ('speler 1 (opslag)', 'opslag1'), ('speler 2 (opslag)', 'opslag2')):
                            x = r[k]
                            check(f"{waar}: {wie} som slagen = baanhandicap", som_ok(x),
                                  'ronde ontbreekt' if x is None else f"chcp {x['chcp']}, slagen {x['phcp']} (som {sum(v for v in x['phcp'] if isinstance(v, int))})")
                            if x: check(f"{waar}: {wie} persoonlijke par = par + slagen", x['ppar'])
                        if r['verwacht1'] is not None and r['spel']:
                            check(f"{waar}: de aangepaste baanhandicap van speler 1 is gebruikt", r['spel']['chcp'] == r['verwacht1'], f"{r['spel']['chcp']} tegen {r['verwacht1']}")
                        if r['verwacht2'] is not None and r['opslag2']:
                            check(f"{waar}: de aangepaste baanhandicap van speler 2 is gebruikt", r['opslag2']['chcp'] == r['verwacht2'], f"{r['opslag2']['chcp']} tegen {r['verwacht2']}")
    check(f"{bron}: geen fouten in de pagina", not pf, str(pf[:3]))
    await pg.close()
    return bron, tees, starts, niet

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")

        print("=== 1. REKENKUNDIG ===")
        pg = await b.new_page()
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, testdata.RONDES]); await pg.reload(); await pg.wait_for_timeout(300)
        if KAPOT: await pg.evaluate(KAPOT_JS)
        reeksen = si_reeksen()
        r = await pg.evaluate(RASTER, reeksen)
        print(f"  {len(reeksen)} SI-reeksen × 71 baanhandicaps = {r['n']} verdelingen")
        check("elke verdeling telt op tot de baanhandicap, eerlijk verdeeld", not r['fout'], ' | '.join(r['fout']))

        print("\n=== 3. MARKS EIGEN RONDES ===")
        afw = []
        for x in ECHTE_RONDES:
            ph = [h.get('phcp') for h in x.get('holes', [])]
            if not ph: continue
            if any(not isinstance(v, int) for v in ph) or sum(ph) != x.get('chcp'):
                afw.append(f"{x.get('date')} {x.get('time')} {x.get('player')} · {x.get('track')}: chcp {x.get('chcp')}, som {sum(v for v in ph if isinstance(v, int))}")
        print(f"  {len(ECHTE_RONDES)} rondes nagekeken, {len(afw)} afwijkend")
        check("het testbestand bevat Marks rondes", len(ECHTE_RONDES) >= 40, str(len(ECHTE_RONDES)))
        check("bij elke bestaande ronde is de som van de slagen de baanhandicap", not afw, ' | '.join(afw[:5]))
        await pg.close()

        print("\n=== 2. IN DE APP: OP ELKE BAAN EN TEE STARTEN ===")
        uit = await asyncio.gather(laag2(b, 'eigen clubs', ECHTE_CLUBS), laag2(b, 'testclubs', testdata.CLUBS))
        for bron, tees, starts, niet in uit:
            print(f"  {bron}: {tees} tees, {starts} rondes gestart" + (f", {len(niet)} niet gestart" if niet else ''))
            for n in niet[:6]: print("     niet gestart: " + n[:200])
            check(f"{bron}: op elke tee is elke variant gestart", not niet, f"{len(niet)} niet gestart")
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
