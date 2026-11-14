"""Clubs kunnen dezelfde baannamen hebben, op elk scherm.

Regel van de gebruiker: clubnamen zijn uniek, baannamen en wedstrijdlussen niet. Het startscherm
heeft daar zijn eigen test voor (test-startscherm-clubs.py). Deze test loopt de REST
langs, met twee clubs die allebei een baan 'Noord' en een baan 'Zuid' hebben — met
andere holes, par, CR en SR — en bij elke club rondes van Testspeler. Bij club A is hole 1 van
Noord steeds een ramp, bij club B niet: valt er iets samen, dan is dat te zien.

  1. SPELANALYSE — 'vaakst nul punten', 'duurste holes' en de tekst voor de AI-analyse
     tellen per club: nooit meer keren gespeeld dan er bij die club rondes zijn, par en
     SI van de juiste club, en de clubnaam staat erbij omdat de baannaam dubbel is.
     Bij unieke baannamen staat de club er niet bij (de tekst blijft dan kort).
  2. BAANANALYSE in het clubscherm — per club alleen de eigen rondes en eigen holes.
  3. STATISTIEK, groep Clubs, en RONDES gegroepeerd per baan — per club uitgesplitst.
  4. CORRIGEREN van een ronde bij club B terwijl club A gekozen is — het startscherm en
     de gestarte ronde krijgen de baan van club B; de rondes van club A blijven gelijk.
  5. De baan VERWIJDEREN bij club B — club A houdt zijn eigen 'Noord'.

  6. Bij unieke baannamen staat de club er in de analyse niet bij.
  7. WEDSTRIJDLUSSEN met dezelfde naam: beide clubs hebben een lus 'Maan'; en club A heeft
     een lus 'Ster' terwijl club B een gewone baan 'Ster' heeft. Starten, spelanalyse,
     baananalyse, het overzicht per baan op Statistiek (een lus telt daar niet mee, de
     gewone baan wel), Rondes per baan, en de lus verwijderen bij club B.

  8. EEN LUS SAMENSTELLEN EN BIJWERKEN: bij beide clubs in de lus-editor een lus 'Maan'
     maken uit de eigen banen 'Noord' en 'Zuid' (echte tikken). Wijzigt daarna 'Noord'
     bij club B, dan is alleen de lus van club B verouderd; bijwerken rekent hem opnieuw
     uit de banen van club B, en de lus van club A blijft zoals hij was. En omgekeerd.

  9. EEN LUS HERNOEMEN terwijl de andere club een lus met dezelfde naam heeft: de app
     vraagt het, 'nee' verandert geen ronde, 'ja' verandert alleen de naam in de rondes
     van die club; de lus en de rondes van de andere club blijven gelijk, en de rondes
     blijven lusrondes.

Hernoemen met 'ja' bij een dubbele baannaam zit in test-clubs-raken-rondes-niet.py.

Faalt op 13527DA-10F: daar telde de spelanalyse per baannaam, zonder de club.
"""
import asyncio, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testdata
from testdata import app_url
from playwright.async_api import async_playwright

fouten, geteld = [], [0]
def check(naam, ok, detail=''):
    geteld[0] += 1
    if not ok:
        print(f"  FOUT {naam}" + (f": {detail}" if detail else ''))
        fouten.append(naam)

def tee(cr, sr, pars): return {"CR": cr, "SR": sr, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(pars)]}
PA = [4, 3, 5, 4, 4, 3, 4, 5, 4]; PB = [5, 4, 4, 3, 4, 5, 4, 4, 4]
def ids(l): return [f"{l}{i}" for i in range(1, 10)]
BAAN = {('Club A', 'Noord'): (ids('AN'), PA, 35.0, 120), ('Club A', 'Zuid'): (ids('AZ'), PA, 35.5, 122),
        ('Club B', 'Noord'): (ids('BN'), PB, 37.0, 135), ('Club B', 'Zuid'): (ids('BZ'), PB, 37.5, 137)}
def clubs(namen=('Noord', 'Zuid')):
    c = {}
    for (club, baan), (hid, pars, cr, sr) in BAAN.items():
        naam = baan if baan in namen else f"{baan} {club[-1]}"          # voor de proef met unieke namen
        c.setdefault(club, {"club": club, "shortName": club[-1] + '-kort', "courses": {}})["courses"][naam] = {"holeIds": hid, "tees": {"Heren": {"Geel": tee(cr, sr, pars)}}}
    return c

def ronde(rid, dag, club, baan, naam=None):
    hid, pars, cr, sr = BAAN[(club, baan)]
    ramp = (club == 'Club A' and baan == 'Noord')
    holes = [{"id": hid[i], "par": pars[i], "si": i + 1, "phcp": 1, "ppar": pars[i] + 1,
              "score": pars[i] + (6 if (i == 0 and ramp) else 1), "putts": 2} for i in range(9)]
    return {"id": rid, "date": (datetime.date.today() - datetime.timedelta(days=dag)).isoformat(), "time": "09:30", "player": "Testspeler", "hcp": 30.7,
            "club": club, "clubShort": club[-1] + '-kort', "track": naam or baan, "gender": "Heren", "tee": "Geel", "CR": cr, "SR": sr, "PAR": sum(pars),
            "chcp": 9, "qualifying": True, "holesCount": 9, "started": True, "currentHole": 0, "sdFinal": 30.0 + (rid % 4), "pcc": 0,
            "total": sum(h['score'] for h in holes), "totalStb": 18, "holes": holes}

AANTAL = {('Club A', 'Noord'): 8, ('Club B', 'Noord'): 6, ('Club A', 'Zuid'): 5, ('Club B', 'Zuid'): 4}
def rondes(uniek=False):
    uit, rid = [], 1
    for (club, baan), n in AANTAL.items():
        for i in range(n):
            uit.append(ronde(rid, 3 + rid * 4, club, baan, f"{baan} {club[-1]}" if uniek else None)); rid += 1
    return uit

# ── wedstrijdlussen ───────────────────────────────────────────────────────────────
PL_A = [4, 4, 4, 3, 3, 4, 5, 4, 4]; PL_B = [5, 3, 4, 4, 4, 3, 5, 4, 5]
LUS = {('Club A', 'Maan'): (ids('MA'), PL_A, 34.1, 118, True), ('Club B', 'Maan'): (ids('MB'), PL_B, 36.9, 131, True),
       ('Club A', 'Ster'): (ids('SA'), PL_A, 34.4, 119, True), ('Club B', 'Ster'): (ids('SB'), PL_B, 36.2, 128, False)}
LUS_AANTAL = {('Club A', 'Maan'): 5, ('Club B', 'Maan'): 4, ('Club A', 'Ster'): 4, ('Club B', 'Ster'): 6}
def clubs_met_lussen():
    c = clubs()
    for (club, naam), (hid, pars, cr, sr, lus) in LUS.items():
        c[club]['courses'][naam] = {"holeIds": hid, "tees": {"Heren": {"Geel": tee(cr, sr, pars)}}}
        if lus: c[club]['courses'][naam]['lus'] = True
    return c
def rondes_met_lussen():
    uit, rid = rondes(), 500
    for (club, naam), n in LUS_AANTAL.items():
        hid, pars, cr, sr, lus = LUS[(club, naam)]
        for i in range(n):
            ramp = (club == 'Club A' and naam == 'Maan')
            holes = [{"id": hid[k], "par": pars[k], "si": k + 1, "phcp": 1, "ppar": pars[k] + 1, "score": pars[k] + (6 if (k == 0 and ramp) else 1), "putts": 2} for k in range(9)]
            r = {"id": rid, "date": (datetime.date.today() - datetime.timedelta(days=2 + (rid - 500) * 3)).isoformat(), "time": "13:15", "player": "Testspeler", "hcp": 30.7,
                 "club": club, "clubShort": club[-1] + '-kort', "track": naam, "gender": "Heren", "tee": "Geel", "CR": cr, "SR": sr, "PAR": sum(pars), "chcp": 9,
                 "qualifying": True, "holesCount": 9, "started": True, "currentHole": 0, "sdFinal": 31.0, "pcc": 0, "total": sum(h['score'] for h in holes), "totalStb": 18, "holes": holes}
            if lus: r['lus'] = True
            uit.append(r); rid += 1
    return uit

async def lussen(b):
    print("=== 7. WEDSTRIJDLUSSEN MET DEZELFDE NAAM ===")
    pg, pf = await pagina(b, clubs_met_lussen(), rondes_met_lussen())
    await pg.evaluate("() => { _statChartPeriod = 'alles'; localStorage.setItem('golf_lussen_open', '1'); }")
    a = await pg.evaluate(ANALYSE)
    duur = re.findall(r'(Maan|Ster) \((Club [AB])\) hole (\d+) \(par (\d)[^)]*\):\s*([+−±\-]?[\d.]+)[^"]*?(\d+)× gespeeld', a)
    check("lus: de analyse noemt holes van Maan of Ster met de club erbij", len(duur) >= 1, a[a.find('Duurste'):a.find('Duurste') + 260])
    check("lus: geen hole van Maan of Ster zonder club", re.search(r'(Maan|Ster) hole \d', a) is None)
    for naam, club, nr, par, verlies, keer in duur:
        check(f"lus: {naam} ({club}) hole {nr}: aantal en par van die club",
              int(keer) == LUS_AANTAL[(club, naam)] and int(par) == LUS[(club, naam)][1][int(nr) - 1], f"{keer}×, par {par}")
    ramp = [d for d in duur if d[:3] == ('Maan', 'Club A', '1')]
    check("lus: de ramphole (Maan, Club A, hole 1) staat er met +5.0", bool(ramp) and ramp[0][4].lstrip('+') == '5.0', str(ramp))

    for (club, naam), n in LUS_AANTAL.items():
        d = await pg.evaluate("([c, t]) => { const d = courseAnalysisData(c, t); return d ? d.holes.map(h => [h.id, h.nu.n + h.toen.n, h.par]) : null; }", [club, naam])
        hid, pars = LUS[(club, naam)][0], LUS[(club, naam)][1]
        check(f"lus: baananalyse {club} · {naam}: eigen holes, eigen par, {n} rondes", d == [[hid[i], n, pars[i]] for i in range(9)], str(d)[:140])

    # Statistiek, overzicht per baan: een lus telt niet mee, de gewone baan 'Ster' van Club B wel.
    per_baan = await pg.evaluate("""() => { const u = {}; loadSavedRounds().filter(meetelFilter('Testspeler')).forEach(r => { if (isLusRonde(r)) return;
        const k = r.club + ' | ' + r.track; u[k] = (u[k] || 0) + 1; }); return u; }""")
    check("lus: volgens de app zijn Maan (A en B) en Ster (A) lusrondes, Ster (B) niet",
          'Club B | Ster' in per_baan and not any(k in per_baan for k in ('Club A | Maan', 'Club B | Maan', 'Club A | Ster')), str(per_baan))
    await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(300)
    for k in await pg.locator('#screen-stat [onclick*="toggleCourseList("], #screen-stat [onclick*="toggleClub"]').all():
        if await k.is_visible(): await k.click(); await pg.wait_for_timeout(80)
    st = ' | '.join(x.strip() for x in (await pg.evaluate("() => document.getElementById('playerStats').innerText")).split('\n') if x.strip())
    deel = st[st.upper().rfind('CLUBS'):] if 'CLUBS' in st.upper() else st
    # Club A: 8 + 5 gewone rondes (de 5 + 4 lusrondes tellen niet). Club B: 6 + 4, plus 6 op de gewone baan Ster.
    check("lus: het overzicht per club op Statistiek telt bij Club A 13 rondes (lussen niet mee)", 'Club A | 13×' in deel, deel[:200])
    check("lus: en bij Club B 16 (de gewone baan Ster wel, de lus Maan niet)", 'Club B | 16×' in deel, deel[:200])
    check("lus: het overzicht noemt geen Maan", 'Maan' not in deel, deel[:200])
    # Beide clubs uitklappen en de regels per baan aflezen
    for club in ('Club A', 'Club B'):
        kop = pg.locator('#playerStats').get_by_text(club, exact=True).last
        if await kop.count(): await kop.click(); await pg.wait_for_timeout(200)
    st2 = ' | '.join(x.strip() for x in (await pg.evaluate("() => document.getElementById('playerStats').innerText")).split('\n') if x.strip())
    deel2 = st2[st2.upper().rfind('CLUBS'):]
    banen = {}
    stukA, stukB = deel2[deel2.find('Club A'):deel2.find('Club B')], deel2[deel2.find('Club B'):]
    for club, stuk in (('Club A', stukA), ('Club B', stukB)):
        banen[club] = re.findall(r'(Noord|Zuid|Maan|Ster) \| [^|]+ \| [^|]+ \| (\d+)×', stuk)
    check("lus: uitgeklapt toont Statistiek bij Club A alleen Noord (8×) en Zuid (5×)", sorted(banen.get('Club A', [])) == [('Noord', '8'), ('Zuid', '5')], f"{banen.get('Club A')} — {deel2[:260]}")
    check("lus: en bij Club B Noord (6×), Ster (6×) en Zuid (4×), zonder Maan", sorted(banen.get('Club B', [])) == [('Noord', '6'), ('Ster', '6'), ('Zuid', '4')], f"{banen.get('Club B')} — {deel2[:320]}")

    # Rondes per baan
    await pg.locator('#tab-archive').click(); await pg.wait_for_timeout(200)
    await pg.locator('#screen-archive [onclick*="toggleGroupByTrack("]').click(); await pg.wait_for_timeout(300)
    plat = ' | '.join(x.strip() for x in (await pg.evaluate("() => document.getElementById('screen-archive').innerText")).split('\n') if x.strip()).upper()
    a_deel, b_deel = plat[plat.find('CLUB A'):plat.find('CLUB B')], plat[plat.find('CLUB B'):]
    check("lus: Rondes per baan toont Maan en Ster onder Club A met hun eigen aantallen", 'MAAN | 5' in a_deel and 'STER | 4' in a_deel, a_deel[:160])
    # (Club B staat ingeklapt: alleen het totaal. In Rondes tellen lusrondes gewoon mee.)
    check("lus: Club A telt 22 rondes en Club B 20", a_deel.startswith('CLUB A | 22') and b_deel.startswith('CLUB B | 20'), plat[:200])
    kopB = pg.locator('#screen-archive').get_by_text('Club B', exact=True).first
    if await kopB.count(): await kopB.click(); await pg.wait_for_timeout(300)
    plat = ' | '.join(x.strip() for x in (await pg.evaluate("() => document.getElementById('screen-archive').innerText")).split('\n') if x.strip()).upper()
    b_deel = plat[plat.find('CLUB B'):]
    check("lus: uitgeklapt toont Rondes onder Club B: Maan 4, Noord 6, Ster 6, Zuid 4",
          all(x in b_deel for x in ('MAAN | 4', 'NOORD | 6', 'STER | 6', 'ZUID | 4')), b_deel[:200])
    await pg.locator('#screen-archive [onclick*="toggleGroupByTrack("]').click(); await pg.wait_for_timeout(150)

    # Starten op de lus van Club B terwijl Club A gekozen was
    g = await pg.evaluate("""() => { nav('setup'); setDefaultClub('Club B'); sel.holeCount = null; sel._holeCountUserCleared = true; sel.track = 'Maan'; sel.gender = 'Heren'; sel.tee = 'Geel'; sel._teeUserSelected = true; rebuildStartScreen();
        document.getElementById('iName').value = 'Testspeler'; document.getElementById('iHcp').value = '30.7';
        if (COURSES[sel.track].lus) zetQualifyingUitVoorLus();
        startRound(); for (const id of ['confirmModalBtn', 'keuzeModalKnop2']) { const k = document.getElementById(id); if (k && k.offsetParent) k.click(); }
        return game.started ? { club: game.club, baan: game.track, CR: game.CR, hole1: game.holes[0].id, par1: game.holes[0].par, lus: game.lus === true, qual: !!game.qualifying } : null; }""")
    check("lus: een ronde starten op Maan bij Club B geeft de lus van Club B, als lus en niet qualifying",
          g == {'club': 'Club B', 'baan': 'Maan', 'CR': 36.9, 'hole1': 'MB1', 'par1': 5, 'lus': True, 'qual': False}, str(g))
    await pg.evaluate("() => { const id = localStorage.getItem('golf_active_id'); clearActiveRound(); const s = loadSavedRounds().filter(r => String(r.id) !== id); metVerwijderen(() => setRoundsAndMark(JSON.stringify(s))); }")

    # De lus verwijderen bij Club B
    voor = await pg.evaluate("() => JSON.stringify(loadSavedRounds())")
    await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); openCourseEditor('Maan'); }"); await pg.wait_for_timeout(200)
    k = pg.locator('[onclick="deleteCourseFromEditor(this)"]')
    await k.click(); await pg.wait_for_timeout(120); await k.click(); await pg.wait_for_timeout(250)
    await pg.locator('#dangerModalConfirmBtn').click(); await pg.wait_for_timeout(300)
    r = await pg.evaluate("() => ({ b: 'Maan' in CLUBS['Club B'].courses, a: CLUBS['Club A'].courses.Maan ? [CLUBS['Club A'].courses.Maan.holeIds[0], CLUBS['Club A'].courses.Maan.lus === true] : null })")
    check("lus: verwijderen bij Club B laat de lus van Club A staan", r == {'b': False, 'a': ['MA1', True]}, str(r))
    check("lus: en verandert geen ronde", await pg.evaluate("() => JSON.stringify(loadSavedRounds())") == voor)
    check("lus: de rondes van Club B op Maan tellen nog als lusronde", await pg.evaluate("() => loadSavedRounds().filter(r => r.club === 'Club B' && r.track === 'Maan').every(isLusRonde)"))
    check("lus: geen fouten in de pagina", not pf, str(pf[:3]))
    await pg.close()

async def lus_hernoemen(b):
    print("=== 9. EEN LUS HERNOEMEN BIJ GELIJKE NAMEN ===")
    for ja in (False, True):
        wat = f"lus hernoemen, '{'ja' if ja else 'nee'}'"
        pg, pf = await pagina(b, clubs_met_lussen(), rondes_met_lussen())
        R = "() => { const u = {}; loadSavedRounds().forEach(r => u[r.id] = JSON.stringify(r)); return u; }"
        voor = await pg.evaluate(R)
        lusA = await pg.evaluate("() => JSON.stringify(CLUBS['Club A'].courses.Maan)")
        await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); openCourseEditor('Maan'); document.getElementById('editorCourseName').value = 'Zon'; }"); await pg.wait_for_timeout(200)
        await pg.locator('[onclick="saveCourseFromEditor()"]').click(); await pg.wait_for_timeout(300)
        gesteld = await pg.evaluate("() => !document.getElementById('clubRenameModal').classList.contains('hidden')")
        tekst = await pg.evaluate("() => document.getElementById('clubRenameText').innerText.replace(/\\s+/g, ' ')")
        check(f"{wat}: de app stelt de vraag, met het aantal rondes van Club B op die lus (4)", gesteld and '4' in tekst and 'Maan' in tekst, tekst[:120])
        if gesteld:
            await pg.locator(f'[onclick="clubRenameKeuze({"true" if ja else "false"})"]').click(); await pg.wait_for_timeout(300)
        na = await pg.evaluate(R)
        c = await pg.evaluate("() => ({ b: Object.keys(CLUBS['Club B'].courses).sort(), lusB: CLUBS['Club B'].courses.Zon ? CLUBS['Club B'].courses.Zon.lus === true : null, a: JSON.stringify(CLUBS['Club A'].courses.Maan) })")
        check(f"{wat}: bij Club B heet de lus nu Zon en is het nog een lus", 'Zon' in c['b'] and 'Maan' not in c['b'] and c['lusB'] is True, str(c['b']))
        check(f"{wat}: de lus Maan van Club A is gelijk gebleven", c['a'] == lusA)
        anders = {i for i in voor if voor[i] != na.get(i)}
        vanB = {str(r['id']) for r in rondes_met_lussen() if r['club'] == 'Club B' and r['track'] == 'Maan'}
        if not ja:
            check(f"{wat}: geen enkele ronde is veranderd", not anders, str(sorted(anders))[:120])
        else:
            check(f"{wat}: precies de 4 rondes van Club B op Maan zijn aangepast", anders == vanB, f"{sorted(anders)} tegen {sorted(vanB)}")
            for i in sorted(anders & vanB):
                o, n = json.loads(voor[i]), json.loads(na[i])
                verschil = {k for k in set(o) | set(n) if o.get(k) != n.get(k)}
                check(f"{wat}: ronde {i}: alleen de baannaam is veranderd, en hij is nog een lusronde", verschil == {'track'} and n['track'] == 'Zon' and n.get('lus') is True, str(verschil))
            check(f"{wat}: de rondes van Club A op Maan heten nog Maan", await pg.evaluate("() => loadSavedRounds().filter(r => r.club === 'Club A' && r.lus).filter(r => r.track === 'Maan').length") == 5)
        check(f"{wat}: geen fouten in de pagina", not pf, str(pf[:3]))
        await pg.close()

async def lus_maken_en_bijwerken(b):
    print("=== 8. EEN LUS SAMENSTELLEN EN BIJWERKEN BIJ GELIJKE NAMEN ===")
    pg, pf = await pagina(b, clubs(), rondes())
    LUSJS = "(c) => JSON.parse(JSON.stringify(CLUBS[c].courses['Maan'] || null))"
    async def maak(club):
        await pg.evaluate("(c) => { document.querySelectorAll('[id$=Overlay]:not(.hidden)').forEach(m => m.classList.add('hidden')); nav('club'); openClubEditor(c); }", club)
        await pg.wait_for_timeout(150)
        await pg.click('#lusMaakKnop'); await pg.wait_for_timeout(150)
        await pg.fill('#lusNaam', 'Maan'); await pg.click('[data-lus-bron="Noord"]')
        for i in (0, 1, 2): await pg.click(f'[data-lus-hole="{i}"]')
        await pg.click('[data-lus-bron="Zuid"]')
        for i in range(6): await pg.click(f'[data-lus-hole="{i}"]')
        await pg.click('text=Opslaan als lus'); await pg.wait_for_timeout(300)
        return await pg.evaluate(LUSJS, club)
    async def cr_wijzigen(club, baan, cr):
        await pg.evaluate("""([c, baan, cr]) => { document.querySelectorAll('[id$=Overlay]:not(.hidden)').forEach(m => m.classList.add('hidden')); nav('club'); openClubEditor(c); openCourseEditor(baan);
            const v = document.querySelector('.cr-name-field'); v.dataset.value = cr; v.textContent = cr; }""", [club, baan, cr])
        await pg.locator('[onclick="saveCourseFromEditor()"]').click(); await pg.wait_for_timeout(300)
    async def status(): return await pg.evaluate("() => [lusStatus('Club A', 'Maan'), lusStatus('Club B', 'Maan')]")

    a0 = await maak('Club A'); b0 = await maak('Club B')
    check("lus maken: Club A krijgt een lus uit zijn eigen holes", a0 and a0.get('lus') is True and a0['holeIds'] == ['AN1', 'AN2', 'AN3'] + [f'AZ{i}' for i in range(1, 7)], str(a0)[:200])
    check("lus maken: Club B krijgt een lus met dezelfde naam uit ZIJN eigen holes", b0 and b0['holeIds'] == ['BN1', 'BN2', 'BN3'] + [f'BZ{i}' for i in range(1, 7)], str(b0)[:200])
    check("lus maken: par en CR verschillen per club (eigen bronbanen)", a0 and b0 and a0['tees'] != b0['tees'])
    check("lus maken: beide zijn actueel", await status() == ['actueel', 'actueel'], str(await status()))
    rondes0 = await pg.evaluate("() => JSON.stringify(loadSavedRounds())")

    await cr_wijzigen('Club B', 'Noord', '39.9')
    check("Noord gewijzigd bij Club B: alleen de lus van Club B is verouderd", await status() == ['actueel', 'verouderd'], str(await status()))
    await pg.evaluate("() => { document.querySelectorAll('[id$=Overlay]:not(.hidden)').forEach(m => m.classList.add('hidden')); nav('club'); openClubEditor('Club B'); const g = document.getElementById('clubCourseGrouplus'); if (g && g.classList.contains('hidden')) toggleClubCourseGroup('lus'); }"); await pg.wait_for_timeout(200)
    regel = await pg.evaluate("() => { const m = document.querySelector('#clubCourseGrouplus [data-lus-status]'); return m ? [m.dataset.lusStatus, m.innerText.replace(/\\s+/g, ' ').trim()] : null; }")
    check("in de editor van Club B staat de melding met Bijwerken", regel == ['verouderd', 'Een bronbaan is gewijzigd. Bijwerken'], str(regel))
    await pg.evaluate("() => { openClubEditor('Club A'); const g = document.getElementById('clubCourseGrouplus'); if (g && g.classList.contains('hidden')) toggleClubCourseGroup('lus'); }"); await pg.wait_for_timeout(150)
    check("in de editor van Club A staat die melding niet", await pg.evaluate("() => !document.querySelector('#clubCourseGrouplus [data-lus-status]')"))
    await pg.evaluate("() => { openClubEditor('Club B'); const g = document.getElementById('clubCourseGrouplus'); if (g && g.classList.contains('hidden')) toggleClubCourseGroup('lus'); }"); await pg.wait_for_timeout(150)
    await pg.locator('#clubCourseGrouplus [data-lus-status] span', has_text='Bijwerken').click(); await pg.wait_for_timeout(200)
    await pg.locator('#keuzeModal button', has_text='Bijwerken').click(); await pg.wait_for_timeout(300)
    a1, b1 = await pg.evaluate(LUSJS, 'Club A'), await pg.evaluate(LUSJS, 'Club B')
    hoortB = await pg.evaluate("() => berekenLus('Club B', CLUBS['Club B'].courses['Maan'].bron).tees")
    check("bijwerken bij Club B: de lus is opnieuw berekend uit de banen van Club B", b1['tees'] == hoortB and b1['tees'] != b0['tees'], str(b1['tees'])[:160])
    check("bijwerken bij Club B: zelfde holes van Club B", b1['holeIds'] == b0['holeIds'])
    check("bijwerken bij Club B: de lus van Club A is niet aangeraakt", a1 == a0)
    check("bijwerken bij Club B: beide weer actueel", await status() == ['actueel', 'actueel'], str(await status()))

    await cr_wijzigen('Club A', 'Zuid', '31.1')
    check("Zuid gewijzigd bij Club A: nu is alleen de lus van Club A verouderd", await status() == ['verouderd', 'actueel'], str(await status()))
    check("de lus van Club B is daarbij gelijk gebleven", await pg.evaluate(LUSJS, 'Club B') == b1)
    check("en geen enkele ronde is veranderd", await pg.evaluate("() => JSON.stringify(loadSavedRounds())") == rondes0)
    check("lus maken en bijwerken: geen fouten in de pagina", not pf, str(pf[:3]))
    await pg.close()

async def pagina(b, c, r):
    pg = await b.new_page(viewport={'width': 390, 'height': 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
    await pg.goto(app_url()); await pg.evaluate(testdata.SEED, [c, r])
    await pg.evaluate("() => { localStorage.setItem('golf_default_club', 'Club A'); localStorage.setItem('golf_home_club', 'Club A'); localStorage.setItem('golf_stats_grp_clubs', 'open'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }")
    await pg.reload(); await pg.wait_for_timeout(400)
    return pg, pf

ANALYSE = """() => { const a = buildGameAnalysis(); return (typeof a === 'string' ? a : JSON.stringify(a)).replace(/<[^>]+>/g, '').replace(/\\\\u2014/g, '—'); }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg, pf = await pagina(b, clubs(), rondes())
        await pg.evaluate("() => { _statChartPeriod = 'alles'; }")

        print("=== 1. SPELANALYSE ===")
        a = await pg.evaluate(ANALYSE)
        holes = re.findall(r'(Noord|Zuid)( \(Club [AB]\))? hole (\d+) ?\(([^)]*)\)', a)
        check("de analyse noemt holes van de dubbele banen", len(holes) >= 2, a[:200])
        zonder = [h for h in holes if not h[1]]
        check("bij elke hole van een dubbele baannaam staat de club", not zonder, str(zonder[:3]))
        for baan, club, nr, rest in holes:
            m = re.search(r'(\d+) van (\d+)', rest)
            if m and club:
                hoort = AANTAL[(club.strip(' ()'), baan)]
                check(f"nullers {baan}{club} hole {nr}: geteld binnen die club ({hoort} rondes)", int(m.group(2)) == hoort, rest)
        duur = re.findall(r'(Noord|Zuid) \((Club [AB])\) hole (\d+) \(par (\d)[^)]*\):\s*([+−±\-]?[\d.]+)[^"]*?(\d+)× gespeeld', a)
        check("'duurste holes' noemt holes met club", len(duur) >= 1, a[a.find('Duurste'):a.find('Duurste') + 300])
        for baan, club, nr, par, verlies, keer in duur:
            hoort = AANTAL[(club, baan)]; echte_par = BAAN[(club, baan)][1][int(nr) - 1]
            check(f"duurste holes {baan} ({club}) hole {nr}: {keer}× gespeeld is het aantal rondes bij die club", int(keer) == hoort, f"hoort {hoort}")
            check(f"duurste holes {baan} ({club}) hole {nr}: de par is die van die club", int(par) == echte_par, f"par {par}, hoort {echte_par}")
        ramp = [d for d in duur if d[0] == 'Noord' and d[1] == 'Club A' and d[2] == '1']
        check("de ramphole (Noord, Club A, hole 1) staat bij de duurste, met het volle verlies van +5.0",
              bool(ramp) and ramp[0][4].lstrip('+') == '5.0', str(ramp))
        check("hole 1 van Noord bij Club B staat er niet als verliespost", not any(d[0] == 'Noord' and d[1] == 'Club B' and d[2] == '1' and d[4].lstrip('+') not in ('0.0',) and not d[4].startswith('±') for d in duur), str(duur))

        # de tekst voor de AI-analyse
        tekst = await pg.evaluate("""async () => { let t = null; const o = navigator.clipboard && navigator.clipboard.writeText;
            try { Object.defineProperty(navigator, 'clipboard', { value: { writeText: async x => { t = x; } }, configurable: true }); } catch (e) {}
            try { await copyAnalysisForAi(); } catch (e) { return 'FOUT ' + e.message; } return t; }""")
        if tekst and not str(tekst).startswith('FOUT'):
            regels = [x for x in tekst.split('\n') if re.match(r'^(Noord|Zuid).* \| \d+ \| par', x)]
            check("AI-tekst: er staan holeregels in", len(regels) > 0)
            check("AI-tekst: elke holeregel noemt de club", all(re.match(r'^(Noord|Zuid) \(Club [AB]\) \|', x) for x in regels), str(regels[:2]))
            for x in regels:
                m = re.match(r'^(Noord|Zuid) \((Club [AB])\) \| (\d+) \| par (\d).*\| (\d+)$', x)
                if m: check(f"AI-tekst {m.group(1)} ({m.group(2)}) hole {m.group(3)}: aantal en par van die club",
                            int(m.group(5)) == AANTAL[(m.group(2), m.group(1))] and int(m.group(4)) == BAAN[(m.group(2), m.group(1))][1][int(m.group(3)) - 1], x)
        else:
            check("AI-tekst: is opgebouwd", False, str(tekst)[:120])

        print("=== 2. BAANANALYSE ===")
        for (club, baan), n in AANTAL.items():
            d = await pg.evaluate("([c, t]) => { const d = courseAnalysisData(c, t); return d ? d.holes.map(h => [h.id, h.nu.n + h.toen.n, h.par]) : null; }", [club, baan])
            hid, pars = BAAN[(club, baan)][0], BAAN[(club, baan)][1]
            check(f"baananalyse {club} · {baan}: eigen holes, eigen par, {n} rondes", d == [[hid[i], n, pars[i]] for i in range(9)], str(d)[:160])

        print("=== 3. STATISTIEK EN RONDES ===")
        await pg.locator('#tab-stat').click(); await pg.wait_for_timeout(300)
        for k in await pg.locator('#screen-stat [onclick*="toggleCourseList("], #screen-stat [onclick*="toggleClub"]').all():
            if await k.is_visible(): await k.click(); await pg.wait_for_timeout(80)
        st = await pg.evaluate("() => document.getElementById('playerStats').innerText")
        check("Statistiek noemt beide clubs apart", 'Club A' in st and 'Club B' in st)
        await pg.locator('#tab-archive').click(); await pg.wait_for_timeout(200)
        await pg.locator('#screen-archive [onclick*="toggleGroupByTrack("]').click(); await pg.wait_for_timeout(300)
        groepen = await pg.evaluate("""() => { const u = {}; const s = loadSavedRounds();
            s.forEach(r => { const k = (r.club || 'Onbekend') + ' | ' + (r.track || 'Onbekend'); u[k] = (u[k] || 0) + 1; }); return u; }""")
        kop = await pg.evaluate("() => document.getElementById('screen-archive').innerText")
        plat = ' | '.join(x.strip() for x in kop.split('\n') if x.strip()).upper()
        check("Rondes per baan: op het scherm staat elke club met zijn eigen banen en aantallen",
              'CLUB A | 13 | NOORD | 8 | ZUID | 5' in plat and 'CLUB B | 10' in plat, plat[:200])
        for (club, baan), n in AANTAL.items():
            check(f"Rondes per baan: {club} heeft {n} rondes op {baan}", groepen.get(f"{club} | {baan}") == n, str(groepen))
        await pg.locator('#screen-archive [onclick*="toggleGroupByTrack("]').click(); await pg.wait_for_timeout(150)

        print("=== 4. CORRIGEREN BIJ DE ANDERE CLUB ===")
        vanA = await pg.evaluate("() => JSON.stringify(loadSavedRounds().filter(r => r.club === 'Club A'))")
        rid = next(r['id'] for r in rondes() if r['club'] == 'Club B' and r['track'] == 'Noord')
        await pg.evaluate("(id) => herplanRonde(id, true)", rid); await pg.wait_for_timeout(300)
        s = await pg.evaluate("() => ({ club: localStorage.getItem('golf_default_club'), baan: sel.track, hole1: COURSES[sel.track].holeIds[0], cr: COURSES[sel.track].tees.Heren.Geel.CR })")
        check("corrigeren: het startscherm staat op Noord van Club B", s == {'club': 'Club B', 'baan': 'Noord', 'hole1': 'BN1', 'cr': 37.0}, str(s))
        await pg.evaluate("() => { startRound(); for (const id of ['confirmModalBtn', 'keuzeModalKnop2']) { const k = document.getElementById(id); if (k && k.offsetParent) k.click(); } }"); await pg.wait_for_timeout(300)
        g = await pg.evaluate("() => game.started ? { club: game.club, baan: game.track, CR: game.CR, SR: game.SR, hole1: game.holes[0].id, par1: game.holes[0].par } : null")
        check("corrigeren: de gestarte ronde heeft de gegevens van Club B", g == {'club': 'Club B', 'baan': 'Noord', 'CR': 37.0, 'SR': 135, 'hole1': 'BN1', 'par1': 5}, str(g))
        check("corrigeren: de rondes van Club A zijn gelijk gebleven", await pg.evaluate("() => JSON.stringify(loadSavedRounds().filter(r => r.club === 'Club A'))") == vanA)
        await pg.evaluate("() => { clearActiveRound(); document.querySelectorAll('[id$=Modal]:not(.hidden)').forEach(m => m.classList.add('hidden')); }")

        print("=== 5. DE BAAN VERWIJDEREN BIJ CLUB B ===")
        await pg.evaluate("() => { nav('club'); openClubEditor('Club B'); openCourseEditor('Noord'); }"); await pg.wait_for_timeout(200)
        k = pg.locator('[onclick="deleteCourseFromEditor(this)"]')
        await k.click(); await pg.wait_for_timeout(120); await k.click(); await pg.wait_for_timeout(250)
        await pg.locator('#dangerModalConfirmBtn').click(); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ b: 'Noord' in CLUBS['Club B'].courses, a: CLUBS['Club A'].courses.Noord ? CLUBS['Club A'].courses.Noord.holeIds[0] : null })")
        check("verwijderen: Club B is Noord kwijt, Club A heeft de zijne nog", r == {'b': False, 'a': 'AN1'}, str(r))
        await pg.evaluate("() => { document.querySelectorAll('[id$=Overlay]:not(.hidden)').forEach(m => m.classList.add('hidden')); setDefaultClub('Club A'); nav('setup'); }"); await pg.wait_for_timeout(200)
        s = await pg.evaluate("() => ({ banen: Object.keys(COURSES).sort(), hole1: COURSES.Noord ? COURSES.Noord.holeIds[0] : null })")
        check("verwijderen: het startscherm van Club A toont nog Noord en Zuid, met eigen holes", s == {'banen': ['Noord', 'Zuid'], 'hole1': 'AN1'}, str(s))
        check("geen fouten in de pagina", not pf, str(pf[:3]))
        await pg.close()

        print("=== 6. UNIEKE BAANNAMEN: DE CLUB STAAT ER NIET BIJ ===")
        pg, pf = await pagina(b, clubs(namen=()), rondes(uniek=True))
        await pg.evaluate("() => { _statChartPeriod = 'alles'; }")
        a = await pg.evaluate(ANALYSE)
        check("bij unieke namen noemt de analyse holes", re.search(r'(Noord|Zuid) [AB] hole \d+', a) is not None, a[:160])
        check("en zet er geen club achter", re.search(r'(Noord|Zuid) [AB] \(Club [AB]\) hole', a) is None)
        check("geen fouten in de pagina (unieke namen)", not pf, str(pf[:3]))
        await pg.close()
        await lussen(b)
        await lus_maken_en_bijwerken(b)
        await lus_hernoemen(b)
        await b.close()
        print(f"\n{geteld[0]} controles.")
        print(f"{len(fouten)} FOUT(EN)" if fouten else "GEEN FOUTEN")
        sys.exit(1 if fouten else 0)

asyncio.run(main())
