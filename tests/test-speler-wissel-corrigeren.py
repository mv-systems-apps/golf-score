"""Drie plekken waar het scherm en de gegevens uit elkaar konden lopen.

  1. CORRIGEREN VAN EEN RONDE VAN EEN ANDER. De naam bovenin Start bepaalt wiens handicap
     en statistieken de app toont. Corrigeren (of herplannen) zet daar de speler en de
     handicap van die ronde neer. Annuleerde je, of rondde je de correctie af, dan bleef
     die naam staan: de app dacht dat jij de gast was, tot je herlaadde.
  2. EEN WACHTENDE SCOREWIJZIGING EN EEN SPELERWISSEL. Een gewijzigde score staat twee
     seconden in de wacht. Wisselde je binnen die tijd van speler, dan kwam de oude score
     van speler 1 op dezelfde hole van speler 2 terecht.
  3. STABLEFORD VAN SPELER 2 NA CORRIGEREN. De nieuwe ronde van speler 2 kreeg zijn
     scores terug, maar zijn Stableford-totaal bleef op 0 staan.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

WIE = "() => [startPlayerName(), document.getElementById('iHcp').value, localStorage.getItem('golf_profile_name'), localStorage.getItem('golf_profile_hcp')]"
START = """(twee) => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.qualifying = true;
  document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.7'; onHcpBlur(document.getElementById('iHcp'));
  if (twee) { if (!player2Visible) togglePlayer2(); document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = '18'; sel2.tee = 'Geel'; sel2._teeUserSelected = true; }
  startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); }"""
SCORES = "(a) => { for (let h = a[0]; h < a[1]; h++) { setCurrentHole(h); selectHole(h); armScoreChange(h, a[2]); clearScoreTap(false); } }"
BEVESTIG = "() => { for (let k = 0; k < 3; k++) { const m = document.getElementById('confirmModal'); if (m && !m.classList.contains('hidden')) document.getElementById('confirmModalBtn').click(); } }"

async def vers(b, rondes):
    pg = await b.new_page(viewport={"width": 390, "height": 844})
    pg.fouten = []; pg.on('pageerror', lambda e: pg.fouten.append(str(e)[:140]))
    await pg.goto(app_url())
    await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", [CLUBS, rondes])
    await pg.reload(); await pg.wait_for_timeout(700)
    return pg

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pf = []

        print("\n=== 1. CORRIGEREN VAN EEN RONDE VAN EEN ANDER ===\n")
        R = [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(5)]
        gast = ronde(99, "2026-06-01"); gast['player'] = 'Gast'; gast['hcp'] = 12.3; R.append(gast)
        oud = ronde(98, "2026-03-01"); oud['hcp'] = 34.5; R.append(oud)
        pg = await vers(b, R)
        voor = await pg.evaluate(WIE)
        check("uitgangspunt: Testspeler met 30.7", voor, ['Testspeler', '30.7', 'Testspeler', '30.7'])
        await pg.evaluate("() => herplanRonde(99, true)"); await pg.wait_for_timeout(300)
        check("tijdens het corrigeren staat de gast bovenin (zo wordt zijn ronde opgebouwd)", (await pg.evaluate(WIE))[:2], ['Gast', '12.3'])
        await pg.locator('#herplanBanner button').click(); await pg.wait_for_timeout(300)
        check("annuleren via het kruisje: Testspeler en zijn handicap staan er weer", await pg.evaluate(WIE), voor)
        await pg.evaluate("() => herplanRonde(98, true)"); await pg.wait_for_timeout(300)
        check("een oude eigen ronde corrigeren toont de handicap van toen", (await pg.evaluate(WIE))[:2], ['Testspeler', '34.5'])
        await pg.locator('#herplanBanner button').click(); await pg.wait_for_timeout(300)
        check("annuleren: de handicap van nu staat er weer", await pg.evaluate(WIE), voor)
        await pg.evaluate("() => herplanRonde(99, true)"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { startRound(); }"); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(500)
        na = await pg.evaluate("() => ({ wie: " + WIE[6:] + ", ronde: [game.started, game.player, game.hcp], gast: leesRondes().filter(r => r.player === 'Gast').length })")
        check("de correctie afronden: de ronde is van de gast, met zijn handicap", (na['ronde'], na['gast']), ([True, 'Gast', 12.3], 1))
        check("en bovenin Start staat daarna weer Testspeler, ook in het bewaarde profiel", na['wie'], voor)
        await pg.reload(); await pg.wait_for_timeout(600)
        check("na herladen nog steeds Testspeler", (await pg.evaluate(WIE))[0], 'Testspeler')
        pf += pg.fouten; await pg.close()

        print("\n=== 2. EEN WACHTENDE SCOREWIJZIGING EN EEN SPELERWISSEL ===\n")
        pg = await vers(b, [])
        await pg.evaluate(START, True); await pg.evaluate(SCORES, [0, 3, 5]); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { setCurrentHole(1); selectHole(1); armScoreChange(1, 8); switchToPlayer(2); }")   # 8 staat in de wacht
        await pg.wait_for_timeout(2600)
        s = await pg.evaluate("() => { const l = JSON.parse(localStorage.getItem('golf_rounds')); const van = n => l.find(r => r.player === n).holes.slice(0, 3).map(h => h.score); return { speler: activePlayer, inBeeld: game.holes.slice(0, 3).map(h => h.score), testspeler: van('Testspeler'), partner: van('Partner') }; }")
        check("er is gewisseld naar speler 2, en zijn kaart is nog leeg", (s['speler'], s['inBeeld'], s['partner']), (2, [None, None, None], [None, None, None]))
        check("de niet-bevestigde 8 van speler 1 is vervallen: hole 2 is weer 5", s['testspeler'], [5, 5, 5])
        await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { setCurrentHole(2); selectHole(2); armScoreChange(2, 9); finishActiveRound(null); }")
        await pg.wait_for_timeout(2600)
        s = await pg.evaluate("() => ({ gestart: !!game.started, testspeler: JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.player === 'Testspeler').holes.slice(0, 3).map(h => h.score) })")
        check("afronden met een wijziging in de wacht: de ronde is afgerond, hole 3 is weer 5", (s['gestart'], s['testspeler']), (False, [5, 5, 5]))
        check("geen fouten in de pagina", pg.fouten, [])
        pf += pg.fouten; await pg.close()

        print("\n=== 3. STABLEFORD VAN SPELER 2 NA CORRIGEREN ===\n")
        pg = await vers(b, [])
        await pg.evaluate(START, True); await pg.evaluate(SCORES, [0, 9, 4])
        await pg.evaluate("() => switchToPlayer(2)"); await pg.evaluate(SCORES, [0, 9, 6]); await pg.evaluate("() => switchToPlayer(1)")
        await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(300)
        STB = "() => leesRondes().map(r => [r.player, 'totalStb' in r, r.holes.reduce((s, h) => s + stbFor(h), 0), 'playedCount' in r]).sort()"
        voor = await pg.evaluate(STB)
        check("uitgangspunt: beide rondes gespeeld, en het Stableford-totaal staat niet in de opslag (het wordt uit de holes berekend)", [(v[1], v[2] > 0) for v in voor], [(False, True), (False, True)])
        await pg.evaluate("() => { const mijn = loadSavedRounds().find(r => r.player === 'Testspeler'); corrigeerRonde(String(mijn.id)); document.getElementById('keuzeModalKnop2').click(); }"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { startRound(); }"); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(500)
        na = await pg.evaluate(STB)
        check("na corrigeren (zelfde tee): geen opgeslagen totaal, en de som over de holes", [(v[0], v[1]) for v in na], [('Partner', False), ('Testspeler', False)])
        check("en die som is gelijk aan die van vóór het corrigeren", [(v[0], v[2]) for v in na], [(v[0], v[2]) for v in voor])
        check("het oude hulpveld playedCount staat nergens in de opslag", [v[3] for v in na], [False, False])
        pf += pg.fouten; await pg.close()

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
