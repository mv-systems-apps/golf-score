"""Mislukt het opslaan, dan blijft alles zoals het was: geen half doorgevoerde handeling.

Vier handelingen waarbij het opslaan tijdens de handeling mislukt (opslag vol of
geblokkeerd, nagebootst):
  a. een nieuwe ronde starten terwijl de lopende ronde scores heeft die nog niet zijn
     opgeslagen: die scores mogen niet verloren gaan;
  b. een andere ronde laden in dezelfde situatie;
  c. je naam wijzigen met 'Alles aanpassen': de melding zegt 'er is niets gewijzigd', dus
     de oude naam blijft ook in je profiel staan;
  d. een club hernoemen: thuisclub, gekozen club en favorieten blijven naar de bestaande
     club wijzen, zodat Start na herladen gewoon banen toont.
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

STORING = """(sleutel) => { window.__echt = window.__echt || Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === sleutel) { const e = new Error('vol'); e.name = 'QuotaExceededError'; throw e; } return window.__echt.call(this, k, v); }; }"""
HERSTEL = "() => { if (window.__echt) Storage.prototype.setItem = window.__echt; }"
DICHT = "() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); document.getElementById('opslagStoringMelding')?.remove(); }"
VENSTER = "() => [...document.querySelectorAll('#confirmModal, #keuzeModal')].filter(m => !m.classList.contains('hidden')).map(m => m.textContent.replace(/\\s+/g, ' ').trim()).join(' | ')"

async def verse(b, rondes, extra=None):
    pg = await b.new_page(viewport={"width": 390, "height": 844}); pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:90]))
    await pg.goto(app_url())
    await pg.evaluate("""([c, r, x]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
      localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_fav_clubs', JSON.stringify(['Golfclub Heelsum']));
      localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_player_name', 'Testspeler'); localStorage.setItem('golf_profile_hcp', '30.7');
      localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_last_backup_date', new Date().toISOString());
      for (const [k, v] of Object.entries(x || {})) localStorage.setItem(k, v); }""", [CLUBS, rondes, extra or {}])
    await pg.reload(); await pg.wait_for_timeout(700); await pg.evaluate(DICHT)
    return pg, pf

def lopend():
    A = ronde(100, '2026-06-01', played=2); A['qualifying'] = False
    B = ronde(101, '2026-06-02', played=9)
    return [A, B]
NIEUWE_SCORES = "() => { for (let i = 2; i < 6; i++) { setCurrentHole(i); stepScore(i, 1); } return game.holes.map(h => h.score); }"
A_OPSLAG = "() => JSON.parse(localStorage.getItem('golf_rounds')).find(r => r.id === 100).holes.map(h => h.score)"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for naam, actie in [('a. EEN NIEUWE RONDE STARTEN', "() => { nav('setup'); document.getElementById('iTime').value = '23:58'; onDateTimeChange(); startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"),
                            ('b. EEN ANDERE RONDE LADEN', "() => { const i = loadSavedRounds().findIndex(r => r.id === 101); loadRoundSingle(i); }")]:
            print(f"\n=== {naam}, TERWIJL DE LOPENDE RONDE NIET KAN WORDEN OPGESLAGEN ===\n")
            pg, pf = await verse(b, lopend(), {'golf_active_id': '100'})
            await pg.evaluate("nav('score')")
            await pg.evaluate(STORING, 'golf_rounds')
            geheugen = await pg.evaluate(NIEUWE_SCORES); await pg.wait_for_timeout(300); await pg.evaluate(DICHT)
            await pg.evaluate(actie); await pg.wait_for_timeout(400)
            v = await pg.evaluate(VENSTER)
            check("je krijgt te horen dat het niet kan, omdat de lopende ronde niet is opgeslagen", 'niet opgeslagen' in v.lower(), True)
            check("de lopende ronde blijft in beeld, met de nieuwe scores", await pg.evaluate("() => [game.id, game.holes.map(h => h.score)]"), [100, geheugen])
            await pg.evaluate(HERSTEL); await pg.evaluate(DICHT); await pg.evaluate("() => saveActiveRound(true)")
            check("is de opslag weer beschikbaar, dan worden die scores alsnog bewaard", await pg.evaluate(A_OPSLAG), geheugen)
            check("geen fouten", pf, [])
            await pg.close()

        print("\n=== c. NAAM WIJZIGEN MET 'ALLES AANPASSEN' ===\n")
        pg, pf = await verse(b, [ronde(1, '2026-05-01'), ronde(2, '2026-05-02')])
        await pg.evaluate("nav('setup')"); await pg.evaluate(STORING, 'golf_rounds')
        await pg.click('#iName'); await pg.fill('#iName', 'Marcus'); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(300)
        await pg.locator('#keuzeModal button:visible', has_text='Alles aanpassen').click(); await pg.wait_for_timeout(300)
        v = await pg.evaluate(VENSTER)
        check("melding: niet opgeslagen, er is niets gewijzigd", 'niets gewijzigd' in v, True)
        await pg.evaluate(HERSTEL)
        check("de rondes staan nog op de oude naam", await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds')).map(r => r.player)"), ['Testspeler', 'Testspeler'])
        check("en het profiel en het naamveld ook", await pg.evaluate("() => [localStorage.getItem('golf_profile_name'), document.getElementById('iName').value]"), ['Testspeler', 'Testspeler'])
        await pg.close()

        print("\n=== d. EEN CLUB HERNOEMEN ===\n")
        pg, pf = await verse(b, [ronde(1, '2026-05-01')])
        VERW = "() => ({ standaard: localStorage.getItem('golf_default_club'), thuis: localStorage.getItem('golf_home_club'), favoriet: localStorage.getItem('golf_fav_clubs') })"
        voor = await pg.evaluate(VERW)
        await pg.evaluate("() => openClubEditor('Golfclub Heelsum')"); await pg.wait_for_timeout(200)
        await pg.evaluate(STORING, 'golf_clubs')
        await pg.evaluate("() => { document.getElementById('editorClubName').value = 'Golfclub Heelsum 2'; saveClubFromEditor(); }"); await pg.wait_for_timeout(300)
        check("thuisclub, gekozen club en favorieten wijzen nog naar de bestaande club", await pg.evaluate(VERW), voor)
        await pg.evaluate(HERSTEL); await pg.reload(); await pg.wait_for_timeout(700)
        check("na herladen toont Start gewoon de banen", sorted(await pg.evaluate("() => Object.keys(COURSES)")), sorted(CLUBS['Golfclub Heelsum']['courses']))
        check("geen fouten", pf, [])

        print("\n=== e. NIEUWE RONDE STARTEN BIJ EEN VOLLE OPSLAG: DE HELE TOESTAND BLIJFT ===\n")
        # 'Vol' zoals bij een opslag die net vol is: de lopende ronde bijwerken lukt nog,
        # een ronde erbij niet. Zo komt de start voorbij het bewaren van de lopende ronde
        # en faalt hij precies op het opslaan van de nieuwe. De toestand wordt vlak vóór het starten vastgelegd: het scherm, het
        # geheugen en de volledige opslag. Na de mislukte start moet alles gelijk zijn.
        VOL = """() => { window.__echt = window.__echt || Storage.prototype.setItem; Storage.prototype.setItem = function (k, v) {
          if (k === 'golf_rounds' && JSON.parse(v).length > JSON.parse(localStorage.getItem('golf_rounds') || '[]').length) { const e = new Error('vol'); e.name = 'QuotaExceededError'; throw e; }
          return window.__echt.call(this, k, v); }; }"""
        TOESTAND = """() => ({
          scherm: [...document.querySelectorAll('.screen')].filter(e => e.classList.contains('active')).map(e => e.id).join(),
          kop: ['hdrTrack', 'hdrRoundName'].map(id => (document.getElementById(id) || {}).textContent || ''),
          geheugen: JSON.stringify({ game, currentHole, activePlayer, game2Id, player2Visible, herplan: _herplanIds, corr: !!_corrigeerScores }),
          opslag: Object.keys(localStorage).filter(k => k.startsWith('golf_')).sort().map(k => [k, localStorage.getItem(k)]) })"""
        def met_scores(rid, datum, gespeeld):
            r = ronde(rid, datum, played=gespeeld); r['qualifying'] = False; return r
        GEVALLEN = [
            ('één speler, met een lopende ronde', [met_scores(100, '2026-06-01', 4)], {'golf_active_id': '100'}, "() => {}"),
            ('twee spelers, met een lopende ronde voor beiden', [met_scores(100, '2026-06-01', 4), dict(met_scores(101, '2026-06-01', 4), player='Anna')],
             {'golf_active_id': '100', 'golf_game2_id': '101', 'golf_player2_visible': '1', 'golf_profile_name2': 'Anna', 'golf_profile_hcp2': '20.0'}, "() => {}"),
            ('corrigeren van een gespeelde ronde', [ronde(50, '2026-05-10')], {}, "() => { corrigeerRonde('50'); const k = document.getElementById('keuzeModalKnop2'); if (k && !document.getElementById('keuzeModal').classList.contains('hidden')) k.click(); }"),
            ('herplannen van een geplande ronde', [dict(ronde(60, '2027-04-01', played=0), qualifying=True)], {}, "() => { herplanRonde('60'); }"),
        ]
        for naam, rondes, extra, voorbereiding in GEVALLEN:
            pg, pf = await verse(b, rondes, extra)
            await pg.evaluate(voorbereiding); await pg.wait_for_timeout(300); await pg.evaluate(DICHT)
            await pg.evaluate("() => { nav('setup'); document.getElementById('iTime').value = '23:58'; onDateTimeChange(); }"); await pg.wait_for_timeout(200)
            voor = await pg.evaluate(TOESTAND)
            await pg.evaluate(VOL)
            await pg.evaluate("() => { startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden') && document.getElementById('confirmModalTitle').textContent !== 'Niet opgeslagen') cb.click(); }")
            await pg.wait_for_timeout(400)
            v = await pg.evaluate(VENSTER)
            na = await pg.evaluate(TOESTAND)
            check(f"{naam}: melding dat starten nu niet kan", 'kan nu niet' in v, True)
            check(f"{naam}: het scherm is gelijk", (na['scherm'], na['kop']), (voor['scherm'], voor['kop']))
            check(f"{naam}: het geheugen is gelijk", na['geheugen'] == voor['geheugen'], True)
            # De lopende ronde wordt vóór de start bewaard zoals hij in beeld staat (versie 130);
            # daarbij vallen afgeleide velden weg (totalStb, currentHole). Vergeleken wordt daarom
            # de inhoud die telt: welke rondes er zijn, en per ronde speler, datum, baan, tee,
            # qualifying en alle scores en putts.
            def kern(lijst):
                return sorted((r.get('id'), r.get('player'), r.get('date'), r.get('time'), r.get('track'), r.get('tee'), r.get('qualifying'),
                               tuple((h.get('score'), h.get('putts')) for h in r.get('holes', []))) for r in lijst)
            andere = lambda t: [x for x in t['opslag'] if x[0] != 'golf_rounds']
            rondes = lambda t: kern(json.loads(dict(t['opslag']).get('golf_rounds', '[]')))
            check(f"{naam}: de opslag is gelijk (rondes naar inhoud, al het andere letterlijk)", ([x for x in andere(na) if x not in andere(voor)] + [x for x in andere(voor) if x not in andere(na)], rondes(na) == rondes(voor)), ([], True))
            check(f"{naam}: geen fouten", pf, [])
            await pg.close()
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN)" if fouten else "\nGEEN FOUTEN"); sys.exit(1 if fouten else 0)
asyncio.run(main())
