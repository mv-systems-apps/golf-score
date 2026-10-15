"""Score en putts horen bij elkaar — langs ELKE manier om een score te zetten.

De regel staat in de app zelf: "Putts volgen de score: een score invullen of wijzigen
zet putts op 2 (als de instelling aanstaat en er nog niets stond), een score wissen haalt
putts weg." Op 3-10-2026 bleek lang indrukken op + die regel over te slaan. Dat is
gerepareerd en getest — voor die ene knop. Deze test controleert de regel voor alle
knoppen tegelijk, vanuit elke beginstand, met putts aan en uit, voor speler 1 en 2.

De knoppen worden echt ingedrukt (indrukken, vasthouden, loslaten).

De verwachte uitkomst komt uit een klein model van de regels hieronder, los van de app:
  - tik +      lege hole wordt par+1, anders één erbij (hooguit 19)
  - tik −      lege hole wordt par, anders één eraf; onder 1 wordt de hole leeg
  - lang +     netto dubbel bogey (persoonlijke par + 2)
  - lang −     ongedaan maken: terug naar de score van toen je de hole koos. Dat is een
               VOORLOPIGE wijziging: bevestig je niet binnen twee seconden, dan komt de
               stand van daarvoor terug — de score én de putts.
  - putts      geen score -> geen putts. Putts aan en een score zonder putts -> 2.
               Putts uit -> er komen geen putts bij.
               Hooguit score − 1 putts (bij een hole-in-one 0) en nooit meer dan 5:
               verlaag je de score tot onder het aantal putts, dan gaan de putts mee.
Daarnaast: de opslag is gelijk aan het scherm.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {echt} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

# Beginstanden van de hole: (naam, score t.o.v. par of None, putts of None)
STANDEN = [("lege hole", None, None), ("score met 2 putts", +1, 2), ("score met 0 putts", 0, 0),
           ("score zonder putts (oude ronde)", +1, None), ("hole-in-one", 'een', 0), ("score met 5 putts", +2, 5), ("score 2 met 1 putt", 'twee', 1)]
HANDELINGEN = ["tik +", "tik −", "lang +", "tik + en dan lang − (bevestigd)", "tik + en dan lang − (laten verlopen)", "drie keer −", "tik + tik −"]

def model(score, putts, par, ppar, aan, handeling):
    """Wat er volgens de regels uit moet komen: (score, putts)."""
    def sync(s, p):
        if s is None: return (None, None)
        hoogste = max(0, min(5, s - 1))
        if p is not None: return (s, min(p, hoogste))
        return (s, min(2, hoogste) if aan else None)
    def plus(s, p): return sync(par + 1 if s is None else min(19, s + 1), p)
    def min_(s, p): return sync(par if s is None else (None if s - 1 < 1 else s - 1), p)
    begin = score
    if handeling == "tik +": return plus(score, putts)
    if handeling == "tik −": return min_(score, putts)
    if handeling == "lang +": return sync(ppar + 2, putts)
    if handeling == "drie keer −":
        st = (score, putts)
        for _ in range(3): st = min_(*st)
        return st
    if handeling == "tik + tik −": return min_(*plus(score, putts))
    na_plus = plus(score, putts)
    if "laten verlopen" in handeling: return na_plus            # de voorlopige wijziging vervalt geheel
    return sync(begin, na_plus[1])                                # bevestigd: terug naar de beginscore


HOLE = "() => { const h = game.holes[0]; const o = leesRondes().find(r => String(r.id) === String(game.id)).holes[0]; return { score: h.score, putts: h.putts ?? null, oScore: o.score, oPutts: o.putts ?? null, par: h.par, ppar: h.ppar }; }"

async def start(pg, putts_aan):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, []])
    await pg.evaluate("(aan) => { localStorage.setItem('golf_track_putts', aan ? 'on' : 'off'); localStorage.setItem('golf_auto_next', 'off'); }", putts_aan)
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
        document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8';
        player2Visible = true; sel2.gender = 'Dames'; sel2.tee = 'Rood'; document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
        startRound(); }"""); await pg.wait_for_timeout(300)

async def zet_stand(pg, score, putts):
    # De hole in de beginstand zetten en het invoerpaneel openen, zoals na het aantikken van de rij.
    await pg.evaluate("""([score, putts]) => { clearScoreTap?.(false); const h = game.holes[0];
        h.score = score === null ? null : (score === 'een' ? 1 : score === 'twee' ? 2 : h.par + score);
        if (putts === null) delete h.putts; else h.putts = putts;
        scoreButtonsRow = null; saveActiveRound(true); setCurrentHole(0); selectScoreRow(0); nav('score'); }""", [score, putts])
    await pg.wait_for_timeout(120)

async def druk(pg, cel, ms=60):
    vak = await pg.locator(f'.sum-tr-btn-cell.{cel}[onpointerdown]').first.bounding_box()
    await pg.mouse.move(vak['x'] + vak['width'] / 2, vak['y'] + vak['height'] / 2)
    await pg.mouse.down(); await pg.wait_for_timeout(ms); await pg.mouse.up(); await pg.wait_for_timeout(120)

async def doe(pg, handeling):
    if handeling == "tik +": await druk(pg, 'plus-cell')
    elif handeling == "tik −": await druk(pg, 'minus-cell')
    elif handeling == "lang +": await druk(pg, 'plus-cell', 700)
    elif handeling.startswith("tik + en dan lang −"):
        await druk(pg, 'plus-cell'); await druk(pg, 'minus-cell', 700)
        if "bevestigd" in handeling: await pg.evaluate("() => { if (scoreTapHole !== null) confirmScoreTap(0); }")
        else: await pg.wait_for_timeout(2200)
    elif handeling == "drie keer −":
        for _ in range(3): await druk(pg, 'minus-cell')
    elif handeling == "tik + tik −": await druk(pg, 'plus-cell'); await druk(pg, 'minus-cell')
    await pg.wait_for_timeout(120)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        gevallen = 0
        for putts_aan in (True, False):
            for speler in (1, 2):
                print(f"\n=== PUTTS BIJHOUDEN {'AAN' if putts_aan else 'UIT'}, SPELER {speler} OP HET SCHERM ===\n")
                await start(pg, putts_aan)
                if speler == 2: await pg.evaluate("() => switchToPlayer(2)")
                mis = []
                for snaam, score, putts in STANDEN:
                    for h in HANDELINGEN:
                        await zet_stand(pg, score, putts)
                        voor = await pg.evaluate(HOLE)
                        await doe(pg, h)
                        na = await pg.evaluate(HOLE); gevallen += 1
                        hoort = model(voor['score'], voor['putts'], voor['par'], voor['ppar'], putts_aan, h)
                        waar = f"{snaam} / {h}: {voor['score']}/{voor['putts']} -> {na['score']}/{na['putts']}"
                        if (na['score'], na['putts']) != hoort: mis.append(f"{waar}, verwacht {hoort[0]}/{hoort[1]}")
                        if na['putts'] is not None and not (0 <= na['putts'] <= max(0, min(5, (na['score'] or 0) - 1))): mis.append("meer putts dan kan: " + waar)
                        if (na['score'], na['putts']) != (na['oScore'], na['oPutts']): mis.append(f"opslag wijkt af: {waar} — opslag {na['oScore']}/{na['oPutts']}")
                check(f"alle {len(STANDEN) * len(HANDELINGEN)} combinaties van beginstand en handeling", mis, [])
        print("\n=== EEN VOORLOPIGE WIJZIGING DIE VERLOOPT GEEFT OOK DE PUTTS TERUG ===\n")
        # Je vult een hole in, zet de putts op 4, en drukt per ongeluk lang op −. De hole
        # wordt leeg (voorlopig). Bevestig je niet, dan hoort alles terug te komen.
        for uit_tijdens in (False, True):
            await start(pg, True)
            await pg.evaluate("() => { setCurrentHole(0); selectScoreRow(0); nav('score'); }"); await pg.wait_for_timeout(120)
            await druk(pg, 'plus-cell'); await pg.evaluate("() => { stepPutts(0, +1); stepPutts(0, +1); }")
            if uit_tijdens: await pg.evaluate("() => { localStorage.setItem('golf_track_putts', 'off'); renderScore(); }")
            voor = await pg.evaluate(HOLE)
            await druk(pg, 'minus-cell', 700)
            tussen = await pg.evaluate(HOLE)
            await pg.wait_for_timeout(2300)
            na = await pg.evaluate(HOLE)
            wat = "putts intussen uitgezet" if uit_tijdens else "putts aan"
            check(f"{wat}: ingevuld met 4 putts", (voor['score'], voor['putts']), (voor['par'] + 1, 4))
            check(f"{wat}: lang − maakt de hole voorlopig leeg", (tussen['score'], tussen['putts']), (None, None))
            check(f"{wat}: na twee seconden staat alles terug, ook de 4 putts", (na['score'], na['putts'], na['oScore'], na['oPutts']), (voor['score'], 4, voor['score'], 4))

        print("\n=== DE PUTTKNOPPEN GAAN NIET BOVEN WAT BIJ DE SCORE KAN ===\n")
        await start(pg, True)
        for score, hoogste in [(1, 0), (2, 1), (3, 2), (4, 3), (6, 5), (9, 5)]:
            r = await pg.evaluate("""(score) => { setCurrentHole(0); const h = game.holes[0]; h.score = score; delete h.putts; syncPuttsWithScore(0);
                const start = h.putts; for (let k = 0; k < 8; k++) stepPutts(0, +1); const top = h.putts;
                let n = 0; while (h.putts != null && n++ < 8) stepPutts(0, -1); return [start, top, h.putts ?? null]; }""", score)
            check(f"score {score}: begint op {min(2, hoogste)}, hoogstens {hoogste}, onder 0 leeg", r, [min(2, hoogste), hoogste, None])

        print(f"\n   {gevallen} gevallen doorlopen")
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
