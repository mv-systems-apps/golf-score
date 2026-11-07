"""Qualifying standaard aan.

De schakelaar 'Qualifying standaard aan' (Instellingen, tabblad WHS; sleutel
golf_qual_standaard, standaard uit). Uit: Qualifying op Start begint uit, zoals altijd. Aan:
na het openen van de app staat Qualifying op Start aan, en een gestarte ronde is
qualifying. Omzetten geldt meteen voor Start. Een wedstrijdlus zet hem uit en een gewone
baan daarna weer aan. Zonder Handicap bijhouden is een nieuwe ronde nooit qualifying.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, kreeg, verwacht):
    if kreeg == verwacht: print(f"  ok   {naam}: {kreeg!r}")
    else: print(f"  FOUT {naam}: {kreeg!r} — verwacht {verwacht!r}"); fouten.append(naam)

START = "() => [!!sel.qualifying, document.getElementById('qualifyToggle1').checked]"

async def herlaad(pg):
    await pg.reload(); await pg.wait_for_timeout(500)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await herlaad(pg)

        print("\n=== 1. STANDAARD UIT ===\n")
        check("de schakelaar staat uit", await pg.evaluate("document.getElementById('qualStandaardToggle').checked"), False)
        check("Start: Qualifying uit", await pg.evaluate(START), [False, False])

        print("\n=== 2. AAN ===\n")
        await pg.evaluate("() => { const c = document.getElementById('qualStandaardToggle'); c.checked = true; c.dispatchEvent(new Event('change')); }")
        check("bewaard als 'on'", await pg.evaluate("localStorage.getItem('golf_qual_standaard')"), 'on')
        check("meteen: Start Qualifying aan", await pg.evaluate(START), [True, True])
        await herlaad(pg)
        await pg.evaluate("nav('settings')")
        check("na herladen: de schakelaar aan", await pg.evaluate("document.getElementById('qualStandaardToggle').checked"), True)
        check("na herladen: Start Qualifying aan", await pg.evaluate(START), [True, True])
        await pg.evaluate("nav('setup')"); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const b = document.getElementById('confirmModalBtn'); if (b && !document.getElementById('confirmModal').classList.contains('hidden')) b.click(); }")
        await pg.wait_for_timeout(300)
        check("de gestarte ronde is qualifying", await pg.evaluate("[!!(game && game.started), !!game.qualifying]"), [True, True])
        await pg.evaluate("() => finishActiveRound()")

        # Een ronde opnieuw plannen houdt zijn eigen keuze, ook als je de schakelaar omzet
        await pg.evaluate("""() => { const s = loadSavedRounds(); const r = s.find(x => isRondeAf(x));
            s.push({ ...r, id: 990050, date: '2030-06-01', time: '10:00', qualifying: false, holes: r.holes.map(h => ({ ...h, score: null })) });
            setRoundsAndMark(JSON.stringify(s)); herplanRonde(990050); }""")
        check("herplannen: de eigen keuze van de ronde (uit)", await pg.evaluate("!!sel.qualifying"), False)
        await pg.evaluate("() => { const c = document.getElementById('qualStandaardToggle'); c.checked = false; c.dispatchEvent(new Event('change')); c.checked = true; c.dispatchEvent(new Event('change')); }")
        check("schakelaar omgezet tijdens herplannen: de ronde houdt zijn keuze", await pg.evaluate("!!sel.qualifying"), False)
        await herlaad(pg)

        print("\n=== 3. WEDSTRIJDLUS EN ZELF UITZETTEN ===\n")
        await pg.evaluate("() => zetQualifyingUitVoorLus()")
        check("een wedstrijdlus: uit", await pg.evaluate(START), [False, False])
        await pg.evaluate("() => herstelQualifyingNaLus()")
        check("weer een gewone baan: aan", await pg.evaluate(START), [True, True])
        await pg.evaluate("() => { const t = document.getElementById('qualifyToggle1'); t.checked = false; t.dispatchEvent(new Event('change')); }")
        check("zelf uitgezet op Start: blijft uit in deze sessie", await pg.evaluate(START), [False, False])
        await herlaad(pg)
        check("na herladen weer de standaard: aan", await pg.evaluate(START), [True, True])

        print("\n=== 4. NA OPSTARTEN OP EEN WEDSTRIJDLUS ===\n")
        # Een club met alleen een lus: Start staat na herladen op die lus. Qualifying blijft
        # dan uit, en een gewone baan daarna krijgt de standaard (aan).
        def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": q, "si": i + 1} for i, q in enumerate(pars)]}
        PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
        lus = {"Club L": {"club": "Club L", "shortName": "L", "courses": {
            "Lus": {"holeIds": [f"L{i}" for i in range(1, 10)], "lus": True, "tees": {"Heren": {"Geel": tee(34.0, 117, PB)}}}}}}
        pg2 = await b.new_page(viewport={'width': 360, 'height': 800})
        await pg2.goto(app_url()); await pg2.evaluate(SEED, [lus, []])
        await pg2.evaluate("() => { localStorage.setItem('golf_default_club', 'Club L'); localStorage.setItem('golf_qual_standaard', 'on'); localStorage.setItem('golf_profile_name', 'Testspeler'); }")
        await herlaad(pg2)
        check("op de lus: Qualifying uit", await pg2.evaluate("[!!(COURSES[sel.track] || {}).lus, !!sel.qualifying, document.getElementById('qualifyToggle1').checked]"), [True, False, False])
        check("en bij een gewone baan komt de standaard terug: aan", await pg2.evaluate("() => { herstelQualifyingNaLus(); return [!!sel.qualifying, !!sel2.qualifying]; }"), [True, True])
        # Op de lus zelf Qualifying aan en weer uit (dat wist de onthouden keuze), dan de
        # standaard uit en weer aan: de lus blijft uit, een gewone baan krijgt aan.
        await herlaad(pg2)
        await pg2.evaluate("""() => { const t = document.getElementById('qualifyToggle1'); t.checked = true; t.dispatchEvent(new Event('change'));
            t.checked = false; t.dispatchEvent(new Event('change'));
            const c = document.getElementById('qualStandaardToggle'); c.checked = false; c.dispatchEvent(new Event('change'));
            c.checked = true; c.dispatchEvent(new Event('change')); }""")
        check("schakelaars omgezet op de lus: de lus blijft uit", await pg2.evaluate("[!!(COURSES[sel.track] || {}).lus, !!sel.qualifying]"), [True, False])
        check("en een gewone baan daarna: aan", await pg2.evaluate("() => { herstelQualifyingNaLus(); return !!sel.qualifying; }"), True)
        await pg2.close()

        print("\n=== 5. ZONDER HANDICAP BIJHOUDEN ===\n")
        await pg.evaluate("() => localStorage.setItem('golf_whs_volgen', 'off')"); await herlaad(pg)
        check("nooit qualifying, ook met de schakelaar aan", await pg.evaluate("[!!sel.qualifying, qualifyingStandaardAan()]"), [False, False])
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ", ".join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
