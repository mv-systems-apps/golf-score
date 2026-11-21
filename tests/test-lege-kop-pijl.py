"""Het pijltje bij Geplande rondes volgt wat je ziet (13528FD-003).

Tot 13528FD-002 volgde het pijltje van de gouden kop alleen de bewaarde stand (ingeklapt ja/nee).
Opende je in de ingeklapte stand een kaart (tik op een regel, of via de agendastrook), dan bleef
het ▶; een tik op de kop klapte dan je kaart dicht en opende de eerste. Andersom stond er ▼ als
je in de gewone stand de open kaart dichtklapte. Nu:
  - ▼ zolang er een kaart open staat, ▶ als alles compact is (ook aria-expanded);
  - een tik op de kop doet wat het pijltje belooft en de app onthoudt dat;
  - een kaart openen verandert de bewaarde stand niet (herstart: nog steeds ingeklapt);
  - zonder regels (instelling 0) volgt het pijltje de bewaarde stand;
  - Gepauzeerde rondes zoals voorheen.
Via de echte knoppen (regel, kop) en de agendastrook.
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

async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

async def klik(pg, sel):
    try: await pg.locator(sel).first.click(timeout=2000); await pg.wait_for_timeout(150); return True
    except Exception: return False

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

# [pijl uitgeklapt (90°), aria-expanded, open kaart(en)]
def STAAT(soort='gepland'):
    return """() => { const kop = document.querySelector('#scoreEmptyMsg .lege-kop[data-kop=%s]'); if (!kop) return null; const svg = kop.querySelector('svg');
      return [svg ? svg.style.transform === 'rotate(90deg)' : null, kop.getAttribute('aria-expanded'), [...document.querySelectorAll('#scoreEmptyMsg .lege-open[data-regel^=%s]')].map(e => e.dataset.regel.split(':')[1])]; }""" % (soort, soort)
KOP = '#scoreEmptyMsg .lege-kop[data-kop=gepland]'
REGEL = lambda id_: f'#scoreEmptyMsg .lege-regel[data-regel="gepland:{id_}"]'
BEWAARD = "() => localStorage.getItem('golf_lege_verkort')"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 900})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        hoofd = await ev(pg, "() => startPlayerName()")
        for i, d in enumerate((3, 6, 9)):
            await ev(pg, PLAN % dag(d), [990901 + i, 'Golfclub Heelsum', 'Airborne', 'Blauw', hoofd])
        await ev(pg, "() => { localStorage.setItem('golf_lege_verkort', 'gepland'); _legeOpen.gepland = undefined; nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(200)

        print("\n=== 1. INGEKLAPT ===\n")
        check("ingeklapt, alles compact: ▶", await ev(pg, STAAT()), [False, 'false', []])
        await klik(pg, REGEL(990902))
        check("tik op een regel: die kaart open, ▼", await ev(pg, STAAT()), [True, 'true', ['990902']])
        check("de bewaarde stand blijft ingeklapt", await ev(pg, BEWAARD), 'gepland')
        await klik(pg, KOP)
        check("tik op de kop (▼): alles compact, ▶ — je kaart gaat dicht, niet de eerste open", await ev(pg, STAAT()), [False, 'false', []])
        check("en de app onthoudt: ingeklapt", await ev(pg, BEWAARD), 'gepland')
        await klik(pg, REGEL(990903))
        await ev(pg, "() => { const k = document.querySelector('#scoreEmptyMsg .lege-open[data-regel=\"gepland:990903\"] .lege-knop'); if (!k) return; const r = k.getBoundingClientRect(); legeKaartTik({ target: k, clientX: r.left + 20, clientY: r.top + 8 }, k); }"); await pg.wait_for_timeout(150)
        check("kaart openen en bovenin weer dichtklappen: ▶", await ev(pg, STAAT()), [False, 'false', []])

        print("\n=== 2. VIA DE AGENDASTROOK ===\n")
        await klik(pg, f'#hdrGeplandStrook .kop-dag[data-iso="{dag(9)}"]')
        if not await ev(pg, STAAT()) or (await ev(pg, STAAT()))[2] != ['990903']:
            await ev(pg, "(iso) => naarRondeOpScorescherm(iso, true)", dag(9)); await pg.wait_for_timeout(200)
        check("dag in de strook: die kaart open, ▼", await ev(pg, STAAT()), [True, 'true', ['990903']])
        await ev(pg, "() => { _legeOpen.gepland = undefined; verversLegeScoreKnoppen(); }")
        check("herstart van de lijst (zoals na openen van de app): weer ingeklapt, ▶", await ev(pg, STAAT()), [False, 'false', []])

        print("\n=== 3. UITKLAPPEN EN GEWONE STAND ===\n")
        await klik(pg, KOP)
        check("tik op de kop (▶): de eerste open, ▼", await ev(pg, STAAT()), [True, 'true', ['990901']])
        check("en de app onthoudt: uitgeklapt", await ev(pg, BEWAARD), None)
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990901"] .lege-knop')
        await pg.wait_for_timeout(100)
        st = await ev(pg, STAAT())
        if st and st[2]:   # de kaart klapt dicht met een tik bovenin (datum/naam), niet overal
            await ev(pg, "() => { const k = document.querySelector('#scoreEmptyMsg .lege-open[data-regel=\"gepland:990901\"] .lege-knop'); const r = k.getBoundingClientRect(); legeKaartTik({ target: k, clientX: r.left + 20, clientY: r.top + 8 }, k); }")
            await pg.wait_for_timeout(150)
        check("gewone stand, de open kaart dichtgeklapt: ▶", await ev(pg, STAAT()), [False, 'false', []])
        await klik(pg, KOP)
        check("tik op de kop (▶): de eerste weer open, ▼ (niet ingeklapt bewaard)", [await ev(pg, STAAT()), await ev(pg, BEWAARD)], [[True, 'true', ['990901']], None])

        print("\n=== 4. INSTELLING 0 EN GEPAUZEERD ===\n")
        await ev(pg, "() => { localStorage.setItem('golf_lege_lijst_n', '0'); localStorage.setItem('golf_lege_verkort', 'gepland'); verversLegeScoreKnoppen(); }")
        check("0 regels, ingeklapt bewaard: ▶", (await ev(pg, STAAT()) or [None])[:2], [False, 'false'])
        await ev(pg, "() => { localStorage.removeItem('golf_lege_verkort'); verversLegeScoreKnoppen(); }")
        check("0 regels, uitgeklapt bewaard: ▼", (await ev(pg, STAAT()) or [None])[:2], [True, 'true'])
        await ev(pg, "() => { localStorage.removeItem('golf_lege_lijst_n'); verversLegeScoreKnoppen(); }")
        # een gepauzeerde ronde: ingeklapt alleen de kop (▶), anders de lijst (▼) zoals voorheen
        await ev(pg, """() => { const s = loadSavedRounds(); const r = s.find(x => x.id === 990901); r.date = todayISO(); r.time = '00:01'; r.holes[0].score = 5; setRoundsAndMark(JSON.stringify(s)); _legeOpen.gepauzeerd = undefined; verversLegeScoreKnoppen(); }""")
        check("gepauzeerd uitgeklapt: ▼ met de kaart", await ev(pg, STAAT('gepauzeerd')), [True, 'true', ['990901']])
        await klik(pg, '#scoreEmptyMsg .lege-kop[data-kop=gepauzeerd]')
        check("gepauzeerd ingeklapt: ▶, alleen de kop", [await ev(pg, STAAT('gepauzeerd')), await ev(pg, "() => document.querySelectorAll('#scoreEmptyMsg [data-regel^=gepauzeerd]').length")], [[False, 'false', []], 0])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
