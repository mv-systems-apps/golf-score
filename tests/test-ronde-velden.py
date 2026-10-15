"""Geen enkel veld van een ronde valt onderweg weg.

De notitie verdween ooit omdat de app een ronde op meerdere plekken opnieuw opbouwt uit
een vaste lijst velden; een veld dat op één plek ontbreekt, is daarna stil weg. Dat is
per veld gerepareerd en getest (notitie, wedstrijdlus). Deze test doet het in één keer
voor ALLE velden: een ronde waarin elk veld een herkenbare waarde heeft, gaat door elke
route waarlangs de app een ronde leest en weer wegschrijft. Na elke route moet de ronde
gelijk zijn.

De veldenlijst komt uit Marks echte rondes: alle velden die daar voorkomen doen mee.
Daarnaast heeft de ronde een veld dat de app NIET kent ('toekomst', en 'extra' op een
hole). Ook dat moet overal blijven staan: de app neemt een ronde in zijn geheel over en
werkt alleen bij wat verandert. Zo kan een veld dat later wordt toegevoegd niet stil
verdwijnen omdat het op één plek is vergeten.
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

PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
TEES = {"Heren": {"Geel": {"CR": 35.0, "SR": 120, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(PARS)]}}}
CLUBS = {"Club A": {"club": "Club A", "shortName": "A", "courses": {"Noord": {"holeIds": [f"A{i}" for i in range(1, 10)], "tees": TEES}}}}

def vol(rid, speler, tijd="09:10", gespeeld=6):
    """Een ronde waarin elk veld een eigen, herkenbare waarde heeft."""
    holes = []
    for i, p in enumerate(PARS):
        h = {"id": f"A{i+1}", "par": p, "si": 9 - i, "phcp": 2 if i < 4 else 1, "ppar": p + (2 if i < 4 else 1), "score": None}
        if i < gespeeld: h["score"] = p + (i % 3); h["putts"] = (i % 4)
        if i == 0: h["extra"] = "ook per hole"
        holes.append(h)
    return {"id": rid, "date": "2026-09-12", "time": tijd, "player": speler, "hcp": 17.3, "gender": "Heren", "track": "Noord", "tee": "Geel",
            "club": "Club A", "clubShort": "A", "CR": 34.7, "SR": 123, "PAR": 36, "chcp": 13, "pcc": 1, "sdFinal": 33.3, "qualifying": True,
            "note": f"notitie {speler}", "lus": True, "toekomst": "een veld dat de app nog niet kent", "started": True, "holesCount": 9, "currentHole": 6,
            "total": sum(h["score"] or 0 for h in holes), "totalStb": 0, "holes": holes}

# Alles wat de ronde IS. Afgeleide en vluchtige velden doen niet mee: totalen worden
# herberekend, currentHole en started horen bij het scherm, id wijzigt bij inlezen.
KERN = """(metId) => leesRondes().filter(r => ['Mark', 'Anna'].includes(r.player)).map(r => {
    const { total, totalStb, playedCount, holesCount, currentHole, started, _justImported, sd, id, ...rest } = r;
    const o = { ...rest, holes: r.holes.map(({ _initScore, ...h }) => Object.fromEntries(Object.entries(h).sort())) };
    if (metId) o.id = id;
    return JSON.stringify(Object.fromEntries(Object.entries(o).sort())); }).sort()"""

async def schoon(pg, rondes):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, rondes])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
    await pg.reload(); await pg.wait_for_timeout(400)

def hoort(*rondes, met_id=True):
    uit = []
    for r in rondes:
        o = {k: v for k, v in r.items() if k not in ('total', 'totalStb', 'playedCount', 'holesCount', 'currentHole', 'started', 'id')}
        o['holes'] = [dict(sorted(h.items())) for h in r['holes']]
        if met_id: o['id'] = r['id']
        uit.append(json.dumps(dict(sorted(o.items())), separators=(',', ':'), ensure_ascii=False))
    return sorted(uit)

def verschil(echt, verwacht):
    """Welke velden wijken af? Leesbaarder dan twee lange regels tekst."""
    uit = []
    for e, v in zip(echt, verwacht):
        e, v = json.loads(e), json.loads(v)
        for k in sorted(set(e) | set(v)):
            if k == 'holes':
                for i, (he, hv) in enumerate(zip(e.get('holes', []), v.get('holes', []))):
                    for hk in sorted(set(he) | set(hv)):
                        if he.get(hk, '∅') != hv.get(hk, '∅'): uit.append(f"{v.get('player')} hole {i+1} {hk}: {he.get(hk, 'WEG')} i.p.v. {hv.get(hk, 'afwezig')}")
            elif e.get(k, '∅') != v.get(k, '∅'): uit.append(f"{v.get('player')} {k}: {e.get(k, 'WEG')} i.p.v. {v.get(k, 'afwezig')}")
    if len(echt) != len(verwacht): uit.append(f"aantal rondes {len(echt)} i.p.v. {len(verwacht)}")
    return uit

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
        M, A = vol(7001, 'Mark'), vol(7002, 'Anna')

        async def route(naam, js, rondes=(M, A), met_id=True, wacht=250):
            if js: await pg.evaluate(js)
            await pg.wait_for_timeout(wacht)
            check(naam, verschil(await pg.evaluate(KERN, met_id), hoort(*rondes, met_id=met_id)), [])

        print("\n=== 1. ÉÉN RONDE: LADEN, OPSLAAN, HERLADEN, AFRONDEN ===\n")
        await schoon(pg, [M])
        await route("zoals opgeslagen", None, (M,))
        await route("laden als lopende ronde", "() => loadRound(0)", (M,))
        await route("opslaan tijdens het spelen", "() => saveActiveRound(true)", (M,))
        await pg.reload(); await pg.wait_for_timeout(400)
        await route("na herladen en opnieuw opslaan", "() => saveActiveRound(true)", (M,))
        await route("naar het scorescherm en terug", "() => { nav('score'); nav('setup'); nav('archive'); }", (M,))
        await route("Ronde bewerken, zonder iets te wijzigen", "() => { doOpenRoundInfoModal(0); confirmRoundInfo(); }", (M,))
        await route("Vaststellen, zonder iets te wijzigen", "() => { doOpenRoundResultModal(0); confirmRoundResult(); }", (M,))
        await route("afronden", "() => finishActiveRound(null)", (M,))
        await route("losse ronde bewerken, zonder wijziging", "() => { doOpenRoundInfoModal(0); confirmRoundInfo(); }", (M,))
        await route("losse ronde vaststellen, zonder wijziging", "() => { doOpenRoundResultModal(0); confirmRoundResult(); }", (M,))

        print("\n=== 2. TWEE GEKOPPELDE RONDES: WISSELEN, HERLADEN, AFRONDEN ===\n")
        await schoon(pg, [M, A])
        await pg.evaluate("() => loadRoundAsCouple(leesRondes().findIndex(r => r.player === 'Mark'), leesRondes().find(r => r.player === 'Anna').id)"); await pg.wait_for_timeout(250)
        await route("gekoppeld geladen", None)
        await route("naar speler 2", "() => switchToPlayer(2)")
        await route("opslaan met speler 2 op het scherm", "() => saveActiveRound(true)")
        await route("terug naar speler 1", "() => switchToPlayer(1)")
        await pg.evaluate("() => switchToPlayer(2)"); await pg.reload(); await pg.wait_for_timeout(400)
        await route("herladen met speler 2 op het scherm", None)
        await route("daarna wisselen en opslaan", "() => { switchToPlayer(2); saveActiveRound(true); switchToPlayer(1); saveActiveRound(true); }")
        await route("bewerken en vaststellen van speler 2, zonder wijziging", """() => { const i = leesRondes().findIndex(r => r.player === 'Anna');
            doOpenRoundInfoModal(i); confirmRoundInfo(); doOpenRoundResultModal(i); confirmRoundResult(); }""")
        await route("afronden", "() => finishActiveRound(null)")

        print("\n=== 3. BACKUP, TERUGZETTEN EN INLEZEN ===\n")
        # Alleen helemaal ingevulde rondes horen in de backup; daarom hier twee volle rondes.
        M, A = vol(7001, 'Mark', gespeeld=9), vol(7002, 'Anna', gespeeld=9)
        await schoon(pg, [M, A])
        tekst = await pg.evaluate("async () => { let uit = null; window.tryWriteToExportFolder = async (n, j) => { uit = j; return true; }; await exportAllRounds(); return uit; }")
        check("de backup bevat beide rondes", len(json.loads(tekst or '[]')), 2)
        await route("volledig terugzetten", f"() => doFullRestoreImport({tekst})", rondes=(M, A), met_id=False)
        await pg.evaluate("() => { metVerwijderen(() => setRoundsAndMark('[]')); }")
        await route("toevoegen uit hetzelfde bestand", f"() => doAdditiveImport({tekst})", rondes=(M, A), met_id=False)
        await schoon(pg, [])
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_velden.json'); open(pad, 'w', encoding='utf-8').write(tekst)
        await pg.evaluate("() => nav('settings')"); await pg.locator('#importRoundFile').set_input_files(pad); await pg.wait_for_timeout(600); os.remove(pad)
        await pg.evaluate("""() => { document.querySelectorAll('[id$=Modal]:not(.hidden) button').forEach(k => { if (/toevoegen|herstel|importeer|ok/i.test(k.textContent)) k.click(); }); }""")
        await pg.wait_for_timeout(400)
        await route("inlezen via het echte bestandsveld", None, rondes=(M, A), met_id=False)
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden')); loadRound(leesRondes().findIndex(r => r.player === 'Mark')); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden')); }")
        await route("een ingelezen ronde laden en opslaan", "() => saveActiveRound(true)", rondes=(M, A), met_id=False)

        print("\n=== 4. ER KOMT OOK NIETS BIJ ===\n")
        # Sinds de app een ronde in zijn geheel overneemt, komt alles wat in de lopende ronde
        # in het geheugen staat ook in de opslag en in de backup. Iets tijdelijks hoort daar
        # dus niet in. Hier: een ronde echt starten en spelen, met twee spelers, en daarna
        # mogen er alleen de bekende velden in de opslag staan.
        RONDEVELDEN = {'id', 'date', 'time', 'player', 'hcp', 'gender', 'track', 'tee', 'club', 'clubShort', 'CR', 'SR', 'PAR', 'chcp',
                       'pcc', 'sdFinal', 'qualifying', 'note', 'lus', 'started', 'total', 'holesCount', 'currentHole', 'holes'}
        HOLEVELDEN = {'id', 'par', 'si', 'phcp', 'ppar', 'score', 'putts', '_initScore'}
        await schoon(pg, [])
        await pg.evaluate("""() => { nav('setup'); sel.track = 'Noord'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true;
            document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '24.0';
            player2Visible = true; sel2.gender = 'Heren'; sel2.tee = 'Geel'; sel2._teeUserSelected = true;
            document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20';
            zetStartNote(1, 'n'); startRound(); }"""); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { for (let i = 0; i < 9; i++) { setCurrentHole(i); stepScore(i, +1); stepPutts(i, +1); }
            switchToPlayer(2); for (let i = 0; i < 9; i++) { setCurrentHole(i); stepScore(i, +1); } armScoreChange(8, 7); clearScoreTap(false); setDoubleBogey(3);
            switchToPlayer(1); nav('setup'); nav('archive'); nav('stat'); nav('score'); }""")
        await pg.reload(); await pg.wait_for_timeout(400)
        await pg.evaluate("""() => { stepScore(currentHole, -1); switchToPlayer(2); switchToPlayer(1);
            const i = leesRondes().findIndex(r => r.player === 'Mark'); doOpenRoundInfoModal(i); confirmRoundInfo(); doOpenRoundResultModal(i); confirmRoundResult(); finishActiveRound(null); }""")
        await pg.wait_for_timeout(200)
        velden = await pg.evaluate("() => { const l = JSON.parse(localStorage.getItem('golf_rounds')); return { ronde: [...new Set(l.flatMap(r => Object.keys(r)))], hole: [...new Set(l.flatMap(r => r.holes.flatMap(h => Object.keys(h))))], n: l.length }; }")
        check("twee rondes gespeeld en afgerond", velden['n'], 2)
        check("geen onbekende velden in de ronde", sorted(set(velden['ronde']) - RONDEVELDEN), [])
        check("geen onbekende velden per hole", sorted(set(velden['hole']) - HOLEVELDEN), [])

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
