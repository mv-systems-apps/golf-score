"""Lang indrukken op + (netto dubbel bogey) zet lege putts op 2, net als de andere knoppen.

Aanleiding (melding van de gebruiker): met putts bijhouden aan krijgt een hole bij het invullen
standaard 2 putts — behalve als je begint met lang indrukken op +. Oorzaak:
setDoubleBogey riep syncPuttsWithScore niet aan. Zo'n hole bleef zonder putts en viel
uit de puttcijfers.

Gecontroleerd met de ECHTE knop: indrukken, vasthouden, loslaten.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

async def start(pg, putts):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.evaluate("(aan) => localStorage.setItem('golf_track_putts', aan ? 'on' : 'off')", putts)
    await pg.reload(); await pg.wait_for_timeout(500)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
       document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.8'; }""")
    await pg.wait_for_timeout(250)
    await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
       if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(400)

async def open_hole(pg, i):
    await pg.evaluate("(i) => { selectScoreRow(i); }", i)
    await pg.wait_for_timeout(150)

async def lang_plus(pg, ms=700):
    vak = await pg.locator('.sum-tr-btn-cell.plus-cell[onpointerdown]').first.bounding_box()
    await pg.mouse.move(vak['x'] + vak['width'] / 2, vak['y'] + vak['height'] / 2)
    await pg.mouse.down(); await pg.wait_for_timeout(ms); await pg.mouse.up()
    await pg.wait_for_timeout(150)

HOLE = "(i) => ({ score: game.holes[i].score, putts: game.holes[i].putts ?? null, db: game.holes[i].ppar + 2 })"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        paginafouten = []
        pg.on('pageerror', lambda e: paginafouten.append(str(e)[:120]))

        print("\n=== 1. LEGE HOLE, LANG INDRUKKEN OP + ===\n")
        await start(pg, True)
        await open_hole(pg, 0)
        await lang_plus(pg)
        h = await pg.evaluate(HOLE, 0)
        check("score is netto dubbel bogey", h['score'], h['db'])
        check("putts staan op 2", h['putts'], 2)
        check("en dat is bewaard in de opgeslagen ronde", await pg.evaluate(
            "() => (leesRondes().find(r => String(r.id) === String(game.id)).holes[0].putts ?? null)"), 2)

        print("\n=== 2. KORTE TIK OP + (was al goed) ===\n")
        await open_hole(pg, 1)
        await lang_plus(pg, ms=60)
        h = await pg.evaluate(HOLE, 1)
        check("putts staan op 2", h['putts'], 2)

        print("\n=== 3. AL INGEVULDE PUTTS BLIJVEN STAAN ===\n")
        await open_hole(pg, 2)
        await lang_plus(pg, ms=60)
        await pg.evaluate("() => { stepPutts(2, +1); }")          # 3 putts
        await lang_plus(pg)
        h = await pg.evaluate(HOLE, 2)
        check("score is netto dubbel bogey", h['score'], h['db'])
        check("putts blijven 3", h['putts'], 3)

        print("\n=== 4. PUTTS UIT: GEEN PUTTS ===\n")
        await start(pg, False)
        await open_hole(pg, 0)
        await lang_plus(pg)
        h = await pg.evaluate(HOLE, 0)
        check("score is netto dubbel bogey", h['score'], h['db'])
        check("geen putts", h['putts'], None)

        check("geen fouten in de pagina", paginafouten, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
