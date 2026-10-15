"""Een wachtende scorewijziging blijft bij haar eigen ronde.

Tik je één keer op een score om die te wissen of te wijzigen, dan wacht de app twee
seconden op een bevestiging; zonder bevestiging gaat de oude score terug. Vervang je in
die twee seconden de lopende ronde door een andere, dan mag de oude score niet in de
nieuwe ronde terechtkomen, en moet de eerste ronde haar oude score terugkrijgen.
In 122 is dit geregeld voor wisselen van speler, afronden en opslaan. Hier de overige
wegen die de lopende ronde vervangen.
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

def rondes():
    A = ronde(100, '2026-06-01', played=6); A['qualifying'] = False      # loopt, holes 1-6 gespeeld
    B = ronde(101, '2026-06-02', played=9); B['holes'][4]['score'] = 3    # andere ronde, hole 5 = 3
    C = ronde(102, '2026-06-03', played=9)
    return [A, B, C]
ZET = """([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_player_name', 'Mark');
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); localStorage.setItem('golf_active_id', '100'); }"""
OPSLAG = "(id) => { const r = JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.id === id); return r ? r.holes[4].score : 'weg'; }"
BEVESTIG = "() => { const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"
WEGEN = [
    ('een andere ronde laden',          "() => { const i = loadSavedRounds().findIndex(r => r.id === 101); loadRoundSingle(i); }", 101),
    ('een andere ronde verwijderen',    "() => { const i = loadSavedRounds().findIndex(r => r.id === 102); performDeleteRound(i); }", None),
    ('de lopende ronde zelf verwijderen', "() => { const i = loadSavedRounds().findIndex(r => r.id === 100); performDeleteRound(i); }", None),
    ('een nieuwe ronde starten',        "() => { nav('setup'); document.getElementById('iTime').value = '23:58'; onDateTimeChange(); startRound(); }", None),
    ('een backup terugzetten',          "() => { const l = loadSavedRounds().filter(r => r.id !== 100); doFullRestoreImport(schiftRondes(l).goed, false); }", None),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, js, ander in WEGEN:
            print(f"\n=== {naam.upper()} ===\n")
            pg = await b.new_page(viewport={"width": 390, "height": 844}); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
            await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, rondes()]); await pg.reload(); await pg.wait_for_timeout(700)
            await pg.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
            voorA = await pg.evaluate(OPSLAG, 100); voorB = await pg.evaluate(OPSLAG, 101)
            # één tik op hole 5 van ronde A: de score voorlopig wissen (wacht op bevestiging)
            await pg.evaluate("() => { setCurrentHole(4); armScoreChange(4, null); }")
            await pg.evaluate(js); await pg.wait_for_timeout(300); await pg.evaluate(BEVESTIG)
            await pg.wait_for_timeout(2500)                                   # de wachttijd verloopt
            naA = await pg.evaluate(OPSLAG, 100); naB = await pg.evaluate(OPSLAG, 101)
            check("ronde A heeft haar oude score terug (de wijziging is niet bevestigd)", naA, voorA if naA != 'weg' else 'weg')
            if naA != 'weg': check("  en die is niet leeg gebleven", naA is not None, True)
            check("ronde B is niet veranderd", naB, voorB if naB != 'weg' else 'weg')
            nu = await pg.evaluate("() => game.started ? [game.id, game.holes[4].score] : null")
            if nu and nu[0] != 100:
                bron = await pg.evaluate(OPSLAG, nu[0])
                check("de ronde die nu loopt, heeft geen score van ronde A gekregen", nu[1], bron)
            check("geen fouten, ook niet bij de foutvanger", (pf, await pg.evaluate("document.querySelectorAll('#foutMelding').length")), ([], 0))
            await pg.close()
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
