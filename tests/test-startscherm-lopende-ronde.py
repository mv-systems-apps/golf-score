"""Het startscherm mag een lopende ronde nooit beïnvloeden.

Marks regel. Twee keer bleek er toch een weg te bestaan: de baanhandicap werd opnieuw
berekend zodra de baan op het startscherm overeenkwam, en later bleken naam en handicap
uit het startscherm in de lopende ronde te worden geschreven (bij speler 2 op het scherm
kreeg ZIJN ronde de naam van speler 1). Eén voor één repareren vangt de volgende niet.

Deze test loopt daarom ELKE bediening van het startscherm langs, met een lopende ronde
van twee spelers, en vergelijkt na elke handeling de volledige ronde — in het geheugen
en in de opslag — met hoe hij ervoor was. Zowel met speler 1 als met speler 2 op het
scherm. Alleen 'Start' zelf hoort een ronde te raken en doet hier niet mee.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {echt} — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
def ids(l, n=9): return [f"{l}{i}" for i in range(1, n + 1)]
CLUBS = {
  "Club A": {"club": "Club A", "shortName": "A", "courses": {
    "Noord": {"holeIds": ids('A'), "tees": {"Heren": {"Geel": tee(35.0, 120, PA), "Wit": tee(36.4, 128, PA)}, "Dames": {"Rood": tee(36.5, 126, PA)}}},
    "Zuid":  {"holeIds": ids('Z'), "tees": {"Heren": {"Geel": tee(33.1, 112, PB)}, "Dames": {"Rood": tee(34.0, 115, PB)}}},
    "Groot": {"holeIds": ids('G', 18), "tees": {"Heren": {"Geel": tee(70.4, 124, PA + PA)}}},
    "Kort":  {"holeIds": ids('K'), "tees": {"Heren": {"Geel": tee(25.0, 76, [3] * 9)}}},
    "Lus":   {"holeIds": ids('L'), "lus": True, "tees": {"Heren": {"Geel": tee(34.1, 118, PB)}}}}},
  "Club B": {"club": "Club B", "shortName": "B", "courses": {
    "Noord": {"holeIds": ids('B'), "tees": {"Heren": {"Geel": tee(38.0, 139, PB)}}}}},
}

# De volledige lopende ronde: wat er in het geheugen staat, en wat er is opgeslagen.
FOTO = """() => { const vast = o => JSON.stringify(o, Object.keys(o).sort());
  const r = leesRondes().map(x => JSON.stringify(x, (k, v) => (k === '_initScore' ? undefined : v)));
  return { opslag: r.sort(), geheugen: JSON.stringify({ ...game, holes: game.holes.map(h => ({ ...h, _initScore: undefined })) }),
    actief: localStorage.getItem('golf_active_id'), g2: localStorage.getItem('golf_game2_id'), speler: activePlayer, hole: currentHole }; }"""

SLUIT = """() => { ['confirmModal', 'infoModal', 'keuzeModal', 'clubSearchModal', 'chcpPctModal', 'player2Modal'].forEach(id => {
    const m = document.getElementById(id); if (m && !m.classList.contains('hidden')) m.classList.add('hidden'); }); }"""

async def typ(pg, veld, tekst):
    # Echte gebeurtenissen op het veld: focus, invoer, verlaten. Zo lopen de eigen
    # afhandelaars van het veld, ook als de kaart van speler 2 op dat moment dicht is.
    await pg.evaluate("""([veld, tekst]) => { const el = document.querySelector(veld);
        el.dispatchEvent(new Event('focus')); el.value = tekst;
        el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur')); }""", [veld, tekst])
    await pg.wait_for_timeout(120)

# (omschrijving, handeling). Een str is JavaScript; een functie krijgt de pagina.
HANDELINGEN = [
    ("naam van speler 1 wijzigen",        lambda pg: typ(pg, '#iName', 'Gast')),
    ("handicap van speler 1 wijzigen",    lambda pg: typ(pg, '#iHcp', '4.0')),
    ("handicap terug naar berekend",      "() => resetHcpToComputed()"),
    ("naam van speler 2 wijzigen",        lambda pg: typ(pg, '#iName2', 'Iemand')),
    ("handicap van speler 2 wijzigen",    lambda pg: typ(pg, '#iHcp2', '36.0')),
    ("speler 2 invullen: favoriet",       "() => fillPlayer2('fav')"),
    ("speler 2 invullen: standaard",      "() => fillPlayer2('default')"),
    ("datum en tijd wijzigen",            "() => { document.getElementById('iDate').value = '2027-03-04'; document.getElementById('iTime').value = '07:15'; onDateTimeChange(); }"),
    ("datum en tijd op nu",               "() => setDateTimeNow([...document.querySelectorAll('button')].find(b => (b.getAttribute('onclick') || '').startsWith('setDateTimeNow')))"),
    ("andere baan aantikken",             "() => [...document.querySelectorAll('#trackList .track-btn')].find(b => b.textContent.includes('Zuid')).click()"),
    ("filter 18 holes",                   "() => selectHoleCount('18')"),
    ("filter 9 holes",                    "() => selectHoleCount('9')"),
    ("filter par 3",                      "() => togglePar3()"),
    ("filter par 3 weer uit",             "() => togglePar3()"),
    ("kop Wedstrijdlussen open",          "() => toggleLusKop()"),
    ("wedstrijdlus aantikken",            "() => [...document.querySelectorAll('#trackList .track-btn')].find(b => b.textContent.includes('Lus'))?.click()"),
    ("geslacht speler 1: Dames",          "() => selectGender('Dames')"),
    ("geslacht speler 1: Heren",          "() => selectGender('Heren')"),
    ("andere tee aantikken",              "() => { [...document.querySelectorAll('#trackList .track-btn')].find(b => b.textContent.includes('Noord')).click(); [...document.querySelectorAll('#teeBtns button')].find(b => b.textContent.includes('Wit'))?.click(); }"),
    ("geslacht speler 2: Heren",          "() => selectGender2('Heren')"),
    ("tee speler 2 aantikken",            "() => document.querySelector('#teeBtns2 button')?.click()"),
    ("baanhandicap +1",                   "() => adjustChcp(1)"),
    ("baanhandicap -1 (twee keer)",       "() => { adjustChcp(-1); adjustChcp(-1); }"),
    ("baanhandicap herstellen",           "() => resetChcpOverride()"),
    ("baanhandicap speler 2 +1",          "() => adjustChcp2(1)"),
    ("baanhandicap speler 2 herstellen",  "() => resetChcp2Override()"),
    ("handicappercentage openen",         "() => openChcpPercentage()"),
    ("qualifying speler 1 aan",           "() => { const t = document.getElementById('qualifyToggle1'); t.checked = !t.checked; toggleQualifying(1); }"),
    ("qualifying speler 2 om",            "() => { const t = document.getElementById('qualifyToggle2'); t.checked = !t.checked; toggleQualifying(2); }"),
    ("notitie speler 1 typen",            "() => { toggleStartNote(1); const v = document.getElementById('startNote1'); v.value = 'voor de volgende ronde'; groeiStartNote(v); }"),
    ("notitie speler 2 typen",            "() => { toggleStartNote(2); const v = document.getElementById('startNote2'); v.value = 'ook'; groeiStartNote(v); }"),
    ("andere club via het zoekvenster",   "() => { openClubSearchModal(); selectClubSearchCandidate('Club B'); confirmClubSearchModal(); }"),
    ("terug met de thuisclubknop",        "() => useHomeClub()"),
    ("speler 2 uitzetten",                "() => togglePlayer2()"),
    ("speler 2 weer aanzetten",           "() => togglePlayer2()"),
    ("naar een ander tabblad en terug",   "() => { nav('settings'); nav('stat'); nav('club'); nav('archive'); nav('setup'); }"),
]

async def opzet(pg, speler2):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, []])
    await pg.evaluate("""() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A');
        localStorage.setItem('golf_fav_player2_name', 'Favoriet'); localStorage.setItem('golf_fav_player2_hcp', '18');
        localStorage.setItem('golf_default_player2_name', 'Standaard'); localStorage.setItem('golf_default_player2_hcp', '28'); }""")
    await pg.reload(); await pg.wait_for_timeout(400)
    await pg.evaluate("""() => { nav('setup'); sel.track = 'Noord'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true;
        document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8';
        player2Visible = true; sel2.gender = 'Dames'; sel2.tee = 'Rood'; sel2._teeUserSelected = true;
        document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
        zetStartNote(1, 'notitie Mark'); zetStartNote(2, 'notitie Anna'); startRound(); }"""); await pg.wait_for_timeout(300)
    await pg.evaluate("() => { for (let i = 0; i < 3; i++) { setCurrentHole(i); stepScore(i, +1); } switchToPlayer(2); for (let i = 0; i < 2; i++) { setCurrentHole(i); stepScore(i, +1); } }")
    if not speler2: await pg.evaluate("() => switchToPlayer(1)")
    await pg.evaluate("() => nav('setup')"); await pg.wait_for_timeout(200)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        for speler2 in (False, True):
            print(f"\n=== LOPENDE RONDE VAN TWEE SPELERS, SPELER {2 if speler2 else 1} OP HET SCHERM ===\n")
            await opzet(pg, speler2)
            foto = await pg.evaluate(FOTO)
            check("de ronde loopt, met scores van beide spelers", (len(foto['opslag']), foto['speler'], foto['g2'] is not None), (2, 2 if speler2 else 1, True))
            for naam, doe in HANDELINGEN:
                if isinstance(doe, str): await pg.evaluate(doe)
                else: await doe(pg)
                await pg.wait_for_timeout(120); await pg.evaluate(SLUIT)
                na = await pg.evaluate(FOTO)
                verschil = [k for k in foto if foto[k] != na[k]]
                check(naam, verschil, [])
                if verschil:                       # opnieuw beginnen, zodat de volgende handeling zuiver is
                    await opzet(pg, speler2); foto = await pg.evaluate(FOTO)
            # En de ronde is daarna gewoon verder te spelen.
            await pg.evaluate("() => { nav('score'); setCurrentHole(game.holes.findIndex(h => h.score == null)); stepScore(currentHole, +1); }")
            check("daarna gewoon verder spelen", await pg.evaluate("() => leesRondes().map(r => [r.player, r.holes.filter(h => h.score != null).length]).sort()"),
                  [['Anna', 3], ['Mark', 3]] if speler2 else [['Anna', 2], ['Mark', 4]])
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
