"""Eén route van opgeslagen ronde naar lopende ronde (1352898-018).

Drie plekken maken van een opgeslagen ronde de lopende ronde: restoreActiveRound (bij het
starten), gameFromRound (laden, hervatten) en volgLopendeRondeUitOpslag (een wijziging in
een ander venster). Ze lopen nu via maakLopendeRonde; leegmaken via wisLopendeRonde.

  1. Speler 2 met een id als tekst (na een import uit een ander bestand): na herstarten
     kun je naar speler 2 wisselen en een score invoeren. Tot 017 werd het id met
     Number() gelezen, en bleef de app op speler 1.
  2. De drie routes geven voor dezelfde ronde dezelfde lopende ronde (zonder pcc, sdFinal
     en qualifying in de ronde: die vulden alleen restoreActiveRound in).
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

GAME = """() => JSON.stringify({ ...game, holes: game.holes.map(h => { const { _initScore, ...rest } = h; return rest; }) })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. SPELER 2 MET EEN ID ALS TEKST ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        r1 = ronde(1, '2026-05-01', played=3); r1['id'] = 'a1'
        r2 = ronde(2, '2026-05-01', played=3, speler='Partner'); r2['id'] = '17'
        await pg.evaluate(SEED, [CLUBS, [r1, r2]])
        await pg.evaluate("() => { localStorage.setItem('golf_active_id', 'a1'); localStorage.setItem('golf_game2_id', '17'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
        await pg.reload(); await pg.wait_for_timeout(800)
        check("na herstarten: speler 2 hoort bij de ronde '17'", await pg.evaluate("() => game2Id"), '17')
        await pg.evaluate("() => switchToPlayer(2)"); await pg.wait_for_timeout(200)
        check("wisselen naar speler 2 lukt", await pg.evaluate("() => [game.id, activePlayer]"), ['17', 2])
        await pg.evaluate("() => { setCurrentHole(4); selectHole(4); toggleScoreButtons(4); armScoreChange(4, 2); clearScoreTap(false); }"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(200)
        check("de score van speler 2 is opgeslagen", await pg.evaluate("() => leesRondes().find(r => r.id === '17').holes[4].score") is not None, True)
        check("terug bij speler 1", await pg.evaluate("() => [game.id, activePlayer]"), ['a1', 1])
        check("geen fouten in de pagina", pf, [])
        await ctx.close()

        print("\n=== 2. DRIE ROUTES, DEZELFDE LOPENDE RONDE ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        await pg.goto(app_url())
        r = ronde(5, '2026-06-01', played=4)
        for veld in ('pcc', 'sdFinal', 'qualifying'):
            r.pop(veld, None)
        await pg.evaluate(SEED, [CLUBS, [r]])
        await pg.evaluate("() => { localStorage.setItem('golf_active_id', '5'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
        await pg.reload(); await pg.wait_for_timeout(800)
        bijStart = await pg.evaluate(GAME)
        uitLaden = await pg.evaluate("() => { gameFromRound(leesRondes()[0]); return (" + GAME + ")(); }")
        uitVenster = await pg.evaluate("() => { game = { ...game, holes: [] }; volgLopendeRondeUitOpslag(); return (" + GAME + ")(); }")
        a, l, v = json.loads(bijStart), json.loads(uitLaden), json.loads(uitVenster)
        check("starten en laden geven dezelfde lopende ronde", sorted(k for k in set(a) | set(l) if a.get(k) != l.get(k)), [])
        check("starten en een ander venster geven dezelfde lopende ronde", sorted(k for k in set(a) | set(v) if a.get(k) != v.get(k)), [])
        check("pcc, dagresultaat en qualifying staan klaar", [a.get('pcc', 'ontbreekt'), a.get('sdFinal', 'ontbreekt'), a.get('qualifying')], [None, None, False])
        await ctx.close()
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
