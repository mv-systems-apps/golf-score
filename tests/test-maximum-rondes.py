"""Het maximum van 2500 rondes (1352898-014).

Komt een import boven het maximum uit, dan haalt de app de oudste rondes weg. Tot 013
gebeurde dat stil (alleen in de console). Nu zegt de melding na de import hoeveel er weg
zijn. Het startscherm waarschuwde al vóór je een ronde start (geen wijziging).

  1. Toevoegen uit een bestand: 2500 rondes + 3 → de melding noemt de 3 oudste.
  2. Vervangen door een backup van 2502 rondes → de melding noemt de 2 oudste.
  3. Onder het maximum: geen zin over verwijderen, en een eerdere telling lekt niet mee.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

MAAK = """([basis, n, start]) => Array.from({ length: n }, (_, i) => {
  const r = JSON.parse(JSON.stringify(basis));
  const d = new Date(Date.UTC(2010, 0, 1) + (start + i) * 864e5);
  r.id = 100000 + start + i; r.date = d.toISOString().slice(0, 10); r.time = '09:30';
  return r;
})"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        await pg.goto(app_url())
        basis = ronde(1, '2026-01-01')
        await pg.evaluate(SEED, [CLUBS, []])
        await pg.evaluate("([m, b]) => localStorage.setItem('golf_rounds', JSON.stringify(eval(m)([b, 2500, 0])))", [MAAK, basis])
        await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
        await pg.reload(); await pg.wait_for_timeout(800)
        melding = "() => document.getElementById('confirmModalMessage').textContent"

        print("\n=== 1. TOEVOEGEN BOVEN HET MAXIMUM ===\n")
        await pg.evaluate("([m, b]) => doAdditiveImport(eval(m)([b, 3, 5000]))", [MAAK, basis])
        tekst = await pg.evaluate(melding)
        check("de melding noemt dat de 3 oudste rondes weg zijn", 'de 3 oudste rondes zijn verwijderd' in tekst, True)
        check("het maximum staat erbij", 'maximum is 2500 rondes' in tekst, True)
        check("er staan 2500 rondes", await pg.evaluate("() => leesRondes().length"), 2500)
        check("de drie oudste zijn weg, de nieuwe staan er", await pg.evaluate(
            "() => { const d = new Set(leesRondes().map(r => r.date)); return [d.has('2010-01-01'), d.has('2010-01-03'), d.has('2010-01-04'), d.has(new Date(Date.UTC(2010, 0, 1) + 5002 * 864e5).toISOString().slice(0, 10))]; }"),
            [False, False, True, True])

        print("\n=== 2. VERVANGEN DOOR EEN BACKUP BOVEN HET MAXIMUM ===\n")
        await pg.evaluate("""([m, b]) => { if (doFullRestoreImport(eval(m)([b, 2502, 0]))) showStatus('2502 rondes geïmporteerd, je vorige rondes zijn vervangen.', false); }""", [MAAK, basis])
        tekst = await pg.evaluate(melding)
        check("de melding noemt dat de 2 oudste rondes weg zijn", 'de 2 oudste rondes zijn verwijderd' in tekst, True)

        print("\n=== 3. ONDER HET MAXIMUM ===\n")
        await pg.evaluate("() => { const R = loadSavedRounds().slice(0, 100); metVerwijderen(() => setRoundsAndMark(JSON.stringify(R))); }")
        check("eerst teruggebracht tot 100 rondes", await pg.evaluate("() => leesRondes().length"), 100)
        await pg.evaluate("([m, b]) => doAdditiveImport(eval(m)([b, 1, 7000]))", [MAAK, basis])
        tekst = await pg.evaluate(melding)
        check("geen zin over verwijderen", "oudste" in tekst, False)
        if "oudste" in tekst: print("        melding:", tekst)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
