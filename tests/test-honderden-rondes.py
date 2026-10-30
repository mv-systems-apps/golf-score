"""Elk scherm opent zonder fout bij honderden rondes.

Vaste regel (gebruiker, 4-10-2026). De test vult de app met 300, 1.000 en 2.500 bewust
rommelige rondes, en met de eigen rondes tien keer vermenigvuldigd over tien jaar.
Daarna opent hij met echte tikken alles wat er te openen valt:

  - elk tabblad, en elke subtab en sectie van Instellingen;
  - in Rondes: elke groepering (aan, alle jaarkoppen open, uit), het zoekveld met een
    zoekopdracht, 'meer laden', en het bewerkkeuze- en exportvenster van een ronde;
  - op Statistiek: elke periode en knop, elke groep, de controlekaart, 'Wat als?' met
    een waarde, en de spelanalyse;
  - in Clubs: elke club en subgroep open, elke baananalyse, de groepering, de editor;
  - het scorescherm en de ronde-informatie met een lopende ronde (bij 1.000 rondes).

De rommel: meerdere spelers en clubs, 9 en 18 holes, niet-qualifying, half gespeeld,
gepland, geïmporteerd, wedstrijdlussen, lange notities met vreemde tekens, met en
zonder putts, dubbele datum en tijd, en rondes zoals oude backups ze hadden: zonder
tijd, korte clubnaam, geslacht, pcc, dagresultaat of holesCount, of met een lege
holeslijst.

Bewust NIET in de gegevens (keuze van de gebruiker, 4-10-2026): een ronde zonder holeslijst. De
app weigert zo'n ronde bij het inlezen ('geen holes'), dus hij kan alleen ontstaan als
de opslag zelf beschadigd raakt. Staat hij er toch, dan blijft het tabblad Rondes leeg;
dat is bekend en zo gelaten.

Fout is: een foutmelding in de pagina of de console, een tabblad dat leeg blijft, een
ronde die door het openen verandert, of — bij 1.000 rondes — een tik die langer dan één
seconde nodig heeft. Bij de andere groottes worden de tijden alleen gemeld. Deze
testomgeving is sneller dan een telefoon: de grens is een vangnet, geen belofte.

Bewijs dat de test kan falen:  KAPOT=1 python3 test-honderden-rondes.py
draait op een app waarin het tellen van gespeelde holes struikelt over een ronde met een
lege holeslijst. Dan moet hij falen.
"""
import asyncio, copy, datetime, json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
KAPOT = os.environ.get('KAPOT') == '1'
GRENS_MS, GRENS_BIJ = 1000, 1000
ECHTE_CLUBS = {c['club']: c for c in json.load(open(os.path.join(HIER, 'echte-clubs.json'), encoding='utf-8'))}
ECHTE_RONDES = json.load(open(os.path.join(HIER, 'echte-rondes.json'), encoding='utf-8'))
SPELER = 'Testspeler'

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

# ── de rommelige gegevens ─────────────────────────────────────────────────────────
TEES = [(club, c.get('shortName', ''), baan, g, t, te, b['holeIds'])
        for club, c in ECHTE_CLUBS.items() for baan, b in c['courses'].items()
        for g, tt in b['tees'].items() for t, te in tt.items()]

def verdeel(chcp, holes):
    n = len(holes); basis = int(chcp / n); rest = abs(chcp) % n
    ph = [basis] * n
    volgorde = sorted(range(n), key=lambda i: holes[i]['si'] if chcp > 0 else -holes[i]['si'])
    for i in volgorde[:rest]: ph[i] += 1 if chcp > 0 else -1
    return ph

def rommel(aantal, zaad):
    rnd = random.Random(zaad); vandaag = datetime.date.today(); uit = []
    for i in range(aantal):
        club, kort, baan, g, t, te, ids = TEES[rnd.randrange(len(TEES))]
        speler = SPELER if rnd.random() < 0.7 else rnd.choice(['Partner', 'Kind', "O'Brien <b>&", 'Ω speler'])
        hcp = round(rnd.uniform(-2, 54), 1); n = len(ids); par = sum(h['par'] for h in te['holes'])
        chcp = round(te['SR'] / 113 * (hcp / 2 if n == 9 else hcp) + (te['CR'] - par))
        ph = verdeel(chcp, te['holes'])
        soort = rnd.random()
        gespeeld = n if soort < 0.86 else (0 if soort < 0.91 else rnd.randrange(1, n))
        datum = vandaag - datetime.timedelta(days=rnd.randrange(0, 3650)) if gespeeld else vandaag + datetime.timedelta(days=rnd.randrange(1, 60))
        holes = []
        for k, hid in enumerate(ids):
            h = {'id': hid, 'par': te['holes'][k]['par'], 'si': te['holes'][k]['si'], 'phcp': ph[k], 'ppar': te['holes'][k]['par'] + ph[k],
                 'score': (te['holes'][k]['par'] + rnd.randrange(-1, 5)) if k < gespeeld else None}
            if h['score'] is not None and rnd.random() < 0.6: h['putts'] = min(max(0, h['score'] - 1), rnd.randrange(0, 4))
            holes.append(h)
        qual = rnd.random() < 0.75
        r = {'id': 1_000_000 + i, 'date': datum.isoformat(), 'time': f"{rnd.randrange(7, 20):02d}:{rnd.choice(['00', '04', '32', '48'])}",
             'player': speler, 'hcp': hcp, 'club': club, 'clubShort': kort, 'gender': g, 'track': baan, 'tee': t,
             'CR': te['CR'], 'SR': te['SR'], 'PAR': par, 'chcp': chcp, 'qualifying': qual, 'pcc': rnd.choice([None, 0, -0.5, 1]),
             'sdFinal': round(rnd.uniform(5, 60), 1) if (qual and gespeeld == n and rnd.random() < 0.8) else None,
             'holesCount': n, 'currentHole': 0, 'started': True, 'holes': holes,
             'total': sum(h['score'] or 0 for h in holes), 'totalStb': rnd.randrange(0, 40)}
        w = rnd.random()
        if w < 0.05: r['lus'] = True
        if w < 0.12: r['note'] = rnd.choice(['Wedstrijd', 'Regen & wind — "zwaar"', '<script>alert(1)</script>', 'x' * 400, 'Texas Scramble 🏌️', "l'été; ça va"])
        if 0.12 <= w < 0.14: r['_justImported'] = True
        # zoals oude backups: velden die ontbreken
        if 0.20 <= w < 0.26:
            for veld in rnd.sample(['time', 'clubShort', 'gender', 'pcc', 'sdFinal', 'holesCount', 'total', 'totalStb', 'currentHole', 'started', 'PAR', 'tee'], 4): r.pop(veld, None)
        if 0.26 <= w < 0.27: r['holes'] = []
        if 0.275 <= w < 0.285 and uit: r['date'], r['time'], r['player'] = uit[-1]['date'], uit[-1].get('time', '09:00'), uit[-1]['player']   # duplicaat
        if 0.285 <= w < 0.29: r['CR'] = None; r['SR'] = 0
        uit.append(r)
    # De lastigste gevallen ook bovenaan de lijst (recente datum), zodat elke doorloop ze
    # echt op het scherm krijgt en het niet van het toeval afhangt.
    bron = [r for r in uit if r.get('holes') and r['player'] == SPELER][:4]
    for k, r in enumerate(bron):
        x = copy.deepcopy(r); x['id'] = 1_900_000 + k; x['date'] = (vandaag - datetime.timedelta(days=1 + k)).isoformat(); x['time'] = '08:00'
        if k == 0: x['qualifying'] = True; x['sdFinal'] = None; x.pop('pcc', None)
        if k == 1: x['holes'] = []
        if k == 2:
            for veld in ('time', 'clubShort', 'gender', 'pcc', 'sdFinal', 'holesCount', 'total', 'totalStb', 'PAR', 'tee', 'CR', 'SR', 'chcp', 'hcp'): x.pop(veld, None)
        if k == 3: x['note'] = '<img src=x onerror=alert(1)> ' + 'lang ' * 80
        uit.append(x)
    return uit

def eigen_keer_tien():
    uit = []
    for jaar in range(10):
        for i, x in enumerate(ECHTE_RONDES):
            r = copy.deepcopy(x); d = datetime.date.fromisoformat(r['date'])
            r['date'] = d.replace(year=d.year - jaar).isoformat(); r['id'] = 2_000_000 + jaar * 1000 + i
            uit.append(r)
    return uit

# ── wat er per scherm getikt wordt ────────────────────────────────────────────────
# (functienaam in onclick, hoeveel hooguit, toelichting)
TIKKEN = {
    'stat':    [('renderPlayerStats(', 12), ('toggleStatsGroup(', 6), ('toggleStatsGroup(', 6), ('ccSwapView(', 2), ('ccShowPoint(', 3), ('ccSwapView(', 2),
                ('toggleLowHiGraph(', 2), ('toggleMoreInfo(', 2), ('toggleWatIfCard(', 1), ('jumpToArchiveRound(', 1)],
    'archive': [('toggleArchiefZoeken(', 1), ('tekenRondelijst(', 2), ('openRoundEditChoice(', 1), ('openExportModal(', 1)],
    'club':    [('toggleCourseList(', 8), ('toggleClubSubGroup(', 8), ('toggleCourseAnalysis(', 12), ('toggleClubGroupByCategory(', 1), ('toggleCourseList(', 4),
                ('toggleClubGroupByCategory(', 1), ('toggleClubZoeken(', 1), ('confirmEditClub(', 1)],
    'settings': [('switchSettingsTab(', 3), ('toggleMoreInfo(', 4)],
    'setup':   [('selectGender(', 2), ('selectHoleCount(', 2), ('togglePar3(', 2), ('toggleStartNote(', 1), ('openClubSearchModal(', 1), ('togglePlayer2(', 2)],
    'score':   [('selectNine(', 2), ('switchToPlayer(', 2)],
}
GROEPERINGEN = ['toggleGroupByPlayer(', 'toggleGroupByTrack(', 'toggleGroupByCategory(', 'toggleGroupByWhs(', 'toggleGroupByPlanned(']

SLUIT = """() => { document.querySelectorAll('[id$=Modal]:not(.hidden), [id$=Overlay]:not(.hidden)').forEach(m => m.classList.add('hidden')); }"""
RONDES = """() => { const vast = v => Array.isArray(v) ? '[' + v.map(vast).join(',') + ']'
    : (v && typeof v === 'object') ? '{' + Object.keys(v).filter(k => v[k] !== undefined).sort().map(k => JSON.stringify(k) + ':' + vast(v[k])).join(',') + '}'
    : JSON.stringify(v === undefined ? null : v);
  const u = {}; loadSavedRounds().forEach(r => u[r.id] = vast(r)); return u; }"""
KAPOT_JS = "() => { window.gespeeldeHoles = r => { if (!r.holes.length) throw new Error('lege holeslijst'); return r.holes.filter(h => h.score !== null).length; }; }"

class Loop:
    def __init__(self, pg, naam):
        self.pg, self.naam, self.fout, self.tijden, self.tikken = pg, naam, [], {}, 0
        pg.on('pageerror', lambda e: self.fout.append('pagina: ' + str(e)[:160]))
        pg.on('console', lambda m: self.fout.append('console: ' + m.text[:160]) if m.type == 'error' else None)

    async def meet(self, waar, doe):
        """Doet de tik en meet in de PAGINA hoe lang de app ermee bezig was (van de tik tot en
        met het volgende beeld). Niet de tijd van de test zelf: die wacht ook op animaties en
        op het in beeld schuiven van een knop, en dat zegt niets over de app."""
        n0 = len(self.fout)
        try:
            await self.pg.evaluate("() => { window._evt = 0; }")
            await doe()
            ms = await self.pg.evaluate("""() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => {
                (window._obs ? window._obs.takeRecords() : []).forEach(e => { if (e.duration > window._evt) window._evt = e.duration; });
                r(window._evt || 0); }, 30))))""")
        except Exception as e:
            self.fout.append(f"{waar}: tik mislukt: {str(e)[:120]}"); ms = 0
        self.tikken += 1
        if ms > self.tijden.get(waar, 0): self.tijden[waar] = ms
        for f in self.fout[n0:]: check(f"{self.naam}: {waar} zonder fout", False, f)
        geteld[0] += 1
        return ms

    async def tab(self, s):
        await self.pg.evaluate(SLUIT)
        ms = await self.meet(f"tabblad {s}", lambda: self.pg.locator('#tab-' + s).click(timeout=5000))
        leeg = await self.pg.evaluate("(s) => document.getElementById('screen-' + s).innerText.trim().length === 0", s)
        check(f"{self.naam}: tabblad {s} is niet leeg", not leeg)

    async def tik(self, scherm, functie, hooguit):
        sel = f'#screen-{scherm} [onclick*="{functie}"]'
        for i in range(hooguit):
            el = self.pg.locator(sel)
            n = await el.count()
            if i >= n: break
            e = el.nth(i)
            if not await e.is_visible() or not await e.is_enabled(): continue      # een uitgeschakelde knop (bv. agenda zonder geplande rondes) hoort zo
            await self.meet(f"{scherm}: {functie})", lambda: e.click(timeout=3000))
            await self.pg.wait_for_timeout(40)
            if functie in ('openRoundEditChoice(', 'openExportModal(', 'confirmEditClub(', 'openClubSearchModal(', 'jumpToArchiveRound('):
                await self.pg.evaluate(SLUIT)

async def doorloop(b, naam, clubs, rondes, speler, lopend=False, grens=False):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    L = Loop(pg, naam)
    try:
        await pg.goto(app_url())
        await pg.evaluate("""([clubs, rondes, speler]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', JSON.stringify(rondes)); localStorage.setItem('golf_profile_name', speler); localStorage.setItem('golf_profile_hcp', '30.8');
            localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_track_putts', 'on');
            localStorage.setItem('golf_home_club', 'Golfclub Heelsum'); localStorage.setItem('golf_default_club', 'Golfclub Heelsum'); }""", [clubs, rondes, speler])
        t0 = time.perf_counter(); await pg.reload(); await pg.wait_for_load_state('load')
        await pg.evaluate("() => new Promise(r => requestAnimationFrame(() => r(1)))")
        L.tijden['app starten'] = (time.perf_counter() - t0) * 1000
        await pg.wait_for_timeout(300)
        if KAPOT: await pg.evaluate(KAPOT_JS)
        await pg.evaluate("""() => { window._evt = 0;
            window._obs = new PerformanceObserver(l => l.getEntries().forEach(e => { if (e.duration > window._evt) window._evt = e.duration; }));
            window._obs.observe({ type: 'event', durationThreshold: 16, buffered: false }); }""")
        ingelezen = await pg.evaluate("() => loadSavedRounds().length")
        check(f"{naam}: alle {len(rondes)} rondes zijn ingelezen", ingelezen == len(rondes), str(ingelezen))
        if lopend:
            await pg.evaluate("""(speler) => { const s = loadSavedRounds(); const i = s.findIndex(r => r.player === speler && r.qualifying && isRondeAf(r) && (r.holes || []).length === 18);
                loadRoundSingle(i >= 0 ? i : s.findIndex(r => r.player === speler && isRondeAf(r))); }""", speler)
            await pg.wait_for_timeout(300)
        voor = await pg.evaluate(RONDES)

        for s in ('setup', 'score', 'stat', 'archive', 'club', 'settings'):
            await L.tab(s)
            for functie, hooguit in TIKKEN.get(s, []):
                await L.tik(s, functie, hooguit)
            if s == 'stat':
                veld = pg.locator('#watIfInput')
                if await veld.count() and await veld.is_visible():
                    await L.meet('stat: Wat als? invullen', lambda: veld.fill('25.5'))
                    await veld.dispatch_event('input')
                knop = pg.locator('#screen-stat [onclick*="openGameAnalysis("]')
                if await knop.count() and await knop.first.is_visible():
                    await L.meet('stat: spelanalyse', lambda: knop.first.click(timeout=5000)); await pg.evaluate(SLUIT)
            if s == 'archive':
                zoek = pg.locator('#screen-archive input[type="text"], #screen-archive input[type="search"]').first
                if await zoek.count() and await zoek.is_visible():
                    for woord in ('Sandr', 'geel 2021', 'xyz-bestaat-niet', ''):
                        await L.meet('archive: zoeken', lambda: zoek.fill(woord)); await zoek.dispatch_event('input'); await pg.wait_for_timeout(120)
                for g in GROEPERINGEN:
                    await L.tik('archive', g, 1)                         # aan
                    await L.tik('archive', 'jaarKopKlik(', 12)            # koppen openklappen
                    for kop in ('toggleCat(', 'toggleCollaps', 'toggleGroup(', 'togglePlayerGroup(', 'toggleTrackGroup(', 'toggleWhsCardExpand('):
                        await L.tik('archive', kop, 6)
                    await L.tik('archive', 'tekenRondelijst(', 1)
                    await L.tik('archive', g, 1)                         # uit
            if s == 'settings':
                for i in range(3):
                    tabs = pg.locator('#screen-settings [onclick*="switchSettingsTab("]')
                    if i < await tabs.count(): await L.meet('settings: subtab', lambda: tabs.nth(i).click(timeout=3000))
                    koppen = pg.locator('#screen-settings [data-section-key]')
                    for k in range(await koppen.count()):
                        if await koppen.nth(k).is_visible(): await L.meet('settings: sectie openen', lambda: koppen.nth(k).click(timeout=3000))
        await pg.evaluate(SLUIT)
        for s in ('stat', 'archive', 'setup'):                           # nog een keer, nu met alles opengeklapt
            await L.tab(s)

        na = await pg.evaluate(RONDES)
        anders = [i for i in set(voor) | set(na) if voor.get(i) != na.get(i)]
        check(f"{naam}: geen enkele ronde is door het openen veranderd", not anders, f"{len(anders)} rondes, bv. {anders[:3]}")
        check(f"{naam}: er is echt getikt", L.tikken > 60, str(L.tikken))
        traag = sorted(((ms, w) for w, ms in L.tijden.items()), reverse=True)
        if grens:
            te = [(round(ms), w) for ms, w in traag if ms > GRENS_MS and w != 'app starten']
            check(f"{naam}: geen tik duurt langer dan {GRENS_MS} ms", not te, str(te[:5]))
        return naam, len(rondes), L.tikken, traag[:4], len(L.fout)
    except Exception as e:
        check(f"{naam}: de doorloop is afgemaakt", False, str(e)[:250])
        return naam, len(rondes), L.tikken, [], len(L.fout)
    finally:
        await pg.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        if KAPOT: print("LET OP: opzettelijk kapotte app — deze doorloop HOORT te falen.")
        werk = [
            ('300 rommelige rondes',               ECHTE_CLUBS, rommel(300, 1),  SPELER, False, False),
            ('1.000 rommelige rondes',             ECHTE_CLUBS, rommel(1000, 2), SPELER, False, True),
            ('1.000 rondes, met lopende ronde',    ECHTE_CLUBS, rommel(1000, 3), SPELER, True,  True),
            ('2.500 rommelige rondes',             ECHTE_CLUBS, rommel(2500, 4), SPELER, False, False),
            ('De echte rondes × 10 (430)',            ECHTE_CLUBS, eigen_keer_tien(), SPELER, False, False),
        ]
        # na elkaar, niet tegelijk: anders meten de doorlopen elkaars drukte
        for w in werk:
            naam, n, tikken, traag, nf = await doorloop(b, *w)
            print(f"  {naam:<34} {tikken:>4} tikken, {nf} foutmeldingen; traagste: " + ', '.join(f"{w_} {ms:.0f} ms" for ms, w_ in traag))
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
