"""Na onleesbare gegevens moet je backup terugzetten ook echt lukken.

Raakt de opslag beschadigd, dan toont de app een lege lijst en schrijft hij niets meer
weg (test-corrupt.py). De melding zegt: zet je backup terug. Maar tot 13527DA-116 hield
dezelfde rem ook het terugzetten tegen — de enige uitweg was 'Alles wissen'.

De regel:
  * terugzetten van een backup lukt, na een uitdrukkelijke bevestiging;
  * annuleer je, dan blijven de onleesbare gegevens onaangeroerd;
  * al het andere (een score, één ronde inlezen, een club wijzigen) blijft geweigerd,
    en de melding noemt de echte oorzaak, niet 'te weinig opslagruimte';
  * de verwijzing naar je lopende ronde blijft staan zolang de gegevens onleesbaar zijn.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

KAPOT = '[{"id":1,"date":"2026-05-01","holes":[{"par":4,"sco'
KAPOTTE_CLUBS = '{"Golfclub Heelsum":{"club":"Golfclub Hee'
def bestand(inhoud, naam):
    pad = os.path.join(tempfile.mkdtemp(), naam)
    with open(pad, 'w', encoding='utf-8') as f: json.dump(inhoud, f, ensure_ascii=False)
    return pad
VENSTER = """() => { const m = document.getElementById('confirmModal'), k = document.getElementById('keuzeModal');
  const open = e => e && !e.classList.contains('hidden');
  return (open(k) ? k.innerText : open(m) ? m.innerText : '').replace(/\\s+/g, ' ').trim(); }"""
async def tik(pg, tekst):
    k = pg.locator(f'#confirmModal:not(.hidden) button:visible, #keuzeModal:not(.hidden) button:visible, #dangerModal:not(.hidden) button:visible').filter(has_text=tekst)
    if await k.count(): await k.first.click(); await pg.wait_for_timeout(350); return True
    return False
async def sluit(pg):
    for _ in range(3):
        if not await tik(pg, 'Sluiten'): break

async def start(b, rondes_ruw, clubs_ruw, extra=None):
    pg = await b.new_page(viewport={"width": 390, "height": 844})
    pg.fouten = []; pg.on('pageerror', lambda e: pg.fouten.append(str(e)[:160]))
    await pg.goto(app_url())
    await pg.evaluate("""([r, c, extra]) => { localStorage.clear(); localStorage.setItem('golf_clubs', c); localStorage.setItem('golf_rounds', r);
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
      for (const k in (extra || {})) localStorage.setItem(k, extra[k]); }""", [rondes_ruw, clubs_ruw, extra])
    await pg.reload(); await pg.wait_for_timeout(900)
    return pg

async def main():
    backup = [ronde(i + 1, f"2026-06-{i + 1:02d}") for i in range(4)]
    for r in backup: r.pop('id', None)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pf = []

        print("\n=== 1. ONLEESBARE RONDES: BACKUP TERUGZETTEN ===\n")
        pg = await start(b, KAPOT, json.dumps(CLUBS), {'golf_active_id': '1'})
        melding = await pg.evaluate(VENSTER); await sluit(pg)
        check("bij het openen: de melding dat de gegevens niet leesbaar zijn", 'niet leesbaar' in melding, True)
        check("de verwijzing naar de lopende ronde is niet opgeruimd", await pg.evaluate("() => localStorage.getItem('golf_active_id')"), '1')
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importRoundFile').set_input_files(bestand(backup, 'rondes_backup.json')); await pg.wait_for_timeout(600)
        vraag = await pg.evaluate(VENSTER)
        check("terugzetten vraagt eerst om bevestiging en noemt de onleesbare gegevens", 'niet leesbaar' in vraag and 'vervang' in vraag.lower(), True)
        check("vóór de bevestiging is er niets overschreven", await pg.evaluate("() => localStorage.getItem('golf_rounds')"), KAPOT)
        await tik(pg, 'Annuleren')
        check("annuleren: de onleesbare gegevens staan er nog", await pg.evaluate("() => localStorage.getItem('golf_rounds')"), KAPOT)
        await pg.locator('#importRoundFile').set_input_files(bestand(backup, 'rondes_backup.json')); await pg.wait_for_timeout(600)
        async with pg.expect_download() as d: await pg.locator('#keuzeModal button:visible', has_text='Bewaar eerst').click()
        kopie = await d.value
        check("noodkopie: de onleesbare tekst komt letterlijk in een bestand", (open(await kopie.path(), encoding='utf-8').read(), kopie.suggested_filename.startswith('golf_rounds_onleesbaar_')), (KAPOT, True))
        check("daarna staat de vraag er weer, en is er nog niets overschreven", ('Terugzetten' in await pg.evaluate(VENSTER), await pg.evaluate("() => localStorage.getItem('golf_rounds')")), (True, KAPOT))
        await tik(pg, 'Terugzetten'); klaar = await pg.evaluate(VENSTER); await sluit(pg)
        na = await pg.evaluate("() => { try { return JSON.parse(localStorage.getItem('golf_rounds')).map(r => r.date).sort(); } catch (e) { return String(e); } }")
        check("bevestigen: de vier rondes uit de backup staan in de opslag", na, sorted(r['date'] for r in backup))
        check("en dat wordt gemeld als gelukt", 'mislukt' not in klaar.lower() and ('teruggezet' in klaar.lower() or 'geïmporteerd' in klaar.lower()), True)
        await pg.reload(); await pg.wait_for_timeout(700)
        check("na herladen: geen melding meer, vier rondes", (('niet leesbaar' in await pg.evaluate(VENSTER)), await pg.evaluate("() => leesRondes().length")), (False, 4))
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.7';
          startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
          nav('score'); setCurrentHole(0); selectHole(0); armScoreChange(0, 5); clearScoreTap(false); }""")
        check("daarna werkt opslaan weer gewoon: vijf rondes", await pg.evaluate("() => { try { return JSON.parse(localStorage.getItem('golf_rounds')).length; } catch (e) { return 'onleesbaar'; } }"), 5)
        pf += pg.fouten; await pg.close()

        print("\n=== 2. ONLEESBARE RONDES: AL HET ANDERE BLIJFT GEWEIGERD ===\n")
        pg = await start(b, KAPOT, json.dumps(CLUBS)); await sluit(pg)
        await pg.evaluate("() => nav('settings')")
        await pg.locator('#importRoundFile').set_input_files(bestand(backup[0], 'ronde.json')); await pg.wait_for_timeout(600)
        m = await pg.evaluate(VENSTER); await sluit(pg)
        check("één ronde inlezen: geweigerd, opslag onaangeroerd", await pg.evaluate("() => localStorage.getItem('golf_rounds')"), KAPOT)
        check("de melding noemt de oorzaak en niet de opslagruimte", ('niet leesbaar' in m, 'opslagruimte' in m, 'geïmporteerd' in m.lower()), (True, False, False))
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.7';
          startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(300)
        check("een ronde starten: opslag onaangeroerd", await pg.evaluate("() => localStorage.getItem('golf_rounds')"), KAPOT)
        pf += pg.fouten; await pg.close()

        print("\n=== 3. ONLEESBARE CLUBS: CLUBBACKUP TERUGZETTEN ===\n")
        pg = await start(b, '[]', KAPOTTE_CLUBS)
        melding = await pg.evaluate(VENSTER); await sluit(pg)
        check("bij het openen: de melding dat de clubgegevens niet leesbaar zijn", 'niet leesbaar' in melding, True)
        await pg.evaluate("() => nav('club')")
        # Marks eigen clubbackup: de verzonnen clubs uit testdata.py komen niet door de keuring.
        clubbackup = json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))
        namen = sorted(c['club'] for c in clubbackup)
        await pg.locator('#importClubFile').set_input_files(bestand(clubbackup, 'clubs_backup.json')); await pg.wait_for_timeout(600)
        vraag = await pg.evaluate(VENSTER)
        check("terugzetten vraagt eerst om bevestiging", 'niet leesbaar' in vraag and 'vervang' in vraag.lower(), True)
        check("vóór de bevestiging is er niets overschreven", await pg.evaluate("() => localStorage.getItem('golf_clubs')"), KAPOTTE_CLUBS)
        await tik(pg, 'Annuleren')
        check("annuleren: de onleesbare clubgegevens staan er nog", await pg.evaluate("() => localStorage.getItem('golf_clubs')"), KAPOTTE_CLUBS)
        await pg.locator('#importClubFile').set_input_files(bestand(clubbackup, 'clubs_backup.json')); await pg.wait_for_timeout(600)
        await tik(pg, 'Terugzetten'); await tik(pg, 'Overschrijven'); await sluit(pg)
        na = await pg.evaluate("() => { try { return Object.keys(JSON.parse(localStorage.getItem('golf_clubs'))).sort(); } catch (e) { return String(e); } }")
        check("bevestigen: de clubs uit de backup staan in de opslag", [k for k in namen if k in na] if isinstance(na, list) else na, namen)
        check("de vraag noemde het aantal clubs in het bestand", f"{len(namen)} clubs" in vraag, True)
        await pg.reload(); await pg.wait_for_timeout(700)
        check("na herladen: geen melding meer", 'niet leesbaar' in await pg.evaluate(VENSTER), False)
        pf += pg.fouten; await pg.close()

        print("\n=== 4. ONLEESBARE CLUBS: EEN GEWONE WIJZIGING BLIJFT GEWEIGERD EN ZEGT DAT ===\n")
        pg = await start(b, '[]', KAPOTTE_CLUBS); await sluit(pg)
        r = await pg.evaluate("() => { const ok = saveClubsToStorage(); return [ok, localStorage.getItem('golf_clubs')]; }")
        check("opslaan van clubs: geweigerd, opslag onaangeroerd", r, [False, KAPOTTE_CLUBS])
        pf += pg.fouten; await pg.close()

        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
