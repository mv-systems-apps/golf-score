"""Een ronde onthoudt zelf dat hij op een wedstrijdlus is gespeeld.

Marks keuze: de markering in de ronde bewaren, omdat een lus tijdelijk is en na afloop
kan worden verwijderd. Met alleen opzoeken bij de baan zou de ronde dan weer als gewone
baan in het overzicht per baan verschijnen.

De app bouwt een ronde op vijf plekken opnieuw op uit een vaste lijst velden; een veld
dat op één plek ontbreekt verdwijnt stil (zo raakten eerder notities kwijt). Deze test
loopt daarom elke route langs: starten met één en twee spelers, herladen, wisselen van
speler, afronden, bewerken, opnieuw laden, corrigeren, backup en terugzetten.
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url, SEED, ronde
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt}" + ('' if ok else f" — verwacht {verwacht}"))
    if not ok: fouten.append(naam)

def holes(pars): return [{"par": p, "si": i + 1} for i, p in enumerate(pars)]
H = holes([4, 3, 5, 4, 4, 3, 4, 5, 4])
TEES = {"Heren": {"Rood": {"CR": 33.9, "SR": 119, "holes": H}}, "Dames": {"Rood": {"CR": 36.4, "SR": 131, "holes": H}}}
CLUBS = {"Lusclub": {"club": "Lusclub", "shortName": "Lus", "courses": {
    "Oost": {"holeIds": [f"O{i}" for i in range(1, 10)], "tees": TEES},
    "Maanlus": {"holeIds": [f"M{i}" for i in range(1, 10)], "tees": TEES, "lus": True},
}}}

# Per ronde van de proefspelers: [speler, baan, markering zoals OPGESLAGEN, isLusRonde]
STAND = """() => leesRondes().filter(r => ['Mark', 'Anna'].includes(r.player) && r.id > 5000)
    .map(r => [r.player, r.track, r.lus ?? null, isLusRonde(r)]).sort()"""

async def schoon(pg, rondes=None):
    await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, rondes or []])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Lusclub'); localStorage.setItem('golf_home_club', 'Lusclub'); }")
    await pg.reload(); await pg.wait_for_timeout(400)

async def start(pg, baan, twee=False):
    await pg.evaluate("""([baan, twee]) => { nav('setup'); sel.track = baan; sel.gender = 'Heren'; sel.tee = 'Rood'; sel._teeUserSelected = true;
        document.getElementById('iName').value = 'Mark'; document.getElementById('iHcp').value = '30.8';
        player2Visible = twee; if (twee) { sel2.gender = 'Dames'; sel2.tee = 'Rood'; sel2._teeUserSelected = true;
            document.getElementById('iName2').value = 'Anna'; document.getElementById('iHcp2').value = '20'; }
        startRound(); const cb = document.getElementById('confirmModalBtn');
        if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }""", [baan, twee])
    await pg.wait_for_timeout(300)

VUL = "(n) => { for (let i = 0; i < Math.min(n, game.holes.length); i++) { setCurrentHole(i); if (game.holes[i].score == null) stepScore(i, +1); } }"
LUS1 = [['Mark', 'Maanlus', True, True]]
LUS2 = [['Anna', 'Maanlus', True, True], ['Mark', 'Maanlus', True, True]]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:150]))

        print("\n=== 1. ÉÉN SPELER: VAN STARTEN TOT OPNIEUW LADEN ===\n")
        await schoon(pg); await start(pg, 'Maanlus')
        check("gestart", await pg.evaluate(STAND), LUS1)
        await pg.evaluate(VUL, 3)
        check("na scores", await pg.evaluate(STAND), LUS1)
        await pg.reload(); await pg.wait_for_timeout(400); await pg.evaluate(VUL, 5)
        check("na herladen en nog een score", await pg.evaluate(STAND), LUS1)
        await pg.evaluate(VUL, 9); await pg.evaluate("() => finishActiveRound(null)")
        check("afgerond", await pg.evaluate(STAND), LUS1)
        await pg.evaluate("""() => { const i = leesRondes().findIndex(r => r.player === 'Mark');
            doOpenRoundInfoModal(i); document.getElementById('editNoteInput').value = 'maan'; confirmRoundInfo();
            doOpenRoundResultModal(i); confirmRoundResult(); }"""); await pg.wait_for_timeout(200)
        check("na Ronde bewerken en Vaststellen", await pg.evaluate(STAND), LUS1)
        await pg.evaluate("() => loadRound(leesRondes().findIndex(r => r.player === 'Mark'))"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => stepScore(currentHole, +1)"); await pg.evaluate("() => finishActiveRound(null)")
        check("opnieuw geladen, score gewijzigd, afgerond", await pg.evaluate(STAND), LUS1)

        print("\n=== 2. BACKUP EN TERUGZETTEN ===\n")
        tekst = await pg.evaluate("""async () => { let uit = null; window.tryWriteToExportFolder = async (n, j) => { uit = j; return true; }; await exportAllRounds(); return uit; }""")
        check("de markering staat in het backupbestand", [r.get('lus') for r in json.loads(tekst)], [True])
        await pg.evaluate("(t) => { doFullRestoreImport(JSON.parse(t)); }", tekst); await pg.wait_for_timeout(300)
        check("na volledig terugzetten", await pg.evaluate("() => leesRondes().map(r => [r.player, r.track, r.lus ?? null])"), [['Mark', 'Maanlus', True]])

        print("\n=== 3. DE LUS IS VERWIJDERD: DE RONDE BLIJFT EEN WEDSTRIJDLUSRONDE ===\n")
        await pg.evaluate("() => { delete CLUBS['Lusclub'].courses['Maanlus']; rebuildCourseLookup(); rebuildAll(); }")
        await pg.reload(); await pg.wait_for_timeout(400)
        check("de baan bestaat niet meer", await pg.evaluate("() => !!CLUBS['Lusclub'].courses['Maanlus']"), False)
        check("de ronde telt nog als wedstrijdlus", await pg.evaluate("() => leesRondes().map(isLusRonde)"), [True])
        await pg.evaluate("() => { localStorage.setItem('golf_stats_grp_banen', 'open'); localStorage.setItem('golf_min_rounds_stat', '1'); window._statClubCollapsed = { Lusclub: false }; nav('stat'); renderPlayerStats(); }")
        await pg.wait_for_timeout(300)
        check("en staat niet in het overzicht per baan", 'Maanlus' in await pg.evaluate("() => document.getElementById('screen-stat').textContent"), False)

        print("\n=== 4. TWEE SPELERS, MET WISSELEN EN HERLADEN ===\n")
        await schoon(pg); await start(pg, 'Maanlus', twee=True)
        check("gestart", await pg.evaluate(STAND), LUS2)
        await pg.evaluate(VUL, 2); await pg.evaluate("() => switchToPlayer(2)"); await pg.evaluate(VUL, 2)
        await pg.evaluate("() => switchToPlayer(1)"); await pg.evaluate(VUL, 3)
        check("na scores en twee keer wisselen", await pg.evaluate(STAND), LUS2)
        await pg.reload(); await pg.wait_for_timeout(400)
        await pg.evaluate("() => switchToPlayer(2)"); await pg.evaluate(VUL, 4); await pg.evaluate("() => switchToPlayer(1)")
        check("na herladen, wisselen en scores", await pg.evaluate(STAND), LUS2)

        print("\n=== 5. CORRIGEREN: DE MARKERING VOLGT DE NIEUWE BAAN ===\n")
        await schoon(pg); await start(pg, 'Maanlus'); await pg.evaluate(VUL, 4)
        await pg.evaluate("() => herplanRonde(leesRondes().find(r => r.player === 'Mark').id, true)"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { sel.holeCount = null; buildTrackList(); [...document.querySelectorAll('#trackList .track-btn')].find(b => b.textContent.includes('Oost')).click(); }")
        await pg.evaluate("""() => { startRound(); const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click(); }"""); await pg.wait_for_timeout(300)
        check("van lus naar gewone baan: markering weg", await pg.evaluate(STAND), [['Mark', 'Oost', None, False]])

        print("\n=== 6. GEWONE RONDES KRIJGEN HET VELD NIET ===\n")
        await schoon(pg); await start(pg, 'Oost', twee=True); await pg.evaluate(VUL, 2)
        await pg.reload(); await pg.wait_for_timeout(400); await pg.evaluate(VUL, 3)
        check("geen veld 'lus' in de opgeslagen rondes",
              await pg.evaluate("() => JSON.parse(localStorage.getItem('golf_rounds')).some(r => 'lus' in r)"), False)

        print("\n=== 7. ALLEEN DE RONDE TELT, NIET DE BAAN ===\n")
        # Een ronde zonder markering is geen wedstrijdlusronde, ook als de baan er een is.
        # Er bestaan geen oudere rondes op een wedstrijdlus, dus er is geen vangnet (Marks keuze).
        await schoon(pg, [ronde(777, "2026-09-15", baan="Maanlus", club="Lusclub", kort="Lus", tee="Rood"),
                          ronde(778, "2026-09-16", baan="Oost", club="Lusclub", kort="Lus", tee="Rood")])
        check("zonder markering in de ronde: geen wedstrijdlusronde", await pg.evaluate("() => leesRondes().map(r => [r.track, isLusRonde(r)]).sort()"),
              [['Maanlus', False], ['Oost', False]])

        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
