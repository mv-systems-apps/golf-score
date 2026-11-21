"""De handicap wordt alleen berekend voor de speler bovenin Start, nooit voor speler 2.

Vaste regel (gebruiker, 4-10-2026). Speler 2 mag later zelf bovenin Start staan; dan wordt er
voor hem gerekend, maar alleen met zijn eigen rondes.

Drie lagen:

  1. VOOR WIE WORDT ER GEREKEND — terwijl de test alle schermen langsloopt, wordt bij
     elke handicapberekening genoteerd voor welke speler, en van welke spelers de
     rondes zijn die erin gaan. Dat mag alleen de naam bovenin Start zijn. Standen:
     geen lopende ronde, twee spelers met speler 1 voor, twee spelers met speler 2
     voor, en een afgeronde ronde van de ander opnieuw geladen.
  2. OP HET SCHERM — bij de ronde van speler 2 (scorescherm, ronde-informatie) en op
     zijn rondekaarten staat geen berekende handicap, geen 'Nieuwe/Verwachte WHS-hcp'
     en geen WHS-driehoekje.
  3. SPELER 2 BOVENIN START — zijn naam bovenin geeft een handicap uit alleen zijn
     eigen rondes: dezelfde uitkomst als wanneer alle rondes van Testspeler zijn weggehaald,
     en een andere dan die van Testspeler.

Speler 2 heeft in deze test zelf een geschiedenis van afgeronde qualifying rondes: er
valt voor hem dus echt iets te berekenen, als de app dat zou doen.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-handicap-alleen-speler1.py
draait op een app waarin 'de speler bovenin Start' is vervangen door 'de speler die
op het scherm staat'. Dan moet hij falen.
"""
import asyncio, datetime, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

KAPOT = os.environ.get('KAPOT') == '1'
fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

# Testspeler: de gewone testrondes. Partner: veertien eigen afgeronde qualifying rondes met
# heel andere dagresultaten, zodat zijn handicap herkenbaar anders is.
def rondes():
    v = datetime.date.today() - datetime.timedelta(days=3)
    uit = list(testdata.RONDES)
    for i in range(14):
        r = testdata.ronde(5000 + i, (v - datetime.timedelta(days=i * 9)).isoformat(), speler='Partner')
        r['time'] = '14:10'; r['hcp'] = 12.0
        r['sd'] = 11.0 + (i % 4); r['sdFinal'] = r['sd'] if i % 3 else None    # een deel zonder vastgesteld dagresultaat
        uit.append(r)
    return uit

MEESCHRIJVEN = """(kapot) => {
  window._wie = [];
  const boven = () => (document.getElementById('iName').value || '').trim();
  const noteer = (bron, speler) => window._wie.push([bron, speler == null ? null : String(speler), boven()]);
  for (const naam of ['whsStand', 'last20Qualifying', 'esrMapFor', 'effectiveLowHi', 'derivedLowHi', 'currentOfficialHcp', 'computeWhatIf', 'lowHiCheckStatus']) {
    const f = window[naam]; if (typeof f !== 'function') { window._wie.push(['ONTBREEKT ' + naam, null, boven()]); continue; }
    window[naam] = function (speler, ...rest) { if (speler) noteer(naam, speler); return f(speler, ...rest); };
  }
  const whs = window.whsHandicap;
  window.whsHandicap = function (rounds, low = null, esr = null) {
    const r = whs(rounds, low, esr);
    if (r) new Set((rounds || []).map(x => x.player)).forEach(p => noteer('whsHandicap (rondes van)', p));
    return r;
  };
  if (kapot) window.startPlayerName = () => (game && game.started && game.player) ? game.player : boven();
}"""

START = """(twee) => { nav('setup'); sel.track='Airborne'; sel.gender='Heren'; sel.tee='Blauw'; sel.qualifying=true;
  document.getElementById('iName').value='Testspeler'; document.getElementById('iHcp').value='30.7';
  if (twee) togglePlayer2(true); }"""
START2 = """(twee) => { if (twee) { document.getElementById('iName2').value='Partner'; document.getElementById('iHcp2').value='12.0';
  sel2.track='Airborne'; sel2.gender='Heren'; sel2.tee='Blauw'; sel2.qualifying=true; }
  startRound(); const cb=document.getElementById('confirmModalBtn');
  if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"""

async def start_twee(pg):
    await pg.evaluate(START, True); await pg.wait_for_timeout(200)
    await pg.evaluate(START2, True); await pg.wait_for_timeout(300)
    await pg.evaluate("() => { nav('score'); renderScore(); }"); await pg.wait_for_timeout(100)
    for speler in (1, 2):                       # allebei alle holes: dan is er het meest te berekenen
        await pg.evaluate("(n) => switchToPlayer(n)", speler); await pg.wait_for_timeout(120)
        for h in range(9):
            await pg.evaluate("(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h); armScoreChange(h, 5); clearScoreTap(false); }", h)
            await pg.wait_for_timeout(40)

async def stand_geen(pg): pass
async def stand_twee_p1(pg): await start_twee(pg); await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(150)
async def stand_twee_p2(pg): await start_twee(pg); await pg.evaluate("() => switchToPlayer(2)"); await pg.wait_for_timeout(150)
async def stand_ander_geladen(pg):
    await pg.evaluate("() => { const s = loadSavedRounds(); loadRoundSingle(s.findIndex(r => r.player === 'Partner' && r.qualifying && isRondeAf(r))); }")
    await pg.wait_for_timeout(300)

STANDEN = [
    ('geen lopende ronde',                      stand_geen,          None),
    ('twee spelers, speler 1 voor',             stand_twee_p1,       'Testspeler'),
    ('twee spelers, speler 2 voor',             stand_twee_p2,       'Partner'),
    ('afgeronde ronde van de ander geladen',    stand_ander_geladen, 'Partner'),
]

GETAL = r'(-?\d+\.\d)'
KAARTEN = """() => [...document.querySelectorAll('#screen-archive .saved-item')].map(k => ({
  tekst: k.innerText,
  driehoek: [...k.querySelectorAll('svg')].filter(s => (s.getAttribute('stroke') || '').includes('--orange') && s.querySelector('path[d^="M10.29"]')).length,
}))"""

async def pagina(b):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [testdata.CLUBS, rondes()])
    await pg.reload(); await pg.wait_for_timeout(400)
    return pg, pf

async def doorloop(b, naam, opzet, op_scherm):
    pg, pf = await pagina(b)
    try:
        await pg.evaluate(MEESCHRIJVEN, KAPOT)
        await opzet(pg)
        boven = await pg.evaluate("() => document.getElementById('iName').value.trim()")
        check(f"{naam}: bovenin Start staat Testspeler", boven == 'Testspeler', boven)

        teksten = {}
        for s in ('setup', 'score', 'stat', 'archive', 'club', 'settings', 'stat', 'score'):
            await pg.locator('#tab-' + s).click(); await pg.wait_for_timeout(220)
            teksten[s] = await pg.evaluate("(s) => document.getElementById('screen-' + s).innerText", s)
        await pg.locator('#tab-archive').click(); await pg.wait_for_timeout(250)
        kaarten = await pg.evaluate(KAARTEN)

        # laag 1
        wie = await pg.evaluate("() => window._wie")
        ontbreekt = [w[0] for w in wie if w[0].startswith('ONTBREEKT')]
        check(f"{naam}: de test kan alle rekenfuncties volgen", not ontbreekt, str(ontbreekt))
        check(f"{naam}: er is onderweg gerekend", len(wie) > 5, str(len(wie)))
        fout = sorted({(bron, speler) for bron, speler, top in wie if speler != top and not bron.startswith('ONTBREEKT')})
        check(f"{naam}: er wordt alleen voor de speler bovenin Start gerekend", not fout,
              '; '.join(f"{bron} voor '{speler}'" for bron, speler in fout))
        geteld[0] += len(wie)

        # laag 2: de ronde van de ander op het scherm
        if op_scherm == 'Partner':
            check(f"{naam}: de ronde-informatie is die van Partner", 'Partner' in teksten['stat'], teksten['stat'][:80].replace('\n', ' | '))
            for s in ('score', 'stat'):
                t = teksten[s]
                check(f"{naam}: scherm '{s}' toont geen berekende WHS-hcp bij Partner",
                      not re.search(r'WHS-hcp', t, re.I), ' | '.join(x for x in t.split('\n') if re.search('whs', x, re.I))[:200])

        # laag 2: de rondekaarten
        vanPartner = [k for k in kaarten if re.search(r'(^|\n)\s*Partner\b', k['tekst'])]
        vanTestspeler = [k for k in kaarten if re.search(r'(^|\n)\s*Testspeler\b', k['tekst'])]
        check(f"{naam}: er staan kaarten van Partner en van Testspeler in Rondes", len(vanPartner) >= 10 and len(vanTestspeler) >= 10,
              f"{len(vanPartner)} / {len(vanTestspeler)} van {len(kaarten)}")
        metWhs = [k['tekst'].replace('\n', ' | ')[:120] for k in vanPartner if re.search(r'Whs\s*' + GETAL + r'\s*' + GETAL, k['tekst'])]
        check(f"{naam}: geen kaart van Partner toont een berekende handicap", not metWhs, str(metWhs[:2]))
        metDriehoek = [k['tekst'].replace('\n', ' | ')[:120] for k in vanPartner if k['driehoek']]
        check(f"{naam}: geen kaart van Partner heeft een WHS-driehoekje", not metDriehoek, str(metDriehoek[:2]))
        # De teller 'N zonder dagresultaat' bovenaan Rondes en in Instellingen: alleen rondes van de speler bovenin.
        tel = await pg.evaluate("""() => { const r = leesRondes().filter(roundHasWarning); return [r.length, r.filter(x => x.player !== document.getElementById('iName').value.trim()).length]; }""")
        check(f"{naam}: de waarschuwing 'zonder dagresultaat' telt geen rondes van een ander", tel[1] == 0, f"{tel[1]} van de {tel[0]}")
        if not KAPOT:
            check(f"{naam}: de kaarten van Testspeler tonen de berekende handicap wel",
                  any(re.search(r'Whs\s*' + GETAL + r'\s*' + GETAL, k['tekst']) for k in vanTestspeler))
        check(f"{naam}: geen fouten in de pagina", not pf, str(pf))
        return naam, len(wie)
    except Exception as e:
        check(f"{naam}: de doorloop is afgemaakt", False, str(e)[:300])
        return naam, 0
    finally:
        await pg.close()

async def bovenin(pg, naam):
    """Typt de naam bovenin Start en geeft de getoonde WHS-hcp terug."""
    await pg.locator('#tab-setup').click(); await pg.wait_for_timeout(150)
    await pg.locator('#iName').fill(naam)
    await pg.locator('#iName').dispatch_event('input'); await pg.locator('#iName').dispatch_event('change')
    await pg.locator('#iName').blur(); await pg.wait_for_timeout(250)
    # 'Naam bestaat al — die rondes gaan meetellen in je handicap': dat is precies de bedoeling.
    knop = pg.locator('#keuzeModalKnop2')
    if await knop.is_visible():
        await knop.click(); await pg.wait_for_timeout(250)
    await pg.evaluate("() => updateComputedHcp()")
    return (await pg.evaluate("() => document.getElementById('computedHcpVal').textContent")).strip()

async def speler2_bovenin(b):
    naam = 'speler 2 bovenin Start'
    pg, pf = await pagina(b)
    vanTestspeler = await bovenin(pg, 'Testspeler')
    await pg.evaluate(MEESCHRIJVEN, False)
    metTestspeler = await bovenin(pg, 'Partner')
    await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(250)
    stat = await pg.evaluate("() => document.getElementById('screen-stat').innerText")
    wie = await pg.evaluate("() => window._wie")
    await pg.close()
    check(f"{naam}: er komt een handicap voor Partner", re.fullmatch(GETAL, metTestspeler) is not None, metTestspeler)
    check(f"{naam}: een andere dan die van Testspeler ({vanTestspeler})", metTestspeler != vanTestspeler, metTestspeler)
    m = re.search(GETAL + r'\s*\n\s*WHS-HCP', stat)
    check(f"{naam}: Statistiek toont dezelfde", m is not None and m.group(1) == metTestspeler, m.group(1) if m else stat[:60])
    fout = sorted({(bron, s, top) for bron, s, top in wie if s != top and not bron.startswith('ONTBREEKT')})
    check(f"{naam}: er wordt alleen gerekend voor wie op dat moment bovenin staat", not fout, str(fout))
    check(f"{naam}: en er is voor Partner gerekend", any(s == 'Partner' and top == 'Partner' for _, s, top in wie))

    # dezelfde app zonder één ronde van Testspeler: de uitkomst moet gelijk zijn
    pg, pf2 = await pagina(b)
    await pg.evaluate("() => { const s = loadSavedRounds().filter(r => r.player === 'Partner'); metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); }")
    await pg.reload(); await pg.wait_for_timeout(400)
    zonderTestspeler = await bovenin(pg, 'Partner')
    await pg.close()
    check(f"{naam}: de rondes van Testspeler weghalen verandert zijn handicap niet", zonderTestspeler == metTestspeler, f"{metTestspeler} → {zonderTestspeler}")
    check(f"{naam}: geen fouten in de pagina", not pf and not pf2, str(pf + pf2))
    print(f"  Testspeler bovenin: {vanTestspeler}   Partner bovenin: {metTestspeler}   Partner zonder de rondes van Testspeler: {zonderTestspeler}")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")
        uit = await asyncio.gather(*[doorloop(b, *s) for s in STANDEN])
        for naam, n in uit: print(f"  {naam:<42} {n:>5} berekeningen gevolgd")
        if not KAPOT: await speler2_bovenin(b)
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
