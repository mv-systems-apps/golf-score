"""Een lege ronde mag een ronde met scores nooit overschrijven, en zegt dat ook.

saveActiveRound() weigert een lopende ronde zonder holes op te slaan als de opgeslagen
ronde wel holes heeft (een half geladen of leeg spel zou een volle kaart wissen). Die
weigering moet als 'niet opgeslagen' terugkomen, zodat afronden, laden en starten niet
doorgaan alsof er is opgeslagen. Gecontroleerd: de terugmelding (false bij weigering,
true bij een gewone opslag en zonder lopende ronde), en dat de ronde met scores in de
opslag ongewijzigd blijft, ook als je daarna afrondt of een andere ronde laadt.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

A = ronde(100, '2026-06-01', played=4); A['qualifying'] = False
B = ronde(101, '2026-06-02')
OPSLAG = "() => { const r = JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.id === 100); return r ? r.holes.map(h => h.score) : null; }"
VENSTER = "() => document.getElementById('confirmModal').classList.contains('hidden') ? '' : document.getElementById('confirmModalTitle').textContent"
DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def verse(b):
    pg = await b.new_page(viewport={"width": 390, "height": 844}); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
    await pg.goto(app_url())
    await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
      localStorage.setItem('golf_last_backup_date', new Date().toISOString()); localStorage.setItem('golf_active_id', '100'); }""", [CLUBS, [A, B]])
    await pg.reload(); await pg.wait_for_timeout(700); await pg.evaluate(DICHT)
    return pg, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        print("\n=== DE TERUGMELDING VAN saveActiveRound() ===\n")
        pg, pf = await verse(b)
        voor = await pg.evaluate(OPSLAG)
        check("uitgangspunt: de lopende ronde heeft 4 scores in de opslag", sum(1 for s in voor if s is not None), 4)
        check("gewone opslag geeft true", await pg.evaluate("saveActiveRound(true)"), True)
        bewaard = await pg.evaluate("game.holes.map(h => ({ ...h }))")
        await pg.evaluate("() => { game.holes = []; }")                        # een leeg spel in het geheugen
        check("een leeg spel over een ronde met scores: geweigerd, false", await pg.evaluate("saveActiveRound(true)"), False)
        check("de ronde met scores staat ongewijzigd in de opslag", await pg.evaluate(OPSLAG), voor)
        await pg.evaluate("(h) => { game.holes = h; }", bewaard)
        check("weer met holes: true", await pg.evaluate("saveActiveRound(true)"), True)
        await pg.evaluate("() => { game = { started: false, holes: [] }; }")
        check("zonder lopende ronde: niets op te slaan, true (zoals voorheen)", await pg.evaluate("saveActiveRound(true)"), True)
        await pg.close()

        print("\n=== AFRONDEN MET EEN LEEG SPEL ===\n")
        pg, pf = await verse(b)
        await pg.evaluate("() => { game.holes = []; finishActiveRound(null); }"); await pg.wait_for_timeout(300)
        check("melding: niet opgeslagen", await pg.evaluate(VENSTER), 'Niet opgeslagen')
        check("de ronde blijft de lopende ronde", await pg.evaluate("localStorage.getItem('golf_active_id')"), '100')
        check("en staat met scores ongewijzigd in de opslag", await pg.evaluate(OPSLAG), voor)
        check("geen fouten", pf, [])
        await pg.close()

        print("\n=== EEN ANDERE RONDE LADEN MET EEN LEEG SPEL ===\n")
        pg, pf = await verse(b)
        await pg.evaluate("() => { game.holes = []; const i = loadSavedRounds().findIndex(r => r.id === 101); loadRoundSingle(i); }"); await pg.wait_for_timeout(300)
        check("melding: niet opgeslagen, en de andere ronde is niet geladen", (await pg.evaluate(VENSTER), await pg.evaluate("game.id")), ('Niet opgeslagen', 100))
        check("de ronde met scores staat ongewijzigd in de opslag", await pg.evaluate(OPSLAG), voor)
        check("geen fouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
