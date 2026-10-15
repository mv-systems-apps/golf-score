"""Een export die mislukt, wordt gemeld en verandert de backupstand niet.

De app weet bij een gewone download niet of het bestand is aangekomen; dat kan een
browser niet vertellen. Wat de app WEL kan weten:
  - de download kon niet worden gestart (geblokkeerd, of een storing onderweg);
  - de exportmap was ingesteld maar niet bereikbaar, zodat het bestand in Downloads
    terechtkwam in plaats van waar je het verwacht.
In het eerste geval mag er geen 'geëxporteerd' staan en mag de backupdatum niet
verspringen; in het tweede hoor je te lezen waar het bestand is gebleven.
Vijf exports: alle rondes, alle clubs, één ronde, één club, de dagresultaten.
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

STAND = """() => ({ rondes: localStorage.getItem('golf_last_backup_date'), inhoud: localStorage.getItem('golf_backup_inhoud') || localStorage.getItem('golf_backup_rondes') || null,
  clubs: localStorage.getItem('golf_clubs_backup_date'), clubsVinger: localStorage.getItem('golf_clubs_backup_fingerprint') })"""
VENSTER = """() => { const m = document.getElementById('confirmModal'); return m.classList.contains('hidden') ? '' : (document.getElementById('confirmModalTitle').textContent + ' | ' + document.getElementById('confirmModalMessage').textContent); }"""
SLUIT = "() => document.getElementById('confirmModal').classList.add('hidden')"
GROEN = """() => [...document.querySelectorAll('.export-rounds-success, .export-clubs-success')].filter(e => !e.classList.contains('hidden')).map(e => e.textContent).join(' ')"""
# De vijf exports, elk via zijn eigen knop of functie
EXPORTS = [
    ('alle rondes', "document.querySelector('button[onclick=\"exportAllRounds()\"]').click()", 'rondes'),
    ('alle clubs',  "document.querySelector('button[onclick=\"exportAllClubs()\"]').click()", 'clubs'),
    ('één ronde',   "exportBackup(0)", None),
    ('één club',    "nav('club'); const k = document.querySelector('button[onclick^=\"exportClub(\"]'); k.click(); k.click()", None),
    ('dagresultaten', "exportDagresultaten()", None),
]
GEEN_DOWNLOAD = "() => { HTMLAnchorElement.prototype.click = function () { throw new Error('download geblokkeerd'); }; }"
MAP = """(lukt) => { window.__geschreven = [];
  const handle = { queryPermission: async () => 'granted', requestPermission: async () => 'granted',
    getFileHandle: async (naam) => { if (!lukt) throw new Error('map niet bereikbaar');
      return { createWritable: async () => ({ write: async (t) => { window.__geschreven.push([naam, t.length]); }, close: async () => {} }) }; } };
  window.exportFolderSupported = () => true; window.getStoredExportFolderHandle = async () => handle; }"""

async def verse(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True); pg = await ctx.new_page()
    await pg.goto(app_url())
    await pg.evaluate("""([c, r]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_profile_name', 'Mark'); localStorage.setItem('golf_player_name', 'Mark'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""",
      [CLUBS, [ronde(i + 1, f"2026-05-{i + 1:02d}") for i in range(4)]])
    await pg.reload(); await pg.wait_for_timeout(600)
    await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); nav('settings'); }"); await pg.wait_for_timeout(200)
    dl = []; pg.on('download', lambda d: dl.append(d.suggested_filename))
    return ctx, pg, dl

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. GEWONE DOWNLOAD (controle: dit blijft zoals het was) ===\n")
        ctx, pg, dl = await verse(b)
        for naam, js, soort in EXPORTS:
            dl.clear(); await pg.evaluate(SLUIT); await pg.evaluate(f"() => {{ {js}; }}"); await pg.wait_for_timeout(700)
            s = await pg.evaluate(STAND)
            check(f"{naam}: bestand gedownload, geen waarschuwing", (len(dl), await pg.evaluate(VENSTER)), (1, ''))
            if soort: check(f"{naam}: backupdatum gezet", s[soort] is not None, True)
        await ctx.close()

        print("\n=== 2. DE DOWNLOAD KAN NIET STARTEN ===\n")
        for naam, js, soort in EXPORTS:
            ctx, pg, dl = await verse(b)
            pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:80]))
            voor = await pg.evaluate(STAND)
            await pg.evaluate(GEEN_DOWNLOAD); await pg.evaluate(f"() => {{ {js}; }}"); await pg.wait_for_timeout(700)
            v = await pg.evaluate(VENSTER)
            check(f"{naam}: rode melding dat het exporteren mislukt is", ('mislukt' in v.lower(), len(dl)), (True, 0))
            check(f"{naam}: er staat nergens 'geëxporteerd'", 'xporteerd' in (await pg.evaluate(GROEN)), False)
            check(f"{naam}: de backupstand is niet verschoven", await pg.evaluate(STAND), voor)
            check(f"{naam}: geen losse fout (de algemene foutvanger blijft stil)", (pf, await pg.evaluate("document.querySelectorAll('#foutMelding').length")), ([], 0))
            await ctx.close()

        print("\n=== 3. EXPORTMAP INGESTELD MAAR NIET BEREIKBAAR ===\n")
        for naam, js, soort in EXPORTS:
            ctx, pg, dl = await verse(b)
            await pg.evaluate(MAP, False); await pg.evaluate(f"() => {{ {js}; }}"); await pg.wait_for_timeout(800)
            v = await pg.evaluate(VENSTER)
            check(f"{naam}: het bestand komt alsnog via een download", len(dl), 1)
            check(f"{naam}: en je leest dat het in Downloads staat, niet in je exportmap", ('Downloads' in v, 'exportmap' in v.lower()), (True, True))
            if soort: check(f"{naam}: de backupdatum is gezet (het bestand is er)", (await pg.evaluate(STAND))[soort] is not None, True)
            await ctx.close()

        print("\n=== 4. EXPORTMAP WERKT (controle) ===\n")
        ctx, pg, dl = await verse(b)
        await pg.evaluate(MAP, True)
        for naam, js, soort in EXPORTS:
            await pg.evaluate("window.__geschreven = []"); dl.clear(); await pg.evaluate(SLUIT); await pg.evaluate(f"() => {{ {js}; }}"); await pg.wait_for_timeout(700)
            check(f"{naam}: in de map geschreven, geen download, geen waarschuwing", (len(await pg.evaluate("window.__geschreven")), len(dl), await pg.evaluate(VENSTER)), (1, 0, ''))
        await ctx.close()
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
