"""De app met de eigen gegevens: zijn clubbestand (vijf clubs) en zijn echte rondes.

De les van de backupmelding: een wijziging testen op verzonnen gegevens is niet genoeg,
de bestaande gegevens moeten er ook doorheen. De banenlijst per club (elke club mag
dezelfde baannamen hebben) was alleen op verzonnen clubs getest. Hier:

  1. elke club kiezen: het startscherm toont precies de banen van die club;
  2. op elke baan van elke club, vanaf elke tee, een ronde klaarzetten: baanhandicap en
     rondegegevens komen uit die club en die tee;
  3. de echte rondes: elk scherm opent zonder fout, en een echte ronde laden en opslaan
     verandert er niets aan.

echte-clubs.json is de eigen clubbackup van 2-10-2026; de rondes komen uit
overstap-standen.json (zijn backup van 19-9-2026).
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
CLUBLIJST = json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))
CLUBS = {c['club']: c for c in CLUBLIJST}
STAND = next(iter(json.load(open(os.path.join(HIER, 'overstap-standen.json'), encoding='utf-8')).values()))
RONDES = json.loads(STAND['opslag']['golf_rounds'])

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}" + ('' if ok else f": {str(echt)[:300]} — verwacht {str(verwacht)[:300]}"))
    if not ok: fouten.append(naam)

async def schoon(pg, rondes):
    await pg.goto(app_url())
    await pg.evaluate("""([clubs, rondes]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
        localStorage.setItem('golf_rounds', JSON.stringify(rondes)); localStorage.setItem('golf_profile_name', 'Testspeler');
        localStorage.setItem('golf_profile_hcp', '30.8'); localStorage.setItem('golf_kenmerk_gevraagd', '1');
        localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
        localStorage.setItem('golf_lussen_open', '1'); }""", [CLUBS, rondes])
    await pg.reload(); await pg.wait_for_timeout(500)

# Alle banen die het startscherm voor de gekozen club kan tonen, over alle filterstanden.
ALLE_BANEN = """() => { const uit = new Set();
  for (const p3 of [false, true]) for (const hc of [null, '9', '18']) {
    sel.showPar3 = p3; sel.holeCount = hc; sel._holeCountUserCleared = hc === null; buildTrackList();
    document.querySelectorAll('#trackList .track-name').forEach(e => uit.add(e.textContent)); }
  sel.showPar3 = false; sel.holeCount = null; sel._holeCountUserCleared = true; buildTrackList();
  return [...uit].sort(); }"""

# Per baan en tee: wat het startscherm berekent, en wat een gestarte ronde zou meekrijgen.
PER_TEE = """(club) => { const uit = [];
  for (const [baan, b] of Object.entries(CLUBS[club].courses)) for (const [g, tm] of Object.entries(b.tees)) for (const [t, v] of Object.entries(tm)) {
    sel.track = baan; sel.gender = g; sel.tee = t; sel._teeUserSelected = true; sel.chcpOverride = null;
    const scherm = calcChcpAuto();
    const hoort = calcChcp(b.holeIds.length, v.CR, v.SR, teePar(v), parseFloat(document.getElementById('iHcp').value));
    const lijst = COURSES[baan];
    uit.push({ baan, tee: g + ' ' + t, goed: scherm === hoort && lijst === b && COURSE_CLUBS[baan] === club, scherm, hoort }); }
  return uit; }"""

KERN = """() => leesRondes().map(r => { const { total, totalStb, playedCount, holesCount, currentHole, started, _justImported, sd, ...rest } = r;
    return JSON.stringify({ ...rest, holes: r.holes.map(({ _initScore, ...h }) => h) }, (k, v) => (v && typeof v === 'object' && !Array.isArray(v)) ? Object.fromEntries(Object.entries(v).sort()) : v); }).sort()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []
        pg.on('pageerror', lambda e: pf.append(str(e)[:200]))

        print(f"\n=== 1. ELKE CLUB KIEZEN ({len(CLUBS)} clubs, {sum(len(c['courses']) for c in CLUBS.values())} banen) ===\n")
        await schoon(pg, [])
        await pg.evaluate("() => { nav('setup'); document.getElementById('iHcp').value = '30.8'; }")
        tees = 0
        for club, c in CLUBS.items():
            await pg.evaluate("(c) => setDefaultClub(c)", club); await pg.wait_for_timeout(120)
            check(f"{club}: het startscherm toont precies de banen van deze club", await pg.evaluate(ALLE_BANEN), sorted(c['courses'].keys()))
            r = await pg.evaluate(PER_TEE, club); tees += len(r)
            check(f"{club}: baanhandicap klopt voor alle {len(r)} tees", [x for x in r if not x['goed']], [])
        print(f"\n   ({tees} tees nagerekend)")
        dubbel = {}
        for club, c in CLUBS.items():
            for baan in c['courses']: dubbel.setdefault(baan, []).append(club)
        print("   baannamen die bij meer dan één club voorkomen:", {k: v for k, v in dubbel.items() if len(v) > 1} or "geen")

        print("\n=== 2. EEN RONDE STARTEN BIJ ELKE CLUB ===\n")
        for nr, (club, c) in enumerate(CLUBS.items()):
            baan = sorted(c['courses'])[0]; bd = c['courses'][baan]
            g = 'Heren' if 'Heren' in bd['tees'] else next(iter(bd['tees'])); t = next(iter(bd['tees'][g])); te = bd['tees'][g][t]
            r = await pg.evaluate("""([club, baan, g, t, tijd]) => { nav('setup'); setDefaultClub(club); sel.holeCount = null; sel._holeCountUserCleared = true; sel.showPar3 = trackCategories(baan).has('par3');
                sel.track = baan; sel.gender = g; sel.tee = t; sel._teeUserSelected = true; rebuildStartScreen();
                document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.8';
                document.getElementById('iTime').value = tijd; sel.time = tijd; sel.date = document.getElementById('iDate').value; sel.dateTimeEdited = true;
                startRound(); const cb = document.getElementById('confirmModalBtn'); if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
                const u = game.started ? { club: game.club, baan: game.track, CR: game.CR, SR: game.SR, holes: game.holes.map(h => h.id), pars: game.holes.map(h => h.par) } : null;
                if (game.started) finishActiveRound(null); return u; }""", [club, baan, g, t, f"{6 + nr:02d}:00"])
            check(f"{club}, {baan}, {g} {t}", r, {'club': club, 'baan': baan, 'CR': te['CR'], 'SR': te['SR'], 'holes': bd['holeIds'], 'pars': [h['par'] for h in te['holes']]})

        print(f"\n=== 3. ECHTE RONDES ({len(RONDES)} stuks) ===\n")
        await schoon(pg, RONDES)
        voor = await pg.evaluate(KERN)
        check("alle rondes zijn ingelezen", len(voor), len(RONDES))
        for scherm in ['archive', 'stat', 'club', 'settings', 'setup', 'score']:
            await pg.evaluate("(s) => nav(s)", scherm); await pg.wait_for_timeout(350)
        await pg.evaluate("""() => { nav('archive'); toggleGroupByTrack(); toggleGroupByTrack(); toggleGroupByPlayer(); toggleGroupByPlayer(); nav('stat');
            ['handicap', 'prestaties', 'banen'].forEach(k => localStorage.setItem('golf_stats_grp_' + k, 'open')); renderPlayerStats(); }"""); await pg.wait_for_timeout(500)
        check("elk scherm opent zonder fout", pf, [])
        check("openen van de schermen verandert geen enkele ronde", await pg.evaluate(KERN) == voor, True)
        banen = await pg.evaluate("() => { const u = {}; leesRondes().forEach(r => { const k = r.club + ' | ' + r.track; u[k] = (u[k] || 0) + 1; }); return u; }")
        onbekend = sorted(k for k in banen if k.split(' | ')[0] not in CLUBS or k.split(' | ')[1] not in CLUBS[k.split(' | ')[0]]['courses'])
        print("   rondes per club en baan:", dict(sorted(banen.items())))
        print("   rondes op een baan die niet (meer) in het clubbestand staat:", onbekend or "geen")
        # Een paar echte rondes laden als lopende ronde en weer afronden: er mag niets veranderen.
        proef = await pg.evaluate("""() => { const l = leesRondes(); const vol = l.filter(r => r.holes.every(h => h.score != null));
            const metNotitie = vol.find(r => r.note), metPutts = vol.find(r => r.holes.some(h => h.putts != null)), vastgesteld = vol.find(r => r.sdFinal != null), oudste = vol[vol.length - 1];
            return [...new Set([metNotitie, metPutts, vastgesteld, oudste, vol[0]].filter(Boolean).map(r => r.id))]; }""")
        for rid in proef:
            await pg.evaluate("""(id) => { loadRoundSingle(leesRondes().findIndex(r => r.id === id)); saveActiveRound(true); nav('score'); nav('archive'); finishActiveRound(null); }""", rid)
            await pg.wait_for_timeout(200)
        check(f"{len(proef)} echte rondes laden, opslaan en afronden: geen veld gewijzigd", await pg.evaluate(KERN) == voor, True)
        await pg.reload(); await pg.wait_for_timeout(500)
        check("na herladen nog steeds gelijk", await pg.evaluate(KERN) == voor, True)
        check("geen fouten in de pagina", pf, [])
        await b.close()
    print()
    print("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)")

asyncio.run(main())
