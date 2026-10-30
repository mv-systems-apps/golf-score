"""Elk tekstveld van een ronde of club is tekst, ook als het uit een bestand komt.

test-namen-met-tekens.py typt lastige tee- en holenamen in via de editor. Deze test gaat
over alles wat via een backup of clubbestand binnenkomt: daar gelden de filters van de
invoervelden niet. Per doorloop krijgen ALLE tekstvelden tegelijk een waarde die zou
uitbreken als hij ergens onbewerkt in HTML of in een klik-opdracht terechtkomt:

  html    <b data-inj="veld">x</b>            uitbreken uit tekst
  enkel   x' data-inj='veld' y='              uitbreken uit een attribuut met '
  dubbel  x" data-inj="veld" y="              uitbreken uit een attribuut met "
  code    ');window.__inj('veld');//          uitbreken uit een klik-opdracht
  entiteit &#39;);window.__inj('veld');//     idem, via een HTML-code voor de apostrof

Daarna gaan alle schermen langs. Er mag nergens een element met data-inj ontstaan, en in
geen enkele klik-opdracht mag __inj buiten een tekst tussen aanhalingstekens staan.
"""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import app_url

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

VORMEN = {
    'html':     lambda v: f'<b data-inj="{v}">x</b>',
    'enkel':    lambda v: f"x' data-inj='{v}' y='",
    'dubbel':   lambda v: f'x" data-inj="{v}" y="',
    'code':     lambda v: f"');window.__inj('{v}');//",
    'entiteit': lambda v: f"&#39;);window.__inj('{v}');//",
}
PARS = [4, 3, 5, 4, 4, 3, 4, 5, 4]
def gegevens(vorm):
    f = VORMEN[vorm]
    club, kort, baan, tee, geslacht, speler = f('club'), f('clubkort'), f('baan'), f('tee'), 'Heren', f('speler')
    hole_ids = [f('hole') + str(i) for i in range(1, 10)]
    t = {"CR": 35.0, "SR": 120, "holes": [{"par": p, "si": i + 1} for i, p in enumerate(PARS)]}
    clubs = {club: {"club": club, "shortName": kort, "courses": {
                baan: {"holeIds": hole_ids, "tees": {geslacht: {tee: t, "Geel": t}, f('geslacht'): {"Rood": t}}},
                "Gewoon": {"holeIds": [f"G{i}" for i in range(1, 10)], "tees": {geslacht: {"Geel": t}}}}},
             "Gewone club": {"club": "Gewone club", "shortName": "GC", "courses": {"Baan": {"holeIds": [f"H{i}" for i in range(1, 10)], "tees": {"Heren": {"Geel": t}}}}}}
    rondes = []
    for i in range(26):
        holes = [{"id": hole_ids[k], "par": p, "si": k + 1, "phcp": 2 if k < 6 else 1, "ppar": p + (2 if k < 6 else 1), "score": p + (i + k) % 3 + 1, "putts": 2} for k, p in enumerate(PARS)]
        r = {"id": 1000 + i, "date": f"2026-{1 + i // 4:02d}-{1 + (i % 4) * 6:02d}", "time": f('tijd') if i == 3 else f"1{i % 8}:00", "player": speler if i % 7 else f('gast'),
             "hcp": 30.0, "club": club, "clubShort": kort, "track": baan, "gender": f('rgeslacht') if i == 5 else geslacht, "tee": tee, "CR": 35.0, "SR": 120, "PAR": 36, "chcp": 15,
             "qualifying": i % 5 != 0, "pcc": 0, "sdFinal": round(28 + (i * 5) % 9 + 0.3, 1), "note": f('notitie') if i % 6 == 0 else None, "started": True,
             "holesCount": 9, "currentHole": -1, "holes": holes, "total": sum(h['score'] for h in holes), "totalStb": 18}
        if r['note'] is None: del r['note']
        rondes.append(r)
    return clubs, rondes, club, baan, speler

# Staat __inj ergens in een klik-opdracht BUITEN een tekst tussen aanhalingstekens?
STAND = r"""() => { const uit = { elementen: [...document.querySelectorAll('[data-inj]')].map(e => e.dataset.inj + ' in #' + ((e.closest('[id]') || {}).id || '?')), code: [], gelopen: window.__gelopen || [] };
  const zonderTekst = s => s.replace(/'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`/g, "''");
  document.querySelectorAll('*').forEach(e => { for (const a of e.attributes) if (a.name.startsWith('on') && a.value.includes('__inj') && zonderTekst(a.value).includes('__inj'))
      uit.code.push(a.name + ' in #' + ((e.closest('[id]') || {}).id || '?') + ': ' + a.value.slice(0, 90)); });
  return uit; }"""
ALLES_OPEN = """() => { document.querySelectorAll('.screen.active [onclick]').forEach(e => { const o = e.getAttribute('onclick') || '';
   if (/^(event\\.stopPropagation\\(\\);)?\\s*(toggle\\w*|window\\._\\w+Collapsed)/.test(o) && !/Analysis|Export|export|delete|Delete|Actions/.test(o)) { try { e.click(); } catch (x) {} } }); }"""

async def doorloop(b, vorm, via_import):
    clubs, rondes, club, baan, speler = gegevens(vorm)
    pg = await b.new_page(viewport={"width": 390, "height": 844})
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
    await pg.add_init_script("window.__gelopen = []; window.__inj = v => window.__gelopen.push(v);")
    await pg.goto(app_url())
    if via_import:
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('golf_kenmerk_gevraagd', '1'); localStorage.setItem('golf_rounds', '[]'); }")
        await pg.reload(); await pg.wait_for_timeout(500)
        d = tempfile.mkdtemp()
        json.dump(list(clubs.values()), open(os.path.join(d, 'clubs.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        for r in rondes: r.pop('id', None)
        json.dump(rondes, open(os.path.join(d, 'rondes.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        async def knoppen():
            for _ in range(4):
                k = pg.locator('#confirmModal:not(.hidden) button:visible, #keuzeModal:not(.hidden) button:visible').filter(has_text='Sluiten').or_(pg.locator('#confirmModal:not(.hidden) #confirmModalBtn:visible'))
                if await k.count(): await k.first.click(); await pg.wait_for_timeout(250)
                else: break
        await pg.evaluate("() => nav('club')"); await pg.locator('#importClubFile').set_input_files(os.path.join(d, 'clubs.json')); await pg.wait_for_timeout(500); await knoppen()
        await pg.evaluate("() => nav('settings')"); await pg.locator('#importRoundFile').set_input_files(os.path.join(d, 'rondes.json')); await pg.wait_for_timeout(700); await knoppen()
        binnen = await pg.evaluate("() => [Object.keys(JSON.parse(localStorage.getItem('golf_clubs') || '{}')).length, JSON.parse(localStorage.getItem('golf_rounds') || '[]').length]")
        await pg.evaluate("([s, c]) => { localStorage.setItem('golf_profile_name', s); if (JSON.parse(localStorage.getItem('golf_clubs') || '{}')[c]) { localStorage.setItem('golf_default_club', c); localStorage.setItem('golf_home_club', c); } }", [speler, club])
    else:
        await pg.evaluate("""([c, r, s, club]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify(c)); localStorage.setItem('golf_rounds', JSON.stringify(r));
          localStorage.setItem('golf_default_club', club); localStorage.setItem('golf_home_club', club); localStorage.setItem('golf_profile_name', s); localStorage.setItem('golf_kenmerk_gevraagd', '1');
          localStorage.setItem('golf_track_putts', 'on'); localStorage.setItem('golf_last_backup_date', '2026-10-01'); }""", [clubs, rondes, speler, club])
        binnen = [len(clubs), len(rondes)]
    await pg.reload(); await pg.wait_for_timeout(700)
    gevonden = {'elementen': set(), 'code': set(), 'gelopen': set()}
    async def kijk(waar):
        s = await pg.evaluate(STAND)
        for k in gevonden:
            for x in s[k]: gevonden[k].add(f"{waar}: {x}")
    stappen = [
        ("start", "() => { nav('setup'); if (!player2Visible) togglePlayer2(); }"),
        ("rondes", "() => nav('archive')"), ("rondes open", ALLES_OPEN),
        ("rondes per speler", "() => { try { toggleGroupByPlayer(); } catch (e) {} }"), ("rondes per speler open", ALLES_OPEN),
        ("rondes per club", "() => { try { toggleGroupByTrack(); } catch (e) {} }"), ("rondes per club open", ALLES_OPEN),
        ("rondes per categorie", "() => { try { toggleGroupByCategory(); } catch (e) {} }"), ("rondes per categorie open", ALLES_OPEN),
        ("rondes zoeken", "() => { const z = document.getElementById('archiveSearch'); if (z) { z.value = 'x'; zoekInRondes(); } }"),
        ("statistiek", "() => { _statChartPeriod = 'alles'; nav('stat'); }"), ("statistiek open", ALLES_OPEN),
        ("spelanalyse", "() => { try { openGameAnalysis(); } catch (e) {} }"),
        ("clubs", "() => { document.querySelectorAll('[id$=Overlay]:not(.hidden) button, [id$=Modal]:not(.hidden) button').forEach(k => { if (/sluit|×|✕/i.test(k.textContent + (k.title || ''))) k.click(); }); nav('club'); }"),
        ("clubs open", """() => { document.querySelectorAll('#screen-club [onclick*="toggleCourseList("], #screen-club [onclick*="toggleClubSubGroup("], #screen-club [onclick*="toggleClubActions("]').forEach(e => { try { e.click(); } catch (x) {} });
                          document.querySelectorAll('#screen-club [onclick*="toggleCourseAnalysis("]').forEach(e => { try { e.click(); } catch (x) {} }); }"""),
        ("clubs zoeken", "() => { const z = document.getElementById('clubSearch') || document.querySelector('#screen-club input[type=text]'); if (z) { z.value = 'x'; z.dispatchEvent(new Event('input', { bubbles: true })); } }"),
        ("clubeditor", "(c) => { try { openClubEditor(c[0]); } catch (e) {} }"),
        ("baaneditor", "(c) => { try { openCourseEditor(c[1]); ['tees', 'holes'].forEach(k => { const w = document.getElementById(k === 'tees' ? 'editorTeesWrap' : 'editorHolesWrap'); if (w && w.classList.contains('hidden')) toggleEditorSection(k); }); } catch (e) {} }"),
        ("nieuwe lus", "(c) => { try { closeCourseEditor(); openLusMaker(); kiesLusBron(c[1]); } catch (e) {} }"),
        ("instellingen", "() => { try { sluitLusMaker(); closeClubEditor(); } catch (e) {} nav('settings'); }"),
        ("ronde starten", """(c) => { nav('setup'); sel.track = c[1]; rebuildAll(); document.getElementById('iHcp').value = '30.0'; onHcpBlur(document.getElementById('iHcp'));
            document.getElementById('iName2').value = 'Partner'; document.getElementById('iHcp2').value = '18'; startRound();
            for (let k = 0; k < 3; k++) { const m = document.getElementById('confirmModal'); if (m && !m.classList.contains('hidden')) document.getElementById('confirmModalBtn').click(); }
            if (game.started) { nav('score'); for (let h = 0; h < game.holes.length; h++) { setCurrentHole(h); selectHole(h); armScoreChange(h, 5); clearScoreTap(false); } } }"""),
        ("scorekaart", "() => 0"), ("rondes met lopende ronde", "() => nav('archive')"), ("statistiek met lopende ronde", "() => nav('stat')"),
    ]
    for naam, js in stappen:
        try: await pg.evaluate(js, [club, baan])
        except Exception as e: pf.append(f"{naam}: {str(e)[:120]}")
        await pg.wait_for_timeout(280); await kijk(naam)
    gestart = await pg.evaluate("() => !!game.started")
    await pg.close()
    return binnen, gestart, gevonden, pf

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for via_import in (False, True):
            print(f"\n=== {'VIA DE ECHTE IMPORT' if via_import else 'RECHTSTREEKS IN DE OPSLAG'} ===\n")
            for vorm in VORMEN:
                binnen, gestart, g, pf = await doorloop(b, vorm, via_import)
                print(f"   vorm '{vorm}': {binnen[0]} clubs en {binnen[1]} rondes in de opslag, ronde gestart: {gestart}")
                if not via_import: check(f"{vorm}: de gegevens staan er en er is een ronde gestart", (binnen, gestart), ([2, 26], True))
                check(f"{vorm}: nergens een element uit een veld ontstaan", sorted(g['elementen'])[:12], [])
                check(f"{vorm}: in geen klik-opdracht staat een veld als code", sorted(g['code'])[:12], [])
                check(f"{vorm}: er is geen code uit een veld uitgevoerd", sorted(g['gelopen'])[:12], [])
                check(f"{vorm}: geen fouten in de pagina", pf[:6], [])
        print("\n=== KNOPPEN MET EEN GEWONE NAAM VOL LEESTEKENS BLIJVEN WERKEN ===\n")
        CLUB, BAAN = 'Golf & Country "d\'Or" <1>', 'Noord & Zuid \'A\' "B" \\ <2>'
        clubs, rondes, club0, baan0, speler = gegevens('html')
        c = json.loads(json.dumps(clubs[club0])); c['club'] = CLUB; c['shortName'] = 'G&C'; c['courses'] = {BAAN: c['courses'][baan0]}
        for r in rondes: r['club'] = CLUB; r['clubShort'] = 'G&C'; r['track'] = BAAN; r['player'] = 'Testspeler'; r['time'] = '10:00'; r['tee'] = 'Geel'; r['gender'] = 'Heren'; r.pop('note', None)
        pg = await b.new_page(viewport={"width": 390, "height": 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:140]))
        await pg.goto(app_url())
        await pg.evaluate("""([c, r, club]) => { localStorage.clear(); localStorage.setItem('golf_clubs', JSON.stringify({ [club]: c })); localStorage.setItem('golf_rounds', JSON.stringify(r));
          localStorage.setItem('golf_default_club', club); localStorage.setItem('golf_home_club', club); localStorage.setItem('golf_profile_name', 'Testspeler'); localStorage.setItem('golf_kenmerk_gevraagd', '1'); }""", [c, rondes, CLUB])
        await pg.reload(); await pg.wait_for_timeout(600)
        await pg.evaluate("""() => { window.__aanroep = []; for (const f of ['toggleCourseAnalysis', 'openCourseEditor', 'exportClub', 'selectClubSearchCandidate']) { const o = window[f];
            window[f] = function (...a) { window.__aanroep.push([f, ...a.filter(x => typeof x === 'string')]); if (f !== 'exportClub') return o.apply(this, a); }; } nav('club');
            document.querySelectorAll('#screen-club [onclick*="toggleCourseList("], #screen-club [onclick*="toggleClubSubGroup("], #screen-club [onclick*="toggleClubActions("]').forEach(e => e.click()); }""")
        await pg.wait_for_timeout(300)
        for kies in ('[onclick*="toggleCourseAnalysis("]', '[onclick*="exportClub("]'):
            # De klik-opdracht van de knop zelf uitvoeren, zoals een tik dat doet.
            await pg.evaluate("(s) => { const k = document.querySelector('#screen-club ' + s); if (k) k.click(); }", kies); await pg.wait_for_timeout(250)
        await pg.evaluate("(c) => openClubEditor(c)", CLUB); await pg.wait_for_timeout(250)
        await pg.evaluate("() => { document.querySelectorAll('#clubCourseList [onclick*=\"toggleClubCourseGroup(\"]').forEach(e => e.click()); }"); await pg.wait_for_timeout(200)
        await pg.evaluate('''() => { const k = document.querySelector('#clubCourseList [onclick*="openCourseEditor("]'); if (k) k.click(); }'''); await pg.wait_for_timeout(300)
        aan = await pg.evaluate("() => window.__aanroep")
        check("baananalyse: de knop geeft club en baan letterlijk door", [a for a in aan if a[0] == 'toggleCourseAnalysis'][:1], [['toggleCourseAnalysis', CLUB, BAAN]])
        check("exporteren: de knop geeft de clubnaam letterlijk door", [a for a in aan if a[0] == 'exportClub'][:1], [['exportClub', CLUB]])
        check("baan bewerken: de knop geeft de baannaam letterlijk door", [a for a in aan if a[0] == 'openCourseEditor'][:1], [['openCourseEditor', BAAN]])
        check("en de baaneditor staat open op die baan", await pg.evaluate("() => document.getElementById('editorCourseName').value"), BAAN)
        check("geen fouten in de pagina", pf, [])
        await pg.close()
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
    sys.exit(1 if fouten else 0)
asyncio.run(main())
