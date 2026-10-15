"""De overstap naar de nieuwe backupmelding, vanaf opgeslagen standen van oudere versies.

De standen in overstap-standen.json zijn gemaakt met de versies 13527DA-0EE en -0EF,
met Marks echte rondes (backup van 19-9-2026).
Op 15-10-2026 geanonimiseerd (naam → Testspeler); de vingerafdruk die 0EF bij de backup
bewaarde (golf_backup_fp_bij_backup) is daarvoor opnieuw berekend over dezelfde rondes. Deze test bestaat omdat 0EF precies hier
misging: getest op een schone installatie, niet op een bestaande. Na de update gaf het
starten van een ronde een backupmelding.

Per stand: de opslag van de oude versie terugzetten, de nieuwe versie openen en kijken
of de melding klopt. Daarna nog een ronde starten (mag niets veranderen), en waar een
melding hoort: een backup maken, waarna het stil moet zijn.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
STANDEN = json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8'))

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

STAND = """() => { nav('settings'); updateLastBackupDisplay(); const r = document.getElementById('newRoundsInfoTop');
  return r.classList.contains('hidden') ? 'geen' : (r.innerHTML.includes('--orange') ? 'oranje' : 'grijs'); }"""

async def start(pg):
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
       document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.8'; }""")
    await pg.wait_for_timeout(250)
    await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
       if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, stand in STANDEN.items():
            print(f"\n=== {naam} ===\n")
            pg = await b.new_page(viewport={'width': 390, 'height': 844})
            paginafouten = []
            pg.on('pageerror', lambda e: paginafouten.append(str(e)[:120]))
            await pg.goto(app_url())
            await pg.evaluate("""([clubs, opslag]) => { localStorage.clear();
                localStorage.setItem('golf_clubs', JSON.stringify(clubs));
                localStorage.setItem('golf_profile_name', 'Testspeler');
                localStorage.setItem('golf_kenmerk_gevraagd', '1');
                localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
                localStorage.setItem('golf_backup_reminder_days', '1');
                localStorage.setItem('golf_backup_reminder_rounds', '1');
                for (const [k, v] of Object.entries(opslag)) if (v !== null) localStorage.setItem(k, v); }""",
                [CLUBS, stand['opslag']])
            await pg.reload(); await pg.wait_for_timeout(500)
            if stand['verwacht'] == 'stil':
                check("na de update: geen melding", await pg.evaluate(STAND), 'geen')
                if not await pg.evaluate("() => !!game.started"):
                    await start(pg)
                    check("na het starten van een ronde: nog steeds geen", await pg.evaluate(STAND), 'geen')
            else:
                check("na de update: de melding blijft staan", await pg.evaluate(STAND) != 'geen', True)
                await pg.evaluate("async () => { window.tryWriteToExportFolder = async () => true; await exportAllRounds(); }")
                check("na een backup: geen melding", await pg.evaluate(STAND), 'geen')
                if not await pg.evaluate("() => !!game.started"):
                    await start(pg)
                    check("daarna een ronde starten: nog steeds geen", await pg.evaluate(STAND), 'geen')
            oud = await pg.evaluate("""() => ['golf_rounds_changed','golf_backup_fingerprint','golf_backup_fp_bij_backup']
                .filter(k => localStorage.getItem(k) !== null)""")
            check("de oude stempels zijn opgeruimd", oud, [])
            check("geen fouten in de pagina", paginafouten, [])
            await pg.close()
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
