"""Fouten uit de onafhankelijke review van 18-10-2026 (1352898-009).

  1. Rondes TOEVOEGEN uit een bestand, zonder eerdere backup maar met eigen rondes: de
     app legde de hele stand vast als backup. De eigen rondes stonden in geen enkel
     bestand en de backupmelding verdween.
  2. Twee vensters: venster B schreef een clubwijziging uit venster A stil weg (club
     inlezen, verwijderen, nieuwe club). Nu neemt B de clubs over als er geen editor
     openstaat, en weigert het opslaan als er wel een openstaat.
  3. De spelanalyse en 'Prompt voor AI' noemden nooit de handicap (de functie werd zonder
     speler aangeroepen).
  4. + of − op het startscherm tijdens een lopende ronde zette een andere baanhandicap in
     de kopbalk van die ronde.
  5. Een ronde zonder baanhandicap kreeg na herstarten chcp 0 (er kwam een veld bij).
  6. De keuring weigerde slagen per hole die de app zelf kan maken (9 holes, baanhandicap
     50: 6 per hole), zodat zo'n ronde niet uit een backup terug te zetten was.
  7. 'Alles wissen' liet de WHS-schakelaar staan; 'baanen' in de importmelding.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, RONDES, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def nieuw(ctx, rondes, extra=None):
    pg = await ctx.new_page()
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
    pg._pf = pf
    await pg.goto(app_url())
    await pg.evaluate(SEED, [CLUBS, rondes])
    await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
    if extra: await pg.evaluate(extra)
    await pg.reload(); await pg.wait_for_timeout(600)
    await pg.evaluate(DICHT)
    return pg

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. TOEVOEGEN UIT EEN BESTAND, NOG NOOIT EEN BACKUP ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        eigen = [ronde(i, f'2026-03-{i:02d}') for i in range(1, 11)]
        pg = await nieuw(ctx, eigen)
        check("vooraf: eigen rondes, geen backup, melding staat", await pg.evaluate("() => isBackupOverdue()"), True)
        vreemd = [ronde(201, '2026-04-01'), ronde(202, '2026-04-02')]
        await pg.evaluate("(r) => doAdditiveImport(r)", vreemd)
        await pg.evaluate(DICHT)
        check("na Toevoegen: de eigen rondes staan nog niet in een backup", await pg.evaluate("() => isBackupOverdue()"), True)
        check("er is geen backupdatum verzonnen", await pg.evaluate("() => localStorage.getItem('golf_last_backup_date')"), None)
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, [])
        await pg.evaluate("(r) => doAdditiveImport(r)", vreemd)
        await pg.evaluate(DICHT)
        check("leeg archief (nieuw toestel): de import geldt wel als backup",
              [await pg.evaluate("() => !!localStorage.getItem('golf_last_backup_date')"), await pg.evaluate("() => isBackupOverdue()")], [True, False])
        await ctx.close()

        print("\n=== 2. TWEE VENSTERS, CLUBS ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        A = await nieuw(ctx, RONDES)
        B = await ctx.new_page(); B._pf = []; B.on('pageerror', lambda e: B._pf.append(str(e)[:160]))
        await B.goto(app_url()); await B.wait_for_timeout(600); await B.evaluate(DICHT)
        nieuwe_club = lambda naam: """() => { CLUBS['%s'] = JSON.parse(JSON.stringify(CLUBS['Papendal'])); CLUBS['%s'].club = '%s'; return saveClubsToStorage(); }""" % (naam, naam, naam)
        check("A bewaart Testclub A", await A.evaluate(nieuwe_club('Testclub A')), True)
        await B.wait_for_timeout(300)
        check("B heeft Testclub A overgenomen", await B.evaluate("() => !!CLUBS['Testclub A']"), True)
        await B.evaluate(DICHT)
        check("B bewaart daarna Testclub B", await B.evaluate(nieuwe_club('Testclub B')), True)
        check("in de opslag staan A en B allebei",
              await A.evaluate("() => { const c = JSON.parse(localStorage.getItem('golf_clubs')); return [!!c['Testclub A'], !!c['Testclub B']]; }"), [True, True])
        # met een editor open in B: overnemen zou de invoer onderuit halen, dus weigeren
        await B.evaluate("() => document.getElementById('clubEditorOverlay').classList.remove('hidden')")
        await A.evaluate(nieuwe_club('Testclub C')); await B.wait_for_timeout(300)
        await B.evaluate(DICHT)
        check("B met de clubeditor open: B weigert op te slaan", await B.evaluate(nieuwe_club('Testclub D')), False)
        check("en Testclub C uit A blijft in de opslag",
              await A.evaluate("() => { const c = JSON.parse(localStorage.getItem('golf_clubs')); return [!!c['Testclub C'], !!c['Testclub D']]; }"), [True, False])
        check("de melding zegt waarom", await B.evaluate("() => { let t = ''; const oud = showConfirmModal; showConfirmModal = (a, m) => { t = m; }; meldSchrijvenMislukt('De club', 'clubs'); showConfirmModal = oud; return /ander tabblad/.test(t); }"), True)
        await ctx.close()

        print("\n=== 3. ANALYSE EN PROMPT VOOR AI NOEMEN DE HANDICAP ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, RONDES)
        tekst = await pg.evaluate("""async () => { let t = ''; navigator.clipboard.writeText = async x => { t = x; }; try { await copyAnalysisForAi(); } catch (e) {} return t; }""")
        check("de prompt noemt de handicap", 'Mijn handicap is nu' in tekst, True)
        check("de analyse noemt de handicap", await pg.evaluate("() => JSON.stringify(buildGameAnalysis()).includes('handicap is nu')"), True)
        await ctx.close()

        print("\n=== 4. STARTSCHERM +/- TIJDENS EEN RONDE ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, RONDES, "() => localStorage.setItem('golf_last_backup_date', new Date().toISOString())")
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.tee = 'Blauw'; startRound(); const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
        await pg.wait_for_timeout(300); await pg.evaluate(DICHT)
        voor = await pg.evaluate("() => [game.started, document.getElementById('hdrChcp').textContent]")
        await pg.evaluate("() => { nav('setup'); sel.track = 'Sandr'; adjustChcp(1); adjustChcp(1); adjustChcp(1); nav('score'); }")
        na = await pg.evaluate("() => [game.started, document.getElementById('hdrChcp').textContent]")
        check("de kopbalk van de lopende ronde blijft gelijk", na, voor)
        await ctx.close()

        print("\n=== 5. RONDE ZONDER BAANHANDICAP NA HERSTARTEN ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        r = ronde(301, '2026-10-01', played=3); del r['chcp']
        pg = await nieuw(ctx, [r], "() => localStorage.setItem('golf_active_id', '301')")
        await pg.evaluate("() => { nav('score'); setCurrentHole(3); stepScore(3, 1); }"); await pg.wait_for_timeout(300)
        check("na een tik staat er geen verzonnen chcp in de opslag",
              await pg.evaluate("() => 'chcp' in JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.id === 301)"), False)
        await ctx.close()

        print("\n=== 6. KEURING: SLAGEN PER HOLE DIE DE APP ZELF MAAKT ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, [])
        r9 = ronde(401, '2026-10-02'); r9['chcp'] = 50
        for i, h in enumerate(r9['holes']): h['phcp'] = 6 if i < 5 else 5; h['id'] = str(h['id'])
        check("9 holes, baanhandicap 50: de keuring laat hem toe", await pg.evaluate("(r) => keurRonde(r)", r9), None)
        r18 = ronde(402, '2026-10-03'); r18['holes'] = r18['holes'] + [dict(h, id=h['id'] + 9) for h in r18['holes']]; r18['holesCount'] = 18; r18['PAR'] = 2 * r18['PAR']
        for i, h in enumerate(r18['holes']): h['phcp'] = 6; h['id'] = str(i + 1); h['si'] = i + 1
        check("18 holes met 6 per hole kan niet: geweigerd", await pg.evaluate("(r) => keurRonde(r)", r18), 'slagen per hole buiten -3 tot 5')

        print("\n=== 7. ALLES WISSEN EN DE IMPORTMELDING ===\n")
        await pg.evaluate("() => { localStorage.setItem('golf_whs_volgen', 'off'); }")
        await pg.evaluate("async () => { await doResetAll(); }"); await pg.wait_for_timeout(300)
        check("'Alles wissen' wist ook de WHS-schakelaar", await pg.evaluate("() => localStorage.getItem('golf_whs_volgen')"), None)
        bron = open(os.environ.get('APP') or os.path.join(os.path.dirname(HIER), 'golf-score.html'), encoding='utf-8').read()
        check("geen 'baanen' meer in de app", 'baanen' in bron or "baan${n !== 1 ? 'en'" in bron, False)
        await ctx.close()

        print("\n=== 8. TWEE RONDES OP HETZELFDE TIJDSTIP OP DE GRENS VAN DE LAATSTE 20 (1352898-010) ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        rs = []
        for i in range(21):
            r = ronde(500 + i, f'2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}')
            r['sdFinal'] = 20.0
            rs.append(r)
        # de twee oudste op precies hetzelfde tijdstip, met een heel ander dagresultaat
        rs[1]['date'] = rs[0]['date']; rs[0]['time'] = ''; rs[1]['time'] = ''
        rs[0]['sdFinal'] = 14.0; rs[1]['sdFinal'] = 26.0
        rs.reverse()   # zoals de app bewaart: nieuwste eerst
        # een handmatige Low HI ver weg, zodat de caps het verschil niet verbergen
        pg = await nieuw(ctx, rs, "() => localStorage.setItem('golf_low_hi', '40')")
        uit = await pg.evaluate("""() => { const R = leesRondes(); const nu = currentOfficialHcp('Testspeler', R);
            const v = whsVerloop(verloopChrono('Testspeler', R), getManualLowHi()); return [nu, v.stappen[v.stappen.length - 1].value]; }""")
        check("'handicap nu' en het verloop kiezen dezelfde ronde", uit[0], uit[1])
        await ctx.close()

        pf = [x for x in getattr(A, '_pf', []) + getattr(B, '_pf', [])]
        check("geen fouten in de pagina's", pf, [])
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
