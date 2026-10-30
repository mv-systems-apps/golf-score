"""Alles werkt hetzelfde, of speler 1 of speler 2 op het scherm staat.

De regel: wie er op het scorescherm staat is een kwestie van kijken, niet van gegevens.
Een handeling op een ronde — afronden, pauzeren, verwijderen, een andere ronde laden,
de pagina herladen, corrigeren, een nieuwe ronde starten — moet hetzelfde opleveren met
speler 2 op het scherm als met speler 1.

Op 3-10-2026 bleken de twee bewerkschermen ervan uit te gaan dat de ronde op het scherm
altijd die van speler 1 is. Dat is gerepareerd. Deze test controleert de regel voor de
overige handelingen, met echte tikken op de knoppen waar die er zijn.

Per handeling, twee keer (speler 1 en speler 2 op het scherm):
  A  geen gegevens kwijt: scores, putts en notitie van elke overgebleven ronde kloppen
  B  de toestand klopt in zichzelf: wat de app 'actief' en 'gekoppeld' noemt bestaat, en
     de ronde in het geheugen is de ronde die volgens de app op het scherm staat
  C  de uitkomst is in beide opstellingen dezelfde
  D  daarna kun je gewoon verder spelen, en de score komt in de juiste ronde
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, app_url, SEED, ronde
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {str(echt)[:330]} — verwacht {str(verwacht)[:330]}"))
    if not ok: fouten.append(naam)

ANDERE = [ronde(101, "2026-08-01", speler="Testspeler", played=5)]     # een losse, half gespeelde ronde om te laden

# Toestand: gegevens per ronde, wie actief/gekoppeld is, en of dat in zichzelf klopt.
STAAT = """() => {
  const l = leesRondes(), aId = localStorage.getItem('golf_active_id'), gId = localStorage.getItem('golf_game2_id');
  const a = l.find(r => String(r.id) === aId), g = l.find(r => String(r.id) === gId);
  const mis = [];
  if (aId && !a) mis.push('actieve ronde bestaat niet');
  if (gId && !g) mis.push('gekoppelde ronde bestaat niet');
  if (gId && !aId) mis.push('wel gekoppeld, niet actief');
  if (gId && gId === aId) mis.push('actief en gekoppeld zijn dezelfde ronde');
  if (String(game2Id ?? '') !== String(gId ?? '')) mis.push('koppeling in geheugen ' + game2Id + ' wijkt af van opslag ' + gId);
  if (activePlayer === 2 && !gId) mis.push('speler 2 op het scherm zonder koppeling');
  if (!aId && game.started) mis.push('geen actieve ronde, wel een ronde in het geheugen (' + game.player + ')');
  if (aId && !game.started) mis.push('actieve ronde, maar niets in het geheugen');
  const hoort = activePlayer === 2 ? gId : aId;
  if (aId && game.started && String(game.id) !== String(hoort)) mis.push('in het geheugen staat ' + game.player + ', op het scherm hoort ' + ((activePlayer === 2 ? g : a) || {}).player);
  const balk = !document.getElementById('playerSwitchBar')?.classList.contains('hidden');
  return { rondes: l.map(r => [r.player, r.date, r.holes.map(h => h.score ?? '-').join(''), r.holes.map(h => h.putts ?? '-').join(''), r.note ?? null]).sort(),
           actief: a ? a.player : null, gekoppeld: g ? g.player : null, scherm: game.started ? game.player : null, mis }; }"""

async def opzet(pg, speler2):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, ANDERE])
    await pg.evaluate("() => { localStorage.setItem('golf_auto_next', 'off'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
        document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.8';
        player2Visible = true; sel2.gender = 'Dames'; sel2.tee = 'Rood'; document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
        zetStartNote(1, 'notitie Testspeler'); zetStartNote(2, 'notitie Anna'); startRound(); }"""); await pg.wait_for_timeout(300)
    await pg.evaluate("""() => { for (let i = 0; i < 4; i++) { setCurrentHole(i); stepScore(i, +1); } stepPutts(1, +1);
        switchToPlayer(2); for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, +1); stepScore(i, +1); } stepPutts(0, -1); }""")
    if not speler2: await pg.evaluate("() => switchToPlayer(1)")
    # Een laatste wijziging op de ronde die op het scherm staat, vlak voor de handeling.
    await pg.evaluate("() => { const i = game.holes.findIndex(h => h.score == null); setCurrentHole(i); stepScore(i, +1); }")
    await pg.wait_for_timeout(150)

async def tik_tweemaal(pg, selector):
    await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(250)
    knop = pg.locator(selector).first
    await knop.scroll_into_view_if_needed(); await knop.click(); await pg.wait_for_timeout(150); await knop.click(); await pg.wait_for_timeout(300)

async def id_van(pg, speler):
    return await pg.evaluate("(s) => String(leesRondes().find(r => r.player === s && r.note).id)", speler)

async def h_gereed_score(pg):   await pg.evaluate("() => { nav('score'); finishActiveRound(null); }")
async def h_gereed_p1(pg):      await tik_tweemaal(pg, f'button[data-round-id="{await id_van(pg, "Testspeler")}"][onclick^="saveAndClearActiveRound"]')
async def h_gereed_p2(pg):      await tik_tweemaal(pg, f'button[data-round-id="{await id_van(pg, "Anna")}"][onclick^="saveAndClearPlayer2Round"]')
async def h_wis(pg, speler):
    await pg.evaluate("(s) => { nav('archive'); performDeleteRound(leesRondes().findIndex(r => r.player === s && r.note)); }", speler)
async def h_laad(pg):
    await pg.evaluate("() => nav('archive')"); await pg.wait_for_timeout(250)
    i = await pg.evaluate("() => loadSavedRounds().findIndex(r => r.id === 101)")
    await pg.evaluate("(i) => { const k = [...document.querySelectorAll('button')].find(x => x.getAttribute('onclick') === 'loadRound(' + i + ')'); if (k) { k.closest('.hidden')?.classList.remove('hidden'); k.click(); } else loadRound(i); }", i)
async def h_herlaad(pg):        await pg.reload(); await pg.wait_for_timeout(450)
async def h_corrigeer(pg):
    await pg.evaluate("() => { herplanRonde(leesRondes().find(r => r.player === 'Testspeler' && r.note).id, true); }"); await pg.wait_for_timeout(250)
    await pg.locator('#trackList .track-btn', has_text='Sandr').first.click(); await pg.click('#startRoundBtn'); await pg.wait_for_timeout(350)
async def h_nieuw(pg):
    await pg.evaluate("""() => { nav('setup'); if (player2Visible) togglePlayer2(); document.getElementById('iName').value = 'Testspeler';
        document.getElementById('iTime').value = '05:05'; sel.time = '05:05'; sel.date = document.getElementById('iDate').value; sel.dateTimeEdited = true; }""")
    await pg.click('#startRoundBtn'); await pg.wait_for_timeout(250)
    await pg.evaluate("() => { const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"); await pg.wait_for_timeout(300)
async def h_tabs(pg):           await pg.evaluate("() => ['archive', 'stat', 'club', 'settings', 'setup', 'score'].forEach(nav)")
async def h_18(pg):             await pg.evaluate("() => { nav('score'); selectNine(0); toggleScoreButtons(currentHole); toggleScoreButtons(currentHole); }")

HANDELINGEN = [
    ("naar alle tabbladen en terug", h_tabs, 'beide lopen door'),
    ("invoerpaneel open en dicht", h_18, 'beide lopen door'),
    ("Gereed op het scorescherm", h_gereed_score, 'beide losgelaten'),
    ("Gereed op de kaart van speler 1, in Rondes", h_gereed_p1, 'beide losgelaten'),
    ("Gereed op de kaart van speler 2, in Rondes", h_gereed_p2, 'speler 1 loopt door'),
    ("de ronde van speler 2 verwijderen", lambda pg: h_wis(pg, 'Anna'), 'speler 1 loopt door'),
    ("de ronde van speler 1 verwijderen", lambda pg: h_wis(pg, 'Testspeler'), 'speler 2 neemt over'),
    ("een andere ronde laden", h_laad, 'andere ronde actief'),
    ("de pagina herladen", h_herlaad, 'beide lopen door'),
    ("de ronde corrigeren naar een andere baan", h_corrigeer, 'beide op de nieuwe baan'),
    ("een nieuwe ronde starten", h_nieuw, 'nieuwe ronde actief'),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        for naam, doe, bedoeling in HANDELINGEN:
            print(f"\n=== {naam.upper()}  ({bedoeling}) ===\n")
            uit = {}
            for speler2 in (False, True):
                wie = f"speler {2 if speler2 else 1} op het scherm"
                await opzet(pg, speler2)
                voor = await pg.evaluate(STAAT)
                check(f"{wie}: de beginstand klopt in zichzelf", voor['mis'], [])
                await doe(pg); await pg.wait_for_timeout(250)
                await pg.evaluate("() => document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden'))")
                na = await pg.evaluate(STAAT)
                check(f"{wie}: de toestand klopt in zichzelf", na['mis'], [])
                # A: van elke ronde die er vooraf was en er nog is, zijn de gegevens gelijk
                # (bij corrigeren wijzigen baan en dus niets aan scores, putts en notitie).
                kwijt = [r for r in voor['rondes'] if r not in na['rondes'] and any(x[0] == r[0] and x[4] == r[4] for x in na['rondes'])]
                check(f"{wie}: geen gegevens gewijzigd in een ronde die er nog is", kwijt, [])
                uit[speler2] = na
                # D: verder spelen
                if na['scherm']:
                    d = await pg.evaluate("""() => { nav('score'); const wie = game.player, id = game.id, i = game.holes.findIndex(h => h.score == null);
                        if (i < 0) return { wie, vol: true }; setCurrentHole(i); const n0 = leesRondes().find(r => r.id === id).holes.filter(h => h.score != null).length;
                        stepScore(i, +1); const r = leesRondes().find(r => r.id === id);
                        return { wie, erbij: r.holes.filter(h => h.score != null).length - n0, speler: r.player }; }""")
                    check(f"{wie}: verder spelen schrijft in de ronde die op het scherm staat", d.get('vol') or (d['erbij'], d['speler']) == (1, d['wie']), True)
            # C: zelfde uitkomst in beide opstellingen. Vooraf verschilt alleen de ene extra
            # score op de ronde die op het scherm stond; die halen we uit de vergelijking.
            def kern(s): return (s['actief'], s['gekoppeld'], sorted((r[0], r[4] or '') for r in s['rondes']))
            check("dezelfde uitkomst met speler 1 en met speler 2 op het scherm: wie actief en gekoppeld is, en welke rondes er zijn", kern(uit[True]), kern(uit[False]))
            # Wie er op het scherm staat hoort alleen gelijk te zijn als de handeling de ronde
            # zelf raakt; bij alleen rondkijken blijft staan wie er stond.
            if bedoeling != 'beide lopen door' or naam == "de pagina herladen":
                check("en na afloop staat in beide gevallen dezelfde speler op het scherm", uit[True]['scherm'], uit[False]['scherm'])
            else:
                check("wie op het scherm stond, staat er nog", (uit[False]['scherm'], uit[True]['scherm']), ('Testspeler', 'Anna'))
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
