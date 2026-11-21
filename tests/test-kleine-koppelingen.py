"""Vijf kleine koppelingen tussen scherm en gegevens (bevinding 15c t/m g).

c. Na het afronden van een ronde met twee spelers: wat Start laat zien en wat een
   nieuwe ronde doet, horen hetzelfde te zijn.
d. Een nieuwe club waar je nog geen naam aan gaf, hoort niet in de opslag te staan.
e. Een knop op een rondekaart hoort altijd de ronde te raken die op die kaart staat, ook
   als een ander tabblad intussen een ronde heeft verwijderd.
f. De opgeslagen tee en het geslacht horen bij de CR en SR waarmee gerekend is.
g. De ronde krijgt de datum en tijd die op Start in beeld staan.
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

ZET = """([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
  localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7');
  localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString()); }"""
DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"
RONDES = "() => JSON.parse(localStorage.getItem('golf_rounds'))"
BEVESTIG = "() => { const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"

async def verse(ctx, rondes=()):
    pg = await ctx.new_page(); await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, list(rondes)])
    await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate(DICHT); await pg.click('#tab-setup'); await pg.wait_for_timeout(200)
    return pg
async def vul_naam(pg):
    await pg.fill('#iName', 'Testspeler'); await pg.fill('#iHcp', '30.7'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(150); await pg.evaluate(DICHT)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})

        print("\n=== c. NA EEN RONDE MET TWEE SPELERS ===\n")
        pg = await verse(ctx); await vul_naam(pg)
        await pg.evaluate("togglePlayer2()"); await pg.wait_for_timeout(200)
        await pg.fill('#iName2', 'Anna'); await pg.fill('#iHcp2', '20.0'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(150)
        await pg.evaluate("() => { startRound(); }"); await pg.wait_for_timeout(300); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(400)
        check("twee rondes gestart", len(await pg.evaluate(RONDES)), 2)
        await pg.evaluate("""() => { const l = loadSavedRounds(); l.forEach(r => r.holes.forEach(h => { h.score = h.par + 1; })); setRoundsAndMark(JSON.stringify(l));
            game.holes.forEach(h => { h.score = h.par + 1; }); finishActiveRound(null); }"""); await pg.wait_for_timeout(500)
        await pg.evaluate(DICHT); await pg.click('#tab-setup'); await pg.wait_for_timeout(300)
        s = await pg.evaluate("() => ({ kaart: !document.getElementById('player2Card').classList.contains('hidden') && document.getElementById('player2Card').offsetParent !== null, intern: player2Visible, opslag: localStorage.getItem('golf_player2_visible') })")
        check("wat Start toont, wat de app denkt en wat bewaard is, zijn gelijk", (s['kaart'], s['intern'], s['opslag'] == '1'), (s['kaart'],) * 3)
        await pg.evaluate("() => { document.getElementById('iTime').value = '23:58'; onDateTimeChange(); startRound(); }"); await pg.wait_for_timeout(300); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(400)
        nieuw = len(await pg.evaluate(RONDES)) - 2
        check("een nieuwe ronde start voor zoveel spelers als Start laat zien", nieuw, 2 if s['kaart'] else 1)
        await pg.close()

        print("\n=== d. EEN NIEUWE CLUB ZONDER NAAM ===\n")
        pg = await verse(ctx); await pg.click('#tab-club'); await pg.wait_for_timeout(200)
        await pg.click('button[onclick="createNewClub()"]'); await pg.wait_for_timeout(300)
        check("met de editor open staat de naamloze club niet in de opslag", [k for k in json.loads(await pg.evaluate("localStorage.getItem('golf_clubs')")) if k.startswith('__nieuw__')], [])
        await pg.reload(); await pg.wait_for_timeout(600)
        check("na sluiten en opnieuw openen is er geen naamloze club", await pg.evaluate("Object.keys(CLUBS).filter(k => k.startsWith('__nieuw__') || !CLUBS[k].club)"), [])
        await pg.evaluate("(c) => { c['__nieuw__123'] = { club: '', shortName: '', courses: {} }; localStorage.setItem('golf_clubs', JSON.stringify(c)); }", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600)
        check("een naamloze club uit een eerdere versie wordt bij het laden opgeruimd", (await pg.evaluate("Object.keys(CLUBS).length"), await pg.evaluate("clubsOnleesbaar")), (len(CLUBS), False))
        await pg.evaluate("document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))")
        await pg.close()

        print("\n=== d2. NAAMLOZE CLUB MET BANEN, EN ALLES WISSEN ===\n")
        pg = await verse(ctx)
        await pg.evaluate("(c) => { CLUBS['__nieuw__9'] = { club: '', shortName: '', courses: { Proef: JSON.parse(JSON.stringify(c['Golfclub Heelsum'].courses.Airborne)) } }; saveClubsToStorage(); }", CLUBS)
        check("een naamloze club waar al een baan in staat, wordt wel bewaard (anders ben je de baan kwijt)", '__nieuw__9' in json.loads(await pg.evaluate("localStorage.getItem('golf_clubs')")), True)
        await pg.evaluate("localStorage.setItem('golf_fouten', JSON.stringify(['proef']))")
        await pg.evaluate("() => doResetAll()"); await pg.wait_for_timeout(600)
        check("'Alles wissen' wist ook de lijst met laatste fouten", await pg.evaluate("localStorage.getItem('golf_fouten')"), None)
        await pg.close()

        print("\n=== e. EEN KNOP RAAKT DE RONDE OP ZIJN EIGEN KAART ===\n")
        oud = [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(5)]
        A = await verse(ctx, oud); await A.click('#tab-archive'); await A.wait_for_timeout(300)
        doel = await A.evaluate("""() => { const k = document.querySelector('#savedList [onclick^="openExportModal("]'); const i = +k.getAttribute('onclick').match(/\\((\\d+)/)[1]; window.__knop = k; return loadSavedRounds()[i].date; }""")
        B = await ctx.new_page(); await B.goto(app_url()); await B.wait_for_timeout(500)
        await B.evaluate("() => { const l = loadSavedRounds(); l.splice(0, 1); metVerwijderen(() => setRoundsAndMark(JSON.stringify(l))); }"); await B.wait_for_timeout(300); await B.close()
        await A.wait_for_timeout(300); await A.evaluate(DICHT)
        # de kaart van die ronde staat nog bovenaan; tik op de knop die er NU staat
        await A.evaluate("document.querySelector('#savedList [onclick^=\"openExportModal(\"]').click()"); await A.wait_for_timeout(200)
        raakt = await A.evaluate("(loadSavedRounds()[_exportModalIdx] || {}).date")
        check("de knop op de kaart opent de ronde van die kaart, niet een buurman", raakt, doel)
        await A.close()

        print("\n=== f. TEE EN GESLACHT HOREN BIJ DE GEBRUIKTE CR EN SR ===\n")
        pg = await verse(ctx); await vul_naam(pg)
        await pg.evaluate("() => { sel.track = 'Airborne'; sel.gender = 'Dames'; sel.tee = 'Rood'; sel._teeUserSelected = true; rebuildStartScreen(); }"); await pg.wait_for_timeout(200)
        await pg.locator('.track-btn', has_text='Sandr').first.click(); await pg.wait_for_timeout(300)     # Sandr heeft alleen Heren Blauw
        await pg.evaluate("() => { startRound(); }"); await pg.wait_for_timeout(300); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(400)
        r = (await pg.evaluate(RONDES))[0]
        echt = CLUBS['Golfclub Heelsum']['courses'][r['track']]['tees'].get(r['gender'], {}).get(r['tee'])
        check("de opgeslagen tee bestaat op die baan, met dezelfde CR en SR", (r['track'], bool(echt), echt and (echt['CR'], echt['SR'])), ('Sandr', True, (r['CR'], r['SR'])))
        await pg.close()

        print("\n=== g. DE RONDE KRIJGT DE DATUM EN TIJD DIE IN BEELD STAAN ===\n")
        ctx2 = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx2.new_page(); await pg.clock.install(time="2026-06-10T09:00:00")
        await pg.goto(app_url()); await pg.evaluate(ZET, [CLUBS, []]); await pg.reload(); await pg.wait_for_timeout(600); await pg.evaluate(DICHT); await pg.click('#tab-setup')
        await vul_naam(pg)
        await pg.clock.fast_forward("07:00")                                   # zeven minuten later tik je op Start
        beeld = await pg.evaluate("[document.getElementById('iDate').value, document.getElementById('iTime').value]")
        await pg.evaluate("() => { startRound(); }"); await pg.wait_for_timeout(300); await pg.evaluate(BEVESTIG); await pg.wait_for_timeout(400)
        r = (await pg.evaluate(RONDES))[0]
        check("datum en tijd van de ronde zijn wat op Start stond", [r['date'], r['time']], beeld)
        await ctx2.close(); await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
