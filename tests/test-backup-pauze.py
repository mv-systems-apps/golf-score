"""Na een backup blijft de backupmelding stil bij starten, invullen en pauzeren.

Aanleiding (Marks melding): een gepauzeerde ronde gaf een backupsignaal, terwijl alleen
afgeronde rondes in de backup horen. Oorzaak: een backup legde niet vast WAT erin zat
(de vingerafdruk). Liep die al achter, dan bleef hij achterlopen, en de eerstvolgende
opslag van de rondelijst — het starten van een ronde — zag een 'wijziging' die er niet
was.

Daarom begint elke proef met een bewust verouderde vingerafdruk, en daarna een echte
backup (of een volledig herstel). Een ronde wordt gestart, er worden holes ingevuld en
hij wordt gepauzeerd met de echte knop in Rondes — bij één en bij twee spelers.
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

STAND = """() => {
  nav('settings'); updateLastBackupDisplay();
  const r = document.getElementById('newRoundsInfoTop');
  return {
    regel: r.classList.contains('hidden') ? 'geen' : (r.innerHTML.includes('--orange') ? 'oranje' : 'grijs'),
    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
  };
}"""

async def proef(page, twee, via):
    await page.goto(app_url()); await page.evaluate(SEED, [CLUBS, RONDES])
    await page.evaluate("""() => { localStorage.setItem('golf_profile_name', 'Mark');
        localStorage.setItem('golf_kenmerk_gevraagd', '1');
        localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_backup_reminder_days', '1');
        localStorage.setItem('golf_backup_reminder_rounds', '1'); }""")
    await page.reload(); await page.wait_for_timeout(500)
    # Verouderde vingerafdruk, zoals na een eerdere afronding zonder stempel.
    await page.evaluate("() => localStorage.setItem('golf_backup_fingerprint', 'verouderd')")
    if via == 'backup':
        await page.evaluate("async () => { await exportAllClubs(); await exportAllRounds(); }")
    else:
        await page.evaluate("""async () => { await exportAllClubs();
            doFullRestoreImport(JSON.parse(JSON.stringify(loadSavedRounds()))); }""")
    await page.wait_for_timeout(300)
    s = await page.evaluate(STAND)
    check(f"na de {via}: niets te melden", (s['regel'], s['stip']), ('geen', False))

    await page.evaluate("""(twee) => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren';
        sel.tee = 'Blauw'; sel.qualifying = true;
        document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.7';
        if (twee) togglePlayer2(true); }""", twee)
    await page.wait_for_timeout(250)
    await page.evaluate("""(twee) => { if (twee) {
            document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = '18.0';
            sel2.track = 'Airborne'; sel2.gender = 'Heren'; sel2.tee = 'Blauw'; sel2.qualifying = true; }
        startRound(); const cb = document.getElementById('confirmModalBtn');
        if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""", twee)
    await page.wait_for_timeout(400)
    check("de ronde loopt", await page.evaluate("() => !!game.started"), True)
    s = await page.evaluate(STAND)
    check("na starten: niets te melden", (s['regel'], s['stip']), ('geen', False))

    await page.evaluate("() => { nav('score'); renderScore(); }"); await page.wait_for_timeout(200)
    for spelers in ([1, 2] if twee else [1]):
        if twee: await page.evaluate("(n) => switchToPlayer(n)", spelers); await page.wait_for_timeout(200)
        for h in range(3):
            await page.evaluate("""(h) => { setCurrentHole(h); selectHole(h); toggleScoreButtons(h);
                armScoreChange(h, 5); clearScoreTap(false); }""", h)
            await page.wait_for_timeout(70)
    if twee: await page.evaluate("() => switchToPlayer(1)"); await page.wait_for_timeout(200)
    s = await page.evaluate(STAND)
    check("3 holes ingevuld: niets te melden", (s['regel'], s['stip']), ('geen', False))

    await page.evaluate("() => nav('archive')"); await page.wait_for_timeout(300)
    knop = page.locator('button[onclick^="saveAndClearActiveRound"]').first
    check("de knop is 'Pauzeren'", await knop.get_attribute('title'), 'Pauzeren')
    await knop.click(); await page.wait_for_timeout(100)
    await knop.click(); await page.wait_for_timeout(300)
    s = await page.evaluate(STAND)
    check("gepauzeerd: niets te melden", (s['regel'], s['stip']), ('geen', False))
    await page.reload(); await page.wait_for_timeout(500)
    s = await page.evaluate(STAND)
    check("na herladen: nog steeds niets", (s['regel'], s['stip']), ('geen', False))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 844})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)[:120]))
        for twee, via, kop in [(False, 'backup', '1. ÉÉN SPELER, NA EEN BACKUP'),
                               (True, 'backup', '2. TWEE SPELERS, NA EEN BACKUP'),
                               (False, 'herstel', '3. ÉÉN SPELER, NA VOLLEDIG HERSTELLEN')]:
            print(f"\n=== {kop} ===\n")
            await proef(page, twee, via)
        check("geen fouten in de pagina", paginafouten, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
