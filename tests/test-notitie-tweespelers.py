"""Notities (en naam) blijven bij de juiste ronde als je met twee spelers een ronde bewerkt.

Aanleiding (Marks melding: notities kwijt). De bewerkschermen 'Ronde bewerken' en
'Vaststellen' gingen ervan uit dat de ronde op het scorescherm altijd die van speler 1
is. Stond speler 2 voor, dan:
  - bewerkte je ZIJN notitie: de eerstvolgende score schreef de oude terug;
  - bewerkte je die van speler 1: notitie (en bij Ronde bewerken ook de naam) kwam op de
    ronde van speler 2 terecht.
Eerdere reparaties aan notities waren alleen met speler 1 op het scherm getest.

Alle combinaties: beide schermen x speler 1 of 2 op het scherm x ronde van 1 of 2
bewerken. Na elke bewerking: direct kijken, dan een score + spelerwissel + score, dan
herladen.
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

NOTES = "() => leesRondes().filter(r => [String(game.id), String(game2Id), String(localStorage.getItem('golf_active_id')), String(localStorage.getItem('golf_game2_id'))].includes(String(r.id))).map(r => [r.player, r.note ?? null])"

async def start(pg):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
    await pg.reload(); await pg.wait_for_timeout(500)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
       document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8';
       player2Visible = true; sel2.gender='Dames'; sel2.tee = Object.keys(CLUBS['Golfclub Heelsum'].courses['Airborne'].tees['Dames']||{})[0] || 'Rood';
       document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
       zetStartNote(1, 'notitie Mark'); zetStartNote(2, 'notitie Anna'); }""")
    await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
       if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""")
    await pg.wait_for_timeout(400)

async def bewerk(pg, speler, tekst, via='info'):
    await pg.evaluate("""([speler, tekst, via]) => { const s = loadSavedRounds(); const idx = s.findIndex(r => r.player === speler && (String(r.id)===localStorage.getItem('golf_active_id') || String(r.id)===localStorage.getItem('golf_game2_id')));
      if (via === 'info') { doOpenRoundInfoModal(idx); if (tekst !== null) document.getElementById('editNoteInput').value = tekst; confirmRoundInfo(); }
      else { doOpenRoundResultModal(idx); if (tekst !== null) document.getElementById('resultNoteInput').value = tekst; confirmRoundResult(); } }""", [speler, tekst, via])
    await pg.wait_for_timeout(200)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:120]))
        for via in ['info', 'resultaat']:
            for actief in [1, 2]:
                for doel in ['Mark', 'Anna']:
                    print(f"\n=== {'Ronde bewerken' if via == 'info' else 'Vaststellen'}, speler {actief} op het scherm, ronde van {doel} ===\n")
                    await start(pg)
                    if actief == 2: await pg.evaluate("() => switchToPlayer(2)")
                    await bewerk(pg, doel, 'NIEUW ' + doel, via)
                    goed = sorted([['Mark', 'NIEUW Mark' if doel == 'Mark' else 'notitie Mark'],
                                   ['Anna', 'NIEUW Anna' if doel == 'Anna' else 'notitie Anna']])
                    check("direct na het opslaan", sorted(await pg.evaluate(NOTES)), goed)
                    await pg.evaluate("() => { stepScore(currentHole, +1); }")
                    await pg.evaluate("(n) => switchToPlayer(n)", 1 if actief == 2 else 2)
                    await pg.evaluate("() => { stepScore(currentHole, +1); }")
                    check("na een score, wisselen en nog een score", sorted(await pg.evaluate(NOTES)), goed)
                    await pg.reload(); await pg.wait_for_timeout(500)
                    check("na herladen", sorted(await pg.evaluate(NOTES)), goed)
                    check("beide rondes hebben nog hun score", await pg.evaluate(
                        "() => leesRondes().filter(r => ['Mark','Anna'].includes(r.player) && r.note).map(r => r.holes.filter(h => h.score != null).length)"), [1, 1])
        print("\n=== VIA DE ECHTE KNOPPEN IN RONDES, SPELER 2 OP HET SCHERM ===\n")
        await start(pg); await pg.evaluate("() => switchToPlayer(2)")
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        idx = await pg.evaluate("() => loadSavedRounds().findIndex(r => r.player === 'Anna')")
        await pg.locator(f'button[onclick="openRoundEditChoice({idx})"]').first.click(); await pg.wait_for_timeout(150)
        await pg.click('#roundEditChoiceInfo'); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const k = document.getElementById('confirmModalBtn'); if (k && !document.getElementById('confirmModal').classList.contains('hidden')) k.click(); }")
        await pg.fill('#editNoteInput', 'getikt Anna'); await pg.click('button[onclick="confirmRoundInfo()"]'); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { nav('score'); stepScore(currentHole, +1); switchToPlayer(1); stepScore(currentHole, +1); }")
        check("notitie van speler 2 blijft, die van speler 1 ook", sorted(await pg.evaluate(NOTES)), sorted([['Mark', 'notitie Mark'], ['Anna', 'getikt Anna']]))

        print("\n=== DATUM WIJZIGEN MET SPELER 2 OP HET SCHERM: ONTKOPPELEN ===\n")
        STAAT = """() => ({ rondes: leesRondes().filter(r => ['Mark','Anna'].includes(r.player) && r.note).map(r => [r.player, r.date, r.note, r.holes.filter(h => h.score != null).length]).sort(),
            actief: (leesRondes().find(r => String(r.id) === localStorage.getItem('golf_active_id')) || {}).player || null,
            g2: localStorage.getItem('golf_game2_id'), scherm: game.player, speler: activePlayer })"""
        for doel in ['Anna', 'Mark']:
            await start(pg)
            vandaag = await pg.evaluate("() => todayISO()")
            await pg.evaluate("() => { stepScore(currentHole, +1); switchToPlayer(2); stepScore(currentHole, +1); }")
            await pg.evaluate("""(doel) => { const i = leesRondes().findIndex(r => r.player === doel && r.note); doOpenRoundInfoModal(i);
                document.getElementById('editDateInput').value = '2026-01-05'; confirmRoundInfo(); }""", doel); await pg.wait_for_timeout(200)
            goed = sorted([['Anna', '2026-01-05' if doel == 'Anna' else vandaag, 'notitie Anna', 1], ['Mark', '2026-01-05' if doel == 'Mark' else vandaag, 'notitie Mark', 1]])
            st = await pg.evaluate(STAAT)
            check(f"datum van {doel}: beide rondes kloppen", st['rondes'], goed)
            check("speler 1 is actief én staat op het scherm, koppeling weg", (st['actief'], st['scherm'], st['speler'], st['g2']), ('Mark', 'Mark', 1, None))
            await pg.reload(); await pg.wait_for_timeout(500)
            st = await pg.evaluate(STAAT)
            check("na herladen hetzelfde", (st['rondes'], st['actief'], st['scherm']), (goed, 'Mark', 'Mark'))

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
