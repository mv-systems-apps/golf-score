"""Een opslagstoring gevolgd door een handeling die het spel uit het geheugen haalt.

test-opslagstoring.py bewijst dat scores tijdens een storing in beeld blijven en later
alsnog worden weggeschreven. Drie handelingen braken die belofte, omdat ze het geheugen
leegmaken of vervangen zonder te kijken of het opslaan gelukt was:

  1. afronden ("Gereed") en opslaan vanaf de rondekaart;
  2. wisselen van speler;
  3. corrigeren met twee spelers, als alleen de schrijfactie van speler 2 mislukt.

De regel: geen handeling mag ingevulde scores weghalen of vervangen nadat de opslag die
eraan voorafgaat is mislukt. De handeling gaat dan niet door, en dat wordt gemeld.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, app_url

fouten = []
def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam); print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")

# welke: 0 = elke schrijfactie van de rondes mislukt; n = alleen de n-de.
STORING = """(welke) => { window.__echt = window.__echt || Storage.prototype.setItem; window.__n = 0;
  Storage.prototype.setItem = function (k, v) {
    if (k === 'golf_rounds') { window.__n++; if (welke === 0 || welke === window.__n) { const e = new Error('vol'); e.name = 'QuotaExceededError'; throw e; } }
    return window.__echt.call(this, k, v); }; }"""
HERSTEL = "() => { Storage.prototype.setItem = window.__echt; }"
START = """(twee) => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.qualifying = true;
  document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.7';
  onHcpBlur(document.getElementById('iHcp'));
  if (twee) { if (!player2Visible) togglePlayer2(); document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = '18'; sel2.tee = 'Geel'; sel2._teeUserSelected = true; }
  startRound(); const cb = document.getElementById('confirmModalBtn');
  if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); }"""
SCORES = "(a) => { for (let h = a[0]; h < a[1]; h++) { setCurrentHole(h); selectHole(h); armScoreChange(h, a[2]); clearScoreTap(false); } }"
STAND = """() => { const m = document.getElementById('confirmModal'); const zicht = m && !m.classList.contains('hidden');
  const uit = { gestart: !!game.started, inBeeld: (game.holes || []).filter(h => h.score !== null).length, speler: activePlayer,
    actiefId: localStorage.getItem('golf_active_id'), id2: localStorage.getItem('golf_game2_id'),
    melding: zicht ? m.innerText.replace(/\\s+/g, ' ').trim() : '',
    opslag: JSON.parse(localStorage.getItem('golf_rounds') || '[]').map(r => [r.player, r.tee, r.holes.filter(h => h.score !== null).length, String(r.id)]) };
  if (zicht) document.getElementById('confirmModalBtn').click();
  return uit; }"""
def per_speler(stand): return sorted([p, n] for p, t, n, i in stand['opslag'])

async def vers(browser):
    page = await browser.new_page(viewport={"width": 390, "height": 844})
    page.fouten = []
    page.on('pageerror', lambda e: page.fouten.append(str(e)[:160]))
    await page.goto(app_url())
    await page.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", CLUBS)
    await page.reload(); await page.wait_for_timeout(700)
    return page

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pf = []

        print("\n=== 1. AFRONDEN TIJDENS EEN STORING ===\n")
        pg = await vers(b); await pg.evaluate(START, False); await pg.evaluate(SCORES, [0, 2, 5]); await pg.wait_for_timeout(300)
        await pg.evaluate(STORING, 0); await pg.evaluate(SCORES, [2, 9, 5]); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND)
        check("uitgangspunt: negen holes in beeld, twee opgeslagen", (s['inBeeld'], per_speler(s)), (9, [['Testspeler', 2]]))
        await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("Gereed: het spel blijft staan met alle negen holes", (s['gestart'], s['inBeeld']), (True, 9))
        check("de ronde blijft de lopende ronde", s['actiefId'] is not None, True)
        check("en het wordt gemeld", 'niet' in s['melding'].lower() and 'opgeslagen' in s['melding'].lower(), True)
        await pg.evaluate(HERSTEL); await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND)
        check("werkt de opslag weer, dan rondt Gereed af met negen holes in de opslag", (s['gestart'], s['actiefId'], per_speler(s)), (False, None, [['Testspeler', 9]]))
        pf += pg.fouten

        print("\n=== 1b. OPSLAAN VANAF DE RONDEKAART TIJDENS EEN STORING ===\n")
        pg = await vers(b); await pg.evaluate(START, False); await pg.evaluate(SCORES, [0, 2, 5]); await pg.wait_for_timeout(300)
        await pg.evaluate(STORING, 0); await pg.evaluate(SCORES, [2, 9, 5])
        KAART = "() => { const k = document.createElement('button'); k.dataset.roundId = String(game.id); k.dataset.confirm = '1'; document.body.appendChild(k); saveAndClearActiveRound(k); k.remove(); }"
        await pg.evaluate(KAART); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("het spel blijft staan met alle negen holes", (s['gestart'], s['inBeeld'], s['actiefId'] is not None), (True, 9, True))
        check("en het wordt gemeld", 'niet' in s['melding'].lower() and 'opgeslagen' in s['melding'].lower(), True)
        await pg.evaluate(HERSTEL); await pg.evaluate(KAART); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND)
        check("werkt de opslag weer, dan staan er negen holes in de opslag", (s['gestart'], per_speler(s)), (False, [['Testspeler', 9]]))
        pf += pg.fouten

        print("\n=== 2. WISSELEN VAN SPELER TIJDENS EEN STORING ===\n")
        pg = await vers(b); await pg.evaluate(START, True); await pg.evaluate(SCORES, [0, 2, 4]); await pg.wait_for_timeout(300)
        await pg.evaluate(STORING, 0); await pg.evaluate(SCORES, [2, 6, 4])
        await pg.evaluate("() => switchToPlayer(2)"); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("naar speler 2: er wordt niet gewisseld, speler 1 houdt zes holes", (s['speler'], s['inBeeld']), (1, 6))
        check("en het wordt gemeld", 'niet' in s['melding'].lower() and 'opgeslagen' in s['melding'].lower(), True)
        await pg.evaluate(HERSTEL); await pg.evaluate("() => switchToPlayer(2)"); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("werkt de opslag weer, dan lukt de wissel en staan de zes holes in de opslag", (s['speler'], per_speler(s)), (2, [['Partner', 0], ['Testspeler', 6]]))
        await pg.evaluate(STORING, 0); await pg.evaluate(SCORES, [0, 3, 6])
        await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("terug naar speler 1: er wordt niet gewisseld, speler 2 houdt drie holes", (s['speler'], s['inBeeld']), (2, 3))
        check("en het wordt gemeld", 'niet' in s['melding'].lower() and 'opgeslagen' in s['melding'].lower(), True)
        await pg.evaluate(HERSTEL); await pg.evaluate("() => switchToPlayer(1)"); await pg.wait_for_timeout(200)
        s = await pg.evaluate(STAND)
        check("werkt de opslag weer: speler 1 zes holes in beeld, beide kaarten compleet in de opslag", (s['speler'], s['inBeeld'], per_speler(s)), (1, 6, [['Partner', 3], ['Testspeler', 6]]))
        pf += pg.fouten

        print("\n=== 3. CORRIGEREN MET TWEE SPELERS, ALLEEN DE RONDE VAN SPELER 2 MISLUKT ===\n")
        pg = await vers(b); await pg.evaluate(START, True); await pg.evaluate(SCORES, [0, 9, 4])
        await pg.evaluate("() => switchToPlayer(2)"); await pg.evaluate(SCORES, [0, 9, 6]); await pg.evaluate("() => switchToPlayer(1)")
        await pg.evaluate("() => finishActiveRound(null)"); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND)
        check("uitgangspunt: beide spelers negen holes", per_speler(s), [['Partner', 9], ['Testspeler', 9]])
        await pg.evaluate("""() => { const mijn = loadSavedRounds().find(r => r.player === 'Testspeler'); corrigeerRonde(String(mijn.id)); document.getElementById('keuzeModalKnop2').click(); sel.tee = 'Geel'; sel._teeUserSelected = true; rebuildAll(); }""")
        await pg.wait_for_timeout(200)
        await pg.evaluate(STORING, 2)
        await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(300)
        s = await pg.evaluate(STAND); await pg.evaluate(HERSTEL)
        check("de negen holes van speler 2 staan nog in de opslag", [n for p_, n in per_speler(s) if p_ == 'Partner'], [9])
        check("de gecorrigeerde ronde van speler 1 staat er, op de nieuwe tee", [[t, n] for p_, t, n, i in s['opslag'] if p_ == 'Testspeler'], [['Geel', 9]])
        check("de verwijzing naar speler 2 wijst niet naar een ronde die niet bestaat", s['id2'] is None or s['id2'] in [i for p_, t, n, i in s['opslag']], True)
        check("en het wordt gemeld", 'speler 2' in s['melding'].lower() or 'partner' in s['melding'].lower(), True)
        pf += pg.fouten

        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
