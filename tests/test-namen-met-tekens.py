"""Tee- en holenamen met tekens als ' " < > & mogen geen scherm breken.

De naamvelden voor speler, club en baan filteren tekens; tee- en holenamen gaan via het
gedeelde invoervenster en kennen geen filter. Tot 13527DA-117 werden ze op een aantal
plekken onbewerkt in HTML gezet. Gevolg: een tee die Men's heet gaf de teeknop van
speler 2 een schrijffout, en een naam met < of " verminkte de editor en de kaarten.

De regel: een naam is tekst. Wat je intypt staat overal letterlijk zo in beeld, alle
knoppen blijven werken, en er ontstaat nergens een extra element.

De namen worden hier via de echte editor ingetypt, daarna gaan alle schermen langs.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

TEE = 'Men\'s <b data-inj="tee">&amp;</b>'
HOLE = 'A\'<i data-inj="hole">"1</i>'
def tee(cr, sr): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate([4, 3, 5, 4, 4, 3, 4, 5, 4])]}
CLUBS = {"Testclub": {"club": "Testclub", "shortName": "TC", "courses": {"Baan": {"holeIds": [f"H{i}" for i in range(1, 10)],
         "tees": {"Heren": {"Geel": tee(35.0, 120), "Wit": tee(36.1, 125)}, "Dames": {"Rood": tee(36.5, 126)}}}}}}
# Is er iets als HTML uitgevoerd? En welke namen staan er als tekst?
STAND = """() => ({ inj: [...document.querySelectorAll('[data-inj]')].map(e => e.dataset.inj + ' in #' + ((e.closest('[id]') || {}).id || '?')),
  scherm: document.querySelector('.screen.active')?.id })"""
TEKST = "(sel) => [...document.querySelectorAll(sel)].map(e => e.textContent.trim())"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""(c) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', '[]');
          localStorage.setItem('golf_default_club', 'Testclub'); localStorage.setItem('golf_home_club', 'Testclub'); localStorage.setItem('golf_profile_name', 'Mark');
          localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_track_putts', 'on'); }""", CLUBS)
        await pg.reload(); await pg.wait_for_timeout(600)
        async def schoon(waar):
            s = await pg.evaluate(STAND)
            check(f"{waar}: niets als HTML uitgevoerd", s['inj'], [])
            n = len(pf); 
            check(f"{waar}: geen fout in de pagina", pf[:], []) if pf else None
            del pf[:]

        print("\n=== 1. NAMEN INTYPEN IN DE EDITOR ===\n")
        await pg.evaluate("() => { nav('club'); openClubEditor('Testclub'); openCourseEditor('Baan'); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { ['tees', 'holes'].forEach(k => { const w = document.getElementById(k === 'tees' ? 'editorTeesWrap' : 'editorHolesWrap'); if (w && w.classList.contains('hidden')) toggleEditorSection(k); }); }")
        wit = "() => [...document.querySelectorAll('#editorTeesBody .tee-name-field')].find(e => e.dataset.value === 'Wit')"
        await pg.evaluate(f"() => ({wit})().click()"); await pg.wait_for_timeout(200)
        await pg.fill('#valueEditInput', TEE); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check("de teenaam staat in het veld zoals getypt", await pg.evaluate("(t) => [...document.querySelectorAll('#editorTeesBody .tee-name-field')].some(e => e.dataset.value === t && e.textContent.trim() === t)", TEE), True)
        await schoon("na het intypen van de teenaam")
        await pg.evaluate("() => { const rij = [...document.querySelectorAll('#editorTeesBody .tee-name-field')].find(e => e.dataset.value.startsWith('Men')).closest('tr'); rij.querySelector('.cr-name-field').click(); }"); await pg.wait_for_timeout(200)
        check("het invoervenster voor de CR noemt de tee als tekst", TEE.upper() in (await pg.evaluate("() => document.getElementById('valueEditLabel').textContent")).upper() or TEE in await pg.evaluate("() => document.getElementById('valueEditLabel').textContent"), True)
        await schoon("invoervenster CR"); await pg.evaluate("() => closeValueEditModal()")
        await pg.evaluate("() => { const i = document.querySelector('#editorHolesBody .hole-id'); openHoleFieldModal(i, 1, 'ID'); }"); await pg.wait_for_timeout(200)
        await pg.fill('#valueEditInput', HOLE); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check("de holenaam staat in het veld zoals getypt", await pg.evaluate("() => document.querySelector('#editorHolesBody .hole-id').value"), HOLE)
        await pg.evaluate("() => { const i = document.querySelector('#editorHolesBody .hole-si'); openHoleFieldModal(i, 1, 'SI'); }"); await pg.wait_for_timeout(200)
        await schoon("invoervenster SI (noemt de hole)"); await pg.evaluate("() => closeValueEditModal()")
        await pg.evaluate("() => saveCourseFromEditor()"); await pg.wait_for_timeout(400)
        opgeslagen = await pg.evaluate("() => { const b = JSON.parse(localStorage.getItem('golf_clubs')).Testclub.courses.Baan; return [Object.keys(b.tees.Heren).sort(), b.holeIds[0]]; }")
        check("opgeslagen zoals getypt", opgeslagen, [sorted(['Geel', TEE]), HOLE])
        await schoon("na opslaan")
        await pg.evaluate("() => { closeCourseEditor(); openCourseEditor('Baan'); ['tees', 'holes'].forEach(k => { const w = document.getElementById(k === 'tees' ? 'editorTeesWrap' : 'editorHolesWrap'); if (w && w.classList.contains('hidden')) toggleEditorSection(k); }); }"); await pg.wait_for_timeout(300)
        check("de editor opnieuw geopend toont dezelfde namen", await pg.evaluate("() => [[...document.querySelectorAll('#editorTeesBody .tee-name-field')].map(e => e.dataset.value).sort(), document.querySelector('#editorHolesBody .hole-id').value, document.querySelectorAll('#editorTeesBody tr').length]"),
              [sorted(['Geel', 'Rood', TEE]), HOLE, 3])
        await schoon("editor opnieuw geopend")
        await pg.evaluate("() => { saveCourseFromEditor(); }"); await pg.wait_for_timeout(300)
        check("nog een keer opslaan verandert niets", await pg.evaluate("() => { const b = JSON.parse(localStorage.getItem('golf_clubs')).Testclub.courses.Baan; return [Object.keys(b.tees.Heren).sort(), b.holeIds[0]]; }"), opgeslagen)
        await pg.evaluate("() => { closeCourseEditor(); openLusMaker(); kiesLusBron('Baan'); }"); await pg.wait_for_timeout(300)
        await schoon("venster Nieuwe lus")
        check("Nieuwe lus toont de holenaam als tekst", HOLE in await pg.evaluate("() => document.getElementById('lusOverlay').textContent"), True)
        await pg.evaluate("() => { sluitLusMaker(); closeClubEditor(); }")

        print("\n=== 2. STARTSCHERM: DE TEEKNOPPEN VAN BEIDE SPELERS ===\n")
        await pg.evaluate("() => { nav('setup'); sel.track = 'Baan'; rebuildAll(); if (!player2Visible) togglePlayer2(); }"); await pg.wait_for_timeout(300)
        await schoon("startscherm")
        k1 = pg.locator('#teeBtns .tee-btn').filter(has_text='Men')
        check("speler 1: de knop toont de naam als tekst", await k1.first.text_content(), TEE)
        await k1.first.click(); await pg.wait_for_timeout(200)
        check("speler 1: aantikken kiest de tee", await pg.evaluate("() => sel.tee"), TEE)
        k2 = pg.locator('#teeBtns2 .tee-btn').filter(has_text='Men')
        check("speler 2: de knop toont de naam als tekst", (await k2.first.text_content()) if await k2.count() else None, TEE)
        await pg.locator('#teeBtns2 .tee-btn').filter(has_text='Geel').first.click(); await pg.wait_for_timeout(150)
        if await k2.count(): await k2.first.click(); await pg.wait_for_timeout(200)
        check("speler 2: aantikken kiest de tee", await pg.evaluate("() => sel2.tee"), TEE)
        await schoon("na het kiezen van de tees")

        print("\n=== 3. EEN RONDE MET TWEE SPELERS OP DIE TEE ===\n")
        await pg.evaluate("""() => { document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.7'; onHcpBlur(document.getElementById('iHcp'));
          document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = '18';
          startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); nav('score'); }""")
        await pg.wait_for_timeout(400)
        check("de ronde is gestart op de tee", await pg.evaluate("() => [game.started, game.tee, game.holes[0].id]"), [True, TEE, HOLE])
        await pg.evaluate("() => { for (let h = 0; h < 9; h++) { setCurrentHole(h); selectHole(h); armScoreChange(h, 5); clearScoreTap(false); } }"); await pg.wait_for_timeout(300)
        await schoon("scorekaart")
        check("de scorekaart toont de holenaam als tekst", HOLE in await pg.evaluate("() => document.getElementById('screen-score').textContent"), True)
        check("de ronde-info toont de tee als tekst", TEE in await pg.evaluate("() => document.body.textContent"), True)
        await pg.evaluate("() => switchToPlayer(2)"); await pg.wait_for_timeout(250); await schoon("scorekaart speler 2")
        await pg.evaluate("() => { for (let h = 0; h < 9; h++) { setCurrentHole(h); selectHole(h); armScoreChange(h, 6); clearScoreTap(false); } switchToPlayer(1); }"); await pg.wait_for_timeout(300)
        for tab in ('stat', 'archive'):
            await pg.evaluate("(t) => nav(t)", tab); await pg.wait_for_timeout(300); await schoon(f"tabblad {tab} met lopende ronde")
        await pg.evaluate("() => { nav('score'); finishActiveRound(null); }"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(300)
        await schoon("Rondes na afronden")
        check("de rondekaart toont de tee als tekst", TEE in await pg.evaluate("() => document.getElementById('savedList').textContent"), True)
        await pg.evaluate("() => { document.querySelectorAll('#savedList [onclick]').forEach(e => { const o = e.getAttribute('onclick'); if (/toggle|Collapsed|expand/i.test(o)) { try { e.click(); } catch (x) {} } }); }"); await pg.wait_for_timeout(300)
        await schoon("Rondes, alles uitgeklapt")
        for tab in ('stat', 'club', 'settings', 'setup'):
            await pg.evaluate("(t) => nav(t)", tab); await pg.wait_for_timeout(300); await schoon(f"tabblad {tab}")
        await pg.evaluate("() => { nav('stat'); try { openGameAnalysis(); } catch (e) {} }"); await pg.wait_for_timeout(300); await schoon("spelanalyse")
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]:not(.hidden) button, [id$=Overlay]:not(.hidden) button').forEach(k => { if (/sluiten|×/i.test(k.textContent)) k.click(); }); nav('club'); document.querySelectorAll('#screen-club [onclick*=\"toggleCourseList(\"]').forEach(e => e.click()); document.querySelectorAll('#screen-club [onclick*=\"toggleClubSubGroup(\"]').forEach(e => e.click()); document.querySelectorAll('#screen-club [onclick*=\"toggleCourseAnalysis(\"]').forEach(e => e.click()); }")
        await pg.wait_for_timeout(400); await schoon("Clubs met baananalyse")
        await pg.evaluate("() => { const r = leesRondes()[0]; try { buildScoreText(r); } catch (e) { throw e; } }")

        check("aan het eind: geen fouten in de pagina", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
