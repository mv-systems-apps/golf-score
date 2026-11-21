"""De handicap komt nooit boven 54,0 en nooit meer dan 5,0 boven de Low HI.

Vaste regel (gebruiker, 4-10-2026). Welke Low HI: de handmatig ingevulde als die er is,
anders de afgeleide; in het handicapverloop en op de rondekaarten per ronde de Low HI
van dat moment.

Drie lagen:

  1. REKENKUNDIG — de begrenzing over een raster van ruwe waarden (-10 t/m 80) en Low
     HI's (geen, en -5 t/m 54), en whsHandicap over honderden verzonnen reeksen rondes.
  2. ELKE BEREKENING ONDERWEG — terwijl de test alle schermen langsloopt, wordt elke
     uitkomst van de begrenzing en van whsHandicap meegeschreven, met de Low HI die
     erbij gebruikt is. Geen enkele mag de grens over. Zo telt ook mee wat in een
     grafiek staat en niet als tekst af te lezen is.
  3. OP HET SCHERM — de getoonde getallen zelf: WHS-hcp op Start, het kerngetal op
     Statistiek (drie periodes), 'Wat als?', de rondekaarten, en de WHS-hcp op Start
     met een open ronde en na het afronden van een rampzalige ronde.

Reeksen: goede rondes gevolgd door rampzalige (harde cap), alleen rampzalige (54,0),
een handmatige lage Low HI, het soft-capgebied, maar drie rondes, en de eigen
gegevens met een heel lage handmatige Low HI.

Buiten de regel: het Hcp-veld op Start dat je zelf invult (jouw invoer, tot 54,0) en de
lijn 'Zonder cap' in de grafiek (die toont juist de waarde zonder begrenzing).

Bewijs dat de test kan falen:  KAPOT=1 python3 test-handicap-grenzen.py
draait op een app waarin de begrenzing is uitgeschakeld. Dan moet hij falen.
"""
import asyncio, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
KAPOT = os.environ.get('KAPOT') == '1'
ECHTE_CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
_STAND = next(iter(json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8')).values()))
ECHTE_RONDES = json.loads(_STAND['opslag']['golf_rounds'])
ECHTE_SPELER = 'Testspeler'

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

# ── reeksen ───────────────────────────────────────────────────────────────────────
def reeks(sds, stap=15):
    """Rondes met deze dagresultaten, de laatste van eergisteren, om de `stap` dagen."""
    v = datetime.date.today() - datetime.timedelta(days=2)
    uit = []
    for i, sd in enumerate(sds):
        r = testdata.ronde(1000 + i, (v - datetime.timedelta(days=(len(sds) - 1 - i) * stap)).isoformat())
        r['sd'] = sd; r['sdFinal'] = sd
        uit.append(r)
    return uit

# naam, eigen gegevens?, rondes, handmatige Low HI, verwachte WHS-hcp op Start (None = niet vastgelegd)
REEKSEN = [
    ('goed, daarna rampzalig (harde cap)', False, reeks([20.0] * 6 + [45.0 + i * 1.5 for i in range(6, 26)]), None, '23.0'),
    ('alleen rampzalig (54,0)',            False, reeks([70.0 + (i % 7) for i in range(24)]), None, '54.0'),
    ('handmatige Low HI 12,0',             False, reeks([60.0 + (i % 5) for i in range(22)]), '12.0', '17.0'),
    ('handmatige Low HI 52,0 (54 wint)',   False, reeks([75.0 + (i % 5) for i in range(22)]), '52.0', '54.0'),
    ('soft-capgebied',                     False, reeks([20.0] * 8 + [24.0] * 20), None, '23.0'),   # Low HI 19,0; ruw 24,0 → 19 + 3 + 1
    ('maar drie rondes',                   False, reeks([70.0, 72.0, 71.0]), None, '54.0'),
    ('eigen gegevens, zoals ze zijn',      True,  ECHTE_RONDES, None, None),
    ('eigen gegevens, Low HI 5,0',         True,  ECHTE_RONDES, '5.0', None),
]

# ── meeschrijven: elke uitkomst van de begrenzing en van whsHandicap ──────────────
MEESCHRIJVEN = """(kapot) => {
  window._log = [];
  const cap = window.applyHandicapCaps;
  window.applyHandicapCaps = function (raw, low) {
    const r = kapot ? { value: raw, type: null } : cap(raw, low);
    window._log.push(['cap', raw, low == null || !isFinite(low) ? null : low, r.value, r.type]);
    return r;
  };
  const whs = window.whsHandicap;
  window.whsHandicap = function (rounds, low = null, esr = null) {
    const r = whs(rounds, low, esr);
    if (r) window._log.push(['whs', r.rawValue, low == null || !isFinite(low) ? null : low, r.value, r.capType]);
    return r;
  };
}"""

def over_de_grens(v, low):
    if v is None: return None
    if v > 54.0 + 1e-9: return f"{v} > 54,0"
    if low is not None and v > low + 5.0 + 1e-9: return f"{v} > Low HI {low} + 5,0"
    return None

# ── laag 1: rekenkundig ───────────────────────────────────────────────────────────
RASTER = """() => {
  const fout = []; let n = 0, hard = 0, soft = 0, op54 = 0;
  const lows = [null]; for (let l = -5; l <= 54.001; l += 0.5) lows.push(Math.round(l * 10) / 10);
  for (const low of lows) for (let k = -100; k <= 800; k++) {
    const raw = k / 10, r = applyHandicapCaps(raw, low), v = r.value; n++;
    if (r.type === 'hard') hard++; if (r.type === 'soft') soft++; if (v === 54) op54++;
    const zeg = t => { if (fout.length < 8) fout.push(`ruw ${raw}, Low HI ${low} → ${v}: ${t}`); };
    if (!(v <= 54 + 1e-9)) zeg('boven 54,0');
    if (low != null && !(v <= low + 5 + 1e-9)) zeg('meer dan 5,0 boven de Low HI');
    if (!(v <= raw + 1e-9)) zeg('de begrenzing verhoogt');
    if (raw <= 54 && (low == null || raw <= low + 3) && Math.abs(v - raw) > 1e-9) zeg('verlaagd zonder reden');
    if (Math.abs(v * 10 - Math.round(v * 10)) > 1e-6) zeg('niet op één decimaal');
  }
  return { n, hard, soft, op54, fout };
}"""

REEKSEN_WILLEKEURIG = """() => {
  let s = 12345; const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  const fout = []; let n = 0, begrensd = 0;
  for (let t = 0; t < 400; t++) {
    const aantal = 1 + Math.floor(rnd() * 24);
    const basis = rnd() * 90, spreiding = rnd() * 40;
    const rondes = Array.from({ length: aantal }, (_, i) => ({ id: i + 1, player: 'X', qualifying: true,
      date: '2026-0' + (1 + (i % 9)) + '-1' + (i % 9), time: '09:00',
      sdFinal: Math.round((basis + (rnd() - 0.5) * spreiding) * 10) / 10, holesCount: 9, holes: [] }));
    const low = rnd() < 0.3 ? null : Math.round((rnd() * 60 - 5) * 10) / 10;
    const w = whsHandicap(rondes, low, null); if (!w) continue; n++;
    if (w.capped) begrensd++;
    const v = w.value;
    if (!(v <= 54 + 1e-9) || (low != null && !(v <= low + 5 + 1e-9))) {
      if (fout.length < 8) fout.push(`${aantal} rondes rond ${basis.toFixed(1)}, Low HI ${low} → ${v}`);
    }
  }
  return { n, begrensd, fout };
}"""

# ── laag 3: de getoonde getallen ──────────────────────────────────────────────────
GETAL = r'(-?\d+\.\d)'
def getallen_whs(tekst):
    """Uit 'Whs 30.7 → 23.0': het BEREKENDE getal (het tweede; het eerste is de hcp van toen)."""
    uit = []
    for m in re.finditer(r'Whs\s*' + GETAL + r'\s*' + GETAL + r'?', tekst):
        if m.group(2): uit.append(float(m.group(2)))
    return uit

async def klik_tab(pg, s):
    await pg.locator('#tab-' + s).click(); await pg.wait_for_timeout(200)

async def doorloop(b, naam, echt, rondes, lowhi, verwacht):
    speler = ECHTE_SPELER if echt else 'Testspeler'
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    try:
        await pg.goto(app_url())
        if echt:
            await pg.evaluate("""([clubs, rondes]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_rounds', JSON.stringify(rondes)); localStorage.setItem('golf_profile_name', 'Testspeler');
                localStorage.setItem('golf_profile_hcp', '30.8'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
                localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
                ['handicap','prestaties','banen'].forEach(g => localStorage.setItem('golf_stats_grp_' + g, 'open')); }""", [ECHTE_CLUBS, rondes])
        else:
            await pg.evaluate(testdata.SEED, [testdata.CLUBS, rondes])
        if lowhi is not None: await pg.evaluate("(v) => localStorage.setItem('golf_low_hi', v)", lowhi)
        await pg.reload(); await pg.wait_for_timeout(400)
        await pg.evaluate(MEESCHRIJVEN, KAPOT)
        low = await pg.evaluate("(p) => effectiveLowHi(p, loadSavedRounds())", speler)
        getoond = []          # (waar, waarde, low die erbij hoort of None)

        # Start
        await klik_tab(pg, 'setup')
        await pg.evaluate("() => updateComputedHcp()")
        t = (await pg.evaluate("() => document.getElementById('computedHcpVal').textContent")).strip()
        if re.fullmatch(GETAL, t): getoond.append(('WHS-hcp op Start', float(t), low))
        if verwacht is not None and not KAPOT:
            check(f"{naam}: WHS-hcp op Start is {verwacht}", t == verwacht, t)
        # Los nagerekend, buiten de app om: ruwe waarde en Low HI → wat er hoort te staan.
        ruw = await pg.evaluate("""(p) => { const a = loadSavedRounds(); const w = whsHandicap(last20Qualifying(p, a), null, esrMapFor(p, a)); return w ? w.rawValue : null; }""", speler)
        if ruw is not None and not KAPOT:
            hoort = ruw if (low is None or ruw <= low + 3) else min(low + 3 + (ruw - low - 3) / 2, low + 5)
            hoort = min(hoort, 54.0)
            hoort = f"{int(hoort * 10 + 0.5 + 1e-9) / 10:.1f}"
            check(f"{naam}: WHS-hcp op Start klopt met de narekening ({hoort}; ruw {ruw}, Low HI {low})", t == hoort, t)

        # Statistiek, drie periodes, en Wat als?
        await klik_tab(pg, 'stat')
        for periode in ('Laatste 20', '12 maanden', 'Alles'):
            k = pg.get_by_text(periode, exact=True).first
            if await k.count() and await k.is_visible():
                await k.click(); await pg.wait_for_timeout(200)
            tekst = await pg.evaluate("() => document.getElementById('screen-stat').innerText")
            m = re.search(GETAL + r'\s*\n\s*WHS-HCP', tekst)
            check(f"{naam}: kerngetal WHS-hcp staat op Statistiek ({periode})", m is not None)
            if m: getoond.append((f'kerngetal Statistiek ({periode})', float(m.group(1)), low))
        if await pg.locator('#watIfInput').count() == 0 or not await pg.locator('#watIfInput').is_visible():
            kop = pg.get_by_text('Wat als', exact=False).first
            if await kop.count(): await kop.click(); await pg.wait_for_timeout(200)
        if await pg.locator('#watIfInput').count() and await pg.locator('#watIfInput').is_visible():
            for sd in ('99', '54', '80.5', '0'):
                await pg.locator('#watIfInput').fill(sd)
                await pg.locator('#watIfInput').dispatch_event('input'); await pg.wait_for_timeout(120)
                r = await pg.evaluate("() => (document.getElementById('watIfResult') || {}).innerText || ''")
                for v in getallen_whs(r): getoond.append((f"Wat als? met dagresultaat {sd}", v, low))
                for m in re.finditer(r'Whs\s*' + GETAL, r): getoond.append((f"Wat als? huidige stand", float(m.group(1)), low))
        else:
            check(f"{naam}: 'Wat als?' is te openen", False)

        # Rondes: elke kaart
        await klik_tab(pg, 'archive')
        tekst = await pg.evaluate("() => document.getElementById('screen-archive').innerText")
        kaarten = getallen_whs(tekst)
        check(f"{naam}: de rondekaarten tonen een berekende handicap", len(kaarten) > 0)
        for v in kaarten: getoond.append(('rondekaart', v, None))      # Low HI van dat moment: zie laag 2

        # Scorescherm: een afgeronde qualifying ronde geladen
        await pg.evaluate("""(p) => { const s = loadSavedRounds(); const i = s.findIndex(r => r.player === p && r.qualifying && isRondeAf(r)); loadRoundSingle(i); }""", speler)
        await pg.wait_for_timeout(250)
        # Bij een open ronde staat sinds 10E geen 'Verwachte/Nieuwe WHS-hcp' meer (er wordt
        # gerekend met wat afgerond is en niet meer actief: zie test-meetellen.py). Wat hier
        # telt: ook met een open ronde blijft de WHS-hcp op Start binnen de grenzen, en na
        # het afronden van een rampzalige nieuwe ronde ook.
        async def start_nu(waar):
            await klik_tab(pg, 'setup')
            await pg.evaluate("() => updateComputedHcp()")
            t = (await pg.evaluate("() => document.getElementById('computedHcpVal').textContent")).strip()
            check(f"{naam}: WHS-hcp op Start is afgelezen ({waar})", re.fullmatch(GETAL, t) is not None, t)
            if re.fullmatch(GETAL, t):
                l = await pg.evaluate("(p) => effectiveLowHi(p, loadSavedRounds())", speler)
                getoond.append((f'WHS-hcp op Start ({waar})', float(t), l))
        await start_nu('met een opnieuw geladen ronde open')

        if not echt:
            await pg.evaluate("""() => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
                document.getElementById('iName').value='Testspeler'; document.getElementById('iHcp').value='30.7'; }""")
            await pg.wait_for_timeout(200)
            await pg.evaluate("""() => { startRound(); const cb=document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
            await pg.wait_for_timeout(300)
            await pg.evaluate("() => { nav('score'); renderScore(); }")
            for h in range(9):
                await pg.evaluate("(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 12); clearScoreTap(false); }", h)
                await pg.wait_for_timeout(40)
            await start_nu('met een nieuwe volle ronde open')
            await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(250)
            await start_nu('na het afronden van die ronde')
            await klik_tab(pg, 'archive')
            for v in getallen_whs(await pg.evaluate("() => document.getElementById('screen-archive').innerText")):
                getoond.append(('rondekaart na het afronden', v, None))

        # laag 3
        check(f"{naam}: er zijn getoonde handicaps afgelezen", len(getoond) >= 5, str(len(getoond)))
        for waar, v, l in getoond:
            g = over_de_grens(v, l)
            check(f"{naam}: {waar}", g is None, g)

        # laag 2
        log = await pg.evaluate("() => window._log")
        check(f"{naam}: er is onderweg gerekend", len(log) > 10, str(len(log)))
        gezien = set()
        for soort, raw, l, v, typ in log:
            g = over_de_grens(v, l)
            if g and (soort, v, l) not in gezien:
                gezien.add((soort, v, l))
                check(f"{naam}: berekening onderweg ({soort})", False, g)
        geteld[0] += len(log)
        check(f"{naam}: geen fouten in de pagina", not pf, str(pf))
        return {'naam': naam, 'getoond': len(getoond), 'berekend': len(log),
                'hard': sum(1 for x in log if x[4] == 'hard'), 'soft': sum(1 for x in log if x[4] == 'soft'),
                'op54': sum(1 for x in log if x[3] == 54.0 and x[1] > 54.0)}
    except Exception as e:
        check(f"{naam}: de doorloop is afgemaakt", False, str(e)[:300])
        return {'naam': naam, 'getoond': 0, 'berekend': 0, 'hard': 0, 'soft': 0, 'op54': 0}
    finally:
        await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app (begrenzing uit) — deze doorloop HOORT te falen.")

        print("=== 1. REKENKUNDIG ===")
        pg = await b.new_page()
        await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, testdata.RONDES]); await pg.reload(); await pg.wait_for_timeout(300)
        if KAPOT: await pg.evaluate(MEESCHRIJVEN, True)
        r = await pg.evaluate(RASTER)
        print(f"  raster: {r['n']} combinaties ({r['hard']} harde cap, {r['soft']} soft cap, {r['op54']} op 54,0)")
        check("raster: geen enkele combinatie over de grens", not r['fout'], ' | '.join(r['fout']))
        if not KAPOT:
            check("raster: alle drie de begrenzingen komen voor", r['hard'] > 0 and r['soft'] > 0 and r['op54'] > 0)
        w = await pg.evaluate(REEKSEN_WILLEKEURIG)
        print(f"  verzonnen reeksen: {w['n']} berekend, waarvan {w['begrensd']} begrensd")
        check("verzonnen reeksen: geen enkele over de grens", not w['fout'], ' | '.join(w['fout']))
        if not KAPOT:
            check("verzonnen reeksen: de begrenzing komt echt voor", w['begrensd'] > 20, str(w['begrensd']))
        await pg.close()

        print("\n=== 2 en 3. ONDERWEG EN OP HET SCHERM ===")
        uit = await asyncio.gather(*[doorloop(b, *x) for x in REEKSEN])
        for u in uit:
            print(f"  {u['naam']:<38} {u['getoond']:>4} getoond  {u['berekend']:>5} berekend  "
                  f"(harde cap {u['hard']}, soft cap {u['soft']}, op 54,0 {u['op54']})")
        if not KAPOT:
            check("de harde cap is onderweg echt geraakt", sum(u['hard'] for u in uit) > 0)
            check("de soft cap ook", sum(u['soft'] for u in uit) > 0)
            check("en de grens van 54,0", sum(u['op54'] for u in uit) > 0)
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
