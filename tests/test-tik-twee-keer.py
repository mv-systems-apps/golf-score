"""Tik twee keer om te bevestigen, voor alle knoppen (1352898-021).

Zestien knoppen vragen een tweede tik voordat ze iets doen (verwijderen, opslaan, afronden,
alles wissen). Tot 020 stond dat 15 keer met de hand in de app, naast bevestigTweeTikken.
Nu loopt het via één functie, tweedeTik. Per knop:
  1. de eerste tik doet niets, maar zet de knop klaar;
  2. na 2 seconden springt de knop terug;
  3. twee tikken na elkaar doen het één keer, en daarna staat de knop weer gewoon;
  4. een derde tik meteen daarna doet het niet nog een keer.
Punt 3 en 4 gingen tot 020 mis bij zeven knoppen: daar bleef de knop na de tweede tik
nog tot 2 seconden klaarstaan, en deed een derde tik het opnieuw.

De actie zelf wordt per knop vervangen door een teller (de eerste functie die na de tweede
tik draait); wat de actie doet, testen de andere tests.
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

# naam, voorbereiding (zet window.__teller op wat telt), aanroep met knop b
GEVALLEN = [
    ('ronde bewaren na import', "setRoundsAndMark = () => { window.__n++; return true; }; tekenRondelijst = () => {}; b.dataset.roundId = '1';", "archiveImportedRound(0, b)"),
    ('club uitlezen', "tryWriteToExportFolder = async () => { window.__n++; return true; };", "exportClub('Golfclub Heelsum', b)"),
    ('ronde afronden', "handelWachtendeTikAf = () => { window.__n++; }; saveActiveRound = () => false; meldNietOpgeslagen = () => {};", "finishActiveRound(b)"),
    ('ronde speler 2 opslaan', "handelWachtendeTikAf = () => { window.__n++; throw 'stop'; }; b.dataset.roundId = '2';", "saveAndClearPlayer2Round(b)"),
    ('opslaan en sluiten', "handelWachtendeTikAf = () => { window.__n++; }; saveActiveRound = () => false; meldNietOpgeslagen = () => {}; b.dataset.roundId = '1';", "saveAndClearActiveRound(b)"),
    ('ronde verwijderen', "showDangerModal = () => { window.__n++; }; _roundInfoIdx = 0;", "deleteRoundFromInfoModal(b)"),
    ('tee-regel verwijderen', "renderHoleTeeChooser = () => { window.__n++; throw 'stop'; }; updateTeeRowMoveHint = () => {};", "removeLastTeeRow(b)"),
    ('hole verwijderen', "syncHoleTableNaarTee = () => { window.__n++; throw 'stop'; }; const h = document.createElement('input'); h.className = 'hole-si'; document.getElementById('editorHoles').appendChild(h);", "removeHoleRow(b)"),
    ('club verwijderen', "showDangerModal = () => { window.__n++; }; editorClub = 'Golfclub Heelsum';", "deleteClubFromEditor(b)"),
    ('nieuwe club weggooien', "editorClub = '__nieuw__1'; CLUBS['__nieuw__1'] = { club: '', shortName: '', courses: {} }; hasUnsavedClubChanges = () => true; rebuildAll = () => { window.__n++; CLUBS['__nieuw__1'] = { club: '', shortName: '', courses: {} }; editorClub = '__nieuw__1'; };", "deleteClubFromEditor(b)"),
    ('baan verwijderen', "showDangerModal = () => { window.__n++; }; editorClub = 'Golfclub Heelsum'; editorOrigCourseName = 'Airborne';", "deleteCourseFromEditor(b)"),
    ('nieuwe baan weggooien', "editorOrigCourseName = null; hasUnsavedCourseChanges = () => true; editorCourseSnapshot = 'x'; window.__teller = () => editorCourseSnapshot === null ? 1 : 0;", "deleteCourseFromEditor(b) ; if (editorCourseSnapshot === null) { window.__n++; editorCourseSnapshot = 'x'; }"),
    ('alles wissen', "showDangerModal = () => { window.__n++; };", "confirmResetAll(b)"),
    ('niet-qualifying verwijderen', "showDangerModal = () => { window.__n++; };", "confirmPurgeNonQ(b)"),
    ('andere spelers verwijderen', "showDangerModal = () => { window.__n++; };", "confirmDeleteOtherPlayers(b)"),
    ('tee-knoppen (bevestigTweeTikken)', "", "bevestigTweeTikken(b, () => { window.__n++; })"),
]

async def main():
    rs = [ronde(1, '2026-05-01'), ronde(2, '2026-05-01', speler='Partner'), ronde(3, '2026-05-02', qual=False)]
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for naam, voor, roep in GEVALLEN:
            ctx = await br.new_context(viewport={"width": 390, "height": 844})
            pg = await ctx.new_page()
            await pg.goto(app_url())
            await pg.evaluate(SEED, [CLUBS, rs])
            await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
            await pg.reload(); await pg.wait_for_timeout(600)
            await pg.evaluate("""([voor, roep]) => {
              window.__n = 0;
              const b = document.createElement('button'); b.id = '__knop'; document.body.appendChild(b);
              (new Function('b', voor))(b);
              window.__tik = async () => { try { await (new Function('b', 'return (async () => { ' + roep + ' })()'))(b); } catch (e) { if (e !== 'stop') window.__fout = String(e); } };
            }""", [voor, roep])
            stand = "() => { const b = document.getElementById('__knop'); return [window.__n, b.dataset.confirm || '0', b.classList.contains('confirm-armed')]; }"
            print(f"\n=== {naam} ===")
            await pg.evaluate("() => window.__tik()")
            eerste = await pg.evaluate(stand)
            check(f"{naam}: de eerste tik doet niets en zet de knop klaar", [eerste[0], eerste[1]], [0, '1'])
            await pg.wait_for_timeout(2150)
            check(f"{naam}: na 2 seconden springt de knop terug", (await pg.evaluate(stand))[1:], ['0', False])
            await pg.evaluate("async () => { await window.__tik(); await window.__tik(); }")
            na = await pg.evaluate(stand)
            check(f"{naam}: twee tikken doen het één keer, en de knop staat weer gewoon", na, [1, '0', False])
            await pg.evaluate("() => window.__tik()")
            check(f"{naam}: een derde tik meteen daarna doet het niet opnieuw", (await pg.evaluate(stand))[0], 1)
            check(f"{naam}: geen fout", await pg.evaluate("() => window.__fout || null"), None)
            await ctx.close()
        await br.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
