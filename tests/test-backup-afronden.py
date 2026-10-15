"""Backupmelding volgt de drempels, ook na het AFRONDEN van een ronde.

Sinds 10B wacht de melding tot de ronde is afgerond (Marks keuze), ook als alle holes al
zijn ingevuld; het backupbestand neemt een volle open ronde wel mee.

Aanleiding (Marks melding): backup 5 dagen geleden, drempels op 1 dag en 1 wijziging,
een nieuwe ronde gespeeld — en toch een GRIJZE regel en geen stip. Oorzaak: de ronde
die je speelt zit niet in de backup; bij het afronden werd hij alleen losgelaten als
actieve ronde, zonder dat de rondelijst opnieuw werd geschreven. Dan kwam er geen
wijzigingsstempel, en de controle voor oranje keek alleen naar dat stempel.

Gecontroleerd via de ECHTE routes: een actieve ronde wordt bij het laden hersteld,
en daarna afgerond met finishActiveRound, saveAndClearActiveRound of clearActiveRound.
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

# Backup van 5 dagen geleden, alles veilig. Daarna een ronde als ACTIEVE ronde in de
# lijst zetten (zoals saveActiveRound dat doet) en de pagina herladen, zodat de app hem
# zelf als lopende ronde herstelt. compleet=False: de ronde is nog niet uitgespeeld.
OPZET = """async ([compleet, dagenDrempel, rondesDrempel]) => {
  localStorage.setItem('golf_backup_reminder_days', String(dagenDrempel));
  localStorage.setItem('golf_backup_reminder_rounds', String(rondesDrempel));
  await exportAllClubs();                       // clubs veilig: de stip gaat alleen over rondes
  // Eerst de backup (vóór het spelen), dan pas de ronde. Sinds 0EF telt een helemaal
  // ingevulde ronde ook mee als hij open staat; een backup ná het klaarzetten zou hem
  // dus al bevatten.
  const d = new Date(); d.setDate(d.getDate() - 5);
  const dISO = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  localStorage.setItem('golf_last_backup_date', dISO);
  localStorage.setItem('golf_last_backup_ts', d.toISOString());
  legBackupInhoudVast();
  const lijst = loadSavedRounds();
  const basis = lijst.find(r => (r.holes || []).length && r.holes.every(h => h.score !== null));
  const nieuw = { ...basis, id: 990001, date: todayISO(), time: '07:00',
                  holes: basis.holes.map((h, i) => ({ ...h, score: (compleet || i < 3) ? h.score : null })) };
  localStorage.setItem('golf_active_id', '990001');
  lijst.unshift(nieuw);
  metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
}"""

STAND = """() => {
  nav('settings'); updateLastBackupDisplay();
  const regel = document.getElementById('newRoundsInfoTop');
  return {
    actief: !!localStorage.getItem('golf_active_id'),
    regel: regel.classList.contains('hidden') ? 'geen' :
           (regel.innerHTML.includes('--orange') ? 'oranje' : 'grijs'),
    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
  };
}"""

async def opzetten(page, compleet=True, dagen=1, rondes=1):
    await page.goto(app_url()); await page.evaluate(SEED, [CLUBS, RONDES])
    await page.reload(); await page.wait_for_timeout(500)
    await page.evaluate(OPZET, [compleet, dagen, rondes])
    await page.reload(); await page.wait_for_timeout(600)
    return await page.evaluate("() => ({ hersteld: game.started === true && String(game.id) === '990001' })")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 780})
        pagina_fouten = []
        page.on('pageerror', lambda e: pagina_fouten.append(str(e)[:120]))

        print("\n=== 1. MARKS SITUATIE: AFRONDEN MET DE KNOP ===\n")
        h = await opzetten(page)
        check("de ronde loopt na herladen", h['hersteld'], True)
        s = await page.evaluate(STAND)
        # Sinds 10B (Marks keuze): de melding wacht tot de ronde is afgerond, ook als alle
        # holes al zijn ingevuld. Het backupbestand neemt hem wel al mee.
        check("alle holes ingevuld, nog open: nog geen melding",
              (s['regel'], s['stip']), ('geen', False))
        await page.evaluate("() => finishActiveRound(null)")
        await page.wait_for_timeout(150)
        s = await page.evaluate(STAND)
        check("afgerond: geen actieve ronde meer", s['actief'], False)
        check("drempel 1 dag / 1 ronde gehaald: oranje", s['regel'], 'oranje')
        check("en de stip op het tandwiel", s['stip'], True)

        print("\n=== 2. AFRONDEN VIA 'OPSLAAN EN SLUITEN' IN RONDES ===\n")
        await opzetten(page)
        # De echte knop in Rondes, twee tikken (de tweede bevestigt).
        await page.evaluate("() => nav('archive')")
        await page.wait_for_timeout(300)
        knop = page.locator('button[data-round-id="990001"][onclick^="saveAndClearActiveRound"]').first
        check("de knop 'Gereed' staat in Rondes", await knop.count() > 0, True)
        await knop.click(); await page.wait_for_timeout(100)
        await knop.click(); await page.wait_for_timeout(250)
        s = await page.evaluate(STAND)
        check("oranje", s['regel'], 'oranje')
        check("stip", s['stip'], True)

        print("\n=== 3. AFRONDEN VIA clearActiveRound ===\n")
        await opzetten(page)
        await page.evaluate("() => clearActiveRound()")
        await page.wait_for_timeout(150)
        s = await page.evaluate(STAND)
        check("oranje", s['regel'], 'oranje')
        check("stip", s['stip'], True)

        print("\n=== 4. EEN ONAFGEMAAKTE RONDE LOSLATEN GEEFT GEEN MELDING ===\n")
        await opzetten(page, compleet=False)
        await page.evaluate("() => clearActiveRound()")
        await page.wait_for_timeout(150)
        s = await page.evaluate(STAND)
        check("geen regel (niets nieuws in de backup)", s['regel'], 'geen')
        check("geen stip", s['stip'], False)
        check("en niets veranderd ten opzichte van de backup",
              await page.evaluate("() => backupVerschil().totaal"), 0)

        print("\n=== 5. VASTE REGEL: OOK MET OUDE DREMPELWAARDEN IN DE OPSLAG ORANJE ===\n")
        # De drempels zijn vervallen. Staan er nog waarden van vroeger in de opslag (hier
        # 30 dagen / 2 rondes, die vroeger grijs gaven), dan tellen die niet meer mee.
        await opzetten(page, dagen=30, rondes=2)
        await page.evaluate("() => finishActiveRound(null)")
        await page.wait_for_timeout(150)
        s = await page.evaluate(STAND)
        check("oranje", s['regel'], 'oranje')
        check("met stip", s['stip'], True)

        print("\n=== 6. DE GRIJZE REGEL EN DE DRINGENDE STAND ZIJN HET EENS ===\n")
        await opzetten(page)
        r = await page.evaluate("""() => {
            localStorage.removeItem('golf_active_id');   // losgelaten zonder verder op te slaan
            return { nieuw: isErIetsOnveiligs(), overdue: isBackupOverdue(), verschil: backupVerschil() };
        }""")
        check("beide zien de nieuwe ronde", (r['nieuw'], r['overdue']), (True, True))
        check("en tellen hem als één nieuwe ronde", (r['verschil']['nieuw'], r['verschil']['bewerkt']), (1, 0))

        print("\n=== 7. OPSLAAN TIJDENS HET SPELEN VERANDERT NIETS AAN DE BACKUPSTAND ===\n")
        await opzetten(page, compleet=False)
        r = await page.evaluate("""() => {
            saveActiveRound(true);                       // schrijven tijdens het spelen
            return backupVerschil().totaal;
        }""")
        check("niets veranderd ten opzichte van de backup", r, 0)

        check("geen fouten in de pagina", pagina_fouten, [])
        await b.close()

    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
