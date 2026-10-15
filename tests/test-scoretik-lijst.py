"""Een tik op de scorekaart bouwt de rondelijst niet opnieuw op.

Tot 13527DA-113 rekende elke tik op + of − het hele archief door om de (onzichtbare)
rondelijst te verversen. Nu slaat een tik alleen op (bewaarNaTik); de lijst wordt
opgebouwd zodra je de tab Rondes opent.

Wat daarbij NIET mag veranderen:
  * de score staat direct in de opslag;
  * de stip op het tabblad Rondes klopt direct (een score zonder putts geeft een stip);
  * na openen van Rondes is de lijst bij, precies alsof hij per tik was opgebouwd.
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

TEL = """() => { window.__lijst = 0; if (!window.__echtLoadSaved) { window.__echtLoadSaved = loadSaved; window.loadSaved = function () { window.__lijst++; return window.__echtLoadSaved.apply(this, arguments); }; } }"""
STAND = """() => ({ lijst: window.__lijst, stip: document.getElementById('tab-archive').classList.contains('has-dot'), hoortStip: openStaandeMeldingen().length > 0,
  inBeeld: game.holes.map(h => h.score), opslag: JSON.parse(localStorage.getItem('golf_rounds')).find(r => String(r.id) === String(game.id)).holes.map(h => [h.score, h.putts ?? null]) })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        oud = [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(12)]
        await pg.goto(app_url())
        await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
          localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
          localStorage.setItem('golf_last_backup_date', new Date().toISOString()); localStorage.setItem('golf_track_putts', 'on'); }""", [CLUBS, oud])
        await pg.reload(); await pg.wait_for_timeout(600)
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; sel.qualifying = true;
          document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.7'; onHcpBlur(document.getElementById('iHcp'));
          startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); }""")
        await pg.wait_for_timeout(400)
        await pg.evaluate(TEL)
        plus = pg.locator('#screen-score .current-row .plus-cell'); minus = pg.locator('#screen-score .current-row .minus-cell')

        print("\n=== 1. TIKKEN OP DE SCOREKAART ===\n")
        s0 = await pg.evaluate(STAND)
        check("uitgangspunt: lege kaart, geen stip", (s0['inBeeld'][0], s0['stip']), (None, False))
        for knop in (plus, plus, minus, plus):
            await knop.first.click(); await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(2300)          # een voorlopige wijziging laten verlopen
        s = await pg.evaluate(STAND)
        check("de score van hole 1 staat in beeld", s['inBeeld'][0] is not None, True)
        check("en staat in de opslag", s['opslag'][0][0], s['inBeeld'][0])
        check("de rondelijst is daarbij niet opnieuw opgebouwd", s['lijst'], 0)
        check("de stip op het tabblad Rondes klopt met de openstaande meldingen", s['stip'], s['hoortStip'])

        print("\n=== 2. EEN SCORE ZONDER PUTTS GEEFT DIRECT EEN STIP ===\n")
        # Hole 1 heeft putts (bijhouden staat aan). Zet je het bijhouden uit en speel je
        # verder, dan krijgen de volgende holes geen putts: 'met onvolledige putts'.
        await pg.evaluate("() => { stepPutts(0, 1); localStorage.removeItem('golf_track_putts'); game.holes.forEach((h, i) => { if (h.score === null) { setCurrentHole(i); selectHole(i); stepScore(i, 1); } }); }")
        await pg.wait_for_timeout(2600)
        s = await pg.evaluate(STAND)
        check("ook via de functies voor score en putts wordt de lijst niet opgebouwd", s['lijst'], 0)
        check("er hoort nu een stip te staan, en hij staat er", (s['hoortStip'], s['stip']), (True, True))

        print("\n=== 3. ZODRA JE RONDES OPENT IS DE LIJST BIJ ===\n")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => { const voor = document.getElementById('savedList').innerHTML; const n = window.__lijst; window.__echtLoadSaved();
            return { opgebouwd: n, gelijk: voor === document.getElementById('savedList').innerHTML, lengte: voor.length,
                     stip: document.getElementById('tab-archive').classList.contains('has-dot') === (openStaandeMeldingen().length > 0) }; }""")
        check("Rondes openen bouwt de lijst één keer op", r['opgebouwd'], 1)
        check("en die lijst is dezelfde als wanneer je hem nu nog eens opbouwt", (r['gelijk'], r['lengte'] > 1000), (True, True))
        check("de stip klopt", r['stip'], True)

        print("\n=== 4. DE ANDERE PADEN BOUWEN DE LIJST NOG WEL OP ===\n")
        await pg.evaluate("() => { window.__lijst = 0; saveActiveRound(); }")
        check("saveActiveRound() zonder invoer bouwt de lijst op, zoals voorheen", await pg.evaluate("() => window.__lijst"), 1)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
